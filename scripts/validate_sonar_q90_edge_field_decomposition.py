#!/usr/bin/env python3
"""Independent fail-closed Q90 replay validator."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json
from pathlib import Path
import numpy as np
import sonar_q90_edge_field_decomposition as q90
import sonar_q87_node_graph_phase_lag as q87


def close(a,b,tol=1e-12):
    return abs(float(a)-float(b))<=tol


def compare_nested(a,b,path="root",tol=1e-12):
    if isinstance(a,dict) and isinstance(b,dict):
        if set(a)!=set(b): raise ValueError(f"Q90 key mismatch at {path}")
        for k in a: compare_nested(a[k],b[k],path+"."+str(k),tol)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b): raise ValueError(f"Q90 list length mismatch at {path}")
        for i,(x,y) in enumerate(zip(a,b)): compare_nested(x,y,f"{path}[{i}]",tol)
    elif isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        if not close(a,b,tol): raise ValueError(f"Q90 numeric mismatch at {path}: {a} != {b}")
    elif a!=b:
        raise ValueError(f"Q90 value mismatch at {path}: {a!r} != {b!r}")


def verify_manifest(manifest,include_validation):
    required=("catalog","target_ledger","report","protocol","checkpoint")
    for key in required:
        meta=manifest["files"].get(key)
        if not meta: raise ValueError("Q90 manifest missing "+key)
        path=q90.ROOT/meta["path"]
        data=path.read_bytes()
        if len(data)!=meta["bytes"] or q90.sha256_bytes(data)!=meta["sha256"]:
            raise ValueError("Q90 manifest byte/hash mismatch: "+key)
    if include_validation:
        meta=manifest["files"].get("validation")
        if not meta: raise ValueError("Q90 manifest missing validation")
        data=q90.VALIDATION.read_bytes()
        if len(data)!=meta["bytes"] or q90.sha256_bytes(data)!=meta["sha256"]:
            raise ValueError("Q90 validation byte/hash mismatch")


def validate(read_only=False):
    archive_sha1=q90.q84.git_blob_sha1(q90.ARCHIVE)
    archive_sha256=q90.sha256_file(q90.ARCHIVE)
    draws=q87.read_draws()
    dates=[d["date"].isoformat() for d in draws]
    if archive_sha1!=q90.EXPECTED_ARCHIVE_GIT_BLOB_SHA1 or len(draws)!=q90.EXPECTED_DRAWS:
        raise ValueError("Q90 pinned archive identity/count mismatch")
    if dates[0]!=q90.EXPECTED_FIRST or dates[-1]!=q90.EXPECTED_LAST:
        raise ValueError("Q90 archive date range mismatch")
    for path in (q90.CATALOG,q90.LEDGER,q90.REPORT,q90.MANIFEST,q90.CHECKPOINT,q90.PROTOCOL):
        if not path.is_file(): raise ValueError("Q90 missing artifact "+str(path.name))
    protocol=json.loads(q90.PROTOCOL.read_text(encoding="utf-8"))
    manifest=json.loads(q90.MANIFEST.read_text(encoding="utf-8"))
    report=json.loads(q90.REPORT.read_text(encoding="utf-8"))
    if protocol.get("task_id")!=q90.TASK_ID or protocol.get("status")!="PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q90 protocol identity/status mismatch")
    if protocol.get("source_archive",{}).get("git_blob_sha1")!=archive_sha1:
        raise ValueError("Q90 protocol archive mismatch")
    if manifest.get("source_archive_git_blob_sha1")!=archive_sha1 or manifest.get("source_archive_sha256")!=archive_sha256:
        raise ValueError("Q90 manifest archive mismatch")
    catalog=[json.loads(line) for line in q90.CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [x.get("strategy_id") for x in catalog]!=list(q90.MODEL_IDS):
        raise ValueError("Q90 catalog model order mismatch")
    result=q90.compute_experiment(draws)
    if len(report.get("metrics",[]))!=15 or len(report.get("exact_null_holm_tests",[]))!=45:
        raise ValueError("Q90 report exact-null dimensions mismatch")
    if len(report.get("paired_block_bootstrap",[]))!=32 or len(report.get("paired_holm_tests",[]))!=32:
        raise ValueError("Q90 report paired dimensions mismatch")
    for key,expected in (
        ("metrics",result["metrics"]),
        ("exact_null_holm_tests",result["exact_tests"]),
        ("paired_block_bootstrap",result["paired"]),
        ("paired_holm_tests",result["paired_tests"]),
        ("primary_gate",result["primary_gate"]),
        ("decomposition_diagnostics",result["decomposition_summary"]),
        ("blind_temporal_blocks",result["temporal_blocks"]),
    ):
        compare_nested(report[key],expected,"report."+key)
    expected_fields=q90.ledger_fields()
    total=len(result["labels"])
    rank_count=signal_count=decomposition_count=0
    max_row_sum=0.0
    with gzip.open(q90.LEDGER,"rt",newline="",encoding="utf-8") as handle:
        reader=csv.DictReader(handle)
        if reader.fieldnames!=expected_fields: raise ValueError("Q90 ledger schema mismatch")
        rows=list(reader)
    if len(rows)!=total or total!=3203: raise ValueError("Q90 ledger row count mismatch")
    decomposition_keys=("mu","edge_rms","main_rms","interaction_rms","interaction_energy_fraction",
        "main_energy_fraction","residual_row_sum_max_abs","reconstruction_max_abs","main_interaction_inner_product")
    for t,row in enumerate(rows):
        i=q90.MIN_HISTORY+t
        if row["target_date"]!=dates[i] or row["cutoff_date"]!=dates[i-1] or int(row["prior_draws"])!=i or row["split"]!=result["labels"][t]:
            raise ValueError("Q90 strict-prior cutoff/split mismatch row "+str(t))
        if row["actual_quintet"]!=" ".join(map(str,sorted(draws[i]["nums"]))):
            raise ValueError("Q90 actual quintet mismatch row "+str(t))
        for key in decomposition_keys:
            col={"mu":"edge_delta_mu","edge_rms":"edge_delta_rms","main_rms":"edge_main_rms",
                 "interaction_rms":"edge_interaction_rms","interaction_energy_fraction":"interaction_energy_fraction",
                 "main_energy_fraction":"main_energy_fraction","residual_row_sum_max_abs":"residual_row_sum_max_abs",
                 "reconstruction_max_abs":"reconstruction_max_abs","main_interaction_inner_product":"main_interaction_inner_product"}[key]
            if not close(float(row[col]),result["decomposition"][key][t],1e-10):
                raise ValueError("Q90 decomposition ledger replay mismatch "+col+" row "+str(t))
            decomposition_count+=1
        max_row_sum=max(max_row_sum,float(row["residual_row_sum_max_abs"]))
        for component in q90.COMPONENTS:
            for kind,array in (("raw",result["signals"][component]),("ewma",result["smoothed"][component])):
                vector=np.asarray([float(row[f"{component}_transfer_{kind}_{n:02d}"]) for n in range(1,41)])
                expected=array[t]
                if not np.isfinite(vector).all() or not np.allclose(vector,expected,atol=1e-10,rtol=0):
                    raise ValueError("Q90 signal replay mismatch "+component+" "+kind+" row "+str(t))
                signal_count+=40
        for mi,model in enumerate(q90.MODEL_IDS):
            vector=np.asarray([int(row[f"rank_{q90.slug(model)}_{n:02d}"]) for n in range(1,41)],dtype=np.int8)
            if sorted(vector.tolist())!=list(range(1,41)) or not np.array_equal(vector,result["ranks"][t,mi]):
                raise ValueError("Q90 ranking replay mismatch "+model+" row "+str(t))
            rank_count+=1
    if rank_count!=total*len(q90.MODEL_IDS) or signal_count!=total*len(q90.COMPONENTS)*2*40:
        raise ValueError("Q90 replay count mismatch")
    validation={
      "task_id":q90.TASK_ID,"status":"PASS","scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "checks":{"archive_git_blob_sha1":archive_sha1,"archive_sha256":archive_sha256,"canonical_draws":len(draws),
        "targets":total,"strict_prior_cutoffs":total,"split_counts":result["counts"],"models":len(q90.MODEL_IDS),
        "rank_vectors_replayed":rank_count,"signal_values_replayed":signal_count,
        "decomposition_diagnostics_replayed":decomposition_count,"max_residual_row_sum_abs":max_row_sum,
        "exact_null_holm_tests":len(result["exact_tests"]),"paired_holm_tests":len(result["paired_tests"]),
        "target_ledger_sha256":q90.sha256_file(q90.LEDGER),"report_sha256":q90.sha256_file(q90.REPORT)},
      "primary_gate":result["primary_gate"],"engine_promotion_allowed":False,
      "human_review_required":True,"immutable_freezes_modified":False}
    if read_only:
        if manifest.get("status")!="ACCEPTANCE_PASS": raise ValueError("Q90 persisted manifest not acceptance PASS")
        verify_manifest(manifest,True)
        saved=json.loads(q90.VALIDATION.read_text(encoding="utf-8"))
        compare_nested(saved,validation,"saved_validation")
    else:
        if q90.VALIDATION.exists(): raise ValueError("Q90 append-only validation already exists")
        dump=q90.dump
        dump(q90.VALIDATION,validation)
        checkpoint=q90.CHECKPOINT.read_text(encoding="utf-8")
        checkpoint=checkpoint.replace("State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE","State: ACCEPTANCE_PASS")
        checkpoint += "\n## Independent acceptance\n\n- Validator status: PASS.\n- Strict-prior cutoffs: 3,203/3,203.\n- Rank vectors replayed: "+str(rank_count)+".\n- Signal values replayed: "+str(signal_count)+".\n- Primary predictive gate: "+result["primary_gate"]["status"]+".\n"
        q90.CHECKPOINT.write_text(checkpoint,encoding="utf-8")
        manifest["status"]="ACCEPTANCE_PASS"
        for key,path in (("checkpoint",q90.CHECKPOINT),("validation",q90.VALIDATION)):
            data=path.read_bytes()
            manifest["files"][key]={"path":str(path.relative_to(q90.ROOT)),"bytes":len(data),"sha256":q90.sha256_bytes(data)}
        q90.dump(q90.MANIFEST,manifest)
        verify_manifest(manifest,True)
    print("SONAR_Q90_ACCEPTANCE_BEGIN")
    print(json.dumps(validation,sort_keys=True,separators=(",",":")))
    print("SONAR_Q90_ACCEPTANCE_END")
    return validation


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--read-only",action="store_true")
    validate(p.parse_args().read_only)
