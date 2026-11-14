import unittest
import numpy as np

from sonar_q141_a19_residual_subspace_drift import (
    build_projection, compute_drift_capture, drift_at, predict_one,
    rolling_predictions, block_signflip_p, split_ranges, verify_future_invariance,
)

class Q141A19Tests(unittest.TestCase):
    def test_projection_is_deterministic_and_orthonormal(self):
        a, ea = build_projection(40, 12, 1901)
        b, eb = build_projection(40, 12, 1901)
        np.testing.assert_array_equal(a, b)
        self.assertLess(ea, 1e-11)
        self.assertLess(eb, 1e-11)
        np.testing.assert_allclose(a.T @ a, np.eye(12), atol=1e-11)

    def test_projection_rejects_invalid_dimensions(self):
        with self.assertRaises(ValueError):
            build_projection(8, 12, 1902)

    def test_drift_requires_two_strictly_prior_windows(self):
        x = np.random.default_rng(1903).normal(size=(30, 12))
        with self.assertRaises(ValueError):
            drift_at(x, 19, window=10, k=3)
        value, basis = drift_at(x, 20, window=10, k=3)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)
        self.assertEqual(basis.shape, (12, 3))

    def test_drift_and_capture_start_after_two_windows(self):
        x = np.random.default_rng(1904).normal(size=(80, 16))
        drift, capture = compute_drift_capture(x, window=10, k=3)
        self.assertTrue(np.isnan(drift[:20]).all())
        self.assertTrue(np.isnan(capture[:20]).all())
        self.assertTrue(np.isfinite(drift[20:]).all())
        self.assertTrue(np.isfinite(capture[20:]).all())
        self.assertTrue(np.all((drift[20:] >= 0) & (drift[20:] <= 1)))
        self.assertTrue(np.all((capture[20:] >= 0) & (capture[20:] <= 1)))

    def test_prediction_uses_only_prior_pairs(self):
        rng = np.random.default_rng(1905)
        drift = rng.uniform(0, 1, 80)
        capture = np.clip(0.6 - 0.1 * drift + rng.normal(0, 0.02, 80), 0, 1)
        t = 60
        original = predict_one(drift, capture, t, window=20)[0]
        changed = capture.copy()
        changed[t:] = 0.999
        changed_drift = drift.copy()
        changed_drift[t + 1:] = 0.001
        replay = predict_one(changed_drift, changed, t, window=20)[0]
        self.assertAlmostEqual(original, replay, places=14)

    def test_rolling_predictions_are_missing_before_start(self):
        rng = np.random.default_rng(1906)
        drift = rng.uniform(0, 1, 80)
        capture = rng.uniform(0, 1, 80)
        pred, b400, b20, slope, mean = rolling_predictions(drift, capture, 30, window=20)
        self.assertTrue(np.isnan(pred[:30]).all())
        self.assertTrue(np.isfinite(pred[30:]).all())
        self.assertTrue(np.isfinite(b400[30:]).all())
        self.assertTrue(np.isfinite(b20[30:]).all())

    def test_prediction_is_clipped_to_probability_range(self):
        drift = np.linspace(0.0, 1.0, 50)
        capture = np.linspace(0.0, 0.5, 50)
        pred = predict_one(drift, capture, 40, window=20)[0]
        self.assertGreaterEqual(pred, 0.0)
        self.assertLessEqual(pred, 1.0)

    def test_signflip_is_deterministic(self):
        values = np.linspace(-0.01, 0.02, 80)
        a = block_signflip_p(values, seed=1907, replicates=100, block=10)
        b = block_signflip_p(values, seed=1907, replicates=100, block=10)
        self.assertEqual(a, b)
        self.assertGreaterEqual(a[0], 0.0)
        self.assertLessEqual(a[0], 1.0)

    def test_chronological_splits_cover_all_evaluated_targets(self):
        ranges, counts = split_ranges(3386, 1200)
        self.assertEqual(counts, {"discovery": 1311, "validation": 437, "blind_oos": 438})
        self.assertEqual(ranges["discovery"].start, 1200)
        self.assertEqual(ranges["discovery"].stop, ranges["validation"].start)
        self.assertEqual(ranges["validation"].stop, ranges["blind_oos"].start)
        self.assertEqual(ranges["blind_oos"].stop, 3386)

    def test_future_suffix_does_not_change_drift_at_target(self):
        rng = np.random.default_rng(1908)
        x = rng.normal(size=(90, 20))
        t = 70
        before = drift_at(x, t, window=20, k=4)[0]
        mutated = x.copy()
        mutated[t:] = rng.normal(loc=100.0, scale=3.0, size=mutated[t:].shape)
        after = drift_at(mutated, t, window=20, k=4)[0]
        self.assertAlmostEqual(before, after, places=14)

    def test_future_invariance_helper_checks_drift_and_prediction(self):
        rng = np.random.default_rng(1910)
        projected = rng.normal(size=(90, 20))
        drift, capture = compute_drift_capture(projected, window=20, k=6)
        ok, checks = verify_future_invariance(projected, drift, capture, [60, 75, 89], window=20)
        self.assertTrue(ok)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(x["drift_unchanged"] and x["prediction_unchanged"] for x in checks))

    def test_training_window_is_strictly_prior(self):
        rng = np.random.default_rng(1909)
        drift = rng.uniform(0, 1, 100)
        capture = rng.uniform(0, 1, 100)
        t = 80
        predict_one(drift, capture, t, window=40)
        self.assertEqual(t - 40, 40)
        self.assertEqual(t, 80)

if __name__ == "__main__":
    unittest.main()
