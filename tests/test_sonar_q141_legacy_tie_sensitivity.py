#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_legacy_tie_sensitivity as audit


def make_row(offset, split="discovery", top5_delta_hits=0, top10_delta_hits=0,
             top20_delta_hits=0, rank_mismatches=0):
    target = date(2020, 1, 1) + timedelta(days=offset + 1)
    cutoff = target - timedelta(days=1)
    row = {
        "target_index": str(50 + offset),
        "target_offset": str(offset),
        "target_date": target.isoformat(),
        "cutoff_date": cutoff.isoformat(),
        "prior_draws": str(50 + offset),
        "split": split,
        "formula_sample_count": "120",
        "alias_mismatches": "0",
        "stable_raw_vs_canonical_score_mismatches": "0",
        "stable_raw_vs_canonical_rank_mismatches": "0",
        "legacy_numpy_rank_mismatches": str(rank_mismatches),
        "legacy_numpy_max_rank_displacement": "2" if rank_mismatches else "0",
        "legacy_numpy_max_abs_score_delta": "1e-15" if rank_mismatches else "0",
    }
    for k, delta in ((5, top5_delta_hits), (10, top10_delta_hits), (20, top20_delta_hits)):
        stable = 0.125 if k == 5 else (0.25 if k == 10 else 0.5)
        row[f"stable_raw_top{k}_hit_share"] = str(stable)
        row[f"canonical_top{k}_hit_share"] = str(stable)
        row[f"legacy_numpy_top{k}_hit_share"] = str(stable + delta / 600.0)
    return row


class LegacyTieSensitivityTests(unittest.TestCase):
    def test_integer_hit_delta_reconstruction(self):
        rows = [
            make_row(0, top5_delta_hits=-1, top10_delta_hits=1, rank_mismatches=1),
            make_row(1, split="validation", top5_delta_hits=1, top20_delta_hits=0),
        ]
        result = audit.summarize_rows(rows, expected_split_counts=None)
        all_rows = result["all"]
        self.assertEqual(all_rows["legacy_rank_mismatches"], 1)
        self.assertEqual(all_rows["formula_target_comparisons"], 240)
        self.assertEqual(all_rows["topk"]["5"]["legacy_minus_stable_hit_count"], 0)
        self.assertEqual(all_rows["topk"]["10"]["legacy_minus_stable_hit_count"], 1)
        self.assertEqual(all_rows["topk"]["20"]["legacy_minus_stable_hit_count"], 0)

    def test_stable_canonical_mismatch_fails_closed(self):
        row = make_row(0)
        row["canonical_top5_hit_share"] = "0.126"
        with self.assertRaisesRegex(ValueError, "stable/canonical Top-5 mismatch"):
            audit.summarize_rows([row])

    def test_fractional_hit_delta_fails_closed(self):
        row = make_row(0)
        row["legacy_numpy_top5_hit_share"] = str(0.125 + 0.0001)
        with self.assertRaisesRegex(ValueError, "not an integer hit count"):
            audit.summarize_rows([row])

    def test_future_or_same_day_cutoff_fails_closed(self):
        row = make_row(0)
        row["cutoff_date"] = row["target_date"]
        with self.assertRaisesRegex(ValueError, "non-prior cutoff"):
            audit.summarize_rows([row])

    def test_nonchronological_targets_fail_closed(self):
        rows = [make_row(0), make_row(1)]
        rows[1]["target_date"] = rows[0]["target_date"]
        rows[1]["cutoff_date"] = (date.fromisoformat(rows[1]["target_date"]) - timedelta(days=1)).isoformat()
        with self.assertRaisesRegex(ValueError, "not strictly chronological"):
            audit.summarize_rows(rows)

    def test_target_index_and_prior_count_must_match(self):
        row = make_row(0)
        row["prior_draws"] = "49"
        with self.assertRaisesRegex(ValueError, "target offset/index/prior history mismatch"):
            audit.summarize_rows([row])

    def test_unknown_split_fails_closed(self):
        row = make_row(0, split="blind")
        with self.assertRaisesRegex(ValueError, "unexpected split"):
            audit.summarize_rows([row])


if __name__ == "__main__":
    unittest.main(verbosity=2)
