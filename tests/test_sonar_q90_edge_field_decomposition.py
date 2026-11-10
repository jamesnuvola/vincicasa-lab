#!/usr/bin/env python3
"""Q90 decomposition, projection, prefix and ranking regression tests."""
import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import sonar_q90_edge_field_decomposition as q90
import sonar_q88_signed_node_graph_transfer as q88
import sonar_q87_node_graph_phase_lag as q87

class Q90EdgeDecompositionTests(unittest.TestCase):
    def test_random_symmetric_edge_decomposes_exactly(self):
        rng=np.random.default_rng(9001)
        x=rng.normal(size=(40,40))
        edge=.5*(x+x.T); np.fill_diagonal(edge,0.0)
        main,residual,diag=q90.decompose_edge_change(edge)
        np.testing.assert_allclose(main+residual,edge,atol=1e-12,rtol=0)
        np.testing.assert_allclose(residual,residual.T,atol=1e-12,rtol=0)
        np.testing.assert_allclose(np.diag(residual),0.0,atol=1e-12,rtol=0)
        np.testing.assert_allclose(residual.sum(axis=1),0.0,atol=1e-10,rtol=0)
        self.assertLess(diag["residual_row_sum_max_abs"],1e-10)
        self.assertLess(abs(diag["main_interaction_inner_product"]),1e-9)

    def test_additive_edge_field_has_zero_pair_residual(self):
        rng=np.random.default_rng(9002)
        effects=rng.normal(size=40); effects-=effects.mean()
        mu=.17
        edge=mu+effects[:,None]+effects[None,:]
        np.fill_diagonal(edge,0.0)
        main,residual,diag=q90.decompose_edge_change(edge)
        np.testing.assert_allclose(main,edge,atol=1e-12,rtol=0)
        np.testing.assert_allclose(residual,0.0,atol=1e-12,rtol=0)
        self.assertLess(diag["interaction_energy_fraction"],1e-28)

    def test_zero_edge_is_stable(self):
        main,residual,diag=q90.decompose_edge_change(np.zeros((40,40)))
        np.testing.assert_array_equal(main,np.zeros((40,40)))
        np.testing.assert_array_equal(residual,np.zeros((40,40)))
        self.assertEqual(diag["interaction_energy_fraction"],0.0)

    def test_rejects_asymmetric_or_nonzero_diagonal(self):
        edge=np.zeros((40,40)); edge[0,1]=1.0
        with self.assertRaises(ValueError): q90.decompose_edge_change(edge)
        edge=np.zeros((40,40)); edge[0,0]=1.0
        with self.assertRaises(ValueError): q90.decompose_edge_change(edge)

    def test_projection_is_linear_across_main_and_interaction(self):
        rng=np.random.default_rng(9003)
        x=rng.normal(size=(40,40)); edge=.5*(x+x.T); np.fill_diagonal(edge,0.0)
        features=rng.normal(size=(40,6))
        main,residual,_=q90.decompose_edge_change(edge)
        whole=q88.projected_graph_change(edge,features)
        pieces=q88.projected_graph_change(main,features)+q88.projected_graph_change(residual,features)
        np.testing.assert_allclose(whole,pieces,atol=1e-12,rtol=0)

    def test_residual_projection_annihilates_constant_neighbor_channel(self):
        rng=np.random.default_rng(9004)
        x=rng.normal(size=(40,40)); edge=.5*(x+x.T); np.fill_diagonal(edge,0.0)
        _,residual,_=q90.decompose_edge_change(edge)
        constant=np.ones((40,1))
        np.testing.assert_allclose(residual@constant,0.0,atol=1e-10,rtol=0)

    def test_rolling_signal_excludes_future_rows(self):
        rng=np.random.default_rng(9005)
        history=rng.normal(size=(60,40))
        expected=q88.rolling_signed_transfer(history,24,20,.80)
        changed=history.copy(); changed[25:]=rng.normal(size=changed[25:].shape)*100
        np.testing.assert_array_equal(q88.rolling_signed_transfer(changed,24,20,.80),expected)

    def test_rank_extraction_model_winner_orientation(self):
        ranks=np.tile(np.arange(1,41,dtype=np.int8),(len(q90.MODEL_IDS),1))
        actual=np.array([1,5,10,20,30])
        got=q90.extract_actual_ranks(ranks,actual)
        self.assertEqual(got.shape,(5,5))
        np.testing.assert_array_equal(got[0],actual)

    def test_chronological_split_counts_for_pinned_archive(self):
        labels=q90.split_labels(3203)
        from collections import Counter
        self.assertEqual(dict(Counter(labels)),{"discovery":1921,"validation":641,"blind_oos":641})

    def test_equal42_rank_is_complete_and_deterministic(self):
        draws=q87.read_draws()
        history=draws[:q90.MIN_HISTORY]
        a=q90.equal42_rank(history); b=q90.equal42_rank(history)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(sorted(a.tolist()),list(range(1,41)))

    def test_fixed_operator_parameters_and_focal_model(self):
        self.assertEqual((q90.ALPHA,q90.WINDOW,q90.DECAY),(0.20,20,0.80))
        self.assertEqual(q90.FOCAL,"Q90::PAIR_INTERACTION_TRANSFER")
        self.assertEqual(len(q90.MODEL_IDS),5)
        self.assertEqual(len(q90.COMPARATORS),4)

if __name__=="__main__":
    unittest.main(verbosity=2)
