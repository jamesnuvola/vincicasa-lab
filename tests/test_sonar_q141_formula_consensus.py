#!/usr/bin/env python3
"""Synthetic leakage, determinism and tie-policy tests for Q141-C3."""
from __future__ import annotations

import random
import sys
import unittest
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_consensus as consensus
import sonar_q141_formula_registry as registry


def synthetic_features(draws, target_index):
    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrences = [[] for _ in range(40)]
    for i, draw in enumerate(draws[:target_index]):
        for value in draw:
            occurrences[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1
    return base.feature_matrix(
        target_index, draws, prefix, pos_prefix, pair_counts, occurrences
    )


class FormulaConsensusTests(unittest.TestCase):
    def test_frozen_sample_is_deterministic_and_exactly_deduplicated(self):
        first = consensus.build_formula_sample()
        second = consensus.build_formula_sample()
        self.assertEqual(first, second)
        formulas, raw_count = first
        self.assertEqual(raw_count, 120)
        self.assertEqual(len(formulas), 113)
        self.assertEqual(len({row["formula_id"] for row in formulas}), 113)

    def test_rank_ascending_uses_number_as_deterministic_tie_break(self):
        values = np.array([0.0] * 40)
        ranks = consensus.rank_ascending(values)
        self.assertTrue(np.array_equal(ranks, np.arange(1, 41)))

    def test_consensus_rankings_are_deterministic_and_complete(self):
        rng = np.random.default_rng(14120261112)
        features = rng.normal(size=(40, 27))
        models_a, controls_a, diagnostics_a = consensus.consensus_rankings(features)
        models_b, controls_b, diagnostics_b = consensus.consensus_rankings(features)
        self.assertEqual(set(models_a), {"borda_mean_rank", "median_rank", "top5_vote"})
        self.assertEqual(set(controls_a), {"equal_family", "equal_feature"})
        for name in models_a:
            self.assertTrue(np.array_equal(models_a[name], models_b[name]))
            self.assertEqual(set(models_a[name].tolist()), set(range(1, 41)))
        for name in controls_a:
            self.assertTrue(np.array_equal(controls_a[name], controls_b[name]))
        self.assertEqual(diagnostics_a, diagnostics_b)

    def test_future_suffix_and_target_outcome_invariance(self):
        rng = random.Random(14120261112)
        draws = [tuple(sorted(rng.sample(range(40), 5))) for _ in range(90)]
        target_index = 65
        mutated = list(draws[:target_index]) + [
            tuple(sorted(rng.sample(range(40), 5)))
            for _ in range(len(draws) - target_index)
        ]
        features_a = synthetic_features(draws, target_index)
        features_b = synthetic_features(mutated, target_index)
        self.assertTrue(np.array_equal(features_a, features_b))
        models_a, controls_a, _ = consensus.consensus_rankings(features_a)
        models_b, controls_b, _ = consensus.consensus_rankings(features_b)
        for name in models_a:
            self.assertTrue(np.array_equal(models_a[name], models_b[name]))
        for name in controls_a:
            self.assertTrue(np.array_equal(controls_a[name], controls_b[name]))

        target_mutated = list(draws)
        target_mutated[target_index] = tuple(sorted(rng.sample(range(40), 5)))
        target_mutated[target_index + 1:] = [
            tuple(sorted(rng.sample(range(40), 5)))
            for _ in range(len(target_mutated) - target_index - 1)
        ]
        features_c = synthetic_features(target_mutated, target_index)
        self.assertTrue(np.array_equal(features_a, features_c))
        models_c, controls_c, _ = consensus.consensus_rankings(features_c)
        for name in models_a:
            self.assertTrue(np.array_equal(models_a[name], models_c[name]))
        for name in controls_a:
            self.assertTrue(np.array_equal(controls_a[name], controls_c[name]))

    def test_git_blob_sha1_uses_the_canonical_nul_header(self):
        data = b"abc"
        expected = hashlib.sha1(b"blob 3\\0abc").hexdigest()
        self.assertEqual(consensus.git_blob_sha1(data), expected)

    def test_alias_canonicalization_uses_one_vote_per_unique_formula(self):
        raw_sample = registry.sample_formulas()
        ids = {
            registry.canonical_formula_id(registry.canonicalize_formula(columns)[0])
            for columns in raw_sample
        }
        self.assertEqual(len(raw_sample), 120)
        self.assertEqual(len(ids), 113)
        self.assertEqual(len(consensus.FORMULAS), 113)


if __name__ == "__main__":
    unittest.main(verbosity=2)
