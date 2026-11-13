#!/usr/bin/env python3
"""Q141-D5: formula-level behavioural diversity as a residual correction to Q141-C5."""
from __future__ import annotations
import argparse, bisect, csv, hashlib, io, json, math, zipfile
from pathlib import Path
import numpy as np

Q90_ZIP="12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"
Q90_MATRIX="681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49"
Q90_CATALOG="a61f77ede7136d4eb88a57932488590741fd0b84ace8307d5dd90c192d520586"
SAMPLE_HASH="3ee52f0f270eafb6a8c54c7a7166fe55f2c7730a59ae700ea50b92be6a5412ae"
Q7_BLOB="025fcfa99dc54913fc9b6660aef172bc7cc3ef96"
Q90_FAMILY_BLOB="10d16cc343250ef7e0c4b74864871407b93185da"
C5_BLOB="b0a79cf1f8fc2da5b73cce4ffb6f3a87e8189b1e"
Q7_REPORT_BLOB="56c0ce3420e5ac04b6ba279adf665c587d23fee4"
Q90_REPORT_BLOB="5723a98ba70d194255667d0ad0ea5202d0c45fbf"
C5_REPORT_BLOB="606faf9368660ff8bc680a3dc30baaf6cc2f34bd"
Q7_ARCHIVE="7dab05ba49ace909fe8783eef729605049c65e50"
Q90_ARCHIVE="5d2efd70684e918b27d8f06386d545647898336d"
FAMILIES=("linear_mean_L4","linear_mean_L5","linear_mean_L6","linear_mean_L7","linear_mean_L8","pairwise_interaction_I4","conditional_gate_G4")
START=150; DISCOVERY_END=1972; VALIDATION_END=2629; BLOCK=20; REPS=20000; SEED=14120261113; ALPHA=1.0; THRESHOLD=0.005

def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()
def read_csv(p):
    with Path(p).open(encoding="utf-8",newline="") as f: return list(csv.DictReader(f))
def quintet(s):
    x=tuple(sorted(int(v) for v in str(s).replace(","," ").split()))
    if len(x)!=5 or len(set(x))!=5 or x[0]<1 or x[-1]>40: raise ValueError(f"invalid quintet {s}")
    return x
def write_json(p,x): Path(p).write_text(json.dumps(x,sort_keys=True,indent=2)+"\n",encoding="utf-8")
def select_sample(rows):
    buckets={f:[] for f in FAMILIES}
    for r in rows:
        t=r["formula_type"]; n=int(r["formula_size"])
        fam=f"linear_mean_L{n}" if t=="linear_mean" else ("pairwise_interaction_I4" if t=="pairwise_interaction" else "conditional_gate_G4" if t=="conditional_gate" else "")
        if fam in buckets:
            fid=r["formula_id"]; h=hashlib.sha256(("Q141-B7|"+fid).encode()).hexdigest(); buckets[fam].append((h,fid,r))
    chosen=[]; ids=[]
    for fam in FAMILIES:
        part=sorted(buckets[fam],key=lambda x:(x[0],x[1]))[:100]
        if len(part)!=100: raise RuntimeError(f"sample incomplete: {fam}")
        chosen.extend(x[2] for x in part); ids.extend(x[1] for x in part)
    digest=sha(("\n".join(ids)).encode())
    if len(set(ids))!=700 or digest!=SAMPLE_HASH: raise RuntimeError("fixed Q90 700-formula sample hash mismatch")
    return chosen,digest

def plan_formulas(rows,names):
    ni={n:i for i,n in enumerate(names)}; fi={n:i for i,n in enumerate(FAMILIES)}; k=len(rows); m=max(int(r["formula_size"]) for r in rows)
    idx=np.zeros((k,m),int); mask=np.zeros((k,m)); sizes=np.zeros(k); typ=np.zeros(k,np.int8); a=np.zeros(k,int); b=np.zeros(k,int); gate=np.zeros(k,int); th=np.zeros(k); w=np.zeros(k); fam=np.zeros(k,np.int8)
    for i,r in enumerate(rows):
        ids=[int(x) for x in r["feature_indices"].split(";")]
        if [names[j] for j in ids]!=r["features"].split("+"): raise RuntimeError("formula feature-index/name mismatch")
        idx[i,:len(ids)]=ids; mask[i,:len(ids)]=1; sizes[i]=len(ids); w[i]=float(r["weight"] or 0)
        t=r["formula_type"]
        if t=="linear_mean": family=f"linear_mean_L{len(ids)}"
        elif t=="pairwise_interaction":
            family="pairwise_interaction_I4"; typ[i]=1; aa,bb=r["interaction_pair"].split("*"); a[i]=ni[aa]; b[i]=ni[bb]
            if a[i] not in ids or b[i] not in ids: raise RuntimeError("interaction pair outside base features")
        elif t=="conditional_gate":
            family="conditional_gate_G4"; typ[i]=2; gate[i]=ni[r["gate_feature"]]; th[i]=float(r["gate_threshold"])
            if gate[i] not in ids: raise RuntimeError("gate outside base features")
        else: raise RuntimeError(f"unknown formula type {t}")
        fam[i]=fi[family]
    return dict(idx=idx,mask=mask,sizes=sizes,typ=typ,a=a,b=b,gate=gate,th=th,w=w,fam=fam)

def formula_top5_and_features(row,p):
    x=np.asarray(row,dtype=np.float64)
    if x.shape!=(40,59) or not np.isfinite(x).all(): raise ValueError("expected finite 40x59 prior-only feature row")
    base=(x[:,p["idx"]]*p["mask"][None,:,:]).sum(axis=2)/p["sizes"][None,:]
    scores=base.T.copy(); inter=np.flatnonzero(p["typ"]==1); gates=np.flatnonzero(p["typ"]==2)
    if len(inter):
        prod=x[:,p["a"][inter]]*x[:,p["b"][inter]]; sd=prod.std(axis=0); sd=np.where(sd<1e-12,1,sd)
        scores[inter]+=p["w"][inter,None]*((prod-prod.mean(axis=0))/sd).T
    if len(gates): scores[gates]+=p["w"][gates,None]*(x[:,p["gate"][gates]]>=p["th"][gates][None,:]).T
    top=np.argsort(-np.round(scores,12),axis=1,kind="stable")[:,:5]+1
    votes=np.bincount(top.ravel()-1,minlength=40); prob=votes/votes.sum(); pos=prob>0
    entropy=float(-np.sum(prob[pos]*np.log(prob[pos]))/math.log(40))
    sig=np.bitwise_or.reduce(np.uint64(1)<<(top.astype(np.uint64)-1),axis=1)
    unique=float(len(np.unique(sig))/len(top))
    overlap=float(np.sum(votes*(votes-1)/2)/(math.comb(len(top),2)*5))
    sv=np.sort(votes)[::-1]; margin=float((sv[4]-sv[5])/len(top))
    return top,np.array([entropy,unique,overlap,margin]),votes

def family_shares(top,actual,p):
    hit=np.isin(top,np.asarray(actual)).sum(axis=1); out={}
    for i,f in enumerate(FAMILIES):
        m=p["fam"]==i; out[f]=float(hit[m].sum()/(m.sum()*5))
    return out

def ridge_fit(x,y):
    x=np.asarray(x,float); y=np.asarray(y,float); mean=x.mean(0); scale=x.std(0); scale[scale<1e-12]=1
    z=np.column_stack([np.ones(len(y)),(x-mean)/scale]); penalty=np.eye(z.shape[1])*ALPHA; penalty[0,0]=0
    return mean,scale,np.linalg.solve(z.T@z+penalty,z.T@y)
def ridge_predict(model,x):
    mean,scale,coef=model; z=(np.asarray(x,float)-mean)/scale
    return np.column_stack([np.ones(len(z)),z])@coef
def summary(y,p):
    e=p-y
    return {"targets":len(y),"mae":float(np.mean(np.abs(e))),"rmse":float(np.sqrt(np.mean(e*e))),"mean_error":float(e.mean())}
def block_ci(v,seed):
    x=np.asarray(v,float); rng=np.random.default_rng(seed); n=len(x); nb=math.ceil(n/BLOCK); off=np.arange(BLOCK); out=np.empty(REPS)
    for s in range(0,REPS,500):
        e=min(REPS,s+500); starts=rng.integers(0,n,size=(e-s,nb)); ids=((starts[:,:,None]+off)%n).reshape(e-s,-1)[:,:n]; out[s:e]=x[ids].mean(1)
    return [float(z) for z in np.quantile(out,[.025,.975])]
def signflip(v,seed):
    x=np.asarray(v,float); sums=np.asarray([x[i:i+BLOCK].sum() for i in range(0,len(x),BLOCK)]); rng=np.random.default_rng(seed)
    null=rng.choice([-1.,1.],size=(REPS,len(sums)))@sums/len(x); return float((1+(null>=x.mean()-1e-15).sum())/(REPS+1)),len(sums)

def run(a):
    zbytes=a.q90_zip.read_bytes()
    if sha(zbytes)!=Q90_ZIP: raise RuntimeError("Q90 ZIP hash mismatch")
    with zipfile.ZipFile(io.BytesIO(zbytes)) as z:
        mb=z.read("adaptive_novelty_feature_matrix.npz"); cb=z.read("q90_formula_catalog.csv")
    if sha(mb)!=Q90_MATRIX or sha(cb)!=Q90_CATALOG: raise RuntimeError("Q90 matrix/catalog hash mismatch")
    nz=np.load(io.BytesIO(mb),allow_pickle=False); mat=nz["feature_matrix"].astype(float); dates=nz["target_dates"].astype(str); cuts=nz["cutoff_dates"].astype(str); acts=nz["actual_quintets"].astype(int); names=nz["feature_names"].astype(str).tolist()
    if mat.shape!=(3351,40,59) or str(nz["archive_blob_sha"].item())!=Q90_ARCHIVE: raise RuntimeError("Q90 matrix lineage/shape mismatch")
    q7=read_csv(a.q7_ledger); q90=read_csv(a.q90_family_ledger); c5=read_csv(a.c5_ledger)
    q7r=json.loads(a.q7_report.read_text()); q90r=json.loads(a.q90_family_report.read_text()); c5r=json.loads(a.c5_report.read_text())
    expected={a.q7_ledger:Q7_BLOB,a.q90_family_ledger:Q90_FAMILY_BLOB,a.c5_ledger:C5_BLOB,a.q7_report:Q7_REPORT_BLOB,a.q90_family_report:Q90_REPORT_BLOB,a.c5_report:C5_REPORT_BLOB}
    source_hashes={}
    for path,want in expected.items():
        raw=path.read_bytes(); got=blob(raw)
        if got!=want: raise RuntimeError(f"Git blob mismatch {path.name}")
        source_hashes[path.name]={"git_blob_sha1":got,"sha256":sha(raw),"bytes":len(raw)}
    if q7r.get("task_id")!="Q141-B8" or q7r.get("walkforward",{}).get("strict_prior") is not True: raise RuntimeError("Q7 source not strict-prior")
    if q90r.get("task_id")!="Q141-B7" or q90r.get("formula_universe",{}).get("sample_count")!=700 or q90r.get("formula_universe",{}).get("sample_formula_ids_sha256")!=SAMPLE_HASH or q90r.get("walkforward",{}).get("strict_prior") is not True or q90r.get("source",{}).get("feature_matrix_sha256")!=Q90_MATRIX: raise RuntimeError("Q90 family source report/strict-prior lineage mismatch")
    if q90r.get("source",{}).get("artifact_sha256")!=Q90_ZIP or q90r.get("source",{}).get("archive_blob_sha1")!=Q90_ARCHIVE: raise RuntimeError("Q90 source lineage mismatch")
    if c5r.get("task_id")!="Q141-C5" or c5r.get("walkforward",{}).get("strict_prior") is not True or c5r.get("walkforward",{}).get("coefficients_frozen_after_discovery") is not True: raise RuntimeError("C5 baseline is not frozen strict-prior")
    if len(q7)!=3286 or len(q90)!=3351 or len(c5)!=3186: raise RuntimeError("source ledger dimensions mismatch")
    if q7r.get("source",{}).get("q7_archive_blob_sha1")!=Q7_ARCHIVE or q90r.get("source",{}).get("archive_blob_sha1")!=Q90_ARCHIVE: raise RuntimeError("source archive blob mismatch")
    c5src=c5r.get("source",{})
    for field,path,want in [("q7_ledger_sha256",a.q7_ledger,"828e4fae76795264f15eb7d2c951848c643c7a446eceedf4e887a85120ca8059"),("q90_ledger_sha256",a.q90_family_ledger,"ff72c817f74b54036176d99abbcd2e3cc58bd9df443a690158f9dbe63bb7e6e1")]:
        if sha(path.read_bytes())!=want or c5src.get(field)!=want: raise RuntimeError(f"C5 source SHA mismatch {field}")
    if q7[0]["prior_draws"]!="101" or q7[-1]["prior_draws"]!="3386": raise RuntimeError("Q7 target range mismatch")
    if [r["split"] for r in q7].count("discovery")!=1972 or [r["split"] for r in q7].count("validation")!=657 or [r["split"] for r in q7].count("blind_oos")!=657: raise RuntimeError("Q7 split counts mismatch")
    sample,digest=select_sample(list(csv.DictReader(io.StringIO(cb.decode())))); p=plan_formulas(sample,names)
    q90map={int(r["prior_draws"]):r for r in q90}; c5map={int(r["prior_draws"]):r for r in c5}
    if len(q90map)!=len(q90) or len(c5map)!=len(c5): raise RuntimeError("duplicate source keys")
    d=np.full((len(q7),4),np.nan); y=np.array([float(r["mean_percentile_all_formulas"]) for r in q7]); base=np.full(len(q7),np.nan); fammax=0.; famchecks=0
    for i,r in enumerate(q7):
        key=int(r["prior_draws"]); mi=key-50; actual=quintet(r["actual_quintet"]); qr=q90map.get(key)
        if mi<0 or mi>=len(mat) or qr is None: raise RuntimeError("Q7 target missing Q90 row")
        if str(dates[mi])!=r["target_date"] or str(cuts[mi])!=r["cutoff_date"] or tuple(sorted(acts[mi]))!=actual or r["cutoff_date"]>=r["target_date"]: raise RuntimeError("Q7/Q90 date/cutoff/actual misalignment")
        if qr["target_date"]!=r["target_date"] or qr["cutoff_date"]!=r["cutoff_date"] or quintet(qr["actual_quintet"])!=actual: raise RuntimeError("Q7/Q90 family ledger misalignment")
        top,d[i],votes=formula_top5_and_features(mat[mi],p)
        shares=family_shares(top,actual,p)
        for fam,val in shares.items():
            err=abs(val-float(qr[fam])); fammax=max(fammax,err); famchecks+=1
            if err>1e-12: raise RuntimeError(f"Q90 family score replay mismatch {fam} at {r['target_date']}")
        if votes.sum()!=3500: raise RuntimeError("formula vote count mismatch")
    for i,r in enumerate(q7):
        if i<100: continue
        key=int(r["prior_draws"]); c=c5map.get(key)
        if c is None: raise RuntimeError(f"missing frozen C5 baseline at {key}")
        if c["target_date"]!=r["target_date"] or c["cutoff_date"]!=r["cutoff_date"] or quintet(c["actual_quintet"])!=quintet(r["actual_quintet"]) or c["split"]!=r["split"]: raise RuntimeError("C5/Q7 target alignment mismatch")
        if abs(float(c["q7_mean_percentile_all_formulas"])-y[i])>1e-12: raise RuntimeError("C5/Q7 target outcome mismatch")
        base[i]=float(c["pred_m2_q7_q80_q90"])
    if not np.isfinite(d).all() or not np.isfinite(base[100:]).all(): raise RuntimeError("missing D5 features or C5 predictions")
    c5_metric_replay_max=0.0
    for split in ("discovery","validation","blind_oos"):
        ix=np.asarray([i for i in range(100,len(q7)) if q7[i]["split"]==split],dtype=int)
        observed=summary(y[ix],base[ix]); expected=c5r["metrics_by_split"][split]["m2_q7_q80_q90_ridge"]
        for field,ef in (("mae","mae"),("rmse","rmse"),("mean_error","mean_prediction_error")):
            err=abs(observed[field]-float(expected[ef])); c5_metric_replay_max=max(c5_metric_replay_max,err)
            if err>1e-12: raise RuntimeError(f"C5 report replay mismatch {split}/{field}: {err}")
        if observed["targets"]!=int(expected["targets"]): raise RuntimeError("C5 report replay target count mismatch")
    c5_metric_replay_max = 0.0
    for split in ("discovery", "validation", "blind_oos"):
        ix = np.asarray([i for i in range(100, len(q7)) if q7[i]["split"] == split], dtype=int)
        observed = summary(y[ix], base[ix])
        expected = c5r["metrics_by_split"][split]["m2_q7_q80_q90_ridge"]
        for field, expected_field in (("mae", "mae"), ("rmse", "rmse"), ("mean_error", "mean_prediction_error")):
            err = abs(observed[field] - float(expected[expected_field]))
            c5_metric_replay_max = max(c5_metric_replay_max, err)
            if err > 1e-12: raise RuntimeError(f"C5 baseline report replay mismatch {split}/{field}: {err}")
        if observed["targets"] != int(expected["targets"]): raise RuntimeError("C5 baseline report target count mismatch")
    # Strict-prior suffix mutations on six targets.
    mutations=[]
    for i in (150,250,1000,2000,3000,3285):
        mi=int(q7[i]["prior_draws"])-50; before=formula_top5_and_features(mat[mi],p)[1]
        altered=mat.copy(); rng=np.random.default_rng(SEED+i); altered[mi+1:]=rng.normal(size=altered[mi+1:].shape)
        after=formula_top5_and_features(altered[mi],p)[1]
        if not np.array_equal(before,after): raise RuntimeError("future matrix suffix changed current D5 features")
        mutations.append({"offset":i,"target_date":q7[i]["target_date"],"unchanged":True})
    pred=np.full(len(q7),np.nan); train_n=np.zeros(len(q7),int); mode=["warmup"]*len(q7)
    residual=y-base
    for i in range(START,DISCOVERY_END):
        tr=np.arange(100,i); model=ridge_fit(d[tr],residual[tr]); corr=float(ridge_predict(model,d[i:i+1])[0])
        pred[i]=float(np.clip(base[i]+corr,0,1)); train_n[i]=len(tr); mode[i]="expanding_residual_fit"
    tr=np.arange(100,DISCOVERY_END); frozen=ridge_fit(d[tr],residual[tr])
    for i in range(DISCOVERY_END,len(q7)):
        corr=float(ridge_predict(frozen,d[i:i+1])[0]); pred[i]=float(np.clip(base[i]+corr,0,1)); train_n[i]=len(tr); mode[i]="frozen_discovery_residual_model"
    if not np.isfinite(pred[START:]).all(): raise RuntimeError("D5 predictions incomplete")
    ranges={"discovery":(START,DISCOVERY_END),"validation":(DISCOVERY_END,VALIDATION_END),"blind_oos":(VALIDATION_END,len(q7))}
    metrics={}; ledger=[]
    for split,(lo,hi) in ranges.items():
        ix=np.arange(lo,hi); gain=np.abs(y[ix]-base[ix])-np.abs(y[ix]-pred[ix])
        metrics[split]={"targets":len(ix),"q7_meta_quality_mean":float(y[ix].mean()),"constant_0_5_mae":float(np.mean(np.abs(y[ix]-.5))),"c5_m2_baseline":summary(y[ix],base[ix]),"d5_residual_corrected":summary(y[ix],pred[ix]),"mae_improvement_m2_minus_d5":float(gain.mean()),"mean_vote_entropy":float(d[ix,0].mean()),"mean_unique_top5_share":float(d[ix,1].mean()),"mean_pairwise_overlap":float(d[ix,2].mean()),"mean_boundary_margin":float(d[ix,3].mean())}
        for i in ix:
            r=q7[i]; ledger.append({"prior_draws":int(r["prior_draws"]),"target_date":r["target_date"],"cutoff_date":r["cutoff_date"],"split":split,"actual_quintet":r["actual_quintet"],"q7_mean_percentile_all_formulas":float(y[i]),"vote_entropy_normalized":float(d[i,0]),"unique_top5_share":float(d[i,1]),"pairwise_overlap_fraction":float(d[i,2]),"boundary_margin":float(d[i,3]),"pred_m2_c5":float(base[i]),"pred_m3_d5":float(pred[i]),"abs_error_m2":float(abs(y[i]-base[i])),"abs_error_m3":float(abs(y[i]-pred[i])),"mae_improvement":float(abs(y[i]-base[i])-abs(y[i]-pred[i])),"training_rows":int(train_n[i]),"model_mode":mode[i],"q90_matrix_index":int(r["prior_draws"])-50})
    ix=np.arange(VALIDATION_END,len(q7)); gains=np.abs(y[ix]-base[ix])-np.abs(y[ix]-pred[ix]); effect=float(gains.mean()); ci=block_ci(gains,SEED+1); pv,nb=signflip(gains,SEED+2); passed=effect>=THRESHOLD and ci[0]>0 and pv<.05
    report={"schema_version":"1.0","task_id":"Q141-D5","status":"COMPLETED_HISTORICAL_WALK_FORWARD","decision":"Q90_FORMULA_DIVERSITY_INCREMENTAL_LIFT_DEMONSTRATED" if passed else "NO_Q90_FORMULA_DIVERSITY_INCREMENTAL_LIFT_DEMONSTRATED","hypothesis":"Current-target prior-only diversity across a fixed 700-formula Q90 sample improves next-target Q7 meta-quality beyond the frozen C5 Q7+Q80+Q90 baseline.","estimand":"Blind OOS MAE reduction for Q7 mean percentile across 1,023 quintet-score formulas; this is meta-quality prediction, not winning-number prediction.","formula_sample":{"count":700,"per_family":100,"families":list(FAMILIES),"ordered_ids_sha256":digest,"selection":"lowest SHA256(Q141-B7|formula_id) within each family"},"feature_definitions":{"vote_entropy":"Shannon entropy of 3,500 Top-5 votes over 40 numbers, normalized by log(40)","unique_top5_share":"unique Top-5 signatures divided by 700","pairwise_overlap_fraction":"sum_i C(v_i,2)/(C(700,2)*5)","boundary_margin":"(fifth-highest vote count - sixth-highest vote count)/700"},"walkforward":{"strict_prior":True,"q7_targets":len(q7),"warmup_offsets":150,"scored_targets":{"discovery":1822,"validation":657,"blind_oos":657,"total":3136},"split_offsets":{"discovery":[150,1972],"validation":[1972,2629],"blind_oos":[2629,3286]},"baseline":"Persisted Q141-C5 M2 predictions; source report confirms strict-prior and coefficients frozen after Discovery.","residual_model":"Ridge(alpha=1) predicts C5 residual y-pred_M2 from four current-target D5 features. Discovery is expanding prequential from offsets 100..t-1; model frozen after Discovery.","training_rows_first_discovery":50,"training_rows_frozen":1872,"standardization":"training rows only"},"split_metrics":metrics,"primary_blind_oos":{"mean_mae_improvement":effect,"practical_threshold":THRESHOLD,"ci95_circular_moving_block":ci,"one_sided_block_signflip_p":pv,"block_length":BLOCK,"block_count":nb,"replicates":REPS,"confirmatory_endpoints":1,"within_experiment_multiplicity":"not required for one preregistered primary endpoint; global Q00-Q141 multiplicity not covered","criteria_met":passed},"integrity":{"q7_q90_target_rows_aligned":len(q7),"q90_family_share_replay_comparisons":famchecks,"q90_family_share_replay_max_abs_error":fammax,"future_suffix_mutation_checks":mutations,"target_outcomes_not_used_in_current_d5_features":True,"c5_baseline_target_rows_aligned":len(c5),"c5_baseline_is_strict_prior_and_frozen":True,"c5_baseline_report_replay_max_abs_error":c5_metric_replay_max},"source":{"q90_zip_sha256":Q90_ZIP,"q90_matrix_sha256":Q90_MATRIX,"q90_catalog_sha256":Q90_CATALOG,"q7_archive_blob_sha1":Q7_ARCHIVE,"q90_archive_blob_sha1":Q90_ARCHIVE,"q7_rows":len(q7),"q90_family_rows":len(q90),"c5_baseline_rows":len(c5),"hashes":source_hashes},"limitations":["700 fixed formulas are a deterministic sample of the 330,429 Q90 catalogue, not the full universe.","Q90 uses a 20-feature Discovery-selected subset from 59 available features.","Q7 outcome is the mean percentile of 1,023 quintet-scoring formulas, not a winning-ticket metric.","Historical Blind OOS has prior SONAR exposure and is not virgin prospective evidence.","The one-endpoint correction does not cover the global Q00-Q141 research family."],"governance":{"research_only":True,"no_engine_promotion":True,"no_freeze_mutation":True,"no_archive_mutation":True,"no_merge":True,"protected_prs":[6,7,8]},"next_action":"If D5 fails, archive and stop adding formula-diversity meta-features; continue the independent prospective evidence programme. If it passes, require a new prospective replication without historical retuning."}
    out=a.output_dir; out.mkdir(parents=True,exist_ok=True); lp=out/"q141_d5_formula_behaviour_diversity_target_ledger_2026-11-13.csv"; rp=out/"q141_d5_formula_behaviour_diversity_report_2026-11-13.json"
    with lp.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0])); w.writeheader(); w.writerows(ledger)
    write_json(rp,report)
    code={}
    root=Path(__file__).resolve().parents[1]
    for label,path in (("script",Path(__file__).resolve()),("tests",root/"tests"/"test_sonar_q141_d5_formula_behaviour_diversity.py"),("preregistration",a.preregistration.resolve())):
        raw=path.read_bytes(); code[label]={"path":str(path.relative_to(root)),"sha256":sha(raw),"git_blob_sha1":blob(raw),"bytes":len(raw)}
    manifest={"task_id":"Q141-D5","status":"OUTPUTS_COMPUTED","sample_ids_sha256":digest,"target_rows":len(ledger),"split_counts":{"discovery":1822,"validation":657,"blind_oos":657},"code_lineage":code,"outputs":{"report":{"sha256":sha(rp.read_bytes()),"git_blob_sha1":blob(rp.read_bytes()),"bytes":rp.stat().st_size},"ledger":{"sha256":sha(lp.read_bytes()),"git_blob_sha1":blob(lp.read_bytes()),"bytes":lp.stat().st_size}}}
    mp=out/"q141_d5_formula_behaviour_diversity_manifest_2026-11-13.json"; write_json(mp,manifest)
    cp=out/"q141_d5_formula_behaviour_diversity_checkpoint_2026-11-13.json"; write_json(cp,{"task_id":"Q141-D5","status":"OUTPUTS_COMPUTED_PENDING_REMOTE_READBACK","decision":report["decision"],"blind_oos_effect":effect,"ci95":ci,"p":pv,"target_rows":len(ledger),"sample_ids_sha256":digest,"next_action":report["next_action"]})
    return report

def main():
    ap=argparse.ArgumentParser()
    for n in ("q90-zip","q7-ledger","q90-family-ledger","c5-ledger","q7-report","q90-family-report","c5-report","preregistration","output-dir"): ap.add_argument("--"+n,type=Path,required=True)
    a=ap.parse_args(); r=run(a); print(json.dumps({"decision":r["decision"],"primary_blind_oos":r["primary_blind_oos"],"split_metrics":r["split_metrics"]},sort_keys=True))
if __name__=="__main__": main()
