import unittest
from datetime import datetime, timezone

from scripts.sonar_q60_h101_rrf import (
    build_freeze_row,
    reciprocal_rank_fusion,
)


class H101RRFTests(unittest.TestCase):
    def test_shared_candidates_gain_two_rank_contributions(self):
        global_top20 = list(range(1, 21))
        positional_top20 = list(range(1, 21))
        fused = reciprocal_rank_fusion(global_top20, positional_top20)
        self.assertEqual(fused, global_top20)

    def test_numeric_tie_break_is_deterministic(self):
        global_top20 = [1] + list(range(3, 22))
        positional_top20 = [2] + list(range(3, 22))
        fused = reciprocal_rank_fusion(global_top20, positional_top20)
        self.assertEqual(len(fused), 20)
        self.assertEqual(len(set(fused)), 20)
        self.assertEqual(fused[0], 3)

    def test_rejects_duplicate_parent_candidates(self):
        with self.assertRaises(ValueError):
            reciprocal_rank_fusion([1] * 20, list(range(1, 21)))

    def test_builds_only_after_both_parent_freezes_and_before_draw(self):
        global_rows = [{
            "target_date": "2026-11-10",
            "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09",
            "config_id": "freq_100",
            "top20": "26 16 25 36 10 12 15 28 29 38 1 5 9 17 18 30 34 37 39 24",
            "status": "FROZEN_PENDING",
        }]
        positional_rows = [{
            "target_date": "2026-11-10",
            "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09",
            "config_id": "position_seed_mix_top20_v1",
            "top20": "26 16 36 12 15 29 38 1 17 37 39 3 23 2 25 10 28 5 9 18",
            "status": "FROZEN_PENDING",
        }]
        archive_rows = [{"data": "2026-11-09"}]
        row = build_freeze_row(
            global_rows, positional_rows, archive_rows,
            "2026-11-10", "2026-11-10T12:49:51+01:00"
        )
        self.assertEqual(row["status"], "FROZEN_PENDING")
        self.assertEqual(row["history_cutoff"], "2026-11-09")
        self.assertEqual(row["top20"], "26 16 36 12 15 29 25 38 1 10 17 28 37 39 5 9 18 3 23 2")

    def test_rejects_post_draw_freeze(self):
        global_rows = [{
            "target_date": "2026-11-10", "frozen_at": "2026-11-10T10:53:16+01:00",
            "history_cutoff": "2026-11-09", "config_id": "freq_100",
            "top20": " ".join(map(str, range(1, 21))), "status": "FROZEN_PENDING"
        }]
        positional_rows = [{
            "target_date": "2026-11-10", "frozen_at": "2026-11-10T10:55:31+01:00",
            "history_cutoff": "2026-11-09", "config_id": "position_seed_mix_top20_v1",
            "top20": " ".join(map(str, range(21, 41))), "status": "FROZEN_PENDING"
        }]
        with self.assertRaises(ValueError):
            build_freeze_row(global_rows, positional_rows, [{"data": "2026-11-09"}],
                             "2026-11-10", "2026-11-10T19:01:00+01:00")


if __name__ == "__main__":
    unittest.main()
