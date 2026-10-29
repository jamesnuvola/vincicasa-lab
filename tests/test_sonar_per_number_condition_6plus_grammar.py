#!/usr/bin/env python3
"""Acceptance tests for the exhaustive six-feature Q86 formula grammar."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_per_number_condition_6plus_grammar as Q86
import sonar_per_number_condition_grammar as Q80


def synthetic_draws(count):
    draws = []
    for i in range(count):
        values = sorted(((i * 7 + j * 11) % 40) + 1 for j in range(5))
        if len(set(values)) != 5:
            raise AssertionError("synthetic draw collision")
        draws.append(tuple(values))
    return draws


class Q86GrammarTests(unittest.TestCase):
    def test_all_five_feature_combinations_are_unique(self):
        formulas = Q86.make_formulas()
        self.assertEqual(len(Q86.FEATURE_NAMES), 27)
        self.assertEqual(len(formulas), math.comb(27, 6))
        self.assertEqual(len(formulas), 296010)
        self.assertEqual(len(set(formulas)), 296010)
        self.assertEqual(formulas[0], (0, 1, 2, 3, 4, 5))
        self.assertEqual(formulas[-1], (21, 22, 23, 24, 25, 26))

    def test_feature_stack_uses_only_draws_before_target(self):
        a = synthetic_draws(55)
        b = list(a)
        b[-1] = tuple(sorted(((55 * 7 + j * 13 + 3) % 40) + 1 for j in range(5)))
        self.assertEqual(len(set(b[-1])), 6)
        fa = Q86.build_feature_stack(a)
        fb = Q86.build_feature_stack(b)
        self.assertEqual(fa.shape, (5, 40, 27))
        np.testing.assert_array_equal(fa[-1], fb[-1])

    def test_rank_ties_are_deterministic_by_number(self):
        ranks = Q86.rank_matrix(np.zeros((40, 7), dtype=np.float64))
        np.testing.assert_array_equal(ranks[:, 0], np.arange(1, 41, dtype=np.int16))
        np.testing.assert_array_equal(ranks[:, 6], np.arange(1, 41, dtype=np.int16))

    def test_chronological_splits_cover_every_scored_target(self):
        scored = 101
        counts = {s: sum(Q80.split_name(i, scored) == s for i in range(scored))
                  for s in ("discovery", "validation", "blind_oos")}
        self.assertEqual(counts, {"discovery": 61, "validation": 20, "blind_oos": 20})
        self.assertEqual(sum(counts.values()), scored)

    def test_formula_batches_cover_the_universe_without_gaps(self):
        batches = Q86.batch_ranges(296010, 1024)
        self.assertEqual(len(batches), 290)
        self.assertEqual(batches[0], (0, 1024))
        self.assertEqual(batches[-1], (79872, 296010))
        self.assertEqual(sum(end - start for start, end in batches), 296010)
        for previous, current in zip(batches, batches[1:]):
            self.assertEqual(previous[1], current[0])

    def test_formula_weight_matrix_has_equal_weights_and_five_variables(self):
        formulas = Q86.make_formulas()[:3]
        weights = Q86.build_formula_weight_matrix(formulas)
        self.assertEqual(weights.shape, (27, 3))
        for i, formula in enumerate(formulas):
            self.assertAlmostEqual(float(weights[:, i].sum()), 1.0)
            self.assertEqual(int(np.count_nonzero(weights[:, i])), 6)
            self.assertTrue(all(weights[col, i] == 1/6 for col in formula))


if __name__ == "__main__":
    unittest.main(verbosity=2)
