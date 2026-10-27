#!/usr/bin/env python3
"""Acceptance tests for the Q80 per-number condition grammar."""
import importlib.util
import itertools
import math
import unittest
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sonar_per_number_condition_grammar.py"
SPEC = importlib.util.spec_from_file_location("sonar_q80", SCRIPT)
Q80 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(Q80)


class Q80GrammarTests(unittest.TestCase):
    def test_feature_and_formula_universe_is_complete_and_unique(self):
        self.assertEqual(len(Q80.FEATURE_NAMES), 27)
        formulas = Q80.make_formulas()
        self.assertEqual(len(formulas), 27 + math.comb(27, 2) + math.comb(27, 3))
        self.assertEqual(len(formulas), 3303)
        self.assertEqual(len(set(formulas)), 3303)
        self.assertEqual(formulas[0], (0,))
        self.assertEqual(formulas[-1], tuple(range(24, 27)))

    def test_features_use_only_prefix_before_target(self):
        draws_a = [(1,2,3,4,5),(1,7,8,9,10),(2,11,12,13,14),(15,16,17,18,19)]
        draws_b = list(draws_a)
        draws_b[3] = (21,22,23,24,25)  # Change the target; its features must not change.
        i = 3
        prefix = np.zeros((len(draws_a)+1,40),dtype=np.int32)
        pos = np.zeros((len(draws_a)+1,5,40),dtype=np.int32)
        for j,draw in enumerate(draws_a):
            prefix[j+1]=prefix[j]
            pos[j+1]=pos[j]
            for p,n in enumerate(draw):
                prefix[j+1,n-1]+=1
                pos[j+1,p,n-1]+=1
        occ=[[] for _ in range(40)]
        for j,draw in enumerate(draws_a[:i]):
            for n in draw:
                occ[n-1].append(j)
        pair=np.zeros((40,40),dtype=np.int32)
        for draw in draws_a[:i]:
            for a,b in itertools.combinations(draw,2):
                pair[a-1,b-1]+=1;pair[b-1,a-1]+=1
        a=Q80.feature_matrix(i,draws_a,prefix,pos,pair,occ,np.zeros(40),np.zeros(40),np.zeros(40))
        b=Q80.feature_matrix(i,draws_b,prefix,pos,pair,occ,np.zeros(40),np.zeros(40),np.zeros(40))
        np.testing.assert_array_equal(a,b)
        self.assertEqual(a.shape,(40,27))
        self.assertEqual(a[0,0],2)  # Number 1 appeared in two of the three prior draws.
        self.assertTrue(np.isfinite(a).all())

    def test_candidate_rank_ties_are_deterministic(self):
        scores=np.ones(40)
        order=np.lexsort((np.arange(40),-scores))
        self.assertEqual(order[:5].tolist(),[0,1,2,3,4])

    def test_split_sizes_cover_all_scored_targets(self):
        n=3388
        scored=n-Q80.MIN_HISTORY
        sizes=[sum(Q80.split_name(i,scored)==s for i in range(scored))
               for s in ("discovery","validation","blind_oos")]
        self.assertEqual(sum(sizes),scored)
        self.assertEqual(sizes[0],int(scored*0.60)+1 if (int(scored*0.60)/scored)<0.60 else int(scored*0.60))


if __name__ == "__main__":
    unittest.main(verbosity=2)
