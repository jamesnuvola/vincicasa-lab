#!/usr/bin/env python3
"""Walk-forward evaluation of every 4-feature equal-weight formula in the Q81 grammar."""
from __future__ import annotations
import csv, hashlib, itertools, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/sequence_agent"
METRICS=OUT/"per_number_condition_4plus_formula_metrics.csv"
TARGET_LEDGER=OUT/"per_number_condition_4plus_target_ledger.csv"
REPORT=OUT/"per_number_condition_4plus_grammar.json"
MIN_HISTORY=q80.MIN_HISTORY
FEATURE_NAMES=q80.FEATURE_NAMES
FEATURE_COUNT=len(FEATURE_NAMES)
FORMULA_SIZE=4
SPLITS=("discovery","validation","blind_oos")

def make_formulas():
    formulas=list(itertools.combinations(range(FEATURE_COUNT),FORMULA_SIZE))
    if len(formulas)!=math.comb(FEATURE_COUNT,FORMULA_SIZE) or len(set(formulas))!=len(formulas):
        raise RuntimeError("Q81 formula enumeration mismatch")
    return formulas

FORMULAS=make_formulas()
FORMULA_IDS=["P4_"+"_".join(f"{i:02d}" for i in cols) for cols in FORMULAS]

def rank_matrix(scores):
    """Rank every column; stable sort gives lower number priority on exact ties."""
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    return ranks

def build_feature_stack(draws):
    """Build standardized 40x27 feature matrices using only the prefix before each target."""
    n=len(draws)
    if n<=MIN_HISTORY: raise ValueError("Q81 needs at least 51 draws to score a target")
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
    if scored_targets<=0: raise SystemExit("Q81_BLOCKED: no targets have sufficient prior history")
    formula_count=len(FORMULAS)
    if formula_count!=math.comb(FEATURE_COUNT,FORMULA_SIZE): raise SystemExit("Q81_BLOCKED: formula count mismatch")
    standardized_stack=build_feature_stack(draws)
    if standardized_stack.shape!=(scored_targets,40,FEATURE_COUNT): raise SystemExit("Q81_BLOCKED: feature stack dimensions mismatch")
    weights=build_formula_weight_matrix(FORMULAS)
    fields=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")
    accum={s:{f:np.zeros(formula_count,dtype=np.int64) for f in fields} for s in SPLITS}
    split_counts=Counter(); target_rows=[]
    for target_offset,target_index in enumerate(range(MIN_HISTORY,n)):
        standardized=standardized_stack[target_offset]
        ranks=rank_matrix(standardized@weights)
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        actual_ranks=ranks[actual_indices,:]
        rank_sum=actual_ranks.sum(axis=0,dtype=np.int64)
        hits5=np.sum(actual_ranks<=5,axis=0,dtype=np.int64)
        hits10=np.sum(actual_ranks<=10,axis=0,dtype=np.int64)
        hits20=np.sum(actual_ranks<=20,axis=0,dtype=np.int64)
        split=q80.split_name(target_offset,scored_targets); split_counts[split]+=1
        bucket=accum[split]
        bucket["number_hits_top5"]+=hits5; bucket["number_hits_top10"]+=hits10; bucket["number_hits_top20"]+=hits20
        bucket["all5_top5"]+=np.all(actual_ranks<=5,axis=0)
        bucket["all5_top10"]+=np.all(actual_ranks<=10,axis=0)
        bucket["all5_top20"]+=np.all(actual_ranks<=20,axis=0)
        bucket["rank_sum"]+=rank_sum
        # Best-per-target is retrospective/descriptive, never a prospective forecast.
        best=int(np.lexsort((-hits5,hits20,rank_sum))[0])
        best_ranks=actual_ranks[:,best].astype(int).tolist()
        single_ranks=rank_matrix(standardized)[actual_indices,:]
        single_ledger=[]
        for column,name in enumerate(FEATURE_NAMES):
            values=single_ranks[:,column].astype(int).tolist()
            single_ledger.append({"feature":name,"ranks":values,"hits_top5":sum(v<=5 for v in values),
                "hits_top10":sum(v<=10 for v in values),"hits_top20":sum(v<=20 for v in values),"rank_sum":sum(values)})
        target_rows.append({"target_date":dates[target_index],"cutoff_date":dates[target_index-1],
            "prior_draws":target_index,"actual_quintet":" ".join(map(str,draws[target_index])),"status":"SCORED",
            "formula_count_tested":formula_count,"best_formula_id":FORMULA_IDS[best],
            "best_formula_features":"+".join(FEATURE_NAMES[c] for c in FORMULAS[best]),
            "best_actual_number_ranks":json.dumps(best_ranks,separators=(",",":")),
            "best_number_hits_top5":sum(v<=5 for v in best_ranks),"best_number_hits_top10":sum(v<=10 for v in best_ranks),
            "best_number_hits_top20":sum(v<=20 for v in best_ranks),"best_rank_sum":sum(best_ranks),
            "single_feature_rank_ledger":json.dumps(single_ledger,separators=(",",":"))})

    metric_rows=[]; p_records=[]
    for split in SPLITS:
        targets=int(split_counts[split])
        if targets<=0: raise SystemExit("Q81_BLOCKED: empty split "+split)
        bucket=accum[split]
        for fi,columns in enumerate(FORMULAS):
            row={"split":split,"formula_id":FORMULA_IDS[fi],"feature_count":4,
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
    adjusted=q80.holm_adjust([p for _,p in p_records])
    for (row_index,_),p_adj in zip(p_records,adjusted):
        metric_rows[row_index]["holm_p_max_endpoint_family"]=max(metric_rows[row_index].get("holm_p_max_endpoint_family",0.0),p_adj)

    OUT.mkdir(parents=True,exist_ok=True)
    with METRICS.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(metric_rows[0].keys())); writer.writeheader(); writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(target_rows[0].keys())); writer.writeheader(); writer.writerows(target_rows)
    blind=[row for row in metric_rows if row["split"]=="blind_oos"]
    best_rank=sorted(blind,key=lambda r:(float(r["mean_rank_of_actual_numbers"]),-float(r["mean_number_hits_top5"])))[:10]
    best_top5=sorted(blind,key=lambda r:(-float(r["mean_number_hits_top5"]),float(r["mean_rank_of_actual_numbers"])))[:10]
    report={"schema_version":"1.0","task_id":"Q81","status":"VALIDATED_FINITE_GRAMMAR_COMPLETE",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),"target_count":n,
        "first_date":dates[0],"last_date":dates[-1],"minimum_prior_history":MIN_HISTORY,
        "scored_targets":len(target_rows),"feature_count":FEATURE_COUNT,"features":FEATURE_NAMES,
        "formula_count":formula_count,"formula_count_check":math.comb(FEATURE_COUNT,FORMULA_SIZE),
        "formula_grammar":"all 4-feature equal-weight combinations",
        "scoring_rule":"per target, z-score each of the 27 features over numbers 1..40, then average each unordered 4-feature subset",
        "metrics_rows":len(metric_rows),"target_ledger_rows":len(target_rows),
        "split_counts":{s:int(split_counts[s]) for s in SPLITS},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,
            "mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":len(p_records),
            "p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test"},
        "holm_adjusted_formula_split_rows_below_0_05":sum(float(r["holm_p_max_endpoint_family"])<0.05 for r in metric_rows),
        "minimum_holm_p_max_endpoint_family":min(float(r["holm_p_max_endpoint_family"]) for r in metric_rows),
        "best_blind_oos_by_mean_rank":[compact_metric(r) for r in best_rank],
        "best_blind_oos_by_mean_top5_hits":[compact_metric(r) for r in best_top5],
        "guardrails":["every feature vector for target i uses only draws with index less than i",
            "all 40 numbers are ranked before evaluating the target quintet",
            "exhaustive only for the declared 4-feature equal-weight grammar",
            "best-per-target formula is retrospective/descriptive, not a prospective forecast",
            "no immutable freeze is read for writing or overwritten",
            "Q82 extends to conditional thresholds/nonlinear interactions; Q83 extends to 5+ feature subsets"],
        "outputs":{"metrics":str(METRICS.relative_to(ROOT)),"target_ledger":str(TARGET_LEDGER.relative_to(ROOT)),"report":str(REPORT.relative_to(ROOT))}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if len(metric_rows)!=formula_count*len(SPLITS) or len(target_rows)!=scored_targets or len(p_records)!=formula_count*len(SPLITS)*3:
        raise SystemExit("Q81_BLOCKED: output dimensions or multiple-testing family mismatch")
    summary={k:report[k] for k in ("task_id","status","review_status","target_count","first_date","last_date",
        "minimum_prior_history","scored_targets","feature_count","formula_count","metrics_rows","target_ledger_rows",
        "split_counts","multiple_testing","holm_adjusted_formula_split_rows_below_0_05",
        "minimum_holm_p_max_endpoint_family","best_blind_oos_by_mean_rank","best_blind_oos_by_mean_top5_hits")}
    print("SONAR_Q81_SUMMARY_BEGIN"); print(json.dumps(summary,ensure_ascii=False,separators=(",",":"))); print("SONAR_Q81_SUMMARY_END")
    print("SONAR_Q81_REPORT_BEGIN"); print(REPORT.read_text(encoding="utf-8"),end=""); print("SONAR_Q81_REPORT_END")

if __name__=="__main__": main()
