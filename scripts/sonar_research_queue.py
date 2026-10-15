#!/usr/bin/env python3
"""Validate and publish the ordered SONAR research queue; never marks absent evidence complete."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "reports" / "sequence_agent" / "research_backlog.json"
STATUS = ROOT / "reports" / "sequence_agent" / "research_queue_status.json"

def main():
    plan = json.loads(BACKLOG.read_text(encoding="utf-8"))
    tasks = plan.get("tasks", [])
    by_id = {t["id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise SystemExit("QUEUE_INVALID: duplicate task id")
    for task in tasks:
        missing = [dep for dep in task.get("depends_on", []) if dep not in by_id]
        if missing:
            raise SystemExit(f"QUEUE_INVALID: {task['id']} has unknown dependencies {missing}")
    # Detect dependency cycles with a DFS before scheduling.
    visiting, visited = set(), set()
    def visit(task_id):
        if task_id in visiting:
            raise SystemExit(f"QUEUE_INVALID: dependency cycle at {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in by_id[task_id].get("depends_on", []):
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in by_id:
        visit(task_id)

    states = {}
    for task in sorted(tasks, key=lambda t: (t["priority"], t["id"])):
        missing_evidence = [p for p in task.get("evidence", []) if not (ROOT / p).is_file()]
        deps = [states[d]["status"] for d in task.get("depends_on", [])]
        if missing_evidence:
            status = "READY" if all(s == "COMPLETE" for s in deps) else "BLOCKED_BY_DEPENDENCY"
        else:
            status = "EVIDENCE_PRESENT_REQUIRES_VALIDATION"
        # Only Q00 can be marked complete automatically, after validating actual data and metrics.
        if task["id"] == "Q00" and not missing_evidence:
            import csv
            data = ROOT / "data" / "storico_daily.csv"
            with data.open(newline="", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            if not rows or rows[0][:6] not in (["data", "n1", "n2", "n3", "n4", "n5"], ["date", "n1", "n2", "n3", "n4", "n5"]):
                raise SystemExit(f"QUEUE_BLOCKED: canonical CSV header invalid: {rows[0][:6] if rows else 'EMPTY'}")
            seen, previous, count = set(), "", 0
            for row in rows[1:]:
                if not row:
                    continue
                if len(row) < 6:
                    raise SystemExit("QUEUE_BLOCKED: malformed canonical row")
                d, nums = row[0], [int(v) for v in row[1:6]]
                if d in seen or (previous and d <= previous):
                    raise SystemExit("QUEUE_BLOCKED: duplicate or non-chronological dates")
                if len(set(nums)) != 5 or nums != sorted(nums) or any(n < 1 or n > 40 for n in nums):
                    raise SystemExit(f"QUEUE_BLOCKED: invalid quintet at {d}")
                seen.add(d); previous = d; count += 1
            metrics = json.loads((ROOT / "reports/sequence_agent/latest_metrics.json").read_text(encoding="utf-8"))
            if metrics.get("data_last_date") != previous or metrics.get("total_draws") != count:
                raise SystemExit("QUEUE_BLOCKED: latest metrics do not match canonical archive")
            status = "COMPLETE"
        states[task["id"]] = {
            "id": task["id"], "priority": task["priority"], "title": task["title"],
            "status": status, "depends_on": task.get("depends_on", []),
            "missing_evidence": missing_evidence,
            "acceptance_criteria": task.get("acceptance", [])
        }

    ready = [s["id"] for s in states.values() if s["status"] == "READY"]
    active = ready[0] if ready else None
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": plan["project"],
        "queue_status": "QUEUE_VALID" if len(visited) == len(tasks) else "QUEUE_INVALID",
        "task_count": len(tasks),
        "complete_count": sum(s["status"] == "COMPLETE" for s in states.values()),
        "ready_count": len(ready),
        "active_next_task": active,
        "active_next_task_title": states[active]["title"] if active else None,
        "tasks": list(states.values()),
        "guardrail": "Queue registration and evidence-file presence are not proof of a successful statistical result. Analyses remain incomplete until implementation, validation and OOS criteria pass."
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("queue_status","task_count","complete_count","ready_count","active_next_task","active_next_task_title")}, ensure_ascii=False))

if __name__ == "__main__":
    main()
