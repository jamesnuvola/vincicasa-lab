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
        self.assertEqual(self.spec["feature_count"], 27)
        self.assertEqual(len(self.spec["features"]), 27)
        self.assertEqual(self.spec["formula_count"], math.comb(27, 7))
        self.assertEqual(self.spec["formula_count"], 888030)
        self.assertEqual(self.spec["formula_count_check"], 888030)

    def test_six_shards_are_contiguous_and_equal(self):
        shard_count = self.spec["shard_count"]
        shard_size = self.spec["shard_formula_count"]
        total = self.spec["formula_count"]
        self.assertEqual(shard_count, 6)
        self.assertEqual(shard_size, 148005)
        self.assertEqual(total % shard_count, 0)
        self.assertEqual(shard_size * shard_count, total)
        cursor = 0
        for index in range(shard_count):
            start = index * shard_size
            end = start + shard_size
            self.assertEqual(start, cursor)
            self.assertEqual(end - start, shard_size)
            cursor = end
        self.assertEqual(cursor, total)

    def test_batch_manifest_arithmetic_and_coverage(self):
        total = self.spec["formula_count"]
        batch_size = self.spec["formula_batch_size"]
        batches = self.spec["batch_manifest"]
        self.assertEqual(batch_size, 1024)
        self.assertEqual(self.spec["formula_batch_count"], math.ceil(total / batch_size))
        self.assertEqual(len(batches), math.ceil(total / batch_size))
        cursor = 0
        for index, batch in enumerate(batches):
            start = batch["formula_start_inclusive"]
            end = batch["formula_end_exclusive"]
            self.assertEqual(batch["batch_index"], index)
            self.assertEqual(start, cursor)
            self.assertEqual(end, min(start + batch_size, total))
            self.assertEqual(batch["formula_count"], end - start)
            cursor = end
        self.assertEqual(cursor, total)
        self.assertEqual(batches[0]["formula_id_first"], "P7_00_01_02_03_04_05_06")
        self.assertEqual(batches[-1]["formula_id_last"], "P7_20_21_22_23_24_25_26")

    def test_test_family_and_output_dimensions(self):
        formula_count = self.spec["formula_count"]
        splits = self.spec["split_counts"]
        self.assertEqual(set(splits), {"discovery", "validation", "blind_oos"})
        self.assertEqual(sum(splits.values()), self.spec["scored_targets"])
        self.assertEqual(self.spec["metrics_rows"], formula_count * len(splits))
        self.assertEqual(self.spec["target_ledger_rows"], self.spec["scored_targets"])
        self.assertEqual(
            self.spec["multiple_testing"]["test_count"],
            formula_count * len(splits) * 3,
        )

    def test_sample_formula_ids_are_unique_and_stable(self):
        formulas = list(itertools.islice(itertools.combinations(range(27), 7), 1000))
        ids = ["P7_" + "_".join(f"{i:02d}" for i in cols) for cols in formulas]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "P7_00_01_02_03_04_05_06")
        self.assertEqual(ids[-1], "P7_00_01_02_03_09_12_26")


if __name__ == "__main__":
    unittest.main(verbosity=2)
