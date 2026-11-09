#!/usr/bin/env python3
"""Fail-closed acceptance replay for the Q92 2026-11-08 ten-feature walk-forward."""
from __future__ import annotations
import csv,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_q92_common as q92
import sonar_q92_aggregate_common as q92a
import aggregate_sonar_q92_ten_feature as aggregate

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
ARCHIVE=ROOT/"data/storico_daily.csv"
REPORT_PATH=OUT/"q92_20261108_report.json"
MANIFEST_PATH=OUT/"q92_20261108_manifest.json"
SHORTLIST_PATH=OUT/"q92_20261108_candidate_shortlist.csv"
SELECTION_PATH=OUT/"q92_20261108_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q92_20261108_paired_blind_ledger.csv"
INFERENCE_PATH=OUT/"q92_20261108_paired_inference.json"
METRICS_PART_DIR=OUT/"q92_20261108_metrics_parts"
TARGET_PART_DIR=OUT/"q92_20261108_target_ledger_parts"
SPLITS=("discovery","validation","blind_oos")
SPLIT_COUNTS={"discovery":2012,"validation":670,"blind_oos":670}
TOTAL=q92.TOTAL_FORMULA_COUNT
SHARDS=q92.SHARD_COUNT
SHARD_SIZE=q92.SHARD_SIZE
EXPECTED_TESTS=TOTAL*3*3
ENDPOINTS=(5,10,20)
METRIC_FIELDS=("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
    "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers",
    "p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx")

def fail(message):
    raise SystemExit("Q92_ACCEPTANCE_BLOCKED: "+str(message))

def read_json(path):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:fail("required JSON unreadable "+str(path)+": "+str(exc))

def read_csv_fields_rows(path):
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle);fields=reader.fieldnames;rows=list(reader)
    return fields,rows

def sha256_file(path):
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1<<20),b""):digest.update(block)
    return digest.hexdigest()

def compare_float(actual,expected,label,tolerance=1e-12):
    try:a=float(actual);e=float(expected)
    except Exception:fail(label+" numeric conversion failed")
    if not math.isfinite(a) or not math.isfinite(e) or abs(a-e)>tolerance:
        fail(label+" mismatch: observed="+repr(a)+" expected="+repr(e))

def compare_json_numeric(observed,expected,label,tolerance=1e-12):
    if isinstance(expected,dict):
        if not isinstance(observed,dict) or set(observed)!=set(expected):
            fail(label+" JSON object keys mismatch")
        for key in expected:compare_json_numeric(observed[key],expected[key],label+"/"+str(key),tolerance)
    elif isinstance(expected,list):
        if not isinstance(observed,list) or len(observed)!=len(expected):fail(label+" JSON list length mismatch")
        for index,(left,right) in enumerate(zip(observed,expected)):compare_json_numeric(left,right,label+"/"+str(index),tolerance)
    elif isinstance(expected,(int,float)) and not isinstance(expected,bool):
        compare_float(observed,expected,label,tolerance)
    else:
        if observed!=expected:fail(label+" value mismatch")

def validate_q89_control(archive_sha256,dates,draws,feature_stack):
    report,selection,paired,q89_id,q89_columns=aggregate.validate_q89_control(archive_sha256,dates,draws,feature_stack)
    return report,selection,paired,q89_id,q89_columns

def validate_metric_parts(archive_sha256,dates,draws,feature_stack,manifest,selection):
    parts=manifest.get("metrics_parts",[])
    if len(parts)!=SHARDS or manifest.get("metrics_part_count")!=SHARDS:
        fail("Q92 metric parts manifest count mismatch")
    raw_path=OUT/"q92_20261108_acceptance_raw_pvalues_temp.bin"
    adjusted_path=OUT/"q92_20261108_acceptance_adjusted_pvalues_temp.bin"
    for path in (raw_path,adjusted_path):
        if path.exists():path.unlink()
    raw=np.memmap(raw_path,dtype=np.float64,mode="w+",shape=(EXPECTED_TESTS,))
    adjusted=np.memmap(adjusted_path,dtype=np.float64,mode="w+",shape=(EXPECTED_TESTS,))
    candidate_pool=[]
    global_metric_row=0
    split_rows={split:0 for split in SPLITS}
    for shard,part in enumerate(parts):
        start,end=q92.shard_bounds(shard)
        expected_part_path=METRICS_PART_DIR/f"shard_{shard}_metrics.csv.gz"
        if part.get("shard_index")!=shard or part.get("path")!=str(expected_part_path.relative_to(ROOT)) or part.get("rows")!=SHARD_SIZE*3:
            fail("Q92 metric part manifest identity/count mismatch shard "+str(shard))
        if part.get("formula_rank_start_inclusive")!=start or part.get("formula_rank_end_exclusive")!=end:
            fail("Q92 metric part formula rank interval mismatch shard "+str(shard))
        if not expected_part_path.is_file() or expected_part_path.stat().st_size!=int(part.get("bytes",-1)) or sha256_file(expected_part_path)!=part.get("sha256"):
            fail("Q92 metric part byte/SHA mismatch shard "+str(shard))
        raw_source=aggregate.SHARD_INPUT_DIR/f"shard_{shard}_metrics.csv"
        if raw_source.is_file() and sha256_file(raw_source)!=part.get("source_artifact_sha256"):
            fail("Q92 metric part source artifact SHA mismatch shard "+str(shard))
        local_heap=[]
        local_candidate_map=None
        expected_formula_iter=None
        previous_split=-1
        local_row=0
        with gzip.open(expected_part_path,"rt",newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            required={"split","formula_id","feature_count","features","targets","formula_rank",
                "holm_p_top5","holm_p_top10","holm_p_top20","holm_p_max_endpoint_family",*METRIC_FIELDS}
            if not required.issubset(set(reader.fieldnames or [])):
                fail("Q92 adjusted metric part schema incomplete shard "+str(shard))
            for row in reader:
                if local_row>=SHARD_SIZE*3:fail("Q92 adjusted metric part has extra rows shard "+str(shard))
                split_index=local_row//SHARD_SIZE
                local_rank=local_row%SHARD_SIZE
                split=SPLITS[split_index]
                if split_index!=previous_split:
                    expected_formula_iter=q92.iter_formula_slice(start,end)
                    previous_split=split_index
                    if split_index==1:
                        if len(local_heap)!=100:fail("Q92 acceptance local Discovery top100 incomplete shard "+str(shard))
                        ordered=sorted(local_heap,key=lambda entry:(-entry[2],entry[3],entry[1]))
                        local_candidate_map={entry[1]:{"formula_id":entry[1],"features":entry[4],"formula_rank":entry[5],
                            "mean_number_hits_top5":entry[2],"mean_rank_of_actual_numbers":entry[3],
                            "discovery_local_rank":rank+1,"discovery":entry[6]} for rank,entry in enumerate(ordered)}
                        local_heap=[]
                    elif split_index==2 and (local_candidate_map is None or len(local_candidate_map)!=100):
                        fail("Q92 acceptance local candidate map missing shard "+str(shard))
                columns=next(expected_formula_iter,None)
                if columns is None:fail("Q92 acceptance expected formula iterator ended early shard "+str(shard))
                expected_id=q92.formula_id(columns)
                fid=row.get("formula_id","")
                if row.get("split")!=split or int(row.get("targets",-1))!=SPLIT_COUNTS[split] or int(row.get("feature_count",-1))!=10 or fid!=expected_id:
                    fail("Q92 adjusted metric formula/split/order mismatch shard "+str(shard)+" local row "+str(local_row))
                if int(row.get("formula_rank",-1))!=start+local_rank:
                    fail("Q92 adjusted metric formula rank mismatch shard "+str(shard)+" local row "+str(local_row))
                expected_features="+".join(q80.FEATURE_NAMES[column] for column in columns)
                if row.get("features")!=expected_features:fail("Q92 adjusted metric feature string mismatch shard "+str(shard)+" formula "+fid)
                targets=SPLIT_COUNTS[split]
                s5=aggregate.integer_from_mean(row["mean_number_hits_top5"],5*targets,"Q92 Top5")
                s10=aggregate.integer_from_mean(row["mean_number_hits_top10"],5*targets,"Q92 Top10")
                s20=aggregate.integer_from_mean(row["mean_number_hits_top20"],5*targets,"Q92 Top20")
                raw_p=[q92.hypergeom_upper_normal_p(s5,targets,5),q92.hypergeom_upper_normal_p(s10,targets,10),q92.hypergeom_upper_normal_p(s20,targets,20)]
                adjusted_p=[float(row["holm_p_top5"]),float(row["holm_p_top10"]),float(row["holm_p_top20"])]
                for endpoint_index,p in enumerate(raw_p):
                    compare_float(row[("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx")[endpoint_index]],p,
                        "Q92 raw p-value replay shard "+str(shard)+" formula "+fid+" split "+split)
                    if not 0.0<=adjusted_p[endpoint_index]<=1.0 or not math.isfinite(adjusted_p[endpoint_index]):
                        fail("Q92 adjusted p-value outside bounds shard "+str(shard)+" formula "+fid)
                    raw[global_metric_row*3+endpoint_index]=p
                    adjusted[global_metric_row*3+endpoint_index]=adjusted_p[endpoint_index]
                compare_float(row["holm_p_max_endpoint_family"],max(adjusted_p),"Q92 row max Holm shard "+str(shard)+" formula "+fid)
                if split_index==0:
                    summary=aggregate.metric_summary(row)
                    score=summary["mean_number_hits_top5"];mean_rank=summary["mean_rank_of_actual_numbers"]
                    key=(score,-mean_rank,aggregate.invert_id(fid))
                    entry=(key,fid,score,mean_rank,expected_features,start+local_rank,summary)
                    if len(local_heap)<100:heapq.heappush(local_heap,entry)
                    elif key>local_heap[0][0]:heapq.heapreplace(local_heap,entry)
                elif split_index in (1,2):
                    item=local_candidate_map.get(fid) if local_candidate_map is not None else None
                    if item is not None:
                        summary=aggregate.metric_summary(row)
                        item["validation" if split_index==1 else "blind"]=summary
                        if split_index==1:
                            item["validation_mean_number_hits_top5"]=summary["mean_number_hits_top5"]
                            item["validation_mean_rank_of_actual_numbers"]=summary["mean_rank_of_actual_numbers"]
                local_row+=1;global_metric_row+=1;split_rows[split]+=1
        if local_row!=SHARD_SIZE*3 or global_metric_row!=(shard+1)*SHARD_SIZE*3:
            fail("Q92 adjusted metric part row count mismatch shard "+str(shard))
        if local_candidate_map is None or len(local_candidate_map)!=100:fail("Q92 acceptance local candidate map incomplete shard "+str(shard))
        for item in local_candidate_map.values():
            if "validation" not in item or "blind" not in item:fail("Q92 acceptance candidate missing Validation/Blind shard "+str(shard))
            candidate_pool.append(item)
    if global_metric_row!=TOTAL*3 or split_rows!={split:TOTAL for split in SPLITS}:
        fail("Q92 adjusted metric global coverage mismatch")
    raw.flush();adjusted.flush()
    raw_hash=aggregate.sha256_memmap(raw);adjusted_hash=aggregate.sha256_memmap(adjusted)
    mt=manifest.get("multiple_testing",{})
    if mt.get("test_count")!=EXPECTED_TESTS or mt.get("raw_pvalue_vector_sha256")!=raw_hash or mt.get("adjusted_pvalue_vector_sha256")!=adjusted_hash:
        fail("Q92 raw/adjusted p-value vector hashes or Holm family size mismatch")
    q92a.holm_adjust_in_place(raw,chunk_size=500_000)
    raw.flush()
    for start in range(0,EXPECTED_TESTS,1_000_000):
        end=min(start+1_000_000,EXPECTED_TESTS)
        if not np.array_equal(raw[start:end],adjusted[start:end]):
            fail("Q92 global Holm replay mismatch at p-value index "+str(start))
    holm_below=0;minimum_holm=1.0
    for row_start in range(0,TOTAL*3,1_000_000):
        row_end=min(row_start+1_000_000,TOTAL*3)
        chunk=np.asarray(adjusted[row_start*3:row_end*3],dtype=np.float64).reshape(-1,3)
        row_max=chunk.max(axis=1)
        holm_below+=int(np.sum(row_max<0.05));minimum_holm=min(minimum_holm,float(row_max.min()))
    report=read_json(REPORT_PATH)
    if report.get("multiple_testing",{}).get("holm_adjusted_formula_split_rows_below_0_05")!=holm_below or abs(float(report.get("multiple_testing",{}).get("minimum_holm_p_max_endpoint_family",-1))-minimum_holm)>1e-15:
        fail("Q92 report Holm summary does not reconcile to persisted adjusted vector")
    del raw,adjusted
    raw_path.unlink(missing_ok=True);adjusted_path.unlink(missing_ok=True)
    return candidate_pool,holm_below,minimum_holm

def validate_candidate_freeze(candidate_pool,selection):
    global_top100=q92a.discovery_top_k(candidate_pool,k=100)
    validation_order=sorted(global_top100,key=lambda item:(-item["validation_mean_number_hits_top5"],item["validation_mean_rank_of_actual_numbers"],item["formula_id"]))
    selected=validation_order[0]
    if selection.get("status")!="CANDIDATE_FROZEN_BEFORE_BLIND_OOS" or selection.get("blind_oos_used_for_selection") is not False or selection.get("selected_candidate_ids_frozen") is not True:
        fail("Q92 candidate freeze status/leakage guard mismatch")
    if selection.get("top100_discovery_candidates")!=[item["formula_id"] for item in global_top100]:
        fail("Q92 global Discovery top100 formula IDs do not replay")
    if selection.get("Q92_candidate",{}).get("formula_id")!=selected["formula_id"]:
        fail("Q92 Validation-selected formula ID does not replay")
    if selection.get("Q92_candidate",{}).get("formula_rank")!=selected["formula_rank"]:
        fail("Q92 Validation-selected formula rank does not replay")
    if selection.get("Q89_control",{}).get("formula_id")!=selection.get("Q89_control_candidate_id",selection.get("Q89_control",{}).get("formula_id")):
        pass
    shortlist_fields,shortlist=read_csv_fields_rows(SHORTLIST_PATH)
    required={"formula_id","features","discovery_rank","discovery_mean_number_hits_top5","discovery_mean_rank_of_actual_numbers",
        "validation_mean_number_hits_top5","validation_mean_rank_of_actual_numbers","validation_selection_rank","selected"}
    if len(shortlist)!=100 or not required.issubset(set(shortlist_fields or [])):
        fail("Q92 candidate shortlist schema/count mismatch")
    if sorted(int(row["discovery_rank"]) for row in shortlist)!=list(range(1,101)) or sorted(int(row["validation_selection_rank"]) for row in shortlist)!=list(range(1,101)):
        fail("Q92 shortlist Discovery/Validation rank coverage mismatch")
    if len({row["formula_id"] for row in shortlist})!=100:
        fail("Q92 shortlist formula IDs duplicated")
    selected_rows=[row for row in shortlist if int(row["selected"])==1]
    if len(selected_rows)!=1 or selected_rows[0]["formula_id"]!=selected["formula_id"]:
        fail("Q92 shortlist selected row does not reconcile")
    rank_map={item["formula_id"]:rank+1 for rank,item in enumerate(validation_order)}
    for discovery_rank,item in enumerate(global_top100,start=1):
        row=shortlist[discovery_rank-1]
        if row["formula_id"]!=item["formula_id"] or int(row["discovery_rank"])!=discovery_rank or int(row["validation_selection_rank"])!=rank_map[item["formula_id"]]:
            fail("Q92 shortlist candidate/rank order mismatch at discovery rank "+str(discovery_rank))
        compare_float(row["discovery_mean_number_hits_top5"],item["mean_number_hits_top5"],"Q92 shortlist Discovery Top5 "+item["formula_id"])
        compare_float(row["discovery_mean_rank_of_actual_numbers"],item["mean_rank_of_actual_numbers"],"Q92 shortlist Discovery mean rank "+item["formula_id"])
        compare_float(row["validation_mean_number_hits_top5"],item["validation_mean_number_hits_top5"],"Q92 shortlist Validation Top5 "+item["formula_id"])
        compare_float(row["validation_mean_rank_of_actual_numbers"],item["validation_mean_rank_of_actual_numbers"],"Q92 shortlist Validation mean rank "+item["formula_id"])
    return selected

def validate_target_ledger_parts(dates,draws,feature_stack,manifest):
    parts=manifest.get("target_ledger_parts",[])
    if len(parts)!=SHARDS or manifest.get("target_ledger_part_count")!=SHARDS:
        fail("Q92 target ledger parts manifest count mismatch")
    target_count=len(draws)-q80.MIN_HISTORY
    reference_single=None
    for shard,part in enumerate(parts):
        start,end=q92.shard_bounds(shard)
        path=TARGET_PART_DIR/f"shard_{shard}_target_ledger.csv.gz"
        if part.get("shard_index")!=shard or part.get("path")!=str(path.relative_to(ROOT)) or part.get("rows")!=target_count:
            fail("Q92 target ledger part identity/count mismatch shard "+str(shard))
        if part.get("formula_rank_start_inclusive")!=start or part.get("formula_rank_end_exclusive")!=end:
            fail("Q92 target ledger part formula interval mismatch shard "+str(shard))
        if not path.is_file() or path.stat().st_size!=int(part.get("bytes",-1)) or sha256_file(path)!=part.get("sha256"):
            fail("Q92 target ledger part byte/SHA mismatch shard "+str(shard))
        raw_source=aggregate.SHARD_INPUT_DIR/f"shard_{shard}_target_ledger.csv"
        if raw_source.is_file() and sha256_file(raw_source)!=part.get("source_artifact_sha256"):
            fail("Q92 target ledger source artifact SHA mismatch shard "+str(shard))
        with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            required={"target_date","cutoff_date","prior_draws","actual_quintet","status","formula_count_tested","best_formula_id",
                "best_actual_number_ranks","best_number_hits_top5","best_number_hits_top10","best_number_hits_top20","best_rank_sum","single_feature_rank_ledger"}
            if not required.issubset(set(reader.fieldnames or [])):fail("Q92 target ledger part schema incomplete shard "+str(shard))
            count=0
            for row in reader:
                target_index=q80.MIN_HISTORY+count
                offset=count
                if target_index>=len(draws):fail("Q92 target ledger extra rows shard "+str(shard))
                if row.get("target_date")!=dates[target_index] or row.get("cutoff_date")!=dates[target_index-1] or int(row.get("prior_draws",-1))!=target_index:
                    fail("Q92 target ledger strict-prefix date/cutoff mismatch shard "+str(shard)+" offset "+str(offset))
                if row.get("actual_quintet")!=" ".join(map(str,draws[target_index])) or row.get("status")!="SCORED" or int(row.get("formula_count_tested",-1))!=TOTAL:
                    fail("Q92 target ledger actual/status/formula-count mismatch shard "+str(shard)+" offset "+str(offset))
                columns=q92a.parse_formula_id(row["best_formula_id"])
                rank=q92.formula_rank(columns)
                if not start<=rank<end:fail("Q92 target ledger best formula outside shard interval shard "+str(shard)+" offset "+str(offset))
                actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
                observed=json.loads(row["best_actual_number_ranks"])
                expected=aggregate.rank_actual_for_formula(feature_stack[offset],columns,actual_indices)
                if observed!=expected:fail("Q92 target ledger best formula rank replay mismatch shard "+str(shard)+" offset "+str(offset))
                hits={k:sum(v<=k for v in observed) for k in (5,10,20)}
                if int(row["best_number_hits_top5"])!=hits[5] or int(row["best_number_hits_top10"])!=hits[10] or int(row["best_number_hits_top20"])!=hits[20] or int(row["best_rank_sum"])!=sum(observed):
                    fail("Q92 target ledger best formula metrics mismatch shard "+str(shard)+" offset "+str(offset))
                single=json.loads(row["single_feature_rank_ledger"])
                expected_single=aggregate.expected_single_feature_ledger(feature_stack[offset],actual_indices)
                if single!=expected_single:fail("Q92 target ledger 27-feature rank replay mismatch shard "+str(shard)+" offset "+str(offset))
                if shard==0:
                    if reference_single is None:reference_single=[]
                    reference_single.append(single)
                elif reference_single is None or single!=reference_single[offset]:
                    fail("Q92 target ledger single-feature ledger differs across shards shard "+str(shard)+" offset "+str(offset))
                count+=1
            if count!=target_count:fail("Q92 target ledger part exact row count mismatch shard "+str(shard))
    return target_count*SHARDS

def validate_paired_ledger_and_inference(dates,draws,feature_stack,q89_selection,q89_paired_rows,q89_id,q89_columns,selection,inference):
    fields,rows=read_csv_fields_rows(PAIRED_LEDGER_PATH)
    required={"target_date","cutoff_date","prior_draws","actual_quintet","Q92_formula_id","Q92_actual_number_ranks",
        "Q92_number_hits_top5","Q92_number_hits_top10","Q92_number_hits_top20","Q92_all5_top5","Q92_all5_top10","Q92_all5_top20","Q92_rank_sum",
        "Q89_formula_id","Q89_actual_number_ranks","Q89_number_hits_top5","Q89_number_hits_top10","Q89_number_hits_top20","Q89_all5_top5","Q89_all5_top10","Q89_all5_top20","Q89_rank_sum",
        "delta_number_hits_top5","delta_number_hits_top10","delta_number_hits_top20","delta_hit_share_top5","delta_hit_share_top10","delta_hit_share_top20","delta_rank_sum","delta_mean_rank_actual_numbers"}
    if len(rows)!=EXPECTED_BLIND_TARGETS or not required.issubset(set(fields or [])):
        fail("Q92 paired Blind OOS ledger schema/count mismatch")
    q92_id=selection.get("Q92_candidate",{}).get("formula_id")
    q92_columns=q92a.parse_formula_id(q92_id)
    q89_by_date={row["target_date"]:row for row in q89_paired_rows}
    scored=len(draws)-q80.MIN_HISTORY
    expected_dates=[dates[index] for offset,index in enumerate(range(q80.MIN_HISTORY,len(draws))) if q80.split_name(offset,scored)=="blind_oos"]
    if [row["target_date"] for row in rows]!=expected_dates:fail("Q92 paired Blind OOS target date coverage/order mismatch")
    endpoint_deltas={"top5_hit_share":[],"top10_hit_share":[],"top20_hit_share":[],"mean_rank_actual_numbers":[]}
    for offset,row in enumerate(rows):
        date=row["target_date"]
        target_index=dates.index(date)
        target_offset=target_index-q80.MIN_HISTORY
        control=q89_by_date.get(date)
        if control is None:fail("Q92 paired ledger Q89 control target missing "+date)
        if row.get("cutoff_date")!=dates[target_index-1] or int(row.get("prior_draws",-1))!=target_index or row.get("actual_quintet")!=" ".join(map(str,draws[target_index])):
            fail("Q92 paired ledger target/cutoff/quintet mismatch "+date)
        if row.get("Q92_formula_id")!=q92_id or row.get("Q89_formula_id")!=q89_id:
            fail("Q92 paired ledger frozen formula IDs changed "+date)
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        ranks92=aggregate.rank_actual_for_formula(feature_stack[target_offset],q92_columns,actual_indices)
        ranks89=aggregate.rank_actual_for_formula(feature_stack[target_offset],q89_columns,actual_indices)
        if json.loads(row["Q92_actual_number_ranks"])!=ranks92 or json.loads(row["Q89_actual_number_ranks"])!=ranks89:
            fail("Q92 paired ledger rank vector replay mismatch "+date)
        if json.loads(control["Q89_actual_number_ranks"])!=ranks89:
            fail("Q92 paired ledger Q89 control disagrees with persisted Q89 ledger "+date)
        hits92={k:sum(v<=k for v in ranks92) for k in (5,10,20)}
        hits89={k:sum(v<=k for v in ranks89) for k in (5,10,20)}
        all592={k:int(all(v<=k for v in ranks92)) for k in (5,10,20)}
        all589={k:int(all(v<=k for v in ranks89)) for k in (5,10,20)}
        delta={k:hits92[k]-hits89[k] for k in (5,10,20)}
        delta_rank=sum(ranks92)-sum(ranks89)
        for k in (5,10,20):
            if int(row[f"Q92_number_hits_top{k}"])!=hits92[k] or int(row[f"Q89_number_hits_top{k}"])!=hits89[k]:
                fail("Q92 paired ledger hit count mismatch "+date)
            if int(row[f"Q92_all5_top{k}"])!=all592[k] or int(row[f"Q89_all5_top{k}"])!=all589[k]:
                fail("Q92 paired ledger all-five indicator mismatch "+date)
            if int(row[f"delta_number_hits_top{k}"])!=delta[k] or abs(float(row[f"delta_hit_share_top{k}"])-delta[k]/5.0)>1e-12:
                fail("Q92 paired ledger hit delta mismatch "+date)
        if int(row["Q92_rank_sum"])!=sum(ranks92) or int(row["Q89_rank_sum"])!=sum(ranks89) or int(row["delta_rank_sum"])!=delta_rank or abs(float(row["delta_mean_rank_actual_numbers"])-delta_rank/5.0)>1e-12:
            fail("Q92 paired ledger rank-sum delta mismatch "+date)
        endpoint_deltas["top5_hit_share"].append(delta[5]/5.0)
        endpoint_deltas["top10_hit_share"].append(delta[10]/5.0)
        endpoint_deltas["top20_hit_share"].append(delta[20]/5.0)
        endpoint_deltas["mean_rank_actual_numbers"].append(delta_rank/5.0)
    replay=q92a.paired_endpoint_inference(endpoint_deltas,replicates=20_000,block_length=7,bootstrap_seed=920027,signflip_seed=920028,confidence_level=0.95)
    compare_json_numeric(inference,replay,"Q92 paired inference replay",tolerance=1e-12)
    report=read_json(REPORT_PATH)
    compare_json_numeric(report.get("paired_blind_inference"),replay,"Q92 report paired inference replay",tolerance=1e-12)
    return replay

def validate():
    report=read_json(REPORT_PATH)
    manifest=read_json(MANIFEST_PATH)
    selection=read_json(SELECTION_PATH)
    inference=read_json(INFERENCE_PATH)
    dates,draws,archive_sha256,archive_sha1=aggregate.load_archive()
    if report.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION" or manifest.get("status")!="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION":
        fail("Q92 report/manifest status is not pending acceptance")
    if report.get("task_id")!="Q92_2026_11_08" or manifest.get("task_id")!="Q92_2026_11_08":
        fail("Q92 report/manifest task identity mismatch")
    if report.get("source_archive_sha256")!=archive_sha256 or manifest.get("source_archive_sha256")!=archive_sha256 or report.get("source_archive_git_blob_sha1")!=archive_sha1 or manifest.get("source_archive_git_blob_sha1")!=archive_sha1:
        fail("Q92 report/manifest archive SHA mismatch")
    expected_report={"target_count":3402,"scored_targets":3352,"formula_count":TOTAL,"formula_size":10,"feature_count":27,
        "metrics_rows":TOTAL*3,"split_counts":SPLIT_COUNTS,"shard_count":SHARDS,"shard_formula_count":SHARD_SIZE}
    for key,value in expected_report.items():
        if report.get(key)!=value:fail("Q92 report dimension/split mismatch field "+key)
    if manifest.get("formula_count")!=TOTAL or manifest.get("formula_size")!=10 or manifest.get("feature_count")!=27 or manifest.get("metrics_rows")!=TOTAL*3 or manifest.get("formula_rank_coverage")!="0..8436284 exactly once":
        fail("Q92 manifest formula universe/dimensions mismatch")
    if manifest.get("formula_split_endpoint_holm_family_size")!=EXPECTED_TESTS:
        fail("Q92 manifest global Holm family size mismatch")
    feature_stack=q81.build_feature_stack(draws)
    q89_report,q89_selection,q89_paired,q89_id,q89_columns=validate_q89_control(archive_sha256,dates,draws,feature_stack)
    for shard in range(SHARDS):aggregate.validate_shard_report(shard,archive_sha256,dates)
    candidate_pool,holm_below,minimum_holm=validate_metric_parts(archive_sha256,dates,draws,feature_stack,manifest,selection)
    selected=validate_candidate_freeze(candidate_pool,selection)
    target_rows=validate_target_ledger_parts(dates,draws,feature_stack,manifest)
    paired_replay=validate_paired_ledger_and_inference(dates,draws,feature_stack,q89_selection,q89_paired,q89_id,q89_columns,selection,inference)
    report=read_json(REPORT_PATH)
    if report.get("multiple_testing",{}).get("holm_adjusted_formula_split_rows_below_0_05")!=holm_below or abs(float(report.get("multiple_testing",{}).get("minimum_holm_p_max_endpoint_family",-1))-minimum_holm)>1e-15:
        fail("Q92 report global Holm summary mismatch")
    supplemental=manifest.get("supplemental_outputs",{})
    checks=[("candidate_shortlist",SHORTLIST_PATH,100),("candidate_selection",SELECTION_PATH,None),
        ("paired_blind_ledger",PAIRED_LEDGER_PATH,EXPECTED_BLIND_TARGETS),("paired_inference",INFERENCE_PATH,None)]
    for key,path,rows_expected in checks:
        entry=supplemental.get(key,{})
        if entry.get("path")!=str(path.relative_to(ROOT)) or entry.get("bytes")!=path.stat().st_size or entry.get("sha256")!=sha256_file(path):
            fail("Q92 supplemental output manifest byte/SHA/path mismatch "+key)
        if rows_expected is not None and entry.get("rows")!=rows_expected:
            fail("Q92 supplemental output manifest row count mismatch "+key)
    if manifest.get("target_ledger_rows_per_shard")!=3352 or manifest.get("target_ledger_part_count")!=SHARDS or target_rows!=3352*SHARDS:
        fail("Q92 target ledger part row totals mismatch")
    print("Q92_ACCEPTANCE_PASS: canonical archive, 15 shards, formula×split coverage, global Holm replay, candidate freeze, target ledger strict-prior replay and paired Blind OOS inference reconciled")
    print(json.dumps({"task_id":"Q92_2026_11_08","status":"ACCEPTANCE_PASS_PENDING_PERSISTENCE","formula_count":TOTAL,
        "metrics_rows":TOTAL*3,"holm_family_size":EXPECTED_TESTS,"holm_adjusted_formula_split_rows_below_0_05":holm_below,
        "minimum_holm_p_max_endpoint_family":minimum_holm,"selected_q92_candidate_id":selected["formula_id"],
        "q89_control_candidate_id":q89_id,"paired_blind_ledger_rows":EXPECTED_BLIND_TARGETS,
        "paired_primary_decision":paired_replay["primary_decision"]},ensure_ascii=False,separators=(",",":")))

if __name__=="__main__":
    validate()
