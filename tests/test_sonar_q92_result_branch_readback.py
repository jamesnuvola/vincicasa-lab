import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.verify_sonar_q92_result_branch import (
    git_blob_sha,
    status_warnings,
    validate_receipt_summary,
)


class Q92ResultBranchReadbackTests(unittest.TestCase):
    def test_git_blob_sha_matches_git_known_vector(self):
        self.assertEqual(
            git_blob_sha(b"hello\n"),
            "ce013625030ba8dba906f756967f9e9ca394464a",
        )

    def test_receipt_and_summary_core_fields_must_match(self):
        receipt = {
            "source_checkout_sha": "abc",
            "source_archive_sha256": "def",
            "output_sha256": {"report.json": {"bytes": 1, "sha256": "x"}},
            "artifact_bundle": {"byte_readback_verified": True},
            "status": "ACCEPTANCE_PASS_PERSISTED",
        }
        summary = {
            "source_checkout_sha": "abc",
            "source_archive_sha256": "def",
            "output_sha256": {"report.json": {"bytes": 1, "sha256": "x"}},
            "status": "ACCEPTANCE_PASS",
        }
        validate_receipt_summary(receipt, summary)
        summary["source_checkout_sha"] = "different"
        with self.assertRaises(ValueError):
            validate_receipt_summary(receipt, summary)

    def test_stale_statuses_are_reported_not_silently_rewritten(self):
        warnings = status_warnings(
            {"status": "AGGREGATED_PENDING_ACCEPTANCE_VALIDATION"},
            {"status": "AGGREGATED_PENDING_ACCEPTANCE_VALIDATION"},
            {"status": "ACCEPTANCE_PASS_PENDING_ARTIFACT_PERSISTENCE"},
            {"status": "ACCEPTANCE_PASS_ARTIFACT_PERSISTED_PENDING_RESULT_BRANCH_CI"},
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("status metadata is not synchronized", warnings[0])

    def test_consistent_statuses_have_no_warning(self):
        obj = {"status": "ACCEPTANCE_PASS"}
        self.assertEqual(status_warnings(obj, obj, obj, obj), [])


if __name__ == "__main__":
    unittest.main()
