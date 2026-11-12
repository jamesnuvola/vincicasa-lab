import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.sonar_fd10_p5_continuous_kernel import (
    ALPHA,
    BANDWIDTHS,
    block_signflip_family,
    build_walkforward,
    circular_block_bootstrap_mean_ci,
    exact_null_pmf,
    holm_adjust,
    kernel_probabilities,
    rank_candidates,
)


def synthetic_rows(maxima):
    rows = []
    for i, maximum in enumerate(maxima):
        rows.append({
            "date": f"2020-01-{i + 1:02d}",
            "numbers": [1, 2, 3, 4, maximum],
        })
    return rows


class FD10ContinuousKernelTests(unittest.TestCase):
    def test_exact_order_statistic_distribution_and_top5(self):
        pmf = exact_null_pmf()
        self.assertAlmostEqual(sum(pmf), 1.0, places=14)
        self.assertAlmostEqual(sum(pmf[-5:]), 0.5066442961179803, places=14)
        self.assertAlmostEqual(sum(pmf[-10:]), 0.7834281650071124, places=14)
        self.assertAlmostEqual(sum(pmf[-20:]), 0.9764379764379765, places=14)

    def test_empty_transition_state_reverts_exactly_to_null(self):
        counts = [[0] * 36 for _ in range(36)]
        for bandwidth in BANDWIDTHS:
            result = kernel_probabilities(counts, 28, bandwidth, ALPHA)
            for observed, expected in zip(result, exact_null_pmf()):
                self.assertAlmostEqual(observed, expected, places=15)

    def test_kernel_probabilities_are_normalized(self):
        counts = [[0] * 36 for _ in range(36)]
        counts[25 - 5][37 - 5] = 12
        counts[26 - 5][39 - 5] = 7
        for bandwidth in BANDWIDTHS:
            result = kernel_probabilities(counts, 26, bandwidth, ALPHA)
            self.assertTrue(all(0 < p < 1 for p in result))
            self.assertAlmostEqual(sum(result), 1.0, places=14)

    def test_tied_candidate_probabilities_use_descending_number(self):
        self.assertEqual(rank_candidates([1.0] * 36)[:5], [40, 39, 38, 37, 36])

    def test_walkforward_scores_target_before_adding_its_transition(self):
        maxima = [20, 25, 30, 35, 22, 40, 18, 33]
        original = build_walkforward(synthetic_rows(maxima), warmup=3)
        changed = maxima[:]
        changed[3] = 10
        altered = build_walkforward(synthetic_rows(changed), warmup=3)
        self.assertEqual(original[0]["target_index"], 3)
        self.assertEqual(original[0]["history_cutoff"], "2020-01-03")
        self.assertEqual(original[0]["models"][1.5]["top5"], altered[0]["models"][1.5]["top5"])
        self.assertEqual(original[0]["models"][12.0]["top5"], altered[0]["models"][12.0]["top5"])

    def test_future_outcomes_do_not_change_earlier_forecast(self):
        maxima = [15, 21, 27, 33, 19, 38, 24, 31, 17]
        baseline = build_walkforward(synthetic_rows(maxima), warmup=3)
        changed = maxima[:]
        changed[5:] = [8, 9, 11, 13]
        altered = build_walkforward(synthetic_rows(changed), warmup=3)
        self.assertEqual(baseline[1]["models"][3.0]["top5"], altered[1]["models"][3.0]["top5"])

    def test_holm_adjustment(self):
        self.assertEqual(holm_adjust([0.01, 0.04, 0.20, 0.90]), [0.04, 0.12, 0.40, 0.90])

    def test_block_signflip_is_deterministic_and_directional(self):
        endpoints = {
            "positive": [1.0] * 28,
            "negative": [-1.0] * 28,
        }
        first = block_signflip_family(endpoints, block_length=7, replicates=999, seed=10)
        second = block_signflip_family(endpoints, block_length=7, replicates=999, seed=10)
        self.assertEqual(first, second)
        self.assertLess(first["positive"], first["negative"])

    def test_circular_bootstrap_is_deterministic(self):
        values = [float((i % 9) - 4) for i in range(83)]
        first = circular_block_bootstrap_mean_ci(values, block_length=7, replicates=999, seed=101)
        second = circular_block_bootstrap_mean_ci(values, block_length=7, replicates=999, seed=101)
        self.assertEqual(first, second)
        self.assertLessEqual(first[0], first[1])

    def test_split_counts_and_cutoff_are_recorded(self):
        maxima = [20, 25, 30, 35, 22, 40, 18, 33]
        records = build_walkforward(synthetic_rows(maxima), warmup=3)
        self.assertEqual(len(records), 5)
        self.assertTrue(all(r["history_cutoff"] < r["target_date"] for r in records))
        self.assertTrue(all(r["split"] == "discovery" for r in records))


if __name__ == "__main__":
    unittest.main()
