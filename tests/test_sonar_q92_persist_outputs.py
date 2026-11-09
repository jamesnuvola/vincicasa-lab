#!/usr/bin/env python3
"""Synthetic fail-closed tests for Q92 append-only result persistence."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"persist_sonar_q92_outputs.py"
TASK_ID="Q92_2026_11_08"
ARCHIVE_SHA="a"*64
SPLITS={"discovery":2012,"validation":670,"blind_oos":670}

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def write_bytes(bundle:Path,relative:str,data:bytes):
    path=bundle/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)
    return {"path":relative,"bytes":len(data),"sha256":sha(data)}

def make_bundle(bundle:Path):
    base="reports/sequence_agent/"
    metrics=[]
    target_parts=[]
    expected_paths=[]
    for shard in range(15):
        metric_path=base+f"q92_20261108_metrics_parts/shard_{shard}_metrics.csv.gz"
        target_path=base+f"q92_20261108_target_ledger_parts/shard_{shard}_target_ledger.csv.gz"
        metrics.append(write_bytes(bundle,metric_path,f"metric shard {shard}\n".encode()))
        target_parts.append(write_bytes(bundle,target_path,f"target shard {shard}\n".encode()))
        expected_paths.extend((metric_path,target_path))
    supplemental={}
    supplemental_data={
        "candidate_shortlist":(base+"q92_20261108_candidate_shortlist.csv",b"formula_id,selected\nQ92_test,1\n"),
        "candidate_selection":(base+"q92_20261108_candidate_selection.json",b"{\"selected\":\"Q92_test\"}\n"),
        "paired_blind_ledger":(base+"q92_20261108_paired_blind_ledger.csv",b"target_date,delta\n2026-01-01,0.0\n"),
        "paired_inference":(base+"q92_20261108_paired_inference.json",b"{\"primary_decision\":\"NO_SIGNIFICANT_GAIN\"}\n")
    }
    for key,(path,data) in supplemental_data.items():
        supplemental[key]=write_bytes(bundle,path,data)
        expected_paths.append(path)
    report={
        "schema_version":"1.0","task_id":TASK_ID,"status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "source_archive_sha256":ARCHIVE_SHA,"source_archive_git_blob_sha1":"b"*40,
        "target_count":3402,"scored_targets":3352,"formula_count":8436285,"metrics_rows":25308855,
        "split_counts":SPLITS,"shard_count":15,
        "multiple_testing":{"test_count":75926565,"holm_adjusted_formula_split_rows_below_0_05":0,"minimum_holm_p_max_endpoint_family":1.0},
        "candidate_selection":{"selected_candidate_id":"Q92_test","Q89_control_candidate_id":"Q89_test","blind_oos_used_for_selection":False},
        "selected_candidate_metrics":{
            "Q92_candidate":{"blind_oos_descriptive_only":{"mean_number_hits_top5":0.12,"mean_number_hits_top10":0.24,"mean_number_hits_top20":0.48,"mean_rank_of_actual_numbers":20.7}},
            "Q89_control":{"blind_oos_descriptive_only":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.50,"mean_rank_of_actual_numbers":20.5}}
        },
        "limitations":["synthetic fixture only"]
    }
    manifest={
        "schema_version":"1.0","task_id":TASK_ID,"status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "source_archive_sha256":ARCHIVE_SHA,"split_counts":SPLITS,
        "formula_split_endpoint_holm_family_size":75926565,
        "metrics_parts":metrics,"target_ledger_parts":target_parts,"supplemental_outputs":supplemental
    }
    report_path=base+"q92_20261108_report.json"
    manifest_path=base+"q92_20261108_manifest.json"
    for path,obj in ((report_path,report),(manifest_path,manifest)):
        p=bundle/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
        expected_paths.append(path)
    marker={
        "status":"ACCEPTANCE_PASS_PENDING_PERSISTENCE","validator_marker":"Q92_ACCEPTANCE_PASS",
        "task_id":TASK_ID,"source_archive_sha256":ARCHIVE_SHA,"source_commit":"synthetic-commit","run_id":123,
        "report_sha256":sha((bundle/report_path).read_bytes()),"manifest_sha256":sha((bundle/manifest_path).read_bytes())
    }
    marker_path=base+"q92_20261108_acceptance_pass_marker.json"
    p=bundle/marker_path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(marker,indent=2)+"\n",encoding="utf-8")
    expected_paths.append(marker_path)
    return expected_paths

class Q92PersistOutputsTests(unittest.TestCase):
    def run_persister(self,root,bundle,dry_run=True):
        args=[sys.executable,str(SCRIPT),"--root",str(root),"--bundle-dir",str(bundle)]
        if dry_run:args.append("--dry-run")
        return subprocess.run(args,capture_output=True,text=True,check=False)

    def test_synthetic_bundle_copies_exact_bytes_and_renders_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);root=tmp/"root";bundle=tmp/"bundle";root.mkdir();bundle.mkdir()
            expected=make_bundle(bundle)
            result=self.run_persister(root,bundle)
            self.assertEqual(result.returncode,0,result.stdout+"\n"+result.stderr)
            self.assertIn("Q92_PERSIST_OUTPUTS_BEGIN",result.stdout)
            payload=json.loads(result.stdout.split("Q92_PERSIST_OUTPUTS_BEGIN\n",1)[1].split("\nQ92_PERSIST_OUTPUTS_END",1)[0])
            self.assertEqual(payload["files_copied"],37)
            self.assertEqual(payload["status"],"DRY_RUN_PERSISTED_PENDING_HUMAN_REVIEW")
            checkpoint=root/"reports/sequence_agent/q92_20261108_persistence_checkpoint.json"
            markdown=root/"reports/sequence_agent/q92_20261108_persistence_checkpoint.md"
            self.assertTrue(checkpoint.is_file());self.assertTrue(markdown.is_file())
            persisted=json.loads(checkpoint.read_text(encoding="utf-8"))
            self.assertEqual(persisted["selected_q92_candidate_id"],"Q92_test")
            self.assertEqual(persisted["paired_blind_inference"]["primary_decision"],"NO_SIGNIFICANT_GAIN")
            self.assertTrue(persisted["dry_run"])
            for relative in expected:
                self.assertEqual((root/relative).read_bytes(),(bundle/relative).read_bytes(),relative)
            self.assertIn("PERSISTED_PENDING_HUMAN_REVIEW",markdown.read_text(encoding="utf-8"))

    def test_append_only_rejects_second_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);root=tmp/"root";bundle=tmp/"bundle";root.mkdir();bundle.mkdir();make_bundle(bundle)
            first=self.run_persister(root,bundle)
            self.assertEqual(first.returncode,0,first.stdout+"\n"+first.stderr)
            second=self.run_persister(root,bundle)
            self.assertNotEqual(second.returncode,0)
            self.assertIn("append-only target already exists",second.stdout+second.stderr)

    def test_marker_sha_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);root=tmp/"root";bundle=tmp/"bundle";root.mkdir();bundle.mkdir();make_bundle(bundle)
            marker=bundle/"reports/sequence_agent/q92_20261108_acceptance_pass_marker.json"
            obj=json.loads(marker.read_text(encoding="utf-8"));obj["report_sha256"]="0"*64
            marker.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
            result=self.run_persister(root,bundle)
            self.assertNotEqual(result.returncode,0)
            self.assertIn("report/manifest SHA-256 mismatch",result.stdout+result.stderr)

if __name__=="__main__":
    unittest.main(verbosity=2)
