import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np

import sonar_q141_a20_drift_quantile_state as a20
from sonar_q141_a21_q7_source_extension import (
    forecast_next_ols,
    forecast_next_state,
    lower_quantile,
    read_extension,
)
import sonar_q141_a17_full_universe_spectral as a17


class Q141A21Tests(unittest.TestCase):
    def test_lower_quantile_uses_registered_lower_order_statistic(self):
        values = np.arange(400, dtype=float)
        self.assertEqual(lower_quantile(values, 0.75), float(values[299]))

    def test_next_state_forecast_uses_only_prior_pairs(self):
        drift = np.linspace(0.0, 1.0, 400)
        capture = np.linspace(0.2, 0.8, 400)
        result = forecast_next_state(drift, capture, 0.99)
        self.assertEqual(result["state"], "high")
        self.assertGreaterEqual(result["selected_count"], 25)
        self.assertTrue(0.0 <= result["prediction"] <= 1.0)

    def test_next_ols_forecast_is_finite_and_bounded(self):
        drift = np.linspace(0.0, 1.0, 400)
        capture = np.clip(0.4 + 0.1 * drift, 0.0, 1.0)
        result = forecast_next_ols(drift, capture, 0.95)
        self.assertTrue(np.isfinite(result["prediction"]))
        self.assertTrue(0.0 <= result["prediction"] <= 1.0)
        self.assertEqual(result["prior_mean400"], float(capture.mean()))

    def test_current_target_response_placeholder_does_not_change_forecast(self):
        drift = np.linspace(0.0, 1.0, 401)
        capture = np.linspace(0.1, 0.9, 401)
        capture[400] = 0.0
        q75_a = a20.forecast_at(drift, capture, 400)
        ols_a = a19_prediction(drift, capture, 400)
        capture[400] = 1.0
        q75_b = a20.forecast_at(drift, capture, 400)
        ols_b = a19_prediction(drift, capture, 400)
        self.assertEqual(q75_a["prediction"], q75_b["prediction"])
        self.assertEqual(ols_a, ols_b)

    def test_extension_reader_accepts_exact_prior_aligned_rows(self):
        current_dates = [f"d{i:04d}" for i in range(3407)]
        current_draws = [(1, 2, 3, 4, 5)] * 3407
        header = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + [
            f"rank_mask_{i:04d}" for i in range(1, a17.FORMULAS + 1)
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "extension.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(header)
                for j in range(20):
                    idx = 3387 + j
                    writer.writerow([
                        current_dates[idx], current_dates[idx - 1], idx,
                        "1 2 3 4 5", "SCORED"
                    ] + [1] * a17.FORMULAS)
            matrix, meta, rows = read_extension(path, current_dates, current_draws)
        self.assertEqual(matrix.shape, (20, a17.FORMULAS))
        self.assertEqual(meta[0]["target_index"], 3387)
        self.assertEqual(meta[-1]["target_index"], 3406)
        self.assertTrue(all(r["cutoff_date"] < r["target_date"] for r in meta))

    def test_extension_reader_rejects_non_strict_cutoff(self):
        current_dates = [f"d{i:04d}" for i in range(3407)]
        current_draws = [(1, 2, 3, 4, 5)] * 3407
        header = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + [
            f"rank_mask_{i:04d}" for i in range(1, a17.FORMULAS + 1)
        ]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "extension.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(header)
                for j in range(20):
                    idx = 3387 + j
                    cutoff = current_dates[idx] if j == 0 else current_dates[idx - 1]
                    writer.writerow([
                        current_dates[idx], cutoff, idx,
                        "1 2 3 4 5", "SCORED"
                    ] + [1] * a17.FORMULAS)
            with self.assertRaisesRegex(ValueError, "cutoff mismatch|non-strict cutoff"):
                read_extension(path, current_dates, current_draws)


def a19_prediction(drift, capture, t):
    x = np.asarray(drift[t-400:t], dtype=float)
    y = np.asarray(capture[t-400:t], dtype=float)
    xm, ym = float(x.mean()), float(y.mean())
    xc = x - xm
    den = float(np.dot(xc, xc))
    slope = 0.0 if den <= 1e-14 else float(np.dot(xc, y-ym) / den)
    return float(np.clip(ym + slope * (drift[t]-xm), 0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
