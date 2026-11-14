#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as q141


def synthetic_draws(count=100):
    rows = []
    for i in range(count):
        values = tuple(sorted({((i * 7 + j * 9) % 40) for j in range(5)}))
        if len(values) != 5:
            raise AssertionError("synthetic draw generator collision")
        rows.append(tuple(v for v in values))
    return rows


class Q141FamilyAnticipationTests(unittest.TestCase):
    def test_family_partition_and_aliases(self):
        flattened = sorted(i for indices in q141.FAMILIES.values() for i in indices)
        self.assertEqual(flattened, list(q141.UNIQUE_FEATURE_INDICES))
        self.assertEqual(len(q141.FEATURE_NAMES), 27)
        self.assertEqual(len(q141.UNIQUE_FEATURE_INDICES), 25)
        self.assertEqual(q141.ALIASES, {"recent_5": "freq_5", "recent_10": "freq_10"})

    def test_future_suffix_invariance(self):
        draws = synthetic_draws(100)
        target = 70
        state = q141.build_state(draws[:target])
        original = q141.feature_matrix(target, draws, *state)
        altered = list(draws)
        for i in range(target, len(altered)):
            altered[i] = tuple(sorted(((i + 11 + j * 7) % 40) for j in range(5)))
        changed = q141.feature_matrix(target, altered, *state)
        np.testing.assert_array_equal(original, changed)

    def test_duplicate_alias_columns_are_exact(self):
        draws = synthetic_draws(90)
        target = 70
        state = q141.build_state(draws[:target])
        features = q141.feature_matrix(target, draws, *state)
        np.testing.assert_array_equal(features[:, 0], features[:, 25])
        np.testing.assert_array_equal(features[:, 1], features[:, 26])

    def test_rank_ties_are_resolved_by_ascending_number(self):
        ranks = q141.rank_scores(np.zeros(40))
        np.testing.assert_array_equal(ranks, np.arange(1, 41, dtype=np.int16))
        scores = np.zeros(40)
        scores[9] = 1.0
        ranks = q141.rank_scores(scores)
        self.assertEqual(int(ranks[9]), 1)
        self.assertEqual(int(ranks[0]), 2)

    def test_family_metric_aggregation_uses_selected_family(self):
        rows = [{"families": {"frequency_level": {"top5_hits": 2, "top10_hits": 3, "top20_hits": 4, "mean_rank": 17.0}}}]
        summary = q141.summarize_metrics(rows, "families", "frequency_level")
        self.assertEqual(summary["targets"], 1)
        self.assertAlmostEqual(summary["mean_number_hits_top5"], 0.4)
        self.assertAlmostEqual(summary["mean_actual_number_rank"], 17.0)

    def test_split_counts(self):
        counts = {}
        n = 3354
        for i in range(n):
            split = q141.split_name(i, n)
            counts[split] = counts.get(split, 0) + 1
        self.assertEqual(counts, {"discovery": 2013, "validation": 671, "blind_oos": 670})

    def test_exact_uniform_tail_is_bounded_and_monotone(self):
        p_low = q141.exact_hypergeom_upper_tail(80, 100, 5)
        p_high = q141.exact_hypergeom_upper_tail(100, 100, 5)
        self.assertGreaterEqual(p_low, p_high)
        self.assertGreaterEqual(p_high, 0.0)
        self.assertLessEqual(p_low, 1.0)

    def test_holm_adjustment_is_bounded_and_monotone_in_sorted_order(self):
        raw = [0.03, 0.001, 0.2, 0.04]
        adjusted = q141.holm_adjust(raw)
        self.assertEqual(len(adjusted), len(raw))
        self.assertTrue(all(0.0 <= p <= 1.0 for p in adjusted))
        order = sorted(range(len(raw)), key=lambda i: raw[i])
        sorted_adjusted = [adjusted[i] for i in order]
        self.assertEqual(sorted_adjusted, sorted(sorted_adjusted))


if __name__ == "__main__":
    unittest.main(verbosity=2)
