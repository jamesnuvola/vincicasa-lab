#!/usr/bin/env python3
"""Unit and source-integrity tests for Q141-D1."""
import importlib.util
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts"/"sonar_q141_d1_standardized_family_advantage.py"
SPEC=importlib.util.spec_from_file_location("q141_d1",SCRIPT)
D1=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D1)

def make_row(hits,ranks=None):
    return {"hits":list(hits),"ranks":list(ranks or [20.0]*6)}

class TestQ141D1(unittest.TestCase):
    def test_pinned_source_and_split_integrity(self):
        rows=D1.load_source()
        self.assertEqual(len(rows),3354)
        self.assertEqual({k:sum(r["split"]==k for r in rows) for k in D1.SPLITS},D1.SPLITS)

    def test_warmup_does_not_select_a_family(self):
        rows=[make_row([1,0,2,1,0,1]) for _ in range(101)]
        self.assertIsNone(D1.select_family(rows,99)[0])

    def test_common_target_shift_does_not_change_standardized_scores(self):
        rows=[make_row([0,1,2,0,3,1],[20,19,21,22,18,23]) for _ in range(100)]
        shifted=[make_row([x+2 for x in r["hits"]],r["ranks"]) for r in rows]
        a=D1.standardized_scores(rows)[0]
        b=D1.standardized_scores(shifted)[0]
        for x,y in zip(a,b): self.assertAlmostEqual(x,y,places=12)

    def test_future_suffix_cannot_change_current_selection(self):
        rows=[make_row([(i+j*2)%6 for j in range(6)],[20+j for j in range(6)]) for i in range(101)]
        original=D1.select_family(rows,100)[0]
        mutated=[dict(r) for r in rows]
        mutated[100]=make_row([5,4,3,2,1,0],[1,2,3,4,5,6])
        self.assertEqual(original,D1.select_family(mutated,100)[0])

    def test_rank_tie_break(self):
        rows=[make_row([1,1,1,1,1,1],[20,18,19,22,21,23]) for _ in range(100)]
        self.assertEqual(D1.select_family(rows,100)[0],1)

    def test_lexical_tie_break(self):
        rows=[make_row([1,1,1,1,1,1],[20]*6) for _ in range(100)]
        self.assertEqual(D1.select_family(rows,100)[0],0)

    def test_holm_adjustment(self):
        self.assertEqual(D1.holm([0.03,0.04]),[0.06,0.06])

    def test_rng_is_deterministic(self):
        a=D1.xorshift32(12345); b=D1.xorshift32(12345)
        self.assertEqual([a() for _ in range(10)],[b() for _ in range(10)])

    def test_full_prediction_replay(self):
        rows=[make_row([(i+j)%6 for j in range(6)],[20+j for j in range(6)]) for i in range(150)]
        self.assertEqual(D1.build_predictions(rows),D1.build_predictions(rows))

if __name__=="__main__": unittest.main(verbosity=2)
