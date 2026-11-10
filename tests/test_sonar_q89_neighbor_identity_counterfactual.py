#!/usr/bin/env python3
"""Q89 deterministic permutation, prior-only and structural regression tests."""
import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sonar_q89_neighbor_identity_counterfactual as q89
import sonar_q88_signed_node_graph_transfer as q88
class Q89Tests(unittest.TestCase):
    def test_permutations_are_fixed_unique_and_hashed(self):
        p=q89.PERMUTATIONS
        self.assertEqual(p.shape,(40,40)); np.testing.assert_array_equal(p[0],np.arange(40))
        self.assertEqual(len({tuple(x.tolist()) for x in p}),40)
        for x in p: self.assertEqual(sorted(x.tolist()),list(range(40)))
        self.assertEqual(q89.PERMUTATION_SHA256,"65550b9161304f61ea7899ad3e2545b8321523ebf9307717b1d28e48cd635bcb")
    def test_identity_projection_matches_q88(self):
        rng=np.random.default_rng(8902); node=rng.normal(size=(40,6)); feat=rng.normal(size=(40,6))
        x=rng.normal(size=(40,40)); edge=.5*(x+x.T); np.fill_diagonal(edge,0)
        got=q89.all_neighbor_transfer(node,edge,feat)
        np.testing.assert_allclose(got[0],q88.signed_transfer_alignment(node,edge,feat),atol=1e-12,rtol=0)
    def test_edge_matrix_and_row_strength_are_unchanged(self):
        rng=np.random.default_rng(8903); x=rng.normal(size=(40,40)); edge=.5*(x+x.T); np.fill_diagonal(edge,0)
        before=edge.copy(); strength=edge.sum(axis=1).copy()
        q89.all_neighbor_transfer(rng.normal(size=(40,6)),edge,rng.normal(size=(40,6)))
        np.testing.assert_array_equal(edge,before); np.testing.assert_array_equal(edge.sum(axis=1),strength)
    def test_rolling_matrix_is_future_invariant(self):
        rng=np.random.default_rng(8904); x=rng.normal(size=(60,40,40))
        expected=q89.rolling_matrix(x,24); changed=x.copy(); changed[25:]=rng.normal(size=changed[25:].shape)*100
        np.testing.assert_array_equal(q89.rolling_matrix(changed,24),expected)
    def test_randomization_p_value_resolution(self):
        self.assertEqual(q89.randomization_p(1.0,np.zeros(39)),.025)
        self.assertEqual(q89.randomization_p(0.0,np.zeros(39)),1.0)
    def test_node_only_cosine_signed_and_graph_free(self):
        a=np.zeros((40,6)); a[:,0]=1
        np.testing.assert_array_equal(q88.rowwise_signed_cosine(a,a),np.ones(40))
        np.testing.assert_array_equal(q88.rowwise_signed_cosine(a,-a),-np.ones(40))
    def test_model_and_multiple_testing_dimensions(self):
        self.assertEqual(len(q89.PERMUTED_IDS),39); self.assertEqual(len(q89.MODEL_IDS),41); self.assertEqual(len(q89.ALL_MODEL_IDS),42)
        self.assertEqual(42*3*3,378); self.assertEqual(2*3*4,24); self.assertEqual(3*3,9)
        self.assertEqual((q89.WINDOW,q89.DECAY,q89.ALPHA),(20,.80,.20))
    def test_all_feature_permutations_preserve_feature_multiset(self):
        f=np.arange(240,dtype=float).reshape(40,6)
        for p in q89.PERMUTATIONS: np.testing.assert_array_equal(np.sort(f[p],axis=0),np.sort(f,axis=0))
    def test_actual_rank_extraction_keeps_model_by_winner_axes(self):
        ranks=np.tile(np.arange(1,41,dtype=np.int8),(42,1))
        actual=np.array([1,5,10,20,30])
        got=q89.extract_actual_ranks(ranks,actual)
        self.assertEqual(got.shape,(42,5))
        np.testing.assert_array_equal(got[0],actual)

    def test_rank_is_complete_permutation(self):
        ranks=q89.q87.field.rank_from_scores(np.linspace(-1,1,40))
        self.assertEqual(sorted(ranks.tolist()),list(range(1,41)))
    def test_node_ewma_is_prefix_only(self):
        rng=np.random.default_rng(8905); x=rng.normal(size=(40,40)); expected=q88.rolling_signed_transfer(x,18)
        x[19:]=rng.normal(size=x[19:].shape)*100
        np.testing.assert_array_equal(q88.rolling_signed_transfer(x,18),expected)
if __name__=="__main__": unittest.main(verbosity=2)
