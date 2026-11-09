#!/usr/bin/env python3
"""Aggregate Q89 shards, apply one global Holm family, freeze candidates, and run paired blind OOS."""
from __future__ import annotations
import csv, gzip, hashlib, heapq, io, json, math
from pathlib import Path
from collections import Counter
import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_4plus_grammar as q81
import sonar_q89_common as q89

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
SHARD_DIR=OUT/"q89_shards"
ARCHIVE=ROOT/"data/storico_daily.csv"
TOTAL=q89.TOTAL_FORMULA_COUNT
SHARDS=q89.SHARD_COUNT
SHARD_SIZE=q89.SHARD_SIZE
CHUNK_ROWS=30000
SPLITS=("discovery","validation","blind_oos")
SPLIT_INDEX={name:index for index,name in enumerate(SPLITS)}
FEATURES=q80.FEATURE_NAMES
MIN_HISTORY=q80.MIN_HISTORY
FEATURE_COUNT=q89.FEATURE_COUNT
FORMULA_SIZE=q89.FORMULA_SIZE
Q89_REPORT_PATH=OUT/"per_number_condition_9plus_grammar.json"
Q89_MANIFEST_PATH=OUT/"per_number_condition_9plus_formula_metrics_manifest.json"
Q89_LEDGER_PATH=OUT/"per_number_condition_9plus_target_ledger.csv"
SHORTLIST_PATH=OUT/"per_number_condition_9plus_candidate_shortlist.csv"
SELECTION_PATH=OUT/"per_number_condition_9plus_candidate_selection.json"
PAIRED_LEDGER_PATH=OUT/"q89_selected_candidate_blind_ledger.csv"
PAIRED_INFERENCE_PATH=OUT/"per_number_condition_9plus_paired_inference.json"
Q88_REPORT_PATH=OUT/"per_number_condition_8plus_grammar.json"
Q88_MANIFEST_PATH=OUT/"per_number_condition_8plus_formula_metrics_manifest.json"

def fail(message):
    raise SystemExit("Q89_AGGREGATION_BLOCKED: "+message)

def read_archive():
    with ARCHIVE.open(newline="",encoding="utf-8-sig") as handle:
        rows=list(csv.DictReader(handle))
    dates=[row["data"] for row in rows]
    if len(dates)!=len(set(dates)) or dates!=sorted(dates):
        fail("canonical archive dates are not unique and chronological")
    draws=[]
    for row in rows:
        values=[int(row[f"n{i}"]) for i in range(1,6)]
        if len(set(values))!=5 or values!=sorted(values) or any(value<1 or value>40 for value in values):
            fail("invalid canonical archive quintet")
        draws.append(values)
    return dates,draws

def parse_formula_id(fid,prefix="P9_",size=9):
    if not isinstance(fid,str) or not fid.startswith(prefix):
        fail("formula ID prefix mismatch")
    try:
        columns=tuple(int(value) for value in fid[len(prefix):].split("_"))
    except Exception:
        fail("malformed formula ID")
    if len(columns)!=size or tuple(sorted(set(columns)))!=columns or columns[0]<0 or columns[-1]>=27:
        fail("formula ID indices are not canonical")
    canonical=prefix+"_".join(f"{value:02d}" for value in columns)
    if canonical!=fid:
        fail("formula ID is not canonical")
    return columns

def invert_id(fid):
    return bytes(255-ord(character) for character in fid)

def discovery_top100(metric_paths,split="discovery",gzip_mode=False,prefix="P9_"):
    heap=[]
    rows_seen=0
    for path in metric_paths:
        opener=gzip.open if gzip_mode else open
        with opener(path,"rt",newline="",encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("split")!=split:
                    continue
                fid=row.get("formula_id","")
                if not fid.startswith(prefix):
                    fail("formula family mismatch during discovery shortlist")
                score=float(row["mean_number_hits_top5"])
                mean_rank=float(row["mean_rank_of_actual_numbers"])
                key=(score,-mean_rank,invert_id(fid))
                entry=(key,fid,score,mean_rank,row.get("features",""))
                if len(heap)<100:
                    heapq.heappush(heap,entry)
                elif key>heap[0][0]:
                    heapq.heapreplace(heap,entry)
                rows_seen+=1
    if len(heap)!=100:
        fail("Discovery did not produce exactly 100 shortlist candidates")
    ordered=sorted(heap,key=lambda entry:(-entry[2],entry[3],entry[1]))
    return [{"formula_id":entry[1],"features":entry[4],"discovery_mean_number_hits_top5":entry[2],
             "discovery_mean_rank_of_actual_numbers":entry[3],"discovery_rank":rank+1}
            for rank,entry in enumerate(ordered)]

def validation_select(metric_paths,shortlist,split="validation",gzip_mode=False,prefix="P9_"):
    ids={row["formula_id"] for row in shortlist}
    if len(ids)!=100:
        fail("Discovery shortlist formula IDs are not unique")
    found={}
    for path in metric_paths:
        opener=gzip.open if gzip_mode else open
        with opener(path,"rt",newline="",encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                if row.get("split")!=split or row.get("formula_id") not in ids:
                    continue
                fid=row["formula_id"]
                if fid in found:
                    fail("duplicate Validation formula row for shortlist candidate")
                if not fid.startswith(prefix):
                    fail("Validation candidate formula prefix mismatch")
                found[fid]={"validation_mean_number_hits_top5":float(row["mean_number_hits_top5"]),
                    "validation_mean_rank_of_actual_numbers":float(row["mean_rank_of_actual_numbers"]),
                    "validation_features":row.get("features","")}
    if set(found)!=ids:
        fail("Validation does not reconcile all 100 Discovery shortlist candidates")
    enriched=[]
    for item in shortlist:
        row=dict(item)
        row.update(found[item["formula_id"]])
        enriched.append(row)
    selected=sorted(enriched,key=lambda row:(-row["validation_mean_number_hits_top5"],
        row["validation_mean_rank_of_actual_numbers"],row["formula_id"]))[0]
    for rank,row in enumerate(sorted(enriched,key=lambda item:(-item["validation_mean_number_hits_top5"],
            item["validation_mean_rank_of_actual_numbers"],item["formula_id"])),start=1):
        row["validation_selection_rank"]=rank
        row["selected"]=row["formula_id"]==selected["formula_id"]
    return selected,enriched

def q88_metric_paths():
    report=json.loads(Q88_REPORT_PATH.read_text(encoding="utf-8"))
    manifest=json.loads(Q88_MANIFEST_PATH.read_text(encoding="utf-8"))
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    dates,draws=read_archive()
    expected_splits={"discovery":math.ceil(.60*(len(draws)-q80.MIN_HISTORY)),
        "validation":math.ceil(.80*(len(draws)-q80.MIN_HISTORY))-math.ceil(.60*(len(draws)-q80.MIN_HISTORY)),
        "blind_oos":len(draws)-q80.MIN_HISTORY-math.ceil(.80*(len(draws)-q80.MIN_HISTORY))}
    if report.get("status")!="VALIDATED_PENDING_HUMAN_REVIEW" or report.get("review_status")!="PENDING_HUMAN_REVIEW_INTEGRATION":
        fail("Q88 control is not accepted/pending human review")
    if report.get("source_archive_sha256")!=source_sha or report.get("target_count")!=len(draws) or report.get("last_date")!=dates[-1]:
        fail("Q88 control archive lineage differs from Q89 canonical archive")
    if report.get("formula_count")!=math.comb(27,8) or report.get("scored_targets")!=len(draws)-q80.MIN_HISTORY or report.get("split_counts")!=expected_splits:
        fail("Q88 control dimensions/splits mismatch")
    if manifest.get("task_id")!="Q88" or manifest.get("source_archive_sha256")!=source_sha or manifest.get("formula_count")!=math.comb(27,8) or manifest.get("metrics_rows")!=math.comb(27,8)*3:
        fail("Q88 metrics manifest identity/dimensions mismatch")
    if manifest.get("parts")!=report.get("metrics_parts") or manifest.get("part_count")!=len(manifest.get("parts",[])):
        fail("Q88 report and metrics manifest parts do not reconcile")
    parts=[]
    cursor=0
    for part in manifest["parts"]:
        path=ROOT/part["path"]
        if not path.is_file():
            fail("missing Q88 control metrics part "+part["path"])
        raw=path.read_bytes()
        if len(raw)!=int(part["bytes"]) or hashlib.sha256(raw).hexdigest()!=part["sha256"]:
            fail("Q88 control metric part byte/SHA mismatch "+part["path"])
        if int(part["row_start_inclusive"])!=cursor or int(part["row_end_exclusive"])!=cursor+int(part["rows"]):
            fail("Q88 control metrics manifest row range mismatch")
        cursor+=int(part["rows"])
        parts.append(path)
    if cursor!=math.comb(27,8)*3:
        fail("Q88 control metric manifest total row count mismatch")
    return parts

def candidate_selection():
    q89_paths=[SHARD_DIR/f"shard_{shard}_metrics.csv" for shard in range(SHARDS)]
    for path in q89_paths:
        if not path.is_file():
            fail("missing Q89 shard metrics "+str(path))
    q89_shortlist=discovery_top100(q89_paths,prefix="P9_")
    q89_selected,q89_enriched=validation_select(q89_paths,q89_shortlist,prefix="P9_")
    q88_paths=q88_metric_paths()
    q88_shortlist=discovery_top100(q88_paths,gzip_mode=True,prefix="P8_")
    q88_selected,q88_enriched=validation_select(q88_paths,q88_shortlist,gzip_mode=True,prefix="P8_")
    rows=[]
    for family,enriched,selected in (("nine_feature",q89_enriched,q89_selected),("eight_feature_control",q88_enriched,q88_selected)):
        for item in enriched:
            rows.append({"family":family,"formula_id":item["formula_id"],"features":item.get("features",item.get("validation_features","")),
                "discovery_rank":item["discovery_rank"],"discovery_mean_number_hits_top5":item["discovery_mean_number_hits_top5"],
                "discovery_mean_rank_of_actual_numbers":item["discovery_mean_rank_of_actual_numbers"],
                "validation_mean_number_hits_top5":item["validation_mean_number_hits_top5"],
                "validation_mean_rank_of_actual_numbers":item["validation_mean_rank_of_actual_numbers"],
                "validation_selection_rank":item["validation_selection_rank"],"selected":int(item["formula_id"]==selected["formula_id"])})
    with SHORTLIST_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    selection={"schema_version":"1.0","task_id":"Q89","protocol_id":"Q89-nine-feature-equal-weight-catalog-2026-11-08",
        "status":"CANDIDATES_FROZEN_BEFORE_BLIND_OOS","blind_oos_used_for_selection":False,
        "selection_rule":"Discovery top100 by mean number_hits_top5, tie-break lower mean_rank_of_actual_numbers then lexicographic formula_id; select one on Validation with the same tie-break.",
        "top100_discovery_candidates":{"Q89":[item["formula_id"] for item in q89_shortlist],"Q88":[item["formula_id"] for item in q88_shortlist]},
        "selected_candidate_ids_frozen":True,
        "Q89_candidate":{"formula_id":q89_selected["formula_id"],"features":q89_selected["features"],
            "discovery_rank":q89_selected["discovery_rank"],"discovery_mean_number_hits_top5":q89_selected["discovery_mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":q89_selected["discovery_mean_rank_of_actual_numbers"],
            "validation_mean_number_hits_top5":q89_selected["validation_mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":q89_selected["validation_mean_rank_of_actual_numbers"],
            "validation_selection_rank":q89_selected["validation_selection_rank"]},
        "Q88_control":{"formula_id":q88_selected["formula_id"],"features":q88_selected["features"],
            "discovery_rank":q88_selected["discovery_rank"],"discovery_mean_number_hits_top5":q88_selected["discovery_mean_number_hits_top5"],
            "discovery_mean_rank_of_actual_numbers":q88_selected["discovery_mean_rank_of_actual_numbers"],
            "validation_mean_number_hits_top5":q88_selected["validation_mean_number_hits_top5"],
            "validation_mean_rank_of_actual_numbers":q88_selected["validation_mean_rank_of_actual_numbers"],
            "validation_selection_rank":q88_selected["validation_selection_rank"]}}
    SELECTION_PATH.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return selection

def formula_columns_from_id(fid):
    if fid.startswith("P9_"):
        return parse_formula_id(fid,"P9_",9)
    if fid.startswith("P8_"):
        return parse_formula_id(fid,"P8_",8)
    fail("frozen candidate formula ID has unknown prefix")

def rank_actual_for_formula(standardized,columns,actual_indices):
    score=standardized[:,columns].mean(axis=1)
    order=np.argsort(-score,kind="stable")
    ranks=np.empty(40,dtype=np.int16)
    ranks[order]=np.arange(1,41,dtype=np.int16)
    return ranks[actual_indices].astype(int).tolist()

def paired_rank_evidence(q89_ranks,q88_ranks):
    return {
        "q89_hits":{k:sum(value<=k for value in q89_ranks) for k in (5,10,20)},
        "q88_hits":{k:sum(value<=k for value in q88_ranks) for k in (5,10,20)}
    }

def paired_blind_ledger(selection,dates,draws):
    q89_id=selection["Q89_candidate"]["formula_id"]
    q88_id=selection["Q88_control"]["formula_id"]
    q89_columns=formula_columns_from_id(q89_id)
    q88_columns=formula_columns_from_id(q88_id)
    standardized_stack=q81.build_feature_stack(draws)
    scored=len(draws)-q80.MIN_HISTORY
    rows=[]
    diffs={"top5":[],"top10":[],"top20":[]}
    for target_offset,target_index in enumerate(range(q80.MIN_HISTORY,len(draws))):
        if q80.split_name(target_offset,scored)!="blind_oos":
            continue
        standardized=standardized_stack[target_offset]
        actual_indices=np.asarray(draws[target_index],dtype=np.int64)-1
        q89_ranks=rank_actual_for_formula(standardized,q89_columns,actual_indices)
        q88_ranks=rank_actual_for_formula(standardized,q88_columns,actual_indices)
        q89_hits={k:sum(value<=k for value in q89_ranks) for k in (5,10,20)}
        q88_hits={k:sum(value<=k for value in q88_ranks) for k in (5,10,20)}
        delta={k:q89_hits[k]-q88_hits[k] for k in (5,10,20)}
        for k,name in ((5,"top5"),(10,"top10"),(20,"top20")):
            diffs[name].append(delta[k])
        rows.append({"target_date":dates[target_index],"cutoff_date":dates[target_index-1],"prior_draws":target_index,
            "actual_quintet":" ".join(map(str,draws[target_index])),"Q89_formula_id":q89_id,"Q88_control_formula_id":q88_id,
            "Q89_actual_number_ranks":json.dumps(q89_ranks,separators=(",",":")),
            "Q88_actual_number_ranks":json.dumps(q88_ranks,separators=(",",":")),
            "Q89_number_hits_top5":q89_hits[5],"Q89_number_hits_top10":q89_hits[10],"Q89_number_hits_top20":q89_hits[20],
            "Q88_number_hits_top5":q88_hits[5],"Q88_number_hits_top10":q88_hits[10],"Q88_number_hits_top20":q88_hits[20],
            "Q89_rank_sum":sum(q89_ranks),"Q88_rank_sum":sum(q88_ranks),
            "paired_delta_number_hits_top5":delta[5],"paired_delta_number_hits_top10":delta[10],"paired_delta_number_hits_top20":delta[20]})
    if len(rows)!=670:
        fail("selected-candidate Blind OOS ledger must contain 670 targets")
    with PAIRED_LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    return rows,diffs

def bootstrap_ci(differences,replicates=20000,block_length=7,seed=890027):
    values=np.asarray(differences,dtype=np.float64)
    n=len(values)
    if n==0: fail("paired bootstrap has no blind targets")
    blocks=math.ceil(n/block_length)
    rng=np.random.default_rng(seed)
    means=np.empty(replicates,dtype=np.float64)
    offsets=np.arange(block_length,dtype=np.int64)
    batch_size=500
    for start in range(0,replicates,batch_size):
        count=min(batch_size,replicates-start)
        starts=rng.integers(0,n,size=(count,blocks),dtype=np.int64)
        indices=(starts[:,:,None]+offsets[None,None,:])%n
        sample=values[indices].reshape(count,-1)[:,:n]
        means[start:start+count]=sample.mean(axis=1)
    return [float(np.quantile(means,0.025)),float(np.quantile(means,0.975))]

def block_signflip_p(differences,replicates=20000,block_length=7,seed=890028):
    """Two-sided circular block sign-flip test with a randomized circular block origin."""
    values=np.asarray(differences,dtype=np.float64)
    n=len(values)
    blocks=math.ceil(n/block_length)
    observed=float(values.mean())
    rng=np.random.default_rng(seed)
    extreme=0
    batch_size=500
    offsets=np.arange(n,dtype=np.int64)
    for start in range(0,replicates,batch_size):
        count=min(batch_size,replicates-start)
        origins=rng.integers(0,block_length,size=count,dtype=np.int64)
        rotated=values[(offsets[None,:]+origins[:,None])%n]
        signs=rng.choice(np.asarray([-1.0,1.0]),size=(count,blocks))
        expanded=np.repeat(signs,block_length,axis=1)[:,:n]
        permuted=(expanded*rotated).mean(axis=1)
        extreme+=int(np.sum(np.abs(permuted)>=abs(observed)))
    return float((extreme+1)/(replicates+1))

def holm_adjust(pvalues):
    ordered=sorted(range(len(pvalues)),key=lambda index:(pvalues[index],index))
    adjusted=[1.0]*len(pvalues)
    running=0.0
    count=len(pvalues)
    for rank,index in enumerate(ordered):
        value=min(1.0,(count-rank)*float(pvalues[index]))
        running=max(running,value)
        adjusted[index]=running
    return adjusted

def main():
    dates,draws=read_archive()
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    n=len(draws)
    scored=n-q80.MIN_HISTORY
    discovery=math.ceil(.60*scored)
    validation=math.ceil(.80*scored)
    expected_splits={"discovery":discovery,"validation":validation-discovery,"blind_oos":scored-validation}
    if n!=3401 or dates[-1]!="2026-11-07" or scored!=3351 or expected_splits!={"discovery":2011,"validation":670,"blind_oos":670}:
        fail("Q89 preregistered archive/split dimensions mismatch")
    total_rows=TOTAL*len(SPLITS)
    tests=total_rows*3
    pvals=np.empty(tests,dtype=np.float64)
    split_counts=Counter()
    cursor=0
    top_rank_heap=[]
    top_top5_heap=[]
    # Pass 1: validate every formula rank, shard boundary, split row and raw p-value.
    for shard in range(SHARDS):
        start,end=q89.shard_bounds(shard)
        path=SHARD_DIR/f"shard_{shard}_metrics.csv"
        report_path=SHARD_DIR/f"shard_{shard}_report.json"
        if not path.is_file() or not report_path.is_file():
            fail("missing Q89 shard metric/report for shard "+str(shard))
        shard_report=json.loads(report_path.read_text(encoding="utf-8"))
        if shard_report.get("task_id")!="Q89" or shard_report.get("status")!="SHARD_COMPLETE_NOT_TASK_COMPLETE":
            fail("Q89 shard report identity/status mismatch")
        if shard_report.get("source_archive_sha256")!=source_sha or shard_report.get("target_count")!=n or shard_report.get("scored_targets")!=scored:
            fail("Q89 shard archive lineage/dimensions mismatch")
        if shard_report.get("shard_index")!=shard or shard_report.get("shard_formula_start_inclusive")!=start or shard_report.get("shard_formula_end_exclusive")!=end or shard_report.get("formula_count")!=SHARD_SIZE:
            fail("Q89 shard rank boundaries mismatch")
        local_counts=Counter()
        with path.open(newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            required={"split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
                "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"}
            if not required.issubset(set(reader.fieldnames or [])):
                fail("Q89 shard metric schema incomplete")
            for row in reader:
                split=row.get("split","")
                if split not in SPLITS:
                    fail("Q89 invalid split in shard metrics")
                columns=parse_formula_id(row.get("formula_id",""),"P9_",9)
                rank=q89.formula_rank(columns)
                expected_rank=start+local_counts[split]
                if rank!=expected_rank:
                    fail("Q89 formula rank gap/overlap/duplicate in shard "+str(shard)+" split "+split)
                expected_features="+".join(FEATURES[index] for index in columns)
                if row.get("features")!=expected_features:
                    fail("Q89 formula feature names do not reconcile to ID")
                if int(row.get("feature_count",-1))!=9 or int(row.get("targets",-1))!=expected_splits[split]:
                    fail("Q89 formula count/split target count mismatch")
                for field in ("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers",
                    "p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx"):
                    value=float(row[field])
                    if not math.isfinite(value) or (field=="mean_rank_of_actual_numbers" and not 1<=value<=40) or (field!="mean_rank_of_actual_numbers" and not 0<=value<=1):
                        fail("Q89 invalid metric value "+field)
                for endpoint_index,field in enumerate(("p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx")):
                    pvalue=float(row[field])
                    if pvalue<0 or pvalue>1:
                        fail("Q89 raw p-value outside [0,1]")
                    pvals[cursor*3+endpoint_index]=pvalue
                if split=="blind_oos":
                    compact={key:row[key] for key in ("formula_id","features","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","mean_rank_of_actual_numbers")}
                    rank_key=(-float(row["mean_rank_of_actual_numbers"]),float(row["mean_number_hits_top5"]),invert_id(row["formula_id"]))
                    top_rank_entry=(rank_key,compact)
                    if len(top_rank_heap)<10: heapq.heappush(top_rank_heap,top_rank_entry)
                    elif rank_key>top_rank_heap[0][0]: heapq.heapreplace(top_rank_heap,top_rank_entry)
                    top5_key=(float(row["mean_number_hits_top5"]),-float(row["mean_rank_of_actual_numbers"]),invert_id(row["formula_id"]))
                    top5_entry=(top5_key,compact)
                    if len(top_top5_heap)<10: heapq.heappush(top_top5_heap,top5_entry)
                    elif top5_key>top_top5_heap[0][0]: heapq.heapreplace(top_top5_heap,top5_entry)
                local_counts[split]+=1
                split_counts[split]+=1
                cursor+=1
        if local_counts!={split:SHARD_SIZE for split in SPLITS}:
            fail("Q89 shard formula/split coverage mismatch for shard "+str(shard))
    if cursor!=total_rows or split_counts!={split:TOTAL for split in SPLITS}:
        fail("Q89 aggregate formula/metric row coverage mismatch")
    # Global Holm step-down over the complete 42,181,425-test formula×split×endpoint family.
    order=np.argsort(pvals,kind="stable")
    sorted_adjusted=np.maximum.accumulate((tests-np.arange(tests,dtype=np.int64))*pvals[order])
    np.minimum(sorted_adjusted,1.0,out=sorted_adjusted)
    adjusted=np.empty_like(pvals)
    adjusted[order]=sorted_adjusted
    row_holm=adjusted.reshape(total_rows,3).max(axis=1)

    # Pass 2: deterministic gzip chunks, manifest and report metrics.
    sample_fields=None
    part_manifest=[]
    part_index=-1
    raw_handle=None
    text_handle=None
    writer=None
    part_rows=0
    total_written=0
    def open_part():
        nonlocal part_index,raw_handle,text_handle,writer,part_rows,sample_fields
        if text_handle is not None:
            text_handle.close()
            raw_handle.close()
        part_index+=1
        part_rows=0
        path=OUT/f"per_number_condition_9plus_formula_metrics_part_{part_index:03d}.csv.gz"
        raw_handle=path.open("wb")
        gzip_handle=gzip.GzipFile(filename="",mode="wb",fileobj=raw_handle,mtime=0)
        text_handle=io.TextIOWrapper(gzip_handle,encoding="utf-8",newline="")
        if sample_fields is None:
            sample_fields=["split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
                "all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"]
        writer=csv.DictWriter(text_handle,fieldnames=sample_fields)
        writer.writeheader()
    try:
        for shard in range(SHARDS):
            path=SHARD_DIR/f"shard_{shard}_metrics.csv"
            with path.open(newline="",encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    if text_handle is None or part_rows>=CHUNK_ROWS:
                        open_part()
                    row["holm_p_max_endpoint_family"]=f"{row_holm[total_written]:.17g}"
                    writer.writerow(row)
                    part_rows+=1
                    total_written+=1
    finally:
        if text_handle is not None:
            text_handle.close()
            raw_handle.close()
    if total_written!=total_rows:
        fail("Q89 written metric rows do not match declared total")
    cursor=0
    for index in range(part_index+1):
        path=OUT/f"per_number_condition_9plus_formula_metrics_part_{index:03d}.csv.gz"
        raw=path.read_bytes()
        rows_in_part=min(CHUNK_ROWS,total_rows-cursor)
        part_manifest.append({"part_index":index,"path":str(path.relative_to(ROOT)),"rows":rows_in_part,
            "row_start_inclusive":cursor,"row_end_exclusive":cursor+rows_in_part,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
        cursor+=rows_in_part
    if cursor!=total_rows or len(part_manifest)!=math.ceil(total_rows/CHUNK_ROWS):
        fail("Q89 metrics chunk manifest dimensions mismatch")

    # Merge the fifteen shard-local retrospective winners into one descriptive global target ledger.
    date_index={date:index for index,date in enumerate(dates)}
    best_by_date={}
    target_seen=Counter()
    expected_target_dates=dates[MIN_HISTORY:]
    for shard in range(SHARDS):
        path=SHARD_DIR/f"shard_{shard}_target_ledger.csv"
        if not path.is_file():
            fail("missing Q89 shard target ledger")
        shard_dates=[]
        with path.open(newline="",encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                date=row["target_date"]
                if date not in date_index:
                    fail("Q89 target ledger date not found in archive")
                index=date_index[date]
                if index<MIN_HISTORY or row["cutoff_date"]!=dates[index-1] or int(row["prior_draws"])!=index:
                    fail("Q89 target strict-prefix cutoff mismatch at "+date)
                if row["actual_quintet"]!=" ".join(map(str,draws[index])):
                    fail("Q89 target actual quintet mismatch at "+date)
                if int(row.get("formula_count_tested",-1))!=TOTAL:
                    fail("Q89 target formula_count_tested mismatch")
                columns=parse_formula_id(row.get("best_formula_id",""),"P9_",9)
                if row.get("best_formula_features")!="+".join(FEATURES[c] for c in columns):
                    fail("Q89 retrospective best formula features/ID mismatch")
                try:
                    ranks=json.loads(row["best_actual_number_ranks"])
                    singles=json.loads(row["single_feature_rank_ledger"])
                    if len(ranks)!=5 or any(not isinstance(value,int) or value<1 or value>40 for value in ranks):
                        raise ValueError("best ranks invalid")
                    if len(singles)!=27 or {item.get("feature") for item in singles}!=set(FEATURES):
                        raise ValueError("single-feature ledger must contain all 27 features")
                    for item in singles:
                        if len(item.get("ranks",[]))!=5 or any(not isinstance(value,int) or value<1 or value>40 for value in item["ranks"]):
                            raise ValueError("single-feature ranks invalid")
                except Exception as exc:
                    fail("Q89 target ledger rank evidence invalid: "+str(exc))
                shard_dates.append(date)
                target_seen[date]+=1
                key=(int(row["best_rank_sum"]),int(row["best_number_hits_top20"]),-int(row["best_number_hits_top5"]),row["best_formula_id"])
                old=best_by_date.get(date)
                if old is None or key<old[0]:
                    best_by_date[date]=(key,row)
        if shard_dates!=expected_target_dates:
            fail("Q89 shard target ledger date coverage/order mismatch")
    if len(best_by_date)!=scored or any(target_seen[date]!=SHARDS for date in expected_target_dates):
        fail("Q89 global retrospective target ledger coverage mismatch")
    ledgers=[]
    for date in expected_target_dates:
        row=dict(best_by_date[date][1])
        row["formula_count_tested"]=TOTAL
        ledgers.append(row)
    with Q89_LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(ledgers[0].keys()))
        writer.writeheader(); writer.writerows(ledgers)

    # Freeze the Discovery/Validation candidate IDs before the blind paired second pass.
    selection=candidate_selection()
    paired_rows,differences=paired_blind_ledger(selection,dates,draws)
    endpoint_names=("top5","top10","top20")
    raw_pvalues=[]
    endpoint_results={}
    for endpoint in endpoint_names:
        values=differences[endpoint]
        mean_count=float(np.mean(values))
        ci=bootstrap_ci(values)
        pvalue=block_signflip_p(values)
        raw_pvalues.append(pvalue)
        endpoint_results[endpoint]={"mean_paired_delta_number_hits":mean_count,
            "mean_paired_delta_hit_share":mean_count/5.0,
            "mean_paired_delta_hit_share_percentage_points":mean_count/5.0*100.0,
            "bootstrap_95_percentile_ci_number_hits":ci,
            "bootstrap_95_percentile_ci_hit_share":[ci[0]/5.0,ci[1]/5.0],
            "block_signflip_p_raw_two_sided":pvalue,"holm_p":None,
            "primary_endpoint":endpoint=="top5","secondary_endpoint":endpoint!="top5"}
    adjusted_p=holm_adjust(raw_pvalues)
    for endpoint,pvalue in zip(endpoint_names,adjusted_p):
        endpoint_results[endpoint]["holm_p"]=float(pvalue)
    inference={"schema_version":"1.0","task_id":"Q89","protocol_id":"Q89-nine-feature-equal-weight-catalog-2026-11-08",
        "blind_oos_targets":len(paired_rows),"bootstrap":{"method":"circular moving-block bootstrap percentile CI","replicates":20000,"block_length":7,"seed":890027,"confidence_level":0.95},
        "signflip":{"method":"circular block sign-flip randomization, two-sided","replicates":20000,"block_length":7,"seed":890028},
        "multiple_testing":{"method":"Holm-Bonferroni","family_size":3,"endpoints":["top5 primary","top10 secondary","top20 secondary"]},
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "Q89_candidate_blind_metrics":{"mean_number_hits_top5":sum(row["Q89_number_hits_top5"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_number_hits_top10":sum(row["Q89_number_hits_top10"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_number_hits_top20":sum(row["Q89_number_hits_top20"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_rank_of_actual_numbers":sum(row["Q89_rank_sum"] for row in paired_rows)/(5*len(paired_rows))},
        "Q88_control_blind_metrics":{"mean_number_hits_top5":sum(row["Q88_number_hits_top5"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_number_hits_top10":sum(row["Q88_number_hits_top10"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_number_hits_top20":sum(row["Q88_number_hits_top20"] for row in paired_rows)/(5*len(paired_rows)),
            "mean_rank_of_actual_numbers":sum(row["Q88_rank_sum"] for row in paired_rows)/(5*len(paired_rows))},
        "paired_endpoints":endpoint_results,
        "decision":"NO_SIGNIFICANT_GAIN" if endpoint_results["top5"]["holm_p"]>=0.05 or endpoint_results["top5"]["bootstrap_95_percentile_ci_hit_share"][0]<=0 else "PRIMARY_GAIN_REQUIRES_HUMAN_REVIEW",
        "blind_oos_used_for_candidate_selection":False,
        "limitations":["finite equal-weight nine-feature grammar only","global formula-family p-values use an exploratory continuity-corrected normal approximation to summed hypergeometric hit counts",
            "historical blind OOS has prior SONAR exposure and is not independent prospective confirmation","no engine promotion or shadow-stream insertion"]}
    PAIRED_INFERENCE_PATH.write_text(json.dumps(inference,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

    parts_sha=hashlib.sha256(json.dumps(part_manifest,sort_keys=True,separators=(",",":")).encode("utf-8")).hexdigest()
    manifest={"schema_version":"1.0","task_id":"Q89","storage_format":"chunked_csv_gzip_parts","source_archive_sha256":source_sha,
        "formula_count":TOTAL,"metrics_rows":total_rows,"part_count":len(part_manifest),"parts_manifest_sha256":parts_sha,"parts":part_manifest}
    report={"schema_version":"1.0","task_id":"Q89","status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","protocol_id":"Q89-nine-feature-equal-weight-catalog-2026-11-08",
        "source_archive":"data/storico_daily.csv","source_archive_sha256":source_sha,"target_count":n,"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":MIN_HISTORY,"scored_targets":scored,"feature_count":FEATURE_COUNT,"features":FEATURES,
        "formula_size":FORMULA_SIZE,"formula_count":TOTAL,"formula_count_check":math.comb(27,9),"formula_batch_size":q89.FORMULA_BATCH_SIZE,
        "formula_batch_count":math.ceil(TOTAL/q89.FORMULA_BATCH_SIZE),"shard_count":SHARDS,"shard_formula_count":SHARD_SIZE,
        "formula_grammar":"all nine-feature equal-weight combinations",
        "scoring_rule":"strict-prefix z-score each registered feature across numbers 1..40, then equal-weight arithmetic mean of each unordered nine-feature subset",
        "metrics_storage":"chunked_csv_gzip_parts","metrics_rows":total_rows,"target_ledger_rows":scored,"split_counts":expected_splits,
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,"mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":tests,
            "p_value_method":"continuity-corrected normal approximation to summed Hypergeometric(40,k,5) number-hit counts; exploratory, not exact",
            "formula_split_endpoint_family_size":tests},
        "holm_adjusted_formula_split_rows_below_0_05":int(np.sum(row_holm<0.05)),
        "minimum_holm_p_max_endpoint_family":float(np.min(row_holm)),
        "best_blind_oos_by_mean_rank":[item[1] for item in sorted(top_rank_heap,key=lambda item:item[0],reverse=True)],
        "best_blind_oos_by_mean_top5_hits":[item[1] for item in sorted(top_top5_heap,key=lambda item:item[0],reverse=True)],
        "candidate_selection":{"rule":"Discovery top100 by Top5 number-hit share; one selected on Validation with same tie-break; blind never used for selection",
            "selected_candidate_ids_frozen_before_blind":True,"Q89_formula_id":selection["Q89_candidate"]["formula_id"],
            "Q88_control_formula_id":selection["Q88_control"]["formula_id"],"blind_oos_targets":len(paired_rows),
            "paired_inference_path":str(PAIRED_INFERENCE_PATH.relative_to(ROOT))},
        "guardrails":["strict prior-only feature values and cutoffs; target draw excluded","rank all 40 numbers before target scoring",
            "retrospective best-per-target formula is descriptive only","global Holm family spans all shards, splits and primary endpoints",
            "candidate selection uses Discovery and Validation only; blind is a frozen paired comparison",
            "finite nine-feature equal-weight grammar only; higher-order, weighted, conditional and nonlinear formulas remain open",
            "immutable freezes preserved; no automatic merge or promotion"],
        "known_limitations":["formula-family normal p-values are approximate under the finite-population hypergeometric null",
            "historical blind OOS is not independent because prior SONAR analyses have inspected this tail",
            "candidate paired historical OOS is exploratory and requires prospective append-only confirmation"],
        "next_action":"Persist all Q89 outputs append-only, validate exact bytes and current-head CI; then human review/integration before any Q89 COMPLETE status.",
        "metrics_parts":part_manifest,
        "outputs":{"metrics_parts":[item["path"] for item in part_manifest],"metrics_parts_manifest_sha256":parts_sha,
            "metrics_manifest":str(Q89_MANIFEST_PATH.relative_to(ROOT)),"target_ledger":str(Q89_LEDGER_PATH.relative_to(ROOT)),
            "candidate_shortlist":str(SHORTLIST_PATH.relative_to(ROOT)),"candidate_selection":str(SELECTION_PATH.relative_to(ROOT)),
            "selected_candidate_blind_ledger":str(PAIRED_LEDGER_PATH.relative_to(ROOT)),"paired_inference":str(PAIRED_INFERENCE_PATH.relative_to(ROOT))}}
    Q89_REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    Q89_MANIFEST_PATH.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SONAR_Q89_AGGREGATE_BEGIN")
    print(json.dumps({key:report[key] for key in ("task_id","status","target_count","last_date","scored_targets","formula_count","metrics_rows","target_ledger_rows","split_counts",
        "multiple_testing","holm_adjusted_formula_split_rows_below_0_05","minimum_holm_p_max_endpoint_family","candidate_selection")},ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q89_AGGREGATE_END")

if __name__=="__main__":
    main()
