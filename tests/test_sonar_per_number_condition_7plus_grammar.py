#!/usr/bin/env python3
"""Acceptance tests for the registered Q87 seven-feature formula universe."""
import itertools
import json
import math
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports/sequence_agent/per_number_condition_7plus_grammar.json"

class Q87ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_formula_universe_is_exact(self):
        self.assertEqual(self.spec["formula_count"], math.comb(27, 7))
        self.assertEqual(self.spec["formula_count"], 888030)
        self.assertEqual(self.spec["formula_count_check"], 888030)

    def test_six_shards_are_contiguous_and_equal(self):
        shards = self.spec["shards"]
        self.assertEqual(len(shards), 6)
        cursor = 0
        for index, shard in enumerate(shards):
            self.assertEqual(shard["shard_index"], index)
            self.assertEqual(shard["formula_start_inclusive"], cursor)
            self.assertEqual(shard["formula_end_exclusive"] - cursor, 148005)
            self.assertEqual(shard["formula_count"], 148005)
            cursor = shard["formula_end_exclusive"]
        self.assertEqual(cursor, 888030)

    def test_batch_manifest_arithmetic(self):
        batch_size = self.spec["formula_batch_size"]
        self.assertEqual(batch_size, 1024)
        self.assertEqual(self.spec["formula_batch_count"], math.ceil(888030 / 1024))
        for shard in self.spec["shards"]:
            self.assertEqual(shard["formula_batch_count"], math.ceil(shard["formula_count"] / batch_size))

    def test_test_family_and_output_dimensions(self):
        self.assertEqual(self.spec["expected_metrics_rows"], 888030 * 3)
        self.assertEqual(self.spec["expected_holm_test_count"], 888030 * 3 * 3)
        self.assertEqual(self.spec["chronological_splits"], ["discovery", "validation", "blind_oos"])

    def test_sample_formula_ids_are_unique_and_stable(self):
        formulas = list(itertools.islice(itertools.combinations(range(27), 7), 1000))
        ids = ["P7_" + "_".join(f"{i:02d}" for i in cols) for cols in formulas]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "P7_00_01_02_03_04_05_06")
        self.assertEqual(ids[-1], "P7_00_01_02_03_09_12_26")

if __name__ == "__main__":
    unittest.main()
