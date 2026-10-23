import unittest
from datetime import date, time
from zoneinfo import ZoneInfo

from scripts.sonar_position_regime_residual_lab import prospective_row_is_eligible


class ProspectiveFreezeEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.actual = {"2026-10-20": (1, 4, 17, 20, 29)}
        self.row = {
            "target_date": "2026-10-20",
            "frozen_at": "2026-10-20T01:00:00+02:00",
            "history_cutoff": "2026-10-19",
            "config_id": "freq_100",
            "status": "EVALUATED",
            "actual_numbers": "1 4 17 20 29",
        }

    def eligible(self, row=None, config=None):
        return prospective_row_is_eligible(
            row or self.row, self.actual, date(2026, 10, 19),
            time(20, 0), ZoneInfo("Europe/Rome"), config
        )

    def test_accepts_existing_pre_target_freeze(self):
        self.assertTrue(self.eligible())

    def test_excludes_pre_registration_target(self):
        row = dict(self.row, target_date="2026-10-18", history_cutoff="2026-10-17")
        actual = {"2026-10-18": (1, 2, 3, 4, 5)}
        self.assertFalse(prospective_row_is_eligible(
            row, actual, date(2026, 10, 19), time(20, 0), ZoneInfo("Europe/Rome")
        ))

    def test_rejects_wrong_cutoff(self):
        self.assertFalse(self.eligible(dict(self.row, history_cutoff="2026-10-18")))

    def test_rejects_late_freeze(self):
        self.assertFalse(self.eligible(dict(self.row, frozen_at="2026-10-20T20:00:00+02:00")))

    def test_rejects_outcome_mismatch(self):
        self.assertFalse(self.eligible(dict(self.row, actual_numbers="1 4 17 20 30")))

    def test_rejects_missing_freeze_or_actual(self):
        self.assertFalse(self.eligible(dict(self.row, frozen_at="")))
        self.assertFalse(prospective_row_is_eligible(
            self.row, {}, date(2026, 10, 19), time(20, 0), ZoneInfo("Europe/Rome")
        ))

    def test_global_comparator_must_be_freq_100(self):
        self.assertTrue(self.eligible(config="freq_100"))
        self.assertFalse(self.eligible(config="freq_50"))


if __name__ == "__main__":
    unittest.main()
