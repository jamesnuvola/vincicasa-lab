import unittest
import numpy as np
from sonar_q141_d4_family_consensus_state import (
    build_family_groups, top5_from_scores, jaccard, target_family_state,
    build_disagreement_state, count_hits, hypergeom_5of40_pmf,
    exact_uniform_upper_tail, holm_adjust
)
class TestQ141D4(unittest.TestCase):
    def setUp(self):
        self.names=[f"f{i}" for i in range(59)]
        self.mapping={}
        groups={"ewma_hit_dynamics":range(27,34),"gap_dynamics":range(34,40),
                "cooccurrence_novelty":range(40,46),"rank_trajectory":range(46,51),
                "residual_surprise":range(51,53),"regime_transition_affinity":range(53,59)}
        for family,idxs in groups.items():
            for i in idxs: self.mapping[self.names[i]]=family
        self.groups=build_family_groups(self.names,self.mapping)
    def test_01_partition_all_59_once(self):
        flat=[i for ids in self.groups.values() for i in ids]
        self.assertEqual(sorted(flat),list(range(59))); self.assertEqual(len(flat),len(set(flat)))
        self.assertEqual(len(self.groups),7); self.assertEqual(len(self.groups["baseline_legacy"]),27)
    def test_02_top5_tie_rule(self):
        self.assertEqual(top5_from_scores(np.zeros(40)).tolist(),[1,2,3,4,5])
    def test_03_jaccard(self):
        self.assertEqual(jaccard([1,2,3,4,5],[1,2,3,4,5]),1.0)
        self.assertEqual(jaccard([1,2,3,4,5],[6,7,8,9,10]),0.0)
        self.assertAlmostEqual(jaccard([1,2,3,4,5],[1,6,7,8,9]),1/9)
    def test_04_target_state_shapes(self):
        x=np.arange(40*59,dtype=float).reshape(40,59); out=target_family_state(x,self.groups)
        self.assertEqual(out["family_scores"].shape,(7,40)); self.assertEqual(len(out["family_top5"]),7)
        self.assertEqual(len(out["consensus_top5"]),5); self.assertEqual(len(out["equal_family_top5"]),5)
        self.assertTrue(0<=out["agreement"]<=1)
    def test_05_disagreement_state_uses_prior_window(self):
        a=np.array([.1,.2,.3,.4,.5,.6]); th,st=build_disagreement_state(a,window=3)
        self.assertTrue(np.isnan(th[:3]).all()); self.assertEqual(th[3],np.median(a[:3]))
        self.assertEqual(st[3],int(a[3]<np.median(a[:3])))
    def test_06_hit_count(self):
        self.assertEqual(count_hits(np.array([1,2,3,4,5]),np.array([1,3,5,7,9])),3)
    def test_07_exact_uniform_hypergeom(self):
        p=hypergeom_5of40_pmf(); self.assertAlmostEqual(float(p.sum()),1.0,places=14)
        self.assertAlmostEqual(float(np.dot(np.arange(6),p)),.625,places=14)
    def test_08_exact_tail_monotonic(self):
        self.assertGreaterEqual(exact_uniform_upper_tail(10,20),exact_uniform_upper_tail(20,20))
    def test_09_holm_adjustment(self):
        adj=holm_adjust([.01,.04,.03])
        self.assertAlmostEqual(adj[0],.03); self.assertAlmostEqual(adj[1],.06); self.assertAlmostEqual(adj[2],.06)
    def test_10_future_suffix_not_used(self):
        x=np.random.default_rng(1).normal(size=(140,40,59)); t=120
        before=target_family_state(x[t],self.groups)
        prior=[target_family_state(x[j],self.groups)["agreement"] for j in range(t-100,t)]
        altered=x.copy(); altered[t+1:]=999.
        after=target_family_state(altered[t],self.groups)
        prior2=[target_family_state(altered[j],self.groups)["agreement"] for j in range(t-100,t)]
        self.assertEqual(before["agreement"],after["agreement"])
        self.assertTrue(np.array_equal(before["consensus_top5"],after["consensus_top5"]))
        self.assertEqual(np.median(prior),np.median(prior2))
    def test_11_family_mapping_rejects_unknown_feature(self):
        bad=dict(self.mapping); bad["not_a_feature"]="residual_surprise"
        with self.assertRaises(ValueError): build_family_groups(self.names,bad)
    def test_12_invalid_matrix_rejected(self):
        with self.assertRaises(ValueError): target_family_state(np.zeros((39,59)),self.groups)
if __name__=="__main__": unittest.main()
