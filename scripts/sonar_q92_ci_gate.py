#!/usr/bin/env python3
"""Select the exact-head CI run for Q92 preflight, ignoring unrelated branch runs."""
from __future__ import annotations
import argparse
import json
import sys
from typing import Any

ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "pending"}

def select_exact_head_run(
    payload: dict[str, Any],
    expected_sha: str,
    expected_branch: str,
    workflow_id: int = 381564482,
) -> dict[str, Any] | None:
    runs = payload.get("workflow_runs", [])
    exact = [
        run for run in runs
        if int(run.get("workflow_id", -1)) == int(workflow_id)
        and run.get("head_sha") == expected_sha
        and run.get("head_branch") == expected_branch
    ]
    if not exact:
        return None
    pull_request_runs = [run for run in exact if run.get("event") == "pull_request"]
    pool = pull_request_runs if pull_request_runs else exact
    active = [run for run in pool if run.get("status") in ACTIVE_STATUSES]
    candidates = active if active else pool
    return max(
        candidates,
        key=lambda run: (
            run.get("created_at", ""),
            int(run.get("run_attempt", 0)),
            int(run.get("id", 0)),
        ),
    )

def format_state(run: dict[str, Any] | None) -> str:
    if run is None:
        return "none|null|null|none"
    return "|".join([
        str(run.get("status", "none")),
        str(run.get("conclusion") or "null"),
        str(run.get("id") or "null"),
        str(run.get("event") or "none"),
    ])

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--workflow-id", type=int, default=381564482)
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    run = select_exact_head_run(payload, args.expected_sha, args.expected_branch, args.workflow_id)
    print(format_state(run))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
