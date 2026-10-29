#!/usr/bin/env python3
"""Fail-closed acceptance validation for persisted Q80-Q83 formula outputs."""
from __future__ import annotations
import csv
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sonar_research_queue import validate_q80, validate_q81, validate_q82, validate_q83

DATA = ROOT / "data" / "storico_daily.csv"
REPORTS = {
    "Q80": ROOT / "reports/sequence_agent/per_number_condition_grammar.json",
    "Q81": ROOT / "reports/sequence_agent/per_number_condition_4plus_grammar.json",
    "Q82": ROOT / "reports/sequence_agent/per_number_condition_conditional_grammar.json",
    "Q83": ROOT / "reports/sequence_agent/per_number_condition_5plus_grammar.json",
}
OUTPUT_PATHS = {
    "Q80": ("reports/sequence_agent/per_number_condition_formula_metrics.csv",
            "reports/sequence_agent/per_number_condition_target_ledger.csv"),
    "Q81": ("reports/sequence_agent/per_number_condition_4plus_formula_metrics.csv",
            "reports/sequence_agent/per_number_condition_4plus_target_ledger.csv"),
    "Q82": ("reports/sequence_agent/per_number_condition_conditional_metrics.csv",
            "reports/sequence_agent/per_number_condition_conditional_target_ledger.csv"),
    "Q83": ("reports/sequence_agent/per_number_condition_5plus_formula_metrics.csv",
            "reports/sequence_agent/per_number_condition_5plus_target_ledger.csv"),
}
QUEUE = ROOT / "reports/sequence_agent/research_queue_status.json"
CHECKPOINT = ROOT / "reports/sequence_agent/per_number_condition_research_checkpoint.json"
ARCHIVE_REPORT = ROOT / "reports/sequence_agent/archive_reconciliation_2026-10-28.json"


def git_blob_sha(path: str) -> str:
    return subprocess.run(
        ["git", "hash-object", path], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, text=True
    ).stdout.strip()


def main_archive_blob_sha() -> str:
    repository = os.environ.get("GITHUB_REPOSITORY", "jamesnuvola/vincicasa-lab")
    url = f"https://api.github.com/repos/{repository}/contents/data/storico_daily.csv?ref=main"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "VinciCasa-SONAR-archive-reconciliation",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["sha"]


def main():
    errors = validate_q80() + validate_q81() + validate_q82() + validate_q83()
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    tasks = {item.get("id"): item for item in queue.get("tasks", [])}
    for task_id in ("Q80", "Q81", "Q82", "Q83"):
        item = tasks.get(task_id)
        if not item or item.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW" or item.get("validation_errors"):
            errors.append(task_id + " is not validated/pending human review")
    if queue.get("queue_status") != "QUEUE_VALID":
        errors.append("research queue is not QUEUE_VALID")

    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        archive_rows = list(csv.DictReader(handle))
    if not archive_rows:
        errors.append("canonical archive is empty")
        branch_blob_sha = ""
        main_blob_sha = ""
    else:
        branch_blob_sha = git_blob_sha("data/storico_daily.csv")
        try:
            main_blob_sha = main_archive_blob_sha()
            if main_blob_sha != branch_blob_sha:
                errors.append("research branch archive blob differs from canonical main archive")
        except Exception as exc:
            errors.append("could not verify canonical main archive blob: " + str(exc))
            main_blob_sha = ""

    if errors:
        raise SystemExit("Q80_Q81_Q82_Q83_ACCEPTANCE_BLOCKED: " + "; ".join(errors))

    event = os.environ.get("GITHUB_EVENT_NAME", "")
    update_checkpoint = event != "workflow_dispatch" or os.environ.get("SONAR_UPDATE_CHECKPOINT") == "1"
    if update_checkpoint:
        now = datetime.now(timezone.utc).isoformat()
        run_id = os.environ.get("GITHUB_RUN_ID", "local")
        head = os.environ.get("GITHUB_SHA", "local")
        first = archive_rows[0]["data"]
        last_row = archive_rows[-1]
        last_date = last_row["data"]
        last_draw = [int(last_row["n" + str(i)]) for i in range(1, 6)]
        count = len(archive_rows)

        cp = json.loads(CHECKPOINT.read_text(encoding="utf-8")) if CHECKPOINT.is_file() else {}
        milestones = {item["id"]: item for item in cp.get("verified_milestones", []) if item.get("id")}
        for task_id, report_path in REPORTS.items():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            metrics_path, ledger_path = OUTPUT_PATHS[task_id]
            item = milestones.get(task_id, {"id": task_id, "first_verified_at_utc": now})
            item.update({
                "status": "VALIDATED_PENDING_HUMAN_REVIEW",
                "archive_cutoff": report.get("last_date"),
                "target_count": report.get("target_count"),
                "scored_targets": report.get("scored_targets"),
                "feature_count": len(report.get("features", [])),
                "formula_count": report.get("formula_count"),
                "metrics_rows": report.get("metrics_rows"),
                "target_ledger_rows": report.get("target_ledger_rows"),
                "multiple_testing": report.get("multiple_testing"),
                "review_status": report.get("review_status", "PENDING_HUMAN_REVIEW_INTEGRATION"),
                "last_artifact_validation_at_utc": now,
                "last_artifact_validation_run_id": run_id,
                "last_artifact_validation_head_sha": head,
                "exact_head_ci_status": "PENDING",
                "outputs": {
                    "report_blob_sha": git_blob_sha(str(REPORTS[task_id].relative_to(ROOT))),
                    "metrics_blob_sha": git_blob_sha(metrics_path),
                    "target_ledger_blob_sha": git_blob_sha(ledger_path),
                },
            })
            milestones[task_id] = item

        cp.update({
            "schema_version": "1.0",
            "project": "VinciCasa SONAR",
            "generated_at_utc": now,
            "archive_snapshot": {
                "source_archive": "data/storico_daily.csv",
                "source_blob_sha": branch_blob_sha,
                "canonical_main_archive_blob_sha": main_blob_sha,
                "draw_count": count,
                "first_date": first,
                "last_date": last_date,
                "latest_quintet": last_draw,
                "immutable_target_2026_10_25_freeze_overwritten": False,
            },
            "verified_milestones": [milestones[k] for k in sorted(milestones)],
            "current_state": {
                "queue_status": queue.get("queue_status"),
                "overall_cycle_status": queue.get("overall_cycle_status"),
                "blocking_tasks": queue.get("blocking_tasks", []),
                "q80_status": tasks["Q80"].get("status"),
                "q81_status": tasks["Q81"].get("status"),
                "q82_status": tasks["Q82"].get("status"),
                "q83_status": tasks["Q83"].get("status"),
                "human_review_required": True,
                "automatic_promotion": False,
                "exact_head_ci_status": "PENDING",
            },
            "pending_refresh": {
                "workflow": ".github/workflows/ci.yml",
                "scope": ["Q80", "Q81", "Q82", "Q83"],
                "status": "ARTIFACT_VALIDATORS_PASS_PENDING_PERSISTED_HEAD_CI",
                "archive_sha": branch_blob_sha,
                "draw_count": count,
                "last_date": last_date,
                "required_postconditions": [
                    "Q80-Q83 reports, metrics, target ledgers and queue are committed via Git Data API",
                    "each persisted artifact is reread from the exact commit and byte-compared",
                    "workflow_dispatch CI passes on the persisted exact head",
                    "human review/integration occurs before any Q80-Q83 task is marked COMPLETE",
                ],
            },
            "next_stages": [
                {"id": "Q84", "status": "READY", "scope": "event-level strategy atlas: occasional rules, lifecycle and complementarity"},
                {"id": "Q85", "status": "ARCHIVE_SYNCED", "scope": "keep the research branch aligned with canonical main archive"},
            ],
            "guardrails": [
                "only the complete prefix strictly before each target may influence its features",
                "formula universes are exhaustive only within their declared finite grammars",
                "best-per-target formula is retrospective/descriptive and never a prospective forecast",
                "immutable target freezes are append-only and are never overwritten",
                "human review/integration is required before Q80, Q81, Q82 or Q83 can be marked COMPLETE",
                "Q82 thresholds are estimated from discovery feature values only and frozen before validation/blind OOS",
                "Q83 must continue beyond five features under explicit compute budgets; no silent truncation",
                "no formula is promoted automatically",
            ],
        })
        history = cp.setdefault("validation_history", [])
        if not any(str(item.get("run_id")) == str(run_id) and item.get("head_sha") == head for item in history):
            history.append({
                "run_id": run_id,
                "head_sha": head,
                "event_name": event,
                "validated_at_utc": now,
                "status": "PASS_ARTIFACT_VALIDATORS_PENDING_EXACT_HEAD_CI",
                "tasks": ["Q80", "Q81", "Q82", "Q83"],
            })
        CHECKPOINT.write_text(json.dumps(cp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        archive_report = {
            "schema_version": "1.0",
            "task_id": "Q85",
            "status": "ARCHIVE_SYNCED_OUTPUTS_VALIDATED_PENDING_PERSISTED_HEAD_CI",
            "observed_at_utc": now,
            "canonical_main_archive": {
                "path": "data/storico_daily.csv",
                "git_blob_sha": main_blob_sha,
                "draw_count": count,
                "first_date": first,
                "last_date": last_date,
                "last_draw": last_draw,
            },
            "research_branch_archive": {
                "path": "data/storico_daily.csv",
                "git_blob_sha": branch_blob_sha,
                "draw_count": count,
                "first_date": first,
                "last_date": last_date,
                "last_draw": last_draw,
            },
            "delta": {
                "new_draws_on_main_not_yet_in_research_branch": 0,
                "dates": [],
                "draws": [],
                "resolution": "Research branch archive byte-matches canonical main; Q80-Q83 were recomputed from the synchronized archive.",
            },
            "affected_outputs": [
                "Q80: reports/sequence_agent/per_number_condition_grammar.json",
                "Q81: reports/sequence_agent/per_number_condition_4plus_grammar.json",
                "Q82: reports/sequence_agent/per_number_condition_conditional_grammar.json",
                "Q83: reports/sequence_agent/per_number_condition_5plus_grammar.json",
            ],
            "required_action": "Persist outputs via Git Data API, verify exact committed bytes, pass exact-head CI, then complete human review/integration. Do not auto-promote formulas.",
            "freeze_policy": "Append-only; do not overwrite or reconstruct historical or prospective freezes.",
            "immutable_target_2026_10_25_freeze_overwritten": False,
        }
        ARCHIVE_REPORT.write_text(json.dumps(archive_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Q80_Q81_Q82_Q83_ACCEPTANCE_VALIDATED: formula metrics, target cutoffs, archive reconciliation, queue and human-review gates passed")


if __name__ == "__main__":
    main()
