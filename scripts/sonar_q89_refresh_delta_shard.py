#!/usr/bin/env python3
"""Strict-prefix target-delta evaluator for the Q89 2026-11-08 archive refresh."""
from __future__ import annotations
import csv
import gzip
import hashlib
import io
import json
import os
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
EXPECTED_DRAW_COUNT=3402
EXPECTED_LAST_DATE="2026-11-08"
EXPECTED_TARGET_COUNT=3352
TARGET_OFFSETS=(2011,2681,3351)
TARGET_MOVEMENTS={
    2011:"old_validation_to_new_discovery",
    2681:"old_blind_to_new_validation",
    3351:"new_target_in_new_blind_oos",
}
SHARD_INDEX=int(os.environ.get("SONAR_Q89_REFRESH_SHARD_INDEX","0"))
SHARD_START,SHARD_END=q89.shard_bounds(SHARD_INDEX)
SHARD_SIZE=SHARD_END-SHARD_START
SHARD_DIR=OUT/"q89_refresh_20261108_delta_shards"
METRICS=SHARD_DIR/f"shard_{SHARD_INDEX}_delta_metrics.csv.gz"
REPORT=SHARD_DIR/f"shard_{SHARD_INDEX}_delta_report.json"
METRIC_NAMES=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")

def rank_matrix(scores):
    """Rank all 40 numbers; stable sort resolves exact ties in favor of lower number."""
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    return ranks

def build_formula_weight_matrix(formulas):
    weights=np.zeros((FEATURE_COUNT,len(formulas)),dtype=np.float64)
    for formula_index,columns in enumerate(formulas):
        weights[list(columns),formula_index]=1.0/FORMULA_SIZE
    return weights

def target_metric_arrays(standardized,actual_indices,weights):
    ranks=rank_matrix(standardized@weights)
    actual_ranks=ranks[actual_indices,:]
    return {
        "number_hits_top5":np.sum(actual_ranks<=5,axis=0,dtype=np.int64),
        "number_hits_top10":np.sum(actual_ranks<=10,axis=0,dtype=np.int64),
        "number_hits_top20":np.sum(actual_ranks<=20,axis=0,dtype=np.int64),
        "all5_top5":np.all(actual_ranks<=5,axis=0).astype(np.int64),
        "all5_top10":np.all(actual_ranks<=10,axis=0).astype(np.int64),
        "all5_top20":np.all(actual_ranks<=20,axis=0).astype(np.int64),
        "rank_sum":np.sum(actual_ranks,axis=0,dtype=np.int64),
    }

def adjust_split_counts(old_counts,delta_counts,split):
    """Exact additive integer refresh from the preregistered three target moves."""
    if split=="discovery":
        result={name:int(old_counts[name])+int(delta_counts[2011][name]) for name in METRIC_NAMES}
    elif split=="validation":
        result={name:int(old_counts[name])-int(delta_counts[2011][name])+int(delta_counts[2681][name]) for name in METRIC_NAMES}
    elif split=="blind_oos":
        result={name:int(old_counts[name])-int(delta_counts[2681][name])+int(delta_counts[3351][name]) for name in METRIC_NAMES}
    else:
        raise ValueError("unknown chronological split: "+str(split))
    return result

def validate_target_delta_ledger(dates,draws,scored_targets):
    rows=[]
    for offset in TARGET_OFFSETS:
        if offset<0 or offset>=scored_targets:
            raise SystemExit("Q89_REFRESH_BLOCKED: target offset outside strict-prefix scored range")
        index=MIN_HISTORY+offset
        if index<MIN_HISTORY or index>=len(draws):
            raise SystemExit("Q89_REFRESH_BLOCKED: target index outside archive")
        rows.append({
            "target_offset":offset,
            "archive_index":index,
            "target_date":dates[index],
            "cutoff_date":dates[index-1],
            "prior_draws":index,
            "actual_quintet":" ".join(map(str,draws[index])),
            "split_movement":TARGET_MOVEMENTS[offset],
        })
    return rows

def main():
    dates,draws=q80.load_archive()
    n=len(draws)
    scored_targets=n-MIN_HISTORY
    if n!=EXPECTED_DRAW_COUNT or dates[-1]!=EXPECTED_LAST_DATE or scored_targets!=EXPECTED_TARGET_COUNT:
        raise SystemExit("Q89_REFRESH_BLOCKED: canonical 2026-11-08 archive dimensions/cutoff mismatch")
    if SHARD_SIZE!=312455:
        raise SystemExit("Q89_REFRESH_BLOCKED: deterministic nine-feature shard count mismatch")
    formulas=list(q89.iter_formula_slice(SHARD_START,SHARD_END))
    if len(formulas)!=SHARD_SIZE:
        raise SystemExit("Q89_REFRESH_BLOCKED: formula shard enumeration count mismatch")
    if q89.formula_rank(formulas[0])!=SHARD_START or q89.formula_rank(formulas[-1])!=SHARD_END-1:
        raise SystemExit("Q89_REFRESH_BLOCKED: formula rank boundaries mismatch")
    target_ledger=validate_target_delta_ledger(dates,draws,scored_targets)
    standardized_stack=q81.build_feature_stack(draws)
    if standardized_stack.shape!=(scored_targets,40,FEATURE_COUNT):
        raise SystemExit("Q89_REFRESH_BLOCKED: prior-only feature stack dimensions mismatch")
    target_states=[]
    for row in target_ledger:
        offset=int(row["target_offset"])
        index=int(row["archive_index"])
        target_states.append((offset,standardized_stack[offset],np.asarray(draws[index],dtype=np.int64)-1))
    formula_batches=q89.batch_ranges(SHARD_SIZE,FORMULA_BATCH_SIZE)
    fieldnames=["formula_rank","formula_id"]+[f"o{offset}_{metric}" for offset in TARGET_OFFSETS for metric in METRIC_NAMES]
    SHARD_DIR.mkdir(parents=True,exist_ok=True)
    OUT.mkdir(parents=True,exist_ok=True)
    row_count=0
    with METRICS.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",compresslevel=9,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as text:
                writer=csv.DictWriter(text,fieldnames=fieldnames,lineterminator="\n")
                writer.writeheader()
                for batch_start,batch_end in formula_batches:
                    global_start=SHARD_START+batch_start
                    global_end=SHARD_START+batch_end
                    batch_formulas=list(q89.iter_formula_slice(global_start,global_end))
                    if len(batch_formulas)!=batch_end-batch_start:
                        raise SystemExit("Q89_REFRESH_BLOCKED: formula batch coverage mismatch")
                    formula_ids=[q89.formula_id(columns) for columns in batch_formulas]
                    weights=build_formula_weight_matrix(batch_formulas)
                    per_target={}
                    for offset,standardized,actual_indices in target_states:
                        arrays=target_metric_arrays(standardized,actual_indices,weights)
                        per_target[offset]=arrays
                    for local_index,formula_id in enumerate(formula_ids):
                        row={"formula_rank":global_start+local_index,"formula_id":formula_id}
                        for offset in TARGET_OFFSETS:
                            for metric in METRIC_NAMES:
                                value=int(per_target[offset][metric][local_index])
                                row[f"o{offset}_{metric}"]=value
                        writer.writerow(row)
                        row_count+=1
    if row_count!=SHARD_SIZE:
        raise SystemExit("Q89_REFRESH_BLOCKED: delta shard row count mismatch")
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    raw_bytes=METRICS.read_bytes()
    report={
        "schema_version":"1.0",
        "task_id":"Q89_REFRESH_2026_11_08",
        "status":"DELTA_SHARD_COMPLETE_NOT_TASK_COMPLETE",
        "protocol_id":"Q89-nine-feature-incremental-refresh-2026-11-08",
        "source_archive":"data/storico_daily.csv",
        "source_archive_sha256":source_sha,
        "target_count":n,
        "first_date":dates[0],
        "last_date":dates[-1],
        "minimum_prior_history":MIN_HISTORY,
        "scored_targets":scored_targets,
        "feature_count":FEATURE_COUNT,
        "formula_size":FORMULA_SIZE,
        "total_formula_count":q89.TOTAL_FORMULA_COUNT,
        "shard_index":SHARD_INDEX,
        "shard_count":q89.SHARD_COUNT,
        "shard_formula_start_inclusive":SHARD_START,
        "shard_formula_end_exclusive":SHARD_END,
        "shard_formula_count":SHARD_SIZE,
        "formula_batch_size":FORMULA_BATCH_SIZE,
        "formula_batch_count":len(formula_batches),
        "formula_grammar":"all nine-feature equal-weight combinations; only the three preregistered target offsets are rescored",
        "target_delta_ledger":target_ledger,
        "metrics_rows":row_count,
        "metric_schema":fieldnames,
        "output":{"path":str(METRICS.relative_to(ROOT)),"bytes":len(raw_bytes),"sha256":hashlib.sha256(raw_bytes).hexdigest()},
        "guardrails":["all target feature states use only draws[0:i] before target i","target outcomes are used only as additive metric deltas for the frozen chronological split transition","formula rank coverage is contiguous and deterministic","no blind target is used for candidate selection","no immutable archive freeze is overwritten; no engine promotion"]
    }
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={key:report[key] for key in ("task_id","status","source_archive_sha256","target_count","last_date","scored_targets","formula_size","total_formula_count","shard_index","shard_count","shard_formula_start_inclusive","shard_formula_end_exclusive","shard_formula_count","formula_batch_count","target_delta_ledger","metrics_rows","output")}
    print("SONAR_Q89_REFRESH_DELTA_SHARD_SUMMARY_BEGIN")
    print(json.dumps(summary,ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q89_REFRESH_DELTA_SHARD_SUMMARY_END")
    print("SONAR_Q89_REFRESH_DELTA_SHARD_REPORT_BEGIN")
    print(REPORT.read_text(encoding="utf-8"),end="")
    print("SONAR_Q89_REFRESH_DELTA_SHARD_REPORT_END")

if __name__=="__main__":
    main()
