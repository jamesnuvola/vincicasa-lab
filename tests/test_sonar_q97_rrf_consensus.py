import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q97_rrf_consensus as q97


class Q97RRFTests(unittest.TestCase):
    def test_rank_vector_validation(self):
        q97.validate_rank(list(range(1, 41)))
        with self.assertRaises(ValueError):
            q97.validate_rank([1] * 40)

    def test_rrf_is_deterministic(self):
        vectors = {name: list(range(1, 41)) for name in q97.MODELS}
        self.assertEqual(q97.rrf_order(vectors), list(range(1, 41)))
        self.assertEqual(q97.rrf_order(vectors), q97.rrf_order(vectors))

    def test_rrf_requires_exact_registered_family(self):
        with self.assertRaises(ValueError):
            q97.rrf_order({"BASE_EQUAL42": list(range(1, 41))})

    def test_holm_adjustment(self):
        got = q97.holm([0.01, 0.04, 0.03])
        self.assertAlmostEqual(got[0], 0.03)
        self.assertAlmostEqual(got[1], 0.06)
        self.assertAlmostEqual(got[2], 0.06)

    def test_exact_null_probability_is_bounded(self):
        p = q97.exact_null_p(3, 1, 20)
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)

    def test_block_signflip_reproducible(self):
        import numpy as np
        d = np.array([1, 0, -1, 1, 0, 1, -1, 0, 1], dtype=float)
        self.assertEqual(q97.block_p(d, 123, 1000), q97.block_p(d, 123, 1000))


if __name__ == "__main__":
    unittest.main()
