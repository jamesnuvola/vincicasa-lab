#!/usr/bin/env python3
"""Aggregate Q81 batches, apply global Holm correction, and fail closed on archive mismatch."""
from __future__ import annotations
import argparse,csv,json,math,re,subprocess,sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"scripts"))
import sonar_higher_order_condition_grammar as q81
import sonar_per_number_condition_grammar as q80
SPLITS=q81.SPLITS; MIN_HISTORY=q81.MIN_HISTORY
REPORT=ROOT/"reports"/"sequence_agent"/"higher_order_condition_grammar.json"; LEDGER=ROOT/"reports"/"sequence_agent"/"higher_order_condition_target_ledger.csv"
MP={"discovery":ROOT/"reports"/"sequence_agent"/"higher_order_condition_formula_metrics_discovery.csv","validation":ROOT/"reports"/"sequence_agent"/"higher_order_condition_formula_metrics_validation.csv","blind_oos":ROOT/"reports"/"sequence_agent"/"higher_order_condition_formula_metrics_blind_oos.csv"}
MF=["split","formula_id","family","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"]
def read_csv(path):
 with path.open(newline="",encoding="utf-8-sig") as h:
  r=csv.DictReader(h)
  if not r.fieldnames: raise SystemExit("Q81_AGGREGATE_BLOCKED: missing header "+str(path))
  return list(r)
def write_csv(path,fields,rows):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",newline="",encoding="utf-8") as h:
  w=csv.DictWriter(h,fieldnames=fields); w.writeheader(); w.writerows(rows)
def main():
 p=argparse.ArgumentParser(); p.add_argument("--batch-dir",type=Path,required=True); p.add_argument("--batch-count",type=int,default=128); args=p.parse_args()
 bd=args.batch_dir if args.batch_dir.is_absolute() else ROOT/args.batch_dir
 mf=sorted(bd.glob("batch_*_metrics.csv")); lf=sorted(bd.glob("batch_*_target_best.csv"))
 if len(mf)!=args.batch_count or len(lf)!=args.batch_count: raise SystemExit(f"Q81_AGGREGATE_BLOCKED: expected {args.batch_count} of each batch file; got {len(mf)}/{len(lf)}")
 mi={int(re.match(r"batch_(\d+)_metrics\.csv$",x.name).group(1)):x for x in mf}; li={int(re.match(r"batch_(\d+)_target_best\.csv$",x.name).group(1)):x for x in lf}
 if set(mi)!=set(range(args.batch_count)) or set(li)!=set(range(args.batch_count)): raise SystemExit("Q81_AGGREGATE_BLOCKED: batch indices incomplete")
 dates,draws=q80.load_archive(); n=len(draws); scored=max(0,n-MIN_HISTORY); targets=dates[MIN_HISTORY:]
 splits=Counter(q80.split_name(i-MIN_HISTORY,scored) for i in range(MIN_HISTORY,n))
 formulas=list(q81.iter_formulas())
 if len(formulas)!=q81.FORMULA_COUNT or q81.FORMULA_COUNT!=q81.FORMULA_COUNT_CHECK: raise SystemExit("Q81_AGGREGATE_BLOCKED: formula count mismatch")
 meta={f[0]:f for f in formulas}; expected=set(meta); raw={}; best_by_date={}
 archive={dates[i]:(" ".join(map(str,draws[i])),i) for i in range(n)}; chunk=math.ceil(q81.FORMULA_COUNT/args.batch_count)
 for b in range(args.batch_count):
  bf=formulas[b*chunk:min(q81.FORMULA_COUNT,(b+1)*chunk)]; bids={f[0] for f in bf}; rows=read_csv(mi[b])
  if len(rows)!=len(bf)*len(SPLITS): raise SystemExit(f"Q81_AGGREGATE_BLOCKED: batch {b} metric row count mismatch")
  seen=set()
  for r in rows:
   fid,s=r.get("formula_id",""),r.get("split",""); key=(s,fid)
   if fid not in bids or s not in SPLITS or key in seen: raise SystemExit(f"Q81_AGGREGATE_BLOCKED: invalid formula/split row {key}")
   seen.add(key); f=meta[fid]
   if r.get("family")!=f[1] or int(r.get("feature_count",-1))!=len(set(f[2])) or r.get("features")!=f[5]: raise SystemExit("Q81_AGGREGATE_BLOCKED: formula metadata mismatch "+fid)
   if int(r.get("targets",-1))!=splits[s]: raise SystemExit("Q81_AGGREGATE_BLOCKED: split target count mismatch "+fid)
   for col in ("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum"):
    if int(r[col])<0: raise SystemExit("Q81_AGGREGATE_BLOCKED: negative accumulator "+fid+"/"+col)
   raw[key]=r
  if len(seen)!=len(bf)*len(SPLITS) or {fid for s,fid in seen}!=bids: raise SystemExit(f"Q81_AGGREGATE_BLOCKED: batch {b} formula/split coverage mismatch")
  tr=read_csv(li[b])
  if len(tr)!=scored or [r.get("target_date","") for r in tr]!=targets: raise SystemExit(f"Q81_AGGREGATE_BLOCKED: batch {b} target coverage mismatch")
  for r in tr:
   d=r["target_date"]; actual,ti=archive[d]
   if r.get("actual_quintet")!=actual or r.get("cutoff_date")!=dates[ti-1] or int(r.get("prior_draws",-1))!=ti: raise SystemExit("Q81_AGGREGATE_BLOCKED: target/cutoff mismatch "+d)
   fid=r.get("best_formula_id","")
   if fid not in bids or r.get("best_formula_family")!=meta[fid][1] or r.get("best_formula_features")!=meta[fid][5]: raise SystemExit("Q81_AGGREGATE_BLOCKED: target-best formula mismatch "+d)
   try:
    ranks=json.loads(r["best_actual_number_ranks"])
    if len(ranks)!=5 or any(not isinstance(x,int) or x<1 or x>40 for x in ranks): raise ValueError("bad ranks")
    h5=sum(x<=5 for x in ranks); h10=sum(x<=10 for x in ranks); h20=sum(x<=20 for x in ranks); rs=sum(ranks)
    if (h5,h10,h20,rs)!=(int(r["best_number_hits_top5"]),int(r["best_number_hits_top10"]),int(r["best_number_hits_top20"]),int(r["best_rank_sum"])): raise ValueError("rank aggregate mismatch")
   except Exception as exc: raise SystemExit("Q81_AGGREGATE_BLOCKED: invalid target-best ranks "+d+": "+str(exc))
   key=(rs,-h20,-h5,fid); old=best_by_date.get(d)
   if old is None or key<old["key"]: best_by_date[d]={"key":key,"row":r,"ranks":ranks}
 if len(raw)!=q81.FORMULA_COUNT*len(SPLITS): raise SystemExit("Q81_AGGREGATE_BLOCKED: global formula/split count mismatch")
 for s in SPLITS:
  if {fid for ss,fid in raw if ss==s}!=expected: raise SystemExit("Q81_AGGREGATE_BLOCKED: formula universe mismatch "+s)
 if set(best_by_date)!=set(targets): raise SystemExit("Q81_AGGREGATE_BLOCKED: global target ledger coverage mismatch")
 metrics=[]; ps=[]; refs=[]
 for s in SPLITS:
  for f in formulas:
   r=raw[(s,f[0])]; t=int(r["targets"]); h5=int(r["number_hits_top5"]); h10=int(r["number_hits_top10"]); h20=int(r["number_hits_top20"]); rs=int(r["rank_sum"])
   row={"split":s,"formula_id":f[0],"family":f[1],"feature_count":len(set(f[2])),"features":f[5],"targets":t,
    "mean_number_hits_top5":h5/(5*t),"mean_number_hits_top10":h10/(5*t),"mean_number_hits_top20":h20/(5*t),
    "all5_top5_rate":int(r["all5_top5"])/t,"all5_top10_rate":int(r["all5_top10"])/t,"all5_top20_rate":int(r["all5_top20"])/t,"mean_rank_of_actual_numbers":rs/(5*t)}
   idx=len(metrics)
   for endpoint,h,k in (("top5",h5,5),("top10",h10,10),("top20",h20,20)):
    pv=q80.binomial_upper_normal_p(h,5*t,k/40); row["p_"+endpoint+"_normal_approx"]=pv; ps.append(pv); refs.append((idx,endpoint))
   row["holm_p_max_endpoint_family"]=1.0; metrics.append(row)
 adj=q80.holm_adjust(ps); maxadj=[0.0]*len(metrics); sig=0; minp=1.0
 for (idx,_),v in zip(refs,adj): maxadj[idx]=max(maxadj[idx],v); minp=min(minp,v); sig+=int(v<0.05)
 for i,r in enumerate(metrics): r["holm_p_max_endpoint_family"]=maxadj[i]
 for s in SPLITS: write_csv(MP[s],MF,[r for r in metrics if r["split"]==s])
 ledger=[]
 for d in targets:
  best=best_by_date[d]; r=best["row"]; ranks=best["ranks"]; actual,ti=archive[d]
  ledger.append({"target_date":d,"cutoff_date":dates[ti-1],"prior_draws":ti,"actual_quintet":actual,"status":"RETROSPECTIVE_DIAGNOSTIC_NOT_FORECAST",
   "formula_count_tested":q81.FORMULA_COUNT,"best_formula_id":r["best_formula_id"],"best_formula_family":r["best_formula_family"],"best_formula_features":r["best_formula_features"],
   "best_actual_number_ranks":json.dumps(ranks,separators=(",",":")),"n1_rank":ranks[0],"n2_rank":ranks[1],"n3_rank":ranks[2],"n4_rank":ranks[3],"n5_rank":ranks[4],
   "best_number_hits_top5":sum(x<=5 for x in ranks),"best_number_hits_top10":sum(x<=10 for x in ranks),"best_number_hits_top20":sum(x<=20 for x in ranks),"best_rank_sum":sum(ranks)})
 write_csv(LEDGER,list(ledger[0].keys()),ledger)
 summaries={}
 for s in SPLITS:
  rows=[r for r in metrics if r["split"]==s]
  def pick(field,maximum=True): return sorted(rows,key=lambda r:(-float(r[field]) if maximum else float(r[field]),float(r["mean_rank_of_actual_numbers"]),r["formula_id"]))[0]
  def compact(r): return {k:r[k] for k in ("formula_id","family","features","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_rank_of_actual_numbers","holm_p_max_endpoint_family")}
  summaries[s]={"targets":splits[s],"formula_rows":len(rows),"best_top5_rate_formula":compact(pick("mean_number_hits_top5")),
   "best_top10_rate_formula":compact(pick("mean_number_hits_top10")),"best_top20_rate_formula":compact(pick("mean_number_hits_top20")),
   "best_mean_rank_formula":compact(pick("mean_rank_of_actual_numbers",False)),
   "formula_split_rows_with_all_endpoint_holm_max_below_0_05":sum(float(r["holm_p_max_endpoint_family"])<0.05 for r in rows)}
 report={"schema_version":"1.0","task_id":"Q81","status":"VALIDATED_FINITE_GRAMMAR_PENDING_HUMAN_REVIEW","review_status":"PENDING_HUMAN_REVIEW_INTEGRATION",
  "source_archive":"data/storico_daily.csv","target_count":n,"first_date":dates[0],"last_date":dates[-1],"minimum_prior_history":MIN_HISTORY,"scored_targets":scored,
  "feature_count":len(q81.FEATURE_NAMES),"features":q81.FEATURE_NAMES,"formula_count":q81.FORMULA_COUNT,"formula_count_check":q81.FORMULA_COUNT_CHECK,
  "formula_grammar":"all 4/5-feature equal-weight combinations plus registered square, pair-product, conditional-threshold, gated and quadratic-additive families",
  "family_counts":q81.FAMILY_COUNTS,"batch_count":args.batch_count,"metrics_rows":len(metrics),"metrics_rows_by_split":{s:q81.FORMULA_COUNT for s in SPLITS},
  "target_ledger_rows":len(ledger),"split_counts":dict(splits),
  "baseline":{"uniform_random_mean_number_hits_top5":0.125,"uniform_random_mean_number_hits_top10":0.25,"uniform_random_mean_number_hits_top20":0.5,
   "uniform_random_mean_rank_of_actual_numbers":20.5,"uniform_random_all5_top5_rate":1/math.comb(40,5),"uniform_random_all5_top10_rate":math.comb(10,5)/math.comb(40,5),"uniform_random_all5_top20_rate":math.comb(20,5)/math.comb(40,5)},
  "chronological_split_summaries":summaries,"multiple_testing":{"method":"Holm-Bonferroni","test_count":len(ps),
   "p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test",
   "holm_adjusted_endpoint_tests_below_0_05":sig,"minimum_holm_adjusted_endpoint_p":minp},
  "guardrails":["all target features use only draws strictly before the target","all 40 numbers are ranked; actual numbers are evaluated only after scoring",
   "the registered grammar is finite and does not exhaust every mathematical formula","best-per-target and best-per-split results are retrospective diagnostics, not prospective forecasts",
   "Holm correction spans every formula x chronological split x endpoint test","the immutable target-2026-10-25 freeze is not read for writing or overwritten","no formula is promoted automatically; human review/integration is required"],
  "metrics_files":{s:str(MP[s].relative_to(ROOT)) for s in SPLITS},"outputs":{"target_ledger":str(LEDGER.relative_to(ROOT)),"report":str(REPORT.relative_to(ROOT))},
  "generated_at_utc":datetime.now(timezone.utc).isoformat()}
 REPORT.parent.mkdir(parents=True,exist_ok=True); REPORT.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 subprocess.run([sys.executable,str(ROOT/"scripts"/"sonar_research_queue.py")],cwd=ROOT,check=True)
 subprocess.run([sys.executable,str(ROOT/"scripts"/"validate_sonar_higher_order_outputs.py")],cwd=ROOT,check=True)
 print("SONAR_Q81_AGGREGATE_SUMMARY_BEGIN")
 print(json.dumps({"status":report["status"],"formula_count":q81.FORMULA_COUNT,"family_counts":q81.FAMILY_COUNTS,"target_count":n,"scored_targets":scored,
  "metrics_rows":len(metrics),"target_ledger_rows":len(ledger),"split_counts":dict(splits),"holm_test_count":len(ps),
  "holm_adjusted_endpoint_tests_below_0_05":sig,"minimum_holm_adjusted_endpoint_p":minp,"queue_status":"VALIDATED_PENDING_HUMAN_REVIEW"},separators=(",",":")))
 print("SONAR_Q81_AGGREGATE_SUMMARY_END")
if __name__=="__main__": main()
