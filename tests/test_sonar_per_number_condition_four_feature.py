#!/usr/bin/env python3
"""Acceptance tests for Q81's batched four-feature formula grammar."""
import importlib.util
import itertools
import math
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
Q80_SPEC = importlib.util.spec_from_file_location("sonar_q80_for_q81_tests", ROOT / "scripts" / "sonar_per_number_condition_grammar.py")
Q80 = importlib.util.module_from_spec(Q80_SPEC)
assert Q80_SPEC and Q80_SPEC.loader
Q80_SPEC.loader.exec_module(Q80)
Q81_SPEC = importlib.util.spec_from_file_location("sonar_q81", ROOT / "scripts" / "sonar_per_number_condition_four_feature.py")
Q81 = importlib.util.module_from_spec(Q81_SPEC)
assert Q81_SPEC and Q81_SPEC.loader
Q81_SPEC.loader.exec_module(Q81)


class Q81FourFeatureTests(unittest.TestCase):
    def test_all_four_feature_combinations_are_unique(self):
        expected = math.comb(27, 4)
        self.assertEqual(expected, 17550)
        self.assertEqual(len(Q81.FORMULAS), expected)
        self.assertEqual(len(set(Q81.FORMULAS)), expected)
        self.assertEqual(Q81.FORMULAS[0], (0, 1, 2, 3))
        self.assertEqual(Q81.FORMULAS[-1], (23, 24, 25, 26))

    def test_batched_ranks_match_scalar_reference(self):
        rng = np.random.default_rng(81027)
        standardized = rng.normal(size=(40, 27))
        formulas = np.asarray(list(itertools.islice(itertools.combinations(range(27), 4), 9)), dtype=np.int16)
        actual = Q81.rank_formula_batch(standardized, formulas)
        self.assertEqual(actual.shape, (40, len(formulas)))
        for j, cols in enumerate(formulas):
            scores = standardized[:, cols].mean(axis=1)
            order = np.lexsort((np.arange(40), -scores))
            expected = np.empty(40, dtype=np.int16)
            expected[order] = np.arange(1, 41, dtype=np.int16)
            np.testing.assert_array_equal(actual[:, j], expected)

    def test_ties_are_deterministic_and_favor_lower_number(self):
        standardized = np.ones((40, 27), dtype=np.float64)
        formulas = np.asarray([(0, 1, 2, 3), (23, 24, 25, 26)], dtype=np.int16)
        ranks = Q81.rank_formula_batch(standardized, formulas)
        expected = np.arange(1, 41, dtype=np.int64)
        np.testing.assert_array_equal(ranks[:, 0], expected)
        np.testing.assert_array_equal(ranks[:, 1], expected)

    def test_target_features_ignore_the_target_draw(self):
        draws_a = [(1,2,3,4,5),(1,7,8,9,10),(2,11,12,13,14),(15,16,17,18,19)]
        draws_b = list(draws_a)
        draws_b[3] = (21,22,23,24,25)
        i = 3
        prefix = np.zeros((len(draws_a)+1,40),dtype=np.int32)
        pos = np.zeros((len(draws_a)+1,5,40),dtype=np.int32)
        for j, draw in enumerate(draws_a):
            prefix[j+1] = prefix[j]
            pos[j+1] = pos[j]
            for p, value in enumerate(draw):
                prefix[j+1,value-1] += 1
                pos[j+1,p,value-1] += 1
        occ = [[] for _ in range(40)]
        pair = np.zeros((40,40),dtype=np.int32)
        for j, draw in enumerate(draws_a[:i]):
            for value in draw:
                occ[value-1].append(j)
            for a,b in itertools.combinations(draw,2):
                pair[a-1,b-1] += 1
                pair[b-1,a-1] += 1
        zeros = np.zeros(40)
        a = Q80.feature_matrix(i, draws_a, prefix, pos, pair, occ, zeros, zeros, zeros)
        b = Q80.feature_matrix(i, draws_b, prefix, pos, pair, occ, zeros, zeros, zeros)
        np.testing.assert_array_equal(a, b)
        self.assertTrue(np.isfinite(a).all())

    def test_chronological_splits_cover_every_scored_target(self):
        scored = 3388 - Q81.MIN_HISTORY
        sizes = {name: sum(Q80.split_name(i, scored) == name for i in range(scored))
                 for name in ("discovery", "validation", "blind_oos")}
        self.assertEqual(sizes, {"discovery": 2003, "validation": 668, "blind_oos": 667})
        self.assertEqual(sum(sizes.values()), scored)


if __name__ == "__main__":
    unittest.main(verbosity=2)
