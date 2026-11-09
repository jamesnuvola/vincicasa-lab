#!/usr/bin/env python3
"""Synthetic regression tests for Q92 combinadic enumeration and deterministic shards."""
import itertools
import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q92_common as q92

class Q92CombinadicTests(unittest.TestCase):
    def test_exact_formula_count_and_endpoints(self):
        self.assertEqual(q92.TOTAL_FORMULA_COUNT, 8_436_285)
        self.assertEqual(q92.SHARD_COUNT, 15)
        self.assertEqual(q92.SHARD_SIZE, 562_419)
        self.assertEqual(q92.formula_id(q92.formula_unrank(0)),
                         "P10_00_01_02_03_04_05_06_07_08_09")
        self.assertEqual(q92.formula_id(q92.formula_unrank(q92.TOTAL_FORMULA_COUNT - 1)),
                         "P10_17_18_19_20_21_22_23_24_25_26")

    def test_rank_unrank_round_trip_seeded(self):
        ranks = [0, 1, 100, q92.SHARD_SIZE - 1, q92.SHARD_SIZE,
                 2 * q92.SHARD_SIZE + 7, q92.TOTAL_FORMULA_COUNT - 1]
        rng = random.Random(920027)
        ranks.extend(rng.randrange(q92.TOTAL_FORMULA_COUNT) for _ in range(10_000))
        for value in ranks:
            columns = q92.formula_unrank(value)
            self.assertEqual(q92.formula_rank(columns), value)
            self.assertEqual(q92.formula_unrank(q92.formula_rank(columns)), columns)

    def test_shards_partition_every_rank_without_gap_or_overlap(self):
        cursor = 0
        for shard in range(q92.SHARD_COUNT):
            start, end = q92.shard_bounds(shard)
            self.assertEqual(start, cursor)
            self.assertEqual(end - start, q92.SHARD_SIZE)
            self.assertEqual(q92.formula_rank(q92.formula_unrank(start)), start)
            self.assertEqual(q92.formula_rank(q92.formula_unrank(end - 1)), end - 1)
            cursor = end
        self.assertEqual(cursor, q92.TOTAL_FORMULA_COUNT)
        self.assertEqual(q92.shard_bounds(14), (7_873_866, 8_436_285))

    def test_successor_matches_lexicographic_combinations(self):
        columns = q92.formula_unrank(10_000)
        expected = itertools.islice(itertools.combinations(range(27), 10), 10_000, 10_100)
        for expected_rank, expected_columns in enumerate(expected, start=10_000):
            self.assertEqual(columns, expected_columns)
            self.assertEqual(q92.formula_rank(columns), expected_rank)
            columns = q92.next_formula(columns)
            self.assertIsNotNone(columns)
            self.assertEqual(q92.formula_rank(columns), expected_rank + 1)

    def test_formula_slice_and_batch_ranges(self):
        for shard in (0, 1, 7, 14):
            start, end = q92.shard_bounds(shard)
            sample = list(q92.iter_formula_slice(start, min(start + 25, end)))
            self.assertEqual(len(sample), 25)
            self.assertEqual(q92.formula_rank(sample[0]), start)
            self.assertEqual(q92.formula_rank(sample[-1]), start + 24)
        batches = q92.batch_ranges(q92.SHARD_SIZE)
        self.assertEqual(len(batches), 550)
        self.assertEqual(batches[0], (0, 1024))
        self.assertEqual(batches[-1], (562_176, 562_419))
        self.assertEqual(sum(end - start for start, end in batches), q92.SHARD_SIZE)

    def test_invalid_formula_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            q92.formula_id(tuple(range(9)))
        with self.assertRaises(ValueError):
            q92.formula_unrank(-1)
        with self.assertRaises(ValueError):
            q92.formula_unrank(q92.TOTAL_FORMULA_COUNT)
        with self.assertRaises(ValueError):
            q92.shard_bounds(15)
        with self.assertRaises(ValueError):
            list(q92.iter_formula_slice(2, q92.TOTAL_FORMULA_COUNT + 1))

    def test_hypergeometric_null_approximation_is_bounded_and_replayable(self):
        targets = 670
        for top_k in (5, 10, 20):
            p = top_k / 40.0
            mean = targets * 5 * p
            value = q92.hypergeom_upper_normal_p(int(mean), targets, top_k)
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
            self.assertEqual(value, q92.hypergeom_upper_normal_p(int(mean), targets, top_k))

if __name__ == "__main__":
    unittest.main(verbosity=2)
