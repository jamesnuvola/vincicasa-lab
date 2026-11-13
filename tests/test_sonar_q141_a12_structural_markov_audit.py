import importlib.util
import pathlib
import unittest
from datetime import date, timedelta

import numpy as np

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "sonar_q141_a12_structural_markov_audit.py"
SPEC = importlib.util.spec_from_file_location("sonar_a12", SCRIPT)
A12 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A12)


def sample_draws(n=650, seed=22):
    rng = np.random.default_rng(seed)
    scores = rng.random((n, 40))
    draws = np.argpartition(scores, 5, axis=1)[:, :5] + 1
    return np.sort(draws, axis=1)


class StructuralMarkovAuditTests(unittest.TestCase):
    def test_fixed_vocabulary_has_51_categories(self):
        self.assertEqual(sum(len(v) for v in A12.FEATURE_CATEGORIES.values()), 51)
        self.assertEqual(len(A12.FEATURES), 11)
        self.assertEqual(len(A12.CORE_FEATURES), 9)

    def test_feature_codes_valid_after_first_row(self):
        codes = A12.build_feature_codes(sample_draws())
        for feature in A12.FEATURES:
            self.assertEqual(len(codes[feature]), 650)
            self.assertGreaterEqual(int(codes[feature][1:].min()), 0)
            self.assertLess(int(codes[feature][1:].max()), len(A12.FEATURE_CATEGORIES[feature]))

    def test_prior_only_counts_and_finite_score(self):
        codes = A12.build_feature_codes(sample_draws())
        result = A12.score_feature(codes["sum_bin"], 400, 5)
        self.assertEqual(result["prior_category_count"], 399)
        self.assertEqual(result["prior_transition_count"], 398)
        self.assertLessEqual(result["transition_count"], 398)
        self.assertTrue(np.isfinite(result["logloss_gain"]))
        self.assertTrue(np.isfinite(result["brier_gain"]))

    def test_future_suffix_invariance(self):
        draws = sample_draws()
        original = A12.build_feature_codes(draws)
        target = 500
        mutated_draws = draws.copy()
        rng = np.random.default_rng(99)
        for i in range(target + 1, len(draws)):
            mutated_draws[i] = np.sort(rng.choice(np.arange(1, 41), 5, replace=False))
        mutated = A12.build_feature_codes(mutated_draws)
        for feature in A12.FEATURES:
            before = A12.score_feature(original[feature], target, len(A12.FEATURE_CATEGORIES[feature]))
            after = A12.score_feature(mutated[feature], target, len(A12.FEATURE_CATEGORIES[feature]))
            self.assertEqual(before, after)

    def test_vectorized_iid_scorer_matches_sequential_scorer(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        y = codes["sum_transition"]
        fast_ll, fast_brier = A12.fast_transition_gains_invalid(y)
        slow = [
            A12.score_feature(y, t, 5)
            for t in range(A12.WARMUP, len(y))
        ]
        np.testing.assert_allclose(fast_ll, [x["logloss_gain"] for x in slow], atol=1e-12, rtol=0)
        np.testing.assert_allclose(fast_brier, [x["brier_gain"] for x in slow], atol=1e-12, rtol=0)

    def test_ledger_is_deterministic_and_cutoffs_are_prior(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        dates = np.asarray([(date(2020, 1, 1) + timedelta(days=i)).isoformat()
                            for i in range(len(draws))])
        cutoffs = np.asarray(["2019-12-31"] + dates[:-1].tolist())
        first = A12.build_ledger(codes, dates, cutoffs)
        second = A12.build_ledger(codes, dates, cutoffs)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(draws) - A12.WARMUP)
        self.assertTrue(all(r["cutoff_date"] < r["target_date"] for r in first))

    def test_invalid_draws_rejected(self):
        draws = sample_draws()
        draws[10, 1] = draws[10, 0]
        with self.assertRaises(ValueError):
            A12.build_feature_codes(draws)


if __name__ == "__main__":
    unittest.main()
