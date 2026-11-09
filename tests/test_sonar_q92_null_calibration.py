#!/usr/bin/env python3
"""Synthetic regressions for Q92 discrete null calibration."""
from __future__ import annotations
import unittest
import numpy as np
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q92_null_calibration as null
class Q92NullCalibrationTests(unittest.TestCase):
    def test_one_target_known_hypergeometric_tails(self):
        denominator=658008
        self.assertAlmostEqual(null.exact_upper_tail_pvalue(0,1,5),1.0,places=14)
        self.assertAlmostEqual(null.exact_upper_tail_pvalue(1,1,5),1.0-324632/denominator,places=14)
        self.assertAlmostEqual(null.exact_upper_tail_pvalue(5,1,5),1.0/denominator,places=14)
    def test_small_sum_tail_matches_direct_convolution(self):
        base=null._single_target_pmf(10); distribution=np.convolve(np.convolve(np.asarray([1.0]),base),base)
        self.assertAlmostEqual(null.exact_upper_tail_pvalue(3,2,10),float(distribution[3:].sum()),places=14)
    def test_exact_tail_is_monotone_and_positive(self):
        tail=null._sum_upper_tail_table(670,5)
        self.assertTrue(np.all(tail[:-1]>=tail[1:])); self.assertTrue(np.all(tail>0.0))
        self.assertLessEqual(float(tail[0]),1.0); self.assertGreater(float(tail[-1]),0.0)
    def test_expected_mean_matches_hypergeometric_expectation(self):
        for targets in (7,670,2012):
            for top_k in (5,10,20):
                tail=null._sum_upper_tail_table(targets,top_k)
                pmf=np.maximum(tail-np.concatenate((tail[1:],np.asarray([0.0]))),0.0)
                self.assertAlmostEqual(float(np.dot(np.arange(pmf.size),pmf)),targets*5.0*top_k/40.0,places=7)
    def test_invalid_inputs_fail_closed(self):
        for args in ((-1,10,5),(51,10,5),(1.5,10,5),(1,0,5),(1,10,41),(True,10,5)):
            with self.assertRaises(ValueError): null.exact_upper_tail_pvalue(*args)
    def test_normal_approximation_error_is_material_in_holm_tail(self):
        exact=null.exact_upper_tail_pvalue(532,670,5); approximate=null.normal_approximation_upper_tail(532,670,5)
        relative=abs(approximate-exact)/exact
        self.assertAlmostEqual(exact,7.934337625211848e-10,places=20)
        self.assertGreater(relative,0.65); self.assertLess(relative,0.70)
    def test_fixed_seedless_calibration_is_deterministic(self):
        self.assertEqual(null.exact_upper_tail_pvalue(984,670,10),null.exact_upper_tail_pvalue(984,670,10))
if __name__=="__main__": unittest.main()
