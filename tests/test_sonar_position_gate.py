"""Regression tests for the prospective positional-shadow acceptance gate."""
import unittest
from datetime import date

from scripts.sonar_position_regime_residual_lab import is_valid_prospective_shadow_row


class ProspectiveShadowGateTests(unittest.TestCase):
    def setUp(self):
        self.actual = [5, 15, 20, 31, 34]
        self.actual_by_date = {
            "2026-10-19": self.actual,
            "2026-10-18": [6, 26, 31, 36, 37],
            "2026-10-20": [1, 4, 17, 20, 29],
        }
        self.row = {
            "target_date": "2026-10-19",
            "frozen_at": "2026-10-19T15:35:46+02:00",
            "history_cutoff": "2026-10-18",
            "status": "EVALUATED",
            "actual_numbers": "5 15 20 31 34",
        }

    def test_valid_post_protocol_freeze_is_eligible(self):
        self.assertTrue(is_valid_prospective_shadow_row(self.row, self.actual_by_date))

    def test_protocol_start_date_is_excluded_exclusively(self):
        row = dict(self.row, target_date="2026-10-18", history_cutoff="2026-10-17",
                   actual_numbers="6 26 31 36 37",
                   frozen_at="2026-10-18T08:33:11+02:00")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))

    def test_cutoff_must_be_previous_calendar_day(self):
        row = dict(self.row, history_cutoff="2026-10-17")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))

    def test_freeze_after_nominal_draw_time_is_excluded(self):
        row = dict(self.row, frozen_at="2026-10-19T20:00:01+02:00")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))

    def test_outcome_must_match_canonical_archive(self):
        row = dict(self.row, actual_numbers="5 15 20 31 35")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))

    def test_pending_freeze_is_not_eligible(self):
        row = dict(self.row, status="FROZEN_PENDING")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))

    def test_target_without_canonical_outcome_is_not_eligible(self):
        row = dict(self.row, target_date="2026-10-21", history_cutoff="2026-10-20")
        self.assertFalse(is_valid_prospective_shadow_row(row, self.actual_by_date))


if __name__ == "__main__":
    unittest.main()
