#!/usr/bin/env python3
"""Acceptance tests for the Q86 six-feature formula grammar and shard partition."""
import itertools
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_per_number_condition_grammar as Q80
import sonar_per_number_condition_5plus_grammar as Q83
import sonar_per_number_condition_6plus_grammar as Q86
from aggregate_sonar_per_number_condition_6plus import holm_adjust_matrix


def synthetic_draws(count):
    draws = []
    for i in range(count):
        values = sorted((((i * 7 + j * 11) % 40) + 1) for j in range(5))
        if len(set(values)) != 5:
            raise AssertionError("synthetic draw collision")
        draws.append(tuple(values))
    return draws


class Q86GrammarTests(unittest.TestCase):
    def test_six_feature_universe_count_and_boundary_ids(self):
        self.assertEqual(Q86.FEATURE_COUNT, 27)
        self.assertEqual(Q86.FORMULA_COUNT, math.comb(27, 6))
        self.assertEqual(Q86.FORMULA_COUNT, 296010)
        first = Q86.formula_slice(0, 1)[0]
        last = Q86.formula_slice(Q86.FORMULA_COUNT - 1, Q86.FORMULA_COUNT)[0]
        self.assertEqual(first, (0, 1, 2, 3, 4, 5))
        self.assertEqual(last, (21, 22, 23, 24, 25, 26))
        self.assertEqual(Q86.formula_id(0, first), "P6_00_01_02_03_04_05")

    def test_shard_ranges_cover_every_formula_without_gaps(self):
        count = Q86.FORMULA_COUNT
        shards = 16
        ranges = [(count * i // shards, count * (i + 1) // shards) for i in range(shards)]
        self.assertEqual(ranges[0][0], 0)
        self.assertEqual(ranges[-1][1], count)
        self.assertEqual(sum(end - start for start, end in ranges), count)
        for previous, current in zip(ranges, ranges[1:]):
            self.assertEqual(previous[1], current[0])
        self.assertTrue(all(end > start for start, end in ranges))

    def test_formula_weight_matrix_has_six_equal_weights(self):
        formulas = Q86.formula_slice(0, 4)
        weights = Q86.build_formula_weight_matrix(formulas)
        self.assertEqual(weights.shape, (27, 4))
        for column, formula in enumerate(formulas):
            self.assertEqual(int(np.count_nonzero(weights[:, column])), 6)
            self.assertAlmostEqual(float(weights[:, column].sum()), 1.0)
            self.assertTrue(all(weights[index, column] == 1 / 6 for index in formula))

    def test_feature_stack_uses_only_prefix_before_target(self):
        a = synthetic_draws(56)
        b = list(a)
        replacement = sorted((((56 * 7 + j * 13 + 3) % 40) + 1) for j in range(5))
        self.assertEqual(len(set(replacement)), 5)
        b[-1] = tuple(replacement)
        features_a = Q83.build_feature_stack(a)
        features_b = Q83.build_feature_stack(b)
        self.assertEqual(features_a.shape, (6, 40, 27))
        np.testing.assert_array_equal(features_a[-1], features_b[-1])

    def test_rank_ties_are_deterministic_by_number(self):
        ranks = Q83.rank_matrix(np.zeros((40, 11), dtype=np.float64))
        expected = np.arange(1, 41, dtype=np.int16)
        for column in range(ranks.shape[1]):
            np.testing.assert_array_equal(ranks[:, column], expected)

    def test_chronological_splits_cover_all_targets(self):
        scored = 101
        counts = {split: sum(Q80.split_name(i, scored) == split for i in range(scored))
                  for split in Q86.SPLITS}
        self.assertEqual(counts, {"discovery": 61, "validation": 20, "blind_oos": 20})
        self.assertEqual(sum(counts.values()), scored)

    def test_global_holm_adjustment_is_monotone_and_not_below_raw_p(self):
        raw = np.asarray([[0.001, 0.02, 0.1], [0.004, 0.03, 0.2], [0.2, 0.4, 0.8]], dtype=float)
        adjusted = holm_adjust_matrix(raw)
        self.assertEqual(adjusted.shape, raw.shape)
        self.assertTrue(np.all(adjusted >= raw))
        self.assertTrue(np.all(adjusted <= 1.0))
        flat = raw.reshape(-1)
        adj_flat = adjusted.reshape(-1)
        order = np.argsort(flat, kind="stable")
        sorted_adj = adj_flat[order]
        self.assertTrue(np.all(np.diff(sorted_adj) >= -1e-12))


if __name__ == "__main__":
    unittest.main(verbosity=2)
