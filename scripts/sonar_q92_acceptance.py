#!/usr/bin/env python3
"""Fail-closed acceptance validator for Q92 persisted ten-feature formula evidence."""
from __future__ import annotations
import csv, gzip, hashlib, json, math
from pathlib import Path
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import numpy as np
import sonar_q92_common as q92
import aggregate_sonar_q92_shards as q92agg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
DATA=ROOT/"data/storico_daily.csv"
REPORT_PATH=OUT/"per_number_condition_10plus_grammar.json"
MANIFEST_PATH=OUT/"per_number_condition_10plus_formula_metrics_manifest.json"
LEDGER_PATH=OUT/"per_number_condition_10plus_target_ledger.csv"
SHORTLIST_PATH=OUT/"per_number_condition_10plus_candidate_shortlist.csv"
SELECTION_PATH=OUT/"per_number_condition_10plus_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q92_selected_candidate_blind_ledger.csv"
PAIRED_INFERENCE_PATH=OUT/"per_number_condition_10plus_paired_inference.json"
Q89_REFRESH_REPORT_PATH=OUT/"q89_refresh_20261108_report.json"
Q89_REFRESH_MANIFEST_PATH=OUT/"q89_refresh_20261108_manifest.json"
Q89_REFRESH_SELECTION_PATH=OUT/"q89_refresh_20261108_candidate_selection.json"
Q89_REFRESH_PAIRED_LEDGER_PATH=OUT/"q89_refresh_20261108_selected_candidate_blind_ledger.csv"
SPLITS=("discovery","validation","blind_oos")
PAIRED_METRIC_BLOCKS=(("Q92_candidate_blind_metrics","Q92"),("Q89_control_blind_metrics","Q89"))

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def load_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("missing CSV header: "+str(path))
        return reader.fieldnames,list(reader)

def fail(errors,message):
    errors.append(message)

def parse_formula_id(fid,prefix,size):
    if not isinstance(fid,str) or not fid.startswith(prefix):
        raise ValueError("formula prefix mismatch")
    columns=tuple(int(value) for value in fid[len(prefix):].split("_"))
    if len(columns)!=size or tuple(sorted(set(columns)))!=columns or columns[0]<0 or columns[-1]>=27:
        raise ValueError("formula indices are not canonical")
    if prefix+"_".join(f"{value:02d}" for value in columns)!=fid:
        raise ValueError("formula ID canonicalization mismatch")
    return columns

def expected_archive():
    with DATA.open(newline="",encoding="utf-8-sig") as handle:
        rows=list(csv.DictReader(handle))
    dates=[row["data"] for row in rows]
    if dates!=sorted(dates) or len(dates)!=len(set(dates)):
        raise ValueError("canonical archive dates invalid")
    draws=[]
    for row in rows:
        values=[int(row[f"n{i}"]) for i in range(1,6)]
        if len(set(values))!=5 or values!=sorted(values) or any(value<1 or value>40 for value in values):
            raise ValueError("canonical archive quintet invalid")
        draws.append(values)
    return dates,draws

def validate_paired_metric_replay(inference,paired):
    errors=[]
    if not paired:
        return errors
    for family,prefix in PAIRED_METRIC_BLOCKS:
        metrics=inference.get(family,{})
        for k in (5,10,20):
            expected=sum(int(row[f"{prefix}_number_hits_top{k}"]) for row in paired)/(5*len(paired))
            actual=float(metrics.get(f"mean_number_hits_top{k}",float("nan")))
            if not math.isfinite(actual) or abs(actual-expected)>=1e-12:
                errors.append("Q92 blind candidate metric replay mismatch "+family+" Top"+str(k))
        expected_rank=sum(int(row[f"{prefix}_rank_sum"]) for row in paired)/(5*len(paired))
        actual_rank=float(metrics.get("mean_rank_of_actual_numbers",float("nan")))
        if not math.isfinite(actual_rank) or abs(actual_rank-expected_rank)>=1e-12:
            errors.append("Q92 blind candidate rank metric replay mismatch "+family)
    return errors

def validate_q92():
    errors=[]
    try:
        report=load_json(REPORT_PATH)
        manifest=load_json(MANIFEST_PATH)
        dates,draws=expected_archive()
    except Exception as exc:
        return ["Q92 required report/manifest/archive unreadable: "+str(exc)]
    raw_archive=DATA.read_bytes()
    source_sha=hashlib.sha256(raw_archive).hexdigest()
    archive_git_sha1=hashlib.sha1(b"blob "+str(len(raw_archive)).encode("ascii")+b"\\0"+raw_archive).hexdigest()
    try:
        q89_refresh=q92agg.validate_q89_refresh_control(dates,draws,source_sha)
    except Exception as exc:
        return ["Q92 same-archive Q89 refresh control acceptance/readback failed: "+str(exc)]
    n=len(draws)
    scored=n-q80.MIN_HISTORY
    discovery=math.ceil(.60*scored)
    validation=math.ceil(.80*scored)
    expected_splits={"discovery":discovery,"validation":validation-discovery,"blind_oos":scored-validation}
    total_rows=q92.TOTAL_FORMULA_COUNT*3
    total_tests=total_rows*3
    add=lambda condition,message: fail(errors,message) if not condition else None
    add(report.get("task_id")=="Q92","Q92 task identity mismatch")
    add(report.get("status") in ("AGGREGATED_PENDING_ACCEPTANCE_VALIDATION","VALIDATED_PENDING_HUMAN_REVIEW"),"Q92 report status mismatch")
    add(report.get("review_status")=="PENDING_HUMAN_REVIEW_INTEGRATION","Q92 human-review gate missing")
    add(report.get("protocol_id")=="Q92-ten-feature-equal-weight-catalog-2026-11-09","Q92 protocol identity mismatch")
    add(report.get("source_archive_sha256")==source_sha and manifest.get("source_archive_sha256")==source_sha and report.get("source_archive_git_blob_sha1")=="77ca692a6082809fcc6c471501617433ec7c36cf","Q92 canonical archive SHA mismatch")
    add(report.get("target_count")==n==3402 and report.get("scored_targets")==scored==3352 and report.get("first_date")==dates[0] and report.get("last_date")==dates[-1]=="2026-11-08" and report.get("source_archive_main_commit")=="6cca9022d4311a3f9aba2925fce8c653dc6b63ab","Q92 archive dimensions/date cutoff mismatch")
    add(report.get("minimum_prior_history")==q80.MIN_HISTORY and q80.MIN_HISTORY>=50,"Q92 minimum prior history mismatch")
    add(report.get("feature_count")==27 and len(report.get("features",[]))==27,"Q92 feature schema mismatch")
    add(report.get("formula_size")==10 and report.get("formula_count")==q92.TOTAL_FORMULA_COUNT==8_436_285 and report.get("formula_count_check")==q92.TOTAL_FORMULA_COUNT,"Q92 formula universe mismatch")
    add(report.get("shard_count")==15 and report.get("shard_formula_count")==562_419,"Q92 shard layout mismatch")
    add(report.get("formula_grammar")=="all ten-feature equal-weight combinations","Q92 grammar label mismatch")
    add(report.get("split_counts")==expected_splits and expected_splits=={"discovery":2012,"validation":670,"blind_oos":670},"Q92 chronological split counts mismatch")
    add(report.get("metrics_rows")==total_rows and report.get("target_ledger_rows")==scored,"Q92 output dimensions mismatch")
    add(report.get("multiple_testing",{}).get("method")=="Global Holm-Bonferroni" and report.get("multiple_testing",{}).get("test_count")==total_tests,"Q92 global Holm family size/method mismatch")
    add(manifest.get("task_id")=="Q92" and manifest.get("storage_format")=="chunked_csv_gzip_parts","Q92 metrics manifest identity/storage mismatch")
    add(manifest.get("formula_count")==q92.TOTAL_FORMULA_COUNT and manifest.get("metrics_rows")==total_rows,"Q92 metrics manifest dimensions mismatch")
    parts=report.get("metrics_parts",[])
    add(parts==manifest.get("parts") and manifest.get("part_count")==len(parts),"Q92 report and manifest part lists mismatch")
    parts_sha=hashlib.sha256(json.dumps(parts,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    add(report.get("outputs",{}).get("metrics_parts_manifest_sha256")==parts_sha and manifest.get("parts_manifest_sha256")==parts_sha,"Q92 metrics parts manifest hash mismatch")
    add(len(parts)==math.ceil(total_rows/30000)==844,"Q92 metrics chunk count mismatch")
    required={"split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
        "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"}
    row_cursor=0
    part_cursor=0
    current_shard=-1
    current_split=-1
    expected_formula_iter=None
    counts={split:0 for split in SPLITS}
    pvals=np.empty(total_tests,dtype=np.float64)
    stored_holm=np.empty(total_rows,dtype=np.float64)
    try:
        for part_index,part in enumerate(parts):
            path=ROOT/part["path"]
            add(part.get("part_index")==part_index,"Q92 metrics part index/order mismatch")
            add(int(part.get("row_start_inclusive",-1))==row_cursor,"Q92 metrics part range gap/overlap")
            if not path.is_file():
                fail(errors,"Q92 metrics part missing: "+part["path"])
                row_cursor+=max(0,int(part.get("rows",-1)))
                continue
            raw=path.read_bytes()
            add(len(raw)==int(part.get("bytes",-1)),"Q92 metrics part byte count mismatch: "+part["path"])
            add(hashlib.sha256(raw).hexdigest()==part.get("sha256"),"Q92 metrics part SHA mismatch: "+part["path"])
            expected_rows=min(30000,total_rows-row_cursor)
            add(int(part.get("rows",-1))==expected_rows,"Q92 metrics part row count manifest mismatch: "+part["path"])
            local=0
            with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
                reader=csv.DictReader(handle)
                add(required.issubset(set(reader.fieldnames or [])),"Q92 metric schema incomplete")
                for row in reader:
                    global_row=row_cursor+local
                    shard=global_row//(q92.SHARD_SIZE*3)
                    within_shard=global_row%(q92.SHARD_SIZE*3)
                    split_index=within_shard//q92.SHARD_SIZE
                    local_formula_rank=within_shard%q92.SHARD_SIZE
                    split=SPLITS[split_index]
                    add(row.get("split")==split,"Q92 metric split order mismatch")
                    start,end=q92.shard_bounds(shard)
                    if current_shard!=shard or current_split!=split_index:
                        current_shard=shard
                        current_split=split_index
                        expected_formula_iter=q92.iter_formula_slice(start,end)
                    try:
                        expected_columns=next(expected_formula_iter)
                    except StopIteration:
                        fail(errors,"Q92 expected formula iterator ended early")
                        break
                    expected_fid=q92.formula_id(expected_columns)
                    add(row.get("formula_id")==expected_fid,"Q92 formula coverage/order mismatch at metric row "+str(global_row))
                    add(int(row.get("feature_count",-1))==9,"Q92 metric feature_count mismatch")
                    add(row.get("features")=="+".join(report["features"][index] for index in expected_columns),"Q92 metric feature names do not match formula ID")
                    add(int(row.get("targets",-1))==expected_splits[split],"Q92 split target count mismatch")
                    for field in ("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers",
                        "p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"):
                        try:
                            value=float(row[field])
                        except Exception:
                            fail(errors,"Q92 non-numeric metric "+field)
                            continue
                        if not math.isfinite(value) or (field=="mean_rank_of_actual_numbers" and not 1<=value<=40) or (field!="mean_rank_of_actual_numbers" and not 0<=value<=1):
                            fail(errors,"Q92 invalid metric "+field)
                    for endpoint_index,field in enumerate(("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx")):
                        pvals[global_row*3+endpoint_index]=float(row[field])
                    stored_holm[global_row]=float(row["holm_p_max_endpoint_family"])
                    counts[split]+=1
                    local+=1
            add(local==expected_rows,"Q92 metrics part decompressed row count mismatch: "+part["path"])
            row_cursor+=local
            add(int(part.get("row_end_exclusive",-1))==row_cursor,"Q92 metrics part end range mismatch")
            part_cursor+=1
    except Exception as exc:
        fail(errors,"Q92 metrics parts validation exception: "+str(exc))
    add(row_cursor==total_rows,"Q92 metrics parts total row count mismatch")
    add(counts=={split:q92.TOTAL_FORMULA_COUNT for split in SPLITS},"Q92 formula/split coverage count mismatch")
    # Recompute the complete global Holm step-down family from every raw formula×split×endpoint p-value.
    order=np.argsort(pvals,kind="stable")
    sorted_adjusted=np.maximum.accumulate((total_tests-np.arange(total_tests,dtype=np.int64))*pvals[order])
    np.minimum(sorted_adjusted,1.0,out=sorted_adjusted)
    adjusted=np.empty_like(pvals)
    adjusted[order]=sorted_adjusted
    replayed_row_holm=adjusted.reshape(total_rows,3).max(axis=1)
    add(np.allclose(stored_holm,replayed_row_holm,rtol=0.0,atol=1e-12),"Q92 global Holm adjusted p-values do not replay")
    add(report.get("holm_adjusted_formula_split_rows_below_0_05")==int(np.sum(replayed_row_holm<0.05)),"Q92 Holm rows below alpha count mismatch")
    add(abs(float(report.get("minimum_holm_p_max_endpoint_family",float("nan")))-float(np.min(replayed_row_holm)))<1e-12,"Q92 minimum global Holm p-value mismatch")

    # Validate the global retrospective target ledger against every canonical target and strict prior cutoff.
    try:
        ledger_fields,ledger=load_csv(LEDGER_PATH)
        required_ledger={"target_date","cutoff_date","prior_draws","actual_quintet","status","formula_count_tested","best_formula_id",
            "best_formula_features","best_actual_number_ranks","single_feature_rank_ledger"}
        add(required_ledger.issubset(set(ledger_fields)),"Q92 target ledger schema incomplete")
        expected_dates=dates[q80.MIN_HISTORY:]
        add(len(ledger)==scored and [row.get("target_date") for row in ledger]==expected_dates,"Q92 target ledger date coverage/order mismatch")
        archive_index={date:index for index,date in enumerate(dates)}
        for row in ledger:
            date=row.get("target_date","")
            index=archive_index.get(date)
            if index is None or index<q80.MIN_HISTORY:
                fail(errors,"Q92 target ledger target missing/too early: "+date); break
            add(row.get("cutoff_date")==dates[index-1] and int(row.get("prior_draws",-1))==index,"Q92 target strict prior cutoff mismatch at "+date)
            add(row.get("actual_quintet")==" ".join(map(str,draws[index])),"Q92 target actual quintet mismatch at "+date)
            add(row.get("status")=="SCORED" and int(row.get("formula_count_tested",-1))==q92.TOTAL_FORMULA_COUNT,"Q92 target status/formula count mismatch")
            columns=parse_formula_id(row.get("best_formula_id",""),"P10_",9)
            add(row.get("best_formula_features")=="+".join(report["features"][value] for value in columns),"Q92 target best formula feature mismatch")
            try:
                ranks=json.loads(row["best_actual_number_ranks"])
                singles=json.loads(row["single_feature_rank_ledger"])
                add(len(ranks)==5 and all(isinstance(value,int) and 1<=value<=40 for value in ranks),"Q92 best actual ranks invalid")
                add(len(singles)==27 and {item.get("feature") for item in singles}==set(report["features"]),"Q92 single-feature rank ledger incomplete")
                for item in singles:
                    add(len(item.get("ranks",[]))==5 and all(isinstance(value,int) and 1<=value<=40 for value in item["ranks"]),"Q92 single-feature ranks invalid")
            except Exception as exc:
                fail(errors,"Q92 target ledger rank evidence invalid at "+date+": "+str(exc)); break
    except Exception as exc:
        fail(errors,"Q92 target ledger validation exception: "+str(exc))

    # Candidate selection is Discovery→Validation frozen; the same-archive Q89 control comes from the accepted refresh.
    try:
        selection=load_json(SELECTION_PATH)
        shortlist_fields,shortlist=load_csv(SHORTLIST_PATH)
        add(selection.get("task_id")=="Q92" and selection.get("status")=="CANDIDATES_FROZEN_BEFORE_BLIND_OOS","Q92 candidate selection status mismatch")
        add(selection.get("blind_oos_used_for_selection") is False and selection.get("selected_candidate_ids_frozen") is True,"Q92 candidate selection leakage guard missing")
        required_shortlist={"family","formula_id","features","discovery_rank","discovery_mean_number_hits_top5","discovery_mean_rank_of_actual_numbers",
            "validation_mean_number_hits_top5","validation_mean_rank_of_actual_numbers","validation_selection_rank","selected"}
        add(len(shortlist)==100 and required_shortlist.issubset(set(shortlist_fields)),"Q92 shortlist schema/row count mismatch")
        family_rows=[row for row in shortlist if row.get("family")=="ten_feature"]
        add(len(family_rows)==100 and all(row.get("family")=="ten_feature" for row in shortlist),"Q92 shortlist family/count mismatch")
        ids=set()
        discovery_ranks=[]
        validation_ranks=[]
        selected_rows=[]
        for row in family_rows:
            fid=row["formula_id"]
            columns=parse_formula_id(fid,"P10_",10)
            add(row.get("features")=="+".join(report["features"][index] for index in columns),"Q92 shortlist feature names/ID mismatch")
            add(fid not in ids,"Q92 duplicate shortlist formula ID")
            ids.add(fid)
            discovery_ranks.append(int(row["discovery_rank"]))
            validation_ranks.append(int(row["validation_selection_rank"]))
            if int(row["selected"])==1:
                selected_rows.append(row)
        add(sorted(discovery_ranks)==list(range(1,101)),"Q92 Discovery shortlist rank coverage mismatch")
        add(sorted(validation_ranks)==list(range(1,101)),"Q92 Validation selection rank coverage mismatch")
        add(len(selected_rows)==1,"Q92 exactly one Validation candidate must be selected")
        selected_id=selected_rows[0]["formula_id"] if selected_rows else None
        add(selection.get("Q92_candidate",{}).get("formula_id")==selected_id,"Q92 selected candidate ID does not reconcile to shortlist")
        add(selection.get("Q92_candidate",{}).get("validation_selection_rank")==1,"Q92 selected candidate is not Validation rank 1")
        top100=selection.get("top100_discovery_candidates",{})
        add(top100.get("Q92")==[row["formula_id"] for row in sorted(family_rows,key=lambda row:int(row["discovery_rank"]))],"Q92 Discovery top100 IDs/order mismatch")
        q89_control=q89_refresh["candidate"]
        q89_selection=selection.get("Q89_control",{})
        add(q89_selection.get("formula_id")==q89_control.get("formula_id") and q89_selection.get("features")==q89_control.get("features"),"Q92 same-archive Q89 control ID/features mismatch")
        for field in ("discovery_rank","discovery_mean_number_hits_top5","discovery_mean_rank_of_actual_numbers","validation_mean_number_hits_top5","validation_mean_rank_of_actual_numbers","validation_selection_rank"):
            add(q89_selection.get(field)==q89_control.get(field),"Q92 same-archive Q89 control selection field mismatch "+field)
        # Recompute the Discovery top-100 and Validation winner from the persisted metric parts.
        metric_paths=[ROOT/part["path"] for part in parts]
        replay_shortlist=q92agg.discovery_top100(metric_paths,gzip_mode=True,prefix="P10_")
        replay_ids=[item["formula_id"] for item in replay_shortlist]
        add(replay_ids==[row["formula_id"] for row in sorted(family_rows,key=lambda row:int(row["discovery_rank"]))],"Q92 Discovery top100 does not replay from metrics")
        replay_selected,replay_enriched=q92agg.validation_select(metric_paths,replay_shortlist,gzip_mode=True,prefix="P10_")
        add(replay_selected.get("formula_id")==selected_id,"Q92 Validation selection does not replay from metrics")
        enriched_by_id={item["formula_id"]:item for item in replay_enriched}
        for row in family_rows:
            item=enriched_by_id.get(row["formula_id"],{})
            add(abs(float(row["discovery_mean_number_hits_top5"])-float(item.get("discovery_mean_number_hits_top5",float("nan"))))<1e-12,"Q92 Discovery Top-5 metric replay mismatch "+row["formula_id"])
            add(abs(float(row["discovery_mean_rank_of_actual_numbers"])-float(item.get("discovery_mean_rank_of_actual_numbers",float("nan"))))<1e-12,"Q92 Discovery mean-rank replay mismatch "+row["formula_id"])
            add(abs(float(row["validation_mean_number_hits_top5"])-float(item.get("validation_mean_number_hits_top5",float("nan"))))<1e-12,"Q92 Validation Top-5 metric replay mismatch "+row["formula_id"])
            add(abs(float(row["validation_mean_rank_of_actual_numbers"])-float(item.get("validation_mean_rank_of_actual_numbers",float("nan"))))<1e-12,"Q92 Validation mean-rank replay mismatch "+row["formula_id"])
    except Exception as exc:
        fail(errors,"Q92 candidate selection validation exception: "+str(exc))

    # Paired Blind OOS ledger replays both frozen formulas from strict-prior feature states.
    paired=[]
    try:
        paired_fields,paired=load_csv(PAIRED_LEDGER_PATH)
        selection=load_json(SELECTION_PATH)
        q92_id=selection["Q92_candidate"]["formula_id"]
        q89_id=selection["Q89_control"]["formula_id"]
        q92_columns=parse_formula_id(q92_id,"P10_",10)
        q89_columns=parse_formula_id(q89_id,"P9_",9)
        expected_blind_indices=list(range(q80.MIN_HISTORY+validation,len(draws)))
        expected_blind_dates=[dates[index] for index in expected_blind_indices]
        required_paired={"target_date","cutoff_date","prior_draws","actual_quintet","Q92_formula_id","Q89_control_formula_id",
            "Q92_actual_number_ranks","Q89_actual_number_ranks","Q92_number_hits_top5","Q92_number_hits_top10","Q92_number_hits_top20",
            "Q89_number_hits_top5","Q89_number_hits_top10","Q89_number_hits_top20","Q92_rank_sum","Q89_rank_sum",
            "paired_delta_number_hits_top5","paired_delta_number_hits_top10","paired_delta_number_hits_top20","paired_delta_mean_rank"}
        add(required_paired.issubset(set(paired_fields)) and len(paired)==670,"Q92 paired Blind ledger schema/row count mismatch")
        add([row.get("target_date") for row in paired]==expected_blind_dates,"Q92 paired Blind target date coverage/order mismatch")
        standardized_stack=q81.build_feature_stack(draws)
        for row,index in zip(paired,expected_blind_indices):
            date=dates[index]
            add(row.get("cutoff_date")==dates[index-1] and int(row.get("prior_draws",-1))==index,"Q92 paired Blind cutoff mismatch at "+date)
            add(row.get("actual_quintet")==" ".join(map(str,draws[index])),"Q92 paired Blind actual quintet mismatch at "+date)
            add(row.get("Q92_formula_id")==q92_id and row.get("Q89_control_formula_id")==q89_id,"Q92 paired candidate IDs changed at "+date)
            actual_indices=np.asarray(draws[index],dtype=np.int64)-1
            standardized=standardized_stack[index-q80.MIN_HISTORY]
            replay_q92=q92agg.rank_actual_for_formula(standardized,q92_columns,actual_indices)
            replay_q89=q92agg.rank_actual_for_formula(standardized,q89_columns,actual_indices)
            q92r=json.loads(row["Q92_actual_number_ranks"])
            q89r=json.loads(row["Q89_actual_number_ranks"])
            add(q92r==replay_q92 and q89r==replay_q89,"Q92/Q89 paired rank replay mismatch at "+date)
            add(len(q92r)==5 and len(q89r)==5 and all(isinstance(value,int) and 1<=value<=40 for value in q92r+q89r),"Q92 paired rank vectors invalid at "+date)
            q92hits={k:sum(value<=k for value in q92r) for k in (5,10,20)}
            q89hits={k:sum(value<=k for value in q89r) for k in (5,10,20)}
            q92all5={k:int(all(value<=k for value in q92r)) for k in (5,10,20)}
            q89all5={k:int(all(value<=k for value in q89r)) for k in (5,10,20)}
            for k in (5,10,20):
                add(int(row[f"Q92_number_hits_top{k}"])==q92hits[k] and int(row[f"Q89_number_hits_top{k}"])==q89hits[k],"Q92 paired hit count mismatch at "+date)
                add(int(row[f"Q92_all5_top{k}"])==q92all5[k] and int(row[f"Q89_all5_top{k}"])==q89all5[k],"Q92 paired all-five indicator mismatch at "+date)
                add(int(row[f"paired_delta_number_hits_top{k}"])==q92hits[k]-q89hits[k],"Q92 paired endpoint delta mismatch at "+date)
            add(int(row["Q92_rank_sum"])==sum(q92r) and int(row["Q89_rank_sum"])==sum(q89r),"Q92 paired rank sum mismatch at "+date)
            add(abs(float(row["paired_delta_mean_rank"])-(sum(q92r)-sum(q89r))/5.0)<1e-12,"Q92 paired mean-rank delta mismatch at "+date)
    except Exception as exc:
        fail(errors,"Q92 paired Blind ledger validation exception: "+str(exc))

    # Paired inference is deterministically replayed from the frozen 670-target ledger.
    try:
        inference=load_json(PAIRED_INFERENCE_PATH)
        add(inference.get("task_id")=="Q92" and inference.get("blind_oos_targets")==670,"Q92 paired inference identity/count mismatch")
        add(inference.get("bootstrap",{}).get("replicates")==20000 and inference.get("bootstrap",{}).get("block_length")==7 and inference.get("bootstrap",{}).get("seed")==920027,"Q92 bootstrap protocol mismatch")
        add(inference.get("signflip",{}).get("replicates")==20000 and inference.get("signflip",{}).get("block_length")==7 and inference.get("signflip",{}).get("seed")==920028,"Q92 sign-flip protocol mismatch")
        add(inference.get("multiple_testing",{}).get("method")=="Holm-Bonferroni" and inference.get("multiple_testing",{}).get("family_size")==4,"Q92 paired endpoint Holm family mismatch")
        endpoint_results=inference.get("paired_endpoints",{})
        add(set(endpoint_results)=={"top5","top10","top20","mean_rank"},"Q92 paired inference endpoint keys mismatch")
        if paired:
            raw_pvalues=[]
            endpoint_names=("top5","top10","top20","mean_rank")
            for endpoint in endpoint_names:
                item=endpoint_results.get(endpoint,{})
                if endpoint=="mean_rank":
                    values=[float(row["paired_delta_mean_rank"]) for row in paired]
                    expected_mean=sum(values)/len(values)
                    add(abs(expected_mean-float(item.get("mean_paired_delta_mean_rank",float("nan"))))<1e-12,"Q92 paired mean-rank point estimate mismatch")
                    ci=q92agg.bootstrap_ci(values,replicates=20000,block_length=7,seed=920027)
                    pvalue=q92agg.block_signflip_p(values,replicates=20000,block_length=7,seed=920028)
                    stored_ci=item.get("bootstrap_95_percentile_ci_mean_rank",[])
                    add(len(stored_ci)==2 and all(abs(float(stored_ci[i])-ci[i])<1e-12 for i in (0,1)),"Q92 paired mean-rank bootstrap CI replay mismatch")
                else:
                    k=int(endpoint[3:])
                    values=[int(row[f"paired_delta_number_hits_top{k}"]) for row in paired]
                    expected_mean=sum(values)/len(values)
                    add(abs(expected_mean-float(item.get("mean_paired_delta_number_hits",float("nan"))))<1e-12,"Q92 paired hit-count point estimate mismatch "+endpoint)
                    add(abs(expected_mean/5.0-float(item.get("mean_paired_delta_hit_share",float("nan"))))<1e-12,"Q92 paired hit-share point estimate mismatch "+endpoint)
                    ci=q92agg.bootstrap_ci(values,replicates=20000,block_length=7,seed=920027)
                    pvalue=q92agg.block_signflip_p(values,replicates=20000,block_length=7,seed=920028)
                    stored_ci=item.get("bootstrap_95_percentile_ci_number_hits",[])
                    add(len(stored_ci)==2 and all(abs(float(stored_ci[i])-ci[i])<1e-12 for i in (0,1)),"Q92 paired bootstrap CI replay mismatch "+endpoint)
                    stored_share_ci=item.get("bootstrap_95_percentile_ci_hit_share",[])
                    add(len(stored_share_ci)==2 and all(abs(float(stored_share_ci[i])-ci[i]/5.0)<1e-12 for i in (0,1)),"Q92 paired hit-share CI replay mismatch "+endpoint)
                add(abs(float(item.get("block_signflip_p_raw_two_sided",float("nan")))-pvalue)<1e-12,"Q92 paired block sign-flip replay mismatch "+endpoint)
                raw_pvalues.append(pvalue)
            adjusted=q92agg.holm_adjust(raw_pvalues)
            for endpoint,value in zip(endpoint_names,adjusted):
                add(abs(float(endpoint_results[endpoint].get("holm_p",float("nan")))-value)<1e-12,"Q92 paired Holm replay mismatch "+endpoint)
            top5=endpoint_results["top5"]
            if top5["holm_p"]<0.05 and top5["bootstrap_95_percentile_ci_hit_share"][0]>0:
                expected_decision="SIGNIFICANT_TOP5_GAIN_REQUIRES_HUMAN_REVIEW"
            elif top5["holm_p"]<0.05 and top5["bootstrap_95_percentile_ci_hit_share"][1]<0:
                expected_decision="SIGNIFICANT_TOP5_DEGRADATION"
            else:
                expected_decision="NO_SIGNIFICANT_GAIN"
            add(inference.get("decision")==expected_decision,"Q92 paired inference decision mismatch")
            for message in validate_paired_metric_replay(inference,paired):
                fail(errors,message)
    except Exception as exc:
        fail(errors,"Q92 paired inference validation exception: "+str(exc))

    if errors:
        return errors
    return []

def main():
    errors=validate_q92()
    if errors:
        raise SystemExit("Q92_ACCEPTANCE_BLOCKED: "+ "; ".join(errors[:40]))
    print("Q92_ACCEPTANCE_VALIDATED: all formula×split metrics, Holm family, target cutoffs, frozen candidates, blind paired ledger and inference reconcile.")

if __name__=="__main__":
    main()
