#!/usr/bin/env python3
"""Q89 walk-forward feature engine. Each target uses only its strict historical prefix."""
import csv,json,math,hashlib,subprocess
from itertools import combinations
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"reports/sequence_agent"; ARCH=ROOT/"data/storico_daily.csv"
HL=(3,7,14,30,60)
NEW=["ewma_hit_hl_3","ewma_hit_hl_7","ewma_hit_hl_14","ewma_hit_hl_30","ewma_hit_hl_60","ewma_acceleration_3_14","ewma_acceleration_7_30","last_gap_vs_median","last_gap_robust_z","gap_cv","gap_slope_recent","gap_hazard_empirical","gap_hazard_residual","pair_lift_recent_last_draw","pair_pmi_recent_last_draw","cooccurrence_strength_recent","cooccurrence_surprise_recent","neighbor_balance_pm1_recent","neighbor_balance_pm2_recent","rank_velocity_5_20","rank_acceleration_5_20_50","rank_volatility_20","feature_disagreement_27","rank_consensus_27","novelty_residual_20","novelty_residual_50","regime_sum_affinity","regime_span_affinity","regime_parity_affinity","regime_entropy_affinity","transition_profile_affinity","conditional_frequency_prev_draw_regime"]
NAMES=q80.FEATURE_NAMES+NEW
NEW_FAMILIES=["ewma_hit_dynamics"]*7+["gap_dynamics"]*6+["cooccurrence_novelty"]*6+["rank_trajectory"]*5+["residual_surprise"]*2+["regime_transition_affinity"]*6
def z(a):
 a=np.asarray(a,float); sd=a.std(axis=0); sd[sd<1e-12]=1; return (a-a.mean(axis=0))/sd
def ranks(a):
 a=np.asarray(a,float); idx=np.arange(a.shape[0]); order=np.empty(a.shape,np.int16)
 for c in range(a.shape[1]):order[:,c]=np.lexsort((idx,-np.round(a[:,c],12)))
 r=np.empty(order.shape,np.int16);r[order,np.arange(a.shape[1])]=np.arange(1,a.shape[0]+1)[:,None];return r
def rank_sum_int(r):
 return int(np.sum(r,dtype=np.int64))
def neighbor_balance(counts,radius):
 counts=np.asarray(counts,float)
 return np.asarray([sum(counts[u] for u in range(max(0,v-radius),min(40,v+radius+1)) if u!=v) for v in range(40)],float)
def duplicate_rank_pairs(rank_matrix):
 groups={}
 for c in range(rank_matrix.shape[1]):
  key=np.ascontiguousarray(rank_matrix[:,c]).tobytes();groups.setdefault(key,[]).append(c)
 return [pair for group in groups.values() for pair in combinations(group,2)]
def sum_regime_bin(draw):
 return min(4,max(0,(sum(draw)-15)//35))
def span_regime_bin(draw):
 return min(3,max(0,(max(draw)-min(draw)-4)//9))
def parity_entropy_bin(draw):
 odd=sum(v%2 for v in draw)
 return 0 if odd in (0,5) else (1 if odd in (1,4) else 2)
def load():
 with ARCH.open(newline="",encoding="utf-8-sig") as f: rows=list(csv.reader(f))
 dates=[];draws=[]
 for row in rows[1:]:
  if not row:continue
  nums=tuple(map(int,row[1:6]));d=row[0]
  if len(set(nums))!=5 or tuple(sorted(nums))!=nums or (dates and d<=dates[-1]):raise ValueError("invalid archive chronology")
  dates.append(d);draws.append(nums)
 return dates,draws
def main():
 dates,draws=load(); n=len(draws)
 assert n>50 and dates[-1]
 blob_sha=subprocess.check_output(["git","rev-parse","HEAD:data/storico_daily.csv"],cwd=ROOT,text=True).strip()
 checkpoint_date=dates[-1]
 prefix=np.zeros((n+1,40),np.int32);pos=np.zeros((n+1,5,40),np.int32);pair=np.zeros((40,40),np.int32);occ=[[] for _ in range(40)]
 ew={h:np.zeros(40) for h in HL};rankhist=[];regimes=[];sum_bins=[];span_bins=[];odd_counts=[];entropy_bins=[]
 split_names=("discovery","validation","blind_oos");split_metric={sp:{name:[0,0,0,0,0] for name in NAMES} for sp in split_names};duplicate_rank_counts={};feature_tensor=np.zeros((n-50,40,59),dtype=np.float32)
 metric={name:[0,0,0,0,0,0.0,float("inf"),float("-inf")] for name in NAMES}; ledger=[]
 for i,actual in enumerate(draws):
  if i>=50:
   base=q80.feature_matrix(i,draws,prefix,pos,pair,occ,np.zeros(40),np.zeros(40),np.zeros(40)); cur_r=ranks(z(base))
   x=np.zeros((40,32)); support=np.full(59,float(i)); support[27:34]=i
   for k,h in enumerate(HL):x[:,k]=ew[h]
   x[:,5]=ew[3]-ew[14];x[:,6]=ew[7]-ew[30]
   gap_supports=[]
   for v in range(40):
    g=np.diff(occ[v]);gap_supports.append(len(g));age=i-occ[v][-1] if occ[v] else i+1;med=float(np.median(g)) if len(g) else 0;mad=float(np.median(abs(g-med))) if len(g) else 0
    x[v,7]=(age-med)/max(med,1);x[v,8]=(age-med)/max(1,1.4826*mad);x[v,9]=float(np.std(g)/max(np.mean(g),1)) if len(g)>1 else 0
    gg=g[-8:];tt=np.arange(len(gg),dtype=float);den=float(np.sum((tt-tt.mean())**2))
    x[v,10]=float(np.sum((tt-tt.mean())*(gg-gg.mean()))/den) if len(gg)>=3 and den>0 else 0
    x[v,11]=(sum(g==age)+2/(med+1))/(max(1,sum(g>=age))+2) if len(g) else 1/(age+1);x[v,12]=x[v,11]-1/(med+1)
   support[34:40]=float(np.mean(gap_supports))
   last=np.array(draws[i-1])-1
   recent=np.zeros((40,40));window_start=max(0,i-30);window_n=i-window_start
   for t in range(window_start,i):
    for a in draws[t]:
     for b in draws[t]:
      if a!=b:recent[a-1,b-1]+=1
   freq=prefix[i].astype(float);freq_recent=(prefix[i]-prefix[window_start]).astype(float);p=(freq_recent+2.5)/(window_n+20.0);support[40:44]=window_n
   for v in range(40):
    lift=[];pm=[];surprise=[]
    for u in last:
     pxy=(recent[v,u]+0.25)/(window_n+20.0);py=p[u]
     l=pxy/max(p[v]*py,1e-9);lift.append(l);pm.append(math.log(max(l,1e-9)))
     surprise.append(math.log((recent[v,u]+0.25)/(window_n+20.0))-math.log((pair[v,u]+0.25)/(i+20.0)))
    x[v,13]=np.mean(lift);x[v,14]=np.mean(pm);x[v,15]=recent[v,last].mean()/max(window_n,1);x[v,16]=np.mean(surprise)
   x[:,17]=neighbor_balance(freq_recent,1);x[:,18]=neighbor_balance(freq_recent,2)
   support[44:46]=window_n
   h=np.asarray(rankhist[-50:],float)
   if len(h)>=20:
    x[:,19]=h[-5:].mean(axis=(0,2))-h[-20:].mean(axis=(0,2));x[:,21]=h[-20:].std(axis=(0,2))
   if len(h)>=50:x[:,20]=h[-20:].mean(axis=(0,2))-h[-50:].mean(axis=(0,2))
   x[:,22]=cur_r.std(axis=1);x[:,23]=np.median(cur_r,axis=1)
   support[46:51]=[20 if len(rankhist)>=20 else 0,50 if len(rankhist)>=50 else 0,20 if len(rankhist)>=20 else 0,27,27]
   for w,col in [(20,24),(50,25)]:
    hits=prefix[i]-prefix[max(0,i-w)];rate=(freq+.5)/(i+20);exp=rate*min(w,i);x[:,col]=(hits-exp)/np.sqrt(np.maximum(exp*(1-rate),.25))
   support[51:53]=[min(20,i),min(50,i)]
   prev=draws[i-1];prev_reg=regimes[i-1];prev_transition=(regimes[i-2],regimes[i-1])
   csum=np.zeros(40);cspan=np.zeros(40);codd=np.zeros(40);cent=np.zeros(40);ctrans=np.zeros(40);creg=np.zeros(40)
   nsum=nspan=nodd=nent=ntrans=nreg=0;regime_start=max(0,i-250)
   for t in range(regime_start,i):
    d=draws[t]
    if sum_bins[t]==sum_bins[i-1]:nsum+=1;csum[np.array(d)-1]+=1
    if span_bins[t]==span_bins[i-1]:nspan+=1;cspan[np.array(d)-1]+=1
    if odd_counts[t]==odd_counts[i-1]:nodd+=1;codd[np.array(d)-1]+=1
    if entropy_bins[t]==entropy_bins[i-1]:nent+=1;cent[np.array(d)-1]+=1
    if regimes[t]==prev_reg:nreg+=1;creg[np.array(d)-1]+=1
    if t>=1 and regimes[t-1]==prev_transition[0] and regimes[t]==prev_transition[1]:ntrans+=1;ctrans[np.array(d)-1]+=1
   x[:,26]=(csum+2.5)/(nsum+20.0);x[:,27]=(cspan+2.5)/(nspan+20.0);x[:,28]=(codd+2.5)/(nodd+20.0);x[:,29]=(cent+2.5)/(nent+20.0);x[:,30]=(ctrans+2.5)/(ntrans+20.0);x[:,31]=(creg+2.5)/(nreg+20.0)
   support[53:59]=[nsum,nspan,nodd,nent,ntrans,nreg]
   full=z(np.column_stack((base,x)));rr=ranks(full);feature_tensor[i-50]=full.astype(np.float32);ai=np.array(actual)-1;split=q80.split_name(i-50,n-50)
   for ca,cb in duplicate_rank_pairs(rr):
    key=(NAMES[ca],NAMES[cb]);duplicate_rank_counts[key]=duplicate_rank_counts.get(key,0)+1
   for c,name in enumerate(NAMES):
    r=rr[ai,c];m=metric[name];m[0]+=1;m[1]+=sum(r<=5);m[2]+=sum(r<=10);m[3]+=sum(r<=20);m[4]+=rank_sum_int(r);m[5]+=support[c];m[6]=min(m[6],support[c]);m[7]=max(m[7],support[c])
    sm=split_metric[split][name];sm[0]+=1;sm[1]+=sum(r<=5);sm[2]+=sum(r<=10);sm[3]+=sum(r<=20);sm[4]+=rank_sum_int(r)
    family="baseline" if c<27 else NEW_FAMILIES[c-27]
    ledger.append({"target_date":dates[i],"cutoff_date":dates[i-1],"prior_draws":i,"split":split,"feature":name,"family":family,"feature_support_draws":float(support[c]),"actual_quintet":" ".join(map(str,actual)),"actual_number_ranks":json.dumps(r.tolist()),"number_hits_top5":int(sum(r<=5)),"number_hits_top10":int(sum(r<=10)),"number_hits_top20":int(sum(r<=20)),"mean_actual_rank":float(np.mean(r))})
   rankhist.append(cur_r)
  for h in HL:
   d=math.exp(math.log(.5)/h);ew[h]=ew[h]*d
   for v in actual:ew[h][v-1]+=1-d
  prefix[i+1]=prefix[i]
  pos[i+1]=pos[i]
  for p0,v in enumerate(actual):prefix[i+1,v-1]+=1;pos[i+1,p0,v-1]+=1;occ[v-1].append(i)
  for a in actual:
   for b in actual:
    if a!=b:pair[a-1,b-1]+=1
  regimes.append(int(sum(actual)>=100)+2*int(max(actual)-min(actual)>=25)+4*int(sum(v%2 for v in actual)>=3))
  sum_bins.append(sum_regime_bin(actual));span_bins.append(span_regime_bin(actual));odd_counts.append(sum(v%2 for v in actual));entropy_bins.append(parity_entropy_bin(actual))
 OUT.mkdir(exist_ok=True,parents=True)
 catalog={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","archive":{"path":"data/storico_daily.csv","blob_sha":blob_sha,"draw_count":n,"first_date":dates[0],"last_date":dates[-1]},"feature_count":59,"baseline_features":q80.FEATURE_NAMES,"new_features":NEW,"formula_search_matrix":{"path":"reports/sequence_agent/adaptive_novelty_feature_matrix.npz","shape":[n-50,40,59],"dtype":"float32","normalization":"per-target feature z-score across the 40 candidate numbers; strictly prior-only"},"feature_lineage":"Target i uses draws[:i]; EWMA states update only after scoring; trajectory ranks are cached at their own prefix; regime-conditioned rates use only the preceding 250 draws.","new_feature_family_map":{name:NEW_FAMILIES[k] for k,name in enumerate(NEW)},"rank_duplicate_pairs":[{"feature_a":a,"feature_b":b,"targets_identical":count,"share_of_targets":count/(n-50)} for (a,b),count in sorted(duplicate_rank_counts.items(),key=lambda kv:(-kv[1],kv[0]))],"rank_tie_policy":"scores rounded to 12 decimal places; equal scores rank by number ascending","guardrails":["prior-only","no oracle labels in feature values","no freeze overwritten","finite grammar not exhausted"]}
 (OUT/"adaptive_novelty_feature_catalog.json").write_text(json.dumps(catalog,indent=2)+"\n")
 with (OUT/"adaptive_novelty_rule_anticipation_metrics.csv").open("w",newline="") as f:
  w=csv.writer(f);w.writerow(["feature","family","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_actual_number_rank","mean_support_draws","min_support_draws","max_support_draws"])
  for name,m in metric.items():
   t=m[0];family="baseline" if name in q80.FEATURE_NAMES else NEW_FAMILIES[NAMES.index(name)-27];w.writerow([name,family,t,m[1]/(5*t),m[2]/(5*t),m[3]/(5*t),m[4]/(5*t),m[5]/t,m[6],m[7]])
 split_rows=[];p_records={ep:[] for ep in ("top5","top10","top20","rank_lower")}
 for sp in split_names:
  for name,m in split_metric[sp].items():
   t=m[0];trials=5*t;row={"split":sp,"feature":name,"family":"baseline" if name in q80.FEATURE_NAMES else NEW_FAMILIES[NAMES.index(name)-27],"targets":t,"mean_number_hits_top5":m[1]/trials,"mean_number_hits_top10":m[2]/trials,"mean_number_hits_top20":m[3]/trials,"mean_actual_number_rank":m[4]/trials}
   for ep,k,successes,p0 in (("top5",5,m[1],5/40),("top10",10,m[2],10/40),("top20",20,m[3],20/40)):
    pv=q80.binomial_upper_normal_p(successes,trials,p0);row["p_"+ep]=pv;p_records[ep].append((len(split_rows),pv))
   zrank=(m[4]-0.5-trials*20.5)/math.sqrt(trials*133.25);prank=min(1.0,max(0.0,0.5*math.erfc(-zrank/math.sqrt(2))));row["p_rank_lower"]=prank;p_records["rank_lower"].append((len(split_rows),prank))
   split_rows.append(row)
 for ep,records in p_records.items():
  adjusted=q80.holm_adjust([pv for _,pv in records])
  for (idx,pv),adj in zip(records,adjusted):split_rows[idx]["holm_"+ep]=adj
 split_metrics_path=OUT/"adaptive_novelty_split_metrics.csv"
 with split_metrics_path.open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(split_rows[0]));w.writeheader();w.writerows(split_rows)
 family_split_summary=[];top_candidates={}
 for sp in split_names:
  sr=[r for r in split_rows if r["split"]==sp]
  top_candidates[sp]=[{k:r[k] for k in ("feature","family","targets","mean_number_hits_top5","mean_actual_number_rank","p_top5","holm_top5","p_rank_lower","holm_rank_lower")} for r in sorted(sr,key=lambda r:(r["mean_actual_number_rank"],r["feature"]))[:10]]
  for fam in sorted({r["family"] for r in sr}):
   gr=[r for r in sr if r["family"]==fam]
   family_split_summary.append({"split":sp,"family":fam,"feature_count":len(gr),"mean_number_hits_top5":float(np.mean([r["mean_number_hits_top5"] for r in gr])),"mean_number_hits_top10":float(np.mean([r["mean_number_hits_top10"] for r in gr])),"mean_number_hits_top20":float(np.mean([r["mean_number_hits_top20"] for r in gr])),"mean_actual_number_rank":float(np.mean([r["mean_actual_number_rank"] for r in gr])),"delta_top5_from_chance":float(np.mean([r["mean_number_hits_top5"] for r in gr])-0.125),"delta_rank_from_chance":float(np.mean([r["mean_actual_number_rank"] for r in gr])-20.5),"raw_p_top5_below_0_05":sum(float(r["p_top5"])<0.05 for r in gr),"holm_p_top5_below_0_05":sum(float(r["holm_top5"])<0.05 for r in gr),"holm_rank_lower_below_0_05":sum(float(r["holm_rank_lower"])<0.05 for r in gr)})
 drift={"schema_version":"1.0","task_id":"Q89","status":"EXPLORATORY_DRIFT_DIAGNOSTIC_PENDING_HUMAN_REVIEW","archive_blob_sha":blob_sha,"archive_draw_count":n,"scored_targets":n-50,"split_target_counts":{sp:split_metric[sp][NAMES[0]][0] for sp in split_names},"family_split_summary":family_split_summary,"top_candidates_by_split":top_candidates,"multiple_testing":{"method":"Holm-Bonferroni","adjustment_family":"59 features across 3 chronological splits, adjusted separately for each endpoint","endpoints":["top5","top10","top20","rank_lower"],"p_value_method":"continuity-corrected normal approximation for hit counts; normal lower-tail approximation for mean rank","promotion":"none; exploratory only"},"guardrails":["strict prior-only feature values","chronological discovery/validation/blind OOS splits","raw p-values are exploratory","no feature or formula promotion","immutable target-2026-10-25 freeze untouched"]}
 drift_path=OUT/"adaptive_novelty_regime_drift.json";drift_path.write_text(json.dumps(drift,indent=2)+"\n")
 with (OUT/"adaptive_novelty_target_ledger.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 feature_matrix_path=OUT/"adaptive_novelty_feature_matrix.npz"
 np.savez_compressed(feature_matrix_path,feature_matrix=feature_tensor,target_dates=np.asarray(dates[50:],dtype="U10"),cutoff_dates=np.asarray(dates[49:n-1],dtype="U10"),actual_quintets=np.asarray(draws[50:],dtype=np.uint8),feature_names=np.asarray(NAMES,dtype="U64"),archive_blob_sha=np.asarray(blob_sha,dtype="U64"))
 manifest={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","archive_blob_sha":blob_sha,"archive_draw_count":n,"scored_targets":n-50,"feature_count":59,"metrics_rows":59,"target_ledger_rows":len(ledger),"ledger_sha256":hashlib.sha256((OUT/"adaptive_novelty_target_ledger.csv").read_bytes()).hexdigest(),"split_metrics_rows":len(split_rows),"split_metrics_sha256":hashlib.sha256(split_metrics_path.read_bytes()).hexdigest(),"feature_matrix_path":str(feature_matrix_path.relative_to(ROOT)),"feature_matrix_shape":[n-50,40,59],"feature_matrix_dtype":"float32","feature_matrix_sha256":hashlib.sha256(feature_matrix_path.read_bytes()).hexdigest(),"regime_drift_sha256":hashlib.sha256(drift_path.read_bytes()).hexdigest(),"rank_duplicate_pairs":len(duplicate_rank_counts),"support_summary":{name:{"mean":metric[name][5]/metric[name][0],"min":metric[name][6],"max":metric[name][7]} for name in NAMES},"compute_allocation":{"new_family":40,"existing_strong_under_drift":25,"residual_complementarity":20,"random_control":10,"unstructured":5},"pending":["ex ante nested walk-forward rule anticipation","finite higher-complexity formula grammar (4+ features, interactions and conditional thresholds)","persisted artifact readback","exact-head CI and human review"]}
 (OUT/"adaptive_novelty_formula_metrics_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
 cp={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","checkpoint_date":checkpoint_date,"archive_blob_sha":blob_sha,"draw_count":n,"feature_count":59,"new_features":32,"scored_targets":n-50,"ledger_rows":len(ledger),"pending":manifest["pending"]}
 (OUT/f"adaptive_novelty_checkpoint_{checkpoint_date}.json").write_text(json.dumps(cp,indent=2)+"\n")
if __name__=="__main__":main()
