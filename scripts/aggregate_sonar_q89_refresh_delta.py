#!/usr/bin/env python3
"""Exact additive refresh of the Q89 nine-feature catalog for the 2026-11-08 archive."""
from __future__ import annotations
import csv, gzip, hashlib, heapq, json, math
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_q89_common as q89

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
ARCHIVE=ROOT/"data/storico_daily.csv"
BASE_REPORT_PATH=OUT/"per_number_condition_9plus_grammar.json"
BASE_MANIFEST_PATH=OUT/"per_number_condition_9plus_formula_metrics_manifest.json"
DELTA_DIR=OUT/"q89_refresh_20261108_delta_shards"
REPORT_PATH=OUT/"q89_refresh_20261108_report.json"
MANIFEST_PATH=OUT/"q89_refresh_20261108_manifest.json"
LEDGER_PATH=OUT/"q89_refresh_20261108_target_delta_ledger.csv"
SHORTLIST_PATH=OUT/"q89_refresh_20261108_candidate_shortlist.csv"
SELECTION_PATH=OUT/"q89_refresh_20261108_candidate_selection.json"
SPLITS=("discovery","validation","blind_oos")
OLD_SPLIT_COUNTS={"discovery":2011,"validation":670,"blind_oos":670}
NEW_SPLIT_COUNTS={"discovery":2012,"validation":670,"blind_oos":670}
TARGET_OFFSETS=(2011,2681,3351)
METRIC_NAMES=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")
ENDPOINTS=(5,10,20)
TOTAL=q89.TOTAL_FORMULA_COUNT
SHARDS=q89.SHARD_COUNT
SHARD_SIZE=q89.SHARD_SIZE
EXPECTED_BASE_SHA1="5d2efd70684e918b27d8f06386d545647898336d"
EXPECTED_BASE_SHA256="3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed"
EXPECTED_NEW_SHA1="77ca692a6082809fcc6c471501617433ec7c36cf"
EXPECTED_NEW_COMMIT="6cca9022d4311a3f9aba2925fce8c653dc6b63ab"
EXPECTED_NEW_COUNT=3402
EXPECTED_NEW_LAST_DATE="2026-11-08"
METRIC_COLUMNS=[f"o{offset}_{metric}" for offset in TARGET_OFFSETS for metric in METRIC_NAMES]

def fail(message):
    raise SystemExit("Q89_REFRESH_AGGREGATION_BLOCKED: "+message)

def git_blob_sha1(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def integer_from_mean(value,denominator,label):
    raw=float(value)*int(denominator)
    rounded=int(round(raw))
    if not math.isfinite(raw) or abs(raw-rounded)>2e-6:
        fail(label+" cannot be reconstructed as an exact integer count")
    return rounded

def adjust_split_counts(old_counts,delta_counts,split):
    if split=="discovery":
        return {name:int(old_counts[name])+int(delta_counts[2011][name]) for name in METRIC_NAMES}
    if split=="validation":
        return {name:int(old_counts[name])-int(delta_counts[2011][name])+int(delta_counts[2681][name]) for name in METRIC_NAMES}
    if split=="blind_oos":
        return {name:int(old_counts[name])-int(delta_counts[2681][name])+int(delta_counts[3351][name]) for name in METRIC_NAMES}
    raise ValueError("unknown split "+str(split))

def metrics_from_counts(counts,targets):
    targets=int(targets)
    return {
        "mean_number_hits_top5":counts["number_hits_top5"]/(5*targets),
        "mean_number_hits_top10":counts["number_hits_top10"]/(5*targets),
        "mean_number_hits_top20":counts["number_hits_top20"]/(5*targets),
        "all5_top5_rate":counts["all5_top5"]/targets,
        "all5_top10_rate":counts["all5_top10"]/targets,
        "all5_top20_rate":counts["all5_top20"]/targets,
        "mean_rank_of_actual_numbers":counts["rank_sum"]/(5*targets),
    }

def load_delta_shard(shard):
    start,end=q89.shard_bounds(shard)
    path=DELTA_DIR/f"shard_{shard}_delta_metrics.csv.gz"
    if not path.is_file():
        fail("missing delta shard "+str(path))
    arrays=np.empty((SHARD_SIZE,len(METRIC_COLUMNS)),dtype=np.int16)
    formula_ids=[]
    expected=q89.iter_formula_slice(start,end)
    with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        required={"formula_rank","formula_id",*METRIC_COLUMNS}
        if not required.issubset(set(reader.fieldnames or [])):
            fail("delta shard schema incomplete for shard "+str(shard))
        count=0
        for row in reader:
            if count>=SHARD_SIZE:
                fail("delta shard has extra rows")
            columns=next(expected,None)
            if columns is None:
                fail("expected formula iterator ended early")
            expected_id=q89.formula_id(columns)
            if int(row["formula_rank"])!=start+count or row["formula_id"]!=expected_id:
                fail("delta formula rank/id coverage mismatch at shard "+str(shard)+" local "+str(count))
            formula_ids.append(expected_id)
            for column,name in enumerate(METRIC_COLUMNS):
                value=int(row[name])
                if name.endswith("number_hits_top5") or name.endswith("number_hits_top10") or name.endswith("number_hits_top20"):
                    if not 0<=value<=5: fail("delta number-hit count outside 0..5")
                elif name.endswith("all5_top5") or name.endswith("all5_top10") or name.endswith("all5_top20"):
                    if not 0<=value<=1: fail("delta all-five indicator outside 0..1")
                elif name.endswith("rank_sum"):
                    if not 5<=value<=200: fail("delta rank sum outside 5..200")
                arrays[count,column]=value
            count+=1
    if count!=SHARD_SIZE or len(formula_ids)!=SHARD_SIZE or next(expected,None) is not None:
        fail("delta shard exact row count/formula coverage mismatch for shard "+str(shard))
    return arrays,formula_ids

def read_archive():
    raw=ARCHIVE.read_bytes()
    if git_blob_sha1(raw)!=EXPECTED_NEW_SHA1:
        fail("canonical 2026-11-08 archive Git blob SHA1 mismatch")
    with ARCHIVE.open(newline="",encoding="utf-8-sig") as handle:
        rows=list(csv.DictReader(handle))
    dates=[row["data"] for row in rows]
    if len(rows)!=EXPECTED_NEW_COUNT or dates[0]!="2017-07-17" or dates[-1]!=EXPECTED_NEW_LAST_DATE or dates!=sorted(dates) or len(dates)!=len(set(dates)):
        fail("canonical archive dimensions/date sequence mismatch")
    draws=[]
    for row in rows:
        values=[int(row[f"n{i}"]) for i in range(1,6)]
        if values!=sorted(values) or len(set(values))!=5 or any(value<1 or value>40 for value in values):
            fail("canonical archive quintet invalid")
        draws.append(values)
    return dates,draws,hashlib.sha256(raw).hexdigest(),git_blob_sha1(raw)

def build_target_delta_ledger(dates,draws):
    expected=[
        (2011,2061,"2023-03-09","2023-03-08","5 19 32 33 37","old_validation_to_new_discovery"),
        (2681,2731,"2025-01-07","2025-01-06","5 17 18 23 33","old_blind_to_new_validation"),
        (3351,3401,"2026-11-08","2026-11-07","3 7 10 16 27","new_target_in_new_blind_oos"),
    ]
    rows=[]
    for offset,index,target_date,cutoff,actual,movement in expected:
        if dates[index]!=target_date or dates[index-1]!=cutoff or " ".join(map(str,draws[index]))!=actual or index!=q80.MIN_HISTORY+offset:
            fail("preregistered target offset/date/cutoff/quintet mismatch")
        rows.append({"target_offset":offset,"archive_index":index,"target_date":target_date,"cutoff_date":cutoff,
            "prior_draws":index,"actual_quintet":actual,"split_movement":movement})
    return rows

def invert_id(fid):
    return bytes(255-ord(character) for character in fid)

def holm_adjust_global(pvalues):
    values=np.asarray(pvalues,dtype=np.float64)
    tests=len(values)
    order=np.argsort(values,kind="stable")
    sorted_adjusted=np.maximum.accumulate((tests-np.arange(tests,dtype=np.int64))*values[order])
    np.minimum(sorted_adjusted,1.0,out=sorted_adjusted)
    adjusted=np.empty_like(values)
    adjusted[order]=sorted_adjusted
    return adjusted

def main():
    dates,draws,new_sha256,new_blob_sha1=read_archive()
    scored=len(draws)-q80.MIN_HISTORY
    if scored!=3352 or NEW_SPLIT_COUNTS!={"discovery":2012,"validation":670,"blind_oos":670}:
        fail("new strict-prefix target/split counts mismatch")
    base_report=json.loads(BASE_REPORT_PATH.read_text(encoding="utf-8"))
    base_manifest=json.loads(BASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    base_archive=ROOT/"data/archive_freezes/storico_daily_2026-11-07.csv"
    if not base_archive.is_file():
        fail("immutable Q89 base archive freeze missing")
    base_bytes=base_archive.read_bytes()
    if git_blob_sha1(base_bytes)!=EXPECTED_BASE_SHA1 or hashlib.sha256(base_bytes).hexdigest()!=EXPECTED_BASE_SHA256:
        fail("immutable Q89 base archive freeze SHA mismatch")
    if base_report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or base_report.get("source_archive_sha256")!=EXPECTED_BASE_SHA256:
        fail("Q89 base report is not accepted or does not match the frozen archive")
    if base_report.get("formula_count")!=TOTAL or base_report.get("metrics_rows")!=TOTAL*3 or base_report.get("split_counts")!=OLD_SPLIT_COUNTS:
        fail("Q89 base report dimensions/splits mismatch")
    if base_manifest.get("task_id")!="Q89" or base_manifest.get("source_archive_sha256")!=EXPECTED_BASE_SHA256 or base_manifest.get("metrics_rows")!=TOTAL*3:
        fail("Q89 base metrics manifest identity/dimensions mismatch")
    parts=base_manifest.get("parts",[])
    if len(parts)!=469 or parts!=base_report.get("metrics_parts"):
        fail("Q89 base metrics manifest/report parts do not reconcile")
    for part in parts:
        path=ROOT/part["path"]
        if not path.is_file():
            fail("Q89 base metrics part missing "+part["path"])
        raw=path.read_bytes()
        if len(raw)!=int(part["bytes"]) or hashlib.sha256(raw).hexdigest()!=part["sha256"]:
            fail("Q89 base metrics part SHA/byte mismatch "+part["path"])
    target_ledger=build_target_delta_ledger(dates,draws)
    with LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(target_ledger[0].keys()),lineterminator="\n")
        writer.writeheader();writer.writerows(target_ledger)

    tests=TOTAL*3*3
    pvalues=np.empty(tests,dtype=np.float64)
    candidate_pool=[]
    current_shard=-1
    delta_arrays=None
    delta_ids=None
    local_heap=[]
    local_candidates=None
    local_candidate_map={}
    row_cursor=0
    split_counts={split:0 for split in SPLITS}
    old_split_index={name:index for index,name in enumerate(SPLITS)}
    for part in parts:
        path=ROOT/part["path"]
        with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            for row in reader:
                global_row=row_cursor
                shard=global_row//(SHARD_SIZE*3)
                within=global_row%(SHARD_SIZE*3)
                split_index=within//SHARD_SIZE
                local_rank=within%SHARD_SIZE
                split=SPLITS[split_index]
                formula_rank=shard*SHARD_SIZE+local_rank
                if shard!=current_shard:
                    if current_shard>=0:
                        if local_candidates is None or len(local_candidate_map)!=100:
                            fail("local Discovery top100 candidate set incomplete at shard boundary")
                        for fid,item in local_candidate_map.items():
                            if "validation" not in item or "blind" not in item:
                                fail("local Discovery top100 candidate lacks Validation/Blind metric replay")
                            candidate_pool.append(item)
                    current_shard=shard
                    delta_arrays,delta_ids=load_delta_shard(shard)
                    local_heap=[]
                    local_candidates=None
                    local_candidate_map={}
                if row.get("split")!=split or int(row.get("targets",-1))!=OLD_SPLIT_COUNTS[split] or row.get("formula_id")!=delta_ids[local_rank]:
                    fail("base Q89 metric row order/split/formula does not reconcile at row "+str(global_row))
                fid=row["formula_id"]
                features=row["features"]
                if int(row.get("feature_count",-1))!=9:
                    fail("base Q89 metric feature_count mismatch")
                old_targets=OLD_SPLIT_COUNTS[split]
                old_counts={
                    "number_hits_top5":integer_from_mean(row["mean_number_hits_top5"],5*old_targets,"old Top5"),
                    "number_hits_top10":integer_from_mean(row["mean_number_hits_top10"],5*old_targets,"old Top10"),
                    "number_hits_top20":integer_from_mean(row["mean_number_hits_top20"],5*old_targets,"old Top20"),
                    "all5_top5":integer_from_mean(row["all5_top5_rate"],old_targets,"old all5 Top5"),
                    "all5_top10":integer_from_mean(row["all5_top10_rate"],old_targets,"old all5 Top10"),
                    "all5_top20":integer_from_mean(row["all5_top20_rate"],old_targets,"old all5 Top20"),
                    "rank_sum":integer_from_mean(row["mean_rank_of_actual_numbers"],5*old_targets,"old rank sum"),
                }
                delta_counts={}
                for offset_index,offset in enumerate(TARGET_OFFSETS):
                    delta_counts[offset]={name:int(delta_arrays[local_rank,offset_index*len(METRIC_NAMES)+metric_index]) for metric_index,name in enumerate(METRIC_NAMES)}
                counts=adjust_split_counts(old_counts,delta_counts,split)
                new_targets=NEW_SPLIT_COUNTS[split]
                if not 0<=counts["number_hits_top5"]<=5*new_targets or not 0<=counts["number_hits_top10"]<=5*new_targets or not 0<=counts["number_hits_top20"]<=5*new_targets:
                    fail("refreshed number-hit count outside split bounds")
                if not 0<=counts["all5_top5"]<=new_targets or not 0<=counts["all5_top10"]<=new_targets or not 0<=counts["all5_top20"]<=new_targets:
                    fail("refreshed all-five count outside split bounds")
                if not 5*new_targets<=counts["rank_sum"]<=200*new_targets:
                    fail("refreshed rank sum outside split bounds")
                metrics=metrics_from_counts(counts,new_targets)
                for endpoint_index,k in enumerate(ENDPOINTS):
                    pvalues[global_row*3+endpoint_index]=q89.hypergeom_upper_normal_p(counts[f"number_hits_top{k}"],new_targets,k)
                if split_index==0:
                    score=metrics["mean_number_hits_top5"]
                    mean_rank=metrics["mean_rank_of_actual_numbers"]
                    key=(score,-mean_rank,invert_id(fid))
                    entry=(key,fid,score,mean_rank,features,formula_rank,metrics)
                    if len(local_heap)<100:
                        heapq.heappush(local_heap,entry)
                    elif key>local_heap[0][0]:
                        heapq.heapreplace(local_heap,entry)
                elif split_index==1:
                    if local_candidates is None:
                        if len(local_heap)!=100:
                            fail("Discovery did not produce 100 local candidates")
                        ordered=sorted(local_heap,key=lambda entry:(-entry[2],entry[3],entry[1]))
                        local_candidates=ordered
                        local_candidate_map={entry[1]:{"formula_id":entry[1],"features":entry[4],"formula_rank":entry[5],
                            "discovery_mean_number_hits_top5":entry[2],"discovery_mean_rank_of_actual_numbers":entry[3],
                            "discovery_local_rank":rank+1,"discovery":entry[6]} for rank,entry in enumerate(ordered)}
                    item=local_candidate_map.get(fid)
                    if item is not None:
                        item["validation"]=metrics
                else:
                    item=local_candidate_map.get(fid)
                    if item is not None:
                        item["blind"]=metrics
                split_counts[split]+=1
                row_cursor+=1
    if current_shard!=SHARDS-1 or row_cursor!=TOTAL*3 or split_counts!={split:TOTAL for split in SPLITS}:
        fail("base Q89 metrics row/formula/split coverage mismatch")
    if local_candidates is None or len(local_candidate_map)!=100:
        fail("last shard local candidate set incomplete")
    for fid,item in local_candidate_map.items():
        if "validation" not in item or "blind" not in item:
            fail("last shard Discovery top100 candidate lacks Validation/Blind metrics")
        candidate_pool.append(item)
    if len(candidate_pool)!=SHARDS*100:
        fail("local top100 candidate pool must contain 1,500 unique candidates")
    if len({item["formula_id"] for item in candidate_pool})!=len(candidate_pool):
        fail("local top100 candidates contain duplicate formula IDs")

    adjusted=holm_adjust_global(pvalues)
    row_holm=adjusted.reshape(TOTAL*3,3).max(axis=1)
    holm_below=int(np.sum(row_holm<0.05))
    minimum_holm=float(np.min(row_holm))
    global_top100=sorted(candidate_pool,key=lambda item:(-item["discovery_mean_number_hits_top5"],item["discovery_mean_rank_of_actual_numbers"],item["formula_id"]))[:100]
    if len(global_top100)!=100:
        fail("global Discovery shortlist does not contain 100 candidates")
    validation_order=sorted(global_top100,key=lambda item:(-item["validation"]["mean_number_hits_top5"],item["validation"]["mean_rank_of_actual_numbers"],item["formula_id"]))
    selected=validation_order[0]
    selection_rank={item["formula_id"]:rank+1 for rank,item in enumerate(validation_order)}
    shortlist=[]
    for discovery_rank,item in enumerate(global_top100,start=1):
        shortlist.append({"formula_id":item["formula_id"],"features":item["features"],"discovery_rank":discovery_rank,
            "discovery_mean_number_hits_top5":item["discovery_mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":item["discovery_mean_rank_of_actual_numbers"],
            "validation_mean_number_hits_top5":item["validation"]["mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":item["validation"]["mean_rank_of_actual_numbers"],
            "validation_selection_rank":selection_rank[item["formula_id"]],"selected":int(item["formula_id"]==selected["formula_id"])})
    with SHORTLIST_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(shortlist[0].keys()),lineterminator="\n")
        writer.writeheader();writer.writerows(shortlist)
    selection={
        "schema_version":"1.0","task_id":"Q89_REFRESH_2026_11_08","protocol_id":"Q89-nine-feature-incremental-refresh-2026-11-08",
        "status":"CANDIDATE_FROZEN_BEFORE_BLIND_OOS","blind_oos_used_for_selection":False,
        "selection_rule":"Discovery global top100 by mean Top-5 hit share, tie-break lower mean rank then lexicographic formula_id; select one on Validation with the same tie-break.",
        "candidate_universe_size":TOTAL,"discovery_local_shortlist_pool_size":SHARDS*100,
        "top100_discovery_candidates":[item["formula_id"] for item in global_top100],
        "selected_candidate_ids_frozen":True,
        "Q89_candidate":{"formula_id":selected["formula_id"],"features":selected["features"],"formula_rank":selected["formula_rank"],
            "discovery_rank":next(row["discovery_rank"] for row in shortlist if row["formula_id"]==selected["formula_id"]),
            "discovery_mean_number_hits_top5":selected["discovery_mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":selected["discovery_mean_rank_of_actual_numbers"],"discovery_metrics":selected["discovery"],
            "validation_mean_number_hits_top5":selected["validation"]["mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":selected["validation"]["mean_rank_of_actual_numbers"],
            "validation_selection_rank":selection_rank[selected["formula_id"]],
            "blind_oos_metrics_descriptive_only":selected["blind"]},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5}}
    SELECTION_PATH.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest_parts=[]
    for shard in range(SHARDS):
        path=DELTA_DIR/f"shard_{shard}_delta_metrics.csv.gz"
        raw=path.read_bytes()
        start,end=q89.shard_bounds(shard)
        manifest_parts.append({"shard_index":shard,"path":str(path.relative_to(ROOT)),"rows":SHARD_SIZE,
            "formula_rank_start_inclusive":start,"formula_rank_end_exclusive":end,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    manifest={"schema_version":"1.0","task_id":"Q89_REFRESH_2026_11_08","protocol_id":"Q89-nine-feature-incremental-refresh-2026-11-08",
        "status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION","source_archive_sha256":new_sha256,"source_archive_git_blob_sha1":new_blob_sha1,
        "formula_count":TOTAL,"metrics_rows":TOTAL,"shard_count":SHARDS,"rows_per_shard":SHARD_SIZE,
        "formula_rank_coverage":"0..4686824 exactly once","target_offsets":list(TARGET_OFFSETS),"metric_names":list(METRIC_NAMES),
        "parts":manifest_parts,"part_count":len(manifest_parts)}
    MANIFEST_PATH.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report={"schema_version":"1.0","task_id":"Q89_REFRESH_2026_11_08","status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","protocol_id":"Q89-nine-feature-incremental-refresh-2026-11-08",
        "source_archive":"data/storico_daily.csv","source_archive_sha256":new_sha256,"source_archive_git_blob_sha1":new_blob_sha1,
        "source_archive_main_commit":EXPECTED_NEW_COMMIT,"target_count":len(draws),"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":q80.MIN_HISTORY,"scored_targets":scored,"feature_count":27,"formula_size":9,"formula_count":TOTAL,
        "shard_count":SHARDS,"shard_formula_count":SHARD_SIZE,"metrics_rows":TOTAL,"delta_shard_rows":TOTAL,
        "old_split_counts":OLD_SPLIT_COUNTS,"split_counts":NEW_SPLIT_COUNTS,
        "target_delta_ledger_rows":len(target_ledger),"target_delta_ledger":target_ledger,
        "multiple_testing":{"method":"Global Holm-Bonferroni","test_count":tests,"formula_split_endpoint_family_size":tests,
            "p_value_method":"continuity-corrected normal approximation to summed Hypergeometric(40,k,5) number-hit counts; exploratory, not exact",
            "holm_adjusted_formula_split_rows_below_0_05":holm_below,"minimum_holm_p_max_endpoint_family":minimum_holm},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "candidate_selection":{"rule":selection["selection_rule"],"blind_oos_used_for_selection":False,"selected_candidate_id":selected["formula_id"],
            "discovery_top100_count":100,"validation_candidates":100,"blind_oos_targets":670},
        "selected_candidate_metrics":{"discovery":selected["discovery"],
            "validation":selected["validation"],"blind_oos_descriptive_only":selected["blind"]},
        "outputs":{"delta_shards":[item["path"] for item in manifest_parts],"target_delta_ledger":str(LEDGER_PATH.relative_to(ROOT)),
            "candidate_shortlist":str(SHORTLIST_PATH.relative_to(ROOT)),"candidate_selection":str(SELECTION_PATH.relative_to(ROOT)),
            "manifest":str(MANIFEST_PATH.relative_to(ROOT))},
        "guardrails":["Q89 base catalog was accepted on the 2026-11-07 frozen archive; only three preregistered target deltas are rescored",
            "all three target feature states use strict prior draws only; target outcomes enter only additive metrics",
            "Discovery top100 and Validation selection freeze the candidate before Blind OOS metrics are reported",
            "global Holm covers all 4,686,825 formulas × 3 splits × 3 endpoints; raw p-values are exploratory normal approximations",
            "historical Blind OOS is not independent prospective confirmation; no automatic promotion or shadow insertion"],
        "limitations":["exact incremental refresh depends on accepted Q89 base metrics and immutable 2026-11-07 archive freeze",
            "formula-family p-values use a finite-population normal approximation and are exploratory",
            "finite equal-weight nine-feature grammar only; Q92 ten-feature catalog remains a separate preregistered extension"],
        "next_action":"Freeze the refreshed Q89 candidate as the same-archive Q92 control only after acceptance, append-only persistence, exact-byte readback and current-head CI; then implement/execute Q92 under its preregistered gate."}
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={key:report[key] for key in ("task_id","status","source_archive_sha256","target_count","scored_targets","formula_count","metrics_rows","split_counts","multiple_testing","candidate_selection")}
    print("SONAR_Q89_REFRESH_AGGREGATE_BEGIN")
    print(json.dumps(summary,ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q89_REFRESH_AGGREGATE_END")

if __name__=="__main__":
    main()
