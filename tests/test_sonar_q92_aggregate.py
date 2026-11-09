#!/usr/bin/env python3
"""Synthetic regression tests for Q92 aggregation primitives; no historical outcomes are read."""
from __future__ import annotations
import csv
import tempfile
import unittest
from unittest import mock
from pathlib import Path
import numpy as np
import aggregate_sonar_q92_shards as q92agg
import sonar_q92_common as q92

class Q92AggregateTests(unittest.TestCase):
    def test_formula_id_roundtrip_for_ten_and_nine_feature_control(self):
        ten=q92.formula_id(q92.formula_unrank(12345))
        self.assertEqual(q92agg.parse_formula_id(ten,"P10_",10),q92.formula_unrank(12345))
        nine="P9_00_01_02_03_04_05_06_07_08"
        self.assertEqual(q92agg.parse_formula_id(nine,"P9_",9),tuple(range(9)))
        with self.assertRaises(SystemExit):
            q92agg.parse_formula_id("P10_00_00_01_02_03_04_05_06_07","P10_",10)

    def test_global_holm_stepdown_small_family(self):
        values=np.asarray([0.01,0.04,0.03],dtype=np.float64)
        order=np.argsort(values,kind="stable")
        sorted_adjusted=np.maximum.accumulate((len(values)-np.arange(len(values)))*values[order])
        np.minimum(sorted_adjusted,1.0,out=sorted_adjusted)
        adjusted=np.empty_like(values)
        adjusted[order]=sorted_adjusted
        self.assertTrue(np.allclose(adjusted,[0.03,0.06,0.06],atol=1e-12))

    def test_discovery_top100_and_validation_selection_are_deterministic(self):
        formulas=[q92.formula_id(q92.formula_unrank(index)) for index in range(100)]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"metrics.csv"
            fields=["split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_rank_of_actual_numbers"]
            with path.open("w",newline="",encoding="utf-8") as handle:
                writer=csv.DictWriter(handle,fieldnames=fields)
                writer.writeheader()
                for index,fid in enumerate(formulas):
                    writer.writerow({"split":"discovery","formula_id":fid,"feature_count":10,"features":"f"+str(index),"targets":2012,
                        "mean_number_hits_top5":1.0-index/1000.0,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,
                        "mean_rank_of_actual_numbers":20.0+index/100.0})
                    writer.writerow({"split":"validation","formula_id":fid,"feature_count":10,"features":"f"+str(index),"targets":670,
                        "mean_number_hits_top5":1.0-(99-index)/1000.0,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,
                        "mean_rank_of_actual_numbers":20.0+(99-index)/100.0})
            shortlist=q92agg.discovery_top100([path],prefix="P10_")
            self.assertEqual(len(shortlist),100)
            self.assertEqual(shortlist[0]["formula_id"],formulas[0])
            selected,enriched=q92agg.validation_select([path],shortlist,prefix="P10_")
            self.assertEqual(len(enriched),100)
            self.assertEqual(selected["formula_id"],formulas[99])
            self.assertEqual(selected["validation_selection_rank"],1)

    def test_bootstrap_and_block_signflip_replay_fixed_seeds(self):
        values=[1,0,-1,2,0,-2,1,0,-1,1,0,-1,2,0]
        ci1=q92agg.bootstrap_ci(values,replicates=500,block_length=7,seed=920027)
        ci2=q92agg.bootstrap_ci(values,replicates=500,block_length=7,seed=920027)
        p1=q92agg.block_signflip_p(values,replicates=500,block_length=7,seed=920028)
        p2=q92agg.block_signflip_p(values,replicates=500,block_length=7,seed=920028)
        self.assertEqual(ci1,ci2)
        self.assertEqual(p1,p2)
        self.assertTrue(0<=p1<=1)

    def test_q89_refresh_control_gate_fails_closed_when_outputs_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with mock.patch.object(q92agg,"Q89_REFRESH_REPORT_PATH",root/"missing-report.json"), \
                 mock.patch.object(q92agg,"Q89_REFRESH_MANIFEST_PATH",root/"missing-manifest.json"), \
                 mock.patch.object(q92agg,"Q89_REFRESH_SELECTION_PATH",root/"missing-selection.json"), \
                 mock.patch.object(q92agg,"Q89_REFRESH_PAIRED_LEDGER_PATH",root/"missing-ledger.csv"):
                with self.assertRaises(SystemExit):
                    q92agg.validate_q89_refresh_control(["2017-07-17"],[[1,2,3,4,5]],"sha")

if __name__=="__main__":
    unittest.main()
