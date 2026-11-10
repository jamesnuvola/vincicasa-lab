#!/usr/bin/env python3
"""Independent fail-closed Q95 replay validator."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, os
from pathlib import Path
import sonar_q95_subspace_permutation_null as q95
ROOT=Path(__file__).resolve().parents[1]

def close(a,b,tol=1e-10): return abs(float(a)-float(b))<=tol
def compare(a,b,path="root",tol=1e-10):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b): raise ValueError(f"Q95 key mismatch at {path}")
        for k in a: compare(a[k],b[k],path+"."+str(k),tol)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b): raise ValueError(f"Q95 list length mismatch at {path}")
        for i,(x,y) in enumerate(zip(a,b)): compare(x,y,f"{path}[{i}]",tol)
    elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        if not close(a,b,tol): raise ValueError(f"Q95 numeric mismatch at {path}: {a} != {b}")
    elif a!=b: raise ValueError(f"Q95 value mismatch at {path}: {a!r} != {b!r}")

def verify_manifest(m,include_validation):
    for key in ("catalog","target_ledger","report","protocol","checkpoint"):
        meta=m.get("files",{}).get(key)
        if not meta: raise ValueError("Q95 manifest missing "+key)
        p=ROOT/meta["path"]; data=p.read_bytes()
        if len(data)!=meta["bytes"] or hashlib.sha256(data).hexdigest()!=meta["sha256"]: raise ValueError("Q95 manifest hash mismatch "+key)
    if include_validation:
        meta=m.get("files",{}).get("validation")
        if not meta: raise ValueError("Q95 manifest missing validation")
        data=q95.VALIDATION.read_bytes()
        if len(data)!=meta["bytes"] or hashlib.sha256(data).hexdigest()!=meta["sha256"]: raise ValueError("Q95 validation hash mismatch")

def validate(read_only=False):
    required=(q95.CATALOG,q95.LEDGER,q95.REPORT,q95.MANIFEST,q95.CHECKPOINT,q95.PROTOCOL)
    missing=[p.name for p in required if not p.is_file()]
    if missing: raise ValueError("Q95 missing outputs: "+", ".join(missing))
    proto=json.loads(q95.PROTOCOL.read_text()); manifest=json.loads(q95.MANIFEST.read_text()); report=json.loads(q95.REPORT.read_text())
    if proto.get("task_id")!=q95.TASK_ID or proto.get("status")!="PREREGISTERED_PENDING_EXECUTION": raise ValueError("Q95 protocol identity/status mismatch")
    if proto.get("permutation_count")!=q95.PERM_COUNT or proto.get("permutation_seed")!=q95.PERM_SEED: raise ValueError("Q95 frozen permutation parameters mismatch")
    if manifest.get("task_id")!=q95.TASK_ID: raise ValueError("Q95 manifest identity mismatch")
    result=q95.compute_experiment()
    for key,value in (("source_archive_git_blob_sha1",result["archive_sha1"]),("source_q93_ledger_sha256",result["q93_ledger_sha256"]),("source_q94_manifest_sha256",result["q94_manifest_sha256"]),("source_q94_validation_sha256",result["q94_validation_sha256"])):
        if manifest.get(key)!=value: raise ValueError("Q95 source fingerprint mismatch "+key)
    for key,value in (("split_results",result["split_results"]),("global_holm_tests",result["holm_tests"]),("primary_gate",result["primary_gate"]),("target_counts",result["counts"]),("source_q93_ledger_sha256",result["q93_ledger_sha256"]),("source_q94_manifest_sha256",result["q94_manifest_sha256"]),("source_q94_validation_sha256",result["q94_validation_sha256"])):
        compare(report.get(key),value,"report."+key)
    if len(report.get("global_holm_tests",[]))!=6 or len(report.get("split_results",[]))!=3: raise ValueError("Q95 inferential family dimensions mismatch")
    with gzip.open(q95.LEDGER,"rt",newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=q95.ledger_fields(): raise ValueError("Q95 ledger schema mismatch")
        rows=list(reader)
    if len(rows)!=3203 or len(result["ledger_rows"])!=3203: raise ValueError("Q95 target count mismatch")
    replayed=0
    for i,(actual,expected) in enumerate(zip(rows,result["ledger_rows"])):
        if actual!=expected:
            diff=[k for k in expected if actual.get(k)!=expected[k]]
            raise ValueError(f"Q95 ledger replay mismatch target {i}: {diff[:5]}")
        draw_i=q95.MIN_HISTORY+i
        if actual["cutoff_date"]>=actual["target_date"] or int(actual["prior_draws"])!=draw_i: raise ValueError("Q95 leakage/cutoff violation "+str(i))
        if not 0<=float(actual["observed_overlap"])<=1 or not 0<=float(actual["permutation_mean"])<=1: raise ValueError("Q95 overlap out of range")
        replayed+=q95.PERM_COUNT
    validation={"task_id":q95.TASK_ID,"status":"PASS","scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "checks":{"archive_git_blob_sha1":result["archive_sha1"],"archive_sha256":result["archive_sha256"],"q93_source_ledger_sha256":result["q93_ledger_sha256"],
        "q94_source_manifest_sha256":result["q94_manifest_sha256"],"q94_source_validation_sha256":result["q94_validation_sha256"],
        "targets":len(rows),"strict_prior_cutoffs":len(rows),"split_counts":result["counts"],"fixed_node_label_permutations":q95.PERM_COUNT,
        "permutation_overlap_values_replayed":replayed,"split_associations_replayed":len(result["split_results"]),
        "global_holm_tests":len(result["holm_tests"]),"bootstrap_replicates_per_split_statistic":q95.REPS,
        "target_ledger_sha256":q95.sha(q95.LEDGER),"report_sha256":q95.sha(q95.REPORT)},
      "primary_gate":result["primary_gate"],"engine_promotion_allowed":False,"human_review_required":True,"immutable_freezes_modified":False}
    if read_only:
        if manifest.get("status")!="ACCEPTANCE_PASS" or report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or report.get("acceptance",{}).get("validator")!="Q95_FORMULA_ACCEPTANCE_PASS": raise ValueError("Q95 persisted acceptance status mismatch")
        verify_manifest(manifest,True)
        saved=json.loads(q95.VALIDATION.read_text()); compare(saved,validation,"saved_validation")
    else:
        if q95.VALIDATION.exists(): raise ValueError("Q95 append-only validation already exists")
        report["status"]="VALIDATED_PENDING_HUMAN_REVIEW"
        report["acceptance"]={"validator":"Q95_FORMULA_ACCEPTANCE_PASS","workflow_run_id":int(os.environ.get("GITHUB_RUN_ID","0")),"source_sha":os.environ.get("GITHUB_SHA",""),"human_review":"PENDING_HUMAN_REVIEW_INTEGRATION","persisted_head_replay":"PENDING"}
        q95.dump(q95.REPORT,report)
        cp=q95.CHECKPOINT.read_text().replace("State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE","State: ACCEPTANCE_PASS")
        cp+="\n## Independent acceptance\n\n- Validator status: PASS.\n"+f"- Strict-prior cutoffs: {len(rows)}/{len(rows)}.\n"+f"- Permutation overlaps replayed: {replayed}.\n"+f"- Global Holm tests replayed: {len(result['holm_tests'])}.\n"+f"- Diagnostic gate: {result['primary_gate']['status']}.\n"
        q95.CHECKPOINT.write_text(cp)
        validation["checks"]["report_sha256"]=q95.sha(q95.REPORT)
        q95.dump(q95.VALIDATION,validation)
        manifest["status"]="ACCEPTANCE_PASS"
        for key,p in (("report",q95.REPORT),("checkpoint",q95.CHECKPOINT),("validation",q95.VALIDATION)):
            data=p.read_bytes(); manifest["files"][key]={"path":str(p.relative_to(ROOT)),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
        q95.dump(q95.MANIFEST,manifest); verify_manifest(manifest,True)
    print("SONAR_Q95_ACCEPTANCE_BEGIN")
    print(json.dumps(validation,sort_keys=True,separators=(",",":")))
    print("SONAR_Q95_ACCEPTANCE_END")
    return validation

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--read-only",action="store_true"); args=parser.parse_args()
    validate(read_only=args.read_only)
