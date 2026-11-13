#!/usr/bin/env python3
"""Unit and integrity tests for Q141-D2."""
import importlib.util, unittest
from pathlib import Path
SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"sonar_q141_d2_family_volatility_standardization.py"
SPEC=importlib.util.spec_from_file_location("q141_d2",SCRIPT)
D2=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(D2)

def row(hits,ranks=None):
    return {"hits":list(hits),"hits10":[min(5,x+1) for x in hits],"hits20":[min(5,x+2) for x in hits],
            "ranks":list(ranks or [20.0]*6),"equal":1,"equal10":2,"equal20":3,"equal_rank":20.0,
            "index":0,"offset":0,"date":"2026-01-02","cutoff":"2026-01-01","split":"discovery",
            "c0_family":"frequency_change","c0":1,"c0_10":2,"c0_20":3,"c0_rank":20.0}

class TestQ141D2(unittest.TestCase):
    def test_source_lineage_and_split_integrity(self):
        rows,parent,archive_check=D2.load_source(skip_archive_check=True)
        self.assertEqual(len(rows),3354); self.assertEqual(parent["source"]["eligible_draw_count"],3404)
        self.assertEqual({k:sum(r["split"]==k for r in rows) for k in D2.SPLITS},D2.SPLITS)
        self.assertEqual(archive_check,"NOT_RECHECKED_LOCAL_PARENT_AND_CI_ATTESTED")

    def test_warmup(self):
        rows=[row([1,0,2,1,0,1]) for _ in range(101)]
        self.assertIsNone(D2.d2_select(rows,99))

    def test_family_specific_volatility_penalizes_noisy_family(self):
        hist=[]
        for i in range(100):
            h=[2, 2+(1 if i%2==0 else -1), 1, 1, 1, 1]
            hist.append(row(h,[20,19,21,22,18,23]))
        scores,ranks=D2.d2_scores(hist,100)
        self.assertGreater(scores[0],scores[1])

    def test_common_target_shift_invariance(self):
        hist=[row([0,1,2,0,3,1],[20,19,21,22,18,23]) for _ in range(100)]
        shifted=[row([x+1 for x in r["hits"]],[20,19,21,22,18,23]) for r in hist]
        a=D2.d2_scores(hist,100)[0]; b=D2.d2_scores(shifted,100)[0]
        for x,y in zip(a,b): self.assertAlmostEqual(x,y,places=12)

    def test_future_suffix_invariance(self):
        hist=[row([(i+j*2)%6 for j in range(6)],[20+j for j in range(6)]) for i in range(101)]
        original=D2.d2_select(hist,100)
        mutated=[dict(r) for r in hist]; mutated[100]=row([5,4,3,2,1,0],[1,2,3,4,5,6])
        self.assertEqual(original,D2.d2_select(mutated,100))

    def test_rank_and_lexical_tie_break(self):
        hist=[row([1,1,1,1,1,1],[20,18,19,22,21,23]) for _ in range(100)]
        self.assertEqual(D2.d2_select(hist,100),1)
        hist=[row([1,1,1,1,1,1],[20]*6) for _ in range(100)]
        self.assertEqual(D2.d2_select(hist,100),0)

    def test_holm(self): self.assertEqual(D2.holm([0.01,0.03,0.04]),[0.03,0.06,0.06])

    def test_rng_determinism(self):
        a=D2.xorshift32(123); b=D2.xorshift32(123)
        self.assertEqual([a() for _ in range(20)],[b() for _ in range(20)])

    def test_d1_replay_matches_pinned_d1_result(self):
        rows,_,_=D2.load_source(skip_archive_check=True); preds=D2.build_predictions(rows)
        blind=[p["d1_hits"] for r,p in zip(rows,preds) if r["split"]=="blind_oos"]
        self.assertAlmostEqual(D2.mean(blind),0.6194029850746269,places=12)

    def test_full_replay_is_deterministic(self):
        rows=[row([(i+j)%6 for j in range(6)],[20+j for j in range(6)]) for i in range(150)]
        self.assertEqual(D2.build_predictions(rows),D2.build_predictions(rows))

if __name__=="__main__": unittest.main(verbosity=2)
