#!/usr/bin/env python3
from __future__ import annotations

import math
import random
import sys
import unittest
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry


class Q141FormulaRegistryTests(unittest.TestCase):
    def test_feature_schema_and_exact_aliases(self):
        self.assertEqual(len(registry.RAW_FEATURE_NAMES), 27)
        self.assertEqual(len(registry.CANONICAL_FEATURE_NAMES), 25)
        self.assertEqual(registry.ALIASES, {"recent_5": "freq_5", "recent_10": "freq_10"})
        self.assertEqual(registry.RAW_TO_CANONICAL[0], registry.RAW_TO_CANONICAL[25])
        self.assertEqual(registry.RAW_TO_CANONICAL[1], registry.RAW_TO_CANONICAL[26])

    def test_canonical_ids_preserve_alias_multiplicity(self):
        sig_a, scale_a = registry.canonicalize_formula((0,))
        sig_b, scale_b = registry.canonicalize_formula((0, 25))
        self.assertEqual(sig_a, sig_b)
        self.assertEqual(registry.canonical_formula_id(sig_a), registry.canonical_formula_id(sig_b))
        self.assertNotEqual(scale_a, scale_b)

        sig_c, _ = registry.canonicalize_formula((1,))
        sig_d, _ = registry.canonicalize_formula((1, 26))
        self.assertEqual(sig_c, sig_d)

        sig_e, _ = registry.canonicalize_formula((0, 1))
        sig_f, _ = registry.canonicalize_formula((0, 1, 25, 26))
        self.assertEqual(sig_e, sig_f)

        sig_g, _ = registry.canonicalize_formula((0, 1))
        sig_h, _ = registry.canonicalize_formula((0, 1, 25))
        self.assertNotEqual(sig_g, sig_h)

    def test_exact_formula_counts(self):
        expected_within_size = [
            25, 302, 2348, 13203, 57201,
            198605, 567479, 1359622, 2768832, 4840649,
        ]
        for k, expected in enumerate(expected_within_size, start=1):
            self.assertEqual(registry.unique_within_size(k), expected)
        raw = sum(math.comb(27, k) for k in range(1, 11))
        self.assertEqual(raw, 16628808)
        self.assertEqual(registry.unique_global_count(10), 9808263)
        self.assertEqual(raw - registry.unique_global_count(10), 6820545)
        self.assertEqual(sum(expected_within_size) - registry.unique_global_count(10), 3)

    def test_canonical_score_matches_raw_formula_and_naive_deletion_fails(self):
        rng = np.random.default_rng(14120261112)
        matrix = rng.normal(size=(40, 27))
        matrix[:, 25] = matrix[:, 0]
        matrix[:, 26] = matrix[:, 1]
        formulas = [(0,), (0, 25), (0, 1, 25), (0, 1, 25, 26), (1, 2, 3, 26)]
        for columns in formulas:
            signature, scale = registry.canonicalize_formula(columns)
            stable_raw = registry.stable_raw_scores(matrix, columns)
            legacy_numpy = matrix[:, list(columns)].mean(axis=1)
            canonical = registry.canonical_scores(matrix, signature, scale)
            self.assertTrue(np.allclose(stable_raw, canonical, rtol=0.0, atol=1e-12))
            self.assertTrue(np.array_equal(base.rank_scores(stable_raw), base.rank_scores(canonical)))
            self.assertTrue(np.allclose(legacy_numpy, canonical, rtol=0.0, atol=1e-12))

        columns = (0, 1, 25)
        raw_scores = registry.stable_raw_scores(matrix, columns)
        naive_deleted = matrix[:, [0, 1]].mean(axis=1)
        self.assertFalse(np.allclose(raw_scores, naive_deleted, rtol=0.0, atol=1e-12))

    def test_sample_is_deterministic_and_covers_cross_size_alias_cases(self):
        first = registry.sample_formulas()
        second = registry.sample_formulas()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 120)
        self.assertIn((0,), first)
        self.assertIn((0, 25), first)
        self.assertIn((1,), first)
        self.assertIn((1, 26), first)
        self.assertIn((0, 1), first)
        self.assertIn((0, 1, 25, 26), first)

    def test_future_suffix_invariance(self):
        rng = random.Random(14120261112)
        draws = [tuple(sorted(rng.sample(range(40), 5))) for _ in range(90)]
        target_index = 65
        mutated = list(draws[:target_index]) + [
            tuple(sorted(rng.sample(range(40), 5)))
            for _ in range(len(draws) - target_index)
        ]
        prefix_a, pos_a = base.build_prefix_arrays(draws)
        prefix_b, pos_b = base.build_prefix_arrays(mutated)

        pair_counts = np.zeros((40, 40), dtype=np.int32)
        occurrences = [[] for _ in range(40)]
        for i, draw in enumerate(draws[:target_index]):
            for value in draw:
                occurrences[value].append(i)
            for a, b in combinations(draw, 2):
                pair_counts[a, b] += 1
                pair_counts[b, a] += 1

        features_a = base.feature_matrix(
            target_index, draws, prefix_a, pos_a, pair_counts, occurrences
        )
        features_b = base.feature_matrix(
            target_index, mutated, prefix_b, pos_b, pair_counts, occurrences
        )
        self.assertTrue(np.array_equal(features_a, features_b))

    def test_registry_grammar_counts_reconcile(self):
        rows = registry.build_formula_grammars()
        self.assertEqual(len(rows), 10)
        for row in rows:
            k = row["formula_size"]
            self.assertEqual(row["nominal_formula_count"], math.comb(27, k))
            self.assertEqual(
                row["unique_canonical_formula_count_within_size"],
                registry.unique_within_size(k),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
