#!/usr/bin/env python3
"""Shard evaluator for the Q87 seven-feature equal-weight formula grammar."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, os
from collections import Counter
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/sequence_agent"
METRICS=OUT/"q87_shards/shard_metrics.csv"
TARGET_LEDGER=OUT/"q87_shards/shard_target_ledger.csv"
REPORT=OUT/"q87_shards/shard_report.json"
MIN_HISTORY=q80.MIN_HISTORY
FEATURE_NAMES=q80.FEATURE_NAMES
FEATURE_COUNT=len(FEATURE_NAMES)
FORMULA_SIZE=7
FORMULA_BATCH_SIZE=1024
SPLITS=("discovery","validation","blind_oos")

def make_formulas():
    formulas=list(itertools.combinations(range(FEATURE_COUNT),FORMULA_SIZE))
    if len(formulas)!=math.comb(FEATURE_COUNT,FORMULA_SIZE) or len(set(formulas))!=len(formulas):
        raise RuntimeError("Q87 formula enumeration mismatch")
    return formulas

FORMULAS_ALL=make_formulas()
TOTAL_FORMULA_COUNT=len(FORMULAS_ALL)
SHARD_COUNT=6
SHARD_INDEX=int(os.environ.get("SONAR_Q87_SHARD_INDEX","0"))
if SHARD_INDEX < 0 or SHARD_INDEX >= SHARD_COUNT:
    raise SystemExit("Q87_BLOCKED: invalid shard index")
SHARD_SIZE=TOTAL_FORMULA_COUNT//SHARD_COUNT
if TOTAL_FORMULA_COUNT % SHARD_COUNT:
    raise SystemExit("Q87_BLOCKED: formula universe cannot be divided evenly")
SHARD_START=SHARD_INDEX*SHARD_SIZE
SHARD_END=SHARD_START+SHARD_SIZE
FORMULAS=FORMULAS_ALL[SHARD_START:SHARD_END]
FORMULA_IDS=["P7_"+"_".join(f"{i:02d}" for i in cols) for cols in FORMULAS]

def batch_ranges(total,batch_size=FORMULA_BATCH_SIZE):
    if batch_size<=0: raise ValueError("batch size must be positive")
    return [(start,min(start+batch_size,total)) for start in range(0,total,batch_size)]

def rank_matrix(scores):
    """Rank every column; stable sort gives lower number priority on exact ties."""
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    return ranks

def build_feature_stack(draws):
    """Build standardized 40x27 feature matrices using only the prefix before each target."""
    n=len(draws)
    if n<=MIN_HISTORY: raise ValueError("Q87 needs at least 51 draws to score a target")
    prefix=np.zeros((n+1,40),dtype=np.int32)
    position_prefix=np.zeros((n+1,5,40),dtype=np.int32)
    for i,draw in enumerate(draws):
        prefix[i+1]=prefix[i]; position_prefix[i+1]=position_prefix[i]
        for position,value in enumerate(draw):
            prefix[i+1,value-1]+=1
            position_prefix[i+1,position,value-1]+=1
    pair_counts=np.zeros((40,40),dtype=np.int32)
    occurrence_lists=[[] for _ in range(40)]
    gap_sum=np.zeros(40,dtype=np.float64)
    gap_sq_sum=np.zeros(40,dtype=np.float64)
    gap_n=np.zeros(40,dtype=np.float64)
    stack=np.empty((n-MIN_HISTORY,40,FEATURE_COUNT),dtype=np.float64)
    for i,draw in enumerate(draws):
        if i>=MIN_HISTORY:
            raw=q80.feature_matrix(i,draws,prefix,position_prefix,pair_counts,occurrence_lists,gap_sum,gap_sq_sum,gap_n)
            stack[i-MIN_HISTORY]=q80.zscore_columns(raw)
        # Update state only after this target's features have been computed.
        for value in draw:
            number=value-1; occurrence_lists[number].append(i)
            if len(occurrence_lists[number])>=2:
                gap=i-occurrence_lists[number][-2]
                gap_sum[number]+=gap; gap_sq_sum[number]+=gap*gap; gap_n[number]+=1
        for a,b in itertools.combinations(draw,2):
            pair_counts[a-1,b-1]+=1; pair_counts[b-1,a-1]+=1
    return stack

def build_formula_weight_matrix(formulas):
    weights=np.zeros((FEATURE_COUNT,len(formulas)),dtype=np.float64)
    for formula_index,columns in enumerate(formulas):
        weights[list(columns),formula_index]=1.0/FORMULA_SIZE
    return weights

def compact_metric(row):
    keys=("formula_id","features","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
          "mean_rank_of_actual_numbers","holm_p_max_endpoint_family")
    return {key:(float(row[key]) if key not in ("formula_id","features") else row[key]) for key in keys}

def main():
    dates,draws=q80.load_archive()
    n=len(draws); scored_targets=n-MIN_HISTORY
    if scored_targets<=0: raise SystemExit("Q87_BLOCKED: no targets have sufficient prior history")
    formula_count=len(FORMULAS)
    if formula_count!=SHARD_SIZE or TOTAL_FORMULA_COUNT!=math.comb(FEATURE_COUNT,FORMULA_SIZE): raise SystemExit("Q87_BLOCKED: shard formula count mismatch")
    standardized_stack=q81.build_feature_stack(draws)
    if standardized_stack.shape!=(scored_targets,40,FEATURE_COUNT): raise SystemExit("Q87_BLOCKED: feature stack dimensions mismatch")
    weights=build_formula_weight_matrix(FORMULAS)
    fields=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")
    accum={s:{f:np.zeros(formula_count,dtype=np.int64) for f in fields} for s in SPLITS}
    split_counts=Counter(); target_rows=[]
    formula_batches=batch_ranges(formula_count)
    for target_offset,target_index in enumerate(range(MIN_HISTORY,n)):
        standardized=standardized_stack[target_offset]
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        split=q80.split_name(target_offset,scored_targets)
        split_counts[split]+=1
        bucket=accum[split]
        best_key=None; best_index=None; best_ranks=None
        # Bound memory and runtime with reproducible formula-index batches.
        for batch_start,batch_end in formula_batches:
            ranks=rank_matrix(standardized@weights[:,batch_start:batch_end])
            actual_ranks=ranks[actual_indices,:]
            rank_sum=actual_ranks.sum(axis=0,dtype=np.int64)
            hits5=np.sum(actual_ranks<=5,axis=0,dtype=np.int64)
            hits10=np.sum(actual_ranks<=10,axis=0,dtype=np.int64)
            hits20=np.sum(actual_ranks<=20,axis=0,dtype=np.int64)
            bucket["number_hits_top5"][batch_start:batch_end]+=hits5
            bucket["number_hits_top10"][batch_start:batch_end]+=hits10
            bucket["number_hits_top20"][batch_start:batch_end]+=hits20
            bucket["all5_top5"][batch_start:batch_end]+=np.all(actual_ranks<=5,axis=0)
            bucket["all5_top10"][batch_start:batch_end]+=np.all(actual_ranks<=10,axis=0)
            bucket["all5_top20"][batch_start:batch_end]+=np.all(actual_ranks<=20,axis=0)
            bucket["rank_sum"][batch_start:batch_end]+=rank_sum
            local_best=int(np.lexsort((-hits5,hits20,rank_sum))[0])
            candidate=(int(rank_sum[local_best]),int(hits20[local_best]),-int(hits5[local_best]),batch_start+local_best)
            if best_key is None or candidate<best_key:
                best_key=candidate; best_index=batch_start+local_best
                best_ranks=actual_ranks[:,local_best].astype(int).tolist()
        single_ranks=rank_matrix(standardized)[actual_indices,:]
        single_ledger=[]
        for column,name in enumerate(FEATURE_NAMES):
            values=single_ranks[:,column].astype(int).tolist()
            single_ledger.append({"feature":name,"ranks":values,"hits_top5":sum(v<=5 for v in values),
                "hits_top10":sum(v<=10 for v in values),"hits_top20":sum(v<=20 for v in values),"rank_sum":sum(values)})
        target_rows.append({"target_date":dates[target_index],"cutoff_date":dates[target_index-1],
            "prior_draws":target_index,"actual_quintet":" ".join(map(str,draws[target_index])),"status":"SCORED",
            "formula_count_tested":formula_count,"best_formula_id":FORMULA_IDS[best_index],
            "best_formula_features":"+".join(FEATURE_NAMES[c] for c in FORMULAS[best_index]),
            "best_actual_number_ranks":json.dumps(best_ranks,separators=(",",":")),
            "best_number_hits_top5":sum(v<=5 for v in best_ranks),"best_number_hits_top10":sum(v<=10 for v in best_ranks),
            "best_number_hits_top20":sum(v<=20 for v in best_ranks),"best_rank_sum":sum(best_ranks),
            "single_feature_rank_ledger":json.dumps(single_ledger,separators=(",",":"))})

    metric_rows=[]; p_records=[]
    for split in SPLITS:
        targets=int(split_counts[split])
        if targets<=0: raise SystemExit("Q87_BLOCKED: empty split "+split)
        bucket=accum[split]
        for fi,columns in enumerate(FORMULAS):
            row={"split":split,"formula_id":FORMULA_IDS[fi],"feature_count":7,
                "features":"+".join(FEATURE_NAMES[c] for c in columns),"targets":targets,
                "mean_number_hits_top5":int(bucket["number_hits_top5"][fi])/(5*targets),
                "mean_number_hits_top10":int(bucket["number_hits_top10"][fi])/(5*targets),
                "mean_number_hits_top20":int(bucket["number_hits_top20"][fi])/(5*targets),
                "all5_top5_rate":int(bucket["all5_top5"][fi])/targets,
                "all5_top10_rate":int(bucket["all5_top10"][fi])/targets,
                "all5_top20_rate":int(bucket["all5_top20"][fi])/targets,
                "mean_rank_of_actual_numbers":int(bucket["rank_sum"][fi])/(5*targets)}
            for endpoint,successes,p0 in (("top5",int(bucket["number_hits_top5"][fi]),5/40),
                                           ("top10",int(bucket["number_hits_top10"][fi]),10/40),
                                           ("top20",int(bucket["number_hits_top20"][fi]),20/40)):
                field="p_"+endpoint+"_normal_approx"
                row[field]=q80.binomial_upper_normal_p(successes,5*targets,p0)
                p_records.append((len(metric_rows),row[field]))
            metric_rows.append(row)
    # No shard-local Holm: aggregation applies one global correction over all shards.
    for row in metric_rows:
        row["holm_p_max_endpoint_family"]=1.0

    METRICS.parent.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    with METRICS.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(metric_rows[0].keys())); writer.writeheader(); writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(target_rows[0].keys())); writer.writeheader(); writer.writerows(target_rows)
    blind=[row for row in metric_rows if row["split"]=="blind_oos"]
    best_rank=sorted(blind,key=lambda r:(float(r["mean_rank_of_actual_numbers"]),-float(r["mean_number_hits_top5"])))[:10]
    best_top5=sorted(blind,key=lambda r:(-float(r["mean_number_hits_top5"]),float(r["mean_rank_of_actual_numbers"])))[:10]
    report={"schema_version":"1.0","task_id":"Q87","status":"SHARD_COMPLETE_NOT_TASK_COMPLETE",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),"target_count":n,
        "first_date":dates[0],"last_date":dates[-1],"minimum_prior_history":MIN_HISTORY,
        "scored_targets":len(target_rows),"feature_count":FEATURE_COUNT,"features":FEATURE_NAMES,
        "formula_count":formula_count,"total_formula_count":TOTAL_FORMULA_COUNT,"formula_count_check":math.comb(FEATURE_COUNT,FORMULA_SIZE),
        "shard_index":SHARD_INDEX,"shard_count":SHARD_COUNT,"shard_formula_start_inclusive":SHARD_START,"shard_formula_end_exclusive":SHARD_END,
        "formula_batch_size":FORMULA_BATCH_SIZE,"formula_batch_count":len(formula_batches),
        "batch_manifest":[{"batch_index":i,"formula_start_inclusive":SHARD_START+a,"formula_end_exclusive":SHARD_START+b,"formula_count":b-a,"formula_id_first":FORMULA_IDS[a],"formula_id_last":FORMULA_IDS[b-1]} for i,(a,b) in enumerate(formula_batches)],
        "formula_grammar":"all 7-feature equal-weight combinations",
        "scoring_rule":"per target, z-score each of the 27 features over numbers 1..40, then average each unordered 7-feature subset",
        "metrics_rows":len(metric_rows),"target_ledger_rows":len(target_rows),
        "split_counts":{s:int(split_counts[s]) for s in SPLITS},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,
            "mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"GLOBAL_HOLM_PENDING_AGGREGATION","test_count":len(p_records),
            "p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test"},
        "holm_adjusted_formula_split_rows_below_0_05":None,
        "minimum_holm_p_max_endpoint_family":None,
        "best_blind_oos_by_mean_rank":[compact_metric(r) for r in best_rank],
        "best_blind_oos_by_mean_top5_hits":[compact_metric(r) for r in best_top5],
        "guardrails":["every feature vector for target i uses only draws with index less than i",
            "all 40 numbers are ranked before evaluating the target quintet",
            "exhaustive only for the declared 7-feature equal-weight grammar",
            "best-per-target formula is retrospective/descriptive, not a prospective forecast",
            "no immutable freeze is read for writing or overwritten",
            "Q87 covers seven-feature subsets; higher orders require separately budgeted runs"],
        "outputs":{"metrics":str(METRICS.relative_to(ROOT)),"target_ledger":str(TARGET_LEDGER.relative_to(ROOT)),"report":str(REPORT.relative_to(ROOT))}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if len(metric_rows)!=formula_count*len(SPLITS) or len(target_rows)!=scored_targets or len(p_records)!=formula_count*len(SPLITS)*3:
        raise SystemExit("Q87_BLOCKED: output dimensions or multiple-testing family mismatch")
    summary={k:report[k] for k in ("task_id","status","review_status","target_count","first_date","last_date",
        "minimum_prior_history","scored_targets","feature_count","formula_count","metrics_rows","target_ledger_rows",
        "split_counts","multiple_testing","holm_adjusted_formula_split_rows_below_0_05",
        "minimum_holm_p_max_endpoint_family","best_blind_oos_by_mean_rank","best_blind_oos_by_mean_top5_hits")}
    print("SONAR_Q87_SHARD_SUMMARY_BEGIN"); print(json.dumps(summary,ensure_ascii=False,separators=(",",":"))); print("SONAR_Q87_SHARD_SUMMARY_END")
    print("SONAR_Q87_SHARD_REPORT_BEGIN"); print(REPORT.read_text(encoding="utf-8"),end=""); print("SONAR_Q87_SHARD_REPORT_END")

if __name__=="__main__": main()
