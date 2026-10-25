import sys
import unittest
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.sonar_position_regime_residual_lab import prospective_row_is_eligible, paired_difference_exact_conservative_ci
from scripts.sonar_sequence_agent import binomial_tail_ge


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

    def test_accepts_protocol_registration_date_itself(self):
        row = dict(self.row, target_date="2026-10-19",
                   frozen_at="2026-10-19T15:00:00+02:00",
                   history_cutoff="2026-10-18",
                   actual_numbers="5 15 20 31 34")
        actual = {"2026-10-19": (5, 15, 20, 31, 34)}
        self.assertTrue(prospective_row_is_eligible(
            row, actual, date(2026, 10, 19), time(20, 0), ZoneInfo("Europe/Rome")
        ))

    def test_rejects_pending_status(self):
        self.assertFalse(self.eligible(dict(self.row, status="FROZEN_PENDING")))

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

    def test_paired_exact_ci_is_conservative_for_tied_zero_hit_sample(self):
        result = paired_difference_exact_conservative_ci([0, 0, 0, 0], [0, 0, 0, 0])
        self.assertLess(result["lower_95"], 0.0)
        self.assertGreater(result["upper_95"], 0.0)
        self.assertIn("Clopper-Pearson", result["method"])

    def test_paired_exact_ci_empty_sample(self):
        result = paired_difference_exact_conservative_ci([], [])
        self.assertIsNone(result["lower_95"])
        self.assertIsNone(result["upper_95"])

    def test_exact_binomial_tail_matches_known_probability(self):
        self.assertAlmostEqual(binomial_tail_ge(10, 10, 0.5), 1 / 1024, places=12)
        self.assertEqual(binomial_tail_ge(0, 10, 0.5), 1.0)
        self.assertEqual(binomial_tail_ge(11, 10, 0.5), 0.0)


if __name__ == "__main__":
    unittest.main()
