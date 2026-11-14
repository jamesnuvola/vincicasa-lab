#!/usr/bin/env python3
from __future__ import annotations
import itertools, json, random, sys, unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry
import sonar_q141_triple_interaction as triple


class Q141TripleInteractionTests(unittest.TestCase):
    def test_complete_triple_catalog_and_stable_formula_ids(self):
        catalog = triple.build_formula_catalog()
        self.assertEqual(len(catalog), 2300)
        ids = [item[key] for item in catalog for key in ("additive_formula_id", "interaction_formula_id")]
        self.assertEqual(len(ids), 4600)
        self.assertEqual(len(set(ids)), 4600)
        self.assertEqual((catalog[0]["feature_i"], catalog[0]["feature_j"], catalog[0]["feature_k"]), (0, 1, 2))
        self.assertEqual(catalog[0]["feature_i_name"], registry.CANONICAL_FEATURE_NAMES[0])
        self.assertEqual(catalog[-1]["feature_k"], 24)

    def test_vectorized_three_way_formula_matches_scalar_definition(self):
        rng = np.random.default_rng(14120261115)
        z = rng.normal(size=(40, 25))
        triples = np.asarray([(0, 1, 2), (2, 11, 24), (5, 6, 7)], dtype=np.int16)
        additive, interaction = triple.triple_score_matrices(z, triples)
        for col, (i, j, k) in enumerate(triples):
            expected_add = z[:, i] + z[:, j] + z[:, k]
            product = z[:, i] * z[:, j] * z[:, k]
            sd = float(product.std())
            expected_product = np.zeros(40) if sd < 1e-12 else (product - product.mean()) / sd
            np.testing.assert_allclose(additive[:, col], expected_add, rtol=0, atol=1e-14)
            np.testing.assert_allclose(interaction[:, col], expected_add + expected_product, rtol=0, atol=1e-14)

    def test_vectorized_ranker_matches_scalar_ranker_and_tie_policy(self):
        rng = np.random.default_rng(14120261115)
        scores = rng.normal(size=(40, 12))
        scores[:, 0] = 0.0
        ranks = triple.rank_score_matrix(scores)
        np.testing.assert_array_equal(ranks[:, 0], np.arange(1, 41, dtype=np.int16))
        for col in range(scores.shape[1]):
            np.testing.assert_array_equal(ranks[:, col], base.rank_scores(scores[:, col]))

    def test_constant_three_way_product_falls_back_to_additive(self):
        z = np.zeros((40, 25), dtype=np.float64)
        z[:, 0] = np.linspace(-1, 1, 40)
        z[:, 1] = np.linspace(1, -1, 40)
        triples = np.asarray([(0, 1, 2)], dtype=np.int16)
        additive, interaction = triple.triple_score_matrices(z, triples)
        np.testing.assert_array_equal(additive, interaction)
        self.assertTrue(np.all(np.isfinite(interaction)))

    def test_future_suffix_and_target_outcome_invariance(self):
        rng = random.Random(14120261115)
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
        changed = list(draws)
        changed[target] = tuple(sorted((x + 1) % 40 for x in draws[target]))
        for index in range(target + 1, len(changed)):
            changed[index] = tuple(sorted(rng.sample(range(40), 5)))
        prefix_b, pos_b = base.build_prefix_arrays(changed)
        fa = base.feature_matrix(target, draws, prefix_a, pos_a, pair_counts, occurrences)
        fb = base.feature_matrix(target, changed, prefix_b, pos_b, pair_counts, occurrences)
        za = base.zscore_columns(fa[:, list(base.UNIQUE_FEATURE_INDICES)])
        zb = base.zscore_columns(fb[:, list(base.UNIQUE_FEATURE_INDICES)])
        np.testing.assert_array_equal(fa, fb)
        np.testing.assert_array_equal(za, zb)
        triples = np.asarray([(0, 1, 2), (2, 11, 24), (5, 6, 7)], dtype=np.int16)
        aa, ia = triple.triple_score_matrices(za, triples)
        ab, ib = triple.triple_score_matrices(zb, triples)
        np.testing.assert_array_equal(aa, ab)
        np.testing.assert_array_equal(ia, ib)
        np.testing.assert_array_equal(triple.rank_score_matrix(ia), triple.rank_score_matrix(ib))

    def test_block_inference_is_deterministic_and_directional(self):
        positive = np.linspace(0.001, 0.02, 200)
        negative = -positive
        p1 = triple.one_sided_block_signflip_p(positive, 14120261115)
        p2 = triple.one_sided_block_signflip_p(positive, 14120261115)
        pn = triple.one_sided_block_signflip_p(negative, 14120261115)
        self.assertEqual(p1, p2)
        self.assertLess(p1, 0.05)
        self.assertGreater(pn, 0.5)

    def test_holm_adjustment(self):
        adjusted = triple.holm_adjust([0.01, 0.04, 0.03])
        np.testing.assert_allclose(adjusted, [0.03, 0.06, 0.06], rtol=0, atol=1e-12)

    def test_registered_formula_family_size_and_preregistration(self):
        prereg_path = ROOT / "reports" / "sequence_agent" / "q141_triple_interaction_preregistration_2026-11-12.json"
        prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
        self.assertEqual(prereg["task_id"], "Q141-B5")
        self.assertEqual(prereg["status"], "PREREGISTERED_EXECUTION_PENDING")
        self.assertEqual(prereg["formula_universe"]["triple_count"], 2300)
        self.assertEqual(prereg["formula_universe"]["formula_variants"], 4600)
        self.assertEqual(prereg["inference"]["registered_test_family_size"], 13)
        self.assertEqual(prereg["walkforward"]["target_count"], 3354)


if __name__ == "__main__":
    unittest.main(verbosity=2)
