import unittest
import numpy as np
import sonar_q141_a11_triple_residual as a11

class TripleResidualTests(unittest.TestCase):
    def setUp(self):
        self.rng=np.random.default_rng(14111321)
    def draws(self,count,n=40):
        return np.asarray([np.sort(self.rng.choice(np.arange(1,n+1),5,replace=False)) for _ in range(count)],dtype=np.int64)
    def test_pair_margins_are_zero(self):
        r,d=a11.triple_residuals(self.draws(200))
        self.assertLess(d["pair_marginal_max"],1e-8)
        self.assertLess(a11.pair_marginal_max(r),1e-8)
    def test_exact_variance_matches_exhaustive_small_enumeration(self):
        self.assertTrue(a11.verify_small_variance())
    def test_additive_lower_order_data_are_removed(self):
        n=8; triples,pairs,*_=a11.structures(n); rng=np.random.default_rng(99)
        mu=2.0; single=rng.normal(size=n); single-=single.mean()
        pair=rng.normal(size=len(pairs)); pm=np.zeros((n,n))
        pm[pairs[:,0],pairs[:,1]]=pair; pm[pairs[:,1],pairs[:,0]]=pair
        for _ in range(3):
            row=pm.sum(axis=1)/(n-2); pm-=row[:,None]+row[None,:]
        y=np.asarray([mu+single[i]+single[j]+single[k]+pm[i,j]+pm[i,k]+pm[j,k] for i,j,k in triples])
        residuals,_=a11.triple_residuals_from_counts(y,n=n)
        self.assertLess(float(np.max(np.abs(residuals))),1e-8)
    def test_requires_400_strictly_prior_rows(self):
        x=self.draws(450)
        with self.assertRaises(ValueError): a11.score_target(x,399)
        r=a11.score_target(x,400)
        self.assertTrue(np.isfinite(r["z3_recent"]) and np.isfinite(r["z3_stale"]) and np.isfinite(r["z3_recent_vs_stale"]))
    def test_future_suffix_mutation_invariance(self):
        x=self.draws(470); t=420; before=a11.score_target(x,t); changed=x.copy()
        for i in range(t+1,len(changed)): changed[i]=np.sort(self.rng.choice(np.arange(1,41),5,replace=False))
        self.assertEqual(before,a11.score_target(changed,t))
    def test_deterministic_replay(self):
        x=self.draws(460); self.assertEqual(a11.score_target(x,430),a11.score_target(x,430))
    def test_duplicate_number_rejected(self):
        x=self.draws(200); x[17,1]=x[17,0]
        with self.assertRaises(ValueError): a11.triple_counts(x)
    def test_contrast_residual_preserves_pair_margins(self):
        recent,_=a11.triple_residuals(self.draws(200)); stale,_=a11.triple_residuals(self.draws(200))
        vr=a11.triple_null_variance(recent); vs=a11.triple_null_variance(stale)
        contrast=recent/np.sqrt(vr)-stale/np.sqrt(vs)
        self.assertLess(a11.pair_marginal_max(contrast),1e-8)
        self.assertGreaterEqual(a11.triple_null_variance(contrast),0.0)

if __name__=="__main__": unittest.main()
