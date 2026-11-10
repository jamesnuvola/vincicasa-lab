#!/usr/bin/env python3
"""Q95: constrained node-label permutation null for prior-only spectral persistence."""
from __future__ import annotations
import csv, gzip, hashlib, io, json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import sonar_q87_node_graph_phase_lag as q87
import sonar_q90_edge_field_decomposition as q90
import sonar_q93_spectral_coherence as q93
import sonar_q94_spectral_subspace_persistence as q94

ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"reports"/"sequence_agent"; ARCHIVE=ROOT/"data"/"storico_daily.csv"
PROTOCOL=OUT/"q95_subspace_permutation_null_protocol_2026-11-10.json"
CATALOG=OUT/"q95_subspace_permutation_null_catalog.jsonl"
LEDGER=OUT/"q95_subspace_permutation_null_target_ledger.csv.gz"
REPORT=OUT/"q95_subspace_permutation_null_report.json"
MANIFEST=OUT/"q95_subspace_permutation_null_manifest.json"
CHECKPOINT=OUT/"q95_subspace_permutation_null_checkpoint_2026-11-10.md"
VALIDATION=OUT/"q95_subspace_permutation_null_validation.json"
TASK_ID="Q95-SPECTRAL-SUBSPACE-PERMUTATION-NULL-01"
MIN_HISTORY=q94.MIN_HISTORY; MODES=q94.REQUESTED_MODES
PERM_COUNT=999; PERM_SEED=9501; SHIFT_COUNT=999; SHIFT_SEED=9502
BLOCK=20; REPS=2000; SPLITS=("discovery","validation","blind_oos")

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def dump(path,obj): path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")

def verify_sources():
    m=json.loads(q94.MANIFEST.read_text()); v=json.loads(q94.VALIDATION.read_text())
    if m.get("status")!="ACCEPTANCE_PASS" or v.get("status")!="PASS": raise ValueError("Q95 blocked: Q94 not accepted")
    for key in ("catalog","target_ledger","report","protocol","checkpoint","validation"):
        meta=m.get("files",{}).get(key)
        if not meta: raise ValueError("Q95 Q94 manifest missing "+key)
        p=ROOT/meta["path"]
        if p.stat().st_size!=meta["bytes"] or sha(p)!=meta["sha256"]: raise ValueError("Q95 Q94 hash mismatch "+key)
    rows, q93sha=q94.read_q93_ledger()
    return rows,q93sha,sha(q94.MANIFEST),sha(q94.VALIDATION)

def fixed_permutations():
    rng=np.random.default_rng(PERM_SEED); identity=tuple(range(40)); seen=set(); out=[]
    while len(out)<PERM_COUNT:
        p=tuple(map(int,rng.permutation(40)))
        if p!=identity and p not in seen: seen.add(p); out.append(p)
    a=np.asarray(out,dtype=np.int16)
    if a.shape!=(PERM_COUNT,40): raise ValueError("Q95 permutation shape")
    return a

def permuted_basis(basis,p):
    basis=np.asarray(basis,dtype=np.float64); p=np.asarray(p,dtype=np.int64)
    if basis.ndim!=2 or basis.shape[0]!=40 or p.shape!=(40,) or sorted(p.tolist())!=list(range(40)): raise ValueError("Q95 invalid basis/permutation")
    v=basis[p,:].copy()
    if v.shape[1] and np.max(np.abs(v.T@np.ones(40)))>1e-8: raise ValueError("Q95 permutation left 1-orthogonal space")
    return v

def overlap_many(current,previous,perms):
    if not current.shape[1] or not previous.shape[1]: return np.zeros(len(perms))
    vp=previous[perms.astype(np.int64),:]
    cross=np.einsum("ia,pib->pab",current,vp,optimize=True)
    x=np.sum(cross*cross,axis=(1,2))/float(min(current.shape[1],previous.shape[1]))
    if not np.isfinite(x).all() or np.any(x < -1e-10) or np.any(x > 1+1e-8): raise ValueError("Q95 overlap outside [0,1]")
    return np.clip(x,0,1)

def average_ranks(x):
    x=np.asarray(x,dtype=float)
    if x.ndim!=1 or not np.isfinite(x).all(): raise ValueError("Q95 invalid rank input")
    order=np.argsort(x,kind="mergesort"); r=np.empty(len(x)); i=0
    while i<len(x):
        j=i+1
        while j<len(x) and x[order[j]]==x[order[i]]: j+=1
        r[order[i:j]]=(i+1+j)/2.0; i=j
    return r

def spearman(x,y):
    x=np.asarray(x,dtype=float); y=np.asarray(y,dtype=float)
    if x.shape!=y.shape or x.ndim!=1 or len(x)<3: raise ValueError("Q95 invalid Spearman arrays")
    a,b=average_ranks(x),average_ranks(y)
    return 0.0 if np.std(a)==0 or np.std(b)==0 else float(np.corrcoef(a,b)[0,1])

def block_indices(n,rng):
    starts=rng.integers(0,n,size=int(np.ceil(n/BLOCK)))
    return np.concatenate([(s+np.arange(BLOCK))%n for s in starts])[:n]

def bootstrap_ci(x,y=None,kind="mean",seed=9503):
    x=np.asarray(x,dtype=float); y=None if y is None else np.asarray(y,dtype=float)
    rng=np.random.default_rng(seed); vals=np.empty(REPS)
    for b in range(REPS):
        ix=block_indices(len(x),rng)
        vals[b]=np.mean(x[ix]) if kind=="mean" else spearman(x[ix],y[ix])
    return [float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]

def shift_offsets(n,seed):
    a=np.arange(1,n,dtype=np.int64); k=min(SHIFT_COUNT,len(a))
    return a if k==len(a) else np.sort(np.random.default_rng(seed).choice(a,k,replace=False))

def holm(tests): return q94.holm(tests)

def ledger_fields():
    f=["target_date","cutoff_date","prior_draws","actual_quintet","split","current_modes","previous_modes","observed_overlap","permutation_mean","permutation_sd","permutation_q95","q93_top20_hits","equal42_top20_hits","q93_minus_equal42_top20"]
    return f+[f"perm_overlap_{i:04d}" for i in range(PERM_COUNT)]

def compute_experiment(draws=None):
    draws=q87.read_draws() if draws is None else draws
    dates=[d["date"].isoformat() for d in draws]
    sha1=q90.q84.git_blob_sha1(ARCHIVE); sha256=sha(ARCHIVE)
    if sha1!=q94.EXPECTED_SHA1 or sha256!=q94.EXPECTED_SHA256 or len(draws)!=q94.EXPECTED_DRAWS or dates[0]!=q94.EXPECTED_FIRST or dates[-1]!=q94.EXPECTED_LAST: raise ValueError("Q95 canonical archive identity mismatch")
    q93rows,q93sha,q94msha,q94vsha=verify_sources()
    n=len(draws)-MIN_HISTORY; labels=q93.split_labels(n); counts=dict(Counter(labels))
    expected={"discovery":1921,"validation":641,"blind_oos":641}
    if n!=3203 or counts!=expected or len(q93rows)!=n: raise ValueError("Q95 target/split mismatch")
    perms=fixed_permutations(); obs=np.zeros(n); pv=np.zeros((n,PERM_COUNT)); cm=np.zeros(n,dtype=np.int16); pm=np.zeros(n,dtype=np.int16)
    prev_edge=None; prev_vec=np.zeros((40,0))
    for off,i in enumerate(range(MIN_HISTORY,len(draws))):
        hist=draws[:i]
        edge=q87.field.pair_residual_graph(hist)
        if prev_edge is None: cur=np.zeros((40,0))
        else:
            _,resid,_=q90.decompose_edge_change(edge-prev_edge)
            _,cur,_=q93.spectral_modes(resid,MODES)
        cm[off]=cur.shape[1]; pm[off]=prev_vec.shape[1]
        obs[off]=q94.subspace_overlap(cur,prev_vec)
        pv[off]=overlap_many(cur,prev_vec,perms)
        prev_edge=edge; prev_vec=cur.copy()
    q94obs,q94cm,q94pm=q94.compute_stability(draws)
    if not np.allclose(obs,q94obs,atol=1e-12,rtol=0) or not np.array_equal(cm,q94cm) or not np.array_equal(pm,q94pm): raise ValueError("Q95 does not reproduce Q94 prior-only subspace sequence")
    adv=np.zeros(n,dtype=np.int8); qh=np.zeros(n,dtype=np.int8); eh=np.zeros(n,dtype=np.int8); rows=[]
    for off,i in enumerate(range(MIN_HISTORY,len(draws))):
        src=q93rows[off]; td=dates[i]; cd=dates[i-1]
        if src.get("target_date")!=td or src.get("cutoff_date")!=cd or int(src.get("prior_draws","-1"))!=i or src.get("split")!=labels[off]: raise ValueError("Q95 source cutoff mismatch "+td)
        er=q94.parse_rank(src,"BASE::EQUAL42"); sr=q94.parse_rank(src,"Q93::SPECTRAL_K2")
        actual=sorted(map(int,draws[i]["nums"]))
        if len(actual)!=5 or len(set(actual))!=5 or min(actual)<1 or max(actual)>40 or src.get("actual_quintet")!=" ".join(map(str,actual)): raise ValueError("Q95 target outcome mismatch "+td)
        e=q94.rank_hits(er,actual)[0][2]; s=q94.rank_hits(sr,actual)[0][2]
        eh[off]=e; qh[off]=s; adv[off]=s-e
        nv=pv[off]
        row={"target_date":td,"cutoff_date":cd,"prior_draws":str(i),"actual_quintet":" ".join(map(str,actual)),"split":labels[off],
             "current_modes":str(int(cm[off])),"previous_modes":str(int(pm[off])),
             "observed_overlap":format(obs[off],".17g"),"permutation_mean":format(nv.mean(),".17g"),
             "permutation_sd":format(nv.std(ddof=1),".17g"),"permutation_q95":format(np.quantile(nv,.95),".17g"),
             "q93_top20_hits":str(int(s)),"equal42_top20_hits":str(int(e)),"q93_minus_equal42_top20":str(int(s-e))}
        row.update({f"perm_overlap_{j:04d}":format(float(v),".17g") for j,v in enumerate(nv)})
        rows.append(row)
    idxs={s:np.asarray([i for i,l in enumerate(labels) if l==s],dtype=int) for s in SPLITS}
    ptests=[]; stests=[]; summaries=[]
    for si,split in enumerate(SPLITS):
        ix=idxs[split]; x=obs[ix]; null=pv[ix]; null_means=null.mean(axis=0); target_null=null.mean(axis=1); excess=x-target_null
        pp=(1+float(np.sum(null_means>=x.mean())))/(1+PERM_COUNT)
        pid=f"Q95PERM|{split}"; ptests.append({"test_id":pid,"p_raw":pp})
        ci_ex=bootstrap_ci(excess,seed=95030+si)
        y=adv[ix].astype(float); rho=spearman(x,y); shifts=shift_offsets(len(ix),SHIFT_SEED+si)
        nullrho=np.asarray([spearman(x,np.roll(y,int(k))) for k in shifts])
        sp=(1+float(np.sum(np.abs(nullrho)>=abs(rho))))/(1+len(shifts))
        sid=f"Q95SHIFT|{split}"; stests.append({"test_id":sid,"p_raw":sp})
        ci_rho=bootstrap_ci(x,y,"spearman",95040+si)
        summaries.append({"split":split,"targets":int(len(ix)),
          "observed_overlap_mean":float(x.mean()),"observed_overlap_median":float(np.median(x)),
          "permutation_null_mean":float(null_means.mean()),"permutation_null_sd":float(null_means.std(ddof=1)),
          "permutation_null_q95":float(np.quantile(null_means,.95)),
          "mean_observed_minus_target_null":float(excess.mean()),"mean_excess_block_bootstrap_ci95":ci_ex,
          "permutation_p_raw":pp,"permutation_count":PERM_COUNT,
          "mean_q93_top20_hits":float(qh[ix].mean()),"mean_equal42_top20_hits":float(eh[ix].mean()),
          "mean_q93_minus_equal42_top20":float(y.mean()),
          "overlap_vs_future_q93_top20_advantage_spearman":rho,"spearman_block_bootstrap_ci95":ci_rho,
          "circular_shift_count":int(len(shifts)),"circular_shift_p_raw":sp,
          "circular_shift_null_abs_q95":float(np.quantile(np.abs(nullrho),.95)),
          "mean_current_modes":float(cm[ix].mean()),"mean_previous_modes":float(pm[ix].mean()),
          "empty_current_subspaces":int(np.sum(cm[ix]==0)),"empty_previous_subspaces":int(np.sum(pm[ix]==0))})
    tests=ptests+stests; adj=holm(tests)
    for t in tests: t["p_holm"]=adj[t["test_id"]]
    for r in summaries:
        r["permutation_p_holm"]=adj[f"Q95PERM|{r['split']}"]
        r["circular_shift_p_holm"]=adj[f"Q95SHIFT|{r['split']}"]
    gate_rows=[r for r in summaries if r["split"] in ("validation","blind_oos")]
    passed=all(r["mean_observed_minus_target_null"]>0 and r["mean_excess_block_bootstrap_ci95"][0]>0 and r["permutation_p_holm"]<.05 and r["overlap_vs_future_q93_top20_advantage_spearman"]>0 and r["spearman_block_bootstrap_ci95"][0]>0 and r["circular_shift_p_holm"]<.05 for r in gate_rows)
    gate={"status":"PERSISTENCE_AND_ASSOCIATION_SUPPORTED" if passed else "NOT_SUPPORTED","required_splits":["validation","blind_oos"],"engine_promotion_allowed":False}
    return {"labels":labels,"counts":counts,"observed":obs,"permutation_values":pv,"ledger_rows":rows,"split_results":summaries,"holm_tests":tests,"primary_gate":gate,"archive_sha1":sha1,"archive_sha256":sha256,"q93_ledger_sha256":q93sha,"q94_manifest_sha256":q94msha,"q94_validation_sha256":q94vsha}

def write_outputs(r):
    for p in (CATALOG,LEDGER,REPORT,MANIFEST,CHECKPOINT,VALIDATION):
        if p.exists(): raise SystemExit("Q95 append-only output exists: "+str(p.relative_to(ROOT)))
    proto=json.loads(PROTOCOL.read_text())
    if proto.get("task_id")!=TASK_ID or proto.get("status")!="PREREGISTERED_PENDING_EXECUTION": raise ValueError("Q95 protocol mismatch")
    entries=[{"id":"OBSERVED_LABEL_OVERLAP","role":"observed consecutive leading k=2 subspace overlap"},{"id":"CONSTRAINED_NODE_LABEL_NULL","role":"999 fixed node-label permutations applied to previous basis"},{"id":"Q93_MINUS_EQUAL42_TOP20","role":"post-forecast outcome advantage used only for association analysis"}]
    with CATALOG.open("w",encoding="utf-8") as f:
        for e in entries: f.write(json.dumps(e,sort_keys=True,separators=(",",":"))+"\n")
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=ledger_fields()); w.writeheader(); w.writerows(r["ledger_rows"])
    report={"task_id":TASK_ID,"status":"COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE","scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "source_archive":{"draws":q94.EXPECTED_DRAWS,"first_date":q94.EXPECTED_FIRST,"last_date":q94.EXPECTED_LAST,"git_blob_sha1":r["archive_sha1"],"sha256":r["archive_sha256"]},
      "source_q93_ledger_sha256":r["q93_ledger_sha256"],"source_q94_manifest_sha256":r["q94_manifest_sha256"],"source_q94_validation_sha256":r["q94_validation_sha256"],
      "target_counts":r["counts"],"hypothesis":"Observed consecutive leading k=2 overlap exceeds a constrained node-label permutation null and prior-only overlap positively predicts Q93-vs-Equal42 Top20 advantage.",
      "frozen_parameters":{"requested_modes":MODES,"permutation_count":PERM_COUNT,"permutation_seed":PERM_SEED,"shift_count":SHIFT_COUNT,"shift_seed":SHIFT_SEED,"bootstrap_block_length":BLOCK,"bootstrap_replicates":REPS,
        "permutation_null":"permute previous-basis node labels only; preserve orthonormality and all-ones-orthogonal subspace",
        "association":"Spearman overlap vs target Q93 minus Equal42 Top20 hits","multiple_testing":"one global Holm family of six split-level tests"},
      "split_results":r["split_results"],"global_holm_tests":r["holm_tests"],"primary_gate":r["primary_gate"],
      "guardrails":["Q93/Q94 sources acceptance-verified before use","current and previous subspaces use strict prefixes draws[:i] only","permutations and circular shifts are inferential only, never forecasts","target outcome read after overlap is frozen","one global Holm family of six tests","historical Blind OOS is exploratory, not virgin holdout","no freeze changes or model promotion"],
      "limitations":["Constrained label permutation is not a Haar null or universal graph null","overlap is geometric, not causal","outcome association is post-forecast and non-causal","failure to reject does not prove absence of all graph structure","Q60 still requires 200 prospective paired targets"]}
    dump(REPORT,report)
    checkpoint=("# SONAR Q95 constrained spectral-subspace permutation null — checkpoint\n\n"
      f"- Task: {TASK_ID}\n- State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE\n"
      f"- Archive: {q94.EXPECTED_DRAWS} draws, {q94.EXPECTED_FIRST} through {q94.EXPECTED_LAST}\n"
      f"- Strict-prior targets: {len(r['labels'])}; splits: {r['counts']}\n- Fixed node-label permutations: {PERM_COUNT}; seed: {PERM_SEED}\n"
      f"- Global Holm family: {len(r['holm_tests'])} tests\n- Diagnostic gate: {r['primary_gate']['status']}\n"
      f"- Q93 ledger SHA-256: {r['q93_ledger_sha256']}\n- Q94 manifest SHA-256: {r['q94_manifest_sha256']}\n\n"
      "## Statistical design amendment before execution\n\n"
      "The earlier proposal specified 99 permutations. Before any Q95 outcome analysis, the count was raised to 999 because a six-test Holm family with 99 permutations has a minimum attainable adjusted p-value of 0.06, making alpha=0.05 unattainable. Seeds and constrained transformation are unchanged. Validation and historical Blind OOS use all 640 nonzero circular shifts.\n\n"
      "## Next action\n\nRun independent replay, append-only persist all evidence, verify exact Git bytes and replay the persisted head read-only. Historical Blind OOS remains exploratory. No promotion, merge or freeze changes.\n")
    CHECKPOINT.write_text(checkpoint)
    files={"catalog":CATALOG,"target_ledger":LEDGER,"report":REPORT,"protocol":PROTOCOL,"checkpoint":CHECKPOINT}
    manifest={"task_id":TASK_ID,"status":"COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE","generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_archive_git_blob_sha1":r["archive_sha1"],"source_archive_sha256":r["archive_sha256"],"source_q93_ledger_sha256":r["q93_ledger_sha256"],
      "source_q94_manifest_sha256":r["q94_manifest_sha256"],"source_q94_validation_sha256":r["q94_validation_sha256"],
      "draws":q94.EXPECTED_DRAWS,"targets":len(r["labels"]),"split_counts":r["counts"],"permutations":PERM_COUNT,"ledger_fields":len(ledger_fields()),
      "files":{k:{"path":str(p.relative_to(ROOT)),"bytes":p.stat().st_size,"sha256":sha(p)} for k,p in files.items()}}
    dump(MANIFEST,manifest)
    print(json.dumps({"task_id":TASK_ID,"status":"COMPUTED","targets":len(r["labels"]),"splits":r["counts"],"permutations":PERM_COUNT,"permutation_values":int(r["permutation_values"].size),"holm_tests":len(r["holm_tests"]),"primary_gate":r["primary_gate"]["status"],"ledger_bytes":LEDGER.stat().st_size},sort_keys=True))

def main(): write_outputs(compute_experiment())
if __name__=="__main__": main()
