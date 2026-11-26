from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_q7_factorial_attribution as b9


FAMILIES = [f"family_{i}" for i in range(10)]


class Q141B9FactorialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contexts = b9.build_contrast_contexts(FAMILIES)

    def test_context_counts_exclude_empty_background(self):
        self.assertEqual(len(self.contexts), 55)
        for item in self.contexts[:10]:
            self.assertEqual(len(item["base"]), 511)
            self.assertTrue(np.all(item["base"] >= 1))
        for item in self.contexts[10:]:
            self.assertEqual(len(item["base"]), 255)
            self.assertTrue(np.all(item["base"] >= 1))

    def test_additive_main_effects_are_recovered_exactly(self):
        masks = np.arange(1, b9.FORMULAS + 1)
        weights = np.arange(1, 11, dtype=np.float64) * 0.001
        p = np.asarray([
            0.35 + sum(weights[i] for i in range(10) if mask & (1 << i))
            for mask in masks
        ])
        effects = b9.factorial_effects_from_percentiles(p, self.contexts)
        np.testing.assert_allclose(effects[:10], weights, rtol=0, atol=1e-14)
        np.testing.assert_allclose(effects[10:], 0.0, rtol=0, atol=1e-14)

    def test_pairwise_difference_in_differences_recovers_interaction(self):
        masks = np.arange(1, b9.FORMULAS + 1)
        weights = np.arange(1, 11, dtype=np.float64) * 0.0005
        gamma = 0.004
        p = np.asarray([
            0.35
            + sum(weights[i] for i in range(10) if mask & (1 << i))
            + (gamma if (mask & 1) and (mask & 2) else 0.0)
            for mask in masks
        ])
        effects = b9.factorial_effects_from_percentiles(p, self.contexts)
        self.assertAlmostEqual(effects[10], gamma, places=13)
        np.testing.assert_allclose(effects[11:], 0.0, rtol=0, atol=1e-14)
        expected_main_0 = weights[0] + gamma * (256.0 / 511.0)
        expected_main_1 = weights[1] + gamma * (256.0 / 511.0)
        self.assertAlmostEqual(effects[0], expected_main_0, places=13)
        self.assertAlmostEqual(effects[1], expected_main_1, places=13)

    def test_target_effects_are_invariant_to_future_rank_rows(self):
        rng = np.random.default_rng(141209)
        matrix = rng.integers(1, b9.CANDIDATES + 1, size=(20, b9.FORMULAS), dtype=np.int32)
        before, mean_before = b9.target_factorial_effects(matrix, 8, self.contexts)
        matrix[9:, :] = rng.integers(1, b9.CANDIDATES + 1, size=matrix[9:, :].shape, dtype=np.int32)
        after, mean_after = b9.target_factorial_effects(matrix, 8, self.contexts)
        np.testing.assert_array_equal(before, after)
        self.assertEqual(mean_before, mean_after)

    def test_two_sided_block_signflip_is_sign_symmetric_and_reproducible(self):
        values = np.asarray([0.01, -0.02, 0.03, 0.01, -0.01, 0.02, -0.02, 0.01], dtype=float)
        p1, blocks1 = b9.block_signflip_two_sided(values, 2, 2000, 141)
        p2, blocks2 = b9.block_signflip_two_sided(-values, 2, 2000, 141)
        p3, blocks3 = b9.block_signflip_two_sided(values, 2, 2000, 141)
        self.assertEqual((blocks1, blocks2, blocks3), (4, 4, 4))
        self.assertEqual(p1, p2)
        self.assertEqual(p1, p3)

    def test_holm_adjustment_and_registered_split_sizes(self):
        adjusted = b9.holm_adjust([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06])
        self.assertEqual(b9.split_sizes(3286), (1972, 657, 657))

    def test_rank_transform_and_invalid_rank_rejection(self):
        ranks = np.asarray([1, b9.CANDIDATES], dtype=np.int64)
        p = 1.0 - (ranks.astype(np.float64) - 1.0) / (b9.CANDIDATES - 1.0)
        self.assertEqual(float(p[0]), 1.0)
        self.assertEqual(float(p[1]), 0.0)
        bad = np.zeros((2, b9.FORMULAS), dtype=np.int32)
        with self.assertRaises(ValueError):
            b9.target_factorial_effects(bad, 0, self.contexts)


if __name__ == "__main__":
    unittest.main()
