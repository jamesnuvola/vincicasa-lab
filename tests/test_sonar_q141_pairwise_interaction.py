#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, random, sys, unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry
import sonar_q141_pairwise_interaction as interaction


class Q141PairwiseInteractionTests(unittest.TestCase):
    def test_complete_pair_catalog_and_stable_formula_ids(self):
        catalog = interaction.build_formula_catalog()
        self.assertEqual(len(catalog), 300)
        ids = [item[key] for item in catalog for key in ("additive_formula_id", "interaction_formula_id")]
        self.assertEqual(len(ids), 600)
        self.assertEqual(len(set(ids)), 600)
        self.assertEqual([item["feature_left"] for item in catalog[:24]],
                         list(registry.CANONICAL_FEATURE_NAMES[0:1]) * 24)
        self.assertEqual(len(set(item["family_group"] for item in catalog)), 21)

    def test_interaction_is_additive_plus_standardized_product(self):
        rng = np.random.default_rng(14120261114)
        z = rng.normal(size=(40, 25))
        additive, enhanced = interaction.interaction_scores(z, 2, 11)
        product = z[:, 2] * z[:, 11]
        expected = additive + (product - product.mean()) / product.std()
        np.testing.assert_allclose(enhanced, expected, rtol=0, atol=1e-14)

    def test_constant_product_falls_back_to_additive_without_nan(self):
        z = np.zeros((40, 25), dtype=np.float64)
        z[:, 0] = np.linspace(-1, 1, 40)
        additive, enhanced = interaction.interaction_scores(z, 0, 1)
        np.testing.assert_array_equal(additive, enhanced)
        self.assertTrue(np.all(np.isfinite(enhanced)))

    def test_deterministic_tie_break_matches_q141_ranker(self):
        ranks = base.rank_scores(np.zeros(40, dtype=np.float64))
        np.testing.assert_array_equal(ranks, np.arange(1, 41, dtype=np.int16))

    def test_future_suffix_and_target_outcome_invariance(self):
        rng = random.Random(14120261114)
        draws = [tuple(sorted(rng.sample(range(40), 5))) for _ in range(120)]
        target = 80
        prefix_a, pos_a = base.build_prefix_arrays(draws)
        pair_counts = np.zeros((40, 40), dtype=np.int32)
        occurrences = [[] for _ in range(40)]
        for index, draw in enumerate(draws[:target]):
            for value in draw:
                occurrences[value].append(index)
            for a, b in itertools.combinations(draw, 2):
                pair_counts[a, b] += 1
                pair_counts[b, a] += 1
        changed = list(draws[:target])
        changed.extend(tuple(sorted(rng.sample(range(40), 5))) for _ in range(len(draws) - target))
        changed[target] = tuple(sorted((x + 1) % 40 for x in changed[target]))
        prefix_b, pos_b = base.build_prefix_arrays(changed)
        fa = base.feature_matrix(target, draws, prefix_a, pos_a, pair_counts, occurrences)
        fb = base.feature_matrix(target, changed, prefix_b, pos_b, pair_counts, occurrences)
        za = base.zscore_columns(fa[:, list(base.UNIQUE_FEATURE_INDICES)])
        zb = base.zscore_columns(fb[:, list(base.UNIQUE_FEATURE_INDICES)])
        np.testing.assert_array_equal(fa, fb)
        np.testing.assert_array_equal(za, zb)
        for i, j in ((0, 1), (2, 11), (7, 24)):
            aa, ia = interaction.interaction_scores(za, i, j)
            ab, ib = interaction.interaction_scores(zb, i, j)
            np.testing.assert_array_equal(aa, ab)
            np.testing.assert_array_equal(ia, ib)
            np.testing.assert_array_equal(base.rank_scores(ia), base.rank_scores(ib))

    def test_one_sided_block_signflip_is_deterministic_and_directional(self):
        positive = np.linspace(0.001, 0.02, 200)
        negative = -positive
        p1 = interaction.one_sided_block_signflip_p(positive, 14120261114)
        p2 = interaction.one_sided_block_signflip_p(positive, 14120261114)
        pn = interaction.one_sided_block_signflip_p(negative, 14120261114)
        self.assertEqual(p1, p2)
        self.assertLess(p1, 0.05)
        self.assertGreater(pn, 0.5)

    def test_holm_adjustment(self):
        adjusted = interaction.holm_adjust([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06], rtol=0, atol=1e-12)

    def test_registered_formula_family_size_and_preregistration(self):
        prereg_path = ROOT / "reports" / "sequence_agent" / "q141_pairwise_interaction_preregistration_2026-11-12.json"
        prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
        self.assertEqual(prereg["task_id"], "Q141-B4")
        self.assertEqual(prereg["status"], "PREREGISTERED_EXECUTION_PENDING")
        self.assertEqual(prereg["formula_universe"]["pair_count"], 300)
        self.assertEqual(prereg["inference"]["registered_test_family_size"], 13)
        self.assertEqual(prereg["walkforward"]["target_count"], 3354)


if __name__ == "__main__":
    unittest.main(verbosity=2)
