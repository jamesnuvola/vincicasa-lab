#!/usr/bin/env python3
"""Synthetic regression tests for the Q89 three-target incremental refresh."""
from __future__ import annotations
import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q89_refresh_delta_shard as delta

class TestQ89RefreshDelta(unittest.TestCase):
    def test_rank_matrix_stable_lower_number_tie_break(self):
        scores=np.asarray([[1.0,2.0],[1.0,0.0],[0.0,2.0]],dtype=np.float64)
        ranks=delta.rank_matrix(scores)
        self.assertEqual(ranks[:,0].tolist(),[1,2,3])
        self.assertEqual(ranks[:,1].tolist(),[1,3,2])

    def test_exact_split_count_adjustment(self):
        old={name:100 for name in delta.METRIC_NAMES}
        d2011={name:2 for name in delta.METRIC_NAMES}
        d2681={name:3 for name in delta.METRIC_NAMES}
        d3351={name:4 for name in delta.METRIC_NAMES}
        adjusted=delta.adjust_split_counts(old,{2011:d2011,2681:d2681,3351:d3351},"discovery")
        self.assertEqual(adjusted,{name:102 for name in delta.METRIC_NAMES})
        adjusted=delta.adjust_split_counts(old,{2011:d2011,2681:d2681,3351:d3351},"validation")
        self.assertEqual(adjusted,{name:101 for name in delta.METRIC_NAMES})
        adjusted=delta.adjust_split_counts(old,{2011:d2011,2681:d2681,3351:d3351},"blind_oos")
        self.assertEqual(adjusted,{name:101 for name in delta.METRIC_NAMES})
        with self.assertRaises(ValueError):
            delta.adjust_split_counts(old,{2011:d2011,2681:d2681,3351:d3351},"unknown")

    def test_main_synthetic_three_target_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/"archive.csv"
            archive.write_text("synthetic archive\n",encoding="utf-8")
            dates=[f"2020-01-{i+1:02d}" for i in range(53)]
            draws=[tuple(((i+j)%40)+1 for j in range(5)) for i in range(53)]
            draws=[tuple(sorted(set(row))) for row in draws]
            for i in range(50,53):
                draws[i]=tuple(range(1+5*(i-50),6+5*(i-50)))
            stack=np.zeros((3,40,27),dtype=np.float64)
            for t in range(3):
                for number in range(40):
                    for feature in range(27):
                        stack[t,number,feature]=number*(feature+1)+t*0.01
            formulas=[tuple(range(0,9)),tuple(range(1,10))]
            def formula_id(columns):
                return "P9_"+"_".join(f"{value:02d}" for value in columns)
            rank_map={formulas[0]:0,formulas[1]:1}
            with ExitStack() as stack_patches:
                stack_patches.enter_context(patch.object(delta,"ARCHIVE",archive))
                stack_patches.enter_context(patch.object(delta,"OUT",root/"reports/sequence_agent"))
                stack_patches.enter_context(patch.object(delta,"SHARD_DIR",root/"reports/sequence_agent/q89_refresh_20261108_delta_shards"))
                stack_patches.enter_context(patch.object(delta,"METRICS",root/"reports/sequence_agent/q89_refresh_20261108_delta_shards/shard_0_delta_metrics.csv.gz"))
                stack_patches.enter_context(patch.object(delta,"REPORT",root/"reports/sequence_agent/q89_refresh_20261108_delta_shards/shard_0_delta_report.json"))
                stack_patches.enter_context(patch.object(delta,"MIN_HISTORY",50))
                stack_patches.enter_context(patch.object(delta,"EXPECTED_DRAW_COUNT",53))
                stack_patches.enter_context(patch.object(delta,"EXPECTED_LAST_DATE",dates[-1]))
                stack_patches.enter_context(patch.object(delta,"EXPECTED_TARGET_COUNT",3))
                stack_patches.enter_context(patch.object(delta,"TARGET_OFFSETS",(0,1,2)))
                stack_patches.enter_context(patch.object(delta,"TARGET_MOVEMENTS",{0:"move0",1:"move1",2:"move2"}))
                stack_patches.enter_context(patch.object(delta,"SHARD_INDEX",0))
                stack_patches.enter_context(patch.object(delta,"SHARD_START",0))
                stack_patches.enter_context(patch.object(delta,"SHARD_END",2))
                stack_patches.enter_context(patch.object(delta,"SHARD_SIZE",2))
                stack_patches.enter_context(patch.object(delta.q80,"load_archive",return_value=(dates,draws)))
                stack_patches.enter_context(patch.object(delta.q81,"build_feature_stack",return_value=stack))
                stack_patches.enter_context(patch.object(delta.q89,"iter_formula_slice",side_effect=lambda start,end:iter(formulas)))
                stack_patches.enter_context(patch.object(delta.q89,"formula_id",side_effect=formula_id))
                stack_patches.enter_context(patch.object(delta.q89,"formula_rank",side_effect=lambda columns:rank_map[tuple(columns)]))
                stack_patches.enter_context(patch.object(delta.q89,"shard_bounds",return_value=(0,2)))
                stack_patches.enter_context(patch.object(delta.q89,"batch_ranges",return_value=[(0,2)]))
                stack_patches.enter_context(patch.object(delta.q89,"TOTAL_FORMULA_COUNT",2))
                stack_patches.enter_context(patch.object(delta.q89,"SHARD_COUNT",1))
                stack_patches.enter_context(patch.object(delta.q89,"SHARD_SIZE",2))
                delta.main()
            with gzip.open(root/"reports/sequence_agent/q89_refresh_20261108_delta_shards/shard_0_delta_metrics.csv.gz","rt",encoding="utf-8",newline="") as handle:
                rows=list(csv.DictReader(handle))
            self.assertEqual(len(rows),2)
            self.assertEqual([int(row["formula_rank"]) for row in rows],[0,1])
            self.assertEqual([row["formula_id"] for row in rows],[formula_id(formulas[0]),formula_id(formulas[1])])
            for row in rows:
                for offset in (0,1,2):
                    self.assertTrue(0<=int(row[f"o{offset}_number_hits_top5"])<=5)
                    self.assertTrue(0<=int(row[f"o{offset}_number_hits_top10"])<=5)
                    self.assertTrue(0<=int(row[f"o{offset}_number_hits_top20"])<=5)
                    self.assertTrue(0<=int(row[f"o{offset}_all5_top5"])<=1)
                    self.assertTrue(0<=int(row[f"o{offset}_all5_top10"])<=1)
                    self.assertTrue(0<=int(row[f"o{offset}_all5_top20"])<=1)
                    self.assertTrue(5<=int(row[f"o{offset}_rank_sum"])<=200)
            report=json.loads((root/"reports/sequence_agent/q89_refresh_20261108_delta_shards/shard_0_delta_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"],"DELTA_SHARD_COMPLETE_NOT_TASK_COMPLETE")
            self.assertEqual(report["metrics_rows"],2)
            self.assertEqual(report["target_count"],53)
            self.assertEqual([row["target_offset"] for row in report["target_delta_ledger"]],[0,1,2])

if __name__=="__main__":
    unittest.main()
