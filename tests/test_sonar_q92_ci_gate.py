#!/usr/bin/env python3
"""Synthetic regressions for exact-head CI run selection in Q92 preflight."""
from __future__ import annotations
import unittest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.sonar_q92_ci_gate import format_state, select_exact_head_run

class ExactHeadRunSelectionTests(unittest.TestCase):
    def make_run(self, run_id, event, status, conclusion, created_at, branch="q92-branch", sha="abc", workflow_id=381564482, attempt=1):
        return {
            "id": run_id, "event": event, "status": status, "conclusion": conclusion,
            "created_at": created_at, "head_branch": branch, "head_sha": sha,
            "workflow_id": workflow_id, "run_attempt": attempt,
        }

    def test_ignores_unrelated_checkpoint_push_with_same_sha(self):
        payload = {"workflow_runs": [
            self.make_run(100, "push", "completed", "cancelled", "2026-11-09T11:50:19Z", branch="checkpoint"),
            self.make_run(99, "pull_request", "in_progress", None, "2026-11-09T11:48:51Z"),
            self.make_run(98, "push", "completed", "cancelled", "2026-11-09T11:48:48Z"),
        ]}
        self.assertEqual(select_exact_head_run(payload, "abc", "q92-branch")["id"], 99)

    def test_prefers_active_pr_run_to_newer_cancelled_pr_run(self):
        payload = {"workflow_runs": [
            self.make_run(102, "pull_request", "completed", "cancelled", "2026-11-09T11:50:19Z"),
            self.make_run(101, "pull_request", "in_progress", None, "2026-11-09T11:48:51Z"),
        ]}
        self.assertEqual(select_exact_head_run(payload, "abc", "q92-branch")["id"], 101)

    def test_latest_completed_pr_attempt_selected_when_no_active(self):
        payload = {"workflow_runs": [
            self.make_run(103, "pull_request", "completed", "success", "2026-11-09T11:50:19Z", attempt=1),
            self.make_run(104, "pull_request", "completed", "failure", "2026-11-09T11:50:19Z", attempt=2),
        ]}
        self.assertEqual(select_exact_head_run(payload, "abc", "q92-branch")["id"], 104)

    def test_falls_back_to_push_when_no_pr_run_exists(self):
        payload = {"workflow_runs": [
            self.make_run(105, "push", "completed", "success", "2026-11-09T11:50:19Z"),
        ]}
        self.assertEqual(select_exact_head_run(payload, "abc", "q92-branch")["id"], 105)

    def test_filters_wrong_sha_workflow_and_branch(self):
        payload = {"workflow_runs": [
            self.make_run(106, "pull_request", "completed", "success", "2026-11-09T11:50:19Z", sha="wrong"),
            self.make_run(107, "pull_request", "completed", "success", "2026-11-09T11:50:19Z", workflow_id=123),
            self.make_run(108, "pull_request", "completed", "success", "2026-11-09T11:50:19Z", branch="other"),
        ]}
        self.assertIsNone(select_exact_head_run(payload, "abc", "q92-branch"))

    def test_format_none(self):
        self.assertEqual(format_state(None), "none|null|null|none")

if __name__ == "__main__":
    unittest.main(verbosity=2)
