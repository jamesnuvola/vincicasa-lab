#!/usr/bin/env python3
"""Q95 regression tests for constrained node-label permutation nulls."""
import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sonar_q95_subspace_permutation_null as q95
import sonar_q94_spectral_subspace_persistence as q94

class Q95Tests(unittest.TestCase):
    def test_fixed_permutations_reproducible_unique_nonidentity(self):
        a=q95.fixed_permutations(); b=q95.fixed_permutations()
        np.testing.assert_array_equal(a,b)
        self.assertEqual(a.shape,(999,40))
        self.assertEqual(len({tuple(x.tolist()) for x in a}),999)
        self.assertFalse(any(np.array_equal(x,np.arange(40)) for x in a))
    def test_permutations_preserve_ones_orthogonality_and_gram(self):
        rng=np.random.default_rng(95011); x=rng.normal(size=(40,2))
        x-=np.ones((40,1))@(np.ones((1,40))@x/40.0); basis,_=np.linalg.qr(x)
        for p in q95.fixed_permutations()[:30]:
            v=q95.permuted_basis(basis,p)
            self.assertLess(np.max(np.abs(v.T@np.ones(40))),1e-8)
            np.testing.assert_allclose(v.T@v,np.eye(2),atol=1e-10,rtol=0)
    def test_identity_overlap_matches_q94(self):
        rng=np.random.default_rng(95012); a,_=np.linalg.qr(rng.normal(size=(40,2))); b,_=np.linalg.qr(rng.normal(size=(40,2)))
        p=np.arange(40,dtype=np.int16)[None,:]
        self.assertAlmostEqual(float(q95.overlap_many(a,b,p)[0]),q94.subspace_overlap(a,b),places=12)
    def test_vectorized_overlap_matches_scalar_loop(self):
        rng=np.random.default_rng(95013); a,_=np.linalg.qr(rng.normal(size=(40,2))); b,_=np.linalg.qr(rng.normal(size=(40,3)))
        ps=q95.fixed_permutations()[:20]
        x=q95.overlap_many(a,b,ps)
        y=np.asarray([q94.subspace_overlap(a,q95.permuted_basis(b,p)) for p in ps])
        np.testing.assert_allclose(x,y,atol=1e-12,rtol=0)
    def test_empty_subspace_yields_zero(self):
        empty=np.zeros((40,0)); b=np.eye(40)[:,:2]
        np.testing.assert_array_equal(q95.overlap_many(empty,b,q95.fixed_permutations()[:5]),np.zeros(5))
    def test_average_ranks_with_ties(self):
        np.testing.assert_allclose(q95.average_ranks([3,1,1,4,3]),[3.5,1.5,1.5,5,3.5])
    def test_spearman_sign_and_constant(self):
        x=np.array([1,2,2,4,5.]); self.assertAlmostEqual(q95.spearman(x,x),1,places=12)
        self.assertAlmostEqual(q95.spearman(x,-x),-1,places=12); self.assertEqual(q95.spearman(np.ones(5),x),0)
    def test_block_bootstrap_reproducible(self):
        x=np.linspace(-1,1,80); a=q95.bootstrap_ci(x,seed=95014); b=q95.bootstrap_ci(x,seed=95014); self.assertEqual(a,b)
    def test_all_nonzero_shifts_for_641_targets(self):
        a=q95.shift_offsets(641,95015); b=q95.shift_offsets(641,95015)
        np.testing.assert_array_equal(a,b); self.assertEqual(len(a),640); self.assertTrue(np.all(a>0)); self.assertTrue(np.all(a<641))
    def test_strict_prefix_and_splits(self):
        d=list(range(20)); self.assertEqual(q94.strict_history(d,12),list(range(12)))
        labels=q95.q93.split_labels(3203)
        self.assertEqual((labels.count("discovery"),labels.count("validation"),labels.count("blind_oos")),(1921,641,641))
    def test_holm_family_is_bounded_and_monotone(self):
        a=q95.holm([{"test_id":"a","p_raw":.001},{"test_id":"b","p_raw":.02},{"test_id":"c","p_raw":.5}])
        self.assertTrue(all(0<=x<=1 for x in a.values())); self.assertGreaterEqual(a["b"],a["a"]); self.assertGreaterEqual(a["c"],a["b"])
    def test_preregistered_family_size_and_counts(self):
        self.assertEqual(q95.PERM_COUNT,999); self.assertEqual(q95.SHIFT_COUNT,999)
        self.assertEqual(q95.BLOCK,20); self.assertEqual(q95.REPS,2000)

if __name__=="__main__": unittest.main(verbosity=2)
