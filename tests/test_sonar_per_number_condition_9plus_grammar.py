#!/usr/bin/env python3
"""Acceptance/unit tests for the finite Q89 nine-feature formula universe."""
import itertools
import math
import random
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_condition_grammar as q80
import sonar_q89_common as q89
import aggregate_sonar_q89_shards as q89agg

class Q89FormulaUniverseTests(unittest.TestCase):
    def test_aggregator_runtime_constants_are_bound(self):
        self.assertEqual(q89agg.MIN_HISTORY,q80.MIN_HISTORY)
        self.assertEqual(q89agg.FEATURE_COUNT,q89.FEATURE_COUNT)
        self.assertEqual(q89agg.FORMULA_SIZE,q89.FORMULA_SIZE)

    def test_exact_formula_count_and_endpoints(self):
        self.assertEqual(q89.TOTAL_FORMULA_COUNT,4_686_825)
        self.assertEqual(q89.SHARD_COUNT,15)
        self.assertEqual(q89.SHARD_SIZE,312_455)
        self.assertEqual(q89.formula_id(q89.formula_unrank(0)),"P9_00_01_02_03_04_05_06_07_08")
        self.assertEqual(q89.formula_id(q89.formula_unrank(q89.TOTAL_FORMULA_COUNT-1)),"P9_18_19_20_21_22_23_24_25_26")

    def test_rank_unrank_round_trip(self):
        ranks=[0,1,100,312_454,312_455,4_374_370,q89.TOTAL_FORMULA_COUNT-1]
        rng=random.Random(890027)
        ranks.extend(rng.randrange(q89.TOTAL_FORMULA_COUNT) for _ in range(1000))
        for value in ranks:
            columns=q89.formula_unrank(value)
            self.assertEqual(q89.formula_rank(columns),value)
            self.assertEqual(q89.formula_unrank(q89.formula_rank(columns)),columns)

    def test_shards_are_contiguous_and_cover_universe(self):
        cursor=0
        for shard in range(q89.SHARD_COUNT):
            start,end=q89.shard_bounds(shard)
            self.assertEqual(start,cursor)
            self.assertEqual(end-start,q89.SHARD_SIZE)
            self.assertEqual(q89.formula_rank(q89.formula_unrank(start)),start)
            self.assertEqual(q89.formula_rank(q89.formula_unrank(end-1)),end-1)
            cursor=end
        self.assertEqual(cursor,q89.TOTAL_FORMULA_COUNT)

    def test_successor_matches_lexicographic_rank(self):
        columns=q89.formula_unrank(1000)
        for expected_rank in range(1000,1100):
            self.assertEqual(q89.formula_rank(columns),expected_rank)
            columns=q89.next_formula(columns)
            self.assertIsNotNone(columns)
            self.assertEqual(q89.formula_rank(columns),expected_rank+1)

    def test_formula_slice_has_exact_rank_bounds(self):
        for shard in (0,1,7,14):
            start,end=q89.shard_bounds(shard)
            sample=list(q89.iter_formula_slice(start,min(start+20,end)))
            self.assertEqual(len(sample),min(20,end-start))
            self.assertEqual(q89.formula_rank(sample[0]),start)
            self.assertEqual(q89.formula_rank(sample[-1]),start+len(sample)-1)
            self.assertEqual(sample,list(itertools.islice(itertools.combinations(range(27),9),start,start+len(sample))))

    def test_hypergeometric_null_variance(self):
        targets=670
        for top_k in (5,10,20):
            p=top_k/40
            expected_mean=targets*5*p
            expected_var=targets*5*p*(1-p)*35/39
            self.assertGreater(expected_mean,0)
            self.assertGreater(expected_var,0)
            value=q89.hypergeom_upper_normal_p(int(expected_mean),targets,top_k)
            self.assertGreaterEqual(value,0)
            self.assertLessEqual(value,1)

    def test_holm_adjustment_known_family(self):
        self.assertEqual(q89agg.holm_adjust([0.01,0.04,0.03]),[0.03,0.06,0.06])

    def test_block_bootstrap_and_signflip_replay(self):
        differences=[(index%5)-2 for index in range(670)]
        ci1=q89agg.bootstrap_ci(differences,replicates=300,block_length=7,seed=890027)
        ci2=q89agg.bootstrap_ci(differences,replicates=300,block_length=7,seed=890027)
        self.assertEqual(ci1,ci2)
        self.assertLessEqual(ci1[0],ci1[1])
        p1=q89agg.block_signflip_p(differences,replicates=500,block_length=7,seed=890028)
        p2=q89agg.block_signflip_p(differences,replicates=500,block_length=7,seed=890028)
        self.assertEqual(p1,p2)
        self.assertGreaterEqual(p1,0)
        self.assertLessEqual(p1,1)

if __name__=="__main__":
    unittest.main(verbosity=2)
