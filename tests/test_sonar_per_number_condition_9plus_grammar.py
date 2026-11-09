#!/usr/bin/env python3
"""Acceptance/unit tests for the finite Q89 nine-feature formula universe."""
import itertools
import json
import math
import random
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest.mock import patch
import numpy as np
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_condition_grammar as q80
import sonar_q89_common as q89
import aggregate_sonar_q89_shards as q89agg
import sonar_q89_acceptance as q89accept
import persist_q89_outputs as q89persist

class Q89FormulaUniverseTests(unittest.TestCase):
    def test_aggregator_runtime_constants_are_bound(self):
        self.assertEqual(q89agg.MIN_HISTORY,q80.MIN_HISTORY)
        self.assertEqual(q89agg.FEATURE_COUNT,q89.FEATURE_COUNT)
        self.assertEqual(q89agg.FORMULA_SIZE,q89.FORMULA_SIZE)

    def test_acceptance_csv_reader_materializes_rows_before_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"tiny.csv"
            path.write_text("a,b\n1,2\n3,4\n",encoding="utf-8")
            fields,rows=q89accept.load_csv(path)
            self.assertEqual(fields,["a","b"])
            self.assertEqual(rows,[{"a":"1","b":"2"},{"a":"3","b":"4"}])

    def test_paired_candidate_metric_blocks_replay(self):
        paired=[
            {"Q89_number_hits_top5":1,"Q89_number_hits_top10":2,"Q89_number_hits_top20":3,"Q89_rank_sum":50,
             "Q88_number_hits_top5":2,"Q88_number_hits_top10":3,"Q88_number_hits_top20":4,"Q88_rank_sum":60},
            {"Q89_number_hits_top5":2,"Q89_number_hits_top10":3,"Q89_number_hits_top20":4,"Q89_rank_sum":70,
             "Q88_number_hits_top5":1,"Q88_number_hits_top10":2,"Q88_number_hits_top20":3,"Q88_rank_sum":80}
        ]
        inference={}
        for family,prefix in q89accept.PAIRED_METRIC_BLOCKS:
            inference[family]={}
            for k in (5,10,20):
                inference[family][f"mean_number_hits_top{k}"]=sum(row[f"{prefix}_number_hits_top{k}"] for row in paired)/(5*len(paired))
            inference[family]["mean_rank_of_actual_numbers"]=sum(row[f"{prefix}_rank_sum"] for row in paired)/(5*len(paired))
        self.assertEqual(q89accept.validate_paired_metric_replay(inference,paired),[])
        inference["Q89_candidate_blind_metrics"]["mean_number_hits_top5"]=0.25
        self.assertIn("Q89 blind candidate metric replay mismatch Q89_candidate_blind_metrics Top5",
                      q89accept.validate_paired_metric_replay(inference,paired))

    def test_paired_blind_ledger_uses_separate_q89_and_q88_ranks(self):
        matrix=np.zeros((40,27),dtype=np.float64)
        numbers=np.arange(40,dtype=np.float64)
        matrix[:,0:8]=-numbers[:,None]
        matrix[:,8]=1000.0*numbers
        scored=3401-q80.MIN_HISTORY
        standardized_stack=[matrix]*scored
        dates=[(date(2017,7,17)+timedelta(days=index)).isoformat() for index in range(3401)]
        draws=[[1,2,3,4,5] for _ in range(3401)]
        selection={
            "Q89_candidate":{"formula_id":"P9_00_01_02_03_04_05_06_07_08"},
            "Q88_control":{"formula_id":"P8_00_01_02_03_04_05_06_07"}
        }
        with tempfile.TemporaryDirectory() as directory:
            ledger_path=Path(directory)/"paired.csv"
            with patch("aggregate_sonar_q89_shards.q81.build_feature_stack",return_value=standardized_stack), \
                 patch.object(q89agg,"PAIRED_LEDGER_PATH",ledger_path):
                rows,differences=q89agg.paired_blind_ledger(selection,dates,draws)
        self.assertEqual(len(rows),670)
        first=rows[0]
        q89_ranks=json.loads(first["Q89_actual_number_ranks"])
        q88_ranks=json.loads(first["Q88_actual_number_ranks"])
        self.assertEqual(q89_ranks,[40,39,38,37,36])
        self.assertEqual(q88_ranks,[1,2,3,4,5])
        self.assertEqual(first["Q89_number_hits_top5"],0)
        self.assertEqual(first["Q88_number_hits_top5"],5)
        self.assertEqual(first["paired_delta_number_hits_top5"],-5)
        self.assertEqual(differences["top5"][0],-5)

    def test_queue_status_append_guard_accepts_only_validated_q89_append(self):
        old={
            "generated_at_utc":"2026-11-08T20:55:29+00:00","project":"VinciCasa SONAR",
            "queue_status":"QUEUE_VALID","overall_cycle_status":"INCOMPLETE","task_count":1,
            "complete_count":1,"ready_count":0,"active_next_task":None,"blocking_tasks":[],"next_action":None,
            "tasks":[{"id":"Q00","status":"COMPLETE","missing_evidence":[],"validation_errors":[]}]
        }
        new=json.loads(json.dumps(old))
        new["generated_at_utc"]="2026-11-09T00:02:17+00:00"
        new["task_count"]=2
        new["tasks"].append({"id":"Q89","status":"VALIDATED_PENDING_HUMAN_REVIEW","depends_on":["Q00","Q88"],
                             "missing_evidence":[],"validation_errors":[]})
        ok,reason=q89persist.validate_queue_status_append(json.dumps(old).encode(),json.dumps(new).encode(),
                                                          q89persist.QUEUE_STATUS_EXPECTED_BLOB_SHA)
        self.assertTrue(ok,reason)
        changed=json.loads(json.dumps(new))
        changed["tasks"][0]["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
        self.assertFalse(q89persist.validate_queue_status_append(json.dumps(old).encode(),json.dumps(changed).encode(),
                                                                 q89persist.QUEUE_STATUS_EXPECTED_BLOB_SHA)[0])
        invalid_q89=json.loads(json.dumps(new))
        invalid_q89["tasks"][-1]["status"]="COMPLETE"
        self.assertFalse(q89persist.validate_queue_status_append(json.dumps(old).encode(),json.dumps(invalid_q89).encode(),
                                                                 q89persist.QUEUE_STATUS_EXPECTED_BLOB_SHA)[0])
        self.assertFalse(q89persist.validate_queue_status_append(json.dumps(old).encode(),json.dumps(new).encode(),
                                                                 "unexpected-blob-sha")[0])

    def test_exact_formula_count_and_endpoints(self):
        self.assertEqual(q89.TOTAL_FORMULA_COUNT,4_686_825)
        self.assertEqual(q89.SHARD_COUNT,15)
        self.assertEqual(q89.SHARD_SIZE,312_455)
        self.assertEqual(q89.formula_id(q89.formula_unrank(0)),"P9_00_01_02_03_04_05_06_07_08")
        self.assertEqual(q89.formula_id(q89.formula_unrank(q89.TOTAL_FORMULA_COUNT-1)),"P9_18_19_20_21_22_23_24_25_26")

    def test_rank_unrank_round_trip(self):
        ranks=[0,1,100,312_454,312_455,4_374_370,q89.TOTAL_FORMULA_COUNT-1]
        rng=random.Random(890027)
        ranks.extend(rng.randrange(q89.TOTAL_FORMULA_COUNT) for _ in range(1000))
        for value in ranks:
            columns=q89.formula_unrank(value)
            self.assertEqual(q89.formula_rank(columns),value)
            self.assertEqual(q89.formula_unrank(q89.formula_rank(columns)),columns)

    def test_shards_are_contiguous_and_cover_universe(self):
        cursor=0
        for shard in range(q89.SHARD_COUNT):
            start,end=q89.shard_bounds(shard)
            self.assertEqual(start,cursor)
            self.assertEqual(end-start,q89.SHARD_SIZE)
            self.assertEqual(q89.formula_rank(q89.formula_unrank(start)),start)
            self.assertEqual(q89.formula_rank(q89.formula_unrank(end-1)),end-1)
            cursor=end
        self.assertEqual(cursor,q89.TOTAL_FORMULA_COUNT)

    def test_successor_matches_lexicographic_rank(self):
        columns=q89.formula_unrank(1000)
        for expected_rank in range(1000,1100):
            self.assertEqual(q89.formula_rank(columns),expected_rank)
            columns=q89.next_formula(columns)
            self.assertIsNotNone(columns)
            self.assertEqual(q89.formula_rank(columns),expected_rank+1)

    def test_formula_slice_has_exact_rank_bounds(self):
        for shard in (0,1,7,14):
            start,end=q89.shard_bounds(shard)
            sample=list(q89.iter_formula_slice(start,min(start+20,end)))
            self.assertEqual(len(sample),min(20,end-start))
            self.assertEqual(q89.formula_rank(sample[0]),start)
            self.assertEqual(q89.formula_rank(sample[-1]),start+len(sample)-1)
            self.assertEqual(sample,list(itertools.islice(itertools.combinations(range(27),9),start,start+len(sample))))

    def test_hypergeometric_null_variance(self):
        targets=670
        for top_k in (5,10,20):
            p=top_k/40
            expected_mean=targets*5*p
            expected_var=targets*5*p*(1-p)*35/39
            self.assertGreater(expected_mean,0)
            self.assertGreater(expected_var,0)
            value=q89.hypergeom_upper_normal_p(int(expected_mean),targets,top_k)
            self.assertGreaterEqual(value,0)
            self.assertLessEqual(value,1)

    def test_holm_adjustment_known_family(self):
        self.assertEqual(q89agg.holm_adjust([0.01,0.04,0.03]),[0.03,0.06,0.06])

    def test_block_bootstrap_and_signflip_replay(self):
        differences=[(index%5)-2 for index in range(670)]
        ci1=q89agg.bootstrap_ci(differences,replicates=300,block_length=7,seed=890027)
        ci2=q89agg.bootstrap_ci(differences,replicates=300,block_length=7,seed=890027)
        self.assertEqual(ci1,ci2)
        self.assertLessEqual(ci1[0],ci1[1])
        p1=q89agg.block_signflip_p(differences,replicates=500,block_length=7,seed=890028)
        p2=q89agg.block_signflip_p(differences,replicates=500,block_length=7,seed=890028)
        self.assertEqual(p1,p2)
        self.assertGreaterEqual(p1,0)
        self.assertLessEqual(p1,1)

if __name__=="__main__":
    unittest.main(verbosity=2)
