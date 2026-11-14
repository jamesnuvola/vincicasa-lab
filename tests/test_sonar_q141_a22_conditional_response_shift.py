import random
import unittest
from sonar_q141_a22_conditional_response_shift import acf, holm_adjust, longest_run, stationary_sample, validate_temporal_rows


class Q141A22Tests(unittest.TestCase):
    def test_stationary_bootstrap_is_deterministic(self):
        self.assertEqual(stationary_sample([0, 1, 1, 0], 20, 5, random.Random(141)),
                         stationary_sample([0, 1, 1, 0], 20, 5, random.Random(141)))

    def test_stationary_bootstrap_preserves_constant_series(self):
        self.assertEqual(stationary_sample([1] * 10, 20, 20, random.Random(2)), [1] * 20)

    def test_longest_high_run(self):
        self.assertEqual(longest_run([0, 1, 1, 0, 1, 1, 1, 0]), 3)

    def test_acf_constant_series_is_finite(self):
        self.assertEqual(acf([1] * 20, 1), 0.0)

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        tests = [{"p_raw": p} for p in (0.04, 0.001, 0.02, 0.5)]
        holm_adjust(tests)
        pairs = sorted((t["p_raw"], t["p_holm_12"]) for t in tests)
        self.assertEqual([round(x[1], 6) for x in pairs], [0.004, 0.06, 0.08, 0.5])

    def test_holm_never_reduces_raw_p(self):
        tests = [{"p_raw": p} for p in (0.01, 0.2, 0.03)]
        holm_adjust(tests)
        for row in tests:
            self.assertGreaterEqual(row["p_holm_12"], row["p_raw"])

    def test_temporal_validator_accepts_strict_prior(self):
        rows = [{
            "target_index": "10", "target_date": "2026-01-02", "cutoff_date": "2026-01-01",
            "strict_prior": "true", "current_state": "high", "capture_response": "0.6",
            "mse_gain_vs_mean400": "-0.001", "split": "discovery", "drift": "0.2",
            "q75_state_prediction": "0.61", "baseline_mean400": "0.60"
        }]
        self.assertEqual(validate_temporal_rows(rows, [10], "current_state", "mse_gain_vs_mean400")[0]["state"], 1)

    def test_temporal_validator_rejects_same_day_cutoff(self):
        rows = [{
            "target_index": "10", "target_date": "2026-01-02", "cutoff_date": "2026-01-02",
            "strict_prior": "true", "current_state": "high", "capture_response": "0.6",
            "mse_gain_vs_mean400": "-0.001", "split": "discovery", "drift": "0.2",
            "q75_state_prediction": "0.61", "baseline_mean400": "0.60"
        }]
        with self.assertRaisesRegex(ValueError, "non-strict"):
            validate_temporal_rows(rows, [10], "current_state", "mse_gain_vs_mean400")

    def test_temporal_validator_rejects_non_finite_response(self):
        rows = [{
            "target_index": "10", "target_date": "2026-01-02", "cutoff_date": "2026-01-01",
            "strict_prior": "true", "current_state": "high", "capture_response": "nan",
            "mse_gain_vs_mean400": "-0.001", "split": "discovery", "drift": "0.2",
            "q75_state_prediction": "0.61", "baseline_mean400": "0.60"
        }]
        with self.assertRaisesRegex(ValueError, "non-finite"):
            validate_temporal_rows(rows, [10], "current_state", "mse_gain_vs_mean400")


if __name__ == "__main__":
    unittest.main()
