#!/usr/bin/env python3
"""Q90: decompose edge changes into degree/main effects and pair interactions."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, math
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sonar_q87_node_graph_phase_lag as q87
import sonar_q88_signed_node_graph_transfer as q88
import sonar_strategy_atlas as q84

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
PROTOCOL=OUT/"q90_edge_field_decomposition_protocol_2026-11-10.json"
CATALOG=OUT/"q90_edge_field_decomposition_catalog.jsonl"
LEDGER=OUT/"q90_edge_field_decomposition_target_ledger.csv.gz"
REPORT=OUT/"q90_edge_field_decomposition_report.json"
MANIFEST=OUT/"q90_edge_field_decomposition_manifest.json"
CHECKPOINT=OUT/"q90_edge_field_decomposition_checkpoint_2026-11-10.md"
VALIDATION=OUT/"q90_edge_field_decomposition_validation.json"

TASK_ID="Q90-EDGE-FIELD-DECOMPOSITION-01"
EXPECTED_ARCHIVE_GIT_BLOB_SHA1="8d3e19f0b417024ba32e576697eac0648d12ab86"
EXPECTED_DRAWS=3403
EXPECTED_FIRST="2017-07-17"
EXPECTED_LAST="2026-11-09"
MIN_HISTORY=200
ALPHA=0.20
WINDOW=20
DECAY=0.80
N=40
MODEL_IDS=("Q90::FULL_EDGE_TRANSFER","Q90::DEGREE_MAIN_TRANSFER","Q90::PAIR_INTERACTION_TRANSFER","Q90::NODE_ONLY_INERTIA","BASE::EQUAL42")
FOCAL="Q90::PAIR_INTERACTION_TRANSFER"
BASE="BASE::EQUAL42"
COMPONENTS=("full","degree_main","pair_interaction","node_only")
SPLITS=("discovery","validation","blind_oos")
ENDPOINTS=(("top5",5),("top10",10),("top20",20))
COMPARATORS=("Q90::FULL_EDGE_TRANSFER","Q90::DEGREE_MAIN_TRANSFER","Q90::NODE_ONLY_INERTIA","BASE::EQUAL42")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(path.read_bytes())


def dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")


def slug(model):
    return model.replace("::","_").lower()


def decompose_edge_change(edge, tolerance=1e-10):
    """Exact additive-main-effect + zero-row-sum pair-interaction decomposition."""
    e=np.asarray(edge,dtype=np.float64)
    if e.shape!=(N,N) or not np.isfinite(e).all():
        raise ValueError("Q90 edge matrix must be finite 40x40")
    if not np.allclose(e,e.T,atol=tolerance,rtol=0):
        raise ValueError("Q90 edge matrix must be symmetric")
    if np.any(np.abs(np.diag(e))>tolerance):
        raise ValueError("Q90 edge matrix must have zero diagonal")
    mu=float(e.sum()/(N*(N-1)))
    row_sums=e.sum(axis=1)
    effects=(row_sums-(N-1)*mu)/(N-2)
    main=mu+effects[:,None]+effects[None,:]
    np.fill_diagonal(main,0.0)
    interaction=e-main
    np.fill_diagonal(interaction,0.0)
    row_error=float(np.max(np.abs(interaction.sum(axis=1))))
    reconstruction=float(np.max(np.abs((main+interaction)-e)))
    orthogonality=float(np.sum(main*interaction))
    scale=max(1.0,float(np.linalg.norm(e)*np.linalg.norm(main)))
    if abs(float(effects.sum()))>tolerance or row_error>tolerance or reconstruction>tolerance or abs(orthogonality)>tolerance*scale:
        raise ValueError("Q90 decomposition invariant failed")
    diagnostics={
        "mu":mu,
        "main_effect_sum":float(effects.sum()),
        "edge_rms":float(np.sqrt(np.mean(e*e))),
        "main_rms":float(np.sqrt(np.mean(main*main))),
        "interaction_rms":float(np.sqrt(np.mean(interaction*interaction))),
        "interaction_energy_fraction":float(np.sum(interaction*interaction)/np.sum(e*e)) if np.sum(e*e)>0 else 0.0,
        "main_energy_fraction":float(np.sum(main*main)/np.sum(e*e)) if np.sum(e*e)>0 else 0.0,
        "residual_row_sum_max_abs":row_error,
        "reconstruction_max_abs":reconstruction,
        "main_interaction_inner_product":orthogonality,
    }
    return main,interaction,diagnostics


def split_labels(total):
    return [q84.split_name(i,total) for i in range(total)]


def equal42_rank(history):
    """Reproduce the fixed Equal42 Borda ranking using the current strict prefix."""
    if len(q84.CONFIGS)!=42:
        raise ValueError("Q90 requires exactly 42 fixed baseline configurations")
    base=q84.feature_scores(history)
    fixed=np.empty((len(q84.CONFIGS),N),dtype=np.int8)
    for i,config in enumerate(q84.CONFIGS):
        fixed[i]=q84.rank_vector_from_order(q84.strategy_order(base,config))
    return q84.weighted_borda_rank(fixed,np.ones(len(q84.CONFIGS),dtype=np.float64))


def transfer_score(base_z,multiplier,signal):
    arrays=[np.asarray(x,dtype=np.float64) for x in (base_z,multiplier,signal)]
    if any(x.shape!=(N,) for x in arrays) or not all(np.isfinite(x).all() for x in arrays):
        raise ValueError("Q90 score inputs must be finite length-40 vectors")
    return base_z+ALPHA*multiplier*q87.field.zscore(signal)


def extract_actual_ranks(rank_matrix,actual_numbers):
    matrix=np.asarray(rank_matrix,dtype=np.int8)
    nums=np.asarray(actual_numbers,dtype=np.int64)
    if matrix.shape!=(len(MODEL_IDS),N) or nums.shape!=(5,) or np.any(nums<1) or np.any(nums>N):
        raise ValueError("Q90 rank extraction shape/value mismatch")
    result=matrix[:,nums-1]
    if result.shape!=(len(MODEL_IDS),5):
        raise ValueError("Q90 rank extraction orientation mismatch")
    return result


def compute_experiment(draws=None):
    draws=q87.read_draws() if draws is None else draws
    dates=[d["date"].isoformat() for d in draws]
    if len(draws)!=EXPECTED_DRAWS or dates[0]!=EXPECTED_FIRST or dates[-1]!=EXPECTED_LAST:
        raise ValueError("Q90 canonical archive count/date mismatch")
    total=len(draws)-MIN_HISTORY
    if total!=3203:
        raise ValueError("Q90 target count mismatch")
    labels=split_labels(total)
    counts=dict(Counter(labels))
    if counts!={"discovery":1921,"validation":641,"blind_oos":641}:
        raise ValueError("Q90 chronological split mismatch")
    ranks=np.empty((total,len(MODEL_IDS),N),dtype=np.int8)
    hits=np.empty((total,len(MODEL_IDS),3),dtype=np.int8)
    actual_ranks=np.empty((total,len(MODEL_IDS),5),dtype=np.int8)
    signals={name:np.zeros((total,N),dtype=np.float64) for name in COMPONENTS}
    smoothed={name:np.zeros((total,N),dtype=np.float64) for name in COMPONENTS}
    decomposition={name:np.zeros(total,dtype=np.float64) for name in
        ("mu","edge_rms","main_rms","interaction_rms","interaction_energy_fraction",
         "main_energy_fraction","residual_row_sum_max_abs","reconstruction_max_abs","main_interaction_inner_product")}
    histories={name:deque(maxlen=WINDOW) for name in COMPONENTS}
    previous_features=None
    previous_edge=None
    previous_node_delta=None
    for offset,draw_index in enumerate(range(MIN_HISTORY,len(draws))):
        # Strict-prior state: the target draw is not passed to any feature function.
        history=draws[:draw_index]
        state=q87.field.field_state(history)
        edge=q87.field.pair_residual_graph(history)
        equal=equal42_rank(history)
        base_z=q87.field.zscore(41.0-equal.astype(np.float64))
        if previous_features is None or previous_edge is None:
            node_delta=np.zeros((N,6),dtype=np.float64)
            edge_delta=np.zeros((N,N),dtype=np.float64)
            main=np.zeros((N,N),dtype=np.float64)
            interaction=np.zeros((N,N),dtype=np.float64)
            diag={"mu":0.0,"edge_rms":0.0,"main_rms":0.0,"interaction_rms":0.0,
                  "interaction_energy_fraction":0.0,"main_energy_fraction":0.0,
                  "residual_row_sum_max_abs":0.0,"reconstruction_max_abs":0.0,
                  "main_interaction_inner_product":0.0}
            node_signal=np.zeros(N,dtype=np.float64)
        else:
            node_delta=state["features"]-previous_features
            edge_delta=edge-previous_edge
            main,interaction,diag=decompose_edge_change(edge_delta)
            node_signal=np.zeros(N,dtype=np.float64) if previous_node_delta is None else q88.rowwise_signed_cosine(node_delta,previous_node_delta)
        if previous_features is None:
            full_signal=degree_signal=interaction_signal=np.zeros(N,dtype=np.float64)
        else:
            full_signal=q88.signed_transfer_alignment(node_delta,edge_delta,previous_features)
            degree_signal=q88.signed_transfer_alignment(node_delta,main,previous_features)
            interaction_signal=q88.signed_transfer_alignment(node_delta,interaction,previous_features)
        raw={"full":full_signal,"degree_main":degree_signal,"pair_interaction":interaction_signal,"node_only":node_signal}
        for name in COMPONENTS:
            signals[name][offset]=raw[name]
            histories[name].append(raw[name])
            smoothed[name][offset]=q88.rolling_signed_transfer(np.asarray(histories[name]),len(histories[name])-1,WINDOW,DECAY)
        blend=0.5*(state["signals"]["REVERSION"]+state["graph_signal"])
        reversion=state["signals"]["REVERSION"]
        current=np.empty((len(MODEL_IDS),N),dtype=np.int8)
        current[0]=q87.field.rank_from_scores(transfer_score(base_z,blend,smoothed["full"][offset]))
        current[1]=q87.field.rank_from_scores(transfer_score(base_z,blend,smoothed["degree_main"][offset]))
        current[2]=q87.field.rank_from_scores(transfer_score(base_z,blend,smoothed["pair_interaction"][offset]))
        current[3]=q87.field.rank_from_scores(transfer_score(base_z,reversion,smoothed["node_only"][offset]))
        current[4]=equal
        if any(sorted(row.tolist())!=list(range(1,41)) for row in current):
            raise ValueError("Q90 model rank is not a permutation of 1..40")
        # Freeze every model ranking before the target outcome is read.
        actual=np.asarray(draws[draw_index]["nums"],dtype=np.int64)
        ar=extract_actual_ranks(current,actual)
        ranks[offset]=current
        actual_ranks[offset]=ar
        hits[offset]=np.column_stack([np.sum(ar<=5,axis=1),np.sum(ar<=10,axis=1),np.sum(ar<=20,axis=1)]).astype(np.int8)
        for key,value in diag.items():
            decomposition[key][offset]=value
        previous_features=state["features"]
        previous_edge=edge
        previous_node_delta=node_delta
    split_idx={s:np.asarray([i for i,x in enumerate(labels) if x==s],dtype=np.int64) for s in SPLITS}
    exact_tests=[]
    metrics=[]
    for mi,model in enumerate(MODEL_IDS):
        for split in SPLITS:
            idx=split_idx[split]
            h=hits[idx,mi,:]
            row={"strategy_id":model,"split":split,"targets":int(len(idx)),
                 "mean_hits_top5":float(h[:,0].mean()),"mean_hits_top10":float(h[:,1].mean()),
                 "mean_hits_top20":float(h[:,2].mean()),
                 "mean_rank_actual_numbers":float(actual_ranks[idx,mi,:].mean()),
                 "top20_4plus":int(np.sum(h[:,2]>=4)),"top20_5of5":int(np.sum(h[:,2]==5)),
                 "top20_5of5_rate":float(np.mean(h[:,2]==5)),
                 "top20_hit_distribution":{str(k):int(np.sum(h[:,2]==k)) for k in range(6)},
                 "p_values_raw":{}}
            for j,(endpoint,k) in enumerate(ENDPOINTS):
                p=q87.field.exact_upper_tail(int(h[:,j].sum()),len(idx),k)
                tid=f"Q90|{model}|{split}|{endpoint}"
                exact_tests.append({"test_id":tid,"p_raw":p})
                row["p_values_raw"][endpoint]=p
            metrics.append(row)
    if len(exact_tests)!=45:
        raise ValueError("Q90 exact-null family must contain 45 tests")
    exact_adjusted=q84.holm_adjust(exact_tests)
    for row in metrics:
        row["p_values_holm"]={e:exact_adjusted[f"Q90|{row['strategy_id']}|{row['split']}|{e}"] for e,_ in ENDPOINTS}
    paired=[]
    paired_tests=[]
    focal_index=MODEL_IDS.index(FOCAL)
    for si,split in enumerate(("validation","blind_oos")):
        idx=split_idx[split]
        for ci,comparator in enumerate(COMPARATORS):
            comp_index=MODEL_IDS.index(comparator)
            for j,(endpoint,_) in enumerate(ENDPOINTS):
                z=q84.bootstrap_paired(hits[idx,focal_index,j],hits[idx,comp_index,j],90000+si*1000+ci*100+j)
                tid=f"Q90PAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id":tid,"p_raw":float(z["p_two_sided"])})
                paired.append({"test_id":tid,"split":split,"comparator":comparator,"endpoint":endpoint,**z,
                               "positive_difference_favors_pair_interaction":True})
            z=q84.bootstrap_paired(actual_ranks[idx,comp_index,:].mean(axis=1),
                                   actual_ranks[idx,focal_index,:].mean(axis=1),
                                   90000+si*1000+ci*100+3)
            tid=f"Q90PAIRED|{split}|{comparator}|mean_actual_rank_improvement"
            paired_tests.append({"test_id":tid,"p_raw":float(z["p_two_sided"])})
            paired.append({"test_id":tid,"split":split,"comparator":comparator,
                           "endpoint":"mean_actual_rank_improvement",**z,
                           "positive_difference_means_lower_pair_interaction_rank":True})
    if len(paired_tests)!=32:
        raise ValueError("Q90 paired family must contain 32 tests")
    paired_adjusted=q84.holm_adjust(paired_tests)
    for row in paired:
        row["p_holm"]=paired_adjusted[row["test_id"]]
    def metric(model,split):
        return next(x for x in metrics if x["strategy_id"]==model and x["split"]==split)
    def pair(split,comparator,endpoint):
        return next(x for x in paired if x["split"]==split and x["comparator"]==comparator and x["endpoint"]==endpoint)
    focal_blind=metric(FOCAL,"blind_oos")
    main_blind=metric("Q90::DEGREE_MAIN_TRANSFER","blind_oos")
    equal_blind=metric(BASE,"blind_oos")
    p_main=pair("blind_oos","Q90::DEGREE_MAIN_TRANSFER","top20")
    p_equal=pair("blind_oos",BASE,"top20")
    lift_main=focal_blind["mean_hits_top20"]-main_blind["mean_hits_top20"]
    lift_equal=focal_blind["mean_hits_top20"]-equal_blind["mean_hits_top20"]
    exact_p=focal_blind["p_values_holm"]["top20"]
    gate=(lift_main>=0.10 and p_main["ci95"][0] is not None and p_main["ci95"][0]>0 and p_main["p_holm"]<0.05
          and lift_equal>=0.10 and p_equal["ci95"][0] is not None and p_equal["ci95"][0]>0
          and p_equal["p_holm"]<0.05 and exact_p<0.05)
    primary={"focal_model":FOCAL,"blind_top20_pair_interaction":focal_blind["mean_hits_top20"],
             "blind_top20_degree_main":main_blind["mean_hits_top20"],"blind_top20_equal42":equal_blind["mean_hits_top20"],
             "lift_vs_degree_main":lift_main,"lift_vs_equal42":lift_equal,
             "ci95_vs_degree_main":p_main["ci95"],"paired_p_holm_vs_degree_main":p_main["p_holm"],
             "ci95_vs_equal42":p_equal["ci95"],"paired_p_holm_vs_equal42":p_equal["p_holm"],
             "exact_null_p_holm":exact_p,"status":"PASS" if gate else "NOT_MET"}
    decomposition_summary=[]
    for split in SPLITS:
        idx=split_idx[split]
        decomposition_summary.append({"split":split,"targets":int(len(idx)),
            **{f"mean_{k}":float(decomposition[k][idx].mean()) for k in decomposition},
            "max_residual_row_sum_abs":float(decomposition["residual_row_sum_max_abs"][idx].max()),
            "max_reconstruction_error":float(decomposition["reconstruction_max_abs"][idx].max())})
    blocks=[]
    idx=split_idx["blind_oos"]
    for start in range(0,len(idx),100):
        b=idx[start:start+100]
        if len(b)<40: continue
        blocks.append({"first_target":dates[MIN_HISTORY+int(b[0])],"last_target":dates[MIN_HISTORY+int(b[-1])],
            "targets":int(len(b)),
            "pair_interaction_delta_vs_degree_main":float((hits[b,focal_index,2]-hits[b,MODEL_IDS.index("Q90::DEGREE_MAIN_TRANSFER"),2]).mean()),
            "pair_interaction_delta_vs_equal42":float((hits[b,focal_index,2]-hits[b,MODEL_IDS.index(BASE),2]).mean())})
    return {"draws":draws,"dates":dates,"labels":labels,"counts":counts,"split_idx":split_idx,
            "ranks":ranks,"hits":hits,"actual_ranks":actual_ranks,"signals":signals,"smoothed":smoothed,
            "decomposition":decomposition,"metrics":metrics,"exact_tests":exact_tests,"paired":paired,
            "paired_tests":paired_tests,"primary_gate":primary,"decomposition_summary":decomposition_summary,
            "temporal_blocks":blocks}


def ledger_fields():
    f=["target_date","cutoff_date","prior_draws","actual_quintet","split",
       "edge_delta_mu","edge_delta_rms","edge_main_rms","edge_interaction_rms",
       "interaction_energy_fraction","main_energy_fraction","residual_row_sum_max_abs",
       "reconstruction_max_abs","main_interaction_inner_product"]
    for component in COMPONENTS:
        for n in range(1,41):
            f.extend([f"{component}_transfer_raw_{n:02d}",f"{component}_transfer_ewma_{n:02d}"])
    for model in MODEL_IDS:
        f.extend(f"rank_{slug(model)}_{n:02d}" for n in range(1,41))
    return f


def catalog_entries():
    return [
      {"strategy_id":"Q90::FULL_EDGE_TRANSFER","kind":"FULL_EDGE_COMPONENT","definition":"Q88 signed transfer projected from the complete symmetric edge-change matrix; alpha .20, EWMA20 decay .80."},
      {"strategy_id":"Q90::DEGREE_MAIN_TRANSFER","kind":"ADDITIVE_MAIN_EFFECT_COMPONENT","definition":"Q88 signed transfer projected from E_main[i,j]=mu+a_i+a_j, diagonal zero; alpha .20, EWMA20 decay .80."},
      {"strategy_id":"Q90::PAIR_INTERACTION_TRANSFER","kind":"ZERO_ROW_SUM_PAIR_INTERACTION","definition":"Q88 signed transfer projected from E_pair=E-E_main, symmetric zero diagonal and zero row sums; alpha .20, EWMA20 decay .80. Fixed focal hypothesis."},
      {"strategy_id":"Q90::NODE_ONLY_INERTIA","kind":"GRAPH_FREE_CONTROL","definition":"Signed cosine of current and previous six-feature node deltas; alpha .20, reversion multiplier, EWMA20 decay .80."},
      {"strategy_id":BASE,"kind":"FROZEN_BASELINE","definition":"Equal-weight Borda ranking across the 42 fixed SONAR rules."}
    ]


def write_outputs(result):
    for path in (CATALOG,LEDGER,REPORT,MANIFEST,CHECKPOINT,VALIDATION):
        if path.exists():
            raise SystemExit("Q90 append-only output already exists: "+str(path.relative_to(ROOT)))
    with CATALOG.open("w",encoding="utf-8",newline="") as f:
        for item in catalog_entries():
            f.write(json.dumps(item,sort_keys=True,separators=(",",":"))+"\n")
    fields=ledger_fields()
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as handle:
                writer=csv.DictWriter(handle,fieldnames=fields)
                writer.writeheader()
                for t,date in enumerate(result["dates"][MIN_HISTORY:]):
                    i=MIN_HISTORY+t
                    row={"target_date":date,"cutoff_date":result["dates"][i-1],"prior_draws":i,
                         "actual_quintet":" ".join(map(str,sorted(result["draws"][i]["nums"]))),
                         "split":result["labels"][t]}
                    d=result["decomposition"]
                    for key,column in (("mu","edge_delta_mu"),("edge_rms","edge_delta_rms"),("main_rms","edge_main_rms"),
                        ("interaction_rms","edge_interaction_rms"),("interaction_energy_fraction","interaction_energy_fraction"),
                        ("main_energy_fraction","main_energy_fraction"),("residual_row_sum_max_abs","residual_row_sum_max_abs"),
                        ("reconstruction_max_abs","reconstruction_max_abs"),("main_interaction_inner_product","main_interaction_inner_product")):
                        row[column]=format(float(d[key][t]),".17g")
                    for component in COMPONENTS:
                        for n in range(1,41):
                            row[f"{component}_transfer_raw_{n:02d}"]=format(float(result["signals"][component][t,n-1]),".17g")
                            row[f"{component}_transfer_ewma_{n:02d}"]=format(float(result["smoothed"][component][t,n-1]),".17g")
                    for mi,model in enumerate(MODEL_IDS):
                        for n in range(1,41):
                            row[f"rank_{slug(model)}_{n:02d}"]=int(result["ranks"][t,mi,n-1])
                    writer.writerow(row)
    report={
      "task_id":TASK_ID,"generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "source_archive":{"draws":len(result["draws"]),"first_date":result["dates"][0],"last_date":result["dates"][-1],
                        "git_blob_sha1":q84.git_blob_sha1(ARCHIVE),"sha256":sha256_file(ARCHIVE)},
      "target_design":{"targets":len(result["labels"]),"split_counts":result["counts"],"minimum_prior_draws":MIN_HISTORY,
                       "cutoff_rule":"draws[:i] only; all five rankings frozen before reading draw i"},
      "hypothesis":"The zero-row-sum pair-specific edge interaction residual adds predictive information beyond additive degree/main effects and node-only inertia.",
      "decomposition":{"formula":"mu=mean off-diagonal E; a_i=(row_sum_i-39*mu)/38; E_main_ij=mu+a_i+a_j (i!=j); E_pair=E-E_main.",
                       "invariants":"E_main+E_pair=E; E_pair symmetric, zero diagonal, zero row sums; main and residual are Frobenius-orthogonal."},
      "frozen_parameters":{"alpha":ALPHA,"window":WINDOW,"decay":DECAY,"models":list(MODEL_IDS)},
      "metrics":result["metrics"],"exact_null_holm_tests":result["exact_tests"],
      "paired_block_bootstrap":result["paired"],"paired_holm_tests":result["paired_tests"],
      "primary_gate":result["primary_gate"],"decomposition_diagnostics":result["decomposition_summary"],
      "blind_temporal_blocks":result["temporal_blocks"],
      "limitations":["Historical Blind OOS is prior-exposed and exploratory, not virgin prospective confirmation.",
        "The pair graph is a statistical co-occurrence descriptor, not physical coupling or causal evidence.",
        "Exact hypergeometric null assumes independent targets; paired moving-block bootstrap separately addresses serial dependence.",
        "Only one fixed Q88 transfer operator and one decomposition were tested; the wider formula universe is not exhausted."]
    }
    dump(REPORT,report)
    manifest={"task_id":TASK_ID,"status":"COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
      "source_archive_git_blob_sha1":q84.git_blob_sha1(ARCHIVE),"source_archive_sha256":sha256_file(ARCHIVE),
      "draws":len(result["draws"]),"targets":len(result["labels"]),"models":len(MODEL_IDS),
      "exact_null_holm_tests":len(result["exact_tests"]),"paired_holm_tests":len(result["paired_tests"]),
      "ledger_rows":len(result["labels"]),"ledger_fields":len(fields),"files":{}}
    for key,path in (("catalog",CATALOG),("target_ledger",LEDGER),("report",REPORT),("protocol",PROTOCOL)):
        data=path.read_bytes()
        manifest["files"][key]={"path":str(path.relative_to(ROOT)),"bytes":len(data),"sha256":sha256_bytes(data)}
    checkpoint=f"""# Q90 Edge-Field Decomposition — execution checkpoint

- Task: {TASK_ID}
- State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE
- Archive: {len(result["draws"])} draws, {result["dates"][0]} through {result["dates"][-1]}
- Strict-prior targets: {len(result["labels"])}; splits: {result["counts"]}
- Models: {", ".join(MODEL_IDS)}
- Exact-null Holm family: {len(result["exact_tests"])}; paired block-bootstrap Holm family: {len(result["paired_tests"])}
- Primary historical Blind OOS gate: {result["primary_gate"]["status"]}
- Pair-interaction Top20 lift vs degree-main: {result["primary_gate"]["lift_vs_degree_main"]:.8f}
- Pair-interaction Top20 lift vs Equal42: {result["primary_gate"]["lift_vs_equal42"]:.8f}

## Next action

Run the independent validator, persist the catalog/ledger/report/manifest/checkpoint/validation append-only, read back exact bytes, and replay on the persisted head. Historical Blind OOS remains exploratory; no promotion or freeze changes.
"""
    CHECKPOINT.write_text(checkpoint,encoding="utf-8")
    # Include the checkpoint in the manifest after it is written.
    data=CHECKPOINT.read_bytes()
    manifest["files"]["checkpoint"]={"path":str(CHECKPOINT.relative_to(ROOT)),"bytes":len(data),"sha256":sha256_bytes(data)}
    dump(MANIFEST,manifest)
    print("SONAR_Q90_COMPUTE_BEGIN")
    print(json.dumps({"status":manifest["status"],"targets":manifest["targets"],"split_counts":result["counts"],
        "models":manifest["models"],"exact_tests":manifest["exact_null_holm_tests"],"paired_tests":manifest["paired_holm_tests"],
        "primary_gate":result["primary_gate"]},sort_keys=True,separators=(",",":")))
    print("SONAR_Q90_COMPUTE_END")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--compute-only",action="store_true")
    args=p.parse_args()
    if q84.git_blob_sha1(ARCHIVE)!=EXPECTED_ARCHIVE_GIT_BLOB_SHA1:
        raise SystemExit("Q90 archive blob SHA mismatch; protocol is pinned to the canonical archive.")
    if not PROTOCOL.is_file():
        raise SystemExit("Q90 preregistration file missing")
    protocol=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("status")!="PREREGISTERED_PENDING_EXECUTION" or protocol.get("source_archive",{}).get("git_blob_sha1")!=EXPECTED_ARCHIVE_GIT_BLOB_SHA1:
        raise SystemExit("Q90 preregistration/archive mismatch")
    write_outputs(compute_experiment())
if __name__=="__main__":
    main()
