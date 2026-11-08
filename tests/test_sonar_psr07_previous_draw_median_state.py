#!/usr/bin/env python3
"""Unit and synthetic walk-forward tests for SONAR PSR-07."""
from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sonar_psr07_previous_draw_median_state_walkforward import (  # noqa: E402
    ALPHA_GRID,
    exact_p3_quartile_states,
    holm_adjust,
    order_statistic_prior,
    parse_archive_text,
    p3_state,
    posterior_probability,
    run_walkforward,
    score_probability,
    circular_block_means,
    canonicalize,
    rounded,
)


class PSR07UnitTests(unittest.TestCase):
    def test_exact_order_statistic_priors_normalize(self) -> None:
        for position in range(1, 6):
            domain, prior = order_statistic_prior(position)
            self.assertEqual(len(domain), 36)
            self.assertEqual(int(domain[0]), position)
            self.assertEqual(int(domain[-1]), 35 + position)
            self.assertAlmostEqual(float(prior.sum()), 1.0, places=12)
            self.assertTrue(np.all(prior >= 0.0))

    def test_exact_p3_quartile_cutpoints_and_masses(self) -> None:
        cuts, masses = exact_p3_quartile_states()
        self.assertEqual(cuts, (15, 20, 26))
        self.assertAlmostEqual(sum(masses), 1.0, places=12)
        self.assertEqual(p3_state(15, cuts), 0)
        self.assertEqual(p3_state(16, cuts), 1)
        self.assertEqual(p3_state(20, cuts), 1)
        self.assertEqual(p3_state(21, cuts), 2)
        self.assertEqual(p3_state(26, cuts), 2)
        self.assertEqual(p3_state(27, cuts), 3)

    def test_posterior_probability_normalization(self) -> None:
        _, prior = order_statistic_prior(3)
        counts = np.zeros(36, dtype=np.int64)
        counts[10] = 17
        probability = posterior_probability(counts, prior, 300)
        self.assertAlmostEqual(float(probability.sum()), 1.0, places=10)
        self.assertTrue(np.all(probability >= 0.0))

    def test_scoring_and_tie_break(self) -> None:
        probability = np.full(36, 1.0 / 36.0)
        score = score_probability(probability, actual_index=0)
        self.assertEqual(score["rank"], 1)
        self.assertEqual(score["pick"], 0)
        self.assertEqual(score["top1"], 1)
        self.assertEqual(score["top5"], 1)
        self.assertAlmostEqual(float(score["brier"]), 1.0 - 1.0 / 36.0, places=12)

    def test_holm_monotonic_adjustment(self) -> None:
        adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.03})
        self.assertAlmostEqual(adjusted["a"], 0.03, places=12)
        self.assertAlmostEqual(adjusted["c"], 0.06, places=12)
        self.assertAlmostEqual(adjusted["b"], 0.06, places=12)


    def test_canonical_numeric_serialization_suppresses_ulp_noise(self) -> None:
        left = 0.0011042943238679965
        right = 0.0011042943238679958
        self.assertEqual(canonicalize(left), canonicalize(right))
        self.assertNotEqual(canonicalize(4.440892098500626e-16), 0.0)
        self.assertEqual(rounded(0.002310031019999999), rounded(0.002310031019000001))

    def test_block_sampler_is_deterministic(self) -> None:
        values = np.asarray([0.1, -0.2, 0.4, 0.0, 0.3, -0.1, 0.2, 0.05])
        first = circular_block_means(values, replicates=100, block_length=3, seed=42)
        second = circular_block_means(values, replicates=100, block_length=3, seed=42)
        np.testing.assert_array_equal(first, second)

    def test_archive_parser_rejects_duplicate_or_unsorted_draw(self) -> None:
        valid = (
            "data,n1,n2,n3,n4,n5\n"
            "2026-01-01,1,2,3,4,5\n"
            "2026-01-02,2,4,6,8,10\n"
        )
        dates, draws = parse_archive_text(valid)
        self.assertEqual(len(dates), 2)
        self.assertEqual(draws.shape, (2, 5))
        invalid = "data,n1,n2,n3,n4,n5\n2026-01-01,1,2,2,4,5\n"
        with self.assertRaises(ValueError):
            parse_archive_text(invalid)

    def test_synthetic_strict_prefix_walkforward(self) -> None:
        rng = np.random.default_rng(20261108)
        row_count = 50
        dates = [
            (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat()
            for i in range(row_count)
        ]
        draws = np.asarray(
            [sorted((rng.choice(np.arange(1, 41), size=5, replace=False)).tolist()) for _ in range(row_count)],
            dtype=np.int16,
        )
        report, ledger = run_walkforward(
            dates,
            draws,
            warmup=10,
            alpha_grid=ALPHA_GRID,
            bootstrap_replicates=100,
            block_length=7,
            seed_base=12345,
            archive_sha="synthetic-test-archive",
        )
        self.assertEqual(report["protocol"]["scored_targets"], 40)
        self.assertEqual(report["integrity"]["strict_prefix_train_n_t_minus_2_checks"], 40)
        self.assertEqual(report["integrity"]["target_cutoff_before_target_date_checks"], 40)
        self.assertEqual(report["integrity"]["actual_grid_rows"], 40 * 5 * 3)
        self.assertEqual(report["integrity"]["actual_selected_ledger_rows"], 40 * 5)
        self.assertEqual(report["integrity"]["duplicate_grid_keys"], 0)
        self.assertEqual(report["integrity"]["duplicate_selected_target_position_keys"], 0)
        self.assertLessEqual(report["integrity"]["max_probability_normalization_error"], 1e-10)
        first_p1 = next(row for row in ledger if row["target_index"] == 10 and row["position"] == 1)
        self.assertEqual(first_p1["global_training_n"], 8)
        self.assertEqual(first_p1["cutoff_date"], dates[9])
        self.assertLess(first_p1["cutoff_date"], first_p1["date"])
        self.assertEqual(first_p1["last_training_target_date"], dates[9])
        self.assertEqual(len(report["blind_oos_primary_inference"]), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
