import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sonar_q60_h102_disagreement import (
    build_ledger,
    exact_signflip_p,
    holm_adjust,
    ols_slope,
    hypergeom_upper_p,
)


class H102DisagreementTests(unittest.TestCase):
    def test_slope_units(self):
        x = [0, 1, 2, 3, 4]
        y = [1, 3, 5, 7, 9]
        self.assertAlmostEqual(5 * ols_slope(x, y), 10.0)

    def test_exact_signflip_known_case(self):
        self.assertAlmostEqual(exact_signflip_p([1, 1]), 0.5)
        self.assertAlmostEqual(exact_signflip_p([0, 0]), 1.0)

    def test_holm_monotone_and_capped(self):
        adjusted = holm_adjust([0.01, 0.04, 0.20, 0.90])
        self.assertEqual(adjusted, [0.04, 0.12, 0.40, 0.90])

    def test_exact_uniform_null_is_one_for_zero_hits(self):
        self.assertEqual(hypergeom_upper_p(0, 3), 1.0)

    def test_pending_target_is_not_scored_from_shadow_fields(self):
        target = "2026-11-10"
        global_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09", "config_id": "freq_100",
            "top20": "26 16 25 36 10 12 15 28 29 38 1 5 9 17 18 30 34 37 39 24",
            "status": "FROZEN_PENDING"
        }]
        positional_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09", "config_id": "position_seed_mix_top20_v1",
            "top20": "26 16 36 12 15 29 38 1 17 37 39 3 23 2 25 10 28 5 9 18",
            "status": "FROZEN_PENDING"
        }]
        from scripts.sonar_q60_h101_rrf import reciprocal_rank_fusion
        rrf = reciprocal_rank_fusion(
            [int(x) for x in global_rows[0]["top20"].split()],
            [int(x) for x in positional_rows[0]["top20"].split()],
            20
        )
        h101_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T12:49:51+01:00",
            "history_cutoff": "2026-11-09", "config_id": "q60_h101_rrf_k20_v1",
            "top20": " ".join(map(str, rrf)), "rrf_k": "20", "status": "FROZEN_PENDING",
            "source_global_frozen_at": "2026-11-10T10:53:16+01:00",
            "source_positional_frozen_at": "2026-11-10T10:55:31+01:00",
            "source_global_history_cutoff": "2026-11-09",
            "source_positional_history_cutoff": "2026-11-09",
            "actual_numbers": "", "hit_numbers": "", "hit_count": "", "all5_top20": ""
        }]
        archive = [{"data": "2026-11-09", "n1": "9", "n2": "17", "n3": "25", "n4": "32", "n5": "34"}]
        records, pending, latest = build_ledger(global_rows, positional_rows, h101_rows, archive)
        self.assertEqual(records, [])
        self.assertEqual(pending, [target])
        self.assertEqual(latest, "2026-11-09")


    def test_scores_only_from_canonical_target_outcome_and_checks_parent_provenance(self):
        target = "2026-11-10"
        global_top = [26, 16, 25, 36, 10, 12, 15, 28, 29, 38, 1, 5, 9, 17, 18, 30, 34, 37, 39, 24]
        positional_top = [26, 16, 36, 12, 15, 29, 38, 1, 17, 37, 39, 3, 23, 2, 25, 10, 28, 5, 9, 18]
        global_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09", "config_id": "freq_100",
            "top20": " ".join(map(str, global_top)), "status": "FROZEN_PENDING"
        }]
        positional_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09", "config_id": "position_seed_mix_top20_v1",
            "top20": " ".join(map(str, positional_top)), "status": "FROZEN_PENDING"
        }]
        from scripts.sonar_q60_h101_rrf import reciprocal_rank_fusion
        rrf = reciprocal_rank_fusion(global_top, positional_top, 20)
        h101_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T12:49:51+01:00",
            "history_cutoff": "2026-11-09", "config_id": "q60_h101_rrf_k20_v1",
            "rrf_k": "20", "top20": " ".join(map(str, rrf)), "status": "FROZEN_PENDING",
            "source_global_frozen_at": "2026-11-10T10:53:16+01:00",
            "source_positional_frozen_at": "2026-11-10T10:55:31+01:00",
            "source_global_history_cutoff": "2026-11-09",
            "source_positional_history_cutoff": "2026-11-09",
            "actual_numbers": "", "hit_numbers": "", "hit_count": "", "all5_top20": ""
        }]
        archive = [
            {"data": "2026-11-09", "n1": "9", "n2": "17", "n3": "25", "n4": "32", "n5": "34"},
            {"data": "2026-11-10", "n1": "9", "n2": "17", "n3": "25", "n4": "32", "n5": "34"}
        ]
        records, pending, latest = build_ledger(global_rows, positional_rows, h101_rows, archive)
        self.assertEqual(pending, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["history_cutoff"], "2026-11-09")
        self.assertEqual(records[0]["global_hits"], 4)
        self.assertEqual(records[0]["positional_hits"], 3)
        self.assertEqual(records[0]["h101_hits"], 3)
        self.assertEqual(records[0]["h101_minus_global"], -1)
        self.assertEqual(latest, "2026-11-10")

    def test_rejects_mismatched_parent_freeze_provenance(self):
        target = "2026-11-10"
        global_top = list(range(1, 21))
        positional_top = list(range(11, 31))
        global_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09", "config_id": "freq_100",
            "top20": " ".join(map(str, global_top)), "status": "FROZEN_PENDING"
        }]
        positional_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09", "config_id": "position_seed_mix_top20_v1",
            "top20": " ".join(map(str, positional_top)), "status": "FROZEN_PENDING"
        }]
        from scripts.sonar_q60_h101_rrf import reciprocal_rank_fusion
        rrf = reciprocal_rank_fusion(global_top, positional_top, 20)
        h101_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T12:49:51+01:00",
            "history_cutoff": "2026-11-09", "config_id": "q60_h101_rrf_k20_v1",
            "rrf_k": "20", "top20": " ".join(map(str, rrf)), "status": "FROZEN_PENDING",
            "source_global_frozen_at": "2026-11-10T10:53:16+01:00",
            "source_positional_frozen_at": "2026-11-10T10:55:31+01:00",
            "source_global_history_cutoff": "2026-11-09",
            "source_positional_history_cutoff": "2026-11-08",
            "actual_numbers": "", "hit_numbers": "", "hit_count": "", "all5_top20": ""
        }]
        archive = [{"data": "2026-11-09", "n1": "9", "n2": "17", "n3": "25", "n4": "32", "n5": "34"}]
        with self.assertRaises(ValueError):
            build_ledger(global_rows, positional_rows, h101_rows, archive)

    def test_rejects_freeze_after_draw(self):
        target = "2026-11-10"
        global_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09", "config_id": "freq_100",
            "top20": " ".join(map(str, range(1, 21))), "status": "FROZEN_PENDING"
        }]
        positional_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09", "config_id": "position_seed_mix_top20_v1",
            "top20": " ".join(map(str, range(21, 41))), "status": "FROZEN_PENDING"
        }]
        from scripts.sonar_q60_h101_rrf import reciprocal_rank_fusion
        rrf = reciprocal_rank_fusion(list(range(1, 21)), list(range(21, 41)), 20)
        h101_rows = [{
            "target_date": target, "frozen_at": "2026-11-10T19:01:00+01:00",
            "history_cutoff": "2026-11-09", "config_id": "q60_h101_rrf_k20_v1",
            "top20": " ".join(map(str, rrf)), "status": "FROZEN_PENDING",
            "actual_numbers": "", "hit_numbers": "", "hit_count": "", "all5_top20": ""
        }]
        archive = [{"data": "2026-11-09", "n1": "9", "n2": "17", "n3": "25", "n4": "32", "n5": "34"}]
        with self.assertRaises(ValueError):
            build_ledger(global_rows, positional_rows, h101_rows, archive)


if __name__ == "__main__":
    unittest.main()
