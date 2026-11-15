import unittest
import numpy as np
import sonar_q141_a10_pairwise_residual as a10

class PairwiseResidualTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(14111320)

    def draws(self,n):
        return np.array([np.sort(self.rng.choice(np.arange(1,41),5,replace=False)) for _ in range(n)],dtype=np.int64)

    def test_additive_residuals_have_zero_row_sums(self):
        r=a10.pair_residuals(self.draws(200))
        self.assertTrue(np.allclose(r.sum(axis=1),0,atol=1e-9))
        self.assertTrue(np.allclose(r,r.T,atol=1e-12))
        self.assertTrue(np.allclose(np.diag(r),0,atol=1e-12))

    def test_exact_variance_matches_exhaustive_small_enumeration(self):
        self.assertTrue(a10.verify_small_variance())

    def test_requires_400_prior_rows(self):
        x=self.draws(450)
        with self.assertRaises(ValueError): a10.score_target(x,399)
        y=a10.score_target(x,400)
        self.assertTrue(np.isfinite(y["z_recent"]))
        self.assertTrue(np.isfinite(y["z_stale"]))

    def test_future_suffix_mutation_invariance(self):
        x=self.draws(470); t=420
        before=a10.score_target(x,t)
        changed=x.copy()
        for i in range(t+1,len(changed)):
            changed[i]=np.sort(self.rng.choice(np.arange(1,41),5,replace=False))
        self.assertEqual(before,a10.score_target(changed,t))

    def test_deterministic_score_replay(self):
        x=self.draws(460)
        self.assertEqual(a10.score_target(x,430),a10.score_target(x,430))

    def test_duplicate_number_rejected(self):
        x=self.draws(200); x[17,1]=x[17,0]
        with self.assertRaises(ValueError): a10.pair_residuals(x)

    def test_variance_nonnegative(self):
        r=a10.pair_residuals(self.draws(200))
        self.assertGreaterEqual(a10.null_variance(r,5),0.0)

if __name__=="__main__": unittest.main()
