#!/usr/bin/env python3
from __future__ import annotations
import random,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry
import sonar_q141_formula_size_trend as size_trend
class Q141FormulaSizeTrendTests(unittest.TestCase):
    def test_exact_canonical_mass_counts(self):
        self.assertEqual([size_trend.canonical_mass_count(k) for k in size_trend.MASSES],size_trend.EXPECTED_COUNTS)
        self.assertEqual(sum(size_trend.EXPECTED_COUNTS),9808263)
    def test_sample_is_deterministic_balanced_and_globally_unique(self):
        first=size_trend.sample_formulas_by_mass(); second=size_trend.sample_formulas_by_mass()
        self.assertEqual({k:[f["formula_id"] for f in v] for k,v in first.items()},{k:[f["formula_id"] for f in v] for k,v in second.items()})
        self.assertEqual(len(first[1]),25)
        for k in range(2,11): self.assertEqual(len(first[k]),120)
        ids=[f["formula_id"] for values in first.values() for f in values]
        self.assertEqual(len(ids),1105); self.assertEqual(len(set(ids)),1105)
        for mass,formulas in first.items():
            for f in formulas:
                self.assertEqual(sum(w for _,w in f["signature"]),mass)
                self.assertEqual(f["primitive_mass"],mass)
                self.assertEqual(f["formula_id"],registry.canonical_formula_id(f["signature"]))
    def test_alias_equivalence_and_distinct_weighted_functions(self):
        a,sa=registry.canonicalize_formula((0,)); b,sb=registry.canonicalize_formula((0,25))
        self.assertEqual(a,b); self.assertEqual(sa,1); self.assertEqual(sb,2)
        self.assertEqual(size_trend.make_signature(2,0,()),a)
        self.assertNotEqual(size_trend.make_signature(1,0,(2,)),size_trend.make_signature(2,0,(2,)))
    def test_future_suffix_invariance_for_formula_scores(self):
        rng=random.Random(14120261113); draws=[tuple(sorted(rng.sample(range(40),5))) for _ in range(100)]; target=70
        prefix_a,pos_a=base.build_prefix_arrays(draws)
        pair_counts=np.zeros((40,40),dtype=np.int32); occurrences=[[] for _ in range(40)]
        for i,draw in enumerate(draws[:target]):
            for v in draw: occurrences[v].append(i)
            for a in range(5):
                for b in range(a+1,5): pair_counts[draw[a],draw[b]]+=1; pair_counts[draw[b],draw[a]]+=1
        mutated=list(draws[:target])+[tuple(sorted(rng.sample(range(40),5))) for _ in range(len(draws)-target)]
        prefix_b,pos_b=base.build_prefix_arrays(mutated)
        fa=base.feature_matrix(target,draws,prefix_a,pos_a,pair_counts,occurrences)
        fb=base.feature_matrix(target,mutated,prefix_b,pos_b,pair_counts,occurrences)
        za=base.zscore_columns(fa); zb=base.zscore_columns(fb); formula=size_trend.sample_formulas_by_mass()[7][0]
        sa=registry.canonical_scores(za,formula["signature"],1); sb=registry.canonical_scores(zb,formula["signature"],1)
        self.assertTrue(np.array_equal(fa,fb)); self.assertTrue(np.array_equal(sa,sb))
        self.assertTrue(np.array_equal(base.rank_scores(sa),base.rank_scores(sb)))
    def test_complexity_slope(self):
        self.assertAlmostEqual(size_trend.slope_by_mass(list(range(1,11))),1.0)
        self.assertAlmostEqual(size_trend.slope_by_mass([3.0]*10),0.0)
        self.assertLess(size_trend.slope_by_mass(list(range(10,0,-1))),0.0)
    def test_block_signflip_reproducible_and_directional(self):
        pos=np.linspace(.001,.02,200); neg=-pos
        p1=size_trend.one_sided_block_signflip_p(pos,14120261113)
        p2=size_trend.one_sided_block_signflip_p(pos,14120261113)
        pn=size_trend.one_sided_block_signflip_p(neg,14120261113)
        self.assertEqual(p1,p2); self.assertLess(p1,.05); self.assertGreater(pn,.5)
if __name__=="__main__": unittest.main(verbosity=2)
