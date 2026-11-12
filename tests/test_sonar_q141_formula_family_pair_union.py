#!/usr/bin/env python3
import math
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_family_pair_union as c1


def synthetic_draws(count=120):
    return [tuple(((i*7+j*9)%40) for j in range(5)) for i in range(count)]


class Q141PairUnionTests(unittest.TestCase):
    def test_hypergeometric_pmf_normalizes_and_has_conditional_mean(self):
        for u in range(5,11):
            pmf=base.hypergeom_pmf(u)
            self.assertAlmostEqual(sum(pmf.values()),1.0,places=12)
            mean=sum(h*p for h,p in pmf.items())
            self.assertAlmostEqual(mean,5.0*u/40.0,places=12)

    def test_centered_log_mgf_is_exact_and_zero_at_lambda_zero(self):
        for u in range(5,11):
            self.assertAlmostEqual(c1.centered_log_mgf(u,0.0),0.0,places=12)
            for lam in c1.LAMBDA_GRID:
                log_mgf=c1.centered_log_mgf(u,lam)
                mean=5.0*u/40.0
                expectation=sum(p*math.exp(lam*(h-mean)-log_mgf) for h,p in base.hypergeom_pmf(u).items())
                self.assertAlmostEqual(expectation,1.0,places=11)

    def test_pair_union_cardinality_and_hit_count(self):
        a=sum(1<<x for x in range(5))
        b=sum(1<<x for x in range(4,9))
        union,size,hits=c1.pair_union_size_hits(a,b,(0,4,8,9,10))
        self.assertEqual(size,9)
        self.assertEqual(union.bit_count(),9)
        self.assertEqual(hits,3)

    def test_family_top5_masks_have_exact_cardinality(self):
        draws=synthetic_draws()
        target=80
        state=base.build_state(draws[:target])
        features=base.feature_matrix(target,draws,*state)
        masks=c1.family_top5_masks(features)
        self.assertEqual(set(masks),set(base.FAMILY_NAMES))
        self.assertTrue(all(mask.bit_count()==5 for mask in masks.values()))

    def test_future_suffix_invariance_for_pair_candidate_sets(self):
        draws=synthetic_draws()
        target=80
        state=base.build_state(draws[:target])
        original=c1.family_top5_masks(base.feature_matrix(target,draws,*state))
        altered=list(draws)
        for i in range(target,len(altered)):
            altered[i]=tuple(sorted(((i+13+j*7)%40) for j in range(5)))
        changed=c1.family_top5_masks(base.feature_matrix(target,altered,*state))
        self.assertEqual(original,changed)

    def test_e_process_is_deterministic_and_p_is_bounded(self):
        rows=[{"union_size":9,"union_hits":2+(i%2)} for i in range(31)]
        first=c1.e_process_result(rows)
        second=c1.e_process_result(rows)
        self.assertEqual(first,second)
        self.assertGreaterEqual(first["p_anytime_raw"],0.0)
        self.assertLessEqual(first["p_anytime_raw"],1.0)

    def test_holm_adjustment_is_bounded_and_monotone(self):
        raw=[0.03,0.001,0.2,0.04]
        adjusted=base.holm_adjust(raw)
        self.assertEqual(len(adjusted),len(raw))
        self.assertTrue(all(0.0<=p<=1.0 for p in adjusted))
        order=sorted(range(len(raw)),key=lambda i:(raw[i],i))
        values=[adjusted[i] for i in order]
        self.assertEqual(values,sorted(values))


if __name__=="__main__":
    unittest.main(verbosity=2)
