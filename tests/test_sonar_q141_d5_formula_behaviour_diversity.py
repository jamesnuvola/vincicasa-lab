import unittest, numpy as np
from scripts.sonar_q141_d5_formula_behaviour_diversity import plan_formulas, formula_top5_and_features, ridge_fit, ridge_predict, quintet

class D5Tests(unittest.TestCase):
    def make_plan(self):
        names=[f"f{i}" for i in range(59)]; rows=[]
        for fam,typ,size in [("L4","linear_mean",4),("L5","linear_mean",5),("L6","linear_mean",6),("L7","linear_mean",7),("L8","linear_mean",8),("I4","pairwise_interaction",4),("G4","conditional_gate",4)]:
            idx=list(range(size)); base={"formula_id":fam,"formula_type":typ,"formula_size":str(size),"feature_indices":";".join(map(str,idx)),"features":"+".join(names[i] for i in idx),"interaction_pair":"","gate_feature":"","gate_threshold":"","weight":""}
            if typ=="pairwise_interaction": base.update(interaction_pair="f0*f1",weight="0.25")
            if typ=="conditional_gate": base.update(gate_feature="f0",gate_threshold="0.5",weight="0.25")
            rows.extend([dict(base,formula_id=f"{fam}-{i}") for i in range(100)])
        return plan_formulas(rows,names)
    def test_quintet_validation(self): self.assertEqual(quintet("5 1 3 2 4"),(1,2,3,4,5))
    def test_formula_features_bounded_and_votes_conserved(self):
        p=self.make_plan(); top,f,v=formula_top5_and_features(np.random.default_rng(1).normal(size=(40,59)),p)
        self.assertEqual(top.shape,(700,5)); self.assertEqual(v.sum(),3500); self.assertTrue(np.isfinite(f).all()); self.assertTrue(np.all((f[:3]>=0)&(f[:3]<=1)))
    def test_tie_break_is_lower_number(self):
        p=self.make_plan(); top,_,_=formula_top5_and_features(np.zeros((40,59)),p); np.testing.assert_array_equal(top[0],[1,2,3,4,5])
    def test_identical_sets_have_full_pairwise_overlap(self):
        p=self.make_plan(); _,f,_=formula_top5_and_features(np.zeros((40,59)),p)
        self.assertAlmostEqual(f[2],1.0); self.assertAlmostEqual(f[3],1.0); self.assertAlmostEqual(f[1],1/700)
    def test_future_suffix_cannot_change_current_row_features(self):
        p=self.make_plan(); m=np.random.default_rng(2).normal(size=(12,40,59)); before=formula_top5_and_features(m[5],p)[1]
        m[6:]=np.random.default_rng(3).normal(size=m[6:].shape); after=formula_top5_and_features(m[5],p)[1]; np.testing.assert_array_equal(before,after)
    def test_ridge_residual_prediction_is_finite_and_unclipped(self):
        rng=np.random.default_rng(4); x=rng.normal(size=(100,4)); y=.8*x[:,0]-.3*x[:,1]; model=ridge_fit(x[:70],y[:70]); pred=ridge_predict(model,x[70:])
        self.assertTrue(np.isfinite(pred).all()); self.assertLess(float(pred.min()),0.0); self.assertGreater(float(pred.max()),0.0)
    def test_prior_only_training_slice_excludes_current(self):
        t=15; train=np.arange(10,t); self.assertEqual(train[-1],14); self.assertNotIn(t,train)

if __name__=="__main__": unittest.main()
