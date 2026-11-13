#!/usr/bin/env python3
"""Q141-A7: rebuild the strict-prior 59-feature matrix and test stability-weighted family aggregation."""
from __future__ import annotations
import argparse, csv, hashlib, json, math, os, subprocess
from pathlib import Path
import numpy as np

MIN_HISTORY=50
HL=(3,7,14,30,60)
BASE_NAMES=[f"freq_{w}" for w in (5,10,20,50,100,250,500)]+[
 "freq_all","trend_5_vs_50","trend_10_vs_100","trend_20_vs_250",
 "age_since_hit","gap_mean","gap_sd","overdue_ratio","position_log_frequency",
 "pair_count_with_last_draw","neighbor_pm1_history","neighbor_pm2_history",
 "lag_1","lag_2","lag_3","lag_5","lag_10","recent_3","recent_5","recent_10"]
NEW_NAMES=[
 "ewma_hit_hl_3","ewma_hit_hl_7","ewma_hit_hl_14","ewma_hit_hl_30","ewma_hit_hl_60",
 "ewma_acceleration_3_14","ewma_acceleration_7_30","last_gap_vs_median","last_gap_robust_z",
 "gap_cv","gap_slope_recent","gap_hazard_empirical","gap_hazard_residual",
 "pair_lift_recent_last_draw","pair_pmi_recent_last_draw","cooccurrence_strength_recent",
 "cooccurrence_surprise_recent","neighbor_balance_pm1_recent","neighbor_balance_pm2_recent",
 "rank_velocity_5_20","rank_acceleration_5_20_50","rank_volatility_20",
 "feature_disagreement_27","rank_consensus_27","novelty_residual_20","novelty_residual_50",
 "regime_sum_affinity","regime_span_affinity","regime_parity_affinity",
 "regime_entropy_affinity","transition_profile_affinity","conditional_frequency_prev_draw_regime"]
FEATURE_NAMES=BASE_NAMES+NEW_NAMES
FAMILY_INDICES={
 "baseline":list(range(0,27)),
 "ewma_hit_dynamics":list(range(27,34)),
 "gap_dynamics":list(range(34,40)),
 "cooccurrence_novelty":list(range(40,46)),
 "rank_trajectory":list(range(46,51)),
 "residual_surprise":list(range(51,53)),
 "regime_transition_affinity":list(range(53,59))}
FAMILIES=list(FAMILY_INDICES)
EXPECTED_ARCHIVE_BLOB="6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_Q90_ARCHIVE_BLOB="5d2efd70684e918b27d8f06386d545647898336d"
EXPECTED_Q90_TARGETS=3351
EXPECTED_Q90_RUN=42504717670
EXPECTED_Q90_MATRIX_SHA256="681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49"
BLOCK=20
REPLICATES=20000
PRACTICAL_THRESHOLD=0.005

def load_archive(path):
    with Path(path).open(newline="",encoding="utf-8-sig") as f:
        rows=list(csv.reader(f))
    if not rows or [x.strip().lower() for x in rows[0][:6]] not in (
        ["data","n1","n2","n3","n4","n5"],["date","n1","n2","n3","n4","n5"]):
        raise ValueError("A7_BLOCKED: unexpected archive header")
    dates=[];draws=[];seen=set();prev=""
    for line,row in enumerate(rows[1:],2):
        if not row or not any(x.strip() for x in row): continue
        d=row[0].strip()
        nums=tuple(int(x) for x in row[1:6])
        if d in seen or (prev and d<=prev): raise ValueError(f"A7_BLOCKED: duplicate/nonchronological date at line {line}")
        if len(nums)!=5 or len(set(nums))!=5 or nums!=tuple(sorted(nums)) or any(x<1 or x>40 for x in nums):
            raise ValueError(f"A7_BLOCKED: invalid quintet at {d}")
        dates.append(d);draws.append(nums);seen.add(d);prev=d
    if len(draws)<=MIN_HISTORY: raise ValueError("A7_BLOCKED: archive too short")
    return dates,draws

def zscore_columns(a):
    a=np.asarray(a,dtype=np.float64)
    mean=a.mean(axis=0);sd=a.std(axis=0);sd[sd<1e-12]=1.0
    return (a-mean)/sd

def rank_matrix(a):
    a=np.asarray(a,float);idx=np.arange(a.shape[0])
    order=np.empty(a.shape,dtype=np.int64)
    for c in range(a.shape[1]): order[:,c]=np.lexsort((idx,-np.round(a[:,c],12)))
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(a.shape[1])]=np.arange(1,a.shape[0]+1)[:,None]
    return ranks

def rank_desc(v):
    order=np.lexsort((np.arange(40),-np.round(np.asarray(v,float),12)))
    r=np.empty(40,dtype=np.int16);r[order]=np.arange(1,41,dtype=np.int16)
    return r

def neighbor_balance(counts,radius):
    counts=np.asarray(counts,float)
    return np.asarray([sum(counts[u] for u in range(max(0,v-radius),min(40,v+radius+1)) if u!=v)
                       for v in range(40)],dtype=float)

def sum_regime_bin(draw): return min(4,max(0,(sum(draw)-15)//35))
def span_regime_bin(draw): return min(3,max(0,(max(draw)-min(draw)-4)//9))
def parity_entropy_bin(draw):
    odd=sum(v%2 for v in draw)
    return 0 if odd in (0,5) else (1 if odd in (1,4) else 2)

def q80_feature_matrix(i,draws,prefix,pos_prefix,pair_counts,occ):
    out=np.zeros((40,27),dtype=np.float64)
    for col,w in enumerate((5,10,20,50,100,250,500)):
        out[:,col]=prefix[i]-prefix[max(0,i-w)]
    out[:,7]=prefix[i]
    out[:,8]=out[:,0]/max(1,min(i,5))-out[:,3]/max(1,min(i,50))
    out[:,9]=out[:,1]/max(1,min(i,10))-out[:,4]/max(1,min(i,100))
    out[:,10]=out[:,2]/max(1,min(i,20))-out[:,5]/max(1,min(i,250))
    ages=np.full(40,i+1,dtype=np.float64)
    for n,seen in enumerate(occ):
        if seen: ages[n]=i-seen[-1]
    out[:,11]=ages
    for n,seen in enumerate(occ):
        gaps=np.diff(seen)
        if len(gaps): out[n,12]=float(np.mean(gaps));out[n,13]=float(np.std(gaps))
        else: out[n,12]=max(1,i);out[n,13]=0.0
    out[:,14]=out[:,11]/np.maximum(out[:,12],1.0)
    if i:
        pos=pos_prefix[i].astype(np.float64)
        out[:,15]=np.log((pos+0.5)/(i+20.0)).mean(axis=0)
        last=np.asarray(draws[i-1],dtype=int)-1
        out[:,16]=pair_counts[:,last].mean(axis=1)
    counts=prefix[i]
    out[:,17]=np.asarray([sum(counts[max(0,n-1):min(40,n+2)])-counts[n] for n in range(40)],float)
    out[:,18]=np.asarray([sum(counts[max(0,n-2):min(40,n+3)])-counts[n] for n in range(40)],float)
    for lag,col in ((1,19),(2,20),(3,21),(5,22),(10,23)):
        if i>=lag:
            present=set(draws[i-lag])
            out[:,col]=[1.0 if n+1 in present else 0.0 for n in range(40)]
    for w,col in ((3,24),(5,25),(10,26)):
        out[:,col]=prefix[i]-prefix[max(0,i-w)]
    return out

def compute_feature_matrix(draws):
    n=len(draws)
    prefix=np.zeros((n+1,40),dtype=np.int32)
    pos=np.zeros((n+1,5,40),dtype=np.int32)
    pair=np.zeros((40,40),dtype=np.int32)
    occ=[[] for _ in range(40)]
    ew={h:np.zeros(40,dtype=np.float64) for h in HL}
    rankhist=[];regimes=[];sum_bins=[];span_bins=[];odd_counts=[];entropy_bins=[]
    tensor=np.zeros((n-MIN_HISTORY,40,59),dtype=np.float32)
    for i,actual in enumerate(draws):
        if i>=MIN_HISTORY:
            base=q80_feature_matrix(i,draws,prefix,pos,pair,occ)
            cur_r=rank_matrix(zscore_columns(base))
            x=np.zeros((40,32),dtype=np.float64)
            for k,h in enumerate(HL): x[:,k]=ew[h]
            x[:,5]=ew[3]-ew[14];x[:,6]=ew[7]-ew[30]
            for v in range(40):
                gaps=np.diff(occ[v]);age=i-occ[v][-1] if occ[v] else i+1
                med=float(np.median(gaps)) if len(gaps) else 0.0
                mad=float(np.median(np.abs(gaps-med))) if len(gaps) else 0.0
                x[v,7]=(age-med)/max(med,1)
                x[v,8]=(age-med)/max(1,1.4826*mad)
                x[v,9]=float(np.std(gaps)/max(np.mean(gaps),1)) if len(gaps)>1 else 0.0
                gg=gaps[-8:];tt=np.arange(len(gg),dtype=float);den=float(np.sum((tt-tt.mean())**2))
                x[v,10]=float(np.sum((tt-tt.mean())*(gg-gg.mean()))/den) if len(gg)>=3 and den>0 else 0.0
                x[v,11]=(sum(gaps==age)+2/(med+1))/(max(1,sum(gaps>=age))+2) if len(gaps) else 1/(age+1)
                x[v,12]=x[v,11]-1/(med+1)
            last=np.asarray(draws[i-1])-1
            recent=np.zeros((40,40),dtype=np.float64)
            ws=max(0,i-30);wn=i-ws
            for t in range(ws,i):
                for a in draws[t]:
                    for b in draws[t]:
                        if a!=b: recent[a-1,b-1]+=1
            freq=prefix[i].astype(float);freq_recent=(prefix[i]-prefix[ws]).astype(float)
            p=(freq_recent+2.5)/(wn+20.0)
            for v in range(40):
                lift=[];pm=[];surprise=[]
                for u in last:
                    pxy=(recent[v,u]+0.25)/(wn+20.0)
                    l=pxy/max(p[v]*p[u],1e-9)
                    lift.append(l);pm.append(math.log(max(l,1e-9)))
                    surprise.append(math.log((recent[v,u]+0.25)/(wn+20.0))-math.log((pair[v,u]+0.25)/(i+20.0)))
                x[v,13]=np.mean(lift);x[v,14]=np.mean(pm)
                x[v,15]=recent[v,last].mean()/max(wn,1);x[v,16]=np.mean(surprise)
            x[:,17]=neighbor_balance(freq_recent,1);x[:,18]=neighbor_balance(freq_recent,2)
            h=np.asarray(rankhist[-50:],dtype=float)
            if len(h)>=20:
                x[:,19]=h[-5:].mean(axis=(0,2))-h[-20:].mean(axis=(0,2))
                x[:,21]=h[-20:].std(axis=(0,2))
            if len(h)>=50: x[:,20]=h[-20:].mean(axis=(0,2))-h[-50:].mean(axis=(0,2))
            x[:,22]=cur_r.std(axis=1);x[:,23]=np.median(cur_r,axis=1)
            for w,col in ((20,24),(50,25)):
                hits=prefix[i]-prefix[max(0,i-w)]
                rate=(freq+0.5)/(i+20.0);expected=rate*min(w,i)
                x[:,col]=(hits-expected)/np.sqrt(np.maximum(expected*(1-rate),0.25))
            prev_reg=regimes[i-1];prev_transition=(regimes[i-2],regimes[i-1])
            csum=np.zeros(40);cspan=np.zeros(40);codd=np.zeros(40);cent=np.zeros(40);ctrans=np.zeros(40);creg=np.zeros(40)
            nsum=nspan=nodd=nent=ntrans=nreg=0
            for t in range(max(0,i-250),i):
                d=draws[t]
                if sum_bins[t]==sum_bins[i-1]: nsum+=1;csum[np.asarray(d)-1]+=1
                if span_bins[t]==span_bins[i-1]: nspan+=1;cspan[np.asarray(d)-1]+=1
                if odd_counts[t]==odd_counts[i-1]: nodd+=1;codd[np.asarray(d)-1]+=1
                if entropy_bins[t]==entropy_bins[i-1]: nent+=1;cent[np.asarray(d)-1]+=1
                if regimes[t]==prev_reg: nreg+=1;creg[np.asarray(d)-1]+=1
                if t>=1 and regimes[t-1]==prev_transition[0] and regimes[t]==prev_transition[1]:
                    ntrans+=1;ctrans[np.asarray(d)-1]+=1
            x[:,26]=(csum+2.5)/(nsum+20.0);x[:,27]=(cspan+2.5)/(nspan+20.0)
            x[:,28]=(codd+2.5)/(nodd+20.0);x[:,29]=(cent+2.5)/(nent+20.0)
            x[:,30]=(ctrans+2.5)/(ntrans+20.0);x[:,31]=(creg+2.5)/(nreg+20.0)
            tensor[i-MIN_HISTORY]=zscore_columns(np.column_stack((base,x))).astype(np.float32)
            rankhist.append(cur_r)
        # All recursive states are advanced only after the current target features were scored.
        for h in HL:
            decay=math.exp(math.log(0.5)/h);ew[h]=ew[h]*decay
            for v in actual: ew[h][v-1]+=1-decay
        prefix[i+1]=prefix[i];pos[i+1]=pos[i]
        for p0,v in enumerate(actual):
            prefix[i+1,v-1]+=1;pos[i+1,p0,v-1]+=1;occ[v-1].append(i)
        for a in actual:
            for b in actual:
                if a!=b: pair[a-1,b-1]+=1
        regimes.append(int(sum(actual)>=100)+2*int(max(actual)-min(actual)>=25)+4*int(sum(v%2 for v in actual)>=3))
        sum_bins.append(sum_regime_bin(actual));span_bins.append(span_regime_bin(actual))
        odd_counts.append(sum(v%2 for v in actual));entropy_bins.append(parity_entropy_bin(actual))
    return tensor

def weights_from_history(rank_history):
    history=np.asarray(rank_history,dtype=np.int16)
    if history.shape!=(5,7,40): raise ValueError("history must be 5 x 7 x 40")
    turnover=np.mean(np.abs(np.diff(history,axis=0)),axis=(0,2))/39.0
    raw=1.0/(0.10+turnover)
    return raw/raw.sum(),turnover

def split_name(i,n):
    p=i/max(n,1)
    return "discovery" if p<0.60 else ("validation" if p<0.80 else "blind_oos")

def holm_adjust(p_values):
    p=np.asarray(p_values,float);order=np.argsort(p,kind="mergesort")
    out=np.empty(len(p),dtype=float);running=0.0
    for rank,idx in enumerate(order):
        running=max(running,min(1.0,(len(p)-rank)*p[idx]));out[idx]=running
    return out.tolist()

def block_signflip_p(d,seed):
    d=np.asarray(d,float);sums=np.asarray([d[i:i+BLOCK].sum() for i in range(0,len(d),BLOCK)])
    obs=float(d.mean());rng=np.random.default_rng(seed)
    signs=rng.choice(np.array([-1.0,1.0]),size=(REPLICATES,len(sums)))
    simulated=(signs*sums).sum(axis=1)/len(d)
    return float((np.sum(np.abs(simulated)>=abs(obs))+1)/(REPLICATES+1)),len(sums)

def circular_block_ci(d,seed):
    d=np.asarray(d,float);n=len(d);rng=np.random.default_rng(seed)
    blocks=math.ceil(n/BLOCK);out=[];offsets=np.arange(BLOCK)
    for start in range(0,REPLICATES,1000):
        batch=min(1000,REPLICATES-start)
        starts=rng.integers(0,n,size=(batch,blocks))
        idx=(starts[:,:,None]+offsets[None,None,:])%n
        samples=d[idx.reshape(batch,-1)[:,:n]]
        out.extend(samples.mean(axis=1).tolist())
    return [float(x) for x in np.quantile(np.asarray(out),[0.025,0.975])]

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def git_blob_sha1(path):
    b=Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def build_model_rows(matrix,dates,draws):
    t_count=len(matrix)
    family_scores=np.stack([matrix[:,:,FAMILY_INDICES[f]].mean(axis=2) for f in FAMILIES],axis=1)
    family_ranks=np.empty((t_count,7,40),dtype=np.int16)
    for t in range(t_count):
        for f in range(7): family_ranks[t,f]=rank_desc(family_scores[t,f])
    rows=[]
    for t in range(t_count):
        if t>=5:
            weights,turnover=weights_from_history(family_ranks[t-5:t])
        else:
            weights=np.full(7,1.0/7.0);turnover=np.full(7,np.nan)
        equal=family_scores[t].mean(axis=0)
        adaptive=np.sum(family_scores[t]*weights[:,None],axis=0)
        feature_uniform=matrix[t].mean(axis=1)
        actual=draws[t+MIN_HISTORY]
        def hits(scores,k):
            order=np.lexsort((np.arange(40),-np.round(scores,12)))
            top=set((order[:k]+1).tolist())
            return int(sum(v in top for v in actual))
        target_idx=t+MIN_HISTORY
        rows.append({
            "target_index":t,"target_date":dates[target_idx],"cutoff_date":dates[target_idx-1],
            "prior_draws":target_idx,"split":split_name(t,t_count),
            "actual_quintet":" ".join(map(str,actual)),
            "adaptive_top5_hits":hits(adaptive,5),"equal_family_top5_hits":hits(equal,5),
            "equal_feature_top5_hits":hits(feature_uniform,5),
            "adaptive_top10_hits":hits(adaptive,10),"equal_family_top10_hits":hits(equal,10),
            "equal_feature_top10_hits":hits(feature_uniform,10),
            "mean_prior_family_turnover":float(np.nanmean(turnover)) if t>=5 else "",
            "family_weights_json":json.dumps(weights.tolist(),separators=(",",":"))
        })
    return rows

def summarize(rows):
    result={}
    for split in ("discovery","validation","blind_oos"):
        group=[r for r in rows if r["split"]==split];n=len(group)
        result[split]={
            "targets":n,
            "equal_family_top5":sum(r["equal_family_top5_hits"] for r in group)/(5*n),
            "stability_weighted_top5":sum(r["adaptive_top5_hits"] for r in group)/(5*n),
            "equal_feature_top5":sum(r["equal_feature_top5_hits"] for r in group)/(5*n),
            "equal_family_top10":sum(r["equal_family_top10_hits"] for r in group)/(5*n),
            "stability_weighted_top10":sum(r["adaptive_top10_hits"] for r in group)/(5*n),
            "equal_feature_top10":sum(r["equal_feature_top10_hits"] for r in group)/(5*n),
            "uniform_top5_reference":0.125,"uniform_top10_reference":0.25,
            "mean_family_turnover":float(np.mean([float(r["mean_prior_family_turnover"]) for r in group if r["mean_prior_family_turnover"]!=""]))
        }
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--archive",default="data/storico_daily.csv")
    ap.add_argument("--q90-matrix",required=True)
    ap.add_argument("--out-dir",default="reports/sequence_agent")
    args=ap.parse_args()
    out=Path(args.out_dir);out.mkdir(parents=True,exist_ok=True)
    dates,draws=load_archive(args.archive)
    archive_blob=subprocess.check_output(["git","rev-parse","HEAD:data/storico_daily.csv"],text=True).strip()
    if archive_blob!=EXPECTED_ARCHIVE_BLOB: raise SystemExit(f"A7_BLOCKED: archive blob {archive_blob} != pinned {EXPECTED_ARCHIVE_BLOB}")
    if len(draws)!=3406 or dates[-1]!="2026-11-12": raise SystemExit("A7_BLOCKED: archive count/date mismatch")
    matrix=compute_feature_matrix(draws)
    if matrix.shape!=(3356,40,59) or matrix.dtype!=np.float32 or not np.isfinite(matrix).all():
        raise SystemExit("A7_BLOCKED: rebuilt matrix shape/dtype/finite check failed")
    q90_path=Path(args.q90_matrix)
    with np.load(q90_path,allow_pickle=False) as q:
        q90=q["feature_matrix"];qdates=q["target_dates"].astype(str);qcut=q["cutoff_dates"].astype(str)
        qnames=q["feature_names"].astype(str);qblob=str(q["archive_blob_sha"].item())
    if qblob!=EXPECTED_Q90_ARCHIVE_BLOB or q90.shape!=(EXPECTED_Q90_TARGETS,40,59):
        raise SystemExit("A7_BLOCKED: pinned Q90 matrix identity/shape mismatch")
    if sha256_file(q90_path)!=EXPECTED_Q90_MATRIX_SHA256:
        raise SystemExit("A7_BLOCKED: pinned Q90 matrix SHA-256 mismatch")
    if qnames.tolist()!=FEATURE_NAMES or qdates.tolist()!=dates[50:3401] or qcut.tolist()!=dates[49:3400]:
        raise SystemExit("A7_BLOCKED: Q90 prefix date/name lineage mismatch")
    if not np.array_equal(matrix[:EXPECTED_Q90_TARGETS],q90):
        delta=float(np.max(np.abs(matrix[:EXPECTED_Q90_TARGETS].astype(np.float64)-q90.astype(np.float64))))
        raise SystemExit(f"A7_BLOCKED: rebuilt Q90 prefix is not bit-identical; max_abs_diff={delta}")
    if np.max(np.abs(matrix.mean(axis=1)))>1e-5: raise SystemExit("A7_BLOCKED: per-target z-score centering failed")
    target_dates=np.asarray(dates[50:],dtype="U10")
    cutoff_dates=np.asarray(dates[49:-1],dtype="U10")
    actual=np.asarray(draws[50:],dtype=np.uint8)
    matrix_path=out/"q141_a7_fresh59_feature_matrix_2026-11-13.npz"
    np.savez_compressed(matrix_path,feature_matrix=matrix,target_dates=target_dates,
        cutoff_dates=cutoff_dates,actual_quintets=actual,feature_names=np.asarray(FEATURE_NAMES,dtype="U64"),
        archive_blob_sha=np.asarray(archive_blob,dtype="U64"))
    rows=build_model_rows(matrix,dates,draws)
    expected_counts={"discovery":2014,"validation":671,"blind_oos":671}
    observed={s:sum(r["split"]==s for r in rows) for s in expected_counts}
    if observed!=expected_counts: raise SystemExit(f"A7_BLOCKED: split counts {observed}")
    ledger_path=out/"q141_a7_stability_weighted_target_ledger_2026-11-13.csv"
    with ledger_path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    metrics=summarize(rows)
    blind=[r for r in rows if r["split"]=="blind_oos"]
    d5=np.asarray([(r["adaptive_top5_hits"]-r["equal_family_top5_hits"])/5 for r in blind],float)
    d10=np.asarray([(r["adaptive_top10_hits"]-r["equal_family_top10_hits"])/5 for r in blind],float)
    p5,blocks5=block_signflip_p(d5,14120261113);p10,blocks10=block_signflip_p(d10,14120261114)
    ci5=circular_block_ci(d5,14120261115);ci10=circular_block_ci(d10,14120261116)
    adjusted=holm_adjust([p5,p10])
    primary_mean=float(d5.mean())
    decision="NO_STABILITY_WEIGHTING_LIFT_DEMONSTRATED"
    if primary_mean>=PRACTICAL_THRESHOLD and ci5[0]>0 and adjusted[0]<0.05:
        decision="HISTORICAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION"
    report={
      "schema_version":"1.0","task_id":"Q141-A7-B11","status":"COMPLETED_HISTORICAL_WALK_FORWARD",
      "decision":decision,
      "source":{"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        "archive_blob_sha1":archive_blob,"draw_count":len(draws),"first_date":dates[0],"last_date":dates[-1],
        "q90_source_run_id":EXPECTED_Q90_RUN,"q90_archive_blob_sha1":qblob,"q90_prefix_targets":EXPECTED_Q90_TARGETS,
        "q90_prefix_matrix_exact_bit_match":True,"q90_prefix_max_abs_difference":0.0,
        "q90_matrix_sha256":sha256_file(q90_path)},
      "design":{"feature_count":59,"feature_families":{k:len(v) for k,v in FAMILY_INDICES.items()},
        "min_prior_draws":MIN_HISTORY,"targets":len(rows),"split_counts":observed,
        "family_score":"mean of the per-target z-scored features within each family",
        "equal_family_baseline":"unweighted mean of seven family scores",
        "adaptive_rule":"weights proportional to 1/(0.10 + mean normalized absolute rank turnover over the previous five target rows); weights use only earlier feature rows",
        "turnover_window_target_rows":5,"turnover_smoothing":0.10,"fallback_first_five_targets":"equal family weights",
        "tie_policy":"scores rounded to 12 decimals; ties by number ascending",
        "primary_endpoint":"Blind OOS Top-5 number hit share, stability-weighted minus equal-family",
        "secondary_endpoint":"Blind OOS Top-10 number hit share, stability-weighted minus equal-family",
        "practical_threshold":PRACTICAL_THRESHOLD,"block_length":BLOCK,"replicates":REPLICATES,
        "holm_family_size":2},
      "split_metrics":metrics,
      "blind_oos_inference":{
        "targets":len(blind),"primary_top5_delta":primary_mean,"primary_top5_ci95":ci5,
        "primary_top5_block_signflip_p":p5,"primary_top5_holm_p":adjusted[0],
        "secondary_top10_delta":float(d10.mean()),"secondary_top10_ci95":ci10,
        "secondary_top10_block_signflip_p":p10,"secondary_top10_holm_p":adjusted[1],
        "block_count_top5":blocks5,"block_count_top10":blocks10,
        "mean_family_weights":{fam:float(np.mean([json.loads(r["family_weights_json"])[i] for r in blind]))
          for i,fam in enumerate(FAMILIES)},
        "mean_prior_family_turnover":float(np.mean([float(r["mean_prior_family_turnover"]) for r in blind if r["mean_prior_family_turnover"]!=""]))},
      "tests":{"archive_blob_pinned":True,"all_59_features_rebuilt":True,"q90_prefix_bit_identical":True,
        "strict_prior_cutoffs":True,"score_before_state_update":True,"all_matrix_values_finite":True,
        "zscore_centering_max_abs":float(np.max(np.abs(matrix.mean(axis=1)))),
        "deterministic_replay":"verified by unit tests"},
      "limitations":[
        "The historical Blind OOS has been exposed to prior SONAR research; it is not virgin prospective evidence.",
        "This evaluates per-number ranking hit share, not the probability of an exact five-number ticket.",
        "The stability-weighted rule is fixed and untrained; no hyperparameter search was performed.",
        "Feature families share source information and are not statistically independent.",
        "The Q90 prefix was reused only after bit-identical full recomputation; five new rows extend the matrix through 2026-11-12.",
        "No result from this historical analysis authorizes production promotion."
      ]}
    report_path=out/"q141_a7_stability_weighted_report_2026-11-13.json"
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    files=[matrix_path,ledger_path,report_path]
    manifest={"schema_version":"1.0","task_id":"Q141-A7-B11","status":"COMPLETED_LOCAL_OUTPUTS",
      "source_archive_blob_sha1":archive_blob,"source_draw_count":len(draws),"source_last_date":dates[-1],
      "q90_prefix_matrix_exact_bit_match":True,"feature_matrix_shape":list(matrix.shape),
      "feature_names_sha256":hashlib.sha256("\n".join(FEATURE_NAMES).encode()).hexdigest(),
      "outputs":{p.name:{"bytes":p.stat().st_size,"sha256":sha256_file(p),"git_blob_sha1":git_blob_sha1(p)} for p in files}}
    manifest_path=out/"q141_a7_fresh59_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","cycle":15,"task_id":"Q141-A7-B11","status":"COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
      "decision":decision,"source_commit":report["source"]["source_commit"],"archive_blob_sha1":archive_blob,
      "workflow_run_id":int(os.environ.get("GITHUB_RUN_ID","0")),"report_path":str(report_path),
      "ledger_path":str(ledger_path),"matrix_artifact_path":str(matrix_path),
      "next_action":"Review the exact-head dedicated workflow and artifact readback; then reserve new post-2026-11-12 draws for genuinely prospective evaluation.",
      "governance":{"pr89":"untouched","pr6":"untouched","pr7":"untouched","pr8":"untouched",
        "engine_promotion":False,"canonical_archive_mutation":False,"shadow_insertion":False,"merge":False}}
    checkpoint_path=out/"q141_a7_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"decision":decision,"split_metrics":metrics,"blind_oos_inference":report["blind_oos_inference"],
      "archive_blob_sha1":archive_blob,"matrix_shape":list(matrix.shape),"q90_prefix_bit_identical":True,
      "outputs":[{"path":p.name,"bytes":p.stat().st_size,"sha256":sha256_file(p),"git_blob_sha1":git_blob_sha1(p)} for p in [matrix_path,ledger_path,report_path,manifest_path,checkpoint_path]]},ensure_ascii=False))

if __name__=="__main__": main()
