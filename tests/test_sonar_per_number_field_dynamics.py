#!/usr/bin/env python3
import sys, unittest
from datetime import date, timedelta
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_field_dynamics as field


def draws(n=520,seed=8401):
    rng=np.random.default_rng(seed); start=date(2020,1,1); out=[]
    for i in range(n):
        nums=sorted(rng.choice(np.arange(1,41),size=5,replace=False).tolist())
        out.append({"date":start+timedelta(days=i),"nums":nums})
    return out


class Q84PerNumberFieldTests(unittest.TestCase):
    def test_field_shape_and_finite_values(self):
        result=field.field_state(draws())
        self.assertEqual(result["features"].shape,(40,6))
        self.assertEqual(set(result["signals"]),set(field.VARIANTS))
        self.assertTrue(np.isfinite(result["features"]).all())
        self.assertTrue(np.isfinite(result["graph_signal"]).all())

    def test_future_rows_do_not_change_pre_target_field(self):
        history=draws(seed=8402); target_index=480
        before=field.field_state_for_target(history,target_index)
        altered=[dict(row) for row in history]
        for i in range(target_index,len(altered)):
            altered[i]=dict(altered[i],nums=[1,2,3,4,5])
        after=field.field_state_for_target(altered,target_index)
        np.testing.assert_array_equal(before["features"],after["features"])
        np.testing.assert_array_equal(before["graph_signal"],after["graph_signal"])
        self.assertEqual(before["signature"],after["signature"])

    def test_pair_graph_symmetric_and_zero_diagonal(self):
        graph=field.pair_residual_graph(draws(seed=8403))
        np.testing.assert_allclose(graph,graph.T,rtol=0,atol=1e-14)
        np.testing.assert_array_equal(np.diag(graph),np.zeros(40))

    def test_rank_is_stable_permutation(self):
        scores=np.linspace(-1,1,40)
        a=field.rank_from_scores(scores); b=field.rank_from_scores(scores)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(sorted(a.tolist()),list(range(1,41)))

    def test_exact_null_tail_is_bounded_and_monotone(self):
        for k in (5,10,20):
            p=[field.exact_upper_tail(x,40,k) for x in range(201)]
            self.assertEqual(p[0],1.0)
            self.assertTrue(all(0<=v<=1 for v in p))
            self.assertTrue(all(p[i+1] <= p[i]+1e-12 for i in range(len(p)-1)))

    def test_raw_float_signature_drift_is_diagnostic_not_rank_acceptance(self):
        from validate_sonar_per_number_field_dynamics import field_signature_mismatch_is_diagnostic
        self.assertFalse(field_signature_mismatch_is_diagnostic("abc", "abc"))
        self.assertTrue(field_signature_mismatch_is_diagnostic("abc", "def"))


    def test_registered_family_dimensions(self):
        self.assertEqual(len(field.MODEL_IDS),14)
        self.assertEqual(len(field.FIELD_IDS),12)
        self.assertEqual(len(field.MODEL_IDS)*3*3,126)
        self.assertEqual([x["strategy_id"] for x in field.catalog_entries()],list(field.MODEL_IDS))

    def test_invalid_prefix_boundaries_rejected(self):
        sample=draws(120)
        with self.assertRaises(ValueError): field.field_state_for_target(sample,0)
        with self.assertRaises(ValueError): field.field_state_for_target(sample,len(sample)+1)


if __name__=="__main__": unittest.main(verbosity=2)
