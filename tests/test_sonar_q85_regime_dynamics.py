#!/usr/bin/env python3
"""Regression tests for Q85 causal state-transition gates."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q85_regime_dynamics as q85
import sonar_per_number_field_dynamics as field


class Q85RegimeDynamicsTests(unittest.TestCase):
    def test_midrank_percentile_uses_only_supplied_prior_values(self):
        self.assertAlmostEqual(q85.empirical_midrank_percentile(2.0, [1.0, 2.0, 3.0], minimum_history=1), 0.5)
        self.assertEqual(q85.empirical_midrank_percentile(100.0, [1.0, 2.0], minimum_history=3), 0.5)
        prior = [1.0, 2.0, 3.0]
        value = q85.empirical_midrank_percentile(2.0, prior, minimum_history=1)
        prior.append(999.0)
        self.assertAlmostEqual(value, 0.5)

    def test_alpha_gates_are_bounded_and_oppositely_monotone(self):
        self.assertAlmostEqual(q85.alpha_up(0.0), 0.10)
        self.assertAlmostEqual(q85.alpha_up(1.0), 0.30)
        self.assertAlmostEqual(q85.alpha_down(0.0), 0.30)
        self.assertAlmostEqual(q85.alpha_down(1.0), 0.10)
        for percentile in np.linspace(0.0, 1.0, 101):
            self.assertGreaterEqual(q85.alpha_up(percentile), 0.10)
            self.assertLessEqual(q85.alpha_up(percentile), 0.30)
            self.assertGreaterEqual(q85.alpha_down(percentile), 0.10)
            self.assertLessEqual(q85.alpha_down(percentile), 0.30)

    def test_transition_metrics_are_finite_and_nonnegative(self):
        features = np.ones((40, 6), dtype=np.float64)
        edge = np.ones((40, 40), dtype=np.float64)
        previous_features = np.zeros((40, 6), dtype=np.float64)
        previous_edge = np.zeros((40, 40), dtype=np.float64)
        result = q85.transition_metrics(features, edge, previous_features, previous_edge, None, None)
        self.assertEqual(len(result), 6)
        self.assertGreaterEqual(result[0], 0.0)
        self.assertEqual(result[1], 0.0)
        self.assertGreaterEqual(result[2], 0.0)
        self.assertEqual(result[3], 0.0)
        self.assertEqual(result[4].shape, (40, 6))
        self.assertEqual(result[5].shape, (40, 40))

    def test_acceleration_detects_change_in_velocity(self):
        features = np.full((40, 6), 2.0)
        edge = np.full((40, 40), 3.0)
        previous_features = np.ones((40, 6))
        previous_edge = np.ones((40, 40))
        previous_node_delta = np.zeros((40, 6))
        previous_edge_delta = np.zeros((40, 40))
        result = q85.transition_metrics(features, edge, previous_features, previous_edge,
                                        previous_node_delta, previous_edge_delta)
        self.assertAlmostEqual(result[1], 1.0)
        self.assertAlmostEqual(result[3], 2.0)

    def test_transition_ledger_columns_match_registered_schema(self):
        transition = {name: np.asarray([float(index + 1)]) for index, name in enumerate((
            "node_speed", "node_acceleration", "graph_speed", "graph_acceleration",
            "node_percentile", "graph_percentile", "alpha_rev_up", "alpha_rev_down",
            "alpha_graph_up", "alpha_graph_down",
        ))}
        values = q85.transition_ledger_values(transition, 0)
        self.assertEqual(set(values), set(q85.ledger_fields()[:16]) - {
            "target_date", "cutoff_date", "prior_draws", "actual_quintet", "split", "field_state_sha256"
        })
        self.assertEqual(values["node_acceleration_percentile"], "5")
        self.assertEqual(values["alpha_rev_node_up"], "7")


    def test_rank_helper_is_stable_permutation(self):
        scores = np.linspace(-1.0, 1.0, 40)
        rank = field.rank_from_scores(scores)
        self.assertEqual(sorted(rank.tolist()), list(range(1, 41)))

    def test_field_state_is_prefix_invariant_to_future_appends(self):
        draws = []
        for i in range(130):
            nums = tuple(sorted({((i * 7 + j * 11) % 40) + 1 for j in range(5)}))
            self.assertEqual(len(nums), 5)
            draws.append({"nums": nums})
        prefix = q85.field_state_for_target(draws, 120)
        extended = q85.field_state_for_target(draws + draws[120:], 120)
        self.assertEqual(prefix["signature"], extended["signature"])
        np.testing.assert_array_equal(prefix["features"], extended["features"])
        np.testing.assert_array_equal(prefix["graph_signal"], extended["graph_signal"])

    def test_registered_model_and_family_dimensions(self):
        self.assertEqual(len(q85.MODEL_IDS), 8)
        self.assertEqual(len(q85.DYNAMIC_IDS), 4)
        self.assertEqual(len(q85.MODEL_IDS) * 3 * 3, 72)
        self.assertEqual(2 * 4 * 4, 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
