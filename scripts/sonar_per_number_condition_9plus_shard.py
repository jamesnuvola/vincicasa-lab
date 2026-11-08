#!/usr/bin/env python3
"""Distributed prior-only walk-forward evaluator for the Q89 nine-feature formula grammar."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, os
from collections import Counter
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_q89_common as q89

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/sequence_agent"
MIN_HISTORY=q80.MIN_HISTORY
FEATURE_NAMES=q80.FEATURE_NAMES
FEATURE_COUNT=len(FEATURE_NAMES)
FORMULA_SIZE=q89.FORMULA_SIZE
FORMULA_BATCH_SIZE=q89.FORMULA_BATCH_SIZE
SPLITS=("discovery","validation","blind_oos")
SHARD_INDEX=int(os.environ.get("SONAR_Q89_SHARD_INDEX","0"))
SHARD_START,SHARD_END=q89.shard_bounds(SHARD_INDEX)
SHARD_SIZE=SHARD_END-SHARD_START
SHARD_DIR=OUT/"q89_shards"
METRICS=SHARD_DIR/f"shard_{SHARD_INDEX}_metrics.csv"
TARGET_LEDGER=SHARD_DIR/f"shard_{SHARD_INDEX}_target_ledger.csv"
REPORT=SHARD_DIR/f"shard_{SHARD_INDEX}_report.json"

def rank_matrix(scores):
    """Rank every column; stable sort gives lower number priority on exact ties."""
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    return ranks

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
    n=len(draws)
    scored_targets=n-MIN_HISTORY
    if scored_targets<=0:
        raise SystemExit("Q89_BLOCKED: no targets have sufficient prior history")
    formulas=list(q89.iter_formula_slice(SHARD_START,SHARD_END))
    if len(formulas)!=SHARD_SIZE or SHARD_SIZE!=312455:
        raise SystemExit("Q89_BLOCKED: deterministic shard formula count mismatch")
    formula_ids=[q89.formula_id(columns) for columns in formulas]
    if formula_ids[0]!=q89.formula_id(q89.formula_unrank(SHARD_START)) or q89.formula_rank(formulas[-1])!=SHARD_END-1:
        raise SystemExit("Q89_BLOCKED: shard formula rank boundary mismatch")
    standardized_stack=q81.build_feature_stack(draws)
    if standardized_stack.shape!=(scored_targets,40,FEATURE_COUNT):
        raise SystemExit("Q89_BLOCKED: prior-only feature stack dimensions mismatch")
    weights=build_formula_weight_matrix(formulas)
    fields=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")
    accum={split:{field:np.zeros(SHARD_SIZE,dtype=np.int64) for field in fields} for split in SPLITS}
    split_counts=Counter()
    target_rows=[]
    formula_batches=q89.batch_ranges(SHARD_SIZE)
    for target_offset,target_index in enumerate(range(MIN_HISTORY,n)):
        standardized=standardized_stack[target_offset]
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        split=q80.split_name(target_offset,scored_targets)
        split_counts[split]+=1
        bucket=accum[split]
        best_key=None
        best_index=None
        best_ranks=None
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
                best_key=candidate
                best_index=batch_start+local_best
                best_ranks=actual_ranks[:,local_best].astype(int).tolist()
        single_ranks=rank_matrix(standardized)[actual_indices,:]
        single_ledger=[]
        for column,name in enumerate(FEATURE_NAMES):
            values=single_ranks[:,column].astype(int).tolist()
            single_ledger.append({"feature":name,"ranks":values,"hits_top5":sum(v<=5 for v in values),
                "hits_top10":sum(v<=10 for v in values),"hits_top20":sum(v<=20 for v in values),"rank_sum":sum(values)})
        target_rows.append({"target_date":dates[target_index],"cutoff_date":dates[target_index-1],
            "prior_draws":target_index,"actual_quintet":" ".join(map(str,draws[target_index])),"status":"SCORED",
            "formula_count_tested":q89.TOTAL_FORMULA_COUNT,"best_formula_id":formula_ids[best_index],
            "best_formula_features":"+".join(FEATURE_NAMES[c] for c in formulas[best_index]),
            "best_actual_number_ranks":json.dumps(best_ranks,separators=(",",":")),
            "best_number_hits_top5":sum(v<=5 for v in best_ranks),"best_number_hits_top10":sum(v<=10 for v in best_ranks),
            "best_number_hits_top20":sum(v<=20 for v in best_ranks),"best_rank_sum":sum(best_ranks),
            "single_feature_rank_ledger":json.dumps(single_ledger,separators=(",",":"))})

    metric_rows=[]
    for split in SPLITS:
        targets=int(split_counts[split])
        if targets<=0:
            raise SystemExit("Q89_BLOCKED: empty split "+split)
        bucket=accum[split]
        for formula_index,columns in enumerate(formulas):
            successes5=int(bucket["number_hits_top5"][formula_index])
            successes10=int(bucket["number_hits_top10"][formula_index])
            successes20=int(bucket["number_hits_top20"][formula_index])
            row={"split":split,"formula_id":formula_ids[formula_index],"feature_count":9,
                "features":"+".join(FEATURE_NAMES[c] for c in columns),"targets":targets,
                "mean_number_hits_top5":successes5/(5*targets),
                "mean_number_hits_top10":successes10/(5*targets),
                "mean_number_hits_top20":successes20/(5*targets),
                "all5_top5_rate":int(bucket["all5_top5"][formula_index])/targets,
                "all5_top10_rate":int(bucket["all5_top10"][formula_index])/targets,
                "all5_top20_rate":int(bucket["all5_top20"][formula_index])/targets,
                "mean_rank_of_actual_numbers":int(bucket["rank_sum"][formula_index])/(5*targets),
                "p_top5_normal_approx":q89.hypergeom_upper_normal_p(successes5,targets,5),
                "p_top10_normal_approx":q89.hypergeom_upper_normal_p(successes10,targets,10),
                "p_top20_normal_approx":q89.hypergeom_upper_normal_p(successes20,targets,20),
                "holm_p_max_endpoint_family":1.0}
            metric_rows.append(row)

    SHARD_DIR.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    with METRICS.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(target_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_rows)
    blind=[row for row in metric_rows if row["split"]=="blind_oos"]
    best_rank=sorted(blind,key=lambda row:(float(row["mean_rank_of_actual_numbers"]),-float(row["mean_number_hits_top5"])))[:10]
    best_top5=sorted(blind,key=lambda row:(-float(row["mean_number_hits_top5"]),float(row["mean_rank_of_actual_numbers"])))[:10]
    batches=[]
    for batch_index,(local_start,local_end) in enumerate(formula_batches):
        batches.append({"batch_index":batch_index,"formula_start_inclusive":SHARD_START+local_start,
            "formula_end_exclusive":SHARD_START+local_end,"formula_count":local_end-local_start,
            "formula_id_first":formula_ids[local_start],"formula_id_last":formula_ids[local_end-1]})
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    report={"schema_version":"1.0","task_id":"Q89","status":"SHARD_COMPLETE_NOT_TASK_COMPLETE",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":source_sha,"target_count":n,"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":MIN_HISTORY,"scored_targets":len(target_rows),"feature_count":FEATURE_COUNT,
        "features":FEATURE_NAMES,"formula_count":len(formulas),"total_formula_count":q89.TOTAL_FORMULA_COUNT,
        "formula_count_check":math.comb(FEATURE_COUNT,FORMULA_SIZE),"formula_size":FORMULA_SIZE,
        "shard_index":SHARD_INDEX,"shard_count":q89.SHARD_COUNT,"shard_formula_start_inclusive":SHARD_START,
        "shard_formula_end_exclusive":SHARD_END,"shard_formula_count":SHARD_SIZE,
        "formula_batch_size":FORMULA_BATCH_SIZE,"formula_batch_count":len(formula_batches),"batch_manifest":batches,
        "formula_grammar":"all nine-feature equal-weight combinations",
        "scoring_rule":"for each target strict prefix, z-score each of the 27 features across numbers 1..40 and average each unordered nine-feature subset",
        "metrics_rows":len(metric_rows),"target_ledger_rows":len(target_rows),
        "split_counts":{split:int(split_counts[split]) for split in SPLITS},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,
            "mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"GLOBAL_HOLM_PENDING_AGGREGATION","test_count":len(metric_rows)*3,
            "p_value_method":"continuity-corrected normal approximation to summed Hypergeometric(40,k,5) number-hit counts; exploratory, not exact"},
        "holm_adjusted_formula_split_rows_below_0_05":None,"minimum_holm_p_max_endpoint_family":None,
        "best_blind_oos_by_mean_rank":[compact_metric(row) for row in best_rank],
        "best_blind_oos_by_mean_top5_hits":[compact_metric(row) for row in best_top5],
        "guardrails":["all features for target i use only draws[0:i]; target i is not in its feature state",
            "rank all 40 numbers before scoring the target quintet","finite nine-feature equal-weight grammar only",
            "best-per-target formula is retrospective/descriptive and is never used for ex-ante candidate selection",
            "global Holm correction is applied across all 15 shards, three chronological splits and three endpoints",
            "no immutable freeze is overwritten; no automatic engine promotion"],
        "outputs":{"metrics":"reports/sequence_agent/q89_shards/shard_"+str(SHARD_INDEX)+"_metrics.csv",
            "target_ledger":"reports/sequence_agent/q89_shards/shard_"+str(SHARD_INDEX)+"_target_ledger.csv",
            "report":"reports/sequence_agent/q89_shards/shard_"+str(SHARD_INDEX)+"_report.json"}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if len(metric_rows)!=len(formulas)*len(SPLITS) or len(target_rows)!=scored_targets:
        raise SystemExit("Q89_BLOCKED: shard output dimensions mismatch")
    summary={key:report[key] for key in ("task_id","status","review_status","target_count","first_date","last_date",
        "minimum_prior_history","scored_targets","feature_count","formula_count","total_formula_count","shard_index",
        "shard_count","shard_formula_start_inclusive","shard_formula_end_exclusive","metrics_rows","target_ledger_rows",
        "split_counts","multiple_testing","best_blind_oos_by_mean_rank","best_blind_oos_by_mean_top5_hits")}
    print("SONAR_Q89_SHARD_SUMMARY_BEGIN")
    print(json.dumps(summary,ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q89_SHARD_SUMMARY_END")
    print("SONAR_Q89_SHARD_REPORT_BEGIN")
    print(REPORT.read_text(encoding="utf-8"),end="")
    print("SONAR_Q89_SHARD_REPORT_END")

if __name__=="__main__":
    main()
