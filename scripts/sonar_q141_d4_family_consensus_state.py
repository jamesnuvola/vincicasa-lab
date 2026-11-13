#!/usr/bin/env python3
"""Q141-D4: pre-target family-consensus state under inter-family disagreement."""
from __future__ import annotations
import argparse, hashlib, io, json, math, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

Q90_ZIP_SHA256 = "12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"
A6_ZIP_SHA256 = "e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc"
MATRIX_SHA256 = "681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49"
FEATURE_CATALOG_SHA256 = "0761324a35faade7e5dc9a053d19146f21d349ba9e8237b334691c6b1e5517a5"
A6_LEDGER_SHA256 = "3db21ad7a0d94f3d07f437865282ed306d0a022d9f313095fa4bedbb66d5b32b"
WINDOW, BLOCK, BOOTSTRAPS, RANDOMIZATIONS, SEED = 100, 20, 20000, 20000, 14120261113
UNIFORM_EXPECTED_HITS, PRACTICAL_THRESHOLD = 0.625, 0.025
SPLIT_COUNTS = {"discovery": 2011, "validation": 670, "blind_oos": 670}

def sha256_bytes(data): return hashlib.sha256(data).hexdigest()
def git_blob_sha1(data): return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def build_family_groups(feature_names, family_map):
    names = list(feature_names)
    if len(names) != 59 or len(set(names)) != 59: raise ValueError("expected 59 unique feature names")
    if set(family_map) - set(names): raise ValueError("family map contains unknown features")
    groups = {"baseline_legacy":[i for i,n in enumerate(names) if n not in family_map]}
    for family in ["ewma_hit_dynamics","gap_dynamics","cooccurrence_novelty","rank_trajectory","residual_surprise","regime_transition_affinity"]:
        groups[family] = [i for i,n in enumerate(names) if family_map.get(n)==family]
    flat = [i for v in groups.values() for i in v]
    if sorted(flat)!=list(range(59)) or len(flat)!=len(set(flat)): raise ValueError("families do not partition 59 columns")
    if any(not v for v in groups.values()): raise ValueError("empty family")
    return groups

def top5_from_scores(scores):
    x=np.asarray(scores,dtype=np.float64)
    if x.shape!=(40,) or not np.isfinite(x).all(): raise ValueError("expected 40 finite scores")
    return np.lexsort((np.arange(1,41),-np.round(x,12)))[:5]+1

def jaccard(a,b):
    sa,sb=set(map(int,a)),set(map(int,b))
    if not sa or not sb: raise ValueError("Jaccard sets must be non-empty")
    return len(sa&sb)/len(sa|sb)

def target_family_state(row,groups):
    x=np.asarray(row,dtype=np.float64)
    if x.shape!=(40,59) or not np.isfinite(x).all(): raise ValueError("expected finite 40x59 row")
    names=list(groups)
    fs=np.stack([x[:,groups[name]].mean(axis=1) for name in names],axis=0)
    tops=[top5_from_scores(fs[i]) for i in range(len(names))]
    agree=float(np.mean([jaccard(tops[i],tops[j]) for i in range(7) for j in range(i+1,7)]))
    mean_score=fs.mean(axis=0)
    equal=top5_from_scores(mean_score)
    votes=np.zeros(40,dtype=np.int64)
    for selected in tops: votes[np.asarray(selected,dtype=int)-1]+=1
    consensus=np.lexsort((np.arange(1,41),-np.round(mean_score,12),-votes))[:5]+1
    equal59=top5_from_scores(x.mean(axis=1))
    return {"family_scores":fs,"family_top5":tops,"agreement":agree,
            "equal_family_top5":equal,"consensus_top5":consensus,"equal59_top5":equal59,"votes":votes}

def build_disagreement_state(agreement,window=WINDOW):
    a=np.asarray(agreement,dtype=np.float64)
    thresholds=np.full(len(a),np.nan); state=np.full(len(a),-1,dtype=np.int8)
    for t in range(window,len(a)):
        thresholds[t]=float(np.median(a[t-window:t]))
        state[t]=int(a[t]<thresholds[t])
    return thresholds,state

def count_hits(top5,actual): return int(len(set(map(int,top5))&set(map(int,actual))))

def hypergeom_5of40_pmf():
    from math import comb
    den=comb(40,5)
    p=np.array([comb(5,k)*comb(35,5-k)/den for k in range(6)],dtype=np.float64)
    if abs(float(p.sum())-1)>1e-14: raise AssertionError("hypergeometric PMF mass")
    return p

def exact_uniform_upper_tail(total_hits,targets):
    dist=np.array([1.0])
    for _ in range(targets): dist=np.convolve(dist,hypergeom_5of40_pmf())
    if total_hits<0 or total_hits>=len(dist): raise ValueError("total outside support")
    return float(dist[total_hits:].sum())

def circular_block_bootstrap(values,state=None,replicates=BOOTSTRAPS,block=BLOCK,seed=SEED,estimand="mean"):
    y=np.asarray(values,dtype=np.float64); h=None if state is None else np.asarray(state,dtype=np.int8)
    n=len(y)
    if n==0 or (h is not None and len(h)!=n): raise ValueError("invalid bootstrap inputs")
    rng=np.random.default_rng(seed); nb=int(math.ceil(n/block))
    starts=rng.integers(0,n,size=(replicates,nb)); offsets=np.arange(block,dtype=np.int64)
    effects=np.empty(replicates)
    for b in range(replicates):
        idx=((starts[b,:,None]+offsets[None,:])%n).reshape(-1)[:n]
        yb=y[idx]
        if estimand=="mean": effects[b]=yb.mean()
        elif estimand=="high_minus_low":
            hb=h[idx]
            effects[b]=np.nan if hb.sum()==0 or hb.sum()==len(hb) else yb[hb==1].mean()-yb[hb==0].mean()
        else: raise ValueError("unknown estimand")
    effects=effects[np.isfinite(effects)]
    if len(effects)<int(replicates*.99): raise RuntimeError("degenerate bootstrap replicates")
    return [float(v) for v in np.quantile(effects,[.025,.975])]

def circular_shift_p(values,state,replicates=RANDOMIZATIONS,seed=SEED+1):
    y=np.asarray(values,dtype=np.float64); h=np.asarray(state,dtype=np.int8)
    observed=abs(float(y[h==1].mean()-y[h==0].mean()))
    rng=np.random.default_rng(seed); shifts=rng.integers(1,len(y),size=replicates); extreme=0
    for shift in shifts:
        hs=np.roll(h,int(shift))
        if hs.min()==hs.max(): continue
        effect=abs(float(y[hs==1].mean()-y[hs==0].mean()))
        if effect>=observed-1e-15: extreme+=1
    return float((extreme+1)/(replicates+1))

def block_signflip_p(values,replicates=RANDOMIZATIONS,block=BLOCK,seed=SEED+2):
    y=np.asarray(values,dtype=np.float64)
    blocks=np.array_split(np.arange(len(y)),int(math.ceil(len(y)/block)))
    sums=np.array([y[idx].sum() for idx in blocks],dtype=np.float64)
    observed=abs(float(y.mean())); rng=np.random.default_rng(seed)
    signs=rng.choice(np.array([-1.,1.]),size=(replicates,len(sums)))
    sim=np.abs(signs@sums/len(y))
    return float((np.count_nonzero(sim>=observed-1e-15)+1)/(replicates+1))

def holm_adjust(p_values):
    p=np.asarray(p_values,dtype=np.float64); order=np.argsort(p); out=np.empty(len(p)); running=0.
    for rank,idx in enumerate(order):
        running=max(running,(len(p)-rank)*float(p[idx])); out[idx]=min(1.,running)
    return [float(v) for v in out]

def load_inputs(q90_zip,a6_zip):
    q90_bytes=q90_zip.read_bytes(); a6_bytes=a6_zip.read_bytes()
    if sha256_bytes(q90_bytes)!=Q90_ZIP_SHA256: raise ValueError("Q90 ZIP digest mismatch")
    if sha256_bytes(a6_bytes)!=A6_ZIP_SHA256: raise ValueError("A6 ZIP digest mismatch")
    with zipfile.ZipFile(io.BytesIO(q90_bytes)) as zq, zipfile.ZipFile(io.BytesIO(a6_bytes)) as za:
        mb=zq.read("adaptive_novelty_feature_matrix.npz"); cb=zq.read("adaptive_novelty_feature_catalog.json")
        lb=za.read("q141_a6_target_ledger_2026-11-13.csv")
        manifest=json.loads(za.read("q141_a6_full59_covering_manifest_2026-11-13.json"))
        report_a6=json.loads(za.read("q141_a6_full59_covering_report_2026-11-13.json"))
        if sha256_bytes(mb)!=MATRIX_SHA256: raise ValueError("matrix digest mismatch")
        if sha256_bytes(cb)!=FEATURE_CATALOG_SHA256: raise ValueError("feature catalog digest mismatch")
        if sha256_bytes(lb)!=A6_LEDGER_SHA256: raise ValueError("A6 ledger digest mismatch")
        if manifest["source_artifact_sha256"]!=Q90_ZIP_SHA256: raise ValueError("A6 manifest source mismatch")
        if report_a6["source"]["q90_archive_blob_sha1"]!="5d2efd70684e918b27d8f06386d545647898336d": raise ValueError("Q90 archive lineage mismatch")
        z=np.load(io.BytesIO(mb),allow_pickle=False); matrix=z["feature_matrix"]; dates=z["target_dates"].astype(str); cutoffs=z["cutoff_dates"].astype(str)
        actual=z["actual_quintets"].astype(np.int64); names=z["feature_names"].astype(str).tolist(); archive_blob=str(z["archive_blob_sha"].item())
        catalog=json.loads(cb); ledger=pd.read_csv(io.BytesIO(lb))
    if matrix.shape!=(3351,40,59) or matrix.dtype!=np.float32 or not np.isfinite(matrix).all(): raise ValueError("matrix shape/dtype/finite check")
    if archive_blob!="5d2efd70684e918b27d8f06386d545647898336d": raise ValueError("matrix archive blob mismatch")
    if len(ledger)!=len(matrix): raise ValueError("target count mismatch")
    ledger_dates=ledger.target_date.astype(str).to_numpy(); ledger_cutoffs=ledger.cutoff_date.astype(str).to_numpy()
    ledger_actual=np.array([[int(v) for v in str(s).split()] for s in ledger.actual_quintet],dtype=np.int64)
    if not np.array_equal(dates,ledger_dates) or not np.array_equal(cutoffs,ledger_cutoffs) or not np.array_equal(actual,ledger_actual): raise ValueError("Q90/A6 row alignment mismatch")
    if not np.all(cutoffs<dates): raise ValueError("cutoff not strictly before target")
    if not np.array_equal(ledger.prior_draws.to_numpy(dtype=int),np.arange(len(ledger))+50): raise ValueError("prior draw count mismatch")
    if ledger.split.value_counts().to_dict()!=SPLIT_COUNTS: raise ValueError("split counts mismatch")
    if catalog["formula_search_matrix"]["normalization"]!="per-target feature z-score across the 40 candidate numbers; strictly prior-only": raise ValueError("feature lineage mismatch")
    groups=build_family_groups(names,catalog["new_feature_family_map"])
    source={"q90_zip_sha256":Q90_ZIP_SHA256,"a6_zip_sha256":A6_ZIP_SHA256,"matrix_sha256":MATRIX_SHA256,
            "feature_catalog_sha256":FEATURE_CATALOG_SHA256,"a6_ledger_sha256":A6_LEDGER_SHA256,"q90_archive_blob_sha1":archive_blob,
            "matrix_shape":list(matrix.shape),"matrix_dtype":str(matrix.dtype),"feature_count":len(names),
            "family_counts":{k:len(v) for k,v in groups.items()},"q90_archive_cutoff":"2026-11-07","q90_archive_draws":3401,"main_archive_suffix_excluded":5}
    return matrix,dates,cutoffs,actual,ledger,names,groups,source

def analyse(q90_zip,a6_zip,output_dir,preregistration):
    matrix,dates,cutoffs,actual,ledger,feature_names,groups,source=load_inputs(q90_zip,a6_zip)
    n=len(matrix); agreement=np.empty(n); consensus=np.empty((n,5),dtype=np.int64); equal=np.empty((n,5),dtype=np.int64); equal59=np.empty((n,5),dtype=np.int64)
    for t in range(n):
        r=target_family_state(matrix[t],groups); agreement[t]=r["agreement"]; consensus[t]=r["consensus_top5"]; equal[t]=r["equal_family_top5"]; equal59[t]=r["equal59_top5"]
    thresholds,state=build_disagreement_state(agreement)
    hc=np.array([count_hits(consensus[t],actual[t]) for t in range(n)],dtype=np.int8)
    he=np.array([count_hits(equal[t],actual[t]) for t in range(n)],dtype=np.int8)
    h59=np.array([count_hits(equal59[t],actual[t]) for t in range(n)],dtype=np.int8)
    delta=hc.astype(float)-he.astype(float); delta59=hc.astype(float)-h59.astype(float)
    valid=np.arange(n)>=WINDOW; split=ledger.split.astype(str).to_numpy(); split_summary={}
    for name in ["discovery","validation","blind_oos"]:
        mask=valid&(split==name); hs=state[mask]; ds=delta[mask]
        split_summary[name]={"targets":int(mask.sum()),"high_disagreement_targets":int((hs==1).sum()),"low_disagreement_targets":int((hs==0).sum()),
            "mean_family_jaccard":float(agreement[mask].mean()),"consensus_mean_hits":float(hc[mask].mean()),
            "equal_family_mean_hits":float(he[mask].mean()),"equal59_mean_hits":float(h59[mask].mean()),"uniform_expected_hits":UNIFORM_EXPECTED_HITS,
            "consensus_minus_equal_family_mean_hits":float(ds.mean()),"consensus_minus_equal59_mean_hits":float(delta59[mask].mean()),
            "consensus_vs_uniform_mean_hits":float(hc[mask].mean()-UNIFORM_EXPECTED_HITS),
            "paired_delta_high_mean":float(ds[hs==1].mean()),"paired_delta_low_mean":float(ds[hs==0].mean()),
            "high_minus_low_paired_delta":float(ds[hs==1].mean()-ds[hs==0].mean())}
    blind=valid&(split=="blind_oos"); y=delta[blind]; hs=state[blind]; hcb=hc[blind]
    e1=float(y[hs==1].mean()-y[hs==0].mean()); e2=float(y.mean()); e3=float(hcb.mean()-UNIFORM_EXPECTED_HITS)
    ci1=circular_block_bootstrap(y,hs,seed=SEED+10,estimand="high_minus_low")
    ci2=circular_block_bootstrap(y,None,seed=SEED+11,estimand="mean")
    ci3=circular_block_bootstrap(hcb.astype(float)-UNIFORM_EXPECTED_HITS,None,seed=SEED+12,estimand="mean")
    p1=circular_shift_p(y,hs,seed=SEED+20); p2=block_signflip_p(y,seed=SEED+21); p3=exact_uniform_upper_tail(int(hcb.sum()),len(hcb))
    adj=holm_adjust([p1,p2,p3]); accepted=e1>=PRACTICAL_THRESHOLD and ci1[0]>0 and adj[0]<.05
    family_hit_means={}
    for name,idxs in groups.items():
        scores=matrix[:,:,idxs].mean(axis=2); tops=np.stack([top5_from_scores(scores[t]) for t in range(n)])
        fh=np.array([count_hits(tops[t],actual[t]) for t in range(n)])
        family_hit_means[name]={s:float(fh[valid&(split==s)].mean()) for s in ["discovery","validation","blind_oos"]}
    checks=[]
    for t in [100,250,1000,2000,3000,3350]:
        orig=target_family_state(matrix[t],groups); prev=np.array([target_family_state(matrix[j],groups)["agreement"] for j in range(t-WINDOW,t)])
        altered=matrix.copy(); altered[t+1:]=0.
        new=target_family_state(altered[t],groups); prev2=np.array([target_family_state(altered[j],groups)["agreement"] for j in range(t-WINDOW,t)])
        checks.append({"target_index":t,"agreement_unchanged":abs(new["agreement"]-orig["agreement"])<1e-15,
            "threshold_unchanged":abs(float(np.median(prev2))-float(np.median(prev)))<1e-15,
            "consensus_top5_unchanged":bool(np.array_equal(new["consensus_top5"],orig["consensus_top5"])),
            "equal_family_top5_unchanged":bool(np.array_equal(new["equal_family_top5"],orig["equal_family_top5"]))})
    if not all(all(v for k,v in c.items() if k!="target_index") for c in checks): raise RuntimeError("future suffix mutation failed")
    target_ledger=pd.DataFrame({"target_index":np.arange(n),"target_date":dates,"cutoff_date":cutoffs,"prior_draws":ledger.prior_draws.to_numpy(dtype=int),
        "split":split,"actual_quintet":[" ".join(map(str,r)) for r in actual],"family_agreement_mean_jaccard":agreement,
        "prior100_agreement_median":thresholds,"high_disagreement_state":[None if v<0 else int(v) for v in state],
        "consensus_top5":[" ".join(map(str,r)) for r in consensus],"equal_family_top5":[" ".join(map(str,r)) for r in equal],
        "equal59_top5":[" ".join(map(str,r)) for r in equal59],"consensus_hits":hc,"equal_family_hits":he,"equal59_hits":h59,
        "consensus_minus_equal_family_hits":delta,"consensus_minus_equal59_hits":delta59})
    output_dir.mkdir(parents=True,exist_ok=True)
    ledger_path=output_dir/"q141_d4_family_consensus_state_target_ledger_2026-11-13.csv"
    target_ledger.to_csv(ledger_path,index=False,float_format="%.12g",lineterminator="\n")
    endpoints=[
      {"id":"D4_T1","endpoint":"high_disagreement_minus_low_disagreement_paired_hit_delta","effect":e1,"ci95_circular_block_bootstrap":ci1,"p_raw":p1,"practical_threshold_hits_per_target":PRACTICAL_THRESHOLD},
      {"id":"D4_T2","endpoint":"unconditional_consensus_minus_equal_family_mean_hits","effect":e2,"ci95_circular_block_bootstrap":ci2,"p_raw":p2,"practical_threshold_hits_per_target":PRACTICAL_THRESHOLD},
      {"id":"D4_T3","endpoint":"consensus_mean_hits_minus_exact_uniform_expectation","effect":e3,"ci95_circular_block_bootstrap":ci3,"p_raw":p3,"exact_null":"sum of 670 Hypergeometric(40,5,5) outcomes","uniform_expected_hits":UNIFORM_EXPECTED_HITS}]
    for row,p in zip(endpoints,adj): row["p_holm"]=float(p)
    report={"schema_version":"1.0","task_id":"Q141-D4","status":"COMPLETED_HISTORICAL_WALK_FORWARD",
      "decision":"FAMILY_CONSENSUS_LIFT_DEMONSTRATED" if accepted else "NO_FAMILY_CONSENSUS_CONDITIONAL_LIFT_DEMONSTRATED",
      "hypothesis":{"signal":"mean pairwise Jaccard of seven family-specific Top-5 sets","state":"high disagreement when current agreement < median of previous 100 target agreements",
        "primary_outcome":"consensus Top-5 hits minus equal-family-mean Top-5 hits","primary_minimum_effect":PRACTICAL_THRESHOLD,"family_count":len(groups),"window":WINDOW,"top_k":5,
        "tie_rule":"scores rounded to 12 decimals; ascending number; consensus vote count then mean family score then number"},
      "source":source,"walkforward":{"target_rows":n,"warmup_targets":WINDOW,"evaluated_split_counts":{k:v["targets"] for k,v in split_summary.items()},
        "original_split_counts":SPLIT_COUNTS,"first_target":str(dates[0]),"last_target":str(dates[-1]),"strict_prior_alignment":True,"historical_blind_oos_not_virgin":True},
      "split_results":split_summary,"family_top5_hit_means":family_hit_means,
      "blind_oos_inference":{"method":"20,000 circular moving-block bootstrap (block=20); 20,000 circular state shifts; 20,000 non-overlapping block sign-flips; exact hypergeometric convolution; Holm across 3 registered endpoints",
        "endpoints":endpoints,"holm_family_size":3,"acceptance_rule":"primary effect >= +0.025 hits/target AND 95% CI lower > 0 AND Holm p < 0.05","accepted":bool(accepted)},
      "integrity":{"all_cutoffs_strictly_before_targets":True,"matrix_ledger_dates_cutoffs_actuals_exactly_aligned":True,"prior_draws_equal_target_index_plus_50":True,
        "all_feature_values_finite":True,"family_groups_partition_59_features":True,"family_counts":source["family_counts"],"future_suffix_mutation_checks":checks,"inference_target_level":True},
      "limitations":["Historical Blind OOS has been exposed to prior SONAR research and is not virgin prospective evidence.",
        "Q89 features are per-target cross-sectional z-scores; known rank duplicates remain within the baseline legacy family.",
        "Equal-family averaging reduces family-size weighting but does not remove within-family feature redundancy.",
        "The endpoint is per-number Top-5 hit count, not exact five-number ticket probability.",
        "Q90 matrix ends 2026-11-07; five later main-archive rows are excluded.",
        "Holm correction covers the three D4 endpoints only, not the full Q00-Q141 research family."],
      "next_action":"Keep D4 research-only. Continue common-source AST semantic reconciliation and obtain prospective frozen evidence; do not retune the disagreement state on this historical Blind OOS."}
    report_path=output_dir/"q141_d4_family_consensus_state_report_2026-11-13.json"
    report_path.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    files={}
    for p in [preregistration,Path(__file__),report_path,ledger_path]:
        b=p.read_bytes(); files[p.name]={"path":p.name,"bytes":len(b),"sha256":sha256_bytes(b),"git_blob_sha1":git_blob_sha1(b)}
    manifest={"schema_version":"1.0","task_id":"Q141-D4","source_q90_zip_sha256":Q90_ZIP_SHA256,"source_a6_zip_sha256":A6_ZIP_SHA256,
      "preregistration_sha256":sha256_bytes(preregistration.read_bytes()),"runner_sha256":sha256_bytes(Path(__file__).read_bytes()),
      "target_rows":n,"evaluated_targets":int(valid.sum()),"files":files}
    mp=output_dir/"q141_d4_family_consensus_state_manifest_2026-11-13.json"; mp.write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","task_id":"Q141-D4","status":"LOCAL_REPLAY_COMPLETE_PENDING_REMOTE_READBACK","decision":report["decision"],
      "report_path":report_path.name,"ledger_path":ledger_path.name,"manifest_path":mp.name,
      "report_sha256":sha256_bytes(report_path.read_bytes()),"ledger_sha256":sha256_bytes(ledger_path.read_bytes()),"manifest_sha256":sha256_bytes(mp.read_bytes()),
      "source_q90_zip_sha256":Q90_ZIP_SHA256,"source_a6_zip_sha256":A6_ZIP_SHA256,"next_action":report["next_action"],
      "governance":{"research_only":True,"canonical_archive_mutated":False,"b11_or_q60_freeze_mutated":False,"engine_promoted":False,"merge":False,"protected_prs_6_7_8_untouched":True}}
    cp=output_dir/"q141_d4_family_consensus_state_checkpoint_2026-11-13.json"; cp.write_text(json.dumps(checkpoint,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return report,target_ledger,manifest,checkpoint

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--q90-zip",type=Path,required=True); ap.add_argument("--a6-zip",type=Path,required=True)
    ap.add_argument("--preregistration",type=Path,required=True); ap.add_argument("--output-dir",type=Path,required=True)
    a=ap.parse_args(); report,ledger,manifest,checkpoint=analyse(a.q90_zip,a.a6_zip,a.output_dir,a.preregistration)
    print(json.dumps({"decision":report["decision"],"split_counts":report["walkforward"]["evaluated_split_counts"],
      "blind_oos":report["blind_oos_inference"]["endpoints"],"ledger_rows":len(ledger),"manifest_files":len(manifest["files"]),
      "checkpoint_status":checkpoint["status"]},sort_keys=True,indent=2))
if __name__=="__main__": main()
