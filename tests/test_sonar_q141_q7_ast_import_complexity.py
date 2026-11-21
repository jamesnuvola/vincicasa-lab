#!/usr/bin/env python3
import importlib.util
import math
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sonar_q141_q7_ast_import_complexity",
    ROOT / "scripts" / "sonar_q141_q7_ast_import_complexity.py",
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class Q141Q7AstComplexityTests(unittest.TestCase):
    def setUp(self):
        self.families = [
            {"name": f"f{i}", "definition": f"definition {i}"}
            for i in range(10)
        ]
        self.manifest = {"smoothing": {"method": "additive", "alpha": 0.5}}

    def test_mask_maps_to_quintet_score_ast(self):
        ast = MOD.formula_ast(5, self.families, self.manifest)
        self.assertEqual(ast["output_type"], "quintet_score")
        self.assertEqual(ast["candidate_universe"]["size"], 658008)
        self.assertEqual([x["feature_ref"]["feature_id"] for x in ast["terms"]], ["f0", "f2"])
        self.assertEqual(ast["aggregation"]["op"], "sum")
        self.assertEqual(ast["aggregation"]["weight_per_term"], 1)

    def test_ast_id_is_deterministic_and_distinguishes_masks(self):
        a = MOD.formula_ast(5, self.families, self.manifest)
        b = MOD.formula_ast(5, self.families, self.manifest)
        c = MOD.formula_ast(6, self.families, self.manifest)
        self.assertEqual(MOD.canonical_ast_id(a), MOD.canonical_ast_id(b))
        self.assertNotEqual(MOD.canonical_ast_id(a), MOD.canonical_ast_id(c))

    def test_average_ranks_preserve_ties(self):
        ranks = MOD.average_ranks([1, 1, 3, 2])
        np.testing.assert_allclose(ranks, [1.5, 1.5, 4.0, 3.0])

    def test_spearman_perfect_positive_and_negative(self):
        x = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(MOD.spearman_from_values(x, [2, 4, 6, 8, 10]), 1.0)
        self.assertAlmostEqual(MOD.spearman_from_values(x, [10, 8, 6, 4, 2]), -1.0)

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        adjusted = MOD.holm_adjust([0.01, 0.04, 0.03, 0.5])
        self.assertEqual(adjusted, [0.04, 0.09, 0.09, 0.5])
        self.assertTrue(all(0 <= x <= 1 for x in adjusted))

    def test_exact_block_signflip_small_sample(self):
        p, blocks, method = MOD.block_signflip_p([1, 1, 1, 1], block_length=1)
        self.assertEqual(blocks, 4)
        self.assertEqual(method, "exact_16_block_sign_flips")
        self.assertAlmostEqual(p, 1 / 16)

    def test_chronological_split_sizes(self):
        self.assertEqual(MOD.split_sizes(3286), (1972, 657, 657))

    def test_quintet_validation(self):
        MOD.validate_quintet((1, 8, 15, 22, 40))
        with self.assertRaises(ValueError):
            MOD.validate_quintet((1, 8, 8, 22, 40))
        with self.assertRaises(ValueError):
            MOD.validate_quintet((0, 8, 15, 22, 40))

    def test_runner_scores_before_state_update(self):
        source = """
        for i in range(start_index, end_index):
            ranks = ranks_for_actual(standardized, actual_index)
            writer.writerow(row)
            add_draw(state, draw)
        """
        offsets = MOD.assert_runner_strict_prior_order(source)
        self.assertLess(offsets["score_offset"], offsets["write_offset"])
        self.assertLess(offsets["write_offset"], offsets["state_update_offset"])

    def test_runner_order_rejects_update_before_score(self):
        source = """
        for i in range(start_index, end_index):
            add_draw(state, draw)
            ranks = ranks_for_actual(standardized, actual_index)
            writer.writerow(row)
        """
        with self.assertRaises(RuntimeError):
            MOD.assert_runner_strict_prior_order(source)

    def test_target_metric_groups_match_declared_formula_counts(self):
        complexity = np.asarray([int(x).bit_count() for x in range(1, 1024)], dtype=np.int32)
        ranks = np.arange(1, 1024, dtype=np.int32) * 640
        metrics = MOD.target_metrics(ranks, complexity, None)
        self.assertEqual(int(np.count_nonzero(complexity <= 2)), 55)
        self.assertEqual(int(np.count_nonzero(complexity >= 6)), 386)
        self.assertTrue(math.isfinite(metrics["spearman_rho"]))
        self.assertTrue(math.isfinite(metrics["high_low_percentile_delta"]))

    def test_bootstrap_is_deterministic_and_finite(self):
        values = np.linspace(-0.01, 0.02, 75)
        a = MOD.moving_block_ci(values, block_length=10, replicates=200, seed=123)
        b = MOD.moving_block_ci(values, block_length=10, replicates=200, seed=123)
        self.assertEqual(a, b)
        self.assertLessEqual(a[0], a[1])

if __name__ == "__main__":
    unittest.main(verbosity=2)
