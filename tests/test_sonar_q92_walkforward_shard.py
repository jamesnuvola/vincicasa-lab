#!/usr/bin/env python3
"""Synthetic regressions for the Q92 ten-feature strict-prior shard evaluator."""
from __future__ import annotations
import csv
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
import sonar_q92_common as q92
import sonar_q92_null_calibration as q92null
import sonar_per_number_condition_10plus_shard as runner

class Q92WalkForwardTests(unittest.TestCase):
    def test_canonical_archive_last_draw_matches_registered_quintet(self):
        dates,draws=runner.q80.load_archive()
        self.assertEqual(len(dates),3402)
        self.assertEqual(dates[-1],"2026-11-08")
        # The archive loader returns immutable sorted tuples, not lists.
        self.assertEqual(draws[-1],(3,7,10,16,27))
    def test_formula_universe_count_shards_and_batch_partition(self):
        self.assertEqual(q92.TOTAL_FORMULA_COUNT,8_436_285)
        self.assertEqual(q92.SHARD_SIZE,562_419)
        intervals=[q92.shard_bounds(index) for index in range(15)]
        self.assertEqual(intervals[0][0],0)
        self.assertEqual(intervals[-1][1],q92.TOTAL_FORMULA_COUNT)
        self.assertTrue(all(intervals[index][1]==intervals[index+1][0] for index in range(14)))
        self.assertEqual(len(q92.batch_ranges(q92.SHARD_SIZE)),275)
        self.assertEqual(len(q92.batch_ranges(q92.TOTAL_FORMULA_COUNT)),4_120)
        sample_ranks=[0,1,1000,q92.TOTAL_FORMULA_COUNT//2,q92.TOTAL_FORMULA_COUNT-1]
        for rank in sample_ranks:
            columns=q92.formula_unrank(rank)
            self.assertEqual(q92.formula_rank(columns),rank)
            self.assertTrue(q92.formula_id(columns).startswith("P10_"))
        columns=q92.formula_unrank(1000)
        for rank in range(1000,1100):
            self.assertEqual(q92.formula_rank(columns),rank)
            columns=q92.next_formula(columns)
        self.assertTrue(0.0<=q92null.exact_upper_tail_pvalue(100,670,5)<=1.0)

    def test_rank_matrix_stable_lower_number_tie_break(self):
        scores=np.zeros((2,40),dtype=np.float64)
        scores[0,:3]=[1.0,1.0,0.0]
        scores[1,:3]=[2.0,0.0,2.0]
        ranks=runner.rank_matrix(scores)
        self.assertEqual(ranks[0,:3].tolist(),[1,2,3])
        self.assertEqual(ranks[1,:3].tolist(),[1,3,2])
        self.assertEqual(ranks[0,3:].tolist(),list(range(4,41)))
        self.assertEqual(ranks[1,3:].tolist(),list(range(4,41)))

    def test_rank_actual_numbers_matches_full_stable_rank_kernel(self):
        rng=np.random.default_rng(920092)
        scores=rng.normal(size=(40,4096)).astype(np.float64)
        actual_indices=np.asarray([0,1,2,17,39],dtype=np.int64)
        full=runner.rank_matrix(scores.T)
        observed=runner.rank_actual_numbers(scores,actual_indices)
        self.assertTrue(np.array_equal(observed,full[:,actual_indices].T))
        tied=np.zeros((40,3),dtype=np.float64)
        tied[0,:]=1.0
        tied[1,:]=1.0
        tied[2,:]=0.0
        actual_tied=np.asarray([0,1,2,10,39],dtype=np.int64)
        full_tied=runner.rank_matrix(tied.T)
        self.assertTrue(np.array_equal(runner.rank_actual_numbers(tied,actual_tied),full_tied[:,actual_tied].T))

    def test_equal_weight_matrix_has_exactly_ten_features_per_formula(self):
        formulas=[tuple(range(10)),tuple(range(1,11))]
        weights=runner.build_formula_weight_matrix(formulas)
        self.assertEqual(weights.shape,(27,2))
        self.assertTrue(np.allclose(weights.sum(axis=0),[1.0,1.0]))
        self.assertEqual(np.count_nonzero(weights[:,0]),10)
        self.assertEqual(np.count_nonzero(weights[:,1]),10)
        self.assertTrue(np.allclose(weights[ list(formulas[0]),0],0.1))

    def test_main_synthetic_three_target_strict_prefix_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/"archive.csv"
            archive.write_text("synthetic archive\n",encoding="utf-8")
            # source_code_hashes() covers the full Q92 execution/acceptance envelope.
            # Supply deterministic placeholder files for every declared path in this isolated fixture.
            for relative in q92.SOURCE_CODE_HASH_PATHS:
                fixture=root/relative
                fixture.parent.mkdir(parents=True,exist_ok=True)
                fixture.write_bytes(("synthetic source fixture: "+relative+"\n").encode("utf-8"))
            dates=[f"2020-01-{i+1:02d}" for i in range(53)]
            draws=[tuple(sorted(set(((i+j)%40)+1 for j in range(5)))) for i in range(53)]
            draws[50]=tuple(range(1,6))
            draws[51]=tuple(range(6,11))
            draws[52]=tuple(range(11,16))
            standardized=np.zeros((3,40,27),dtype=np.float64)
            for target in range(3):
                for number in range(40):
                    for feature in range(27):
                        standardized[target,number,feature]=number*(feature+1)+target*0.01
            formulas=[tuple(range(0,10)),tuple(range(1,11))]
            def formula_id(columns):
                return "P10_"+"_".join(f"{value:02d}" for value in columns)
            rank_map={formulas[0]:0,formulas[1]:1}
            with ExitStack() as patches:
                patches.enter_context(patch.object(runner,"ROOT",root))
                patches.enter_context(patch.object(runner,"ARCHIVE",archive))
                patches.enter_context(patch.object(runner,"OUT",root/"reports/sequence_agent"))
                patches.enter_context(patch.object(runner,"SHARD_DIR",root/"reports/sequence_agent/q92_shards"))
                patches.enter_context(patch.object(runner,"METRICS",root/"reports/sequence_agent/q92_shards/shard_0_metrics.csv"))
                patches.enter_context(patch.object(runner,"TARGET_LEDGER",root/"reports/sequence_agent/q92_shards/shard_0_target_ledger.csv"))
                patches.enter_context(patch.object(runner,"REPORT",root/"reports/sequence_agent/q92_shards/shard_0_report.json"))
                patches.enter_context(patch.object(runner,"MIN_HISTORY",50))
                patches.enter_context(patch.object(runner,"SHARD_INDEX",0))
                patches.enter_context(patch.object(runner,"SHARD_START",0))
                patches.enter_context(patch.object(runner,"SHARD_END",2))
                patches.enter_context(patch.object(runner,"SHARD_SIZE",2))
                patches.enter_context(patch.object(runner.q80,"MIN_HISTORY",50))
                patches.enter_context(patch.object(runner.q80,"load_archive",return_value=(dates,draws)))
                patches.enter_context(patch.object(runner.q80,"split_name",side_effect=["discovery","validation","blind_oos"]))
                patches.enter_context(patch.object(runner.q81,"build_feature_stack",return_value=standardized))
                patches.enter_context(patch.object(runner.q92,"iter_formula_slice",side_effect=lambda start,end:iter(formulas)))
                patches.enter_context(patch.object(runner.q92,"formula_id",side_effect=formula_id))
                patches.enter_context(patch.object(runner.q92,"formula_unrank",return_value=formulas[0]))
                patches.enter_context(patch.object(runner.q92,"formula_rank",side_effect=lambda columns:rank_map[tuple(columns)]))
                patches.enter_context(patch.object(runner.q92,"shard_bounds",return_value=(0,2)))
                patches.enter_context(patch.object(runner.q92,"batch_ranges",return_value=[(0,2)]))
                patches.enter_context(patch.object(runner.q92,"TOTAL_FORMULA_COUNT",2))
                patches.enter_context(patch.object(runner.q92,"SHARD_COUNT",1))
                patches.enter_context(patch.object(runner.q92,"SHARD_SIZE",2))
                runner.main()
            with (root/"reports/sequence_agent/q92_shards/shard_0_metrics.csv").open(newline="",encoding="utf-8") as handle:
                metrics=list(csv.DictReader(handle))
            with (root/"reports/sequence_agent/q92_shards/shard_0_target_ledger.csv").open(newline="",encoding="utf-8") as handle:
                ledger=list(csv.DictReader(handle))
            report=json.loads((root/"reports/sequence_agent/q92_shards/shard_0_report.json").read_text(encoding="utf-8"))
            self.assertEqual(len(metrics),6)
            self.assertEqual({row["feature_count"] for row in metrics},{"10"})
            self.assertEqual({row["formula_id"][:4] for row in metrics},{"P10_"})
            self.assertEqual(len(ledger),3)
            self.assertEqual([row["prior_draws"] for row in ledger],["50","51","52"])
            self.assertEqual([row["cutoff_date"] for row in ledger],dates[49:52])
            self.assertEqual(report["status"],"SHARD_COMPLETE_NOT_TASK_COMPLETE")
            self.assertEqual(report["total_formula_count"],2)
            self.assertEqual(report["formula_size"],10)
            self.assertEqual(report["split_counts"],{"discovery":1,"validation":1,"blind_oos":1})

if __name__=="__main__":
    unittest.main()
