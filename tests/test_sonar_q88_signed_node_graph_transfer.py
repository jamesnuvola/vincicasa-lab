#!/usr/bin/env python3
"""Regression tests for Q88 signed node-to-graph transfer."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q88_signed_node_graph_transfer as q88


class Q88SignedTransferTests(unittest.TestCase):
    def test_projection_has_six_neighbor_feature_channels(self):
        prior = np.zeros((40, 6), dtype=np.float64)
        prior[0, 0] = 1.0
        edge = np.zeros((40, 40), dtype=np.float64)
        for i in range(1, 40):
            edge[i, 0] = 0.5
            edge[0, i] = 0.5
        projected = q88.projected_graph_change(edge, prior)
        self.assertEqual(projected.shape, (40, 6))
        np.testing.assert_allclose(projected[1:, 0], 0.5 / np.sqrt(39.0), atol=1e-12)
        np.testing.assert_allclose(projected[:, 1:], 0.0, atol=1e-12)

    def test_signed_transfer_alignment_preserves_positive_and_negative_direction(self):
        prior = np.zeros((40, 6), dtype=np.float64)
        prior[0, 0] = 1.0
        edge = np.zeros((40, 40), dtype=np.float64)
        for i in range(1, 40):
            edge[i, 0] = 1.0
            edge[0, i] = 1.0
        node_delta = np.zeros((40, 6), dtype=np.float64)
        node_delta[1:, 0] = 1.0
        positive = q88.signed_transfer_alignment(node_delta, edge, prior)
        negative = q88.signed_transfer_alignment(node_delta, -edge, prior)
        np.testing.assert_allclose(positive[1:], 1.0, atol=1e-12)
        np.testing.assert_allclose(negative[1:], -1.0, atol=1e-12)

    def test_signed_cosine_detects_alignment_opposition_and_orthogonality(self):
        left = np.zeros((40, 6), dtype=np.float64)
        right = np.zeros((40, 6), dtype=np.float64)
        left[:, 0] = 1.0
        right[:, 0] = 2.0
        right[1::3, 0] = -2.0
        right[2::3, 0] = 0.0
        right[2::3, 1] = 1.0
        result = q88.rowwise_signed_cosine(left, right)
        self.assertEqual(result[0], 1.0)
        self.assertEqual(result[1], -1.0)
        self.assertEqual(result[2], 0.0)
        self.assertTrue(np.all(np.abs(result) <= 1.0))

    def test_zero_norm_is_neutral(self):
        zeros = np.zeros((40, 6), dtype=np.float64)
        ones = np.ones((40, 6), dtype=np.float64)
        np.testing.assert_array_equal(q88.rowwise_signed_cosine(zeros, ones), np.zeros(40))
        np.testing.assert_array_equal(q88.rowwise_signed_cosine(ones, zeros), np.zeros(40))

    def test_rolling_transfer_is_strictly_prefix_only(self):
        rng = np.random.default_rng(8801)
        values = rng.uniform(-1.0, 1.0, size=(50, 40))
        expected = q88.rolling_signed_transfer(values, 24)
        changed = values.copy()
        changed[25:] = rng.uniform(-100.0, 100.0, size=changed[25:].shape)
        actual = q88.rolling_signed_transfer(changed, 24)
        np.testing.assert_array_equal(actual, expected)

    def test_rolling_transfer_uses_latest_transition_weight_one(self):
        values = np.zeros((20, 40), dtype=np.float64)
        values[-1] = 1.0
        result = q88.rolling_signed_transfer(values, 19)
        self.assertTrue(np.all(result > 0.0))
        self.assertTrue(np.all(result < 1.0))
        first = np.ones((1, 40), dtype=np.float64)
        one_row = q88.rolling_signed_transfer(first, 0)
        np.testing.assert_array_equal(one_row, np.ones(40))

    def test_transfer_projection_rejects_asymmetric_or_nonzero_diagonal_graph(self):
        prior = np.ones((40, 6), dtype=np.float64)
        bad = np.zeros((40, 40), dtype=np.float64)
        bad[0, 1] = 1.0
        with self.assertRaises(ValueError):
            q88.projected_graph_change(bad, prior)
        bad = np.zeros((40, 40), dtype=np.float64)
        np.fill_diagonal(bad, 1.0)
        with self.assertRaises(ValueError):
            q88.projected_graph_change(bad, prior)

    def test_transfer_projection_rejects_shape_and_nonfinite_inputs(self):
        with self.assertRaises(ValueError):
            q88.projected_graph_change(np.zeros((40, 39)), np.zeros((40, 6)))
        bad = np.zeros((40, 6))
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            q88.projected_graph_change(np.zeros((40, 40)), bad)

    def test_operator_scores_are_fixed_alpha_and_finite(self):
        base = np.linspace(-1.0, 1.0, 40)
        reversion = np.linspace(1.0, -1.0, 40)
        graph = np.sin(np.arange(40, dtype=np.float64))
        transfer = np.linspace(-1.0, 1.0, 40)
        scores = q88.transfer_operator_scores(base, reversion, graph, transfer)
        self.assertEqual(tuple(scores), q88.DYNAMIC_IDS)
        self.assertEqual(len(scores), 3)
        self.assertTrue(all(x.shape == (40,) and np.isfinite(x).all() for x in scores.values()))
        signal = q88.q87.field.zscore(transfer)
        np.testing.assert_allclose(scores[q88.DYNAMIC_IDS[0]] - base, 0.20 * reversion * signal, atol=1e-12)
        np.testing.assert_allclose(scores[q88.DYNAMIC_IDS[1]] - base, 0.20 * graph * signal, atol=1e-12)
        np.testing.assert_allclose(scores[q88.DYNAMIC_IDS[2]] - base, 0.20 * 0.5 * (reversion + graph) * signal, atol=1e-12)

    def test_registered_families_and_cutoff_dimensions(self):
        self.assertEqual(len(q88.MODEL_IDS), 15)
        self.assertEqual(len(q88.DYNAMIC_IDS), 3)
        self.assertEqual(len(q88.MODEL_IDS) * 3 * 3, 135)
        self.assertEqual(2 * len(q88.COMPARATORS) * 4, 96)
        self.assertEqual(q88.WINDOW, 20)
        self.assertEqual(q88.DECAY, 0.80)
        self.assertEqual(q88.ALPHA, 0.20)
        self.assertEqual(q88.EXPECTED_DRAWS - q88.q87.q86.q84.MIN_HISTORY, q88.EXPECTED_TARGETS)

    def test_rank_helper_returns_stable_permutation(self):
        rank = q88.q87.field.rank_from_scores(np.linspace(-1.0, 1.0, 40))
        self.assertEqual(sorted(rank.tolist()), list(range(1, 41)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
