#!/usr/bin/env python3
"""Acceptance tests for Q82 conditional, nonlinear and interaction terms."""
import sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_condition_conditional_grammar as Q82
import sonar_per_number_condition_grammar as Q80
import sonar_per_number_condition_4plus_grammar as Q81

def synthetic_draws(count):
    draws=[]
    for i in range(count):
        values=sorted(((i*7+j*11)%40)+1 for j in range(5))
        if len(set(values))!=5: raise AssertionError("synthetic draw collision")
        draws.append(tuple(values))
    return draws

class Q82GrammarTests(unittest.TestCase):
    def test_finite_grammar_counts_and_unique_ids(self):
        self.assertEqual(Q82.FAMILY_COUNTS,{"base":27,"nonlinear":108,"interaction":351,"conditional":4212})
        self.assertEqual(Q82.EXPECTED_FORMULA_COUNT,4698)
        terms=Q82.make_term_definitions()
        self.assertEqual(len(terms),4698)
        self.assertEqual(len({x["formula_id"] for x in terms}),4698)
        self.assertEqual(sum(x["formula_family"]=="conditional" for x in terms),4212)

    def test_thresholds_are_frozen_from_discovery_only(self):
        stack=np.zeros((8,40,27),dtype=np.float64)
        for i in range(8):
            stack[i]=i
        thresholds=Q82.select_thresholds(stack,4)
        changed=stack.copy()
        changed[4:]=1e6
        later=Q82.select_thresholds(changed,4)
        np.testing.assert_array_equal(thresholds,later)
        self.assertEqual(thresholds.shape,(27,3))
        self.assertTrue(np.isfinite(thresholds).all())

    def test_term_score_dimensions_and_finite_values(self):
        z=np.arange(40*27,dtype=np.float64).reshape(40,27)/100.0
        thresholds=np.zeros((27,3),dtype=np.float64)
        scores=Q82.build_term_scores(z,thresholds)
        self.assertEqual(scores.shape,(40,4698))
        self.assertTrue(np.isfinite(scores).all())
        np.testing.assert_array_equal(scores[:,0:27],z)

    def test_prior_only_stack_and_deterministic_rank_ties(self):
        draws=synthetic_draws(55)
        stack=Q81.build_feature_stack(draws)
        self.assertEqual(stack.shape,(5,40,27))
        changed=list(draws)
        changed[-1]=tuple(sorted(((55*7+j*13+3)%40)+1 for j in range(5)))
        self.assertEqual(len(set(changed[-1])),5)
        changed_stack=Q81.build_feature_stack(changed)
        np.testing.assert_array_equal(stack[-1],changed_stack[-1])
        ranks=Q81.rank_matrix(np.ones((40,7),dtype=np.float64))
        np.testing.assert_array_equal(ranks[:,0],np.arange(1,41,dtype=np.int16))

    def test_chronological_splits_cover_all_scored_targets(self):
        scored=3388-Q80.MIN_HISTORY
        counts={s:sum(Q80.split_name(i,scored)==s for i in range(scored)) for s in Q82.SPLITS}
        self.assertEqual(counts,{"discovery":2003,"validation":668,"blind_oos":667})
        self.assertEqual(sum(counts.values()),scored)

if __name__=="__main__":
    unittest.main(verbosity=2)
