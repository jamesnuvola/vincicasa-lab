#!/usr/bin/env python3
"""Q94 regression tests: spectral-subspace overlap, strict prefixes and fixed rank blending."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q94_spectral_subspace_persistence as q94


class Q94SpectralSubspacePersistenceTests(unittest.TestCase):
    def test_identical_subspace_has_unit_persistence(self):
        basis = np.eye(40, dtype=np.float64)[:, :2]
        self.assertAlmostEqual(q94.subspace_overlap(basis, basis), 1.0, places=12)

    def test_orthogonal_subspaces_have_zero_persistence(self):
        left = np.eye(40, dtype=np.float64)[:, :2]
        right = np.eye(40, dtype=np.float64)[:, 2:4]
        self.assertAlmostEqual(q94.subspace_overlap(left, right), 0.0, places=12)

    def test_overlap_is_symmetric_and_bounded(self):
        rng = np.random.default_rng(94001)
        a, _ = np.linalg.qr(rng.normal(size=(40, 2)))
        b, _ = np.linalg.qr(rng.normal(size=(40, 4)))
        ab = q94.subspace_overlap(a, b)
        ba = q94.subspace_overlap(b, a)
        self.assertGreaterEqual(ab, 0.0)
        self.assertLessEqual(ab, 1.0)
        self.assertAlmostEqual(ab, ba, places=12)

    def test_empty_subspace_has_zero_persistence(self):
        empty = np.zeros((40, 0), dtype=np.float64)
        basis = np.eye(40, dtype=np.float64)[:, :2]
        self.assertEqual(q94.subspace_overlap(empty, basis), 0.0)
        self.assertEqual(q94.subspace_overlap(basis, empty), 0.0)

    def test_strict_history_excludes_target_and_future(self):
        draws = list(range(20))
        prefix = q94.strict_history(draws, 12)
        extended = draws + [20, 21, 22]
        extended_prefix = q94.strict_history(extended, 12)
        self.assertEqual(prefix, list(range(12)))
        self.assertEqual(extended_prefix, prefix)
        self.assertNotIn(draws[12], prefix)

    def test_strict_history_rejects_invalid_index(self):
        with self.assertRaises(ValueError):
            q94.strict_history([1, 2, 3], 4)

    def test_rank_blend_endpoints_recover_baseline_and_spectral_order(self):
        equal = np.arange(1, 41, dtype=np.float64)
        spectral = np.arange(40, 0, -1, dtype=np.float64)
        stable_zero, unstable_zero = q94.persistence_weighted_scores(equal, spectral, 0.0)
        stable_one, unstable_one = q94.persistence_weighted_scores(equal, spectral, 1.0)
        np.testing.assert_array_equal(stable_zero, 41.0 - equal)
        np.testing.assert_array_equal(unstable_zero, 41.0 - spectral)
        np.testing.assert_array_equal(stable_one, 41.0 - spectral)
        np.testing.assert_array_equal(unstable_one, 41.0 - equal)

    def test_midpoint_weight_makes_stable_and_unstable_controls_equal(self):
        equal = np.random.default_rng(94002).permutation(np.arange(1, 41)).astype(float)
        spectral = np.random.default_rng(94003).permutation(np.arange(1, 41)).astype(float)
        stable, unstable = q94.persistence_weighted_scores(equal, spectral, 0.5)
        np.testing.assert_array_equal(stable, unstable)

    def test_rank_blend_rejects_invalid_weight_and_rank(self):
        ranks = np.arange(1, 41, dtype=float)
        with self.assertRaises(ValueError):
            q94.persistence_weighted_scores(ranks, ranks, 1.01)
        bad = ranks.copy()
        bad[0] = 0
        with self.assertRaises(ValueError):
            q94.persistence_weighted_scores(bad, ranks, 0.5)

    def test_fixed_chronological_splits(self):
        labels = q94.q93.split_labels(3203)
        self.assertEqual(labels.count("discovery"), 1921)
        self.assertEqual(labels.count("validation"), 641)
        self.assertEqual(labels.count("blind_oos"), 641)

    def test_fixed_shift_null_is_reproducible_and_nonzero(self):
        def offsets():
            rng = np.random.default_rng(q94.SHIFT_SEED)
            return np.sort(rng.choice(np.arange(1, 641, dtype=np.int64), size=q94.SHIFT_COUNT, replace=False))
        first, second = offsets(), offsets()
        np.testing.assert_array_equal(first, second)
        self.assertEqual(len(first), 99)
        self.assertEqual(len(set(first.tolist())), 99)
        self.assertTrue(np.all(first > 0))

    def test_model_family_and_primary_gate_are_frozen(self):
        self.assertEqual(q94.FOCAL, "Q94::STABILITY_WEIGHTED")
        self.assertEqual(len(q94.MODELS), 5)
        self.assertEqual(len(q94.COMPARATORS), 4)
        self.assertEqual(q94.REQUESTED_MODES, 2)
        self.assertEqual(q94.SHIFT_COUNT, 99)
        self.assertEqual(q94.BOOTSTRAP_BLOCK, 20)
        self.assertEqual(q94.BOOTSTRAP_REPLICATES, 2000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
