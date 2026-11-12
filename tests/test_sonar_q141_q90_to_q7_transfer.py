import unittest
import numpy as np

from scripts.sonar_q141_q90_to_q7_transfer import (
    prior_window, family_state, fit_ridge, predict_ridge,
    block_signflip_p, moving_block_ci, transition_summary,
)

class Q141C5Tests(unittest.TestCase):
    def test_prior_window_excludes_current_and_future(self):
        rows = [{"idx": str(i), "v": str(i)} for i in range(10)]
        selected = prior_window(rows, list(range(10)), 8, 4, "idx")
        self.assertEqual([int(r["idx"]) for r in selected], [4, 5, 6, 7])
        self.assertTrue(all(int(r["idx"]) < 8 for r in selected))

    def test_prior_window_fails_closed_on_internal_gap(self):
        rows = [{"idx": str(i)} for i in [1, 2, 4, 5]]
        with self.assertRaises(RuntimeError):
            prior_window(rows, [1, 2, 4, 5], 6, 3, "idx")

    def test_family_state_bounds_and_trend(self):
        rows = []
        for i in range(50):
            rows.append({"a": str(0.2 if i < 25 else 0.8), "b": str(0.8 if i < 25 else 0.2), "equal": "0.5"})
        equal, dispersion, entropy, trend = family_state(rows, ("a", "b"), 1.0, "equal")
        self.assertAlmostEqual(equal, 0.5)
        self.assertAlmostEqual(dispersion, 0.0)
        self.assertAlmostEqual(entropy, 1.0)
        self.assertAlmostEqual(trend, 0.0)

    def test_family_state_rejects_out_of_range(self):
        rows = [{"a": "1.2", "b": "0.1", "equal": "0.2"} for _ in range(50)]
        with self.assertRaises(RuntimeError):
            family_state(rows, ("a", "b"), 1.0)

    def test_ridge_is_finite_and_deterministic(self):
        x = np.asarray([[0.0], [1.0], [2.0], [3.0], [4.0]], dtype=float)
        y = np.asarray([0.1, 0.2, 0.3, 0.4, 0.5], dtype=float)
        a = fit_ridge(x, y)
        b = fit_ridge(x, y)
        pa = predict_ridge(a, x)
        pb = predict_ridge(b, x)
        self.assertTrue(np.isfinite(pa).all())
        np.testing.assert_allclose(pa, pb, rtol=0, atol=0)

    def test_block_inference_is_reproducible(self):
        values = np.linspace(-0.01, 0.02, 137)
        p1 = block_signflip_p(values, 20, 500, 141)
        p2 = block_signflip_p(values, 20, 500, 141)
        self.assertEqual(p1, p2)
        ci1 = moving_block_ci(values, 20, 500, 142)
        ci2 = moving_block_ci(values, 20, 500, 142)
        self.assertEqual(ci1, ci2)

    def test_transition_summary_counts_switches(self):
        s = transition_summary(["A", "A", "B", "B", "A"])
        self.assertEqual(s["switches"], 2)
        self.assertEqual(s["distinct"], 2)
        self.assertEqual(s["max_run_length"], 2)

if __name__ == "__main__":
    unittest.main()
