#!/usr/bin/env python3
"""Q93 spectral operator, null, strict-prefix and deterministic-control tests."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q87_node_graph_phase_lag as q87
import sonar_q88_signed_node_graph_transfer as q88
import sonar_q90_edge_field_decomposition as q90
import sonar_q93_spectral_coherence as q93


class Q93SpectralCoherenceTests(unittest.TestCase):
    def make_pair_residual(self, seed=93001):
        rng = np.random.default_rng(seed)
        raw = rng.normal(size=(40, 40))
        edge = 0.5 * (raw + raw.T)
        np.fill_diagonal(edge, 0.0)
        _, pair, _ = q90.decompose_edge_change(edge)
        return pair

    def test_spectral_operator_is_symmetric_and_zero_row_sum(self):
        pair = self.make_pair_residual()
        values, vectors, fraction = q93.spectral_modes(pair, 4)
        operator = vectors @ np.diag(values) @ vectors.T
        np.testing.assert_allclose(operator, operator.T, atol=1e-12, rtol=0)
        np.testing.assert_allclose(operator @ np.ones(40), 0.0, atol=1e-9, rtol=0)
        self.assertGreaterEqual(fraction, 0.0)
        self.assertLessEqual(fraction, 1.0 + 1e-12)
        self.assertLessEqual(len(values), 39)

    def test_low_rank_projection_matches_dense_operator(self):
        pair = self.make_pair_residual(93002)
        values, vectors, _ = q93.spectral_modes(pair, 2)
        features = np.random.default_rng(93003).normal(size=(40, 6))
        expected = (vectors @ np.diag(values) @ vectors.T) @ features
        actual = q93.spectral_projection(values, vectors, features)
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)

    def test_node_label_conjugation_preserves_spectrum_symmetry_and_row_sum(self):
        pair = self.make_pair_residual(93004)
        values, vectors, _ = q93.spectral_modes(pair, 2)
        operator = vectors @ np.diag(values) @ vectors.T
        permutation = q93.fixed_permutations()[0]
        projected = q93.permuted_spectral_projection(
            values, vectors, np.random.default_rng(93005).normal(size=(40, 6)), permutation
        )
        features = np.random.default_rng(93005).normal(size=(40, 6))
        explicit = operator[np.ix_(permutation, permutation)] @ features
        np.testing.assert_allclose(projected, explicit, atol=1e-12, rtol=0)
        conjugated = operator[np.ix_(permutation, permutation)]
        np.testing.assert_allclose(np.linalg.eigvalsh(conjugated), np.linalg.eigvalsh(operator), atol=1e-10, rtol=0)
        np.testing.assert_allclose(conjugated, conjugated.T, atol=1e-12, rtol=0)
        np.testing.assert_allclose(conjugated @ np.ones(40), 0.0, atol=1e-9, rtol=0)

    def test_zero_residual_is_stable(self):
        values, vectors, fraction = q93.spectral_modes(np.zeros((40, 40)), 4)
        self.assertEqual(values.size, 0)
        self.assertEqual(vectors.shape, (40, 0))
        self.assertEqual(fraction, 0.0)
        projected = q93.spectral_projection(values, vectors, np.ones((40, 6)))
        np.testing.assert_array_equal(projected, np.zeros((40, 6)))

    def test_permutation_catalog_is_fixed_unique_and_excludes_identity(self):
        first = q93.fixed_permutations()
        second = q93.fixed_permutations()
        self.assertEqual(len(first), 99)
        self.assertEqual(len({tuple(x.tolist()) for x in first}), 99)
        self.assertEqual([x.tolist() for x in first], [x.tolist() for x in second])
        identity = tuple(range(40))
        self.assertNotIn(identity, {tuple(x.tolist()) for x in first})

    def test_permuted_operator_is_exact_conjugation(self):
        pair = self.make_pair_residual(93006)
        values, vectors, _ = q93.spectral_modes(pair, 4)
        features = np.random.default_rng(93007).normal(size=(40, 6))
        permutation = q93.fixed_permutations()[2]
        inverse = np.argsort(permutation)
        operator = vectors @ np.diag(values) @ vectors.T
        expected = operator[np.ix_(permutation, permutation)] @ features
        actual = q93.permuted_spectral_projection(values, vectors, features, permutation)
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
        np.testing.assert_allclose(actual, operator[np.ix_(permutation, permutation)] @ features, atol=1e-12, rtol=0)

    def test_ewma_uses_only_prefix_rows(self):
        history = np.random.default_rng(93008).normal(size=(60, 40))
        expected = q88.rolling_signed_transfer(history, 24, 20, 0.80)
        changed = history.copy()
        changed[25:] = np.random.default_rng(93009).normal(size=changed[25:].shape) * 100
        actual = q88.rolling_signed_transfer(changed, 24, 20, 0.80)
        np.testing.assert_array_equal(actual, expected)

    def test_chronological_split_is_pinned(self):
        labels = q93.split_labels(3203)
        self.assertEqual(labels.count("discovery"), 1921)
        self.assertEqual(labels.count("validation"), 641)
        self.assertEqual(labels.count("blind_oos"), 641)

    def test_model_and_test_families_are_fixed(self):
        self.assertEqual(q93.FOCAL, "Q93::SPECTRAL_K2")
        self.assertEqual(q93.K_VALUES, (1, 2, 4))
        self.assertEqual(q93.PERMUTATION_COUNT, 99)
        self.assertEqual(len(q93.MODEL_IDS), 8)
        self.assertEqual(len(q93.COMPARATORS), 6)
        self.assertEqual(len(q93.ENDPOINTS), 3)

    def test_q90_equal42_control_is_deterministic(self):
        draws = q87.read_draws()
        history = draws[:q93.MIN_HISTORY]
        first = q90.equal42_rank(history)
        second = q90.equal42_rank(history)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(sorted(first.tolist()), list(range(1, 41)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
