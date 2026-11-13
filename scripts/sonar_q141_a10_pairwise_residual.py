#!/usr/bin/env python3
"""Q141-A10: strict-prior pairwise co-occurrence residual score test."""
from __future__ import annotations
import argparse, csv, hashlib, itertools, json, math
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
BLOCK=20
REPS=20_000
SEED=14111310
PRACTICAL_PRIMARY=0.10
PRACTICAL_RECENCY=0.05

def additive_residuals(counts):
    c=np.asarray(counts,dtype=np.float64)
    if c.ndim!=2 or c.shape[0]!=c.shape[1] or c.shape[0]<4: raise ValueError("counts must be square")
    n=c.shape[0]
    if not np.isfinite(c).all() or not np.allclose(c,c.T,atol=1e-12) or not np.allclose(np.diag(c),0,atol=1e-12):
        raise ValueError("counts must be finite, symmetric, with zero diagonal")
    i,j=np.triu_indices(n,1)
    mu=float(c[i,j].mean())
    alpha=(c.sum(axis=1)-(n-1)*mu)/(n-2)
    r=np.zeros_like(c)
    r[i,j]=c[i,j]-mu-alpha[i]-alpha[j]
    r[j,i]=r[i,j]
    if not np.allclose(r.sum(axis=1),0,atol=1e-9): raise ArithmeticError("nonzero residual row sum")
    return r

def pair_residuals(draws):
    x=np.asarray(draws,dtype=np.int64)
    if x.ndim!=2 or x.shape[1]!=5 or len(x)==0: raise ValueError("draws must be nonempty n x 5")
    if np.any(x<1) or np.any(x>40) or any(len(set(row.tolist()))!=5 for row in x):
        raise ValueError("invalid 5-of-40 draw")
    c=np.zeros((40,40),dtype=np.float64)
    a,b=np.triu_indices(5,1)
    for row in x:
        v=row-1
        c[v[a],v[b]]+=1
        c[v[b],v[a]]+=1
    return additive_residuals(c)

def pair_score(r,draw):
    x=np.asarray(draw,dtype=np.int64)-1
    if len(x)!=5 or len(set(x.tolist()))!=5 or np.any(x<0) or np.any(x>=r.shape[0]):
        raise ValueError("invalid target quintet")
    return float(sum(r[i,j] for i,j in itertools.combinations(x.tolist(),2)))

def null_variance(r,k=5):
    n=r.shape[0]
    if not np.allclose(r.sum(axis=1),0,atol=1e-8): raise ValueError("residual rows must sum to zero")
    i,j=np.triu_indices(n,1)
    s2=float(np.dot(r[i,j],r[i,j]))
    def pk(q):
        if k<q: return 0.0
        return math.prod(k-v for v in range(q))/math.prod(n-v for v in range(q))
    return max(0.0,(pk(2)-2*pk(3)+pk(4))*s2)

def verify_small_variance():
    rng=np.random.default_rng(14111309)
    n=8
    a=rng.normal(size=(n,n)); a=(a+a.T)/2; np.fill_diagonal(a,0)
    r=additive_residuals(a)
    vals=np.array([pair_score(r,np.array(c)) for c in itertools.combinations(range(1,n+1),3)])
    return abs(float(vals.var())-null_variance(r,3))<=1e-12 and abs(float(vals.mean()))<=1e-12

def score_target(actual,t):
    if t<WARMUP or t>=len(actual): raise ValueError("need 400 strictly prior matrix rows")
    target=actual[t]
    recent_r=pair_residuals(actual[t-RECENT:t])
    stale_r=pair_residuals(actual[t-WARMUP:t-RECENT])
    tr=pair_score(recent_r,target); ts=pair_score(stale_r,target)
    vr=null_variance(recent_r,5); vs=null_variance(stale_r,5)
    zr=0.0 if vr==0 else tr/math.sqrt(vr)
    zs=0.0 if vs==0 else ts/math.sqrt(vs)
    return {"recent_pair_score":tr,"recent_null_variance":vr,"z_recent":float(zr),
            "stale_pair_score":ts,"stale_null_variance":vs,"z_stale":float(zs),
            "z_recent_minus_stale":float(zr-zs),
            "recent_residual_rowmax":float(np.max(np.abs(recent_r.sum(axis=1)))),
            "stale_residual_rowmax":float(np.max(np.abs(stale_r.sum(axis=1))))}

def validate_matrix(path):
    raw=path.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    if sha!=MATRIX_SHA256: raise ValueError("A7 matrix SHA-256 mismatch")
    with np.load(path,allow_pickle=False) as z:
        matrix=z["feature_matrix"]; dates=z["target_dates"].astype(str)
        cutoffs=z["cutoff_dates"].astype(str); actual=z["actual_quintets"].astype(np.int64)
        names=z["feature_names"].astype(str); archive=str(z["archive_blob_sha"].item())
    if archive!=ARCHIVE_BLOB or matrix.shape!=MATRIX_SHAPE: raise ValueError("A7 source lineage/shape mismatch")
    if not np.isfinite(matrix).all() or len(names)!=59: raise ValueError("invalid feature matrix")
    if actual.shape!=(3356,5) or np.any(actual<1) or np.any(actual>40): raise ValueError("invalid actual quintets")
    if any(len(set(row.tolist()))!=5 for row in actual): raise ValueError("duplicate value in actual quintet")
    if len(set(dates.tolist()))!=len(dates) or np.any(np.diff(dates.astype("datetime64[D]").astype("int64"))<=0):
        raise ValueError("target dates not unique/chronological")
    if not np.all(cutoffs<dates): raise ValueError("cutoff not prior to target")
    return {"matrix_sha256":sha,"archive_blob_sha1":archive,"matrix_shape":list(matrix.shape),
            "feature_count":len(names),"dates":dates,"cutoffs":cutoffs,"actual":actual}

def build_records(src):
    a=src["actual"]; d=src["dates"]; c=src["cutoffs"]; out=[]
    for t in range(WARMUP,len(a)):
        v=score_target(a,t)
        out.append({"target_index":t,"target_date":str(d[t]),"cutoff_date":str(c[t]),
          "prior_archive_draws":t+50,"recent_start_date":str(d[t-RECENT]),
          "recent_end_date":str(d[t-1]),"stale_start_date":str(d[t-WARMUP]),
          "stale_end_date":str(d[t-RECENT-1]),
          "target_quintet":" ".join(map(str,sorted(a[t].tolist()))),**v})
    return out

def signflip(x,seed):
    x=np.asarray(x,dtype=float)
    sums=np.array([x[i:i+BLOCK].sum() for i in range(0,len(x),BLOCK)])
    rng=np.random.default_rng(seed)
    signs=rng.choice(np.array([-1.,1.]),size=(REPS,len(sums)))
    null=(signs@sums)/len(x)
    return float((1+np.count_nonzero(null>=x.mean()))/(REPS+1)),int(len(sums))

def mbb_ci(x,seed):
    x=np.asarray(x,dtype=float); n=len(x); nb=math.ceil(n/BLOCK)
    rng=np.random.default_rng(seed); out=np.empty(REPS); off=np.arange(BLOCK)
    for start in range(0,REPS,500):
        stop=min(REPS,start+500)
        starts=rng.integers(0,n,size=(stop-start,nb))
        idx=(starts[:,:,None]+off[None,None,:])%n
        out[start:stop]=x[idx.reshape(stop-start,-1)[:,:n]].mean(axis=1)
    return [float(np.quantile(out,.025)),float(np.quantile(out,.975))]

def holm(p):
    order=sorted(p.items(),key=lambda x:x[1]); result={}; running=0.
    for rank,(name,value) in enumerate(order):
        running=max(running,min(1.,(len(order)-rank)*value)); result[name]=running
    return result

def summarize(rows):
    r=np.array([x["z_recent"] for x in rows]); s=np.array([x["z_stale"] for x in rows]); delta=r-s
    return {"targets":len(rows),"mean_z_recent":float(r.mean()),"sd_z_recent":float(r.std(ddof=1)),
      "median_z_recent":float(np.median(r)),"positive_share_recent":float(np.mean(r>0)),
      "mean_z_stale":float(s.mean()),"sd_z_stale":float(s.std(ddof=1)),
      "mean_recent_minus_stale":float(delta.mean()),
      "positive_share_recent_minus_stale":float(np.mean(delta>0)),
      "mean_recent_pair_score":float(np.mean([x["recent_pair_score"] for x in rows])),
      "mean_recent_null_variance":float(np.mean([x["recent_null_variance"] for x in rows])),
      "max_residual_row_sum":float(max(max(x["recent_residual_rowmax"],x["stale_residual_rowmax"]) for x in rows))}

def git_blob_sha(path):
    b=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def run(matrix_path,outdir):
    if not verify_small_variance(): raise AssertionError("exact small-subset variance check failed")
    src=validate_matrix(matrix_path); rows=build_records(src)
    replay=build_records(src)
    replay_ok=json.dumps(rows,sort_keys=True,separators=(",",":"))==json.dumps(replay,sort_keys=True,separators=(",",":"))
    if not replay_ok: raise AssertionError("full deterministic replay failed")
    rng=np.random.default_rng(14111312); future_ok=True
    for t in (500,1800,3300):
        base=score_target(src["actual"],t); changed=src["actual"].copy()
        for j in range(t+1,len(changed)): changed[j]=np.sort(rng.choice(np.arange(1,41),5,replace=False))
        if base!=score_target(changed,t): future_ok=False; break
    if not future_ok: raise AssertionError("future suffix changed prior score")
    n=len(rows); nd=round(n*.60); nv=round(n*.20); nb=n-nd-nv
    if (n,nd,nv,nb)!=(2956,1774,591,591): raise AssertionError("unexpected target split")
    split={"discovery":summarize(rows[:nd]),"validation":summarize(rows[nd:nd+nv]),"blind_oos":summarize(rows[nd+nv:])}
    blind=rows[nd+nv:]; zr=np.array([x["z_recent"] for x in blind]); dz=np.array([x["z_recent_minus_stale"] for x in blind])
    p1,b1=signflip(zr,SEED); p2,b2=signflip(dz,SEED+1)
    ci1=mbb_ci(zr,SEED+2); ci2=mbb_ci(dz,SEED+3)
    adj=holm({"recent_z_vs_uniform_zero":p1,"recent_minus_stale_z":p2})
    decision="NO_RECENT_PAIR_RESIDUAL_LIFT_DEMONSTRATED"
    if zr.mean()>=PRACTICAL_PRIMARY and ci1[0]>0 and adj["recent_z_vs_uniform_zero"]<.05:
        decision="HISTORICAL_PAIR_RESIDUAL_SIGNAL_CANDIDATE_REQUIRES_PROSPECTIVE_REPLICATION"
    outdir.mkdir(parents=True,exist_ok=True)
    rp=outdir/"q141_a10_pairwise_residual_report_2026-11-13.json"
    lp=outdir/"q141_a10_pairwise_residual_target_ledger_2026-11-13.csv"
    mp=outdir/"q141_a10_pairwise_residual_manifest_2026-11-13.json"
    cp=outdir/"q141_a10_pairwise_residual_checkpoint_2026-11-13.json"
    report={"schema_version":"1.0","task_id":"Q141-A10-PAIRWISE-RESIDUAL",
      "status":"COMPLETED_HISTORICAL_EXPLORATORY_WALK_FORWARD","decision":decision,
      "source":{"a7_workflow_run_id":A7_RUN,"a7_artifact_id":A7_ARTIFACT,
        "a7_artifact_zip_sha256":A7_ZIP_SHA256,"feature_matrix_sha256":src["matrix_sha256"],
        "archive_blob_sha1":src["archive_blob_sha1"],"archive_draw_count":3406,
        "archive_last_date":"2026-11-12","feature_matrix_shape":src["matrix_shape"],"feature_count":src["feature_count"]},
      "design":{"window_recent":RECENT,"window_stale":STALE,"warmup_matrix_rows":WARMUP,
        "target_index_start_inclusive":WARMUP,"target_index_end_inclusive":3355,"targets":n,
        "split_counts":{"discovery":nd,"validation":nv,"blind_oos":nb},
        "baseline":"uniform unordered 5-of-40; exact null mean Z=0 and per-target null variance=1",
        "pair_residual_model":"C_ij = mu + alpha_i + alpha_j + R_ij; least-squares additive effects removed",
        "primary_endpoint":"Blind OOS mean standardized recent-window pair residual score Z_recent",
        "secondary_endpoint":"Blind OOS mean (Z_recent - Z_stale)",
        "practical_thresholds":{"primary_mean_z":PRACTICAL_PRIMARY,"recent_minus_stale_mean_z":PRACTICAL_RECENCY},
        "block_length":BLOCK,"bootstrap_replicates":REPS,"signflip_replicates":REPS,"holm_family_size":2,
        "parameter_tuning":"none; fixed 200-draw recent and stale windows"},
      "formula":{"pair_residual":"R_ij=C_ij-mu-alpha_i-alpha_j",
        "mu":"sum_{i<j} C_ij / choose(40,2)","alpha_i":"(row_sum_i-39*mu)/38",
        "target_score":"T=sum_{i<j in target quintet} R_ij",
        "null_variance":"(p2-2*p3+p4)*sum_{i<j} R_ij^2; pk=(5)_k/(40)_k",
        "standardized_score":"Z=T/sqrt(Var0(T))"},
      "split_metrics":split,"blind_oos_inference":{
        "recent_z_vs_uniform_zero":{"mean":float(zr.mean()),"ci95_circular_block_bootstrap":ci1,
          "p_one_sided_block_signflip":p1,"p_holm":adj["recent_z_vs_uniform_zero"],"block_count":b1},
        "recent_minus_stale_z":{"mean":float(dz.mean()),"ci95_circular_block_bootstrap":ci2,
          "p_one_sided_block_signflip":p2,"p_holm":adj["recent_minus_stale_z"],"block_count":b2}},
      "integrity":{"source_archive_blob_pinned":True,"matrix_sha256_verified":True,"matrix_finite":True,
        "target_dates_unique_chronological":True,"all_cutoffs_precede_targets":True,
        "recent_and_stale_windows_strictly_prior_disjoint":True,"pair_residual_row_sums_zero":True,
        "future_suffix_invariance":future_ok,"deterministic_full_replay":replay_ok,
        "analytic_variance_exhaustive_small_problem_test":True},
      "limitations":["Pairwise score-test diagnostic, not a calibrated probability for exact tickets.",
        "Historical Blind OOS is exposed to prior SONAR research and is exploratory, not virgin confirmation.",
        "Holm covers only two A10 endpoints, not the entire Q00-Q141 research family.",
        "Uniform 5-of-40 is the exact combinatorial reference, not a physical model.",
        "Overlapping windows induce dependence; block inference is used, but stationarity/sign-symmetry remain assumptions.",
        "No B11 prospective outcome is read; the 2026-11-13 target remains pending."],
      "governance":{"b11_freeze_unchanged":True,"canonical_archive_mutated":False,"engine_promoted":False,
        "shadow_inserted":False,"merge":False,"rebase":False,"protected_prs_6_7_8_untouched":True}}
    rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with lp.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    outputs={}
    for f in (rp,lp):
        b=f.read_bytes(); outputs[f.name]={"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"git_blob_sha1":git_blob_sha(f)}
    manifest={"schema_version":"1.0","task_id":"Q141-A10-PAIRWISE-RESIDUAL","status":"COMPLETED_LOCAL_OUTPUTS",
      "source_archive_blob_sha1":ARCHIVE_BLOB,"source_matrix_sha256":MATRIX_SHA256,"outputs":outputs}
    mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","cycle":20,"task_id":"Q141-A10-PAIRWISE-RESIDUAL",
      "status":"COMPLETED_LOCAL_PENDING_REMOTE_READBACK","decision":decision,
      "source_archive_blob_sha1":ARCHIVE_BLOB,"source_matrix_sha256":MATRIX_SHA256,
      "report_path":str(rp),"ledger_path":str(lp),"manifest_path":str(mp),
      "next_action":"Review pair-residual score-test result; keep B11 frozen and pending. Any positive historical result requires separate prospective replication.",
      "governance":report["governance"]}
    cp.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"decision":decision,"targets":n,
      "split_counts":report["design"]["split_counts"],"split_metrics":split,
      "blind_oos_inference":report["blind_oos_inference"],"integrity":report["integrity"]},sort_keys=True))

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--matrix",required=True,type=Path)
    ap.add_argument("--output-dir",default=Path("reports/sequence_agent"),type=Path)
    args=ap.parse_args()
    run(args.matrix,args.output_dir)
