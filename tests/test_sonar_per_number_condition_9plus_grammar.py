#!/usr/bin/env python3
from __future__ import annotations
import itertools, math, sys, unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_condition_9plus_shard as q89
import aggregate_sonar_q89_shards as agg

class Q89NineFeatureTests(unittest.TestCase):
    def test_declared_universe_and_balanced_shards(self):
        self.assertEqual(q89.TOTAL_FORMULA_COUNT,math.comb(27,9))
        self.assertEqual(q89.TOTAL_FORMULA_COUNT,4686825)
        sizes=[(q89.TOTAL_FORMULA_COUNT*(i+1))//30-(q89.TOTAL_FORMULA_COUNT*i)//30 for i in range(30)]
        self.assertEqual(sum(sizes),q89.TOTAL_FORMULA_COUNT)
        self.assertLessEqual(max(sizes)-min(sizes),1)
        self.assertEqual(q89.SHARD_COUNT,30)
        self.assertEqual(len(q89.FORMULAS),q89.SHARD_SIZE)
        self.assertEqual(q89.SHARD_SIZE,sizes[q89.SHARD_INDEX])

    def test_lexicographic_unrank_and_range_iterator(self):
        expected=list(itertools.combinations(range(8),3))
        for rank in (0,1,4,5,10,20,len(expected)-1):
            self.assertEqual(q89.unrank_lex_combination(8,3,rank),expected[rank])
            self.assertEqual(agg.unrank_lex_combination(8,3,rank),expected[rank])
        self.assertEqual(list(q89.iter_lex_combinations_range(8,3,5,15)),expected[5:15])
        self.assertEqual(q89.unrank_lex_combination(27,9,0),tuple(range(9)))
        self.assertEqual(q89.unrank_lex_combination(27,9,4686824),tuple(range(18,27)))

    def test_formula_rank_is_inverse_of_unrank(self):
        for rank in (0,1,2,100,10000,1000000,4686824):
            self.assertEqual(agg.formula_rank(agg.unrank_lex_combination(27,9,rank)),rank)

    def test_shard_formula_ids_are_canonical_and_unique(self):
        self.assertEqual(len(set(q89.FORMULAS)),q89.SHARD_SIZE)
        self.assertEqual(len(set(q89.FORMULA_IDS)),q89.SHARD_SIZE)
        self.assertTrue(all(fid.startswith("P9_") for fid in q89.FORMULA_IDS))
        self.assertTrue(all(len(x)==9 for x in q89.FORMULAS))

    def test_feature_stack_excludes_target_and_future_draws(self):
        draws=[tuple(sorted(((i*3+j*7)%40)+1 for j in range(5))) for i in range(52)]
        base=q89.build_feature_stack(draws)
        changed=list(draws); changed[50]=(2,4,6,8,10)
        changed_stack=q89.build_feature_stack(changed)
        np.testing.assert_allclose(base[0],changed_stack[0],rtol=0,atol=0)
        future=list(draws); future[51]=(1,5,9,13,17)
        future_stack=q89.build_feature_stack(future)
        np.testing.assert_allclose(base[0],future_stack[0],rtol=0,atol=0)
        np.testing.assert_allclose(base[1],future_stack[1],rtol=0,atol=0)

    def test_rank_matrix_is_complete_and_deterministic(self):
        scores=np.zeros((40,2),dtype=np.float64); scores[7,0]=1.0
        ranks=q89.rank_matrix(scores)
        self.assertEqual(ranks.shape,(40,2))
        self.assertEqual(sorted(ranks[:,0].tolist()),list(range(1,41)))
        self.assertEqual(ranks[0,1],1)
        self.assertEqual(ranks[7,0],1)

    def test_chernoff_bound_dominates_exact_small_sample_tail(self):
        for top_k in (5,10,20):
            probs=np.asarray(agg.hypergeom_probabilities(top_k),dtype=np.float64)
            self.assertAlmostEqual(float(probs.sum()),1.0,places=13)
            self.assertAlmostEqual(float(sum(h*p for h,p in enumerate(probs))),5*top_k/40,places=13)
            exact=np.asarray([1.0])
            for _ in range(3): exact=np.convolve(exact,probs)
            tail=np.cumsum(exact[::-1])[::-1]
            bound=agg.build_chernoff_tail_table(3,top_k)
            self.assertEqual(len(bound),16)
            self.assertTrue(np.all(bound+1e-12>=tail))
            self.assertTrue(np.all(np.diff(bound)<=1e-12))

    def test_chunked_holm_matches_reference(self):
        raw=np.asarray([0.04,0.002,0.03,0.01,0.8,0.12],dtype=np.float64)
        expected=raw.copy(); order=np.argsort(expected,kind="stable")
        adjusted=np.maximum.accumulate((len(raw)-np.arange(len(raw)))*expected[order])
        expected[order]=np.minimum(adjusted,1.0)
        np.testing.assert_allclose(agg.apply_holm_inplace(raw.copy(),chunk_size=2),expected,rtol=0,atol=1e-14)

    def test_validation_selection_uses_only_discovery_and_validation(self):
        top=[{"formula_id":"P9_00_01_02_03_04_05_06_07_08"},
             {"formula_id":"P9_00_01_02_03_04_05_06_07_09"},
             {"formula_id":"P9_00_01_02_03_04_05_06_07_10"}]
        rows={
          top[0]["formula_id"]:{"mean_number_hits_top5":"0.20","mean_rank_of_actual_numbers":"19.0"},
          top[1]["formula_id"]:{"mean_number_hits_top5":"0.22","mean_rank_of_actual_numbers":"19.5"},
          top[2]["formula_id"]:{"mean_number_hits_top5":"0.21","mean_rank_of_actual_numbers":"18.0"}}
        self.assertEqual(agg.select_validation_candidate(top,rows),top[1]["formula_id"])

if __name__=="__main__":
    unittest.main(verbosity=2)
