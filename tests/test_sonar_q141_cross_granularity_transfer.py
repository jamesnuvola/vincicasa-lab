#!/usr/bin/env python3
"""Q141-C4 synthetic leakage, deterministic-fit and block-inference tests."""
from __future__ import annotations

import copy
import datetime as dt
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_cross_granularity_transfer as c4


def synthetic_ledgers(n=60):
    start = dt.date(2020, 4, 10)
    q7 = []
    for i in range(n):
        target_date = start + dt.timedelta(days=i + 1)
        q7.append({
            "prior_draws": str(100 + i),
            "target_date": target_date.isoformat(),
            "cutoff_date": (target_date - dt.timedelta(days=1)).isoformat(),
            "actual_quintet": "1 2 3 4 5",
            "split": "discovery",
            "mean_percentile_all": str(0.35 + 0.002 * i),
        })
    c0 = []
    for index in range(160):
        row = {
            "target_index": str(index),
            "target_date": (start + dt.timedelta(days=index - 50)).isoformat(),
            "cutoff_date": (start + dt.timedelta(days=index - 51)).isoformat(),
            "actual_quintet": "1 2 3 4 5",
            "equal_family_top5_hits": str((index % 5) + 0.1),
        }
        for j, column in enumerate(c4.FAMILY_COLUMNS):
            row[column] = str(((index + j) % 5) + 0.1)
        c0.append(row)
    return q7, c0


class CrossGranularityTransferTests(unittest.TestCase):
    def test_prior_features_are_deterministic_and_have_expected_shape(self):
        q7, c0 = synthetic_ledgers()
        matrix_a, rows_a = c4.build_features(q7, c0)
        matrix_b, rows_b = c4.build_features(q7, c0)
        self.assertTrue(np.array_equal(matrix_a, matrix_b, equal_nan=True))
        self.assertEqual(rows_a, rows_b)
        self.assertEqual(matrix_a.shape, (60, 5))
        self.assertTrue(np.isnan(matrix_a[:50]).all())
        self.assertTrue(np.isfinite(matrix_a[50:]).all())

    def test_current_and_future_outcomes_do_not_change_current_features(self):
        q7, c0 = synthetic_ledgers()
        target_offset = 55
        original_matrix, _ = c4.build_features(q7, c0)
        mutated_q7 = copy.deepcopy(q7)
        mutated_c0 = copy.deepcopy(c0)
        mutated_q7[target_offset]["mean_percentile_all"] = "0.999999"
        for i in range(target_offset + 1, len(mutated_q7)):
            mutated_q7[i]["mean_percentile_all"] = "0.000001"
        target_index = int(q7[target_offset]["prior_draws"])
        for row in mutated_c0:
            if int(row["target_index"]) >= target_index:
                row["equal_family_top5_hits"] = "5"
                for column in c4.FAMILY_COLUMNS:
                    row[column] = "5"
        mutated_matrix, _ = c4.build_features(mutated_q7, mutated_c0)
        self.assertTrue(np.array_equal(original_matrix[target_offset], mutated_matrix[target_offset]))

    def test_feature_window_ends_at_exact_prior_target_index(self):
        q7, c0 = synthetic_ledgers()
        matrix, rows = c4.build_features(q7, c0)
        target_offset = 55
        target_index = int(q7[target_offset]["prior_draws"])
        self.assertEqual(rows[target_offset]["q80_last_prior_target_index"], target_index - 1)
        self.assertEqual(c4.WINDOW, 50)
        self.assertTrue(np.isfinite(matrix[target_offset]).all())

    def test_ridge_fit_and_predictions_are_deterministic(self):
        rng = np.random.default_rng(14120261124)
        x = rng.normal(size=(200, 5))
        y = 0.48 + 0.02 * x[:, 0] - 0.01 * x[:, 2] + rng.normal(0, 0.01, size=200)
        model_a = c4.fit_ridge(x, y)
        model_b = c4.fit_ridge(x, y)
        pred_a = c4.predict_ridge(model_a, x[:20])
        pred_b = c4.predict_ridge(model_b, x[:20])
        self.assertTrue(np.array_equal(pred_a, pred_b))
        self.assertTrue(np.isfinite(pred_a).all())
        self.assertTrue(np.all((pred_a >= 0) & (pred_a <= 1)))

    def test_block_inference_is_reproducible_and_bounded(self):
        values = np.sin(np.arange(657) / 17.0) * 0.01 + 0.002
        p1 = c4.block_signflip_p(values, 20, 2000, 14120261124)
        p2 = c4.block_signflip_p(values, 20, 2000, 14120261124)
        ci1 = c4.moving_block_bootstrap_ci(values, 20, 2000, 14120261125)
        ci2 = c4.moving_block_bootstrap_ci(values, 20, 2000, 14120261125)
        self.assertEqual(p1, p2)
        self.assertEqual(ci1, ci2)
        self.assertGreaterEqual(p1, 0.0)
        self.assertLessEqual(p1, 1.0)
        self.assertLessEqual(ci1[0], ci1[1])

    def test_preregistered_split_boundaries_and_feature_sets_are_fixed(self):
        self.assertEqual(c4.DISCOVERY_END, 1972)
        self.assertEqual(c4.VALIDATION_END, 2629)
        self.assertEqual(c4.FEATURE_A, ("q7_roll50_mean_percentile",))
        self.assertEqual(len(c4.FEATURE_B), 5)
        self.assertEqual(c4.RIDGE_ALPHA, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
