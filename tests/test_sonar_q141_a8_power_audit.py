import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q141_a8_power_audit as audit

class A8PowerAuditTests(unittest.TestCase):
    def test_exact_combinatorial_mass(self):
        for m in range(1, 6):
            values, probs = audit.difference_distribution(m)
            self.assertAlmostEqual(float(probs.sum()), 1.0, places=14)
            self.assertAlmostEqual(float(np.dot(values, probs)), 0.0, places=14)

    def test_variance_matches_closed_form(self):
        for m in range(1, 6):
            expected = (2 * 5 * m / 40 * (40 - 5) / 39) / 25
            self.assertAlmostEqual(audit.null_variance_hit_share(m), expected, places=14)

    def test_exponential_tilt_hits_target_effect(self):
        for m in range(1, 6):
            values, p0 = audit.difference_distribution(m)
            lam, p = audit.tilted_distribution(values, p0, 0.1)
            self.assertGreater(lam, 0)
            self.assertAlmostEqual(float(np.dot(values, p)), 0.1, places=11)

    def test_null_tilt_is_identity(self):
        values, p0 = audit.difference_distribution(3)
        lam, p = audit.tilted_distribution(values, p0, 0.0)
        self.assertEqual(lam, 0.0)
        np.testing.assert_array_equal(p, p0)

    def test_block_allocation_and_reproducibility(self):
        a = audit.simulate_block_signflip(2, 50, 0.02, replicates=1000, seed=123)
        b = audit.simulate_block_signflip(2, 50, 0.02, replicates=1000, seed=123)
        self.assertEqual(a, b)
        self.assertEqual(a["active_targets_per_block"], [5] * 10)

    def test_rejects_invalid_overlap(self):
        with self.assertRaises(ValueError):
            audit.difference_distribution(0)
        with self.assertRaises(ValueError):
            audit.difference_distribution(6)

if __name__ == "__main__":
    unittest.main()
