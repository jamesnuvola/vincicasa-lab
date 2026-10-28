#!/usr/bin/env python3
"""Walk-forward finite grammar of nonlinear, pairwise and discovery-threshold rules (Q82).

All 27 source features are computed from the complete prefix strictly before each
target. Thresholds are quantiles of discovery-split feature values only (never
target outcomes) and are frozen before validation/blind-OOS scoring.
"""
from __future__ import annotations
import csv, hashlib, itertools, json, math
from collections import Counter
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81

ROOT=Path(__file__).resolve().parents[1]
ARCHIVE=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/sequence_agent"
METRICS=OUT/"per_number_condition_conditional_metrics.csv"
TARGET_LEDGER=OUT/"per_number_condition_conditional_target_ledger.csv"
REPORT=OUT/"per_number_condition_conditional_grammar.json"
MIN_HISTORY=q80.MIN_HISTORY
FEATURE_NAMES=q80.FEATURE_NAMES
FEATURE_COUNT=len(FEATURE_NAMES)
SPLITS=("discovery","validation","blind_oos")
QUANTILES=(0.25,0.50,0.75)
QUANTILE_LABELS=("q25","q50","q75")
NONLINEAR_TRANSFORMS=("absolute","centrality","quadratic_up","quadratic_down")
FAMILY_COUNTS={
    "base":FEATURE_COUNT,
    "nonlinear":FEATURE_COUNT*len(NONLINEAR_TRANSFORMS),
    "interaction":math.comb(FEATURE_COUNT,2),
    "conditional":FEATURE_COUNT*(FEATURE_COUNT-1)*len(QUANTILES)*2,
}
EXPECTED_FORMULA_COUNT=sum(FAMILY_COUNTS.values())


def make_term_definitions():
    terms=[]
    for i,name in enumerate(FEATURE_NAMES):
        terms.append({"formula_id":f"BASE_{i:02d}_{name}","formula_family":"base",
            "feature_count":1,"features":name,"threshold_rule":"none","indices":[i]})
    for transform in NONLINEAR_TRANSFORMS:
        for i,name in enumerate(FEATURE_NAMES):
            terms.append({"formula_id":f"NL_{transform.upper()}_{i:02d}_{name}",
                "formula_family":"nonlinear","feature_count":1,"features":name,
                "threshold_rule":"none","indices":[i],"transform":transform})
    for i,j in itertools.combinations(range(FEATURE_COUNT),2):
        terms.append({"formula_id":f"INT_{i:02d}_{j:02d}","formula_family":"interaction",
            "feature_count":2,"features":FEATURE_NAMES[i]+"+"+FEATURE_NAMES[j],
            "threshold_rule":"product","indices":[i,j]})
    # Ordering matches build_term_scores: gate feature, direction, score feature, quantile.
    for gate in range(FEATURE_COUNT):
        other=[i for i in range(FEATURE_COUNT) if i!=gate]
        for direction in ("GT","LT"):
            for score in other:
                for qlabel in QUANTILE_LABELS:
                    terms.append({"formula_id":f"COND_{direction}_{qlabel}_S{score:02d}_G{gate:02d}",
                        "formula_family":"conditional","feature_count":2,
                        "features":FEATURE_NAMES[score]+"+"+FEATURE_NAMES[gate],
                        "threshold_rule":f"{direction.lower()}:{qlabel}",
                        "indices":[score,gate],"score_index":score,"gate_index":gate,
                        "direction":direction,"quantile":qlabel})
    ids=[t["formula_id"] for t in terms]
    counts=Counter(t["formula_family"] for t in terms)
    if len(ids)!=len(set(ids)) or len(terms)!=EXPECTED_FORMULA_COUNT or dict(counts)!=FAMILY_COUNTS:
        raise RuntimeError("Q82 finite grammar enumeration mismatch")
    return terms


TERMS=make_term_definitions()
TERM_IDS=[term["formula_id"] for term in TERMS]


def select_thresholds(standardized_stack, discovery_targets):
    """Quantile thresholds from discovery feature values only; no target outcomes are read."""
    if standardized_stack.ndim!=3 or standardized_stack.shape[1:]!=(40,FEATURE_COUNT):
        raise ValueError("Q82 expected target x 40-number x 27-feature stack")
    if discovery_targets<1 or discovery_targets>=standardized_stack.shape[0]:
        raise ValueError("Q82 invalid discovery target count")
    thresholds=np.empty((FEATURE_COUNT,len(QUANTILES)),dtype=np.float64)
    for feature in range(FEATURE_COUNT):
        values=standardized_stack[:discovery_targets,:,feature].reshape(-1)
        thresholds[feature]=np.quantile(values,QUANTILES)
    if not np.isfinite(thresholds).all():
        raise ValueError("Q82 non-finite discovery threshold")
    return thresholds


def build_term_scores(standardized, thresholds):
    """Return 40 x 4,698 scores in the exact order registered by TERMS."""
    if standardized.shape!=(40,FEATURE_COUNT) or thresholds.shape!=(FEATURE_COUNT,len(QUANTILES)):
        raise ValueError("Q82 score/threshold shape mismatch")
    count=len(TERMS)
    scores=np.empty((40,count),dtype=np.float64)
    cursor=0
    scores[:,cursor:cursor+FEATURE_COUNT]=standardized; cursor+=FEATURE_COUNT
    for transform in NONLINEAR_TRANSFORMS:
        if transform=="absolute":
            block=np.abs(standardized)
        elif transform=="centrality":
            block=-np.abs(standardized)
        elif transform=="quadratic_up":
            block=standardized+0.5*np.square(standardized)
        elif transform=="quadratic_down":
            block=standardized-0.5*np.square(standardized)
        else:
            raise RuntimeError("unregistered Q82 nonlinear transform")
        scores[:,cursor:cursor+FEATURE_COUNT]=block; cursor+=FEATURE_COUNT
    pair_i=[]; pair_j=[]
    for i,j in itertools.combinations(range(FEATURE_COUNT),2):
        pair_i.append(i); pair_j.append(j)
    scores[:,cursor:cursor+len(pair_i)]=standardized[:,pair_i]*standardized[:,pair_j]
    cursor+=len(pair_i)
    for gate in range(FEATURE_COUNT):
        other=np.asarray([i for i in range(FEATURE_COUNT) if i!=gate],dtype=np.int64)
        for direction in ("GT","LT"):
            if direction=="GT":
                weights=1.0+np.maximum(standardized[:,gate,None]-thresholds[gate][None,:],0.0)
            else:
                weights=1.0+np.maximum(thresholds[gate][None,:]-standardized[:,gate,None],0.0)
            # Flatten order is score feature then q25/q50/q75, matching TERMS.
            block=(standardized[:,other,None]*weights[:,None,:]).reshape(40,-1)
            width=len(other)*len(QUANTILES)
            scores[:,cursor:cursor+width]=block
            cursor+=width
    if cursor!=count or not np.isfinite(scores).all():
        raise RuntimeError(f"Q82 score matrix incomplete/non-finite: {cursor} != {count}")
    return scores


def compact_metric(row):
    keys=("formula_id","formula_family","features","threshold_rule","mean_number_hits_top5",
          "mean_number_hits_top10","mean_number_hits_top20","mean_rank_of_actual_numbers",
          "holm_p_max_endpoint_family")
    return {key:(float(row[key]) if key.startswith("mean_") or key=="holm_p_max_endpoint_family" else row[key])
            for key in keys}


def main():
    dates,draws=q80.load_archive()
    n=len(draws); scored_targets=n-MIN_HISTORY
    if scored_targets<=0:
        raise SystemExit("Q82_BLOCKED: no targets have sufficient prior history")
    standardized_stack=q81.build_feature_stack(draws)
    if standardized_stack.shape!=(scored_targets,40,FEATURE_COUNT):
        raise SystemExit("Q82_BLOCKED: prior-only feature stack dimensions mismatch")
    discovery_targets=sum(q80.split_name(i,scored_targets)=="discovery" for i in range(scored_targets))
    thresholds=select_thresholds(standardized_stack,discovery_targets)
    terms=TERMS; formula_count=len(terms)
    if formula_count!=4698:
        raise SystemExit("Q82_BLOCKED: registered finite grammar count mismatch")
    accum={s:{field:np.zeros(formula_count,dtype=np.int64) for field in
        ("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")}
        for s in SPLITS}
    split_counts=Counter(); target_rows=[]
    for target_offset,target_index in enumerate(range(MIN_HISTORY,n)):
        standardized=standardized_stack[target_offset]
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        split=q80.split_name(target_offset,scored_targets)
        split_counts[split]+=1
        bucket=accum[split]
        scores=build_term_scores(standardized,thresholds)
        ranks=q81.rank_matrix(scores)
        actual_ranks=ranks[actual_indices,:]
        rank_sum=actual_ranks.sum(axis=0,dtype=np.int64)
        hits5=np.sum(actual_ranks<=5,axis=0,dtype=np.int64)
        hits10=np.sum(actual_ranks<=10,axis=0,dtype=np.int64)
        hits20=np.sum(actual_ranks<=20,axis=0,dtype=np.int64)
        bucket["number_hits_top5"]+=hits5
        bucket["number_hits_top10"]+=hits10
        bucket["number_hits_top20"]+=hits20
        bucket["all5_top5"]+=np.all(actual_ranks<=5,axis=0)
        bucket["all5_top10"]+=np.all(actual_ranks<=10,axis=0)
        bucket["all5_top20"]+=np.all(actual_ranks<=20,axis=0)
        bucket["rank_sum"]+=rank_sum
        best_index=int(np.lexsort((-hits5,hits20,rank_sum))[0])
        best_ranks=actual_ranks[:,best_index].astype(int).tolist()
        single_ranks=q81.rank_matrix(standardized)[actual_indices,:]
        single_ledger=[]
        for column,name in enumerate(FEATURE_NAMES):
            values=single_ranks[:,column].astype(int).tolist()
            single_ledger.append({"feature":name,"ranks":values,"hits_top5":sum(v<=5 for v in values),
                "hits_top10":sum(v<=10 for v in values),"hits_top20":sum(v<=20 for v in values),
                "rank_sum":sum(values)})
        target_rows.append({"target_date":dates[target_index],"cutoff_date":dates[target_index-1],
            "prior_draws":target_index,"actual_quintet":" ".join(map(str,draws[target_index])),
            "status":"SCORED","formula_count_tested":formula_count,"best_formula_id":TERM_IDS[best_index],
            "best_formula_features":terms[best_index]["features"],
            "best_actual_number_ranks":json.dumps(best_ranks,separators=(",",":")),
            "best_number_hits_top5":sum(v<=5 for v in best_ranks),
            "best_number_hits_top10":sum(v<=10 for v in best_ranks),
            "best_number_hits_top20":sum(v<=20 for v in best_ranks),"best_rank_sum":sum(best_ranks),
            "single_feature_rank_ledger":json.dumps(single_ledger,separators=(",",":"))})

    metric_rows=[]; p_records=[]
    for split in SPLITS:
        targets=int(split_counts[split])
        if targets<=0:
            raise SystemExit("Q82_BLOCKED: empty chronological split "+split)
        bucket=accum[split]
        for fi,term in enumerate(terms):
            row={"split":split,"formula_id":term["formula_id"],"formula_family":term["formula_family"],
                "feature_count":term["feature_count"],"features":term["features"],
                "threshold_rule":term["threshold_rule"],"targets":targets,
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
        metric_rows[row_index]["holm_p_max_endpoint_family"]=max(
            metric_rows[row_index].get("holm_p_max_endpoint_family",0.0),p_adj)

    OUT.mkdir(parents=True,exist_ok=True)
    with METRICS.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(metric_rows[0].keys())); writer.writeheader(); writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(target_rows[0].keys())); writer.writeheader(); writer.writerows(target_rows)
    blind=[row for row in metric_rows if row["split"]=="blind_oos"]
    best_rank=sorted(blind,key=lambda r:(float(r["mean_rank_of_actual_numbers"]),-float(r["mean_number_hits_top5"])))[:10]
    best_top5=sorted(blind,key=lambda r:(-float(r["mean_number_hits_top5"]),float(r["mean_rank_of_actual_numbers"])))[:10]
    threshold_report={FEATURE_NAMES[i]:{label:float(thresholds[i,j]) for j,label in enumerate(QUANTILE_LABELS)}
        for i in range(FEATURE_COUNT)}
    report={"schema_version":"1.0","task_id":"Q82","status":"VALIDATED_FINITE_GRAMMAR_COMPLETE",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),"target_count":n,
        "first_date":dates[0],"last_date":dates[-1],"minimum_prior_history":MIN_HISTORY,
        "scored_targets":len(target_rows),"feature_count":FEATURE_COUNT,"features":FEATURE_NAMES,
        "formula_count":formula_count,"formula_count_check":EXPECTED_FORMULA_COUNT,
        "formula_grammar":"27 base + 108 nonlinear + 351 pairwise interactions + 4,212 discovery-threshold gated interactions",
        "formula_family_counts":FAMILY_COUNTS,
        "nonlinear_transforms":list(NONLINEAR_TRANSFORMS),
        "threshold_selection":{"source_split":"discovery","uses_target_outcomes":False,
            "frozen_before_validation":True,"quantile_levels":list(QUANTILES),
            "quantile_labels":list(QUANTILE_LABELS),"discovery_targets":discovery_targets,
            "discovery_first_target_date":dates[MIN_HISTORY],
            "discovery_last_target_date":dates[MIN_HISTORY+discovery_targets-1],
            "method":"feature-value quantiles from standardized candidate-number features in discovery targets only; no outcome-based threshold tuning"},
        "thresholds":threshold_report,
        "metrics_rows":len(metric_rows),"target_ledger_rows":len(target_rows),
        "split_counts":{s:int(split_counts[s]) for s in SPLITS},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,
            "mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":len(p_records),
            "p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test"},
        "holm_adjusted_formula_split_rows_below_0_05":sum(float(r["holm_p_max_endpoint_family"])<0.05 for r in metric_rows),
        "minimum_holm_p_max_endpoint_family":min(float(r["holm_p_max_endpoint_family"]) for r in metric_rows),
        "best_blind_oos_by_mean_rank":[compact_metric(r) for r in sorted(best_rank,key=lambda x:(float(x["mean_rank_of_actual_numbers"]),-float(x["mean_number_hits_top5"])))],
        "best_blind_oos_by_mean_top5_hits":[compact_metric(r) for r in best_top5],
        "guardrails":["every source feature for target i uses only draws with index less than i",
            "thresholds use discovery feature distributions only and do not use target outcomes",
            "thresholds are frozen before validation and blind OOS evaluation",
            "all 40 numbers are ranked before evaluating the target quintet",
            "best-per-target rule is retrospective/descriptive, not a prospective forecast",
            "this is exhaustive only within the registered 4,698-term finite grammar",
            "no immutable freeze is read for writing or overwritten; no formula is promoted automatically"],
        "outputs":{"metrics":str(METRICS.relative_to(ROOT)),"target_ledger":str(TARGET_LEDGER.relative_to(ROOT)),
            "report":str(REPORT.relative_to(ROOT))}}
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if len(metric_rows)!=formula_count*len(SPLITS) or len(target_rows)!=scored_targets or len(p_records)!=formula_count*len(SPLITS)*3:
        raise SystemExit("Q82_BLOCKED: output dimensions or multiple-testing family mismatch")
    summary={k:report[k] for k in ("task_id","status","review_status","target_count","first_date","last_date",
        "minimum_prior_history","scored_targets","feature_count","formula_count","formula_family_counts",
        "metrics_rows","target_ledger_rows","split_counts","threshold_selection","multiple_testing",
        "holm_adjusted_formula_split_rows_below_0_05","minimum_holm_p_max_endpoint_family",
        "best_blind_oos_by_mean_rank","best_blind_oos_by_mean_top5_hits")}
    print("SONAR_Q82_SUMMARY_BEGIN"); print(json.dumps(summary,ensure_ascii=False,separators=(",",":"))); print("SONAR_Q82_SUMMARY_END")
    print("SONAR_Q82_REPORT_BEGIN"); print(REPORT.read_text(encoding="utf-8"),end=""); print("SONAR_Q82_REPORT_END")


if __name__=="__main__":
    main()
