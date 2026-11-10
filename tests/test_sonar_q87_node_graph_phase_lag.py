#!/usr/bin/env python3
"""Regression tests for Q87 causal node/graph phase-lag features."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q87_node_graph_phase_lag as q87


class Q87NodeGraphPhaseLagTests(unittest.TestCase):
    def test_positive_lag_means_node_leads_graph(self):
        rng = np.random.default_rng(8701)
        node = rng.normal(size=(100, 40))
        graph = np.zeros_like(node)
        graph[1:] = node[:-1]
        forward = q87.lagged_correlation(node, graph, 1, "node_leads_graph")
        backward = q87.lagged_correlation(node, graph, 1, "graph_leads_node")
        np.testing.assert_allclose(forward, np.ones(40), atol=1e-12)
        self.assertLess(float(np.mean(backward)), 0.2)

    def test_negative_lag_means_graph_leads_node(self):
        rng = np.random.default_rng(8702)
        graph = rng.normal(size=(100, 40))
        node = np.zeros_like(graph)
        node[1:] = graph[:-1]
        backward = q87.lagged_correlation(node, graph, 1, "graph_leads_node")
        forward = q87.lagged_correlation(node, graph, 1, "node_leads_graph")
        np.testing.assert_allclose(backward, np.ones(40), atol=1e-12)
        self.assertLess(float(np.mean(forward)), 0.2)

    def test_zero_variance_and_insufficient_pairs_are_neutral(self):
        constant = np.ones((50, 40))
        result = q87.lagged_correlation(constant, constant, 1, "node_leads_graph")
        np.testing.assert_array_equal(result, np.zeros(40))
        short = q87.lagged_correlation(constant[:20], constant[:20], 1, "node_leads_graph", minimum_pairs=30)
        np.testing.assert_array_equal(short, np.zeros(40))

    def test_phase_features_use_only_prefix_through_target_offset(self):
        rng = np.random.default_rng(8703)
        node = rng.normal(size=(120, 40))
        graph = rng.normal(size=(120, 40))
        expected = q87.phase_lag_features(node, graph, 70)
        changed_future_node = node.copy()
        changed_future_graph = graph.copy()
        changed_future_node[71:] = rng.normal(loc=100.0, size=changed_future_node[71:].shape)
        changed_future_graph[71:] = rng.normal(loc=-100.0, size=changed_future_graph[71:].shape)
        actual = q87.phase_lag_features(changed_future_node, changed_future_graph, 70)
        for left, right in zip(expected, actual):
            np.testing.assert_array_equal(left, right)

    def test_phase_asymmetry_and_bidirectional_coherence_identities(self):
        rng = np.random.default_rng(8704)
        node = rng.normal(size=(100, 40))
        graph = rng.normal(size=(100, 40))
        forward, backward, asymmetry, coherence = q87.phase_lag_features(node, graph, 99)
        np.testing.assert_allclose(asymmetry, forward - backward, atol=1e-12)
        np.testing.assert_allclose(coherence, 0.5 * (forward + backward), atol=1e-12)
        self.assertTrue(np.all(np.abs(forward) <= 1.0))
        self.assertTrue(np.all(np.abs(backward) <= 1.0))
        self.assertTrue(np.all(np.abs(asymmetry) <= 2.0))
        self.assertTrue(np.all(np.abs(coherence) <= 1.0))

    def test_phase_lag_features_reject_invalid_shapes_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            q87.phase_lag_features(np.zeros((10, 40)), np.zeros((10, 39)), 9)
        bad = np.zeros((10, 40))
        bad[0, 0] = np.nan
        with self.assertRaises(ValueError):
            q87.phase_lag_features(bad, np.zeros((10, 40)), 9)
        with self.assertRaises(ValueError):
            q87.phase_lag_features(np.zeros((10, 40)), np.zeros((10, 40)), 10)

    def test_operator_scores_have_fixed_alpha_and_expected_signs(self):
        base = np.linspace(-1.0, 1.0, 40)
        reversion = np.linspace(1.0, -1.0, 40)
        graph = np.sin(np.arange(40, dtype=np.float64))
        forward = np.linspace(-0.5, 0.5, 40)
        backward = np.linspace(0.4, -0.4, 40)
        asymmetry = forward - backward
        coherence = 0.5 * (forward + backward)
        scores = q87.phase_operator_scores(base, reversion, graph, forward, backward, asymmetry, coherence)
        self.assertEqual(tuple(scores), q87.DYNAMIC_IDS)
        self.assertEqual(len(scores), 4)
        self.assertTrue(all(value.shape == (40,) and np.isfinite(value).all() for value in scores.values()))
        np.testing.assert_allclose(scores[q87.DYNAMIC_IDS[0]] - base,
                                   0.20 * reversion * q87.field.zscore(forward), atol=1e-12)
        np.testing.assert_allclose(scores[q87.DYNAMIC_IDS[1]] - base,
                                   0.20 * graph * q87.field.zscore(backward), atol=1e-12)

    def test_model_and_multiple_testing_families_are_registered(self):
        self.assertEqual(len(q87.MODEL_IDS), 12)
        self.assertEqual(len(q87.DYNAMIC_IDS), 4)
        self.assertEqual(len(q87.MODEL_IDS) * 3 * 3, 108)
        self.assertEqual(2 * len(q87.COMPARATORS) * 4, 32)
        self.assertEqual(q87.WINDOW, 80)
        self.assertEqual(q87.LAGS, (1, 2, 3))
        self.assertEqual(q87.MIN_PAIRED, 30)

    def test_ledger_contains_all_per_number_phase_and_rank_fields(self):
        fields = q87.ledger_fields()
        for name in ("node_leads_graph_01", "graph_leads_node_40",
                     "phase_asymmetry_20", "bidirectional_phase_coherence_40",
                     "rank_base_equal42_01"):
            self.assertIn(name, fields)
        for prefix in ("node_leads_graph_", "graph_leads_node_",
                       "phase_asymmetry_", "bidirectional_phase_coherence_"):
            self.assertEqual(sum(name.startswith(prefix) and name[-2:].isdigit() for name in fields), 40)

    def test_lag_direction_is_not_silently_reversed(self):
        rng = np.random.default_rng(8705)
        node = rng.normal(size=(100, 40))
        graph = np.zeros_like(node)
        graph[1:] = node[:-1]
        forward, backward, asymmetry, coherence = q87.phase_lag_features(node, graph, 99)
        self.assertGreater(float(forward.mean()), float(backward.mean()))
        np.testing.assert_allclose(asymmetry, forward - backward, atol=1e-12)
        np.testing.assert_allclose(coherence, 0.5 * (forward + backward), atol=1e-12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
