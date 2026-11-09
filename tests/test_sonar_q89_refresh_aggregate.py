#!/usr/bin/env python3
"""Synthetic regression tests for the Q89 archive-aligned incremental aggregator."""
from __future__ import annotations
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import aggregate_sonar_q89_refresh_delta as delta

class Q89RefreshAggregatorTests(unittest.TestCase):
    def test_exact_split_count_transition(self):
        old={name:100 for name in delta.METRIC_NAMES}
        d2011={name:2 for name in delta.METRIC_NAMES}
        d2681={name:3 for name in delta.METRIC_NAMES}
        d3351={name:4 for name in delta.METRIC_NAMES}
        counts={2011:d2011,2681:d2681,3351:d3351}
        self.assertEqual(delta.adjust_split_counts(old,counts,"discovery"),{name:102 for name in delta.METRIC_NAMES})
        self.assertEqual(delta.adjust_split_counts(old,counts,"validation"),{name:101 for name in delta.METRIC_NAMES})
        self.assertEqual(delta.adjust_split_counts(old,counts,"blind_oos"),{name:101 for name in delta.METRIC_NAMES})
        with self.assertRaises(ValueError):
            delta.adjust_split_counts(old,counts,"unknown")

    def test_integer_reconstruction_is_exact_and_fail_closed(self):
        self.assertEqual(delta.integer_from_mean("0.1",50,"fixture"),5)
        self.assertEqual(delta.integer_from_mean("20.5",10,"fixture"),205)
        with self.assertRaises(SystemExit):
            delta.integer_from_mean("0.101",50,"fixture")

    def test_global_holm_step_down_known_family(self):
        adjusted=delta.holm_adjust_global([0.01,0.04,0.03])
        self.assertEqual(adjusted.tolist(),[0.03,0.06,0.06])
        self.assertEqual(delta.holm_adjust_global([0.5,0.7]).tolist(),[1.0,1.0])

    def test_metric_denominators_and_bounds(self):
        counts={"number_hits_top5":251,"number_hits_top10":125,"number_hits_top20":250,
            "all5_top5":1,"all5_top10":2,"all5_top20":3,"rank_sum":10050}
        metrics=delta.metrics_from_counts(counts,100)
        self.assertAlmostEqual(metrics["mean_number_hits_top5"],0.502)
        self.assertAlmostEqual(metrics["mean_number_hits_top10"],0.25)
        self.assertAlmostEqual(metrics["mean_number_hits_top20"],0.5)
        self.assertAlmostEqual(metrics["mean_rank_of_actual_numbers"],20.1)
        for name in ("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate"):
            self.assertTrue(0.0<=metrics[name]<=1.0)
        self.assertTrue(1.0<=metrics["mean_rank_of_actual_numbers"]<=40.0)
    def test_rank_actual_formula_uses_stable_lower_number_tie_break(self):
        standardized=np.zeros((40,27),dtype=np.float64)
        standardized[0,0]=1.0
        standardized[1,0]=1.0
        standardized[2,0]=0.5
        ranks=delta.rank_actual_for_formula(standardized,tuple(range(9)),[0,1,2])
        self.assertEqual(ranks,[1,2,3])

    def test_selected_candidate_blind_ledger_uses_strict_prior_cutoffs(self):
        draws=[[1,2,3,4,5] for _ in range(10)]
        dates=[f"2026-01-{day:02d}" for day in range(1,11)]
        stack=np.zeros((10,40,27),dtype=np.float64)
        stack[:,:,0]=np.arange(40,dtype=np.float64)[None,:]
        selection={"Q89_candidate":{"formula_id":"P9_00_01_02_03_04_05_06_07_08"}}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"paired.csv"
            with patch.object(delta.q80,"MIN_HISTORY",0), patch.object(delta,"EXPECTED_BLIND_TARGETS",2), patch.object(delta.q81,"build_feature_stack",return_value=stack), patch.object(delta,"PAIRED_LEDGER_PATH",path):
                rows=delta.paired_blind_ledger(selection,dates,draws)
            self.assertEqual(len(rows),2)
            self.assertEqual([row["target_date"] for row in rows],dates[8:])
            self.assertEqual([row["cutoff_date"] for row in rows],dates[7:9])
            self.assertEqual([int(row["prior_draws"]) for row in rows],[8,9])
            for row in rows:
                self.assertEqual(json.loads(row["Q89_actual_number_ranks"]),[40,39,38,37,36])
                self.assertEqual(row["Q89_number_hits_top5"],0)
                self.assertEqual(row["Q89_number_hits_top10"],0)
                self.assertEqual(row["Q89_number_hits_top20"],0)
                self.assertEqual(row["Q89_all5_top5"],0)
                self.assertEqual(row["Q89_all5_top10"],0)
                self.assertEqual(row["Q89_all5_top20"],0)
                self.assertEqual(row["Q89_rank_sum"],190)
            self.assertTrue(path.is_file())

    def test_git_blob_sha1_uses_nul_header(self):
        data=b"abc"
        expected=hashlib.sha1(b"blob 3\0abc").hexdigest()
        self.assertEqual(delta.git_blob_sha1(data),expected)

if __name__=="__main__":
    unittest.main()
