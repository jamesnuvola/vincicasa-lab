#!/usr/bin/env python3
"""Synthetic regressions for Q92 global Holm, candidate freeze and paired inference."""
from __future__ import annotations
import unittest
import numpy as np
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q92_aggregate_common as q92a

class Q92AggregateCommonTests(unittest.TestCase):
    def test_formula_id_parser_is_canonical_and_fail_closed(self):
        columns=tuple(range(10))
        fid="P10_"+"_".join(f"{value:02d}" for value in columns)
        self.assertEqual(q92a.parse_formula_id(fid),columns)
        for invalid in ("P9_00_01_02_03_04_05_06_07_08","P10_00_01_02_03_04_05_06_07_08_08","P10_00_01_02_03_04_05_06_07_08_27"):
            with self.assertRaises(ValueError):
                q92a.parse_formula_id(invalid)

    def test_holm_matches_reference_across_chunk_boundaries(self):
        raw=np.asarray([0.01,0.04,0.03,0.001,0.2,0.05,0.005],dtype=np.float64)
        expected=np.empty_like(raw)
        order=np.argsort(raw,kind="stable")
        carry=0.0
        for rank,index in enumerate(order):
            carry=max(carry,(len(raw)-rank)*float(raw[index]))
            expected[index]=min(1.0,carry)
        actual=q92a.holm_adjust_in_place(raw.copy(),chunk_size=2)
        self.assertTrue(np.allclose(actual,expected,rtol=0,atol=1e-15))
        self.assertTrue(np.all(actual>=0.0))
        self.assertTrue(np.all(actual<=1.0))

    def test_holm_known_family(self):
        raw=np.asarray([0.01,0.04,0.03],dtype=np.float64)
        adjusted=q92a.holm_adjust_in_place(raw,chunk_size=1)
        self.assertTrue(np.allclose(adjusted,[0.03,0.06,0.06],rtol=0,atol=1e-15))

    def test_discovery_top_k_and_validation_freeze_tie_breaks(self):
        rows=[
            {"formula_id":"P10_02","mean_number_hits_top5":0.2,"mean_rank_of_actual_numbers":20.0,"validation_mean_number_hits_top5":0.3,"validation_mean_rank_of_actual_numbers":19.0},
            {"formula_id":"P10_01","mean_number_hits_top5":0.2,"mean_rank_of_actual_numbers":19.0,"validation_mean_number_hits_top5":0.3,"validation_mean_rank_of_actual_numbers":19.0},
            {"formula_id":"P10_00","mean_number_hits_top5":0.1,"mean_rank_of_actual_numbers":18.0,"validation_mean_number_hits_top5":0.4,"validation_mean_rank_of_actual_numbers":22.0},
        ]
        top=q92a.discovery_top_k(rows,k=2)
        self.assertEqual([row["formula_id"] for row in top],["P10_01","P10_02"])
        selected,ordered=q92a.validation_freeze(top)
        self.assertEqual(selected["formula_id"],"P10_01")
        self.assertEqual([row["formula_id"] for row in ordered],["P10_01","P10_02"])

    def test_paired_inference_replays_fixed_seeds_and_holm_family(self):
        endpoints={
            "top5":np.full(14,0.2,dtype=np.float64),
            "top10":np.zeros(14,dtype=np.float64),
            "top20":np.zeros(14,dtype=np.float64),
            "mean_rank":np.full(14,-0.1,dtype=np.float64),
        }
        first=q92a.paired_endpoint_inference(endpoints,replicates=100,block_length=7)
        second=q92a.paired_endpoint_inference(endpoints,replicates=100,block_length=7)
        self.assertEqual(first,second)
        self.assertEqual(first["multiple_testing"]["family_size"],4)
        self.assertEqual(first["primary_decision"],"NO_SIGNIFICANT_GAIN")
        self.assertEqual(first["endpoints"]["top5"]["n_targets"],14)
        self.assertAlmostEqual(first["endpoints"]["top5"]["bootstrap_ci_95_low"],0.2,places=12)
        self.assertAlmostEqual(first["endpoints"]["top5"]["bootstrap_ci_95_high"],0.2,places=12)
        self.assertGreaterEqual(first["endpoints"]["top5"]["signflip_p_holm"],first["endpoints"]["top5"]["signflip_p_raw"])

    def test_zero_deltas_have_null_ci_and_pvalue_one(self):
        values=np.zeros(28,dtype=np.float64)
        low,high=q92a.circular_moving_block_bootstrap_ci(values,replicates=100,block_length=7)
        p=q92a.circular_block_signflip_pvalue(values,replicates=100,block_length=7)
        self.assertEqual((low,high),(0.0,0.0))
        self.assertEqual(p,1.0)

if __name__=="__main__":
    unittest.main()
