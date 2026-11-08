#!/usr/bin/env python3
"""Fail-closed acceptance validator for Q89 persisted nine-feature formula evidence."""
from __future__ import annotations
import csv, gzip, hashlib, json, math
from pathlib import Path
import sonar_per_number_condition_grammar as q80
import sonar_q89_common as q89
import aggregate_sonar_q89_shards as q89agg

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
DATA=ROOT/"data/storico_daily.csv"
REPORT_PATH=OUT/"per_number_condition_9plus_grammar.json"
MANIFEST_PATH=OUT/"per_number_condition_9plus_formula_metrics_manifest.json"
LEDGER_PATH=OUT/"per_number_condition_9plus_target_ledger.csv"
SHORTLIST_PATH=OUT/"per_number_condition_9plus_candidate_shortlist.csv"
SELECTION_PATH=OUT/"per_number_condition_9plus_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q89_selected_candidate_blind_ledger.csv"
PAIRED_INFERENCE_PATH=OUT/"per_number_condition_9plus_paired_inference.json"
SPLITS=("discovery","validation","blind_oos")

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

def validate_q89():
    errors=[]
    try:
        report=load_json(REPORT_PATH)
        manifest=load_json(MANIFEST_PATH)
        dates,draws=expected_archive()
    except Exception as exc:
        return ["Q89 required report/manifest/archive unreadable: "+str(exc)]
    source_sha=hashlib.sha256(DATA.read_bytes()).hexdigest()
    n=len(draws)
    scored=n-q80.MIN_HISTORY
    discovery=math.ceil(.60*scored)
    validation=math.ceil(.80*scored)
    expected_splits={"discovery":discovery,"validation":validation-discovery,"blind_oos":scored-validation}
    total_rows=q89.TOTAL_FORMULA_COUNT*3
    total_tests=total_rows*3
    add=lambda condition,message: fail(errors,message) if not condition else None
    add(report.get("task_id")=="Q89","Q89 task identity mismatch")
    add(report.get("status") in ("AGGREGATED_PENDING_ACCEPTANCE_VALIDATION","VALIDATED_PENDING_HUMAN_REVIEW"),"Q89 report status mismatch")
    add(report.get("review_status")=="PENDING_HUMAN_REVIEW_INTEGRATION","Q89 human-review gate missing")
    add(report.get("protocol_id")=="Q89-nine-feature-equal-weight-catalog-2026-11-08","Q89 protocol identity mismatch")
    add(report.get("source_archive_sha256")==source_sha and manifest.get("source_archive_sha256")==source_sha,"Q89 canonical archive SHA mismatch")
    add(report.get("target_count")==n and report.get("scored_targets")==scored and report.get("first_date")==dates[0] and report.get("last_date")==dates[-1],"Q89 archive dimensions/date cutoff mismatch")
    add(report.get("minimum_prior_history")==q80.MIN_HISTORY and q80.MIN_HISTORY>=50,"Q89 minimum prior history mismatch")
    add(report.get("feature_count")==27 and len(report.get("features",[]))==27,"Q89 feature schema mismatch")
    add(report.get("formula_size")==9 and report.get("formula_count")==q89.TOTAL_FORMULA_COUNT==4_686_825 and report.get("formula_count_check")==q89.TOTAL_FORMULA_COUNT,"Q89 formula universe mismatch")
    add(report.get("shard_count")==15 and report.get("shard_formula_count")==312_455,"Q89 shard layout mismatch")
    add(report.get("formula_grammar")=="all nine-feature equal-weight combinations","Q89 grammar label mismatch")
    add(report.get("split_counts")==expected_splits and expected_splits=={"discovery":2011,"validation":670,"blind_oos":670},"Q89 chronological split counts mismatch")
    add(report.get("metrics_rows")==total_rows and report.get("target_ledger_rows")==scored,"Q89 output dimensions mismatch")
    add(report.get("multiple_testing",{}).get("method")=="Holm-Bonferroni" and report.get("multiple_testing",{}).get("test_count")==total_tests,"Q89 global Holm family size/method mismatch")
    add(manifest.get("task_id")=="Q89" and manifest.get("storage_format")=="chunked_csv_gzip_parts","Q89 metrics manifest identity/storage mismatch")
    add(manifest.get("formula_count")==q89.TOTAL_FORMULA_COUNT and manifest.get("metrics_rows")==total_rows,"Q89 metrics manifest dimensions mismatch")
    parts=report.get("metrics_parts",[])
    add(parts==manifest.get("parts") and manifest.get("part_count")==len(parts),"Q89 report and manifest part lists mismatch")
    parts_sha=hashlib.sha256(json.dumps(parts,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    add(report.get("outputs",{}).get("metrics_parts_manifest_sha256")==parts_sha and manifest.get("parts_manifest_sha256")==parts_sha,"Q89 metrics parts manifest hash mismatch")
    add(len(parts)==math.ceil(total_rows/30000)==469,"Q89 metrics chunk count mismatch")
    required={"split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
        "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"}
    row_cursor=0
    part_cursor=0
    current_shard=-1
    current_split=-1
    expected_formula_iter=None
    counts={split:0 for split in SPLITS}
    try:
        for part_index,part in enumerate(parts):
            path=ROOT/part["path"]
            add(part.get("part_index")==part_index,"Q89 metrics part index/order mismatch")
            add(int(part.get("row_start_inclusive",-1))==row_cursor,"Q89 metrics part range gap/overlap")
            if not path.is_file():
                fail(errors,"Q89 metrics part missing: "+part["path"])
                row_cursor+=max(0,int(part.get("rows",-1)))
                continue
            raw=path.read_bytes()
            add(len(raw)==int(part.get("bytes",-1)),"Q89 metrics part byte count mismatch: "+part["path"])
            add(hashlib.sha256(raw).hexdigest()==part.get("sha256"),"Q89 metrics part SHA mismatch: "+part["path"])
            expected_rows=min(30000,total_rows-row_cursor)
            add(int(part.get("rows",-1))==expected_rows,"Q89 metrics part row count manifest mismatch: "+part["path"])
            local=0
            with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
                reader=csv.DictReader(handle)
                add(required.issubset(set(reader.fieldnames or [])),"Q89 metric schema incomplete")
                for row in reader:
                    global_row=row_cursor+local
                    shard=global_row//(q89.SHARD_SIZE*3)
                    within_shard=global_row%(q89.SHARD_SIZE*3)
                    split_index=within_shard//q89.SHARD_SIZE
                    local_formula_rank=within_shard%q89.SHARD_SIZE
                    split=SPLITS[split_index]
                    add(row.get("split")==split,"Q89 metric split order mismatch")
                    start,end=q89.shard_bounds(shard)
                    if current_shard!=shard or current_split!=split_index:
                        current_shard=shard
                        current_split=split_index
                        expected_formula_iter=q89.iter_formula_slice(start,end)
                    try:
                        expected_columns=next(expected_formula_iter)
                    except StopIteration:
                        fail(errors,"Q89 expected formula iterator ended early")
                        break
                    expected_fid=q89.formula_id(expected_columns)
                    add(row.get("formula_id")==expected_fid,"Q89 formula coverage/order mismatch at metric row "+str(global_row))
                    add(int(row.get("feature_count",-1))==9,"Q89 metric feature_count mismatch")
                    add(row.get("features")=="+".join(report["features"][index] for index in expected_columns),"Q89 metric feature names do not match formula ID")
                    add(int(row.get("targets",-1))==expected_splits[split],"Q89 split target count mismatch")
                    for field in ("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers",
                        "p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"):
                        try:
                            value=float(row[field])
                        except Exception:
                            fail(errors,"Q89 non-numeric metric "+field)
                            continue
                        if not math.isfinite(value) or (field=="mean_rank_of_actual_numbers" and not 1<=value<=40) or (field!="mean_rank_of_actual_numbers" and not 0<=value<=1):
                            fail(errors,"Q89 invalid metric "+field)
                    counts[split]+=1
                    local+=1
            add(local==expected_rows,"Q89 metrics part decompressed row count mismatch: "+part["path"])
            row_cursor+=local
            add(int(part.get("row_end_exclusive",-1))==row_cursor,"Q89 metrics part end range mismatch")
            part_cursor+=1
    except Exception as exc:
        fail(errors,"Q89 metrics parts validation exception: "+str(exc))
    add(row_cursor==total_rows,"Q89 metrics parts total row count mismatch")
    add(counts=={split:q89.TOTAL_FORMULA_COUNT for split in SPLITS},"Q89 formula/split coverage count mismatch")

    # Validate the global retrospective target ledger against every canonical target and strict prior cutoff.
    try:
        ledger_fields,ledger=load_csv(LEDGER_PATH)
        required_ledger={"target_date","cutoff_date","prior_draws","actual_quintet","status","formula_count_tested","best_formula_id",
            "best_formula_features","best_actual_number_ranks","single_feature_rank_ledger"}
        add(required_ledger.issubset(set(ledger_fields)),"Q89 target ledger schema incomplete")
        expected_dates=dates[q80.MIN_HISTORY:]
        add(len(ledger)==scored and [row.get("target_date") for row in ledger]==expected_dates,"Q89 target ledger date coverage/order mismatch")
        archive_index={date:index for index,date in enumerate(dates)}
        for row in ledger:
            date=row.get("target_date","")
            index=archive_index.get(date)
            if index is None or index<q80.MIN_HISTORY:
                fail(errors,"Q89 target ledger target missing/too early: "+date); break
            add(row.get("cutoff_date")==dates[index-1] and int(row.get("prior_draws",-1))==index,"Q89 target strict prior cutoff mismatch at "+date)
            add(row.get("actual_quintet")==" ".join(map(str,draws[index])),"Q89 target actual quintet mismatch at "+date)
            add(row.get("status")=="SCORED" and int(row.get("formula_count_tested",-1))==q89.TOTAL_FORMULA_COUNT,"Q89 target status/formula count mismatch")
            columns=parse_formula_id(row.get("best_formula_id",""),"P9_",9)
            add(row.get("best_formula_features")=="+".join(report["features"][value] for value in columns),"Q89 target best formula feature mismatch")
            try:
                ranks=json.loads(row["best_actual_number_ranks"])
                singles=json.loads(row["single_feature_rank_ledger"])
                add(len(ranks)==5 and all(isinstance(value,int) and 1<=value<=40 for value in ranks),"Q89 best actual ranks invalid")
                add(len(singles)==27 and {item.get("feature") for item in singles}==set(report["features"]),"Q89 single-feature rank ledger incomplete")
                for item in singles:
                    add(len(item.get("ranks",[]))==5 and all(isinstance(value,int) and 1<=value<=40 for value in item["ranks"]),"Q89 single-feature ranks invalid")
            except Exception as exc:
                fail(errors,"Q89 target ledger rank evidence invalid at "+date+": "+str(exc)); break
    except Exception as exc:
        fail(errors,"Q89 target ledger validation exception: "+str(exc))

    # Candidate selection must be frozen on Discovery/Validation only and include exactly 100 per family.
    try:
        selection=load_json(SELECTION_PATH)
        shortlist_fields,shortlist=load_csv(SHORTLIST_PATH)
        add(selection.get("task_id")=="Q89" and selection.get("status")=="CANDIDATES_FROZEN_BEFORE_BLIND_OOS","Q89 candidate selection status mismatch")
        add(selection.get("blind_oos_used_for_selection") is False and selection.get("selected_candidate_ids_frozen") is True,"Q89 candidate selection leakage guard missing")
        add(len(shortlist)==200 and {"family","formula_id","features","discovery_rank","discovery_mean_number_hits_top5","discovery_mean_rank_of_actual_numbers",
            "validation_mean_number_hits_top5","validation_mean_rank_of_actual_numbers","validation_selection_rank","selected"}.issubset(set(shortlist_fields)),"Q89 candidate shortlist schema/row count mismatch")
        family_counts={}
        selected_by_family={}
        seen_ids={}
        for family in ("nine_feature","eight_feature_control"):
            family_rows=[row for row in shortlist if row.get("family")==family]
            family_counts[family]=len(family_rows)
            add(len(family_rows)==100,"Q89 shortlist candidate count mismatch for "+family)
            ids=set()
            discovery_ranks=[]
            validation_ranks=[]
            selected_rows=[]
            for row in family_rows:
                fid=row["formula_id"]
                prefix,size=("P9_",9) if family=="nine_feature" else ("P8_",8)
                columns=parse_formula_id(fid,prefix,size)
                add(row.get("features")=="+".join(report["features"][index] for index in columns),"Q89 shortlist feature names/ID mismatch")
                add(fid not in ids,"Q89 duplicate shortlist formula ID")
                ids.add(fid)
                discovery_ranks.append(int(row["discovery_rank"]))
                validation_ranks.append(int(row["validation_selection_rank"]))
                if int(row["selected"])==1:
                    selected_rows.append(row)
            add(sorted(discovery_ranks)==list(range(1,101)),"Q89 Discovery shortlist rank coverage mismatch")
            add(sorted(validation_ranks)==list(range(1,101)),"Q89 Validation selection rank coverage mismatch")
            add(len(selected_rows)==1,"Q89 exactly one Validation candidate must be selected for "+family)
            selected_by_family[family]=selected_rows[0]["formula_id"] if selected_rows else None
        add(selection.get("Q89_candidate",{}).get("formula_id")==selected_by_family.get("nine_feature"),"Q89 selected candidate ID does not reconcile")
        add(selection.get("Q88_control",{}).get("formula_id")==selected_by_family.get("eight_feature_control"),"Q88 control ID does not reconcile")
        top100=selection.get("top100_discovery_candidates",{})
        add(set(top100.get("Q89",[]))=={row["formula_id"] for row in shortlist if row["family"]=="nine_feature"},"Q89 Discovery top100 IDs mismatch")
        add(set(top100.get("Q88",[]))=={row["formula_id"] for row in shortlist if row["family"]=="eight_feature_control"},"Q88 Discovery top100 IDs mismatch")
    except Exception as exc:
        fail(errors,"Q89 candidate selection validation exception: "+str(exc))

    # Paired blind ledger must reconcile every held-out target and all paired endpoint arithmetic.
    paired=[]
    try:
        paired_fields,paired=load_csv(PAIRED_LEDGER_PATH)
        expected_blind_dates=[dates[q80.MIN_HISTORY+offset] for offset in range(scored) if q80.split_name(offset,scored)=="blind_oos"]
        required_paired={"target_date","cutoff_date","prior_draws","actual_quintet","Q89_formula_id","Q88_control_formula_id",
            "Q89_actual_number_ranks","Q88_actual_number_ranks","Q89_number_hits_top5","Q89_number_hits_top10","Q89_number_hits_top20",
            "Q88_number_hits_top5","Q88_number_hits_top10","Q88_number_hits_top20","Q89_rank_sum","Q88_rank_sum",
            "paired_delta_number_hits_top5","paired_delta_number_hits_top10","paired_delta_number_hits_top20"}
        add(required_paired.issubset(set(paired_fields)) and len(paired)==670,"Q89 paired blind ledger schema/row count mismatch")
        selection=load_json(SELECTION_PATH)
        q89_id=selection["Q89_candidate"]["formula_id"]
        q88_id=selection["Q88_control"]["formula_id"]
        add([row.get("target_date") for row in paired]==expected_blind_dates,"Q89 paired blind target date coverage/order mismatch")
        for row in paired:
            date=row["target_date"]
            index=dates.index(date)
            add(row.get("cutoff_date")==dates[index-1] and int(row.get("prior_draws",-1))==index,"Q89 paired blind cutoff mismatch at "+date)
            add(row.get("actual_quintet")==" ".join(map(str,draws[index])),"Q89 paired blind actual quintet mismatch at "+date)
            add(row.get("Q89_formula_id")==q89_id and row.get("Q88_control_formula_id")==q88_id,"Q89 paired candidate IDs changed on blind ledger")
            q9r=json.loads(row["Q89_actual_number_ranks"])
            q8r=json.loads(row["Q88_actual_number_ranks"])
            add(len(q9r)==5 and len(q8r)==5 and all(isinstance(value,int) and 1<=value<=40 for value in q9r+q8r),"Q89 paired blind rank vectors invalid")
            for k in (5,10,20):
                q9h=sum(value<=k for value in q9r)
                q8h=sum(value<=k for value in q8r)
                add(int(row[f"Q89_number_hits_top{k}"])==q9h and int(row[f"Q88_number_hits_top{k}"])==q8h,"Q89 paired blind hit counts mismatch at "+date)
                add(int(row[f"paired_delta_number_hits_top{k}"])==q9h-q8h,"Q89 paired blind endpoint delta mismatch at "+date)
            add(int(row["Q89_rank_sum"])==sum(q9r) and int(row["Q88_rank_sum"])==sum(q8r),"Q89 paired blind rank sum mismatch at "+date)
    except Exception as exc:
        fail(errors,"Q89 paired blind ledger validation exception: "+str(exc))

    # Paired inference is reproducible from the persisted paired ledger and frozen seeds.
    try:
        inference=load_json(PAIRED_INFERENCE_PATH)
        add(inference.get("task_id")=="Q89" and inference.get("blind_oos_targets")==670,"Q89 paired inference identity/count mismatch")
        add(inference.get("bootstrap",{}).get("replicates")==20000 and inference.get("bootstrap",{}).get("block_length")==7 and inference.get("bootstrap",{}).get("seed")==890027,"Q89 bootstrap protocol mismatch")
        add(inference.get("signflip",{}).get("replicates")==20000 and inference.get("signflip",{}).get("block_length")==7 and inference.get("signflip",{}).get("seed")==890028,"Q89 sign-flip protocol mismatch")
        add(inference.get("multiple_testing",{}).get("method")=="Holm-Bonferroni" and inference.get("multiple_testing",{}).get("family_size")==3,"Q89 paired endpoint Holm family mismatch")
        endpoint_results=inference.get("paired_endpoints",{})
        add(set(endpoint_results)=={"top5","top10","top20"},"Q89 paired inference endpoint keys mismatch")
        for endpoint in ("top5","top10","top20"):
            item=endpoint_results.get(endpoint,{})
            for field in ("mean_paired_delta_number_hits","mean_paired_delta_hit_share","block_signflip_p_raw_two_sided","holm_p"):
                value=float(item.get(field,float("nan")))
                add(math.isfinite(value) and 0<=value<=1 if field in ("block_signflip_p_raw_two_sided","holm_p") else math.isfinite(value),"Q89 paired inference metric invalid "+endpoint+" / "+field)
            ci=item.get("bootstrap_95_percentile_ci_number_hits",[])
            add(len(ci)==2 and all(math.isfinite(float(value)) for value in ci) and float(ci[0])<=float(ci[1]),"Q89 bootstrap CI invalid "+endpoint)
        # Recompute the registered bootstrap/sign-flip inference from the frozen paired ledger.
        if paired:
            raw_pvalues=[]
            for endpoint,k in (("top5",5),("top10",10),("top20",20)):
                values=[int(row[f"paired_delta_number_hits_top{k}"]) for row in paired]
                delta=sum(values)/len(values)
                add(abs(delta-float(endpoint_results[endpoint]["mean_paired_delta_number_hits"]))<1e-12,"Q89 paired inference point estimate does not reconcile "+endpoint)
                ci=q89agg.bootstrap_ci(values,replicates=20000,block_length=7,seed=890027)
                pvalue=q89agg.block_signflip_p(values,replicates=20000,block_length=7,seed=890028)
                stored_ci=endpoint_results[endpoint]["bootstrap_95_percentile_ci_number_hits"]
                add(len(stored_ci)==2 and all(abs(float(stored_ci[index])-ci[index])<1e-12 for index in (0,1)),"Q89 bootstrap CI replay mismatch "+endpoint)
                add(abs(float(endpoint_results[endpoint]["block_signflip_p_raw_two_sided"])-pvalue)<1e-12,"Q89 block sign-flip replay mismatch "+endpoint)
                raw_pvalues.append(pvalue)
            adjusted=q89agg.holm_adjust(raw_pvalues)
            for endpoint,value in zip(("top5","top10","top20"),adjusted):
                add(abs(float(endpoint_results[endpoint]["holm_p"])-value)<1e-12,"Q89 paired Holm replay mismatch "+endpoint)
            for family,prefix in (("Q89_candidate","Q89"),("Q88_control","Q88")):
                metrics=inference.get(family,{})
                for k in (5,10,20):
                    expected=sum(int(row[f"{prefix}_number_hits_top{k}"]) for row in paired)/(5*len(paired))
                    add(abs(float(metrics.get(f"mean_number_hits_top{k}",float("nan")))-expected)<1e-12,"Q89 blind candidate metric replay mismatch "+family+" Top"+str(k))
                expected_rank=sum(int(row[f"{prefix}_rank_sum"]) for row in paired)/(5*len(paired))
                add(abs(float(metrics.get("mean_rank_of_actual_numbers",float("nan")))-expected_rank)<1e-12,"Q89 blind candidate rank metric replay mismatch "+family)
    except Exception as exc:
        fail(errors,"Q89 paired inference validation exception: "+str(exc))

    if errors:
        return errors
    return []

def main():
    errors=validate_q89()
    if errors:
        raise SystemExit("Q89_ACCEPTANCE_BLOCKED: "+ "; ".join(errors[:40]))
    print("Q89_ACCEPTANCE_VALIDATED: all formula×split metrics, Holm family, target cutoffs, frozen candidates, blind paired ledger and inference reconcile.")

if __name__=="__main__":
    main()
