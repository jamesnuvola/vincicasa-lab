import importlib.util
import unittest
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sonar_q141_d3_effective_rank_family_state.py"
spec = importlib.util.spec_from_file_location("q141_d3", SCRIPT)
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class EffectiveRankTests(unittest.TestCase):
    def test_rank_is_finite_and_bounded(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=(40, 59))
        value = q.effective_rank(x)
        self.assertTrue(np.isfinite(value))
        self.assertGreater(value, 0)
        self.assertLessEqual(value, 39 + 1e-10)

    def test_rank_invariant_to_column_offsets(self):
        rng = np.random.default_rng(8)
        x = rng.normal(size=(40, 59))
        offsets = rng.normal(size=(1, 59))
        self.assertAlmostEqual(q.effective_rank(x), q.effective_rank(x + offsets), places=10)

    def test_rank_invariant_to_global_scale(self):
        rng = np.random.default_rng(9)
        x = rng.normal(size=(40, 59))
        self.assertAlmostEqual(q.effective_rank(x), q.effective_rank(7.5 * x), places=10)

    def test_rank_rejects_nonfinite_and_wrong_shape(self):
        with self.assertRaises(ValueError):
            q.effective_rank(np.zeros((39, 59)))
        bad = np.zeros((40, 59))
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            q.effective_rank(bad)

    def test_state_uses_exact_previous_window(self):
        ranks = np.array([0.1, 0.2, 0.3, 0.4, 0.9, 0.5], dtype=float)
        thresholds, state = q.build_state(ranks, window=4)
        self.assertTrue(np.isnan(thresholds[3]))
        self.assertAlmostEqual(thresholds[4], 0.25)
        self.assertEqual(int(state[4]), 1)
        self.assertAlmostEqual(thresholds[5], 0.35)
        self.assertEqual(int(state[5]), 1)

    def test_tie_is_low_state(self):
        ranks = np.array([0.5, 0.5, 0.5, 0.5, 0.5], dtype=float)
        _, state = q.build_state(ranks, window=4)
        self.assertEqual(int(state[4]), 0)

    def test_high_minus_low(self):
        y = np.array([1.0, 3.0, 2.0, 4.0])
        h = np.array([0, 1, 0, 1])
        self.assertAlmostEqual(q.high_minus_low(y, h), 2.0)

    def test_holm_is_monotone_and_bounded(self):
        adjusted = q.holm_adjust([0.01, 0.04, 0.03])
        self.assertEqual(len(adjusted), 3)
        self.assertTrue(all(0 <= x <= 1 for x in adjusted))
        self.assertEqual(adjusted, [0.03, 0.06, 0.06])

    def test_future_suffix_does_not_change_prior_state(self):
        rng = np.random.default_rng(10)
        ranks = rng.uniform(size=250)
        thresholds, state = q.build_state(ranks, window=100)
        t = 150
        changed = ranks.copy()
        changed[t+1:] = 999.0
        thresholds2, state2 = q.build_state(changed, window=100)
        self.assertEqual(state[t], state2[t])
        self.assertAlmostEqual(thresholds[t], thresholds2[t], places=14)

    def test_bootstrap_and_shift_are_deterministic(self):
        y = np.linspace(-0.1, 0.1, 80)
        h = (np.arange(80) % 2).astype(np.int8)
        ci1 = q.circular_block_bootstrap_ci(y, h, replicates=300, block=10, seed=11)
        ci2 = q.circular_block_bootstrap_ci(y, h, replicates=300, block=10, seed=11)
        self.assertEqual(ci1, ci2)
        p1 = q.circular_shift_p(y, h, replicates=300, seed=12)
        p2 = q.circular_shift_p(y, h, replicates=300, seed=12)
        self.assertEqual(p1, p2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
