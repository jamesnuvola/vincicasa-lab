#!/usr/bin/env python3
"""Unit tests for Q92 deterministic ten-feature combinadic catalog."""
import itertools
import math
import random
import sys
import unittest

ROOT=__import__("pathlib").Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q92_common as q92
import sonar_per_number_condition_10plus_shard as q92shard

class Q92FormulaUniverseTests(unittest.TestCase):
    def test_exact_catalog_count_and_endpoints(self):
        self.assertEqual(q92.TOTAL_FORMULA_COUNT,8_436_285)
        self.assertEqual(q92.SHARD_COUNT,15)
        self.assertEqual(q92.SHARD_SIZE,562_419)
        self.assertEqual(q92.FORMULA_BATCH_SIZE,1024)
        self.assertEqual(len(q92.batch_ranges(q92.SHARD_SIZE)),550)
        self.assertEqual(q92.formula_id(q92.formula_unrank(0)),"P10_00_01_02_03_04_05_06_07_08_09")
        self.assertEqual(q92.formula_id(q92.formula_unrank(q92.TOTAL_FORMULA_COUNT-1)),"P10_17_18_19_20_21_22_23_24_25_26")

    def test_rank_unrank_round_trip(self):
        ranks=[0,1,100,562_418,562_419,4_218_142,q92.TOTAL_FORMULA_COUNT-1]
        rng=random.Random(920027)
        ranks.extend(rng.randrange(q92.TOTAL_FORMULA_COUNT) for _ in range(1000))
        for value in ranks:
            columns=q92.formula_unrank(value)
            self.assertEqual(q92.formula_rank(columns),value)
            self.assertEqual(q92.formula_unrank(q92.formula_rank(columns)),columns)

    def test_shards_are_contiguous_and_cover_universe(self):
        cursor=0
        for shard in range(q92.SHARD_COUNT):
            start,end=q92.shard_bounds(shard)
            self.assertEqual(start,cursor)
            self.assertEqual(end-start,q92.SHARD_SIZE)
            self.assertEqual(q92.formula_rank(q92.formula_unrank(start)),start)
            self.assertEqual(q92.formula_rank(q92.formula_unrank(end-1)),end-1)
            cursor=end
        self.assertEqual(cursor,q92.TOTAL_FORMULA_COUNT)

    def test_successor_matches_lexicographic_rank(self):
        columns=q92.formula_unrank(1000)
        for expected_rank in range(1000,1100):
            self.assertEqual(q92.formula_rank(columns),expected_rank)
            columns=q92.next_formula(columns)
            self.assertIsNotNone(columns)
            self.assertEqual(q92.formula_rank(columns),expected_rank+1)

    def test_formula_slice_matches_combinations(self):
        for shard in (0,1,7,14):
            start,end=q92.shard_bounds(shard)
            sample=list(q92.iter_formula_slice(start,min(start+25,end)))
            self.assertEqual(len(sample),25)
            self.assertEqual(q92.formula_rank(sample[0]),start)
            self.assertEqual(q92.formula_rank(sample[-1]),start+24)
            self.assertEqual(sample,list(itertools.islice(itertools.combinations(range(27),10),start,start+25)))

    def test_hypergeometric_null_values_are_bounded(self):
        targets=670
        for top_k in (5,10,20):
            probability=top_k/40
            expected_mean=targets*5*probability
            expected_variance=targets*5*probability*(1-probability)*35/39
            self.assertGreater(expected_mean,0)
            self.assertGreater(expected_variance,0)
            value=q92.hypergeom_upper_normal_p(round(expected_mean),targets,top_k)
            self.assertGreaterEqual(value,0)
            self.assertLessEqual(value,1)

    def test_invalid_inputs_fail_closed(self):
        with self.assertRaises(ValueError): q92.formula_unrank(-1)
        with self.assertRaises(ValueError): q92.formula_unrank(q92.TOTAL_FORMULA_COUNT)
        with self.assertRaises(ValueError): q92.shard_bounds(15)
        with self.assertRaises(ValueError): q92.formula_id((0,1,2,3,4,5,6,7,8,8))
        with self.assertRaises(ValueError): q92.batch_ranges(10,0)


    def test_ten_feature_shard_schema_and_equal_weight_matrix(self):
        self.assertEqual(q92shard.FORMULA_SIZE,10)
        self.assertEqual(q92shard.SHARD_SIZE,562_419)
        self.assertEqual(q92shard.SHARD_INDEX,0)
        formulas=[q92.formula_unrank(0),q92.formula_unrank(1),q92.formula_unrank(100)]
        weights=q92shard.build_formula_weight_matrix(formulas)
        self.assertEqual(weights.shape,(27,3))
        for column in range(weights.shape[1]):
            self.assertEqual(int(np.count_nonzero(weights[:,column])),10)
            self.assertAlmostEqual(float(weights[:,column].sum()),1.0,places=14)
            self.assertTrue(np.allclose(weights[weights[:,column]!=0,column],0.1))

    def test_stable_rank_matrix_and_actual_number_lookup(self):
        scores=np.zeros((40,2),dtype=np.float64)
        scores[0,:]=1.0
        scores[1,1]=2.0
        ranks=q92shard.rank_matrix(scores)
        self.assertEqual(ranks[0,0],1)
        self.assertEqual(ranks[1,0],2)
        self.assertEqual(ranks[1,1],1)
        self.assertEqual(ranks[0,1],2)
        self.assertEqual(sorted(ranks[:,0].tolist()),list(range(1,41)))

if __name__=="__main__":
    unittest.main(verbosity=2)
