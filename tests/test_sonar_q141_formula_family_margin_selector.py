#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_family_margin_selector as c2


def synthetic_draws(count=140):
    return [tuple(((i * 7 + j * 9) % 40) for j in range(5)) for i in range(count)]


class Q141MarginSelectorTests(unittest.TestCase):
    def test_standardized_margin_is_scale_and_shift_invariant(self):
        scores = np.arange(40, 0, -1, dtype=float)
        original = c2.standardized_top5_margin(scores)
        transformed = 7.5 * scores + 123.0
        self.assertAlmostEqual(original, c2.standardized_top5_margin(transformed), places=12)

    def test_margin_zero_for_constant_scores(self):
        self.assertEqual(c2.standardized_top5_margin(np.ones(40)), 0.0)

    def test_margin_rejects_bad_score_shape_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            c2.standardized_top5_margin(np.ones(39))
        bad = np.ones(40)
        bad[3] = np.nan
        with self.assertRaises(ValueError):
            c2.standardized_top5_margin(bad)

    def test_exact_margin_ties_choose_ascending_family_id(self):
        family_scores = {name: np.zeros(40) for name in base.FAMILY_NAMES}
        selected, margins = c2.choose_margin_family(family_scores)
        self.assertEqual(selected, min(base.FAMILY_NAMES))
        self.assertTrue(all(value == 0.0 for value in margins.values()))

    def test_rankdata_uses_average_ranks_for_ties(self):
        ranks = c2.rankdata_average([3, 1, 1, 4, 3])
        np.testing.assert_allclose(ranks, [3.5, 1.5, 1.5, 5.0, 3.5])

    def test_spearman_perfect_monotone_relationship(self):
        rho, p = c2.spearman_rho(np.arange(60), np.arange(60), 14120261113)
        self.assertAlmostEqual(rho, 1.0, places=12)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_future_suffix_and_target_outcome_do_not_change_selection(self):
        draws = synthetic_draws()
        target = 90
        state = base.build_state(draws[:target])
        features = base.feature_matrix(target, draws, *state)
        scores = base.zscore_columns(features)
        families = {name: scores[:, idx].mean(axis=1) for name, idx in base.FAMILIES.items()}
        original = c2.choose_margin_family(families)

        altered = list(draws)
        altered[target] = tuple((x + 13) % 40 for x in altered[target])
        for i in range(target + 1, len(altered)):
            altered[i] = tuple((x + 17) % 40 for x in altered[i])
        changed_features = base.feature_matrix(target, altered, *state)
        changed_scores = base.zscore_columns(changed_features)
        changed_families = {name: changed_scores[:, idx].mean(axis=1) for name, idx in base.FAMILIES.items()}
        changed = c2.choose_margin_family(changed_families)
        self.assertEqual(original[0], changed[0])
        self.assertEqual(original[1], changed[1])

    def test_all_six_family_margins_are_finite_and_rankable(self):
        draws = synthetic_draws()
        target = 80
        state = base.build_state(draws[:target])
        features = base.feature_matrix(target, draws, *state)
        standardized = base.zscore_columns(features)
        family_scores = {name: standardized[:, idx].mean(axis=1) for name, idx in base.FAMILIES.items()}
        selected, margins = c2.choose_margin_family(family_scores)
        self.assertIn(selected, base.FAMILY_NAMES)
        self.assertEqual(set(margins), set(base.FAMILY_NAMES))
        self.assertTrue(all(np.isfinite(x) and x >= 0.0 for x in margins.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
