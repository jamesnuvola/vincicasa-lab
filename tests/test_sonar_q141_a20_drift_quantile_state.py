import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q141_a20_drift_quantile_state as a20


class DriftQuantileStateTests(unittest.TestCase):
    def test_empirical_quantile_uses_registered_lower_order_statistic(self):
        self.assertEqual(a20.quantile([4, 1, 3, 2], 0.75), 3)

    def test_forecast_uses_prior_window_and_current_drift(self):
        drift = [float(i % 17) for i in range(420)]
        capture = [float((i % 11) / 10) for i in range(420)]
        result = a20.forecast_at(drift, capture, 400)
        self.assertIn(result["state"], ("high", "low"))
        self.assertEqual(result["prior_high_count"] + result["prior_low_count"], 400)
        self.assertGreaterEqual(result["selected_count"], 25)

    def test_target_response_and_future_suffix_are_invariant(self):
        drift = [float((i * 7) % 31) / 31 for i in range(430)]
        capture = [float((i * 11) % 37) / 37 for i in range(430)]
        target = 410
        expected = a20.forecast_at(drift, capture, target)["prediction"]
        changed_drift = list(drift)
        changed_capture = list(capture)
        changed_capture[target] = 1.0 - changed_capture[target]
        for i in range(target + 1, len(drift)):
            changed_drift[i] = 1.0 - changed_drift[i]
            changed_capture[i] = 1.0 - changed_capture[i]
        actual = a20.forecast_at(changed_drift, changed_capture, target)["prediction"]
        self.assertEqual(expected, actual)

    def test_fallback_when_selected_state_has_too_few_rows(self):
        drift = [1.0] * 400 + [0.0]
        capture = [float(i) / 400 for i in range(400)] + [0.99]
        result = a20.forecast_at(drift, capture, 400)
        self.assertTrue(result["fallback"])
        self.assertEqual(result["selected_count"], 0)
        self.assertAlmostEqual(result["prediction"], sum(capture[:400]) / 400)

    def test_bootstrap_is_deterministic(self):
        values = [((i * 13) % 29) / 1000 for i in range(83)]
        first = a20.bootstrap_ci(values, 1234, reps=500, block=10)
        second = a20.bootstrap_ci(values, 1234, reps=500, block=10)
        self.assertEqual(first, second)

    def test_signflip_is_deterministic_and_bounded(self):
        values = [((i * 5) % 17 - 8) / 100 for i in range(87)]
        p1 = a20.signflip_p(values, 4321, reps=1000, block=10)
        p2 = a20.signflip_p(values, 4321, reps=1000, block=10)
        self.assertEqual(p1, p2)
        self.assertGreaterEqual(p1, 0.0)
        self.assertLessEqual(p1, 1.0)

    def test_holm_adjustment_is_monotone_and_conservative(self):
        raw = [0.04, 0.001, 0.02, 0.5, 0.03, 0.01]
        adjusted = a20.holm(raw)
        order = sorted(range(len(raw)), key=lambda i: (raw[i], i))
        ordered_adjusted = [adjusted[i] for i in order]
        self.assertEqual(ordered_adjusted, sorted(ordered_adjusted))
        self.assertTrue(all(adjusted[i] >= raw[i] for i in range(len(raw))))

    def test_source_blob_is_pinned(self):
        self.assertEqual(a20.SOURCE_SHA, "5613d5176ed48dd63df186258a53039e65840555")

    def test_registered_design_constants(self):
        self.assertEqual(a20.WINDOW, 400)
        self.assertEqual(a20.QUANTILE, 0.75)
        self.assertEqual(a20.MIN_STATE, 25)
        self.assertEqual(a20.SPLITS, ("discovery", "validation", "blind_oos"))


if __name__ == "__main__":
    unittest.main()
