import itertools
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q141_a7_fresh59_behaviour as a7
import sonar_q141_a9_distributional_subset_score as a9


class A9DistributionalSubsetScoreTests(unittest.TestCase):
    def test_log_esym_matches_brute_force(self):
        x = np.asarray([0.2, -0.1, 0.7, 0.0, -0.4, 0.3, 0.8, -0.2])
        k = 3
        brute = sum(np.exp(sum(x[i] for i in subset)) for subset in itertools.combinations(range(len(x)), k))
        self.assertAlmostEqual(a9.log_esym(x, k), np.log(brute), places=12)

    def test_marginals_sum_to_subset_size(self):
        x = np.asarray([0.2, -0.1, 0.7, 0.0, -0.4, 0.3, 0.8, -0.2])
        log_z, p = a9.log_esym_and_marginals(x, 3)
        self.assertTrue(np.isfinite(log_z))
        self.assertAlmostEqual(float(p.sum()), 3.0, places=12)
        self.assertTrue(np.all((p >= 0) & (p <= 1)))

    def test_probability_mass_is_one(self):
        x = np.asarray([0.2, -0.1, 0.7, 0.0, -0.4, 0.3, 0.8, -0.2])
        log_z = a9.log_esym(x, 3)
        mass = sum(np.exp(sum(x[i] for i in subset) - log_z) for subset in itertools.combinations(range(len(x)), 3))
        self.assertAlmostEqual(float(mass), 1.0, places=12)

    def test_uniform_joint_nll(self):
        scores = np.zeros(40)
        actual = (1, 7, 12, 22, 40)
        self.assertAlmostEqual(a9.subset_nll(scores, actual, 1.0), np.log(658008), places=12)

    def test_uniform_marginals(self):
        p = a9.subset_marginals(np.zeros(40), 2.0)
        np.testing.assert_allclose(p, np.full(40, 0.125), atol=1e-13)
        self.assertAlmostEqual(float(p.sum()), 5.0, places=12)

    def test_temperature_fit_is_deterministic(self):
        scores = np.asarray([
            np.linspace(-0.5, 0.5, 40),
            np.linspace(0.5, -0.5, 40),
            np.sin(np.arange(40)),
        ])
        actual = [(1, 2, 3, 4, 5), (36, 37, 38, 39, 40), (1, 7, 14, 22, 31)]
        a = a9.choose_temperature(scores, actual, [0, 1, 2])
        b = a9.choose_temperature(scores, actual, [0, 1, 2])
        self.assertEqual(a, b)

    def test_future_suffix_mutation_does_not_change_prior_features(self):
        rng = np.random.default_rng(14111319)
        draws = [tuple(sorted(rng.choice(np.arange(1, 41), size=5, replace=False).tolist())) for _ in range(80)]
        mutated = list(draws)
        for i in range(65, 80):
            mutated[i] = tuple(sorted(rng.choice(np.arange(1, 41), size=5, replace=False).tolist()))
        original_matrix = a7.compute_feature_matrix(draws)
        mutated_matrix = a7.compute_feature_matrix(mutated)
        np.testing.assert_array_equal(original_matrix[:16], mutated_matrix[:16])

    def test_holm_is_bounded_and_monotone(self):
        adjusted = a9.holm_adjust([0.01, 0.04, 0.03, 0.2])
        self.assertTrue(all(0 <= x <= 1 for x in adjusted))
        self.assertGreaterEqual(adjusted[0], 0.01)
        self.assertGreaterEqual(adjusted[1], 0.04)


if __name__ == "__main__":
    unittest.main()
