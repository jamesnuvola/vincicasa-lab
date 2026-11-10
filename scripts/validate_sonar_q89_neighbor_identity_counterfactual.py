#!/usr/bin/env python3
"""Independent fail-closed Q89 replay validator."""
from __future__ import annotations
import argparse,csv,gzip,json
import numpy as np
import sonar_q89_neighbor_identity_counterfactual as q89
import sonar_q87_node_graph_phase_lag as q87

def close(a,b,tol=1e-12): return abs(float(a)-float(b))<=tol
def compare_metrics(a,b):
    if len(a)!=len(b): raise ValueError("Q89 metric row count mismatch")
    exact=("strategy_id","split","targets","top20_4plus","top20_5of5","top20_hit_distribution")
    numeric=("mean_hits_top5","mean_hits_top10","mean_hits_top20","mean_rank_actual_numbers","top20_5of5_rate")
    for x,y in zip(a,b):
        for k in exact:
            if x.get(k)!=y.get(k): raise ValueError("Q89 metric mismatch "+k)
        for k in numeric:
            if not close(x[k],y[k]): raise ValueError("Q89 metric numeric mismatch "+k)
        for e,_ in q89.ENDPOINTS:
            if not close(x["p_values_raw"][e],y["p_values_raw"][e]) or not close(x["p_values_holm"][e],y["p_values_holm"][e]):
                raise ValueError("Q89 metric p-value mismatch")
def compare_rows(a,b,keys,numeric):
    if len(a)!=len(b): raise ValueError("Q89 result row count mismatch")
    for x,y in zip(a,b):
        for k in keys:
            if x.get(k)!=y.get(k): raise ValueError("Q89 result mismatch "+k)
        for k in numeric:
            if not close(x[k],y[k]): raise ValueError("Q89 result numeric mismatch "+k)
        if "ci95" in x and not np.allclose(x["ci95"],y["ci95"],atol=1e-12,rtol=0): raise ValueError("Q89 CI mismatch")
def validate(read_only=False):
    raw=q89.ARCHIVE.read_bytes(); sha256=__import__("hashlib").sha256(raw).hexdigest()
    sha1=q89.q87.q86.q84.git_blob_sha1(q89.ARCHIVE); draws=q87.read_draws()
    dates=[d["date"].isoformat() for d in draws]
    if sha256!=q89.EXPECTED_SHA256 or sha1!=q89.EXPECTED_SHA1 or len(draws)!=q89.EXPECTED_DRAWS or dates[-1]!=q89.EXPECTED_LAST:
        raise ValueError("Q89 archive identity/dimension mismatch")
    paths=(q89.CATALOG,q89.LEDGER,q89.REPORT,q89.MANIFEST,q89.CHECKPOINT)
    if not all(p.is_file() for p in paths): raise ValueError("Q89 missing output")
    protocol=json.loads(q89.PROTOCOL.read_text()); manifest=json.loads(q89.MANIFEST.read_text()); report=json.loads(q89.REPORT.read_text())
    if protocol["counterfactuals"]["sha256"]!=q89.PERMUTATION_SHA256 or manifest["permutation_sha256"]!=q89.PERMUTATION_SHA256:
        raise ValueError("Q89 permutation hash mismatch")
    if manifest["source_archive_sha256"]!=sha256 or manifest["source_archive_git_blob_sha1"]!=sha1: raise ValueError("Q89 manifest archive mismatch")
    for key,path in (("catalog",q89.CATALOG),("target_ledger",q89.LEDGER),("report",q89.REPORT)):
        meta=manifest["files"][key]
        if meta["bytes"]!=path.stat().st_size or meta["sha256"]!=q89.sha256_file(path): raise ValueError("Q89 byte/hash mismatch "+key)
    catalog=[json.loads(x) for x in q89.CATALOG.read_text().splitlines() if x.strip()]
    if [x["strategy_id"] for x in catalog]!=list(q89.ALL_MODEL_IDS): raise ValueError("Q89 catalog order mismatch")
    if manifest["model_count"]!=42 or manifest["permutation_count"]!=40 or manifest["exact_null_holm_tests"]!=378 or manifest["paired_holm_tests"]!=24 or manifest["neighbor_randomization_tests"]!=9:
        raise ValueError("Q89 family dimensions mismatch")
    r=q89.compute_experiment(draws)
    if len(report["metrics"])!=126 or len(report["paired_block_bootstrap"])!=24 or len(report["neighbor_label_randomization"])!=9:
        raise ValueError("Q89 report dimensions mismatch")
    compare_metrics(report["metrics"],r["metrics"])
    compare_rows(report["paired_block_bootstrap"],r["paired"],("test_id","split","comparator","endpoint","n","p_holm"),("mean_difference","p_two_sided"))
    compare_rows(report["neighbor_label_randomization"],r["randomization"],("test_id","split","endpoint","identity_rank_among_40","p_holm"),("identity_mean","control_mean","control_median","control_min","control_max","p_raw"))
    if report["primary_gate"]!=r["gate"]: raise ValueError("Q89 primary gate mismatch")
    expected=q89.ledger_fields(); total=len(draws)-q89.q87.q86.q84.MIN_HISTORY
    with gzip.open(q89.LEDGER,"rt",newline="",encoding="utf-8") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames!=expected: raise ValueError("Q89 ledger schema mismatch")
        rows=list(reader)
    if len(rows)!=total or total!=q89.EXPECTED_TARGETS: raise ValueError("Q89 ledger row count mismatch")
    rank_count=signal_count=0
    for t,row in enumerate(rows):
        i=q89.q87.q86.q84.MIN_HISTORY+t
        if row["target_date"]!=dates[i] or row["cutoff_date"]!=dates[i-1] or int(row["prior_draws"])!=i or row["split"]!=r["labels"][t]:
            raise ValueError("Q89 prior cutoff/split mismatch row "+str(t))
        if row["actual_quintet"]!=" ".join(map(str,sorted(draws[i]["nums"]))): raise ValueError("Q89 actual quintet mismatch row "+str(t))
        signals=(("identity_transfer_raw",r["raw"][t,0]),("identity_transfer_ewma",r["ewma"][t,0]),
            ("permutation_transfer_mean",r["ewma"][t,1:40].mean(axis=0)),
            ("permutation_transfer_sd",r["ewma"][t,1:40].std(axis=0,ddof=1)),("node_inertia_ewma",r["node_ewma"][t]))
        for name,expected_vector in signals:
            v=np.asarray([float(row[f"{name}_{n:02d}"]) for n in range(1,41)])
            if not np.isfinite(v).all() or not np.allclose(v,expected_vector,atol=1e-9,rtol=0): raise ValueError("Q89 signal replay mismatch "+name+" row "+str(t))
            signal_count+=40
        for mi,model in enumerate(q89.ALL_MODEL_IDS):
            v=np.asarray([int(row[f"rank_{q89.slug(model)}_{n:02d}"]) for n in range(1,41)],dtype=np.int8)
            if sorted(v.tolist())!=list(range(1,41)) or not np.array_equal(v,r["ranks"][t,mi]): raise ValueError("Q89 rank replay mismatch "+model+" row "+str(t))
            rank_count+=1
    if rank_count!=total*42 or signal_count!=total*200: raise ValueError("Q89 replay counts mismatch")
    result={"task_id":q89.TASK_ID,"status":"PASS","scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks":{"archive_sha256":sha256,"canonical_draws":len(draws),"targets":total,"strict_prior_cutoffs":total,
            "models":42,"neighbor_permutations":40,"permutation_sha256":q89.PERMUTATION_SHA256,
            "rank_vectors_replayed":rank_count,"signal_values_replayed":signal_count,
            "exact_null_holm_tests":378,"paired_holm_tests":24,"neighbor_randomization_tests":9,
            "target_ledger_sha256":q89.sha256_file(q89.LEDGER),"report_sha256":q89.sha256_file(q89.REPORT)},
        "primary_gate":r["gate"],"engine_promotion_allowed":False,"human_review_required":True,"immutable_freezes_modified":False}
    if read_only:
        if not q89.VALIDATION.is_file() or json.loads(q89.VALIDATION.read_text())!=result: raise ValueError("Q89 read-only validation mismatch")
    else:
        if q89.VALIDATION.exists(): raise ValueError("Q89 append-only validation already exists")
        q89.dump(q89.VALIDATION,result)
    print("SONAR_Q89_ACCEPTANCE_BEGIN"); print(json.dumps(result,sort_keys=True,separators=(",",":"))); print("SONAR_Q89_ACCEPTANCE_END")
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--read-only",action="store_true"); validate(p.parse_args().read_only)
