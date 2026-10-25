#!/usr/bin/env python3
"""Validate and publish the ordered SONAR research queue; never marks absent evidence complete."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "reports" / "sequence_agent" / "research_backlog.json"
STATUS = ROOT / "reports" / "sequence_agent" / "research_queue_status.json"


def validate_q70():
    """Fail-closed acceptance validation for the exhaustive formula and walk-forward artifacts."""
    import csv
    import math
    import subprocess
    import sys
    import tempfile
    from datetime import date, timedelta

    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import sonar_exhaustive_formula_lab as lab

    catalog_manifest_path = ROOT / "reports/sequence_agent/exhaustive_formula_catalog_manifest.json"
    catalog_manifest = json.loads(catalog_manifest_path.read_text(encoding="utf-8"))
    dates, draws = lab.read_archive()
    total = len(draws)
    if catalog_manifest.get("status") != "EXHAUSTIVE_FINITE_GRAMMAR_COMPLETE":
        raise ValueError("Q70: formula catalog manifest status is not complete")
    if catalog_manifest.get("history_draws") != total or catalog_manifest.get("history_last_date") != dates[-1]:
        raise ValueError("Q70: formula catalog cutoff does not match the canonical archive")
    expected_target = (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat()
    if catalog_manifest.get("target_date") != expected_target or catalog_manifest.get("target_cutoff_date") != dates[-1]:
        raise ValueError("Q70: next-target catalog has an invalid target/cutoff boundary")
    if catalog_manifest.get("candidate_universe_size") != 658008 or catalog_manifest.get("formula_count") != 1023:
        raise ValueError("Q70: candidate or formula count mismatch")

    storage = catalog_manifest.get("storage_layout", {})
    formula_parts = storage.get("formulas_stored_in_parts", [])
    ledger_parts = storage.get("historical_condition_ledger_parts", [])
    if len(formula_parts) != 11 or len(ledger_parts) != 10:
        raise ValueError("Q70: formula/condition-ledger partition manifest is incomplete")

    formulas = []
    for part in formula_parts:
        path = ROOT / part["path"]
        if not path.is_file():
            raise ValueError(f"Q70: missing formula chunk {part['path']}")
        chunk = json.loads(path.read_text(encoding="utf-8"))
        entries = chunk.get("formulas", [])
        if len(entries) != part.get("formula_count") or chunk.get("formula_count") != 1023:
            raise ValueError(f"Q70: formula chunk count mismatch in {part['path']}")
        formulas.extend(entries)
    masks = [entry.get("formula_mask") for entry in formulas]
    if len(formulas) != 1023 or set(masks) != set(range(1, 1024)) or len(set(masks)) != 1023:
        raise ValueError("Q70: formula masks are missing or duplicated")
    for entry in formulas:
        top20 = entry.get("top20", [])
        if len(top20) != 20:
            raise ValueError(f"Q70: {entry.get('formula_id')} does not contain exactly 20 candidates")
        candidates = []
        for candidate in top20:
            numbers = candidate.get("numbers", [])
            if len(numbers) != 5 or numbers != sorted(set(numbers)) or any(n < 1 or n > 40 for n in numbers):
                raise ValueError(f"Q70: invalid candidate in {entry.get('formula_id')}")
            candidates.append(tuple(numbers))
            if not math.isfinite(float(candidate.get("score", float("nan")))):
                raise ValueError(f"Q70: non-finite score in {entry.get('formula_id')}")
        if len(set(candidates)) != 20:
            raise ValueError(f"Q70: duplicate candidate within {entry.get('formula_id')} Top20")

    # Recompute the condition ledger from the canonical archive in a temporary directory.
    old_out, old_ledger = lab.OUT, lab.LEDGER
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            lab.OUT = Path(temp_dir)
            lab.LEDGER = Path(temp_dir) / "condition_ledger.csv"
            expected_rows = lab.build_condition_ledger(dates, draws)["rows"]
    finally:
        lab.OUT, lab.LEDGER = old_out, old_ledger
    actual_rows = []
    expected_header = list(expected_rows[0].keys()) if expected_rows else []
    for part in ledger_parts:
        path = ROOT / part["path"]
        if not path.is_file():
            raise ValueError(f"Q70: missing condition-ledger chunk {part['path']}")
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != expected_header:
                raise ValueError(f"Q70: condition-ledger schema mismatch in {part['path']}")
            rows = list(reader)
        if len(rows) != part.get("data_rows"):
            raise ValueError(f"Q70: condition-ledger row count mismatch in {part['path']}")
        actual_rows.extend(rows)
    if len(actual_rows) != total or len(expected_rows) != total:
        raise ValueError(f"Q70: expected {total} ledger rows, got {len(actual_rows)}")
    for index, (actual, expected) in enumerate(zip(actual_rows, expected_rows)):
        for key, value in expected.items():
            if actual.get(key) != str(value):
                raise ValueError(f"Q70: prior-only ledger mismatch at target index {index}, field {key}")
        if index and actual.get("cutoff_date", "") >= actual.get("target_date", ""):
            raise ValueError(f"Q70: target leakage at ledger index {index}")

    # Re-run the authoritative aggregator: it checks every rank row, canonical pairing,
    # all 34 batches, split sizes, and the 3,069-test Holm family.
    aggregate = subprocess.run(
        [sys.executable, str(ROOT / "scripts/aggregate_sonar_exhaustive_walkforward.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    if aggregate.returncode:
        raise ValueError("Q70: walk-forward aggregation failed: " + (aggregate.stderr or aggregate.stdout)[-3000:])
    metrics_path = ROOT / "reports/sequence_agent/exhaustive_formula_walkforward_metrics.json"
    walk_manifest_path = ROOT / "reports/sequence_agent/exhaustive_formula_walkforward_manifest.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    walk_manifest = json.loads(walk_manifest_path.read_text(encoding="utf-8"))
    if metrics.get("status") != "COMPLETE_EXHAUSTIVE_WALKFORWARD":
        raise ValueError("Q70: walk-forward metrics status is not complete")
    if metrics.get("target_count") != total or metrics.get("scored_target_count") != total - 1:
        raise ValueError("Q70: walk-forward target count does not match canonical history")
    if metrics.get("candidate_universe_size") != 658008 or metrics.get("formula_count") != 1023:
        raise ValueError("Q70: walk-forward universe/formula count mismatch")
    if len(metrics.get("formula_metrics", [])) != 1023 or metrics.get("multiple_testing", {}).get("tests") != 3069:
        raise ValueError("Q70: walk-forward formula metrics or Holm family incomplete")
    if walk_manifest.get("status") != "VALIDATED_COMPLETE" or walk_manifest.get("target_count") != total:
        raise ValueError("Q70: walk-forward manifest failed validation")
    if len(walk_manifest.get("parts", [])) != math.ceil(total / 100):
        raise ValueError("Q70: walk-forward batch count mismatch")
    return {
        "status": "PASS",
        "validation_errors": [],
        "checks": {
            "canonical_targets": total,
            "formula_masks": len(set(masks)),
            "candidate_universe": 658008,
            "condition_ledger_rows_recomputed_and_matched": len(actual_rows),
            "walkforward_rank_rows": total - 1,
            "walkforward_batch_parts": len(walk_manifest["parts"]),
            "holm_tests": metrics["multiple_testing"]["tests"],
            "current_catalog_target": catalog_manifest["target_date"],
        },
    }

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
        acceptance_validation = "NOT_RUN"
        validation_errors = []
        validation_details = None
        if task["id"] == "Q70":
            if missing_evidence:
                acceptance_validation = "BLOCKED_MISSING_EVIDENCE"
            else:
                try:
                    validation_details = validate_q70()
                    status = "COMPLETE"
                    acceptance_validation = "PASS"
                except (Exception, SystemExit) as exc:
                    status = "VALIDATION_FAILED"
                    acceptance_validation = "FAIL"
                    validation_errors = [str(exc)]
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
            "acceptance_validation": acceptance_validation,
            "validation_errors": validation_errors,
            "validation_details": validation_details,
            "acceptance_criteria": task.get("acceptance", [])
        }

    ready = [s["id"] for s in states.values() if s["status"] == "READY"]
    actionable = [
        s for s in states.values()
        if s["status"] in ("READY", "EVIDENCE_PRESENT_REQUIRES_VALIDATION", "VALIDATION_FAILED")
        and all(states[dep]["status"] == "COMPLETE" for dep in s["depends_on"])
    ]
    active_task = actionable[0] if actionable else None
    active = active_task["id"] if active_task else None
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": plan["project"],
        "queue_status": "QUEUE_VALIDATION_FAILED" if any(s["status"] == "VALIDATION_FAILED" for s in states.values()) else ("QUEUE_VALID" if len(visited) == len(tasks) else "QUEUE_INVALID"),
        "completion_gate": "CLOSED" if all(s["status"] == "COMPLETE" for s in states.values()) else "OPEN",
        "task_count": len(tasks),
        "complete_count": sum(s["status"] == "COMPLETE" for s in states.values()),
        "ready_count": len(ready),
        "actionable_count": len(actionable),
        "active_next_task": active,
        "active_next_task_title": active_task["title"] if active_task else None,
        "active_next_task_action": (
            "VALIDATE_EXISTING_EVIDENCE"
            if active_task and active_task["status"] == "EVIDENCE_PRESENT_REQUIRES_VALIDATION"
            else ("COLLECT_MISSING_EVIDENCE" if active_task else None)
        ),
        "tasks": list(states.values()),
        "guardrail": "Queue registration and evidence-file presence are not proof of a successful statistical result. Analyses remain incomplete until implementation, validation and OOS criteria pass."
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("SONAR_RESEARCH_QUEUE_REPORT_BEGIN")
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_RESEARCH_QUEUE_REPORT_END")
    print(json.dumps({k: output[k] for k in ("queue_status","completion_gate","task_count","complete_count","ready_count","actionable_count","active_next_task","active_next_task_title","active_next_task_action")}, ensure_ascii=False))
    failures = [s for s in states.values() if s["status"] == "VALIDATION_FAILED"]
    if failures:
        raise SystemExit("QUEUE_VALIDATION_FAILED: " + "; ".join(f"{s['id']}: {s['validation_errors']}" for s in failures))

if __name__ == "__main__":
    main()
