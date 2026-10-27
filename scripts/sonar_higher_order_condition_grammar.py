#!/usr/bin/env python3
"""Batched walk-forward search over a finite higher-order per-number formula grammar."""
from __future__ import annotations
import argparse,csv,itertools,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import sonar_per_number_condition_grammar as q80
MIN_HISTORY=q80.MIN_HISTORY; FEATURE_NAMES=q80.FEATURE_NAMES
SPLITS=("discovery","validation","blind_oos")
THRESHOLDS=(("GE0p5","ge",0.5),("GE1","ge",1.0),("LEm0p5","le",-0.5),("LEm1","le",-1.0))
WEIGHTS=(("m1",-1.0),("m0p5",-0.5),("p0p5",0.5),("p1",1.0))
FAMILY_COUNTS={"linear4":math.comb(27,4),"linear5":math.comb(27,5),"square":27,"product":math.comb(27,2),
 "conditional_add":27*26*len(THRESHOLDS)*len(WEIGHTS),"gated_multiply":27*26*len(THRESHOLDS),
 "indicator":27*len(THRESHOLDS),"quadratic_add":27*26*len(WEIGHTS)}
FORMULA_COUNT=sum(FAMILY_COUNTS.values()); FORMULA_COUNT_CHECK=115614
def _cols_id(prefix,cols): return prefix+"_"+"_".join(f"{c:02d}" for c in cols)
def _threshold_text(name,op,value): return f"{name}{'>=' if op=='ge' else '<='}{value:g}"
def iter_formulas():
 count=0
 def emit(fid,family,cols,condition,weight,display):
  nonlocal count; count+=1; return (fid,family,tuple(cols),condition,weight,display)
 for cols in itertools.combinations(range(27),4):
  yield emit(_cols_id("L4",cols),"linear4",cols,None,None,"+".join(FEATURE_NAMES[c] for c in cols))
 for cols in itertools.combinations(range(27),5):
  yield emit(_cols_id("L5",cols),"linear5",cols,None,None,"+".join(FEATURE_NAMES[c] for c in cols))
 for i in range(27): yield emit(f"SQ_{i:02d}","square",(i,),None,None,FEATURE_NAMES[i]+"^2")
 for i,j in itertools.combinations(range(27),2):
  yield emit(f"PR_{i:02d}_{j:02d}","product",(i,j),None,None,FEATURE_NAMES[i]+"*"+FEATURE_NAMES[j])
 for i in range(27):
  for j in range(27):
   if i==j: continue
   for tn,op,t in THRESHOLDS:
    for wn,w in WEIGHTS:
     yield emit(f"CA_{i:02d}_{j:02d}_{tn}_{wn}","conditional_add",(i,j),(j,op,t),w,
       FEATURE_NAMES[i]+f"+({w:g})*I("+_threshold_text(FEATURE_NAMES[j],op,t)+")")
 for i in range(27):
  for j in range(27):
   if i==j: continue
   for tn,op,t in THRESHOLDS:
    yield emit(f"GM_{i:02d}_{j:02d}_{tn}","gated_multiply",(i,j),(j,op,t),None,
      FEATURE_NAMES[i]+"*I("+_threshold_text(FEATURE_NAMES[j],op,t)+")")
 for i in range(27):
  for tn,op,t in THRESHOLDS:
   yield emit(f"IN_{i:02d}_{tn}","indicator",(i,),(i,op,t),None,"I("+_threshold_text(FEATURE_NAMES[i],op,t)+")")
 for i in range(27):
  for j in range(27):
   if i==j: continue
   for wn,w in WEIGHTS:
    yield emit(f"QA_{i:02d}_{j:02d}_{wn}","quadratic_add",(i,j),None,w,FEATURE_NAMES[i]+f"+({w:g})*z("+FEATURE_NAMES[j]+")^2")
 if count!=FORMULA_COUNT: raise RuntimeError(f"Q81 formula enumeration mismatch: {count} != {FORMULA_COUNT}")
def formulas_for_batch(batch_index,batch_count):
 if batch_count<1 or not 0<=batch_index<batch_count: raise ValueError("invalid batch index/count")
 chunk=math.ceil(FORMULA_COUNT/batch_count); start=batch_index*chunk; end=min(FORMULA_COUNT,start+chunk)
 if start>=FORMULA_COUNT: raise ValueError("batch is empty; reduce batch_count")
 return list(itertools.islice(iter_formulas(),start,end))
def threshold_mask(z,feature_index,op,threshold):
 values=z[:,feature_index]
 if op=="ge": return values>=threshold
 if op=="le": return values<=threshold
 raise ValueError("unknown threshold operator: "+str(op))
def score_formula(formula,z,z_squared):
 _,family,cols,condition,weight,_=formula
 if family in ("linear4","linear5"): return z[:,cols].mean(axis=1)
 if family=="square": return z[:,cols[0]]**2
 if family=="product": return z[:,cols[0]]*z[:,cols[1]]
 if family=="conditional_add":
  j,op,t=condition; return z[:,cols[0]]+weight*threshold_mask(z,j,op,t)
 if family=="gated_multiply":
  j,op,t=condition; return z[:,cols[0]]*threshold_mask(z,j,op,t)
 if family=="indicator":
  i,op,t=condition; return threshold_mask(z,i,op,t).astype(np.float64)
 if family=="quadratic_add": return z[:,cols[0]]+weight*z_squared[:,cols[1]]
 raise ValueError("unknown formula family: "+str(family))
def _build_prefixes(draws):
 n=len(draws); prefix=np.zeros((n+1,40),dtype=np.int32); position_prefix=np.zeros((n+1,5,40),dtype=np.int32)
 for i,draw in enumerate(draws):
  prefix[i+1]=prefix[i]; position_prefix[i+1]=position_prefix[i]
  for pos,value in enumerate(draw):
   prefix[i+1,value-1]+=1; position_prefix[i+1,pos,value-1]+=1
 return prefix,position_prefix
def main():
 p=argparse.ArgumentParser(); p.add_argument("--batch-index",type=int,required=True); p.add_argument("--batch-count",type=int,default=128); args=p.parse_args()
 formulas=formulas_for_batch(args.batch_index,args.batch_count); dates,draws=q80.load_archive(); n=len(draws); scored=max(0,n-MIN_HISTORY)
 prefix,pos_prefix=_build_prefixes(draws); pairs=np.zeros((40,40),dtype=np.int32); occurrences=[[] for _ in range(40)]; zeros=np.zeros(40)
 accum={s:[[0]*8 for _ in formulas] for s in SPLITS}; target_rows=[]; split_counts=Counter()
 for i,(date,actual) in enumerate(zip(dates,draws)):
  if i>=MIN_HISTORY:
   raw=q80.feature_matrix(i,draws,prefix,pos_prefix,pairs,occurrences,zeros,zeros,zeros); z=q80.zscore_columns(raw); zsq=q80.zscore_columns(z**2)
   actual_idx=np.asarray(actual,dtype=int)-1; split=q80.split_name(i-MIN_HISTORY,scored); split_counts[split]+=1
   best=None; num_idx=np.arange(40)
   for fi,f in enumerate(formulas):
    scores=score_formula(f,z,zsq)
    if not np.isfinite(scores).all(): raise SystemExit("Q81_BLOCKED: non-finite score at "+date)
    order=np.lexsort((num_idx,-scores)); ranks=np.empty(40,dtype=np.int16); ranks[order]=np.arange(1,41,dtype=np.int16)
    ar=ranks[actual_idx]; h5=int(np.sum(ar<=5)); h10=int(np.sum(ar<=10)); h20=int(np.sum(ar<=20)); rs=int(np.sum(ar))
    a=accum[split][fi]; a[0]+=1; a[1]+=h5; a[2]+=h10; a[3]+=h20; a[4]+=int(h5==5); a[5]+=int(h10==5); a[6]+=int(h20==5); a[7]+=rs
    key=(rs,-h20,-h5,f[0])
    if best is None or key<best["key"]: best={"key":key,"f":f,"r":ar.astype(int).tolist(),"h5":h5,"h10":h10,"h20":h20,"rs":rs}
   if best is None: raise SystemExit("Q81_BLOCKED: no formula scored at "+date)
   f=best["f"]; target_rows.append({"target_date":date,"cutoff_date":dates[i-1],"prior_draws":i,"actual_quintet":" ".join(map(str,actual)),
    "best_formula_id":f[0],"best_formula_family":f[1],"best_formula_features":f[5],"best_actual_number_ranks":json.dumps(best["r"],separators=(",",":")),
    "best_number_hits_top5":best["h5"],"best_number_hits_top10":best["h10"],"best_number_hits_top20":best["h20"],"best_rank_sum":best["rs"],"batch_index":args.batch_index})
  # Update only after target scoring.
  for value in draws[i]: occurrences[value-1].append(i)
  for a,b in itertools.combinations(draws[i],2): pairs[a-1,b-1]+=1; pairs[b-1,a-1]+=1
 out=ROOT/"reports"/"sequence_agent"/"q81_batches"; out.mkdir(parents=True,exist_ok=True)
 mp=out/f"batch_{args.batch_index:03d}_metrics.csv"; lp=out/f"batch_{args.batch_index:03d}_target_best.csv"
 fields=["split","formula_id","family","feature_count","features","targets","number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum"]
 with mp.open("w",newline="",encoding="utf-8") as h:
  w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
  for fi,f in enumerate(formulas):
   for split in SPLITS:
    a=accum[split][fi]; w.writerow({"split":split,"formula_id":f[0],"family":f[1],"feature_count":len(set(f[2])),"features":f[5],"targets":a[0],"number_hits_top5":a[1],"number_hits_top10":a[2],"number_hits_top20":a[3],"all5_top5":a[4],"all5_top10":a[5],"all5_top20":a[6],"rank_sum":a[7]})
 lfields=["target_date","cutoff_date","prior_draws","actual_quintet","best_formula_id","best_formula_family","best_formula_features","best_actual_number_ranks","best_number_hits_top5","best_number_hits_top10","best_number_hits_top20","best_rank_sum","batch_index"]
 with lp.open("w",newline="",encoding="utf-8") as h:
  w=csv.DictWriter(h,fieldnames=lfields); w.writeheader(); w.writerows(target_rows)
 print("SONAR_Q81_BATCH_SUMMARY "+json.dumps({"batch_index":args.batch_index,"batch_count":args.batch_count,"formula_count_total":FORMULA_COUNT,"batch_formula_count":len(formulas),"scored_targets":len(target_rows),"split_counts":dict(split_counts)},separators=(",",":")))
if __name__=="__main__": main()
