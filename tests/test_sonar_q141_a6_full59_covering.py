import importlib.util
import unittest
from pathlib import Path
import numpy as np

SCRIPT=Path(__file__).resolve().with_name('sonar_q141_a6_full59_covering.py')
SPEC=importlib.util.spec_from_file_location('q141_a6',SCRIPT)
Q=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(Q)

class Q141A6Tests(unittest.TestCase):
    def setUp(self):
        self.families={i:('baseline' if i<27 else ('ewma' if i<34 else 'gap' if i<40 else 'cooccurrence' if i<46 else 'rank' if i<51 else 'residual' if i<53 else 'regime')) for i in range(59)}
        self.names=[f'f{i:02d}' for i in range(59)]

    def test_full59_covering_design_covers_all_features_and_pairs(self):
        q,pc,fc,stats=Q.pair_cover_quartets(list(range(59)),self.families,350,Q.SEED)
        self.assertEqual(len(q),350)
        self.assertEqual(stats['pairs_covered'],1711)
        self.assertEqual(stats['pairs_total'],1711)
        self.assertEqual((stats['pair_count_min'],stats['pair_count_max']),(1,3))
        self.assertEqual((stats['feature_use_min'],stats['feature_use_max']),(23,24))

    def test_selected20_covering_design_covers_all_pairs_and_balances_features(self):
        indices=list(range(20))
        q,pc,fc,stats=Q.pair_cover_quartets(indices,self.families,350,Q.SEED+1)
        self.assertEqual(stats['pairs_covered'],190)
        self.assertEqual(stats['pairs_total'],190)
        self.assertEqual((stats['feature_use_min'],stats['feature_use_max']),(70,70))

    def test_sample_formula_counts_and_ast_ids(self):
        indices=list(range(20))
        q,pc,fc,stats=Q.pair_cover_quartets(indices,self.families,350,Q.SEED+1)
        linear,final_counts,fam_counts=Q.balanced_linear_sets(indices,self.families,75,Q.SEED+3,fc)
        formulas=Q.build_formulas('test',q,linear,self.names)
        self.assertEqual(len(formulas),5550)
        self.assertEqual(len({x['formula_id'] for x in formulas}),5550)
        self.assertEqual(len({x['ast_id'] for x in formulas}),5550)
        self.assertEqual({k:sum(x['formula_type']==k for x in formulas) for k in ('linear_mean','pairwise_interaction','conditional_gate')},{'linear_mean':650,'pairwise_interaction':2100,'conditional_gate':2800})

    def test_ranker_has_no_outcome_argument_and_future_suffix_invariance(self):
        formulas=[Q.make_formula('test','linear_mean',[0,1,2,3],self.names,'SET-test')]
        comp=Q.compile_formulas(formulas)
        rng=np.random.default_rng(44)
        matrix=rng.normal(size=(8,40,59))
        order_a,scores_a=Q.rank_target(matrix[2],comp)
        changed=matrix.copy(); changed[3:]=rng.normal(size=changed[3:].shape)
        order_b,scores_b=Q.rank_target(changed[2],comp)
        np.testing.assert_array_equal(order_a,order_b)
        np.testing.assert_array_equal(scores_a,scores_b)
        self.assertEqual(order_a[0,:5].tolist(),np.argsort(-np.round(scores_a[0],12),kind='stable')[:5].tolist())

    def test_stable_tie_policy_is_candidate_number_ascending(self):
        formulas=[Q.make_formula('test','linear_mean',[0,1,2,3],self.names,'SET-test')]
        comp=Q.compile_formulas(formulas)
        order,_=Q.rank_target(np.zeros((40,59),dtype=np.float64),comp)
        self.assertEqual(order[0,:5].tolist(),[0,1,2,3,4])

    def test_future_outcome_is_used_only_after_rank_freeze(self):
        formulas=[Q.make_formula('test','linear_mean',[0,1,2,3],self.names,'SET-test')]
        comp=Q.compile_formulas(formulas)
        X=np.arange(40*59,dtype=np.float64).reshape(40,59)
        order_before,_=Q.rank_target(X,comp)
        m1=Q.score_target(X,comp,[1,2,3,4,5])
        m2=Q.score_target(X,comp,[36,37,38,39,40])
        order_after,_=Q.rank_target(X,comp)
        np.testing.assert_array_equal(order_before,order_after)
        self.assertNotEqual(m1['top5'],m2['top5'])

if __name__=='__main__': unittest.main(verbosity=2)
