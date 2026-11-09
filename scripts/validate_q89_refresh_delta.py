#!/usr/bin/env python3
"""Fail-closed acceptance validator for the Q89 2026-11-08 incremental refresh."""
from __future__ import annotations
import csv,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_q89_common as q89

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
ARCHIVE=ROOT/"data/storico_daily.csv"
REPORT_PATH=OUT/"q89_refresh_20261108_report.json"
MANIFEST_PATH=OUT/"q89_refresh_20261108_manifest.json"
LEDGER_PATH=OUT/"q89_refresh_20261108_target_delta_ledger.csv"
SHORTLIST_PATH=OUT/"q89_refresh_20261108_candidate_shortlist.csv"
SELECTION_PATH=OUT/"q89_refresh_20261108_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q89_refresh_20261108_selected_candidate_blind_ledger.csv"
EXPECTED_SHA1="77ca692a6082809fcc6c471501617433ec7c36cf"
EXPECTED_SHA256=""

def fail(errors,message):
    errors.append(message)

def git_blob_sha1(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def parse_formula_id(fid):
    if not isinstance(fid,str) or not fid.startswith("P9_"):
        raise ValueError("formula ID prefix mismatch")
    columns=tuple(int(value) for value in fid[3:].split("_"))
    if len(columns)!=9 or tuple(sorted(set(columns)))!=columns or columns[0]<0 or columns[-1]>=27:
        raise ValueError("formula ID indices are not canonical")
    if "P9_"+"_".join(f"{value:02d}" for value in columns)!=fid:
        raise ValueError("formula ID canonicalization mismatch")
    return columns

def validate():
    errors=[]
    try:
        report=json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        manifest=json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        selection=json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
        with SHORTLIST_PATH.open(newline="",encoding="utf-8-sig") as handle:
            shortlist_fields=csv.DictReader(handle).fieldnames
            shortlist=list(csv.DictReader(handle))
        with LEDGER_PATH.open(newline="",encoding="utf-8-sig") as handle:
            ledger_fields=csv.DictReader(handle).fieldnames
            ledger=list(csv.DictReader(handle))
        with PAIRED_LEDGER_PATH.open(newline="",encoding="utf-8-sig") as handle:
            paired_fields=csv.DictReader(handle).fieldnames
            paired=list(csv.DictReader(handle))
        raw_archive=ARCHIVE.read_bytes()
        archive_sha256=hashlib.sha256(raw_archive).hexdigest()
        with ARCHIVE.open(newline="",encoding="utf-8-sig") as handle:
            archive_rows=list(csv.DictReader(handle))
        dates=[row["data"] for row in archive_rows]
        draws=[[int(row[f"n{i}"]) for i in range(1,6)] for row in archive_rows]
    except Exception as exc:
        return ["Q89 refresh required output/archive unreadable: "+str(exc)]
    add=lambda condition,message: fail(errors,message) if not condition else None
    add(git_blob_sha1(raw_archive)==EXPECTED_SHA1,"canonical 2026-11-08 archive Git blob SHA1 mismatch")
    add(report.get("task_id")=="Q89_REFRESH_2026_11_08","Q89 refresh task identity mismatch")
    add(report.get("status")=="AGGREGATED_PENDING_ACCEPTANCE_VALIDATION","Q89 refresh report status mismatch")
    add(report.get("review_status")=="PENDING_HUMAN_REVIEW_INTEGRATION","Q89 refresh human-review guard missing")
    add(report.get("protocol_id")=="Q89-nine-feature-incremental-refresh-2026-11-08","Q89 refresh protocol identity mismatch")
    add(report.get("source_archive_sha256")==archive_sha256 and manifest.get("source_archive_sha256")==archive_sha256,"Q89 refresh archive SHA256 mismatch")
    add(report.get("source_archive_git_blob_sha1")==EXPECTED_SHA1 and manifest.get("source_archive_git_blob_sha1")==EXPECTED_SHA1,"Q89 refresh archive blob SHA1 mismatch")
    add(report.get("source_archive_main_commit")=="6cca9022d4311a3f9aba2925fce8c653dc6b63ab","Q89 refresh canonical main commit mismatch")
    add(report.get("target_count")==3402 and report.get("last_date")=="2026-11-08" and report.get("scored_targets")==3352,"Q89 refresh archive dimensions/date mismatch")
    add(report.get("formula_count")==4_686_825 and report.get("formula_size")==9 and report.get("feature_count")==27,"Q89 refresh formula universe mismatch")
    add(report.get("shard_count")==15 and report.get("shard_formula_count")==312455,"Q89 refresh shard layout mismatch")
    add(report.get("split_counts")=={"discovery":2012,"validation":670,"blind_oos":670},"Q89 refresh chronological split totals mismatch")
    add(report.get("metrics_rows")==14_060_475 and report.get("delta_shard_rows")==4_686_825,"Q89 refresh metric row dimensions mismatch")
    add(report.get("multiple_testing",{}).get("method")=="Global Holm-Bonferroni" and report.get("multiple_testing",{}).get("test_count")==42_181_425,"Q89 refresh Holm family/method mismatch")
    holm_count=report.get("multiple_testing",{}).get("holm_adjusted_formula_split_rows_below_0_05")
    min_holm=report.get("multiple_testing",{}).get("minimum_holm_p_max_endpoint_family")
    add(isinstance(holm_count,int) and 0<=holm_count<=14_060_475,"Q89 refresh Holm count summary invalid")
    add(isinstance(min_holm,(int,float)) and math.isfinite(min_holm) and 0<=min_holm<=1,"Q89 refresh minimum Holm summary invalid")
    add(manifest.get("task_id")=="Q89_REFRESH_2026_11_08" and manifest.get("formula_count")==4_686_825 and manifest.get("metrics_rows")==4_686_825,"Q89 refresh manifest identity/dimensions mismatch")
    parts=manifest.get("parts",[])
    add(len(parts)==15 and manifest.get("part_count")==15 and report.get("shard_count")==len(parts),"Q89 refresh delta shard manifest count mismatch")
    if len(parts)==15:
        for shard,part in enumerate(parts):
            start,end=q89.shard_bounds(shard)
            path=ROOT/part.get("path","")
            add(part.get("shard_index")==shard and part.get("formula_rank_start_inclusive")==start and part.get("formula_rank_end_exclusive")==end,"Q89 refresh shard boundary mismatch")
            add(part.get("rows")==312455,"Q89 refresh shard row count declaration mismatch")
            if not path.is_file():
                fail(errors,"Q89 refresh delta shard missing: "+str(path));continue
            raw=path.read_bytes()
            add(len(raw)==int(part.get("bytes",-1)) and hashlib.sha256(raw).hexdigest()==part.get("sha256"),"Q89 refresh delta shard byte/SHA mismatch")
            expected=q89.iter_formula_slice(start,end)
            local=0
            try:
                with gzip.open(path,"rt",newline="",encoding="utf-8-sig") as handle:
                    reader=csv.DictReader(handle)
                    required={"formula_rank","formula_id"}
                    add(required.issubset(set(reader.fieldnames or [])),"Q89 refresh delta shard schema incomplete")
                    for row in reader:
                        columns=next(expected,None)
                        if columns is None:
                            fail(errors,"Q89 refresh delta shard has extra rows");break
                        add(int(row.get("formula_rank",-1))==start+local and row.get("formula_id")==q89.formula_id(columns),"Q89 refresh delta formula rank/ID coverage mismatch")
                        local+=1
            except Exception as exc:
                fail(errors,"Q89 refresh delta shard read exception: "+str(exc))
            add(local==312455 and next(expected,None) is None,"Q89 refresh delta shard exact formula coverage mismatch")
    required_ledger={"target_offset","archive_index","target_date","cutoff_date","prior_draws","actual_quintet","split_movement"}
    add(required_ledger.issubset(set(ledger_fields or [])) and len(ledger)==3,"Q89 refresh target-delta ledger schema/count mismatch")
    expected_ledger=[
        (2011,2061,"2023-03-09","2023-03-08","5 19 32 33 37","old_validation_to_new_discovery"),
        (2681,2731,"2025-01-07","2025-01-06","5 17 18 23 33","old_blind_to_new_validation"),
        (3351,3401,"2026-11-08","2026-11-07","3 7 10 16 27","new_target_in_new_blind_oos")]
    if len(ledger)==3:
        for row,expected in zip(ledger,expected_ledger):
            actual=(int(row["target_offset"]),int(row["archive_index"]),row["target_date"],row["cutoff_date"],row["actual_quintet"],row["split_movement"])
            add(actual==expected,"Q89 refresh target offset/date/cutoff/quintet mismatch")
            add(int(row["prior_draws"])==expected[1],"Q89 refresh target prior_draws mismatch")
    add(selection.get("task_id")=="Q89_REFRESH_2026_11_08" and selection.get("status")=="CANDIDATE_FROZEN_BEFORE_BLIND_OOS","Q89 refresh candidate selection status mismatch")
    add(selection.get("blind_oos_used_for_selection") is False and selection.get("selected_candidate_ids_frozen") is True,"Q89 refresh blind-selection leakage guard missing")
    required_shortlist={"formula_id","features","discovery_rank","discovery_mean_number_hits_top5","discovery_mean_rank_of_actual_numbers","validation_mean_number_hits_top5","validation_mean_rank_of_actual_numbers","validation_selection_rank","selected"}
    add(len(shortlist)==100 and required_shortlist.issubset(set(shortlist_fields or [])),"Q89 refresh shortlist schema/count mismatch")
    if len(shortlist)==100:
        ids=[row["formula_id"] for row in shortlist]
        add(len(set(ids))==100 and all(fid.startswith("P9_") for fid in ids),"Q89 refresh shortlist formula IDs invalid/duplicated")
        add(sorted(int(row["discovery_rank"]) for row in shortlist)==list(range(1,101)),"Q89 refresh Discovery rank coverage mismatch")
        add(sorted(int(row["validation_selection_rank"]) for row in shortlist)==list(range(1,101)),"Q89 refresh Validation rank coverage mismatch")
        selected_rows=[row for row in shortlist if int(row["selected"])==1]
        add(len(selected_rows)==1,"Q89 refresh shortlist must select exactly one Validation candidate")
        selected_id=selected_rows[0]["formula_id"] if selected_rows else None
        add(selection.get("Q89_candidate",{}).get("formula_id")==selected_id,"Q89 refresh selected formula ID does not reconcile")
        add(selection.get("top100_discovery_candidates")==ids,"Q89 refresh Discovery top100 IDs do not reconcile")
    add(report.get("candidate_selection",{}).get("selected_candidate_id")==selection.get("Q89_candidate",{}).get("formula_id"),"Q89 refresh report/selection candidate ID mismatch")
    add(report.get("candidate_selection",{}).get("paired_blind_ledger_rows")==670,"Q89 refresh paired Blind OOS ledger row count declaration mismatch")
    add(report.get("supplemental_pairing_protocol_id")=="Q89-refresh-paired-blind-ledger-supplement-2026-11-09" and manifest.get("supplemental_pairing_protocol_id")=="Q89-refresh-paired-blind-ledger-supplement-2026-11-09","Q89 refresh supplemental pairing protocol ID mismatch")
    add(selection.get("Q89_candidate",{}).get("blind_oos_ledger_path")==str(PAIRED_LEDGER_PATH.relative_to(ROOT)),"Q89 refresh selection paired-ledger path mismatch")
    add(report.get("outputs",{}).get("selected_candidate_blind_ledger")==str(PAIRED_LEDGER_PATH.relative_to(ROOT)),"Q89 refresh report paired-ledger path mismatch")
    paired_manifest=manifest.get("supplemental_outputs",{}).get("selected_candidate_blind_ledger",{})
    paired_raw=PAIRED_LEDGER_PATH.read_bytes()
    add(paired_manifest.get("path")==str(PAIRED_LEDGER_PATH.relative_to(ROOT)) and paired_manifest.get("rows")==670,"Q89 refresh supplemental paired-ledger manifest identity/count mismatch")
    add(paired_manifest.get("bytes")==len(paired_raw) and paired_manifest.get("sha256")==hashlib.sha256(paired_raw).hexdigest(),"Q89 refresh supplemental paired-ledger byte/SHA mismatch")
    required_paired={"target_date","cutoff_date","prior_draws","actual_quintet","Q89_formula_id","Q89_actual_number_ranks",
        "Q89_number_hits_top5","Q89_number_hits_top10","Q89_number_hits_top20","Q89_all5_top5","Q89_all5_top10","Q89_all5_top20","Q89_rank_sum"}
    add(len(paired)==670 and required_paired.issubset(set(paired_fields or [])),"Q89 refresh paired Blind OOS ledger schema/count mismatch")
    try:
        scored=len(draws)-q80.MIN_HISTORY
        validation_end=math.ceil(.80*scored)
        expected_blind_dates=[dates[q80.MIN_HISTORY+offset] for offset in range(validation_end,scored)]
        add([row.get("target_date") for row in paired]==expected_blind_dates,"Q89 refresh paired Blind OOS target date coverage/order mismatch")
        archive_index={date:index for index,date in enumerate(dates)}
        selected_id=selection["Q89_candidate"]["formula_id"]
        selected_columns=parse_formula_id(selected_id)
        feature_stack=q81.build_feature_stack(draws)
        add(feature_stack.shape==(scored,40,27),"Q89 refresh paired feature stack dimensions mismatch")
        sums={"number_hits_top5":0,"number_hits_top10":0,"number_hits_top20":0,
            "all5_top5":0,"all5_top10":0,"all5_top20":0,"rank_sum":0}
        for row in paired:
            date=row.get("target_date","")
            index=archive_index.get(date)
            if index is None or index<q80.MIN_HISTORY:
                fail(errors,"Q89 refresh paired ledger target missing/too early: "+date);continue
            add(row.get("cutoff_date")==dates[index-1] and int(row.get("prior_draws",-1))==index,"Q89 refresh paired strict-prefix cutoff mismatch at "+date)
            add(row.get("actual_quintet")==" ".join(map(str,draws[index])),"Q89 refresh paired actual quintet mismatch at "+date)
            add(row.get("Q89_formula_id")==selected_id,"Q89 refresh paired candidate ID changed on Blind OOS ledger")
            actual_indices=np.asarray(draws[index],dtype=np.int64)-1
            score=feature_stack[index-q80.MIN_HISTORY][:,selected_columns].mean(axis=1)
            order=np.argsort(-score,kind="stable")
            ranks=np.empty(40,dtype=np.int16)
            ranks[order]=np.arange(1,41,dtype=np.int16)
            expected_ranks=ranks[actual_indices].astype(int).tolist()
            try:
                observed_ranks=json.loads(row["Q89_actual_number_ranks"])
            except Exception as exc:
                fail(errors,"Q89 refresh paired rank JSON invalid at "+date+": "+str(exc));continue
            add(observed_ranks==expected_ranks,"Q89 refresh paired rank replay mismatch at "+date)
            hits={k:sum(value<=k for value in observed_ranks) for k in (5,10,20)}
            all5={k:int(all(value<=k for value in observed_ranks)) for k in (5,10,20)}
            for k in (5,10,20):
                add(int(row[f"Q89_number_hits_top{k}"])==hits[k],"Q89 refresh paired number-hit count mismatch at "+date)
                add(int(row[f"Q89_all5_top{k}"])==all5[k],"Q89 refresh paired all-five indicator mismatch at "+date)
                sums[f"number_hits_top{k}"]+=hits[k]
                sums[f"all5_top{k}"]+=all5[k]
            add(int(row["Q89_rank_sum"])==sum(observed_ranks),"Q89 refresh paired rank-sum mismatch at "+date)
            sums["rank_sum"]+=sum(observed_ranks)
        paired_means={"mean_number_hits_top5":sums["number_hits_top5"]/(5*len(paired)),
            "mean_number_hits_top10":sums["number_hits_top10"]/(5*len(paired)),
            "mean_number_hits_top20":sums["number_hits_top20"]/(5*len(paired)),
            "all5_top5_rate":sums["all5_top5"]/len(paired),"all5_top10_rate":sums["all5_top10"]/len(paired),
            "all5_top20_rate":sums["all5_top20"]/len(paired),"mean_rank_of_actual_numbers":sums["rank_sum"]/(5*len(paired))}
        selection_metrics=selection["Q89_candidate"]["blind_oos_metrics_descriptive_only"]
        report_metrics=report.get("selected_candidate_metrics",{}).get("blind_oos_descriptive_only",{})
        for field,value in paired_means.items():
            add(math.isfinite(float(selection_metrics.get(field,float("nan")))) and abs(float(selection_metrics[field])-value)<1e-12,"Q89 refresh selected Blind OOS metrics do not reconcile to paired ledger: "+field)
            add(math.isfinite(float(report_metrics.get(field,float("nan")))) and abs(float(report_metrics[field])-value)<1e-12,"Q89 refresh report Blind OOS metrics do not reconcile to paired ledger: "+field)
    except Exception as exc:
        fail(errors,"Q89 refresh paired Blind OOS ledger validation exception: "+str(exc))

    if errors:
        print("Q89_REFRESH_ACCEPTANCE_FAILURES_BEGIN")
        for error in errors: print(error)
        print("Q89_REFRESH_ACCEPTANCE_FAILURES_END")
        raise SystemExit("Q89_REFRESH_ACCEPTANCE_BLOCKED: "+str(len(errors))+" validation errors")
    print("Q89_REFRESH_ACCEPTANCE_PASS: archive, split, formula shards, target cutoffs, Discovery/Validation freeze and Holm family reconciled")
    return []

if __name__=="__main__":
    validate()
