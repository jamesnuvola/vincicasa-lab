#!/usr/bin/env python3
import sys,unittest
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import sonar_higher_order_condition_grammar as q81
class Q81GrammarTests(unittest.TestCase):
 def test_formula_universe_counts_and_unique_ids(self):
  fs=list(q81.iter_formulas()); self.assertEqual(q81.FORMULA_COUNT,115614); self.assertEqual(len(fs),q81.FORMULA_COUNT)
  self.assertEqual(len({f[0] for f in fs}),q81.FORMULA_COUNT); self.assertEqual(dict(Counter(f[1] for f in fs)),q81.FAMILY_COUNTS)
 def test_batches_are_nonempty_and_disjoint_at_edges(self):
  a=q81.formulas_for_batch(0,128); b=q81.formulas_for_batch(127,128)
  self.assertTrue(a); self.assertTrue(b); self.assertFalse({x[0] for x in a}&{x[0] for x in b})
  self.assertEqual(len(a),904); self.assertEqual(len(b),806)
 def test_threshold_masks_respect_direction_and_boundary(self):
  z=np.zeros((40,27)); z[:5,0]=[-1.1,-1.0,-0.5,0.5,1.0]
  self.assertEqual(np.flatnonzero(q81.threshold_mask(z,0,"ge",1.0)).tolist(),[4])
  self.assertEqual(np.flatnonzero(q81.threshold_mask(z,0,"le",-1.0)).tolist(),[0,1])
 def test_conditional_score_is_deterministic_and_finite(self):
  z=np.zeros((40,27)); z[:,0]=np.linspace(-2,2,40); z[:,1]=np.linspace(-2,2,40)
  f=("TEST","conditional_add",(0,1),(1,"ge",1.0),0.5,"test")
  np.testing.assert_array_equal(q81.score_formula(f,z,z**2),z[:,0]+0.5*(z[:,1]>=1.0))
if __name__=="__main__": unittest.main(verbosity=2)
