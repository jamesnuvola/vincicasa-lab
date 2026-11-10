#!/usr/bin/env python3
"""Q96 regression tests for delayed spectral recurrence."""
import json, sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sonar_q96_delayed_spectral_recurrence as q96
import sonar_q94_spectral_subspace_persistence as q94

def orthogonal_basis(rng,columns):
    x=rng.normal(size=(40,columns))
    x-=np.ones((40,1))@(np.ones((1,40))@x/40.0)
    return np.linalg.qr(x)[0]

class Q96Tests(unittest.TestCase):
    def test_fixed_permutations_reproducible_unique_nonidentity(self):
        a=q96.fixed_permutations(); b=q96.fixed_permutations()
        np.testing.assert_array_equal(a,b)
        self.assertEqual(a.shape,(999,40))
        self.assertEqual(len({tuple(x.tolist()) for x in a}),999)
        self.assertFalse(any(np.array_equal(x,np.arange(40)) for x in a))

    def test_permutations_preserve_ones_orthogonality_and_gram(self):
        rng=np.random.default_rng(96011)
        basis=orthogonal_basis(rng,2)
        for p in q96.fixed_permutations()[:40]:
            v=basis[p,:]
            self.assertLess(np.max(np.abs(v.T@np.ones(40))),1e-8)
            np.testing.assert_allclose(v.T@v,np.eye(2),atol=1e-10,rtol=0)

    def test_reference_index_fixed_lags_and_boundaries(self):
        self.assertEqual(q96.reference_index(2,2),0)
        self.assertEqual(q96.reference_index(5,3),2)
        self.assertEqual(q96.reference_index(9,5),4)
        self.assertIsNone(q96.reference_index(0,2))
        self.assertIsNone(q96.reference_index(4,5))
        with self.assertRaises(ValueError):
            q96.reference_index(4,1)

    def test_identical_subspace_overlap_is_one(self):
        basis=orthogonal_basis(np.random.default_rng(96012),2)
        self.assertAlmostEqual(q94.subspace_overlap(basis,basis),1.0,places=12)

    def test_lagged_reference_is_strictly_earlier(self):
        for lag in q96.LAGS:
            for off in range(lag,20):
                j=q96.reference_index(off,lag)
                self.assertLess(j,off)
                self.assertEqual(off-j,lag)

    def test_bootstrap_reproducible(self):
        x=np.linspace(-0.5,0.5,100)
        a=q96.q95.bootstrap_ci(x,seed=96013)
        b=q96.q95.bootstrap_ci(x,seed=96013)
        self.assertEqual(a,b)

    def test_split_sizes(self):
        labels=q96.q93.split_labels(3203)
        self.assertEqual((labels.count("discovery"),labels.count("validation"),labels.count("blind_oos")),(1921,641,641))

    def test_holm_global_family_size_and_monotonicity(self):
        tests=[{"test_id":f"t{i}","p_raw":p} for i,p in enumerate([.001,.01,.03,.04,.2,.4,.6,.8,.9])]
        adj=q96.q95.holm(tests)
        self.assertEqual(len(adj),9)
        self.assertTrue(all(0<=x<=1 for x in adj.values()))
        self.assertLessEqual(adj["t0"],adj["t1"])
        self.assertLessEqual(adj["t1"],adj["t2"])

    def test_ledger_schema_has_three_full_permutation_families(self):
        fields=q96.ledger_fields()
        self.assertEqual(len(fields),4+3*(8+999))
        for lag in q96.LAGS:
            self.assertIn(f"lag_{lag}_perm_0998",fields)

    def test_protocol_matches_frozen_engine_parameters(self):
        protocol=json.loads(q96.PROTOCOL.read_text(encoding="utf-8"))
        self.assertEqual(protocol["lags"],list(q96.LAGS))
        self.assertEqual(protocol["permutation_null"]["count"],q96.PERM_COUNT)
        self.assertEqual(protocol["permutation_null"]["seed"],q96.PERM_SEED)
        self.assertIn("nine",protocol["statistics"]["multiple_testing"])

    def test_compressed_ledger_writer_dependency_is_available(self):
        self.assertTrue(hasattr(q96.io, "TextIOWrapper"))

    def test_q95_accepted_source_fingerprints_present(self):
        self.assertTrue(q96.q95.MANIFEST.is_file())
        self.assertTrue(q96.q95.VALIDATION.is_file())
        self.assertEqual(q96.PERM_COUNT,999)
        self.assertEqual(q96.REPS,2000)

if __name__=="__main__":
    unittest.main(verbosity=2)
