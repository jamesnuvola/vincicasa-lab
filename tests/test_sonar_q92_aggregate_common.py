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
import aggregate_sonar_q92_ten_feature as q92agg
import hashlib
import tempfile
from unittest.mock import patch
import sonar_q92_common as q92
import sonar_q92_null_calibration as q92null

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

    def test_primary_decision_requires_registered_minimum_practical_effect(self):
        small={
            "top5":np.full(140,0.004,dtype=np.float64),
            "top10":np.zeros(140,dtype=np.float64),
            "top20":np.zeros(140,dtype=np.float64),
            "mean_rank":np.zeros(140,dtype=np.float64),
        }
        below=q92a.paired_endpoint_inference(small,replicates=1000,block_length=7)
        self.assertLess(below["endpoints"]["top5"]["signflip_p_holm"],0.05)
        self.assertGreater(below["endpoints"]["top5"]["bootstrap_ci_95_low"],0.0)
        self.assertEqual(below["primary_decision"],"NO_SIGNIFICANT_GAIN")
        self.assertEqual(below["minimum_practical_effect"]["absolute_delta_threshold"],0.005)
        large={key:values.copy() for key,values in small.items()}
        large["top5"]=np.full(140,0.006,dtype=np.float64)
        above=q92a.paired_endpoint_inference(large,replicates=1000,block_length=7)
        self.assertLess(above["endpoints"]["top5"]["signflip_p_holm"],0.05)
        self.assertGreater(above["endpoints"]["top5"]["bootstrap_ci_95_low"],0.0)
        self.assertEqual(above["primary_decision"],"SIGNIFICANT_POSITIVE_GAIN")

    def test_zero_deltas_have_null_ci_and_pvalue_one(self):
        values=np.zeros(28,dtype=np.float64)
        low,high=q92a.circular_moving_block_bootstrap_ci(values,replicates=100,block_length=7)
        p=q92a.circular_block_signflip_pvalue(values,replicates=100,block_length=7)
        self.assertEqual((low,high),(0.0,0.0))
        self.assertEqual(p,1.0)

    def test_compact_metric_count_roundtrip_preserves_raw_summary(self):
        targets=10
        raw={"mean_number_hits_top5":6/(5*targets),"mean_number_hits_top10":12/(5*targets),"mean_number_hits_top20":20/(5*targets),
             "all5_top5_rate":1/targets,"all5_top10_rate":2/targets,"all5_top20_rate":3/targets,"mean_rank_of_actual_numbers":1000/(5*targets)}
        compact=q92.compact_counts_from_raw_metrics(raw,targets)
        self.assertEqual(compact,{"number_hits_top5":6,"number_hits_top10":12,"number_hits_top20":20,"all5_top5":1,"all5_top10":2,"all5_top20":3,"rank_sum":1000})
        summary=q92.metric_summary_from_compact_counts(compact,targets)
        for field,value in raw.items():self.assertAlmostEqual(summary[field],value,places=15)
        self.assertEqual(summary["p_top5_exact_hypergeom_sum"],q92null.exact_upper_tail_pvalue(6,targets,5))
        self.assertEqual(summary["p_top10_exact_hypergeom_sum"],q92null.exact_upper_tail_pvalue(12,targets,10))
        self.assertEqual(summary["p_top20_exact_hypergeom_sum"],q92null.exact_upper_tail_pvalue(20,targets,20))

    def test_compact_metric_count_domains_fail_closed(self):
        compact={"number_hits_top5":51,"number_hits_top10":12,"number_hits_top20":20,"all5_top5":1,"all5_top10":2,"all5_top20":3,"rank_sum":1000}
        with self.assertRaises(ValueError):q92.metric_summary_from_compact_counts(compact,10)
        compact["number_hits_top5"]=6;compact["rank_sum"]=49
        with self.assertRaises(ValueError):q92.metric_summary_from_compact_counts(compact,10)
        compact["rank_sum"]=1000;compact["all5_top20"]=11
        with self.assertRaises(ValueError):q92.metric_summary_from_compact_counts(compact,10)

    def test_source_code_hash_manifest_is_deterministic(self):
        root=Path(__file__).resolve().parents[1]
        first=q92.source_code_hashes(root);second=q92.source_code_hashes(root)
        self.assertEqual(first,second);self.assertEqual(tuple(first),q92.SOURCE_CODE_HASH_PATHS)
        self.assertTrue(all(len(value)==64 and all(character in "0123456789abcdef" for character in value) for value in first.values()))


    def _load_archive_with_fixture_draws(self, draws):
        payload=b"Q92 canonical archive tuple regression fixture\n"
        dates=["2017-07-17","2026-11-08"]
        with tempfile.TemporaryDirectory() as temporary:
            archive=Path(temporary)/"storico_daily.csv"
            archive.write_bytes(payload)
            with patch.object(q92agg,"ARCHIVE",archive), \
                 patch.object(q92agg,"EXPECTED_ARCHIVE_SHA1",q92agg.git_blob_sha1(payload)), \
                 patch.object(q92agg,"EXPECTED_ARCHIVE_SHA256",hashlib.sha256(payload).hexdigest()), \
                 patch.object(q92agg,"EXPECTED_ARCHIVE_COUNT",2), \
                 patch.object(q92agg,"EXPECTED_ARCHIVE_LAST_DATE","2026-11-08"), \
                 patch.object(q92agg.q80,"load_archive",return_value=(dates,draws)):
                return q92agg.load_archive()

    def test_archive_quintet_validation_accepts_tuple_and_list_containers(self):
        draws=[(1,2,3,4,5),[3,7,10,16,27]]
        dates,loaded,_,_=self._load_archive_with_fixture_draws(draws)
        self.assertEqual(dates,["2017-07-17","2026-11-08"])
        self.assertEqual(loaded,draws)

    def test_archive_quintet_validation_rejects_noncanonical_values(self):
        invalid_draw_sets=[
            [(1,3,2,4,5),(3,7,10,16,27)],
            [(1,2,2,4,5),(3,7,10,16,27)],
            [(0,2,3,4,5),(3,7,10,16,27)],
            [(1,2,3,4),(3,7,10,16,27)],
            [(1,2,3,4,41),(3,7,10,16,27)],
        ]
        for draws in invalid_draw_sets:
            with self.subTest(draws=draws):
                with self.assertRaises(SystemExit):
                    self._load_archive_with_fixture_draws(draws)


    def test_selected_formula_global_holm_values_use_shard_major_family_order(self):
        adjusted=np.arange(108,dtype=np.float64)/108.0
        observed=q92a.selected_formula_holm_pvalues(
            adjusted,formula_rank=6,formula_count=12,split_index=1,shard_count=3)
        self.assertEqual(observed,{
            "top5":54/108,
            "top10":55/108,
            "top20":56/108,
        })
        with self.assertRaises(ValueError):
            q92a.selected_formula_holm_pvalues(adjusted[:-1],6,12,1,shard_count=3)
        with self.assertRaises(ValueError):
            q92a.selected_formula_holm_pvalues(adjusted,12,12,1,shard_count=3)
        with self.assertRaises(ValueError):
            q92a.selected_formula_holm_pvalues(adjusted,6,12,3,shard_count=3)
        with self.assertRaises(ValueError):
            q92a.selected_formula_holm_pvalues(adjusted,6,12,1,shard_count=5)

    def test_absolute_uniform_baseline_requires_both_lift_and_global_holm(self):
        passed=q92a.uniform_baseline_evidence(0.14,0.01,0.04,baseline=0.125,alpha=0.05,targets=670)
        self.assertEqual(passed["status"],"ABSOLUTE_LIFT_SUPPORTED")
        self.assertTrue(passed["absolute_baseline_pass"])
        self.assertAlmostEqual(passed["absolute_lift"],0.015)
        below=q92a.uniform_baseline_evidence(0.124,0.001,0.001,baseline=0.125,alpha=0.05,targets=670)
        self.assertEqual(below["status"],"NOT_DEMONSTRATED")
        self.assertFalse(below["absolute_baseline_pass"])
        uncorrected=q92a.uniform_baseline_evidence(0.14,0.001,0.05,baseline=0.125,alpha=0.05,targets=670)
        self.assertEqual(uncorrected["status"],"NOT_DEMONSTRATED")
        self.assertFalse(uncorrected["absolute_baseline_pass"])

if __name__=="__main__":
    unittest.main()
