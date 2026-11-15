#!/usr/bin/env python3
"""Q141-A11: third-order co-occurrence residual score test."""
from __future__ import annotations
import argparse,csv,hashlib,itertools,json,math
from functools import lru_cache
from pathlib import Path
import numpy as np

ARCHIVE_BLOB="6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
MATRIX_SHA256="81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047"
MATRIX_SHAPE=(3356,40,59)
A7_RUN=43348144964
A7_ARTIFACT=14003350043
A7_ZIP_SHA256="9c54699a507e876b7b5b1c0c9e3120ad04c2bcc741dcd5043dc410f81bf6b03a"
RECENT=200
STALE=200
WARMUP=RECENT+STALE
SEED=14111321
PRACTICAL_PRIMARY=0.10
PRACTICAL_CONTRAST=0.05

@lru_cache(maxsize=4)
def structures(n):
    triples=np.asarray(list(itertools.combinations(range(n),3)),dtype=np.int16)
    pairs=np.asarray(list(itertools.combinations(range(n),2)),dtype=np.int16)
    pair_map=np.full((n,n),-1,dtype=np.int32)
    pair_map[pairs[:,0],pairs[:,1]]=np.arange(len(pairs),dtype=np.int32)
    pair_map[pairs[:,1],pairs[:,0]]=np.arange(len(pairs),dtype=np.int32)
    triple_map=np.full((n,n,n),-1,dtype=np.int32)
    triple_map[triples[:,0],triples[:,1],triples[:,2]]=np.arange(len(triples),dtype=np.int32)
    position_triples=tuple(itertools.combinations(range(5),3))
    pair_ids=np.column_stack((pair_map[triples[:,0],triples[:,1]],pair_map[triples[:,0],triples[:,2]],pair_map[triples[:,1],triples[:,2]]))
    return triples,pairs,pair_map,triple_map,position_triples,pair_ids

def validate_draws(draws,n=40,k=5):
    x=np.asarray(draws,dtype=np.int64)
    if x.ndim!=2 or x.shape[1]!=k or len(x)==0: raise ValueError("draws must be a nonempty n_rows x k matrix")
    if np.any(x<1) or np.any(x>n): raise ValueError("draw value outside permitted range")
    if any(len(set(row.tolist()))!=k for row in x): raise ValueError("duplicate number in a draw")
    return np.sort(x,axis=1)

def triple_counts(draws,n=40):
    x=validate_draws(draws,n=n,k=5)-1
    triples,_,_,triple_map,position_triples,_=structures(n)
    ids=np.stack([triple_map[x[:,a],x[:,b],x[:,c]] for a,b,c in position_triples],axis=1)
    if np.any(ids<0): raise ValueError("invalid triple index")
    return np.bincount(ids.reshape(-1),minlength=len(triples)).astype(np.float64)

def pair_marginal_max(residuals,n=40):
    triples,_,_,_,_,pair_ids=structures(n)
    r=np.asarray(residuals,dtype=np.float64)
    if r.shape!=(len(triples),): raise ValueError("triple residual vector has wrong length")
    margins=np.bincount(pair_ids.reshape(-1),weights=np.repeat(r,3),minlength=math.comb(n,2))
    return float(np.max(np.abs(margins)))

def triple_residuals_from_counts(counts,n=40):
    triples,pairs,_,_,_,pair_ids=structures(n)
    y=np.asarray(counts,dtype=np.float64)
    if y.shape!=(len(triples),) or not np.isfinite(y).all(): raise ValueError("counts must be a finite vector indexed by all triples")
    if n<5: raise ValueError("n must be at least 5")
    mu=float(y.mean())
    single_sums=(np.bincount(triples[:,0],weights=y,minlength=n)+np.bincount(triples[:,1],weights=y,minlength=n)+np.bincount(triples[:,2],weights=y,minlength=n))
    a=(single_sums-math.comb(n-1,2)*mu)/math.comb(n-2,2)
    pair_sums=np.bincount(pair_ids.reshape(-1),weights=np.repeat(y,3),minlength=len(pairs))
    pi,pj=pairs[:,0],pairs[:,1]
    b=(pair_sums-(n-2)*mu-(n-3)*(a[pi]+a[pj]))/(n-4)
    i,j,k=triples[:,0],triples[:,1],triples[:,2]
    r=y-mu-a[i]-a[j]-a[k]-b[pair_ids[:,0]]-b[pair_ids[:,1]]-b[pair_ids[:,2]]
    max_margin=pair_marginal_max(r,n)
    if max_margin>1e-8: raise ArithmeticError(f"triple residual pair margins not zero: {max_margin}")
    return r,{"mu":mu,"single_effect_l2":float(np.linalg.norm(a)),"pair_effect_l2":float(np.linalg.norm(b)),"pair_marginal_max":max_margin,"residual_l2_sq":float(np.dot(r,r))}

def triple_residuals(draws,n=40):
    return triple_residuals_from_counts(triple_counts(draws,n=n),n=n)

def inclusion_probability(k,n,q):
    if k<q: return 0.0
    return math.prod(k-j for j in range(q))/math.prod(n-j for j in range(q))

def triple_null_variance(residuals,n=40,k=5):
    triples,_,_,_,_,_=structures(n)
    r=np.asarray(residuals,dtype=np.float64)
    if r.shape!=(len(triples),) or not np.isfinite(r).all(): raise ValueError("invalid triple residual vector")
    if pair_marginal_max(r,n)>1e-8: raise ValueError("triple residuals must have zero pair margins")
    coef=inclusion_probability(k,n,3)-3*inclusion_probability(k,n,4)+3*inclusion_probability(k,n,5)-inclusion_probability(k,n,6)
    return max(0.0,coef*float(np.dot(r,r)))

def score_residuals(residuals,draw,n=40,k=5):
    _,_,_,triple_map,position_triples,_=structures(n)
    x=np.sort(np.asarray(draw,dtype=np.int64))
    if x.shape!=(k,) or np.any(x<1) or np.any(x>n) or len(set(x.tolist()))!=k: raise ValueError("invalid target subset")
    x=x-1
    ids=np.asarray([triple_map[x[a],x[b],x[c]] for a,b,c in position_triples],dtype=np.int32)
    r=np.asarray(residuals,dtype=np.float64)
    variance=triple_null_variance(r,n=n,k=k)
    score=float(np.sum(r[ids]))
    return score,variance,0.0 if variance==0.0 else float(score/math.sqrt(variance))

def score_target(actual,t):
    x=np.asarray(actual,dtype=np.int64)
    if x.ndim!=2 or x.shape[1]!=5 or t<WARMUP or t>=len(x): raise ValueError("need 400 strictly prior rows and a valid target")
    recent_r,recent_diag=triple_residuals(x[t-RECENT:t])
    stale_r,stale_diag=triple_residuals(x[t-WARMUP:t-RECENT])
    recent_score,recent_var,z_recent=score_residuals(recent_r,x[t])
    stale_score,stale_var,z_stale=score_residuals(stale_r,x[t])
    contrast_r=np.zeros_like(recent_r) if recent_var==0.0 or stale_var==0.0 else recent_r/math.sqrt(recent_var)-stale_r/math.sqrt(stale_var)
    contrast_score,contrast_var,z_contrast=score_residuals(contrast_r,x[t])
    return {"recent_triple_score":recent_score,"recent_null_variance":recent_var,"z3_recent":z_recent,
      "stale_triple_score":stale_score,"stale_null_variance":stale_var,"z3_stale":z_stale,
      "normalized_recent_minus_stale_score":contrast_score,"normalized_contrast_null_variance":contrast_var,
      "z3_recent_vs_stale":z_contrast,"recent_pair_marginal_max":recent_diag["pair_marginal_max"],
      "stale_pair_marginal_max":stale_diag["pair_marginal_max"],"contrast_pair_marginal_max":pair_marginal_max(contrast_r)}

def verify_small_variance():
    rng=np.random.default_rng(14111320); n,k=8,5
    triples,_,_,_,_,_=structures(n)
    y=rng.normal(size=len(triples)); r,_=triple_residuals_from_counts(y,n=n)
    values=np.asarray([score_residuals(r,s,n=n,k=k)[0] for s in itertools.combinations(range(1,n+1),k)])
    return abs(float(values.mean()))<=1e-10 and abs(float(values.var())-triple_null_variance(r,n=n,k=k))<=1e-10

def validate_matrix(path):
    raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    if sha!=MATRIX_SHA256: raise ValueError("A7 matrix SHA-256 mismatch")
    with np.load(path,allow_pickle=False) as z:
        matrix=z["feature_matrix"]; dates=z["target_dates"].astype(str); cutoffs=z["cutoff_dates"].astype(str)
        actual=z["actual_quintets"].astype(np.int64); names=z["feature_names"].astype(str); archive=str(z["archive_blob_sha"].item())
    if archive!=ARCHIVE_BLOB or matrix.shape!=MATRIX_SHAPE: raise ValueError("A7 source lineage/shape mismatch")
    if not np.isfinite(matrix).all() or len(names)!=59: raise ValueError("invalid feature matrix")
    if actual.shape!=(3356,5): raise ValueError("invalid actual quintet matrix")
    actual=validate_draws(actual)
    if len(set(dates.tolist()))!=len(dates) or np.any(np.diff(dates.astype("datetime64[D]").astype("int64"))<=0): raise ValueError("target dates not unique/chronological")
    if not np.all(cutoffs<dates): raise ValueError("cutoff not prior to target")
    return {"matrix_sha256":sha,"archive_blob_sha1":archive,"matrix_shape":list(matrix.shape),"feature_count":len(names),"dates":dates,"cutoffs":cutoffs,"actual":actual}

def build_records(src):
    actual,dates,cutoffs=src["actual"],src["dates"],src["cutoffs"]; out=[]
    for t in range(WARMUP,len(actual)):
        values=score_target(actual,t)
        out.append({"target_index":t,"target_date":str(dates[t]),"cutoff_date":str(cutoffs[t]),"prior_archive_draws":t+50,
          "recent_start_date":str(dates[t-RECENT]),"recent_end_date":str(dates[t-1]),
          "stale_start_date":str(dates[t-WARMUP]),"stale_end_date":str(dates[t-RECENT-1]),
          "target_quintet":" ".join(map(str,sorted(actual[t].tolist()))),**values})
    return out

def hac_se(values,max_lag):
    x=np.asarray(values,dtype=np.float64); n=len(x); centered=x-x.mean()
    variance=float(np.dot(centered,centered)/n)
    for lag in range(1,min(max_lag,n-1)+1):
        gamma=float(np.dot(centered[lag:],centered[:-lag])/n)
        variance+=2.0*(1.0-lag/(max_lag+1.0))*gamma
    return math.sqrt(max(0.0,variance)/n)

def acf(values,lag):
    x=np.asarray(values,dtype=np.float64); centered=x-x.mean(); den=float(np.dot(centered,centered))
    return 0.0 if lag>=len(x) or den==0.0 else float(np.dot(centered[lag:],centered[:-lag])/den)

def martingale_inference(values):
    x=np.asarray(values,dtype=np.float64); n=len(x); mean=float(x.mean()); sd=float(x.std(ddof=1))
    null_se=1.0/math.sqrt(n); null_z=mean/null_se; p=0.5*math.erfc(null_z/math.sqrt(2.0))
    ci=[mean-1.96*sd/math.sqrt(n),mean+1.96*sd/math.sqrt(n)]
    return {"targets":n,"mean":mean,"sample_sd":sd,"null_predictable_se":null_se,"martingale_normal_z":null_z,
      "p_one_sided_martingale_normal":p,"ci95_iid_sensitivity":ci,
      "hac_se_sensitivity":{str(l):hac_se(x,l) for l in (20,50,100)},
      "acf_sensitivity":{str(l):acf(x,l) for l in (1,5,20,50,100)},
      "max_abs_increment":float(np.max(np.abs(x))),"max_abs_over_sqrt_n":float(np.max(np.abs(x))/math.sqrt(n)),
      "conditional_null_variance_per_target":1.0,"conditional_null_mean_per_target":0.0}

def summarize(rows):
    recent=np.asarray([r["z3_recent"] for r in rows]); stale=np.asarray([r["z3_stale"] for r in rows])
    contrast=np.asarray([r["z3_recent_vs_stale"] for r in rows])
    return {"targets":len(rows),"mean_z3_recent":float(recent.mean()),"sd_z3_recent":float(recent.std(ddof=1)),
      "positive_share_z3_recent":float(np.mean(recent>0)),"mean_z3_stale":float(stale.mean()),
      "sd_z3_stale":float(stale.std(ddof=1)),"mean_z3_recent_vs_stale":float(contrast.mean()),
      "sd_z3_recent_vs_stale":float(contrast.std(ddof=1)),"positive_share_z3_recent_vs_stale":float(np.mean(contrast>0)),
      "max_pair_marginal_residual":float(max(max(r["recent_pair_marginal_max"],r["stale_pair_marginal_max"],r["contrast_pair_marginal_max"]) for r in rows))}

def holm(p_values):
    ordered=sorted(p_values.items(),key=lambda item:item[1]); adjusted={}; running=0.0
    for rank,(name,value) in enumerate(ordered):
        running=max(running,min(1.0,(len(ordered)-rank)*value)); adjusted[name]=running
    return adjusted

def git_blob_sha(path):
    raw=path.read_bytes(); return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def run(matrix_path,outdir):
    if not verify_small_variance(): raise AssertionError("exact third-order variance check failed")
    src=validate_matrix(matrix_path); rows=build_records(src); replay=build_records(src)
    replay_ok=json.dumps(rows,sort_keys=True,separators=(",",":"))==json.dumps(replay,sort_keys=True,separators=(",",":"))
    if not replay_ok: raise AssertionError("full deterministic replay failed")
    rng=np.random.default_rng(SEED); future_ok=True
    for t in (500,1800,3300):
        baseline=score_target(src["actual"],t); changed=src["actual"].copy()
        for j in range(t+1,len(changed)): changed[j]=np.sort(rng.choice(np.arange(1,41),5,replace=False))
        if baseline!=score_target(changed,t): future_ok=False; break
    if not future_ok: raise AssertionError("future suffix changed a prior score")
    n=len(rows); nd=round(n*.60); nv=round(n*.20); nb=n-nd-nv
    if (n,nd,nv,nb)!=(2956,1774,591,591): raise AssertionError("unexpected target split")
    split={"discovery":summarize(rows[:nd]),"validation":summarize(rows[nd:nd+nv]),"blind_oos":summarize(rows[nd+nv:])}
    blind=rows[nd+nv:]; primary=martingale_inference([r["z3_recent"] for r in blind])
    secondary=martingale_inference([r["z3_recent_vs_stale"] for r in blind])
    p1="recent_triple_residual_vs_uniform_zero"; p2="normalized_recent_vs_stale_triple_contrast"
    adjusted=holm({p1:primary["p_one_sided_martingale_normal"],p2:secondary["p_one_sided_martingale_normal"]})
    decision="NO_THIRD_ORDER_TRIPLE_RESIDUAL_LIFT_DEMONSTRATED"
    if primary["mean"]>=PRACTICAL_PRIMARY and primary["ci95_iid_sensitivity"][0]>0 and adjusted[p1]<.05:
        decision="HISTORICAL_TRIPLE_RESIDUAL_SIGNAL_CANDIDATE_REQUIRES_PROSPECTIVE_REPLICATION"
    outdir.mkdir(parents=True,exist_ok=True)
    rp=outdir/"q141_a11_triple_residual_report_2026-11-13.json"; lp=outdir/"q141_a11_triple_residual_target_ledger_2026-11-13.csv"
    mp=outdir/"q141_a11_triple_residual_manifest_2026-11-13.json"; cp=outdir/"q141_a11_triple_residual_checkpoint_2026-11-13.json"
    report={"schema_version":"1.0","task_id":"Q141-A11-TRIPLE-RESIDUAL","status":"COMPLETED_HISTORICAL_EXPLORATORY_WALK_FORWARD","decision":decision,
      "source":{"a7_workflow_run_id":A7_RUN,"a7_artifact_id":A7_ARTIFACT,"a7_artifact_zip_sha256":A7_ZIP_SHA256,
        "feature_matrix_sha256":src["matrix_sha256"],"archive_blob_sha1":src["archive_blob_sha1"],"archive_draw_count":3406,
        "archive_last_date":"2026-11-12","feature_matrix_shape":src["matrix_shape"],"feature_count":src["feature_count"]},
      "design":{"window_recent":RECENT,"window_stale":STALE,"warmup_matrix_rows":WARMUP,"target_index_start_inclusive":WARMUP,
        "target_index_end_inclusive":3355,"targets":n,"split_counts":{"discovery":nd,"validation":nv,"blind_oos":nb},
        "baseline":"uniform unordered 5-of-40; conditional null mean 0 and variance 1 for each standardized score",
        "primary_endpoint":"Blind OOS mean Z3_recent after removing additive single and pair effects",
        "secondary_endpoint":"Blind OOS mean exact-variance-standardized recent-minus-stale triple residual contrast",
        "practical_thresholds":{"primary_mean_z3":PRACTICAL_PRIMARY,"normalized_contrast_mean_z3":PRACTICAL_CONTRAST},
        "inference":"martingale score test under independent uniform 5-of-40 draws; predictable variance n; one-sided normal martingale approximation",
        "multiple_testing":"Holm across the two registered Blind OOS endpoints only; not the full Q00-Q141 family",
        "parameter_tuning":"none; fixed 200-draw recent and stale windows",
        "diagnostics":"Newey-West HAC and ACF sensitivities at lags 20, 50, 100; no block sign-symmetry assumption"},
      "formula":{"triple_counts":"Y_ijk = number of prior-window draws containing triple {i,j,k}","mu":"mean(Y_ijk) over all choose(40,3) triples",
        "single_effect":"a_i=(S_i-choose(n-1,2)*mu)/choose(n-2,2)","pair_effect":"b_ij=(Q_ij-(n-2)*mu-(n-3)*(a_i+a_j))/(n-4)",
        "triple_residual":"R_ijk=Y_ijk-mu-a_i-a_j-a_k-b_ij-b_ik-b_jk; sum_{k!=i,j}R_ijk=0",
        "target_score":"T3=sum_{triples subset target quintet}R_ijk","null_variance":"(p3-3*p4+3*p5-p6)*sum R_ijk^2; pq=(5)_q/(40)_q; p6=0 for k=5",
        "standardized_score":"Z3=T3/sqrt(Var0(T3))","contrast_tensor":"U=R_recent/sqrt(V_recent)-R_stale/sqrt(V_stale); Z3_contrast=sum U(target triples)/sqrt(Var0(U))"},
      "split_metrics":split,"blind_oos_inference":{
        p1:{**primary,"p_holm":adjusted[p1]},p2:{**secondary,"p_holm":adjusted[p2]}},
      "integrity":{"source_archive_blob_pinned":True,"matrix_sha256_verified":True,"matrix_finite":True,"target_dates_unique_chronological":True,
        "all_cutoffs_precede_targets":True,"recent_and_stale_windows_strictly_prior_disjoint":True,"triple_residual_pair_margins_zero":True,
        "future_suffix_invariance":future_ok,"deterministic_full_replay":replay_ok,"analytic_variance_exhaustive_small_problem_test":True},
      "limitations":["Historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation.",
        "Holm covers only the two A11 endpoints, not the full Q00-Q141 research family.",
        "The martingale null assumes independent uniform 5-of-40 draws; it is a statistical reference, not a physical mechanism model.",
        "The normal martingale approximation is asymptotic; Lindeberg proxy, HAC and ACF sensitivities are reported.",
        "A positive third-order score would not itself establish calibrated exact-ticket probabilities or a deployable engine.",
        "No B11 prospective outcome is read; the 2026-11-13 target remains pending."],
      "governance":{"b11_freeze_unchanged":True,"canonical_archive_mutated":False,"engine_promoted":False,"shadow_inserted":False,
        "merge":False,"rebase":False,"protected_prs_6_7_8_untouched":True}}
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with lp.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    outputs={}
    for f in (rp,lp):
        raw=f.read_bytes(); outputs[f.name]={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"git_blob_sha1":git_blob_sha(f)}
    manifest={"schema_version":"1.0","task_id":"Q141-A11-TRIPLE-RESIDUAL","status":"COMPLETED_LOCAL_OUTPUTS",
      "source_archive_blob_sha1":ARCHIVE_BLOB,"source_matrix_sha256":MATRIX_SHA256,"outputs":outputs}
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","cycle":21,"task_id":"Q141-A11-TRIPLE-RESIDUAL","status":"COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
      "decision":decision,"source_archive_blob_sha1":ARCHIVE_BLOB,"source_matrix_sha256":MATRIX_SHA256,
      "report_path":str(rp),"ledger_path":str(lp),"manifest_path":str(mp),
      "next_action":"Review strict-prior third-order residual walk-forward; keep B11 unchanged/pending; any historical signal requires separate prospective replication.",
      "governance":report["governance"]}
    cp.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"decision":decision,"targets":n,"split_counts":report["design"]["split_counts"],
      "blind_oos_inference":report["blind_oos_inference"],"integrity":report["integrity"]},sort_keys=True))

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--matrix",required=True,type=Path)
    parser.add_argument("--output-dir",default=Path("reports/sequence_agent"),type=Path)
    args=parser.parse_args(); run(args.matrix,args.output_dir)
