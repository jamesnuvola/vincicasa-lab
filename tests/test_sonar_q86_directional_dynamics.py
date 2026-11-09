#!/usr/bin/env python3
"""Regression tests for Q86-DIR directional field kinematics."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q86_directional_dynamics as q86dir
import sonar_per_number_field_dynamics as field

class Q86DirectionalDynamicsTests(unittest.TestCase):
    def test_rowwise_cosine_detects_alignment_reversal_orthogonality_and_zero(self):
        left=np.asarray([[1.,0.],[1.,0.],[1.,0.],[0.,0.]])
        right=np.asarray([[2.,0.],[-1.,0.],[0.,1.],[1.,1.]])
        np.testing.assert_allclose(q86dir.rowwise_cosine(left,right),[1.,-1.,0.,0.],atol=1e-12)

    def test_rowwise_cosine_rejects_shape_and_nonfinite_inputs(self):
        with self.assertRaises(ValueError): q86dir.rowwise_cosine(np.zeros((40,6)),np.zeros((40,5)))
        bad=np.zeros((40,6)); bad[0,0]=np.nan
        with self.assertRaises(ValueError): q86dir.rowwise_cosine(bad,np.zeros((40,6)))

    def test_transition_metrics_returns_neutral_first_state_and_signed_vectors(self):
        features=np.ones((40,6)); edge=np.ones((40,40))
        first=q86dir.transition_metrics(features,edge,None,None,None,None)
        self.assertEqual(first[:4],(0.,0.,0.,0.))
        np.testing.assert_array_equal(first[4],np.zeros(40)); np.testing.assert_array_equal(first[5],np.zeros(40))
        result=q86dir.transition_metrics(features,edge,np.zeros((40,6)),np.zeros((40,40)),np.zeros((40,6)),np.zeros((40,40)))
        np.testing.assert_allclose(result[4],np.ones(40)); np.testing.assert_allclose(result[5],np.ones(40))
        self.assertEqual(result[6].shape,(40,6)); self.assertEqual(result[7].shape,(40,40))

    def test_directional_operator_scores_are_fixed_alpha_and_finite(self):
        base=np.linspace(-1.,1.,40); rev=np.linspace(1.,-1.,40); graph=np.sin(np.arange(40,dtype=float))
        node=np.linspace(-1.,1.,40); edge=np.linspace(1.,-1.,40)
        scores=q86dir.directional_operator_scores(base,rev,graph,node,edge)
        self.assertEqual(tuple(scores),q86dir.DYNAMIC_IDS); self.assertEqual(len(scores),4)
        self.assertTrue(all(v.shape==(40,) and np.isfinite(v).all() for v in scores.values()))
        np.testing.assert_allclose(scores[q86dir.DYNAMIC_IDS[0]]-base,.20*rev*node,atol=1e-12)
        np.testing.assert_allclose(scores[q86dir.DYNAMIC_IDS[1]]-base,-.20*rev*node,atol=1e-12)
        np.testing.assert_allclose(scores[q86dir.DYNAMIC_IDS[2]]-base,.20*graph*edge,atol=1e-12)
        np.testing.assert_allclose(scores[q86dir.DYNAMIC_IDS[3]]-base,.20*.5*(rev+graph)*node*edge,atol=1e-12)

    def test_coherence_product_and_directional_hash_are_deterministic(self):
        node=np.linspace(-1.,1.,40); graph=np.linspace(1.,-1.,40); coherence=node*graph
        a=q86dir.directional_state_hash(node,graph,coherence)
        self.assertEqual(a,q86dir.directional_state_hash(node.copy(),graph.copy(),coherence.copy()))
        self.assertEqual(len(a),64)
        with self.assertRaises(ValueError): q86dir.directional_state_hash(node[:39],graph,coherence)

    def test_field_state_is_prefix_invariant_to_future_appends(self):
        draws=[]
        for i in range(130):
            nums=tuple(sorted({((i*7+j*11)%40)+1 for j in range(5)}))
            self.assertEqual(len(nums),5); draws.append({"nums":nums})
        prefix=q86dir.field_state_for_target(draws,120)
        extended=q86dir.field_state_for_target(draws+draws[120:],120)
        self.assertEqual(prefix["signature"],extended["signature"])
        np.testing.assert_array_equal(prefix["features"],extended["features"])
        np.testing.assert_array_equal(prefix["graph_signal"],extended["graph_signal"])

    def test_ledger_schema_contains_all_directional_values_and_rank_columns(self):
        fields=q86dir.ledger_fields()
        for item in ("directional_state_sha256","node_alignment_01","graph_alignment_40","node_graph_coherence_40","rank_base_equal42_40"):
            self.assertIn(item,fields)
        for prefix in ("node_alignment_","graph_alignment_","node_graph_coherence_"):
            self.assertEqual(sum(x.startswith(prefix) and x[-2:].isdigit() for x in fields),40)

    def test_registered_model_and_multiple_testing_dimensions(self):
        self.assertEqual(len(q86dir.MODEL_IDS),8); self.assertEqual(len(q86dir.DYNAMIC_IDS),4)
        self.assertEqual(len(q86dir.MODEL_IDS)*3*3,72); self.assertEqual(2*4*4,32)
        self.assertEqual(q86dir.EXPECTED_DRAWS-q86dir.MIN_HISTORY,q86dir.EXPECTED_TARGETS)

    def test_rank_helper_is_stable_permutation(self):
        rank=field.rank_from_scores(np.linspace(-1.,1.,40))
        self.assertEqual(sorted(rank.tolist()),list(range(1,41)))

if __name__=="__main__": unittest.main(verbosity=2)
