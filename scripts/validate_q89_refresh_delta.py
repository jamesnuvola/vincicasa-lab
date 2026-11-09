#!/usr/bin/env python3
"""Fail-closed acceptance validator for the Q89 2026-11-08 incremental refresh."""
from __future__ import annotations
import csv,gzip,hashlib,json,math
from pathlib import Path
import sonar_q89_common as q89

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
ARCHIVE=ROOT/"data/storico_daily.csv"
REPORT_PATH=OUT/"q89_refresh_20261108_report.json"
MANIFEST_PATH=OUT/"q89_refresh_20261108_manifest.json"
LEDGER_PATH=OUT/"q89_refresh_20261108_target_delta_ledger.csv"
SHORTLIST_PATH=OUT/"q89_refresh_20261108_candidate_shortlist.csv"
SELECTION_PATH=OUT/"q89_refresh_20261108_candidate_selection.json"
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
        raw_archive=ARCHIVE.read_bytes()
        archive_sha256=hashlib.sha256(raw_archive).hexdigest()
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
    if errors:
        print("Q89_REFRESH_ACCEPTANCE_FAILURES_BEGIN")
        for error in errors: print(error)
        print("Q89_REFRESH_ACCEPTANCE_FAILURES_END")
        raise SystemExit("Q89_REFRESH_ACCEPTANCE_BLOCKED: "+str(len(errors))+" validation errors")
    print("Q89_REFRESH_ACCEPTANCE_PASS: archive, split, formula shards, target cutoffs, Discovery/Validation freeze and Holm family reconciled")
    return []

if __name__=="__main__":
    validate()
