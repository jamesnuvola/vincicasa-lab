#!/usr/bin/env python3
"""Independent fail-closed Q96 replay validator."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, os
from pathlib import Path
import sonar_q96_delayed_spectral_recurrence as q96

ROOT=Path(__file__).resolve().parents[1]

def compare(a,b,path="root",tol=1e-10):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b):
            raise ValueError(f"Q96 key mismatch at {path}")
        for k in a:
            compare(a[k],b[k],path+"."+str(k),tol)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):
            raise ValueError(f"Q96 list length mismatch at {path}")
        for i,(x,y) in enumerate(zip(a,b)):
            compare(x,y,f"{path}[{i}]",tol)
    elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        if abs(float(a)-float(b))>tol:
            raise ValueError(f"Q96 numeric mismatch at {path}: {a} != {b}")
    elif a!=b:
        raise ValueError(f"Q96 value mismatch at {path}: {a!r} != {b!r}")

def verify_manifest(manifest,include_validation):
    for key in ("catalog","target_ledger","report","protocol","checkpoint"):
        meta=manifest.get("files",{}).get(key)
        if not meta:
            raise ValueError("Q96 manifest missing "+key)
        p=ROOT/meta["path"]
        data=p.read_bytes()
        if len(data)!=meta["bytes"] or hashlib.sha256(data).hexdigest()!=meta["sha256"]:
            raise ValueError("Q96 manifest hash mismatch: "+key)
    if include_validation:
        meta=manifest.get("files",{}).get("validation")
        if not meta:
            raise ValueError("Q96 manifest missing validation")
        data=q96.VALIDATION.read_bytes()
        if len(data)!=meta["bytes"] or hashlib.sha256(data).hexdigest()!=meta["sha256"]:
            raise ValueError("Q96 validation hash mismatch")

def validate(read_only=False):
    required=(q96.CATALOG,q96.LEDGER,q96.REPORT,q96.MANIFEST,q96.CHECKPOINT,q96.PROTOCOL)
    missing=[p.name for p in required if not p.is_file()]
    if missing:
        raise ValueError("Q96 missing outputs: "+", ".join(missing))
    protocol=json.loads(q96.PROTOCOL.read_text(encoding="utf-8"))
    manifest=json.loads(q96.MANIFEST.read_text(encoding="utf-8"))
    report=json.loads(q96.REPORT.read_text(encoding="utf-8"))
    if protocol.get("task_id")!=q96.TASK_ID or protocol.get("status")!="PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q96 protocol identity/status mismatch")
    null_spec=protocol.get("permutation_null",{})
    if protocol.get("lags")!=list(q96.LAGS) or null_spec.get("count")!=q96.PERM_COUNT or null_spec.get("seed")!=q96.PERM_SEED:
        raise ValueError("Q96 frozen parameters mismatch")
    if manifest.get("task_id")!=q96.TASK_ID:
        raise ValueError("Q96 manifest identity mismatch")
    result=q96.compute_experiment()
    for key,value in (("source_archive_git_blob_sha1",result["archive_sha1"]),
                      ("source_archive_sha256",result["archive_sha256"]),
                      ("accepted_q95_manifest_sha256",result["q95_manifest_sha256"]),
                      ("accepted_q95_validation_sha256",result["q95_validation_sha256"]),
                      ("accepted_q95_report_sha256",result["q95_report_sha256"])):
        if manifest.get(key)!=value:
            raise ValueError("Q96 source fingerprint mismatch: "+key)
    for key,value in (("split_results",result["split_results"]),
                      ("global_holm_tests",result["holm_tests"]),
                      ("primary_gate",result["primary_gate"]),
                      ("target_design",{"targets":len(result["labels"]),"minimum_prior_draws":q96.MIN_HISTORY,"split_counts":result["counts"],
                                        "cutoff_rule":"Current subspace uses draws[:i]; lagged subspace uses draws[:i-lag]; both strictly precede target i."}),
                      ("accepted_q95_sources",{"manifest_sha256":result["q95_manifest_sha256"],"validation_sha256":result["q95_validation_sha256"],"report_sha256":result["q95_report_sha256"]})):
        compare(report.get(key),value,"report."+key)
    if len(report.get("global_holm_tests",[]))!=9 or len(report.get("split_results",[]))!=9:
        raise ValueError("Q96 inferential family dimension mismatch")
    replayed=0
    with gzip.open(q96.LEDGER,"rt",newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=q96.ledger_fields():
            raise ValueError("Q96 ledger schema mismatch")
        count=0
        for actual in reader:
            if count>=len(result["labels"]):
                raise ValueError("Q96 ledger has extra rows")
            expected=q96.make_ledger_row(result,count)
            if actual!=expected:
                diff=[k for k in expected if actual.get(k)!=expected[k]]
                raise ValueError(f"Q96 exact ledger replay mismatch at target {count}: {diff[:8]}")
            draw_index=q96.MIN_HISTORY+count
            if actual["cutoff_date"]>=actual["target_date"] or int(actual["prior_draws"])!=draw_index:
                raise ValueError("Q96 current cutoff leakage violation at target "+str(count))
            for lag in q96.LAGS:
                ref_prior=int(actual[f"lag_{lag}_reference_prior_draws"])
                ref_cutoff=actual[f"lag_{lag}_reference_cutoff"]
                expected_prior=draw_index-lag if count>=lag else 0
                if ref_prior!=expected_prior:
                    raise ValueError("Q96 lagged prefix index mismatch")
                if count>=lag:
                    if not ref_cutoff or ref_cutoff>=actual["cutoff_date"] or ref_cutoff>=actual["target_date"]:
                        raise ValueError("Q96 lagged cutoff leakage violation")
                elif ref_cutoff:
                    raise ValueError("Q96 early lag reference must be empty")
                vals=[float(actual[f"lag_{lag}_perm_{p:04d}"]) for p in range(q96.PERM_COUNT)]
                if not all(0.0<=v<=1.0 for v in vals):
                    raise ValueError("Q96 permutation overlap outside [0,1]")
                obs=float(actual[f"lag_{lag}_observed_overlap"])
                if not 0.0<=obs<=1.0:
                    raise ValueError("Q96 observed overlap outside [0,1]")
                replayed+=q96.PERM_COUNT
            count+=1
        if count!=len(result["labels"]):
            raise ValueError("Q96 ledger row count mismatch")
    validation={"task_id":q96.TASK_ID,"status":"PASS",
      "scope":"HISTORICAL_GEOMETRIC_DIAGNOSTIC_NOT_PREDICTIVE_OR_PROSPECTIVE_CONFIRMATION",
      "checks":{"archive_git_blob_sha1":result["archive_sha1"],"archive_sha256":result["archive_sha256"],
        "q95_manifest_sha256":result["q95_manifest_sha256"],"q95_validation_sha256":result["q95_validation_sha256"],
        "targets":len(result["labels"]),"strict_prior_cutoffs":len(result["labels"]),
        "split_counts":result["counts"],"lags":list(q96.LAGS),"fixed_node_label_permutations":q96.PERM_COUNT,
        "permutation_overlap_values_replayed":replayed,"global_holm_tests":len(result["holm_tests"]),
        "bootstrap_replicates":q96.REPS,"bootstrap_block_length":q96.BLOCK,
        "target_ledger_sha256":q96.sha(q96.LEDGER),"report_sha256":q96.sha(q96.REPORT)},
      "primary_gate":result["primary_gate"],"engine_promotion_allowed":False,
      "human_review_required":True,"immutable_freezes_modified":False,"target_outcomes_read":False}
    if read_only:
        if manifest.get("status")!="ACCEPTANCE_PASS" or report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or report.get("acceptance",{}).get("validator")!="Q96_FORMULA_ACCEPTANCE_PASS":
            raise ValueError("Q96 persisted acceptance status mismatch")
        verify_manifest(manifest,True)
        saved=json.loads(q96.VALIDATION.read_text(encoding="utf-8"))
        compare(saved,validation,"saved_validation")
    else:
        if q96.VALIDATION.exists():
            raise ValueError("Q96 append-only validation already exists")
        report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
        report["acceptance"]={"validator":"Q96_FORMULA_ACCEPTANCE_PASS",
          "workflow_run_id":int(os.environ.get("GITHUB_RUN_ID","0")),
          "source_sha":os.environ.get("SONAR_SOURCE_SHA",os.environ.get("GITHUB_SHA","")),
          "human_review":"PENDING_HUMAN_REVIEW_INTEGRATION",
          "persisted_head_replay":"PENDING"}
        q96.dump(q96.REPORT,report)
        cp=q96.CHECKPOINT.read_text(encoding="utf-8")
        cp=cp.replace("State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE","State: ACCEPTANCE_PASS")
        cp+="\n## Independent acceptance\n\n- Validator status: PASS.\n"
        cp+=f"- Strict-prior cutoffs: {len(result['labels'])}/{len(result['labels'])}.\n"
        cp+=f"- Permutation overlaps replayed: {replayed}.\n"
        cp+=f"- Global Holm tests replayed: {len(result['holm_tests'])}.\n"
        cp+=f"- Diagnostic gate: {result['primary_gate']['status']}.\n"
        q96.CHECKPOINT.write_text(cp,encoding="utf-8")
        validation["checks"]["report_sha256"]=q96.sha(q96.REPORT)
        q96.dump(q96.VALIDATION,validation)
        manifest["status"]="ACCEPTANCE_PASS"
        for key,p in (("report",q96.REPORT),("checkpoint",q96.CHECKPOINT),("validation",q96.VALIDATION)):
            data=p.read_bytes()
            manifest["files"][key]={"path":str(p.relative_to(ROOT)),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        q96.dump(q96.MANIFEST,manifest)
        verify_manifest(manifest,True)
    print("SONAR_Q96_ACCEPTANCE_BEGIN")
    print(json.dumps(validation,sort_keys=True,separators=(",",":")))
    print("SONAR_Q96_ACCEPTANCE_END")
    return validation

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--read-only",action="store_true")
    args=parser.parse_args()
    validate(read_only=args.read_only)
