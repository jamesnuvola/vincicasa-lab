#!/usr/bin/env python3
"""Synthetic regressions for the Q92 strict-prior ten-feature shard runner."""
from __future__ import annotations
import csv
import datetime as dt
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q92_common as q92
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_per_number_condition_10plus_shard as runner

class Q92WalkForwardTests(unittest.TestCase):
    def test_vectorized_weight_matrix_is_equal_weight_and_exact(self):
        formulas=[tuple(range(10)),tuple(range(1,11))]
        weights=runner.build_formula_weight_matrix(formulas)
        self.assertEqual(weights.shape,(27,2))
        self.assertAlmostEqual(float(weights[:,0].sum()),1.0)
        self.assertAlmostEqual(float(weights[:,1].sum()),1.0)
        self.assertEqual(np.count_nonzero(weights[:,0]),10)
        self.assertEqual(np.count_nonzero(weights[:,1]),10)
        self.assertTrue(np.all(weights[list(formulas[0]),0]==0.1))
        self.assertTrue(np.all(weights[list(formulas[1]),1]==0.1))

    def test_rank_matrix_stable_lower_number_tie_break(self):
        scores=np.zeros((40,2),dtype=np.float64)
        scores[0,0]=scores[1,0]=1.0
        scores[2,1]=scores[3,1]=2.0
        ranks=runner.rank_matrix(scores)
        self.assertEqual(ranks[:4,0].tolist(),[1,2,3,4])
        self.assertEqual(ranks[:4,1].tolist(),[3,4,1,2])

    def test_feature_state_for_target_excludes_target_draw(self):
        rng=random.Random(920092)
        draws=[tuple(sorted(rng.sample(range(1,41),5))) for _ in range(52)]
        changed=list(draws)
        changed[-1]=tuple(sorted({1,2,3,4,5}))
        with patch.object(q80,"MIN_HISTORY",50):
            original_stack=q81.build_feature_stack(draws)
            changed_stack=q81.build_feature_stack(changed)
        self.assertEqual(original_stack.shape,(2,40,27))
        self.assertEqual(changed_stack.shape,(2,40,27))
        # Target index 51 has prior draws 0..50; mutating draw 51 cannot alter its state.
        np.testing.assert_array_equal(original_stack[1],changed_stack[1])

    def test_main_synthetic_walkforward_outputs_reconcile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            dates=[(dt.date(2020,1,1)+dt.timedelta(days=i)).isoformat() for i in range(53)]
            rng=random.Random(920093)
            draws=[tuple(sorted(rng.sample(range(1,41),5))) for _ in range(53)]
            standardized=np.empty((3,40,27),dtype=np.float64)
            for target in range(3):
                for number in range(40):
                    for feature in range(27):
                        standardized[target,number,feature]=(number+1)*(feature+1)+target*0.01
            formulas=[tuple(range(10)),tuple(range(1,11))]
            formula_ranks={formula:index for index,formula in enumerate(formulas)}
            report_dir=root/"reports"/"sequence_agent"
            shard_dir=report_dir/"q92_shards"
            metrics=shard_dir/"shard_0_metrics.csv"
            ledger=shard_dir/"shard_0_target_ledger.csv"
            report_path=shard_dir/"shard_0_report.json"
            with patch.multiple(runner,ROOT=root,OUT=report_dir,ARCHIVE=root/"archive.csv",
                    MIN_HISTORY=50,SHARD_INDEX=0,SHARD_START=0,SHARD_END=2,SHARD_SIZE=2,
                    EXPECTED_SHARD_SIZE=2,SHARD_DIR=shard_dir,METRICS=metrics,
                    TARGET_LEDGER=ledger,REPORT=report_path), \
                 patch.object(q80,"load_archive",return_value=(dates,draws)), \
                 patch.object(q80,"split_name",side_effect=lambda offset,total:("discovery","validation","blind_oos")[offset]), \
                 patch.object(q81,"build_feature_stack",return_value=standardized), \
                 patch.object(q92,"iter_formula_slice",side_effect=lambda start,end:iter(formulas)), \
                 patch.object(q92,"formula_unrank",side_effect=lambda rank:formulas[int(rank)]), \
                 patch.object(q92,"formula_rank",side_effect=lambda columns:formula_ranks[tuple(columns)]), \
                 patch.object(q92,"shard_bounds",return_value=(0,2)), \
                 patch.object(q92,"batch_ranges",return_value=[(0,2)]), \
                 patch.object(q92,"hypergeom_upper_normal_p",return_value=0.5), \
                 patch.object(q92,"TOTAL_FORMULA_COUNT",2),patch.object(q92,"SHARD_COUNT",1),patch.object(q92,"SHARD_SIZE",2):
                runner.main()
            with metrics.open(newline="",encoding="utf-8") as handle:
                metric_rows=list(csv.DictReader(handle))
            with ledger.open(newline="",encoding="utf-8") as handle:
                ledger_rows=list(csv.DictReader(handle))
            self.assertEqual(len(metric_rows),6) # 2 formulas × 3 chronological splits
            self.assertEqual(len(ledger_rows),3)
            self.assertEqual({row["split"] for row in metric_rows},{"discovery","validation","blind_oos"})
            self.assertEqual([row["target_date"] for row in ledger_rows],dates[50:53])
            self.assertEqual([row["cutoff_date"] for row in ledger_rows],dates[49:52])
            self.assertEqual([int(row["prior_draws"]) for row in ledger_rows],[50,51,52])
            self.assertEqual({int(row["feature_count"]) for row in metric_rows},{10})
            self.assertEqual({int(row["formula_count_tested"]) for row in ledger_rows},{2})
            for row in ledger_rows:
                ranks=__import__("json").loads(row["best_actual_number_ranks"])
                self.assertEqual(len(ranks),5)
                self.assertTrue(all(1<=value<=40 for value in ranks))
                self.assertTrue(0<=int(row["best_number_hits_top5"])<=5)
            import json
            report=json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["task_id"],"Q92")
            self.assertEqual(report["status"],"SHARD_COMPLETE_NOT_TASK_COMPLETE")
            self.assertEqual(report["metrics_rows"],6)
            self.assertEqual(report["target_ledger_rows"],3)

if __name__=="__main__":
    unittest.main(verbosity=2)
