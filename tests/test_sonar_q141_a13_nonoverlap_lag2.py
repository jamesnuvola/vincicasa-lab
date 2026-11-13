import unittest

import numpy as np

import sonar_q141_a12_structural_markov_audit as A12
import sonar_q141_a13_nonoverlap_lag2 as A13


def sample_draws(n=700, seed=23):
    rng = np.random.default_rng(seed)
    scores = rng.random((n, 40))
    draws = np.argpartition(scores, 5, axis=1)[:, :5] + 1
    return np.sort(draws, axis=1)


class NonOverlapLag2Tests(unittest.TestCase):
    def test_pinned_a12_feature_builder(self):
        self.assertEqual(
            A13.a12_builder_blob_sha1(),
            A13.EXPECTED_A12_BUILDER_BLOB_SHA1,
        )

    def test_phase_training_blocks_are_disjoint_from_target(self):
        for target in (400, 401, 402, 403, 520, 699):
            samples = A13.training_indices(target)
            self.assertGreater(len(samples), 0)
            self.assertTrue(np.all(samples % 4 == target % 4))
            self.assertLessEqual(int(samples[-1]), target - 4)
            self.assertTrue(np.all(np.diff(samples) == 4))
            windows = [(int(s) - 3, int(s)) for s in samples]
            for previous, following in zip(windows, windows[1:]):
                self.assertLess(previous[1], following[0])
            self.assertLess(windows[-1][1], target - 3)
            self.assertTrue(A13.verify_nonoverlap_geometry(target))

    def test_warmup_phase_has_expected_sample_count(self):
        samples = A13.training_indices(400)
        self.assertEqual(len(samples), 99)
        self.assertEqual(int(samples[0]), 4)
        self.assertEqual(int(samples[-1]), 396)

    def test_vectorized_scorer_matches_scalar_reference(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        for feature in A13.FEATURES:
            y = codes[feature]
            vectorized = A13.score_series(y, 5)
            for target in (400, 401, 402, 403, 420, 500, 699):
                pos = target - A13.WARMUP
                scalar = A13.phase_forecast(y, target, 5)
                self.assertAlmostEqual(
                    vectorized["logloss_gain"][pos],
                    scalar["logloss_gain"],
                    places=13,
                )
                self.assertAlmostEqual(
                    vectorized["brier_gain"][pos],
                    scalar["brier_gain"],
                    places=13,
                )
                self.assertEqual(
                    int(vectorized["prior_samples"][pos]),
                    scalar["prior_samples"],
                )
                self.assertEqual(
                    int(vectorized["max_training_sample_index"][pos]),
                    scalar["max_training_sample_index"],
                )

    def test_forecast_probabilities_are_normalized(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        for feature in A13.FEATURES:
            result = A13.phase_forecast(codes[feature], 500, 5)
            self.assertAlmostEqual(float(result["p0"].sum()), 1.0, places=14)
            self.assertAlmostEqual(float(result["p1"].sum()), 1.0, places=14)
            self.assertTrue(np.all(result["p0"] > 0))
            self.assertTrue(np.all(result["p1"] > 0))

    def test_future_suffix_invariance(self):
        draws = sample_draws()
        self.assertTrue(A13.verify_future_suffix_invariance(draws, 500))

    def test_deterministic_full_score_replay(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        for feature in A13.FEATURES:
            first = A13.score_series(codes[feature], 5)
            second = A13.score_series(codes[feature], 5)
            for key in first:
                np.testing.assert_array_equal(first[key], second[key])

    def test_iid_mechanical_null_is_seed_reproducible(self):
        first = A13.iid_mechanical_null(
            n_draws=650, blind_start=200, reps=8, seed=14111313
        )
        second = A13.iid_mechanical_null(
            n_draws=650, blind_start=200, reps=8, seed=14111313
        )
        np.testing.assert_array_equal(
            first["simulated_pooled"], second["simulated_pooled"]
        )
        np.testing.assert_array_equal(
            first["simulated_features"], second["simulated_features"]
        )

    def test_invalid_category_stream_rejected(self):
        draws = sample_draws()
        codes = A12.build_feature_codes(draws)
        y = codes["sum_transition"].copy()
        y[400] = -1
        with self.assertRaises(ValueError):
            A13.score_series(y, 5)


if __name__ == "__main__":
    unittest.main()
