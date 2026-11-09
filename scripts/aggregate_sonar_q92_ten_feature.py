#!/usr/bin/env python3
"""Aggregate, globally Holm-correct and freeze the preregistered Q92 ten-feature walk-forward."""
from __future__ import annotations
import csv, gzip, hashlib, heapq, io, json, math
from pathlib import Path
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_q89_common as q89
import sonar_q92_common as q92
import sonar_q92_aggregate_common as q92a
import sonar_q92_null_calibration as q92null

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
ARCHIVE=ROOT/"data/storico_daily.csv"
SHARD_INPUT_DIR=OUT/"q92_shards"
METRICS_PART_DIR=OUT/"q92_20261108_metrics_parts"
TARGET_PART_DIR=OUT/"q92_20261108_target_ledger_parts"
REPORT_PATH=OUT/"q92_20261108_report.json"
MANIFEST_PATH=OUT/"q92_20261108_manifest.json"
SHORTLIST_PATH=OUT/"q92_20261108_candidate_shortlist.csv"
SELECTION_PATH=OUT/"q92_20261108_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q92_20261108_paired_blind_ledger.csv"
INFERENCE_PATH=OUT/"q92_20261108_paired_inference.json"
Q89_REPORT_PATH=OUT/"q89_refresh_20261108_report.json"
Q89_MANIFEST_PATH=OUT/"q89_refresh_20261108_manifest.json"
Q89_SELECTION_PATH=OUT/"q89_refresh_20261108_candidate_selection.json"
Q89_PAIRED_LEDGER_PATH=OUT/"q89_refresh_20261108_selected_candidate_blind_ledger.csv"
PREREG_PATH=OUT/"q92_preregistration_2026-11-09.json"
SPLITS=("discovery","validation","blind_oos")
SPLIT_COUNTS={"discovery":2012,"validation":670,"blind_oos":670}
TOTAL=q92.TOTAL_FORMULA_COUNT
SHARDS=q92.SHARD_COUNT
SHARD_SIZE=q92.SHARD_SIZE
EXPECTED_ARCHIVE_SHA1="77ca692a6082809fcc6c471501617433ec7c36cf"
EXPECTED_ARCHIVE_SHA256="5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b"
EXPECTED_ARCHIVE_MAIN_COMMIT="6cca9022d4311a3f9aba2925fce8c653dc6b63ab"
EXPECTED_ARCHIVE_COUNT=3402
EXPECTED_ARCHIVE_LAST_DATE="2026-11-08"
EXPECTED_BLIND_TARGETS=670
ENDPOINTS=(5,10,20)
METRIC_FIELDS=("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
    "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers",
    "p_top5_exact_hypergeom_sum","p_top10_exact_hypergeom_sum","p_top20_exact_hypergeom_sum")

def fail(message):
    raise SystemExit("Q92_AGGREGATION_BLOCKED: "+str(message))

def git_blob_sha1(data):
    return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()

def integer_from_mean(value,denominator,label):
    raw=float(value)*int(denominator)
    rounded=int(round(raw))
    if not math.isfinite(raw) or abs(raw-rounded)>2e-6:
        fail(label+" cannot be reconstructed as an exact integer count")
    return rounded

def invert_id(fid):
    return bytes(255-ord(character) for character in fid)

def metric_summary(row):
    result={}
    for field in METRIC_FIELDS:
        value=float(row[field])
        if not math.isfinite(value):
            fail("non-finite metric field "+field)
        result[field]=value
    return result

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail("required JSON unreadable "+str(path)+": "+str(exc))

def read_csv_fields_rows(path):
    with path.open(newline="",encoding="utf-8-sig") as handle:
        reader=csv.DictReader(handle)
        fields=reader.fieldnames
        rows=list(reader)
    return fields,rows

def write_gzip_csv(path,fieldnames,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0,compresslevel=6) as compressed:
            with io.TextIOWrapper(compressed,encoding="utf-8",newline="") as text:
                writer=csv.DictWriter(text,fieldnames=fieldnames,lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)

def sha256_file(path):
    digest=hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda:handle.read(1<<20),b""):
            digest.update(block)
    return digest.hexdigest()

def sha256_memmap(values,chunk_bytes=8<<20):
    view=np.asarray(values).view(np.uint8)
    digest=hashlib.sha256()
    for start in range(0,view.size,int(chunk_bytes)):
        digest.update(memoryview(view[start:min(start+int(chunk_bytes),view.size)]))
    return digest.hexdigest()

def load_archive():
    raw=ARCHIVE.read_bytes()
    archive_sha256=hashlib.sha256(raw).hexdigest()
    archive_sha1=git_blob_sha1(raw)
    if archive_sha1!=EXPECTED_ARCHIVE_SHA1 or archive_sha256!=EXPECTED_ARCHIVE_SHA256:
        fail("canonical 2026-11-08 archive SHA mismatch")
    dates,draws=q80.load_archive()
    if len(draws)!=EXPECTED_ARCHIVE_COUNT or dates[0]!="2017-07-17" or dates[-1]!=EXPECTED_ARCHIVE_LAST_DATE:
        fail("canonical archive dimensions/date mismatch")
    if dates!=sorted(dates) or len(set(dates))!=len(dates):
        fail("canonical archive dates not unique and ascending")
    for values in draws:
        # q80.load_archive currently returns tuples; normalize the container before
        # comparing sorted values so tuple/list type differences cannot reject a
        # valid canonical quintet.
        quintet=tuple(values)
        if len(quintet)!=5 or quintet!=tuple(sorted(quintet)) or len(set(quintet))!=5 or any(int(v)<1 or int(v)>40 for v in quintet):
            fail("canonical archive quintet invalid")
    return dates,draws,archive_sha256,archive_sha1

def validate_q89_control(archive_sha256,dates,draws,feature_stack):
    report=read_json(Q89_REPORT_PATH)
    manifest=read_json(Q89_MANIFEST_PATH)
    selection=read_json(Q89_SELECTION_PATH)
    fields,paired=read_csv_fields_rows(Q89_PAIRED_LEDGER_PATH)
    if report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or report.get("task_id")!="Q89_REFRESH_2026_11_08":
        fail("Q89 same-archive control report is not accepted")
    if report.get("source_archive_sha256")!=archive_sha256 or report.get("target_count")!=EXPECTED_ARCHIVE_COUNT or report.get("split_counts")!=SPLIT_COUNTS or report.get("source_archive_main_commit")!=EXPECTED_ARCHIVE_MAIN_COMMIT:
        fail("Q89 same-archive report identity/split/canonical commit mismatch")
    if manifest.get("source_archive_sha256")!=archive_sha256 or manifest.get("task_id")!="Q89_REFRESH_2026_11_08":
        fail("Q89 same-archive manifest identity mismatch")
    if selection.get("status")!="CANDIDATE_FROZEN_BEFORE_BLIND_OOS" or selection.get("blind_oos_used_for_selection") is not False or selection.get("selected_candidate_ids_frozen") is not True:
        fail("Q89 control candidate selection freeze/leakage guard mismatch")
    q89_id=selection.get("Q89_candidate",{}).get("formula_id")
    if not isinstance(q89_id,str) or not q89_id.startswith("P9_") or report.get("candidate_selection",{}).get("selected_candidate_id")!=q89_id:
        fail("Q89 control formula ID does not reconcile to the accepted report")
    q89_columns=tuple(int(value) for value in q89_id[3:].split("_"))
    if len(q89_columns)!=9 or tuple(sorted(set(q89_columns)))!=q89_columns or q89_columns[0]<0 or q89_columns[-1]>=27:
        fail("Q89 control formula columns are not canonical")
    if "P9_"+"_".join(f"{value:02d}" for value in q89_columns)!=q89_id:
        fail("Q89 control formula ID canonicalization mismatch")
    expected_dates=[dates[index] for index in range(q80.MIN_HISTORY+math.ceil(.80*(len(draws)-q80.MIN_HISTORY)),len(draws))]
    if len(paired)!=EXPECTED_BLIND_TARGETS or [row.get("target_date") for row in paired]!=expected_dates:
        fail("Q89 paired blind ledger target date coverage/order mismatch")
    required={"target_date","cutoff_date","prior_draws","actual_quintet","Q89_formula_id","Q89_actual_number_ranks",
        "Q89_number_hits_top5","Q89_number_hits_top10","Q89_number_hits_top20","Q89_all5_top5","Q89_all5_top10","Q89_all5_top20","Q89_rank_sum"}
    if not required.issubset(set(fields or [])):
        fail("Q89 paired blind ledger schema incomplete")
    supplemental=manifest.get("supplemental_outputs",{}).get("selected_candidate_blind_ledger",{})
    raw=Q89_PAIRED_LEDGER_PATH.read_bytes()
    if supplemental.get("path")!=str(Q89_PAIRED_LEDGER_PATH.relative_to(ROOT)) or supplemental.get("rows")!=EXPECTED_BLIND_TARGETS:
        fail("Q89 paired blind ledger manifest path/count mismatch")
    if supplemental.get("bytes")!=len(raw) or supplemental.get("sha256")!=hashlib.sha256(raw).hexdigest():
        fail("Q89 paired blind ledger manifest byte/SHA mismatch")
    date_to_row={row["target_date"]:row for row in paired}
    scored=len(draws)-q80.MIN_HISTORY
    for target_offset,target_index in enumerate(range(q80.MIN_HISTORY,len(draws))):
        if q80.split_name(target_offset,scored)!="blind_oos":
            continue
        date=dates[target_index]
        row=date_to_row.get(date)
        if row is None:
            fail("Q89 paired blind ledger target missing "+date)
        if row.get("cutoff_date")!=dates[target_index-1] or int(row.get("prior_draws",-1))!=target_index:
            fail("Q89 paired blind strict-prefix cutoff mismatch "+date)
        if row.get("actual_quintet")!=" ".join(map(str,draws[target_index])) or row.get("Q89_formula_id")!=q89_id:
            fail("Q89 paired blind target/formula mismatch "+date)
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        scores=feature_stack[target_offset][:,q89_columns].mean(axis=1)
        order=np.argsort(-scores,kind="stable")
        ranks=np.empty(40,dtype=np.int16)
        ranks[order]=np.arange(1,41,dtype=np.int16)
        expected_ranks=ranks[actual_indices].astype(int).tolist()
        observed=json.loads(row["Q89_actual_number_ranks"])
        if observed!=expected_ranks:
            fail("Q89 paired blind rank replay mismatch "+date)
        hits={k:sum(value<=k for value in observed) for k in (5,10,20)}
        all5={k:int(all(value<=k for value in observed)) for k in (5,10,20)}
        for k in (5,10,20):
            if int(row[f"Q89_number_hits_top{k}"])!=hits[k] or int(row[f"Q89_all5_top{k}"])!=all5[k]:
                fail("Q89 paired blind hit replay mismatch "+date)
        if int(row["Q89_rank_sum"])!=sum(observed):
            fail("Q89 paired blind rank-sum replay mismatch "+date)
    return report,selection,paired,q89_id,q89_columns

def validate_shard_report(shard,archive_sha256,dates):
    start,end=q92.shard_bounds(shard)
    report_path=SHARD_INPUT_DIR/f"shard_{shard}_report.json"
    report=read_json(report_path)
    expected={
        "task_id":"Q92","status":"SHARD_COMPLETE_NOT_TASK_COMPLETE","source_archive_sha256":archive_sha256,
        "target_count":EXPECTED_ARCHIVE_COUNT,"scored_targets":EXPECTED_ARCHIVE_COUNT-q80.MIN_HISTORY,
        "feature_count":27,"formula_count":SHARD_SIZE,"total_formula_count":TOTAL,"formula_size":10,
        "formula_count_check":math.comb(27,10),"shard_index":shard,"shard_count":SHARDS,
        "shard_formula_start_inclusive":start,"shard_formula_end_exclusive":end,"shard_formula_count":SHARD_SIZE,
        "formula_batch_size":2048,"formula_batch_count":275,"metrics_rows":SHARD_SIZE*3,
        "target_ledger_rows":EXPECTED_ARCHIVE_COUNT-q80.MIN_HISTORY,"split_counts":SPLIT_COUNTS}
    for key,value in expected.items():
        if report.get(key)!=value:
            fail("Q92 shard report field mismatch shard "+str(shard)+" field "+key)
    if report.get("first_date")!=dates[0] or report.get("last_date")!=dates[-1]:
        fail("Q92 shard archive date bounds mismatch shard "+str(shard))
    if report.get("source_checkout_sha") is None or report.get("source_checkout_sha")=="":
        fail("Q92 shard source checkout SHA missing shard "+str(shard))
    if report.get("source_code_sha256")!=q92.source_code_hashes(ROOT):
        fail("Q92 shard source-code hash manifest mismatch shard "+str(shard))
    if report.get("multiple_testing",{}).get("method")!="GLOBAL_HOLM_PENDING_AGGREGATION" or report.get("multiple_testing",{}).get("test_count")!=SHARD_SIZE*3*3:
        fail("Q92 shard raw Holm family declaration mismatch shard "+str(shard))
    if report.get("multiple_testing",{}).get("p_value_method")!="discrete upper-tail convolution of iid Hypergeometric(40,k,5) number-hit counts; deterministic float64 under independent uniform 5-of-40 draws":
        fail("Q92 shard discrete null-calibration method mismatch shard "+str(shard))
    batches=report.get("batch_manifest",[])
    if len(batches)!=275:
        fail("Q92 shard batch manifest count mismatch shard "+str(shard))
    for index,batch in enumerate(batches):
        if batch.get("batch_index")!=index or batch.get("formula_count")!=min(2048,SHARD_SIZE-index*2048):
            fail("Q92 shard batch manifest arithmetic mismatch shard "+str(shard))
    return report

def rank_actual_for_formula(standardized,columns,actual_indices):
    score=standardized[:,columns].mean(axis=1)
    order=np.argsort(-score,kind="stable")
    ranks=np.empty(40,dtype=np.int16)
    ranks[order]=np.arange(1,41,dtype=np.int16)
    return ranks[np.asarray(actual_indices,dtype=np.int64)].astype(int).tolist()

def expected_single_feature_ledger(standardized,actual_indices):
    scores=np.asarray(standardized,dtype=np.float64)
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    actual=ranks[np.asarray(actual_indices,dtype=np.int64),:]
    result=[]
    for column,name in enumerate(q80.FEATURE_NAMES):
        values=actual[:,column].astype(int).tolist()
        result.append({"feature":name,"ranks":values,"hits_top5":sum(v<=5 for v in values),
            "hits_top10":sum(v<=10 for v in values),"hits_top20":sum(v<=20 for v in values),"rank_sum":sum(values)})
    return result

def validate_and_persist_target_ledger_parts(dates,draws,archive_sha256,feature_stack):
    target_count=len(draws)-q80.MIN_HISTORY
    split_for_offset=[q80.split_name(offset,target_count) for offset in range(target_count)]
    manifest_parts=[]
    reference_single_feature=None
    for shard in range(SHARDS):
        start,end=q92.shard_bounds(shard)
        raw_path=SHARD_INPUT_DIR/f"shard_{shard}_target_ledger.csv"
        if not raw_path.is_file():
            fail("missing Q92 target ledger shard "+str(shard))
        fields,rows=read_csv_fields_rows(raw_path)
        required={"target_date","cutoff_date","prior_draws","actual_quintet","status","formula_count_tested","best_formula_id",
            "best_formula_features","best_actual_number_ranks","best_number_hits_top5","best_number_hits_top10","best_number_hits_top20",
            "best_rank_sum","single_feature_rank_ledger"}
        if len(rows)!=target_count or not required.issubset(set(fields or [])):
            fail("Q92 target ledger shard schema/count mismatch shard "+str(shard))
        for offset,row in enumerate(rows):
            target_index=q80.MIN_HISTORY+offset
            actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
            if row.get("target_date")!=dates[target_index] or row.get("cutoff_date")!=dates[target_index-1] or int(row.get("prior_draws",-1))!=target_index:
                fail("Q92 target ledger strict-prefix target/cutoff mismatch shard "+str(shard)+" offset "+str(offset))
            if row.get("actual_quintet")!=" ".join(map(str,draws[target_index])) or row.get("status")!="SCORED" or int(row.get("formula_count_tested",-1))!=TOTAL:
                fail("Q92 target ledger target outcome/status/formula count mismatch shard "+str(shard)+" offset "+str(offset))
            fid=row.get("best_formula_id","")
            columns=q92a.parse_formula_id(fid)
            formula_rank=q92.formula_rank(columns)
            if not start<=formula_rank<end:
                fail("Q92 retrospective best formula outside shard interval shard "+str(shard)+" offset "+str(offset))
            observed_ranks=json.loads(row["best_actual_number_ranks"])
            expected_ranks=rank_actual_for_formula(feature_stack[offset],columns,actual_indices)
            if observed_ranks!=expected_ranks:
                fail("Q92 retrospective best-formula rank replay mismatch shard "+str(shard)+" offset "+str(offset))
            hits={k:sum(value<=k for value in observed_ranks) for k in (5,10,20)}
            if int(row["best_number_hits_top5"])!=hits[5] or int(row["best_number_hits_top10"])!=hits[10] or int(row["best_number_hits_top20"])!=hits[20] or int(row["best_rank_sum"])!=sum(observed_ranks):
                fail("Q92 retrospective best-formula metric replay mismatch shard "+str(shard)+" offset "+str(offset))
            single=json.loads(row["single_feature_rank_ledger"])
            if reference_single_feature is None and shard==0:
                reference_single_feature=[]
            expected_single=expected_single_feature_ledger(feature_stack[offset],actual_indices)
            if single!=expected_single:
                fail("Q92 target ledger 27-feature prior-only rank replay mismatch shard "+str(shard)+" offset "+str(offset))
            if shard==0:
                reference_single_feature.append(single)
            elif single!=reference_single_feature[offset]:
                fail("Q92 target ledger single-feature ranks differ across shards shard "+str(shard)+" offset "+str(offset))
        out_path=TARGET_PART_DIR/f"shard_{shard}_target_ledger.csv.gz"
        write_gzip_csv(out_path,fields,rows)
        manifest_parts.append({"shard_index":shard,"path":str(out_path.relative_to(ROOT)),"rows":len(rows),
            "formula_rank_start_inclusive":start,"formula_rank_end_exclusive":end,"bytes":out_path.stat().st_size,"sha256":sha256_file(out_path),
            "source_artifact_sha256":hashlib.sha256(raw_path.read_bytes()).hexdigest()})
    if len(reference_single_feature or [])!=target_count:
        fail("Q92 target ledger reference single-feature coverage incomplete")
    return manifest_parts

def build_paired_blind_ledger(selection,dates,draws,feature_stack,q89_selection,q89_paired_rows,q89_id,q89_columns):
    q92_id=selection["Q92_candidate"]["formula_id"]
    q92_columns=q92a.parse_formula_id(q92_id)
    q89_by_date={row["target_date"]:row for row in q89_paired_rows}
    scored=len(draws)-q80.MIN_HISTORY
    rows=[]
    endpoint_deltas={"top5_hit_share":[],"top10_hit_share":[],"top20_hit_share":[],"mean_rank_actual_numbers":[]}
    for target_offset,target_index in enumerate(range(q80.MIN_HISTORY,len(draws))):
        if q80.split_name(target_offset,scored)!="blind_oos":
            continue
        date=dates[target_index]
        control=q89_by_date.get(date)
        if control is None:
            fail("paired Blind OOS Q89 control target missing "+date)
        cutoff=dates[target_index-1]
        actual=" ".join(map(str,draws[target_index]))
        if control.get("cutoff_date")!=cutoff or int(control.get("prior_draws",-1))!=target_index or control.get("actual_quintet")!=actual or control.get("Q89_formula_id")!=q89_id:
            fail("paired Blind OOS Q89 control identity mismatch "+date)
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        standardized=feature_stack[target_offset]
        ranks92=rank_actual_for_formula(standardized,q92_columns,actual_indices)
        ranks89=rank_actual_for_formula(standardized,q89_columns,actual_indices)
        if json.loads(control["Q89_actual_number_ranks"])!=ranks89:
            fail("paired Blind OOS Q89 control rank replay mismatch "+date)
        hits92={k:sum(value<=k for value in ranks92) for k in (5,10,20)}
        hits89={k:sum(value<=k for value in ranks89) for k in (5,10,20)}
        all592={k:int(all(value<=k for value in ranks92)) for k in (5,10,20)}
        all589={k:int(all(value<=k for value in ranks89)) for k in (5,10,20)}
        delta={k:hits92[k]-hits89[k] for k in (5,10,20)}
        delta_rank=sum(ranks92)-sum(ranks89)
        endpoint_deltas["top5_hit_share"].append(delta[5]/5.0)
        endpoint_deltas["top10_hit_share"].append(delta[10]/5.0)
        endpoint_deltas["top20_hit_share"].append(delta[20]/5.0)
        endpoint_deltas["mean_rank_actual_numbers"].append(delta_rank/5.0)
        rows.append({"target_date":date,"cutoff_date":cutoff,"prior_draws":target_index,"actual_quintet":actual,
            "Q92_formula_id":q92_id,"Q92_actual_number_ranks":json.dumps(ranks92,separators=(",",":")),
            "Q92_number_hits_top5":hits92[5],"Q92_number_hits_top10":hits92[10],"Q92_number_hits_top20":hits92[20],
            "Q92_all5_top5":all592[5],"Q92_all5_top10":all592[10],"Q92_all5_top20":all592[20],"Q92_rank_sum":sum(ranks92),
            "Q89_formula_id":q89_id,"Q89_actual_number_ranks":json.dumps(ranks89,separators=(",",":")),
            "Q89_number_hits_top5":hits89[5],"Q89_number_hits_top10":hits89[10],"Q89_number_hits_top20":hits89[20],
            "Q89_all5_top5":all589[5],"Q89_all5_top10":all589[10],"Q89_all5_top20":all589[20],"Q89_rank_sum":sum(ranks89),
            "delta_number_hits_top5":delta[5],"delta_number_hits_top10":delta[10],"delta_number_hits_top20":delta[20],
            "delta_hit_share_top5":delta[5]/5.0,"delta_hit_share_top10":delta[10]/5.0,"delta_hit_share_top20":delta[20]/5.0,
            "delta_rank_sum":delta_rank,"delta_mean_rank_actual_numbers":delta_rank/5.0})
    if len(rows)!=EXPECTED_BLIND_TARGETS:
        fail("paired Blind OOS ledger target count mismatch")
    with PAIRED_LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0].keys()),lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    return rows,endpoint_deltas

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    dates,draws,archive_sha256,archive_sha1=load_archive()
    prereg=read_json(PREREG_PATH)
    minimum_effect=float(prereg.get("primary_comparison",{}).get("inference",{}).get("minimum_practical_effect_size_top5",-1.0))
    if not math.isfinite(minimum_effect) or abs(minimum_effect-q92a.MINIMUM_EFFECT_SIZE_TOP5)>1e-15:
        fail("Q92 preregistered minimum Top-5 practical effect mismatch")
    scored=len(draws)-q80.MIN_HISTORY
    if scored!=3352 or SPLIT_COUNTS!={"discovery":2012,"validation":670,"blind_oos":670}:
        fail("strict-prefix target/split counts mismatch")
    feature_stack=q81.build_feature_stack(draws)
    if feature_stack.shape!=(scored,40,27):
        fail("prior-only feature stack dimensions mismatch")
    q89_report,q89_selection,q89_paired_rows,q89_id,q89_columns=validate_q89_control(archive_sha256,dates,draws,feature_stack)
    shard_reports=[]
    for shard in range(SHARDS):
        shard_reports.append(validate_shard_report(shard,archive_sha256,dates))
    source_code_hashes=shard_reports[0].get("source_code_sha256")
    if not isinstance(source_code_hashes,dict) or any(item.get("source_code_sha256")!=source_code_hashes for item in shard_reports):
        fail("Q92 shard source-code hashes differ across shard artifacts")
    source_checkout_shas=sorted({str(item.get("source_checkout_sha")) for item in shard_reports})

    tests=TOTAL*3*3
    pvalue_path=OUT/"q92_20261108_holm_vector_temp.bin"
    if pvalue_path.exists():
        pvalue_path.unlink()
    pvalues=np.memmap(pvalue_path,dtype=np.float64,mode="w+",shape=(tests,))
    candidate_pool=[]
    split_row_counts={split:0 for split in SPLITS}
    global_metric_row=0
    for shard in range(SHARDS):
        start,end=q92.shard_bounds(shard)
        metrics_path=SHARD_INPUT_DIR/f"shard_{shard}_metrics.csv"
        if not metrics_path.is_file():
            fail("missing Q92 metrics shard "+str(shard))
        with metrics_path.open(newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            required={"split","formula_id","feature_count","features","targets",*METRIC_FIELDS}
            if not required.issubset(set(reader.fieldnames or [])):
                fail("Q92 metrics shard schema incomplete shard "+str(shard))
            local_heap=[]
            local_candidate_map=None
            expected_formula_iter=None
            previous_split_index=-1
            local_row=0
            for row in reader:
                if local_row>=SHARD_SIZE*3:
                    fail("Q92 metrics shard extra rows shard "+str(shard))
                split_index=local_row//SHARD_SIZE
                local_rank=local_row%SHARD_SIZE
                split=SPLITS[split_index]
                if split_index!=previous_split_index:
                    expected_formula_iter=q92.iter_formula_slice(start,end)
                    previous_split_index=split_index
                    if split_index==1:
                        if len(local_heap)!=100:
                            fail("Q92 local Discovery top100 incomplete shard "+str(shard))
                        ordered=sorted(local_heap,key=lambda entry:(-entry[2],entry[3],entry[1]))
                        local_candidate_map={entry[1]:{"formula_id":entry[1],"features":entry[4],"formula_rank":entry[5],
                            "mean_number_hits_top5":entry[2],"mean_rank_of_actual_numbers":entry[3],
                            "discovery_local_rank":rank+1,"discovery":entry[6]} for rank,entry in enumerate(ordered)}
                        local_heap=[]
                    elif split_index==2:
                        if local_candidate_map is None or len(local_candidate_map)!=100:
                            fail("Q92 local Discovery candidate map missing shard "+str(shard))
                columns=next(expected_formula_iter,None)
                if columns is None:
                    fail("Q92 expected formula iterator ended early shard "+str(shard))
                expected_id=q92.formula_id(columns)
                fid=row.get("formula_id","")
                if row.get("split")!=split or int(row.get("targets",-1))!=SPLIT_COUNTS[split] or int(row.get("feature_count",-1))!=10 or fid!=expected_id:
                    fail("Q92 metrics formula/split/order mismatch shard "+str(shard)+" local row "+str(local_row))
                expected_features="+".join(q80.FEATURE_NAMES[column] for column in columns)
                if row.get("features")!=expected_features:
                    fail("Q92 metrics feature string mismatch shard "+str(shard)+" formula "+fid)
                summary=metric_summary(row)
                targets=SPLIT_COUNTS[split]
                successes5=integer_from_mean(row["mean_number_hits_top5"],5*targets,"Q92 Top5")
                successes10=integer_from_mean(row["mean_number_hits_top10"],5*targets,"Q92 Top10")
                successes20=integer_from_mean(row["mean_number_hits_top20"],5*targets,"Q92 Top20")
                raw_p=[q92null.exact_upper_tail_pvalue(successes5,targets,5),
                    q92null.exact_upper_tail_pvalue(successes10,targets,10),
                    q92null.exact_upper_tail_pvalue(successes20,targets,20)]
                for endpoint_index,p in enumerate(raw_p):
                    observed=float(row[("p_top5_exact_hypergeom_sum","p_top10_exact_hypergeom_sum","p_top20_exact_hypergeom_sum")[endpoint_index]])
                    if abs(observed-p)>1e-12:
                        fail("Q92 raw p-value replay mismatch shard "+str(shard)+" formula "+fid+" split "+split)
                    pvalues[global_metric_row*3+endpoint_index]=p
                if abs(float(row.get("holm_p_max_endpoint_family",1.0))-1.0)>1e-15:
                    fail("Q92 raw shard Holm placeholder changed before global aggregation")
                if split_index==0:
                    score=summary["mean_number_hits_top5"]
                    mean_rank=summary["mean_rank_of_actual_numbers"]
                    key=(score,-mean_rank,invert_id(fid))
                    entry=(key,fid,score,mean_rank,expected_features,start+local_rank,summary)
                    if len(local_heap)<100:
                        heapq.heappush(local_heap,entry)
                    elif key>local_heap[0][0]:
                        heapq.heapreplace(local_heap,entry)
                elif split_index in (1,2):
                    item=local_candidate_map.get(fid) if local_candidate_map is not None else None
                    if item is not None:
                        item["validation" if split_index==1 else "blind"]=summary
                        if split_index==1:
                            item["validation_mean_number_hits_top5"]=summary["mean_number_hits_top5"]
                            item["validation_mean_rank_of_actual_numbers"]=summary["mean_rank_of_actual_numbers"]
                split_row_counts[split]+=1
                local_row+=1
                global_metric_row+=1
            if local_row!=SHARD_SIZE*3 or global_metric_row!=(shard+1)*SHARD_SIZE*3:
                fail("Q92 metrics shard exact row count mismatch shard "+str(shard))
            if local_candidate_map is None or len(local_candidate_map)!=100:
                fail("Q92 local candidate map incomplete shard "+str(shard))
            for item in local_candidate_map.values():
                if "validation" not in item or "blind" not in item:
                    fail("Q92 local top100 candidate lacks Validation/Blind metrics shard "+str(shard))
                candidate_pool.append(item)
    if global_metric_row!=TOTAL*3 or split_row_counts!={split:TOTAL for split in SPLITS}:
        fail("Q92 global formula×split coverage mismatch")
    if len(candidate_pool)!=SHARDS*100 or len({item["formula_id"] for item in candidate_pool})!=len(candidate_pool):
        fail("Q92 Discovery local top100 candidate pool must contain 1,500 unique formulas")

    raw_pvalue_sha256=sha256_memmap(pvalues)
    q92a.holm_adjust_in_place(pvalues,chunk_size=500_000)
    pvalues.flush()
    adjusted_pvalue_sha256=sha256_memmap(pvalues)
    holm_below=0
    minimum_holm=1.0
    total_metric_rows=TOTAL*3
    for row_start in range(0,total_metric_rows,1_000_000):
        row_end=min(row_start+1_000_000,total_metric_rows)
        chunk=np.asarray(pvalues[row_start*3:row_end*3],dtype=np.float64).reshape(-1,3)
        row_max=chunk.max(axis=1)
        holm_below+=int(np.sum(row_max<0.05))
        minimum_holm=min(minimum_holm,float(row_max.min()))

    global_top100=q92a.discovery_top_k(candidate_pool,k=100)
    validation_order=sorted(global_top100,key=lambda item:(-item["validation_mean_number_hits_top5"],item["validation_mean_rank_of_actual_numbers"],item["formula_id"]))
    selected=validation_order[0]
    selected_holm={}
    selected_metric_by_split={"discovery":selected["discovery"],"validation":selected["validation"],"blind_oos":selected["blind"]}
    for split_index,split in enumerate(SPLITS):
        adjusted=q92a.selected_formula_holm_pvalues(pvalues,int(selected["formula_rank"]),TOTAL,split_index)
        metrics=selected_metric_by_split[split]
        selected_holm[split]={
            "raw_pvalues":{
                "top5":float(metrics["p_top5_exact_hypergeom_sum"]),
                "top10":float(metrics["p_top10_exact_hypergeom_sum"]),
                "top20":float(metrics["p_top20_exact_hypergeom_sum"])},
            "holm_adjusted_pvalues":adjusted}
    uniform_baseline_evidence=q92a.uniform_baseline_evidence(
        float(selected["blind"]["mean_number_hits_top5"]),
        float(selected["blind"]["p_top5_exact_hypergeom_sum"]),
        float(selected_holm["blind_oos"]["holm_adjusted_pvalues"]["top5"]),
        baseline=0.125,alpha=0.05,targets=EXPECTED_BLIND_TARGETS)
    validation_rank={item["formula_id"]:rank+1 for rank,item in enumerate(validation_order)}
    shortlist=[]
    for discovery_rank,item in enumerate(global_top100,start=1):
        shortlist.append({"formula_id":item["formula_id"],"features":item["features"],"discovery_rank":discovery_rank,
            "discovery_mean_number_hits_top5":item["mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":item["mean_rank_of_actual_numbers"],
            "validation_mean_number_hits_top5":item["validation_mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":item["validation_mean_rank_of_actual_numbers"],
            "validation_selection_rank":validation_rank[item["formula_id"]],"selected":int(item["formula_id"]==selected["formula_id"])})
    with SHORTLIST_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(shortlist[0].keys()),lineterminator="\n")
        writer.writeheader();writer.writerows(shortlist)

    q92_selection={
        "schema_version":"1.0","task_id":"Q92_2026_11_08","protocol_id":"Q92-ten-feature-equal-weight-catalog-2026-11-09",
        "status":"CANDIDATE_FROZEN_BEFORE_BLIND_OOS","blind_oos_used_for_selection":False,"selected_candidate_ids_frozen":True,
        "selection_rule":"Discovery global top100 by mean Top-5 hit share, tie-break lower mean rank then lexicographic formula_id; select one on Validation with the same tie-break.",
        "candidate_universe_size":TOTAL,"discovery_local_shortlist_pool_size":SHARDS*100,
        "top100_discovery_candidates":[item["formula_id"] for item in global_top100],
        "Q92_candidate":{"formula_id":selected["formula_id"],"features":selected["features"],"formula_rank":selected["formula_rank"],
            "discovery_rank":next(row["discovery_rank"] for row in shortlist if row["formula_id"]==selected["formula_id"]),
            "discovery_mean_number_hits_top5":selected["mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":selected["mean_rank_of_actual_numbers"],"discovery_metrics":selected["discovery"],
            "validation_mean_number_hits_top5":selected["validation_mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":selected["validation_mean_rank_of_actual_numbers"],
            "validation_selection_rank":validation_rank[selected["formula_id"]],"validation_metrics":selected["validation"],
            "blind_oos_metrics_descriptive_only":selected["blind"],
            "global_holm_adjusted_pvalues":selected_holm,
            "blind_oos_uniform_baseline_evidence":uniform_baseline_evidence,
            "paired_blind_ledger_path":str(PAIRED_LEDGER_PATH.relative_to(ROOT))},
        "Q89_control":{"formula_id":q89_id,"features":"+".join(q80.FEATURE_NAMES[column] for column in q89_columns),
            "discovery_metrics":q89_report["selected_candidate_metrics"]["discovery"],
            "validation_metrics":q89_report["selected_candidate_metrics"]["validation"],
            "blind_oos_metrics_descriptive_only":q89_report["selected_candidate_metrics"]["blind_oos_descriptive_only"],
            "paired_blind_ledger_path":str(Q89_PAIRED_LEDGER_PATH.relative_to(ROOT))},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5}}
    SELECTION_PATH.write_text(json.dumps(q92_selection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    paired_rows,endpoint_deltas=build_paired_blind_ledger(q92_selection,dates,draws,feature_stack,q89_selection,q89_paired_rows,q89_id,q89_columns)
    inference=q92a.paired_endpoint_inference(endpoint_deltas,replicates=20_000,block_length=7,bootstrap_seed=920027,signflip_seed=920028,confidence_level=0.95,minimum_effect_size_top5=minimum_effect)
    inference.update({"schema_version":"1.0","task_id":"Q92_2026_11_08","protocol_id":"Q92-ten-feature-equal-weight-catalog-2026-11-09",
        "source_archive_sha256":archive_sha256,"Q92_candidate_id":selected["formula_id"],"Q89_control_candidate_id":q89_id,
        "paired_blind_ledger_rows":len(paired_rows),"blind_oos_used_for_selection":False})
    INFERENCE_PATH.write_text(json.dumps(inference,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    metrics_parts=[]
    for shard in range(SHARDS):
        start,end=q92.shard_bounds(shard)
        raw_path=SHARD_INPUT_DIR/f"shard_{shard}_metrics.csv"
        output_path=METRICS_PART_DIR/f"shard_{shard}_metrics.csv.gz"
        output_path.parent.mkdir(parents=True,exist_ok=True)
        raw_sha=sha256_file(raw_path)
        with raw_path.open(newline="",encoding="utf-8-sig") as source:
            reader=csv.DictReader(source)
            fieldnames=list(q92.COMPACT_METRIC_FIELDS)
            with output_path.open("wb") as raw_output:
                with gzip.GzipFile(fileobj=raw_output,mode="wb",filename="",mtime=0,compresslevel=9) as compressed:
                    with io.TextIOWrapper(compressed,encoding="utf-8",newline="") as text:
                        writer=csv.DictWriter(text,fieldnames=fieldnames,lineterminator="\\n")
                        writer.writeheader()
                        row_count=0
                        for row in reader:
                            if row_count>=SHARD_SIZE*3:
                                fail("Q92 raw metrics shard has extra rows while compacting shard "+str(shard))
                            split_index=row_count//SHARD_SIZE
                            expected_split=SPLITS[split_index]
                            targets=SPLIT_COUNTS[expected_split]
                            if row.get("split")!=expected_split or int(row.get("targets",-1))!=targets:
                                fail("Q92 raw metrics split/target order mismatch while compacting shard "+str(shard)+" row "+str(row_count))
                            writer.writerow(q92.compact_counts_from_raw_metrics(row,targets))
                            row_count+=1
                        if row_count!=SHARD_SIZE*3:
                            fail("Q92 compact metrics part row count mismatch shard "+str(shard))
        metrics_parts.append({"shard_index":shard,"path":str(output_path.relative_to(ROOT)),"rows":SHARD_SIZE*3,
            "formula_rank_start_inclusive":start,"formula_rank_end_exclusive":end,"row_schema":"compact_counts_v1","bytes":output_path.stat().st_size,
            "sha256":sha256_file(output_path),"source_artifact_sha256":raw_sha})

    target_parts=validate_and_persist_target_ledger_parts(dates,draws,archive_sha256,feature_stack)
    manifest={
        "schema_version":"1.0","task_id":"Q92_2026_11_08","protocol_id":"Q92-ten-feature-equal-weight-catalog-2026-11-09",
        "status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION","source_archive_sha256":archive_sha256,"source_archive_git_blob_sha1":archive_sha1,
        "source_archive_main_commit":EXPECTED_ARCHIVE_MAIN_COMMIT,"target_count":EXPECTED_ARCHIVE_COUNT,"scored_targets":scored,
        "formula_count":TOTAL,"formula_size":10,"feature_count":27,"shard_count":SHARDS,"rows_per_shard":SHARD_SIZE,
        "formula_rank_coverage":"0..8436284 exactly once","split_counts":SPLIT_COUNTS,
        "metrics_rows":TOTAL*3,"formula_split_endpoint_holm_family_size":tests,
        "multiple_testing":{"method":"Global Holm-Bonferroni","test_count":tests,"endpoints":["Top-5","Top-10","Top-20"],
            "raw_pvalue_vector_sha256":raw_pvalue_sha256,"adjusted_pvalue_vector_sha256":adjusted_pvalue_sha256,
            "p_value_method":"discrete upper-tail convolution of iid Hypergeometric(40,k,5) number-hit counts; deterministic float64 under independent uniform 5-of-40 draws"},
        "selected_candidate_global_holm_adjusted_pvalues":selected_holm,
        "blind_oos_uniform_baseline_evidence":uniform_baseline_evidence,
        "metrics_parts":metrics_parts,"metrics_part_count":len(metrics_parts),
        "metrics_parts_schema":{"version":"compact_counts_v1","fields":list(q92.COMPACT_METRIC_FIELDS),
            "row_order":"split-major; formula-rank ascending within split; split and formula-rank are implicit",
            "replay":"integer sufficient statistics reconstruct mean metrics and exact raw p-values; global Holm is replayed and compared by vector SHA"},
        "shard_source_code_sha256":source_code_hashes,"shard_source_checkout_shas":source_checkout_shas,
        "target_ledger_parts":target_parts,"target_ledger_part_count":len(target_parts),"target_ledger_rows_per_shard":scored,
        "supplemental_outputs":{"candidate_shortlist":{"path":str(SHORTLIST_PATH.relative_to(ROOT)),"rows":100,"bytes":SHORTLIST_PATH.stat().st_size,"sha256":sha256_file(SHORTLIST_PATH)},
            "candidate_selection":{"path":str(SELECTION_PATH.relative_to(ROOT)),"bytes":SELECTION_PATH.stat().st_size,"sha256":sha256_file(SELECTION_PATH)},
            "paired_blind_ledger":{"path":str(PAIRED_LEDGER_PATH.relative_to(ROOT)),"rows":len(paired_rows),"bytes":PAIRED_LEDGER_PATH.stat().st_size,"sha256":sha256_file(PAIRED_LEDGER_PATH)},
            "paired_inference":{"path":str(INFERENCE_PATH.relative_to(ROOT)),"bytes":INFERENCE_PATH.stat().st_size,"sha256":sha256_file(INFERENCE_PATH)}},
        "guardrails":["strict-prior feature state uses draws[0:i] only for target i; target quintet enters after ranking",
            "global Holm includes all 8,436,285 formulas × 3 chronological splits × 3 endpoints",
            "selected candidate raw and global Holm-adjusted p-values are exposed for every split and endpoint",
            "absolute Blind OOS evidence requires Top-5 share above 0.125 and selected-candidate global Holm-adjusted Top-5 p<0.05; paired lift over Q89 alone is insufficient",
            "Discovery top100 and Validation freeze precede Blind OOS reporting; Blind OOS cannot select",
            "Q89 control was refreshed and accepted on the exact same 2026-11-08 canonical archive",
            "per-target best formula within each shard is retrospective descriptive only, never a candidate-selection rule",
            "no automatic merge, engine promotion or shadow insertion; human review remains required"],
        "limitations":["finite equal-weight ten-feature grammar only; weighted/nonlinear/conditional/interaction formulas remain untested",
            "global formula-family p-values use discrete float64 convolution under the independent uniform 5-of-40 null; extreme underflow tails use the smallest positive subnormal floor",
            "compact metric parts store seven integer sufficient statistics; exact raw p-values and global Holm adjusted vector are replayed from these counts",
            "historical Blind OOS has prior SONAR exposure and is not independent prospective confirmation",
            "relative paired improvement over Q89 does not establish absolute above-uniform predictive value; the selected candidate's global Holm-adjusted Blind OOS Top-5 p-value is reported separately",
            "the finite formula catalog does not exhaust the infinite mathematical formula universe"]}
    MANIFEST_PATH.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    report={
        "schema_version":"1.0","task_id":"Q92_2026_11_08","status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","protocol_id":"Q92-ten-feature-equal-weight-catalog-2026-11-09",
        "source_archive":"data/storico_daily.csv","source_archive_sha256":archive_sha256,"source_archive_git_blob_sha1":archive_sha1,
        "source_archive_main_commit":EXPECTED_ARCHIVE_MAIN_COMMIT,"aggregate_checkout_sha":os.environ.get("GITHUB_SHA") or "LOCAL_UNPINNED",
        "source_code_sha256":source_code_hashes,"shard_source_checkout_shas":source_checkout_shas,
        "target_count":EXPECTED_ARCHIVE_COUNT,"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":q80.MIN_HISTORY,"scored_targets":scored,"feature_count":27,"formula_size":10,"formula_count":TOTAL,
        "shard_count":SHARDS,"shard_formula_count":SHARD_SIZE,"metrics_rows":TOTAL*3,"metrics_parts_row_schema":"compact_counts_v1","split_counts":SPLIT_COUNTS,
        "target_ledger_rows_per_shard":scored,"target_ledger_rows_total":scored*SHARDS,
        "multiple_testing":{"method":"Global Holm-Bonferroni","test_count":tests,"formula_split_endpoint_family_size":tests,
            "raw_pvalue_vector_sha256":raw_pvalue_sha256,"adjusted_pvalue_vector_sha256":adjusted_pvalue_sha256,
            "p_value_method":"discrete upper-tail convolution of iid Hypergeometric(40,k,5) number-hit counts; deterministic float64 under independent uniform 5-of-40 draws",
            "holm_adjusted_formula_split_rows_below_0_05":holm_below,"minimum_holm_p_max_endpoint_family":minimum_holm},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "selected_candidate_global_holm_adjusted_pvalues":selected_holm,
        "blind_oos_uniform_baseline_evidence":uniform_baseline_evidence,
        "candidate_selection":{"rule":q92_selection["selection_rule"],"blind_oos_used_for_selection":False,
            "selected_candidate_id":selected["formula_id"],"Q89_control_candidate_id":q89_id,"discovery_top100_count":100,
            "validation_candidates":100,"blind_oos_targets":EXPECTED_BLIND_TARGETS,"paired_blind_ledger_rows":len(paired_rows)},
        "selected_candidate_metrics":{"Q92_candidate":{"discovery":selected["discovery"],"validation":selected["validation"],
            "blind_oos_descriptive_only":selected["blind"],"global_holm_adjusted_pvalues":selected_holm,
            "blind_oos_uniform_baseline_evidence":uniform_baseline_evidence},
            "Q89_control":{"discovery":q89_report["selected_candidate_metrics"]["discovery"],
                "validation":q89_report["selected_candidate_metrics"]["validation"],
                "blind_oos_descriptive_only":q89_report["selected_candidate_metrics"]["blind_oos_descriptive_only"]}},
        "paired_blind_inference":inference,"outputs":{"metrics_parts":[item["path"] for item in metrics_parts],
            "target_ledger_parts":[item["path"] for item in target_parts],"candidate_shortlist":str(SHORTLIST_PATH.relative_to(ROOT)),
            "candidate_selection":str(SELECTION_PATH.relative_to(ROOT)),"paired_blind_ledger":str(PAIRED_LEDGER_PATH.relative_to(ROOT)),
            "paired_inference":str(INFERENCE_PATH.relative_to(ROOT)),"manifest":str(MANIFEST_PATH.relative_to(ROOT))},
        "guardrails":manifest["guardrails"],"limitations":manifest["limitations"],
        "next_action":"Run Q92 acceptance validator with candidate-specific global Holm replay; report absolute Blind OOS evidence against the 0.125 uniform Top-5 baseline separately from paired Q89 lift; persist append-only and require human review."}
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary={key:report[key] for key in ("task_id","status","source_archive_sha256","target_count","scored_targets","formula_count","metrics_rows",
        "split_counts","multiple_testing","candidate_selection","paired_blind_inference")}
    print("SONAR_Q92_AGGREGATE_BEGIN")
    print(json.dumps(summary,ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q92_AGGREGATE_END")
    pvalues.flush()
    del pvalues
    pvalue_path.unlink(missing_ok=True)

if __name__=="__main__":
    main()
