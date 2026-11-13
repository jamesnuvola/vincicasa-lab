import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sonar_q141_a7_fresh59_behaviour as a7

class Fresh59Tests(unittest.TestCase):
    @staticmethod
    def draws(n, seed=141):
        rng=np.random.default_rng(seed)
        return [tuple(sorted(rng.choice(np.arange(1,41),5,replace=False).tolist())) for _ in range(n)]

    def test_feature_schema_and_family_partition(self):
        self.assertEqual(len(a7.FEATURE_NAMES),59)
        flat=[i for values in a7.FAMILY_INDICES.values() for i in values]
        self.assertEqual(sorted(flat),list(range(59)))
        self.assertEqual(len(flat),len(set(flat)))

    def test_rank_ties_break_by_number(self):
        np.testing.assert_array_equal(a7.rank_desc(np.zeros(40)),np.arange(1,41))

    def test_stable_family_gets_higher_weight(self):
        base=np.tile(np.arange(1,41,dtype=np.int16),(5,7,1))
        base[:,1,:]=np.tile(np.arange(1,41,dtype=np.int16)[::-1],(5,1))
        base[1::2,1,:]=np.tile(np.arange(1,41,dtype=np.int16),(2,1))
        weights,turnover=a7.weights_from_history(base)
        self.assertAlmostEqual(float(weights.sum()),1.0,places=12)
        self.assertGreater(weights[0],weights[1])
        self.assertLess(turnover[0],turnover[1])

    def test_future_suffix_mutation_does_not_change_target_features(self):
        draws=self.draws(72)
        original=a7.compute_feature_matrix(draws)
        changed=list(draws)
        changed[60:]=self.draws(12,seed=991)
        mutated=a7.compute_feature_matrix(changed)
        # Matrix row 10 is the pre-target feature vector for draw index 60.
        np.testing.assert_array_equal(original[:11],mutated[:11])

    def test_feature_replay_is_deterministic(self):
        draws=self.draws(66,seed=992)
        first=a7.compute_feature_matrix(draws)
        second=a7.compute_feature_matrix(draws)
        np.testing.assert_array_equal(first,second)
        self.assertEqual(first.shape,(16,40,59))
        self.assertEqual(first.dtype,np.float32)
        self.assertTrue(np.isfinite(first).all())

if __name__=="__main__":
    unittest.main()
