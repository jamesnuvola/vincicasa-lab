#!/usr/bin/env python3
"""Q89 walk-forward feature engine. Each target uses only its strict historical prefix."""
import csv,json,math,hashlib
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/"reports/sequence_agent"; ARCH=ROOT/"data/storico_daily.csv"
HL=(3,7,14,30,60)
NEW=["ewma_hit_hl_3","ewma_hit_hl_7","ewma_hit_hl_14","ewma_hit_hl_30","ewma_hit_hl_60","ewma_acceleration_3_14","ewma_acceleration_7_30","last_gap_vs_median","last_gap_robust_z","gap_cv","gap_slope_recent","gap_hazard_empirical","gap_hazard_residual","pair_lift_recent_last_draw","pair_pmi_recent_last_draw","cooccurrence_strength_recent","cooccurrence_surprise_recent","neighbor_balance_pm1_recent","neighbor_balance_pm2_recent","rank_velocity_5_20","rank_acceleration_5_20_50","rank_volatility_20","feature_disagreement_27","rank_consensus_27","novelty_residual_20","novelty_residual_50","regime_sum_affinity","regime_span_affinity","regime_parity_affinity","regime_entropy_affinity","transition_profile_affinity","conditional_frequency_prev_draw_regime"]
NAMES=q80.FEATURE_NAMES+NEW
def z(a):
 a=np.asarray(a,float); sd=a.std(axis=0); sd[sd<1e-12]=1; return (a-a.mean(axis=0))/sd
def ranks(a):
 order=np.argsort(-a,axis=0,kind="stable"); r=np.empty(order.shape,np.int16);r[order,np.arange(a.shape[1])]=np.arange(1,a.shape[0]+1)[:,None];return r
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
 dates,draws=load(); n=len(draws); assert n==3394 and dates[-1]=="2026-10-31"
 prefix=np.zeros((n+1,40),np.int32);pos=np.zeros((n+1,5,40),np.int32);pair=np.zeros((40,40),np.int32);occ=[[] for _ in range(40)]
 ew={h:np.zeros(40) for h in HL};rankhist=[];regimes=[]
 metric={name:[0,0,0,0,0] for name in NAMES}; ledger=[]
 for i,actual in enumerate(draws):
  if i>=50:
   base=q80.feature_matrix(i,draws,prefix,pos,pair,occ,np.zeros(40),np.zeros(40),np.zeros(40)); cur_r=ranks(z(base))
   x=np.zeros((40,32)); 
   for k,h in enumerate(HL):x[:,k]=ew[h]
   x[:,5]=ew[3]-ew[14];x[:,6]=ew[7]-ew[30]
   for v in range(40):
    g=np.diff(occ[v]);age=i-occ[v][-1] if occ[v] else i+1;med=float(np.median(g)) if len(g) else 0;mad=float(np.median(abs(g-med))) if len(g) else 0
    x[v,7]=(age-med)/max(med,1);x[v,8]=(age-med)/max(1,1.4826*mad);x[v,9]=float(np.std(g)/max(np.mean(g),1)) if len(g)>1 else 0
    x[v,10]=float(np.polyfit(np.arange(len(g[-8:])),g[-8:],1)[0]) if len(g)>=3 else 0
    x[v,11]=(sum(g==age)+2/(med+1))/(max(1,sum(g>=age))+2) if len(g) else 1/(age+1);x[v,12]=x[v,11]-1/(med+1)
   last=np.array(draws[i-1])-1
   recent=np.zeros((40,40))
   for t in range(max(0,i-30),i):
    for a in draws[t]:
     for b in draws[t]:
      if a!=b:recent[a-1,b-1]+=1
   freq=prefix[i].astype(float);p=(freq+.5)/(i+20)
   for v in range(40):
    lift=[];pm=[]
    for u in last:
     pxy=(recent[v,u]+.5)/(max(1,i-min(30,i))*20+20);py=(recent[:,u].sum()+20)/(max(1,i-min(30,i))*20+40)
     lift.append(pxy/max(p[v]*py,1e-9));pm.append(math.log(max(pxy,1e-9)/max(p[v]*py,1e-9)))
    x[v,13]=np.mean(lift);x[v,14]=np.mean(pm);x[v,15]=recent[v,last].mean();x[v,16]=math.log((recent[v,last].mean()+1)/(pair[v,last].mean()+1))
   for radius,col in [(1,17),(2,18)]:
    for v in range(40):x[v,col]=sum(freq[u] for u in range(max(0,v-radius),min(40,v+radius+1)) if u!=v)
   if rankhist:
    h=np.asarray(rankhist,float); x[:,19]=h[-5:].mean(axis=(0,2))-h[-20:].mean(axis=(0,2));x[:,20]=h[-20:].mean(axis=(0,2))-h[-50:].mean(axis=(0,2));x[:,21]=h[-20:].std(axis=(0,2));x[:,22]=cur_r.std(axis=1);x[:,23]=np.median(cur_r,axis=1)
   for w,col in [(20,24),(50,25)]:
    hits=prefix[i]-prefix[max(0,i-w)];rate=(freq+.5)/(i+20);exp=rate*min(w,i);x[:,col]=(hits-exp)/np.sqrt(np.maximum(exp*(1-rate),.25))
   prev=draws[i-1];s=sum(prev);span=max(prev)-min(prev);odd=sum(v%2 for v in prev);ent=-sum((c/5)*math.log(c/5) for c in [sum(v%2==0 for v in prev),sum(v%2==1 for v in prev)] if c)
   x[:,26]=np.exp(-abs(freq/max(i,1)-s/200));x[:,27]=np.exp(-abs(np.arange(40)/40-span/40));x[:,28]=np.where((np.arange(1,41)%2)==odd%2,1,-1);x[:,29]=ent
   x[:,30]=[(sum(v in d for d in draws[max(0,i-100):i])+0.5)/(max(1,i)*.05+20) for v in range(1,41)]
   x[:,31]=[(sum(v in draws[t] for t in range(max(0,i-100),i) if regimes[t]==regimes[i-1])+.5)/(max(1,regimes[max(0,i-100):i].count(regimes[i-1]))*5+20) for v in range(1,41)]
   full=z(np.column_stack((base,x)));rr=ranks(full);ai=np.array(actual)-1
   for c,name in enumerate(NAMES):
    r=rr[ai,c];m=metric[name];m[0]+=1;m[1]+=sum(r<=5);m[2]+=sum(r<=10);m[3]+=sum(r<=20);m[4]+=sum(r)
    ledger.append({"target_date":dates[i],"cutoff_date":dates[i-1],"prior_draws":i,"feature":name,"family":"baseline" if c<27 else NEW[c-27],"actual_quintet":" ".join(map(str,actual)),"actual_number_ranks":json.dumps(r.tolist()),"number_hits_top5":int(sum(r<=5)),"number_hits_top10":int(sum(r<=10)),"number_hits_top20":int(sum(r<=20)),"mean_actual_rank":float(np.mean(r))})
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
 OUT.mkdir(exist_ok=True,parents=True)
 catalog={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","archive":{"path":"data/storico_daily.csv","blob_sha":"8082ec0b376e7595733917e89544a08b209ca9b4","draw_count":n,"first_date":dates[0],"last_date":dates[-1]},"feature_count":59,"baseline_features":q80.FEATURE_NAMES,"new_features":NEW,"feature_lineage":"Target i uses draws[:i]; trajectory ranks stored at their own historical prefix; EWMA states update only after scoring target.","guardrails":["prior-only","no oracle labels in feature values","no freeze overwritten","finite grammar not exhausted"]}
 (OUT/"adaptive_novelty_feature_catalog.json").write_text(json.dumps(catalog,indent=2)+"\n")
 with (OUT/"adaptive_novelty_rule_anticipation_metrics.csv").open("w",newline="") as f:
  w=csv.writer(f);w.writerow(["feature","family","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_actual_number_rank"])
  for name,m in metric.items():
   t=m[0];w.writerow([name,"baseline" if name in q80.FEATURE_NAMES else NEW[NAMES.index(name)-27],t,m[1]/(5*t),m[2]/(5*t),m[3]/(5*t),m[4]/(5*t)])
 with (OUT/"adaptive_novelty_target_ledger.csv").open("w",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
 manifest={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","archive_blob_sha":"8082ec0b376e7595733917e89544a08b209ca9b4","archive_draw_count":n,"scored_targets":n-50,"feature_count":59,"metrics_rows":59,"target_ledger_rows":len(ledger),"ledger_sha256":hashlib.sha256((OUT/"adaptive_novelty_target_ledger.csv").read_bytes()).hexdigest(),"compute_allocation":{"new_family":40,"existing_strong_under_drift":25,"residual_complementarity":20,"random_control":10,"unstructured":5},"pending":["ex ante nested walk-forward rule anticipation","finite grammar execution","regime drift diagnostic","acceptance validators and persistence readback","exact-head CI and human review"]}
 (OUT/"adaptive_novelty_formula_metrics_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
 cp={"schema_version":"1.0","task_id":"Q89","status":"FEATURE_ENGINE_EXECUTED_PENDING_ACCEPTANCE","checkpoint_date":"2026-11-02","archive_blob_sha":"8082ec0b376e7595733917e89544a08b209ca9b4","draw_count":n,"feature_count":59,"new_features":32,"scored_targets":n-50,"ledger_rows":len(ledger),"pending":manifest["pending"]}
 (OUT/"adaptive_novelty_checkpoint_2026-11-02.json").write_text(json.dumps(cp,indent=2)+"\n")
if __name__=="__main__":main()
