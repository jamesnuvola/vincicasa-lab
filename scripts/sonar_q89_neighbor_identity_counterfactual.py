#!/usr/bin/env python3
"""Q89: counterfactual test of neighbor-identity specificity in Q88 transfer."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, os, random
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import sonar_q88_signed_node_graph_transfer as q88
import sonar_q87_node_graph_phase_lag as q87

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"reports"/"sequence_agent"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
PROTOCOL=OUT/"q89_neighbor_identity_counterfactual_protocol_2026-11-10.json"
CATALOG=OUT/"q89_neighbor_identity_counterfactual_catalog.jsonl"
LEDGER=OUT/"q89_neighbor_identity_counterfactual_target_ledger.csv.gz"
REPORT=OUT/"q89_neighbor_identity_counterfactual_report.json"
MANIFEST=OUT/"q89_neighbor_identity_counterfactual_manifest.json"
CHECKPOINT=OUT/"q89_neighbor_identity_counterfactual_checkpoint_2026-11-10.json"
VALIDATION=OUT/"q89_neighbor_identity_counterfactual_validation.json"
TASK_ID="Q89-NEIGHBOR-IDENTITY-COUNTERFACTUAL-01"
BASE_EQUAL=q87.q86.BASE_EQUAL; IDENTITY_ID="Q89::IDENTITY_TRANSFER"; NODE_ONLY_ID="Q89::NODE_ONLY_INERTIA"
SEED=8901; WINDOW=20; DECAY=0.80; ALPHA=0.20
SPLITS=("discovery","validation","blind_oos"); ENDPOINTS=(("top5",5),("top10",10),("top20",20))
EXPECTED_SHA1=q88.EXPECTED_SHA1; EXPECTED_SHA256=q88.EXPECTED_SHA256
EXPECTED_DRAWS=q88.EXPECTED_DRAWS; EXPECTED_LAST=q88.EXPECTED_LAST; EXPECTED_TARGETS=q88.EXPECTED_TARGETS

def generate_permutations():
    rng=random.Random(SEED); identity=list(range(40)); out=[identity]; seen={tuple(identity)}
    while len(out)<40:
        p=rng.sample(range(40),40); key=tuple(p)
        if key not in seen: seen.add(key); out.append(p)
    return np.asarray(out,dtype=np.int16)
PERMUTATIONS=generate_permutations()
PERMUTATION_SHA256=hashlib.sha256(json.dumps(PERMUTATIONS.tolist(),separators=(",",":")).encode()).hexdigest()
PERMUTED_IDS=tuple(f"Q89::PERMUTED_NEIGHBORS_{i:02d}" for i in range(1,40))
MODEL_IDS=(IDENTITY_ID,)+PERMUTED_IDS+(NODE_ONLY_ID,)
ALL_MODEL_IDS=MODEL_IDS+(BASE_EQUAL,)
NODE_INDEX=len(MODEL_IDS)-1; BASE_INDEX=len(ALL_MODEL_IDS)-1

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()
def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")
def slug(model): return model.replace("::","_").lower()

def all_neighbor_transfer(node_delta,edge_delta,prior_features):
    """Identity + 39 neighbor-feature label permutations; edge matrix remains untouched."""
    node=np.asarray(node_delta,dtype=np.float64); edge=np.asarray(edge_delta,dtype=np.float64); feat=np.asarray(prior_features,dtype=np.float64)
    if node.shape!=(40,6) or edge.shape!=(40,40) or feat.shape!=(40,6): raise ValueError("Q89 shape mismatch")
    if not all(np.isfinite(x).all() for x in (node,edge,feat)): raise ValueError("Q89 non-finite input")
    if not np.allclose(edge,edge.T,atol=1e-10,rtol=0) or np.any(np.abs(np.diag(edge))>1e-10): raise ValueError("Q89 graph must be symmetric with zero diagonal")
    projected=np.matmul(edge[None,:,:],feat[PERMUTATIONS])/np.sqrt(39.0)
    numerator=np.sum(projected*node[None,:,:],axis=2)
    denominator=np.linalg.norm(projected,axis=2)*np.linalg.norm(node,axis=1)[None,:]
    values=np.divide(numerator,denominator,out=np.zeros_like(numerator),where=denominator>1e-12)
    if not np.isfinite(values).all(): raise ValueError("Q89 non-finite transfer")
    return np.clip(values,-1.0,1.0)

def rolling_matrix(history,offset,window=WINDOW,decay=DECAY):
    x=np.asarray(history,dtype=np.float64)
    if x.ndim!=3 or x.shape[1:]!=(40,40) or not np.isfinite(x).all(): raise ValueError("Q89 history must be (time,40,40)")
    end=int(offset)+1
    if end<1 or end>len(x) or window<1 or not 0<decay<=1: raise ValueError("Q89 invalid history boundary")
    prefix=x[max(0,end-window):end]; w=decay**np.arange(len(prefix)-1,-1,-1,dtype=np.float64)
    return np.average(prefix,axis=0,weights=w)

def randomization_p(identity,controls):
    x=np.asarray(controls,dtype=np.float64)
    if x.shape!=(39,) or not np.isfinite(x).all() or not np.isfinite(identity): raise ValueError("Q89 requires 39 finite permutation controls")
    return float((1+np.sum(x>=float(identity)))/40.0)

def extract_actual_ranks(rank_matrix, actual_numbers):
    """Return model-by-winning-number ranks; avoid NumPy advanced-index axis reordering."""
    matrix=np.asarray(rank_matrix,dtype=np.int8)
    numbers=np.asarray(actual_numbers,dtype=np.int64)
    if matrix.ndim!=2 or matrix.shape[1]!=40 or numbers.shape!=(5,) or np.any(numbers<1) or np.any(numbers>40):
        raise ValueError("Q89 actual-rank extraction shape/value mismatch")
    result=matrix[:,numbers-1]
    if result.shape!=(matrix.shape[0],5):
        raise ValueError("Q89 actual-rank extraction orientation mismatch")
    return result

def metric_row(model,split,idx,hits,actual_ranks,tests):
    mi=ALL_MODEL_IDS.index(model); h=hits[idx,mi,:]; r=actual_ranks[idx,mi,:]; n=len(idx)
    row={"strategy_id":model,"split":split,"targets":int(n),"mean_hits_top5":float(h[:,0].mean()),
         "mean_hits_top10":float(h[:,1].mean()),"mean_hits_top20":float(h[:,2].mean()),
         "mean_rank_actual_numbers":float(r.mean()),"top20_4plus":int(np.sum(h[:,2]>=4)),
         "top20_5of5":int(np.sum(h[:,2]==5)),"top20_5of5_rate":float(np.mean(h[:,2]==5)),
         "top20_hit_distribution":{str(k):int(np.sum(h[:,2]==k)) for k in range(6)},"p_values_raw":{}}
    for j,(endpoint,k) in enumerate(ENDPOINTS):
        p=q87.field.exact_upper_tail(int(h[:,j].sum()),n,k); tid=f"Q89|{model}|{split}|{endpoint}"
        tests.append({"test_id":tid,"p_raw":p}); row["p_values_raw"][endpoint]=p
    return row

def compute_experiment(draws=None):
    draws=q87.read_draws() if draws is None else draws
    dates=[d["date"].isoformat() for d in draws]
    if len(draws)!=EXPECTED_DRAWS or dates[-1]!=EXPECTED_LAST: raise ValueError("Q89 archive identity mismatch")
    if len(draws)-q87.q86.q84.MIN_HISTORY!=EXPECTED_TARGETS: raise ValueError("Q89 target count mismatch")
    prior=q87.compute_experiment(draws); labels=list(prior["split_labels"]); counts=dict(Counter(labels))
    if counts!={"discovery":1921,"validation":640,"blind_oos":641}: raise ValueError("Q89 split mismatch")
    n=len(labels); ranks=np.empty((n,len(ALL_MODEL_IDS),40),dtype=np.int8)
    hits=np.empty((n,len(ALL_MODEL_IDS),3),dtype=np.int8); actual_ranks=np.empty((n,len(ALL_MODEL_IDS),5),dtype=np.int8)
    raw=np.zeros((n,40,40)); ewma=np.zeros((n,40,40)); node_raw=np.zeros((n,40)); node_ewma=np.zeros((n,40))
    transfer_hist=deque(maxlen=WINDOW); node_hist=deque(maxlen=WINDOW)
    prev_feat=prev_edge=prev_node_delta=None; equal_idx=q87.q86.MODEL_IDS.index(BASE_EQUAL)
    for t,draw_index in enumerate(range(q87.q86.q84.MIN_HISTORY,len(draws))):
        history=draws[:draw_index]; state=q87.field.field_state(history); edge=q87.field.pair_residual_graph(history)
        if prev_feat is None:
            trans=np.zeros((40,40)); inertia=np.zeros(40); node_delta=None
        else:
            node_delta=state["features"]-prev_feat; edge_delta=edge-prev_edge
            trans=all_neighbor_transfer(node_delta,edge_delta,prev_feat)
            inertia=np.zeros(40) if prev_node_delta is None else q88.rowwise_signed_cosine(node_delta,prev_node_delta)
        transfer_hist.append(trans); node_hist.append(inertia)
        smooth=rolling_matrix(np.asarray(transfer_hist),len(transfer_hist)-1)
        nsmooth=q88.rolling_signed_transfer(np.asarray(node_hist),len(node_hist)-1)
        raw[t]=trans; ewma[t]=smooth; node_raw[t]=inertia; node_ewma[t]=nsmooth
        equal=prior["ranks"][t,equal_idx]; base=q87.field.zscore(41.0-equal.astype(np.float64))
        rev=state["signals"]["REVERSION"]; graph=state["graph_signal"]; blend=.5*(rev+graph)
        for p in range(40):
            ranks[t,p]=q87.field.rank_from_scores(base+ALPHA*blend*q87.field.zscore(smooth[p]))
        ranks[t,NODE_INDEX]=q87.field.rank_from_scores(base+ALPHA*rev*q87.field.zscore(nsmooth))
        ranks[t,BASE_INDEX]=equal
        # All 42 rankings are frozen before the target quintet is read.
        actual=np.asarray(draws[draw_index]["nums"],dtype=np.int64); ar=extract_actual_ranks(ranks[t],actual); actual_ranks[t]=ar
        hits[t]=np.column_stack([np.sum(ar<=5,axis=1),np.sum(ar<=10,axis=1),np.sum(ar<=20,axis=1)]).astype(np.int8)
        prev_feat=state["features"]; prev_edge=edge; prev_node_delta=node_delta
    split_idx={s:np.asarray([i for i,x in enumerate(labels) if x==s],dtype=np.int64) for s in SPLITS}
    tests=[]; metrics=[]
    for model in ALL_MODEL_IDS:
        for split in SPLITS: metrics.append(metric_row(model,split,split_idx[split],hits,actual_ranks,tests))
    if len(tests)!=378: raise ValueError("Q89 exact-null family must contain 378 tests")
    adjusted=q87.q86.q84.holm_adjust(tests)
    for row in metrics: row["p_values_holm"]={e:adjusted[f"Q89|{row['strategy_id']}|{row['split']}|{e}"] for e,_ in ENDPOINTS}
    paired=[]; paired_tests=[]
    comparator_specs=(("PERMUTATION_MEAN",hits[:,1:40,:],actual_ranks[:,1:40,:]),
                      ("NODE_ONLY",hits[:,NODE_INDEX:NODE_INDEX+1,:],actual_ranks[:,NODE_INDEX:NODE_INDEX+1,:]),
                      ("BASE_EQUAL42",hits[:,BASE_INDEX:BASE_INDEX+1,:],actual_ranks[:,BASE_INDEX:BASE_INDEX+1,:]))
    for si,split in enumerate(("validation","blind_oos")):
        idx=split_idx[split]
        for ci,(comp,ch,cr) in enumerate(comparator_specs):
            rh=ch[idx].mean(axis=1) if comp=="PERMUTATION_MEAN" else ch[idx,0,:]
            rr=cr[idx].mean(axis=1).mean(axis=1) if comp=="PERMUTATION_MEAN" else cr[idx,0,:].mean(axis=1)
            for j,(endpoint,_) in enumerate(ENDPOINTS):
                z=q87.q86.q84.bootstrap_paired(hits[idx,0,j],rh[:,j],89000+si*1000+ci*100+j)
                tid=f"Q89PAIRED|{split}|{comp}|{endpoint}"; paired_tests.append({"test_id":tid,"p_raw":float(z["p_two_sided"])})
                paired.append({"test_id":tid,"split":split,"comparator":comp,"endpoint":endpoint,**z,"positive_difference_favors_identity":True})
            z=q87.q86.q84.bootstrap_paired(rr,actual_ranks[idx,0,:].mean(axis=1),89000+si*1000+ci*100+3)
            tid=f"Q89PAIRED|{split}|{comp}|mean_actual_rank_improvement"; paired_tests.append({"test_id":tid,"p_raw":float(z["p_two_sided"])})
            paired.append({"test_id":tid,"split":split,"comparator":comp,"endpoint":"mean_actual_rank_improvement",**z,"positive_difference_means_lower_identity_rank":True})
    if len(paired_tests)!=24: raise ValueError("Q89 paired family must contain 24 tests")
    padj=q87.q86.q84.holm_adjust(paired_tests)
    for row in paired: row["p_holm"]=padj[row["test_id"]]
    random_rows=[]; random_tests=[]
    for split in SPLITS:
        idx=split_idx[split]
        for j,(endpoint,_) in enumerate(ENDPOINTS):
            identity=float(hits[idx,0,j].mean()); controls=hits[idx,1:40,j].mean(axis=0); p=randomization_p(identity,controls)
            tid=f"Q89RANDOM|{split}|{endpoint}"; random_tests.append({"test_id":tid,"p_raw":p})
            random_rows.append({"test_id":tid,"split":split,"endpoint":endpoint,"identity_mean":identity,
                "control_mean":float(controls.mean()),"control_median":float(np.median(controls)),
                "control_min":float(controls.min()),"control_max":float(controls.max()),
                "identity_rank_among_40":int(1+np.sum(controls>identity)),"p_raw":p})
    if len(random_tests)!=9: raise ValueError("Q89 randomization family must contain 9 tests")
    radj=q87.q86.q84.holm_adjust(random_tests)
    for row in random_rows: row["p_holm"]=radj[row["test_id"]]
    def met(model,split): return next(x for x in metrics if x["strategy_id"]==model and x["split"]==split)
    def pair(split,comp,endpoint): return next(x for x in paired if x["split"]==split and x["comparator"]==comp and x["endpoint"]==endpoint)
    blind=met(IDENTITY_ID,"blind_oos"); base=met(BASE_EQUAL,"blind_oos")
    pb=pair("blind_oos","BASE_EQUAL42","top20"); pc=pair("blind_oos","PERMUTATION_MEAN","top20")
    pr=next(x for x in random_rows if x["split"]=="blind_oos" and x["endpoint"]=="top20")
    lift_base=blind["mean_hits_top20"]-base["mean_hits_top20"]; lift_control=pc["mean_difference"]
    passed=(lift_base>=.10 and pb["ci95"][0] is not None and pb["ci95"][0]>0 and pb["p_holm"]<.05
        and blind["p_values_holm"]["top20"]<.05 and lift_control>0 and pc["ci95"][0] is not None
        and pc["ci95"][0]>0 and pc["p_holm"]<.05 and pr["p_holm"]<.05)
    gate={"identity_strategy":IDENTITY_ID,"blind_top20_identity":blind["mean_hits_top20"],"blind_top20_equal42":base["mean_hits_top20"],
        "blind_lift_vs_equal42":lift_base,"blind_lift_vs_permutation_mean":lift_control,
        "blind_vs_equal42_ci95":pb["ci95"],"blind_vs_equal42_p_holm":pb["p_holm"],
        "blind_vs_permutation_mean_ci95":pc["ci95"],"blind_vs_permutation_mean_p_holm":pc["p_holm"],
        "blind_neighbor_randomization_p_holm":pr["p_holm"],"blind_exact_null_p_holm":blind["p_values_holm"]["top20"],
        "status":"PASS" if passed else "NOT_MET"}
    diagnostics=[]
    for split in SPLITS:
        idx=split_idx[split]
        for name,val in (("identity_signed_transfer",ewma[idx,0,:]),("permutation_mean_signed_transfer",ewma[idx,1:40,:].mean(axis=1)),("node_only_inertia",node_ewma[idx])):
            diagnostics.append({"split":split,"signal":name,"mean":float(val.mean()),"mean_absolute":float(np.abs(val).mean()),
                "positive_fraction":float(np.mean(val>0)),"near_zero_fraction":float(np.mean(np.abs(val)<.05))})
    blocks=[]; blind_idx=split_idx["blind_oos"]
    for start in range(0,len(blind_idx),100):
        b=blind_idx[start:start+100]
        if len(b)<40: continue
        blocks.append({"first_target":dates[q87.q86.q84.MIN_HISTORY+int(b[0])],"last_target":dates[q87.q86.q84.MIN_HISTORY+int(b[-1])],
            "targets":len(b),"identity_top20_delta_vs_equal42":float((hits[b,0,2]-hits[b,BASE_INDEX,2]).mean()),
            "permutation_mean_top20_delta_vs_equal42":float((hits[b,1:40,2].mean(axis=1)-hits[b,BASE_INDEX,2]).mean())})
    return {"draws":draws,"dates":dates,"labels":labels,"counts":counts,"split_idx":split_idx,"ranks":ranks,"hits":hits,
        "actual_ranks":actual_ranks,"raw":raw,"ewma":ewma,"node_raw":node_raw,"node_ewma":node_ewma,
        "metrics":metrics,"exact_tests":tests,"paired":paired,"paired_tests":paired_tests,
        "randomization":random_rows,"random_tests":random_tests,"gate":gate,"diagnostics":diagnostics,"blocks":blocks}

def ledger_fields():
    f=["target_date","cutoff_date","prior_draws","actual_quintet","split"]
    for n in range(1,41):
        f += [f"identity_transfer_raw_{n:02d}",f"identity_transfer_ewma_{n:02d}",f"permutation_transfer_mean_{n:02d}",
              f"permutation_transfer_sd_{n:02d}",f"node_inertia_ewma_{n:02d}"]
    for model in ALL_MODEL_IDS: f += [f"rank_{slug(model)}_{n:02d}" for n in range(1,41)]
    return f

def catalog():
    rows=[{"strategy_id":IDENTITY_ID,"kind":"OBSERVED_IDENTITY_TRANSFER","definition":"Frozen Q88 transfer blend with true neighbor labels; alpha .20, EWMA20 decay .80."}]
    rows += [{"strategy_id":m,"kind":"COUNTERFACTUAL_NEIGHBOR_LABEL_PERMUTATION","permutation_index":i,
        "definition":"Same Q88 operator; prior neighbor-feature rows permuted, edge-delta matrix and row strengths unchanged."} for i,m in enumerate(PERMUTED_IDS,1)]
    rows += [{"strategy_id":NODE_ONLY_ID,"kind":"NODE_ONLY_AUTOREGRESSIVE_NULL","definition":"Cosine of current and previous six-feature node deltas; EWMA20 decay .80; reversion multiplier; no graph input."},
        {"strategy_id":BASE_EQUAL,"kind":"FROZEN_BASELINE","definition":"Q87/Q86 Equal42 fixed-rule Borda baseline."}]
    return rows

def write_outputs(r,sha1,sha256):
    with CATALOG.open("w",encoding="utf-8") as f:
        for x in catalog(): f.write(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n")
    with LEDGER.open("wb") as rawfile:
        with gzip.GzipFile(filename="",fileobj=rawfile,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=ledger_fields()); w.writeheader()
                for t,date in enumerate(r["dates"][q87.q86.q84.MIN_HISTORY:]):
                    i=q87.q86.q84.MIN_HISTORY+t
                    row={"target_date":date,"cutoff_date":r["dates"][i-1],"prior_draws":i,
                        "actual_quintet":" ".join(map(str,sorted(r["draws"][i]["nums"]))),"split":r["labels"][t]}
                    for n in range(1,41):
                        j=n-1
                        row[f"identity_transfer_raw_{n:02d}"]=format(float(r["raw"][t,0,j]),".12g")
                        row[f"identity_transfer_ewma_{n:02d}"]=format(float(r["ewma"][t,0,j]),".12g")
                        row[f"permutation_transfer_mean_{n:02d}"]=format(float(r["ewma"][t,1:40,j].mean()),".12g")
                        row[f"permutation_transfer_sd_{n:02d}"]=format(float(r["ewma"][t,1:40,j].std(ddof=1)),".12g")
                        row[f"node_inertia_ewma_{n:02d}"]=format(float(r["node_ewma"][t,j]),".12g")
                    for mi,model in enumerate(ALL_MODEL_IDS):
                        for n,rank in enumerate(r["ranks"][t,mi],1): row[f"rank_{slug(model)}_{n:02d}"]=int(rank)
                    w.writerow(row)
    report={"status":"COMPUTED_PENDING_ACCEPTANCE","task_id":TASK_ID,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_code_commit":os.environ.get("GITHUB_SHA","LOCAL_UNPINNED"),
        "source_archive":{"draw_count":len(r["draws"]),"first_date":r["dates"][0],"last_date":r["dates"][-1],"git_blob_sha1":sha1,"sha256":sha256},
        "target_count":len(r["labels"]),"split_counts":r["counts"],"models":list(ALL_MODEL_IDS),
        "permutation_seed":SEED,"permutation_sha256":PERMUTATION_SHA256,
        "hypothesis":"Q88 transfer should depend on true neighbor identity; compare with 39 fixed random neighbor-feature label permutations and a graph-free node-inertia control.",
        "transfer_definition":{"identity":"cosine(node_delta_i, edge_delta_i @ prior_neighbor_features / sqrt(39))",
            "counterfactual":"same edge_delta, but prior neighbor-feature rows permuted; graph edge weights and row strengths unchanged",
            "smoothing":{"window":WINDOW,"decay":DECAY},"alpha":ALPHA,
            "node_only":"cosine(current_node_delta_i, previous_node_delta_i), EWMA20 decay .80; no graph input"},
        "metrics":r["metrics"],"paired_block_bootstrap":r["paired"],"neighbor_label_randomization":r["randomization"],
        "multiple_testing":{"exact_null_method":"global Holm; iid Hypergeometric(40,k,5) upper-tail convolution",
            "exact_null_family_size":len(r["exact_tests"]),"paired_method":"global Holm; moving-block bootstrap",
            "paired_family_size":len(r["paired_tests"]),"randomization_method":"(1 + count of 39 permuted split means >= identity)/40",
            "randomization_family_size":len(r["random_tests"]),"bootstrap_block_length":20,"bootstrap_replicates":2000},
        "primary_gate":r["gate"],"signal_diagnostics":r["diagnostics"],"blind_temporal_blocks":r["blocks"],
        "scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "limitations":["Historical Blind OOS is prior-exposed, not a virgin holdout.",
            "39 neighbor-label permutations test identity specificity conditional on label exchangeability; they are not a full graph rewiring null.",
            "The graph matrix is unchanged and row strengths are preserved; the control does not preserve every possible label-dependent graph property.",
            "Exact hypergeometric null assumes independent target draws; paired block bootstrap separately addresses serial dependence.",
            "Signed projection is statistical and does not establish physical or causal coupling.",
            "Only this fixed operator, 39 permutations and one node-only control were tested; the formula universe is not exhausted."],
        "engine_promotion_allowed":False,"human_review_required":True,"immutable_freezes_modified":False}
    dump(REPORT,report)
    files={k:{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size,"sha256":sha256_file(p)}
        for k,p in (("catalog",CATALOG),("target_ledger",LEDGER),("report",REPORT))}
    dump(MANIFEST,{"task_id":TASK_ID,"status":"COMPUTED_PENDING_ACCEPTANCE","source_archive_sha256":sha256,
        "source_archive_git_blob_sha1":sha1,"target_count":len(r["labels"]),"split_counts":r["counts"],
        "model_count":42,"permutation_count":40,"permutation_sha256":PERMUTATION_SHA256,
        "rank_vectors":len(r["labels"])*42,"signal_values_replayed":len(r["labels"])*200,
        "exact_null_holm_tests":len(r["exact_tests"]),"paired_holm_tests":len(r["paired_tests"]),
        "neighbor_randomization_tests":len(r["random_tests"]),"ledger_fields":ledger_fields(),"files":files})
    dump(CHECKPOINT,{"checkpoint_id":"SONAR-Q89-NEIGHBOR-IDENTITY-COUNTERFACTUAL-2026-11-10",
        "status":"COMPUTED_PENDING_ACCEPTANCE","source_archive_sha256":sha256,"source_archive_git_blob_sha1":sha1,
        "target_count":len(r["labels"]),"split_counts":r["counts"],"permutation_seed":SEED,
        "permutation_sha256":PERMUTATION_SHA256,"primary_gate":r["gate"],
        "next_action":"Independent replay of every prior cutoff, 40 transfer mappings, node-only signal, all rank vectors and three multiplicity families; then exact-byte persistence."})

def main():
    for p in (CATALOG,LEDGER,REPORT,MANIFEST,CHECKPOINT,VALIDATION):
        if p.exists(): raise SystemExit("Q89_BLOCKED: append-only output exists: "+str(p))
    protocol=json.loads(PROTOCOL.read_text(encoding="utf-8")); raw=ARCHIVE.read_bytes()
    sha256=hashlib.sha256(raw).hexdigest(); sha1=q87.q86.q84.git_blob_sha1(ARCHIVE)
    if sha1!=EXPECTED_SHA1 or sha256!=EXPECTED_SHA256: raise SystemExit("Q89_BLOCKED: canonical archive identity mismatch")
    if protocol["source_archive"]["sha256"]!=sha256 or protocol["source_archive"]["git_blob_sha1"]!=sha1: raise SystemExit("Q89_BLOCKED: protocol/archive mismatch")
    if protocol["counterfactuals"]["sha256"]!=PERMUTATION_SHA256: raise SystemExit("Q89_BLOCKED: permutation family mismatch")
    r=compute_experiment(); write_outputs(r,sha1,sha256)
    print("SONAR_Q89_SUMMARY_BEGIN")
    print(json.dumps({"status":"COMPUTED_PENDING_ACCEPTANCE","targets":len(r["labels"]),"split_counts":r["counts"],
        "models":42,"rank_vectors":len(r["labels"])*42,"permutation_sha256":PERMUTATION_SHA256,
        "exact_null_holm_tests":len(r["exact_tests"]),"paired_holm_tests":len(r["paired_tests"]),
        "neighbor_randomization_tests":len(r["random_tests"]),"primary_gate":r["gate"]},sort_keys=True,separators=(",",":")))
    print("SONAR_Q89_SUMMARY_END")
if __name__=="__main__": main()
