#!/usr/bin/env python3
"""Synthetic regression tests for the Q89 archive-aligned incremental aggregator."""
from __future__ import annotations
import hashlib
import unittest
from pathlib import Path
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
        counts={"number_hits_top5":251,"number_hits_top10":502,"number_hits_top20":1004,
            "all5_top5":1,"all5_top10":2,"all5_top20":3,"rank_sum":20100}
        metrics=delta.metrics_from_counts(counts,100)
        self.assertAlmostEqual(metrics["mean_number_hits_top5"],0.502)
        self.assertAlmostEqual(metrics["mean_number_hits_top10"],1.004)
        self.assertAlmostEqual(metrics["mean_number_hits_top20"],2.008)
        self.assertAlmostEqual(metrics["mean_rank_of_actual_numbers"],40.2)

    def test_git_blob_sha1_uses_nul_header(self):
        data=b"abc"
        expected=hashlib.sha1(b"blob 3\0abc").hexdigest()
        self.assertEqual(delta.git_blob_sha1(data),expected)

if __name__=="__main__":
    unittest.main()
