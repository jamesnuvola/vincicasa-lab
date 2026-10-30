#!/usr/bin/env python3
"""Aggregate six Q87 shards, apply one global Holm correction, and emit verified chunks."""
from __future__ import annotations
import csv, gzip, hashlib, itertools, json, math
from pathlib import Path
from collections import Counter
import numpy as np
import sonar_per_number_condition_grammar as q80

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
SHARD_DIR=OUT/"q87_shards"
ARCHIVE=ROOT/"data/storico_daily.csv"
TOTAL=math.comb(27,7)
SHARDS=6
SHARD_SIZE=TOTAL//SHARDS
CHUNK_ROWS=30000
SPLITS=("discovery","validation","blind_oos")
FEATURES=q80.FEATURE_NAMES
METRICS_MANIFEST=OUT/"per_number_condition_7plus_formula_metrics_manifest.json"
REPORT_PATH=OUT/"per_number_condition_7plus_grammar.json"
LEDGER_PATH=OUT/"per_number_condition_7plus_target_ledger.csv"

def fail(message):
    raise SystemExit("Q87_AGGREGATION_BLOCKED: "+message)

def read_archive():
    with ARCHIVE.open(newline="",encoding="utf-8-sig") as h:
        rows=list(csv.DictReader(h))
    dates=[r["data"] for r in rows]
    if len(dates)!=len(set(dates)) or dates!=sorted(dates): fail("archive dates are not unique/chronological")
    draws=[]
    for r in rows:
        values=[int(r[f"n{i}"]) for i in range(1,6)]
        if len(set(values))!=5 or any(x<1 or x>40 for x in values): fail("invalid archive quintet")
        draws.append(values)
    return dates,draws

def formula_id(cols):
    return "P7_"+"_".join(f"{x:02d}" for x in cols)

def formula_rank(cols):
    # Lexicographic rank of a 7-combination in itertools.combinations(range(27), 7).
    rank=0
    previous=-1
    for position,value in enumerate(cols):
        for candidate in range(previous+1,value):
            rank += math.comb(27-candidate-1,7-position-1)
        previous=value
    return rank

def main():
    dates,draws=read_archive()
    date_index={d:i for i,d in enumerate(dates)}
    scored=len(draws)-q80.MIN_HISTORY
    if scored<=0: fail("no eligible targets")
    expected_split={"discovery":math.ceil(.60*scored),"validation":math.ceil(.80*scored)-math.ceil(.60*scored),"blind_oos":scored-math.ceil(.80*scored)}
    total_rows=TOTAL*len(SPLITS)
    tests=total_rows*3
    pvals=np.empty(tests,dtype=np.float64)
    row_ids=np.empty(tests,dtype=np.int64)
    split_counts=Counter()
    headers=None
    cursor=0
    formula_seen=set()
    # Pass 1: exact shard coverage and all unadjusted endpoint p-values.
    for shard in range(SHARDS):
        path=SHARD_DIR/f"shard_{shard}_metrics.csv"
        if not path.is_file(): fail(f"missing metrics for shard {shard}")
        local_counts=Counter()
        with path.open(newline="",encoding="utf-8-sig") as h:
            reader=csv.DictReader(h)
            if not reader.fieldnames: fail(f"missing CSV header in shard {shard}")
            if headers is None: headers=reader.fieldnames
            elif reader.fieldnames!=headers: fail("shard metric schemas differ")
            for row in reader:
                split=row.get("split")
                if split not in SPLITS: fail("invalid split in shard")
                fid=row.get("formula_id","")
                if fid in formula_seen: fail("duplicate formula id across shards")
                formula_seen.add(fid)
                # Validate formula ID and exact shard range.
                try:
                    parts=[int(x) for x in fid.split("_")[1:]]
                    if len(parts)!=7 or parts!=sorted(set(parts)) or parts[-1]>=27: fail("invalid seven-feature formula id")
                    if fid!=formula_id(parts): fail("non-canonical formula id")
                    idx=formula_rank(parts)
                    if not (shard*SHARD_SIZE <= idx < (shard+1)*SHARD_SIZE): fail("formula outside its declared shard")
                    if row.get("features")!=" + ".join(FEATURES[i] for i in parts) and row.get("features")!="+".join(FEATURES[i] for i in parts):
                        fail("formula feature names do not match formula id")
                except Exception as exc:
                    if isinstance(exc,SystemExit): raise
                    fail("malformed formula id")
                if int(row.get("feature_count",-1))!=7: fail("wrong feature_count")
                if int(row.get("targets",-1))!=expected_split[split]: fail("split target count mismatch")
                for k in ("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx"):
                    v=float(row[k])
                    if not math.isfinite(v) or v<0 or v>1: fail("invalid raw p-value")
                rid=cursor
                for k in ("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx"):
                    pvals[rid*3+("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx").index(k)]=float(row[k])
                    row_ids[rid*3+("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx").index(k)]=rid
                local_counts[split]+=1; split_counts[split]+=1; cursor+=1
        if local_counts!={s:SHARD_SIZE for s in SPLITS}: fail(f"shard {shard} formula/split coverage mismatch")
    if cursor!=total_rows or len(formula_seen)!=TOTAL: fail("aggregate formula/metric row coverage mismatch")
    if split_counts!={s:TOTAL for s in SPLITS}: fail("aggregate split counts mismatch")
    # Global Holm step-down across all 7,992,270 tests; max adjusted endpoint p is retained per row.
    order=np.argsort(pvals,kind="stable")
    sorted_adjusted=np.maximum.accumulate((tests-np.arange(tests))*pvals[order])
    sorted_adjusted=np.minimum(sorted_adjusted,1.0)
    adjusted=np.empty_like(sorted_adjusted)
    adjusted[order]=sorted_adjusted
    row_holm=np.zeros(total_rows,dtype=np.float64)
    np.maximum.at(row_holm,row_ids,adjusted)
    # Pass 2: write compressed metric chunks in deterministic shard/split/formula order.
    sample_fields=headers+["holm_p_max_endpoint_family"]
    part_manifest=[]; part_index=-1; part_handle=None; writer=None; part_rows=0; total_written=0
    top_rank=[]; top_top5=[]
    def open_part():
        nonlocal part_index,part_handle,writer,part_rows
        if part_handle: part_handle.close()
        part_index+=1; part_rows=0
        p=OUT/f"per_number_condition_7plus_formula_metrics_part_{part_index:02d}.csv.gz"
        part_handle=gzip.open(p,"wt",newline="",encoding="utf-8")
        writer=csv.DictWriter(part_handle,fieldnames=sample_fields); writer.writeheader()
    try:
        for shard in range(SHARDS):
            path=SHARD_DIR/f"shard_{shard}_metrics.csv"
            with path.open(newline="",encoding="utf-8-sig") as h:
                for row in csv.DictReader(h):
                    if part_handle is None or part_rows>=CHUNK_ROWS: open_part()
                    row["holm_p_max_endpoint_family"]=f"{row_holm[total_written]:.17g}"
                    writer.writerow(row)
                    if row["split"]=="blind_oos":
                        compact={k:row[k] for k in ("formula_id","features","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_rank_of_actual_numbers","holm_p_max_endpoint_family")}
                        top_rank.append(compact); top_rank=sorted(top_rank,key=lambda x:(float(x["mean_rank_of_actual_numbers"]),-float(x["mean_number_hits_top5"])))[:10]
                        top_top5.append(compact); top_top5=sorted(top_top5,key=lambda x:(-float(x["mean_number_hits_top5"]),float(x["mean_rank_of_actual_numbers"])))[:10]
                    part_rows+=1; total_written+=1
    finally:
        if part_handle: part_handle.close()
    if total_written!=total_rows: fail("written metric rows do not match declared total")
    cursor=0
    for i in range(part_index+1):
        p=OUT/f"per_number_condition_7plus_formula_metrics_part_{i:02d}.csv.gz"
        # Count rows without loading the decompressed file into memory.
        with gzip.open(p,"rt",newline="",encoding="utf-8") as h:
            count=sum(1 for _ in h)-1
        raw=p.read_bytes()
        part_manifest.append({"part_index":i,"path":str(p.relative_to(ROOT)),"rows":count,
            "row_start_inclusive":cursor,"row_end_exclusive":cursor+count,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
        cursor+=count
    # Merge the six local per-target winners into one globally best descriptive formula per target.
    best_by_date={}
    for shard in range(SHARDS):
        path=SHARD_DIR/f"shard_{shard}_target_ledger.csv"
        if not path.is_file(): fail(f"missing target ledger for shard {shard}")
        with path.open(newline="",encoding="utf-8-sig") as h:
            for row in csv.DictReader(h):
                d=row["target_date"]
                if d not in dates: fail("target ledger date not found in canonical archive")
                ix=date_index[d]
                if row["cutoff_date"]!=dates[ix-1] or int(row["prior_draws"])!=ix: fail("target ledger prior cutoff mismatch")
                actual=" ".join(map(str,draws[ix]))
                if row["actual_quintet"]!=actual: fail("target ledger actual quintet mismatch")
                key=(int(row["best_rank_sum"]),int(row["best_number_hits_top20"]),-int(row["best_number_hits_top5"]),row["best_formula_id"])
                old=best_by_date.get(d)
                if old is None or key<(old[0]): best_by_date[d]=(key,row)
    if len(best_by_date)!=scored: fail("global target ledger coverage mismatch")
    with LEDGER_PATH.open("w",newline="",encoding="utf-8") as h:
        ledgers=[v[1] for v in best_by_date.values()]
        fields=list(ledgers[0].keys())
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for d in dates[q80.MIN_HISTORY:]:
            row=dict(best_by_date[d][1]); row["formula_count_tested"]=TOTAL; w.writerow(row)
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    formulas=list(itertools.combinations(range(27),7))
    batches=[]
    for i,start in enumerate(range(0,TOTAL,1024)):
        end=min(start+1024,TOTAL)
        batches.append({"batch_index":i,"formula_start_inclusive":start,"formula_end_exclusive":end,
            "formula_count":end-start,"formula_id_first":formula_id(formulas[start]),"formula_id_last":formula_id(formulas[end-1])})
    report={"schema_version":"1.0","task_id":"Q87","status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":source_sha,"target_count":len(draws),"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":q80.MIN_HISTORY,"scored_targets":scored,"feature_count":27,"features":FEATURES,
        "formula_count":TOTAL,"formula_count_check":math.comb(27,7),"formula_batch_size":1024,
        "formula_batch_count":len(batches),"batch_manifest":batches,"shard_count":SHARDS,"shard_formula_count":SHARD_SIZE,
        "formula_grammar":"all 7-feature equal-weight combinations",
        "scoring_rule":"per target, z-score each of 27 features over numbers 1..40, then average each unordered seven-feature subset",
        "metrics_storage":"chunked_csv_gzip_parts","metrics_rows":total_rows,"target_ledger_rows":scored,
        "metrics_parts":part_manifest,"metrics_manifest":"reports/sequence_agent/per_number_condition_7plus_formula_metrics_manifest.json",
        "split_counts":expected_split,"uniform_number_rank_baseline":{"mean_number_hits_top5":.125,"mean_number_hits_top10":.25,"mean_number_hits_top20":.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":tests,"p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test"},
        "holm_adjusted_formula_split_rows_below_0_05":int(np.sum(row_holm<.05)),
        "minimum_holm_p_max_endpoint_family":float(np.min(row_holm)),
        "best_blind_oos_by_mean_rank":top_rank,"best_blind_oos_by_mean_top5_hits":top_top5,
        "guardrails":["strict prior-only features; target draw excluded","all 40 numbers ranked before target scoring",
            "best-per-target formula is retrospective/descriptive, not a prospective forecast",
            "global Holm applied across all six shards and all formula×split×endpoint tests",
            "finite seven-feature grammar only; higher-order and conditional formula families remain open",
            "immutable freezes preserved; no automatic strategy promotion"],
        "outputs":{"metrics_parts":[x["path"] for x in part_manifest],
            "metrics_parts_manifest_sha256":hashlib.sha256(json.dumps(part_manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
            "metrics_manifest":str(METRICS_MANIFEST.relative_to(ROOT)),
            "target_ledger":str(LEDGER_PATH.relative_to(ROOT))}}
    manifest={"schema_version":"1.0","task_id":"Q87","storage_format":"chunked_csv_gzip_parts",
        "source_archive_sha256":source_sha,"formula_count":TOTAL,"metrics_rows":total_rows,
        "part_count":len(part_manifest),"parts_manifest_sha256":hashlib.sha256(json.dumps(part_manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest(),"parts":part_manifest}
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    METRICS_MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SONAR_Q87_AGGREGATE_BEGIN"); print(json.dumps({k:report[k] for k in ("task_id","status","target_count","last_date","scored_targets","formula_count","metrics_rows","target_ledger_rows","multiple_testing","holm_adjusted_formula_split_rows_below_0_05","minimum_holm_p_max_endpoint_family","best_blind_oos_by_mean_rank","best_blind_oos_by_mean_top5_hits")},ensure_ascii=False,separators=(",",":"))); print("SONAR_Q87_AGGREGATE_END")

if __name__=="__main__": main()
