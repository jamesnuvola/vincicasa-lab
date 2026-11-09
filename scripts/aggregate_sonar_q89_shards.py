#!/usr/bin/env python3
"""Aggregate Q89 nine-feature shards with conservative conditional-null bounds and global Holm."""
from __future__ import annotations
import csv, gzip, hashlib, heapq, io, json, math, os
from pathlib import Path
from collections import Counter
import numpy as np
import sonar_per_number_condition_grammar as q80
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports/sequence_agent"
SHARD_DIR=OUT/"q89_shards"
ARCHIVE=ROOT/"data/storico_daily.csv"
PROTOCOL=OUT/"q89_protocol_2026-11-09.json"
TOTAL=math.comb(27,9)
SHARDS=30
CHUNK_ROWS=30000
HOLM_CHUNK=1000000
SPLITS=("discovery","validation","blind_oos")
FEATURES=q80.FEATURE_NAMES
METRICS_MANIFEST=OUT/"per_number_condition_9plus_formula_metrics_manifest.json"
REPORT_PATH=OUT/"per_number_condition_9plus_grammar.json"
LEDGER_PATH=OUT/"per_number_condition_9plus_target_ledger.csv"
EXPECTED_ARCHIVE_SHA256="3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed"

def fail(message):
    raise SystemExit("Q89_AGGREGATION_BLOCKED: "+message)

def read_archive():
    with ARCHIVE.open(newline="",encoding="utf-8-sig") as h:
        rows=list(csv.DictReader(h))
    dates=[r["data"] for r in rows]
    if len(dates)!=len(set(dates)) or dates!=sorted(dates):
        fail("archive dates are not unique/chronological")
    draws=[]
    for row in rows:
        values=[int(row[f"n{i}"]) for i in range(1,6)]
        if len(set(values))!=5 or any(x<1 or x>40 for x in values):
            fail("invalid archive quintet")
        draws.append(values)
    return dates,draws

def formula_id(cols):
    return "P9_"+"_".join(f"{x:02d}" for x in cols)

def formula_rank(cols):
    if len(cols)!=9 or list(cols)!=sorted(set(cols)) or cols[-1]>=27:
        raise ValueError("invalid nine-feature combination")
    rank=0
    previous=-1
    for position,value in enumerate(cols):
        for candidate in range(previous+1,value):
            rank += math.comb(27-candidate-1,9-position-1)
        previous=value
    return rank

def unrank_lex_combination(n,k,rank):
    if rank<0 or rank>=math.comb(n,k):
        raise ValueError("combination rank outside universe")
    result=[]
    previous=-1
    for position in range(k):
        for candidate in range(previous+1,n):
            block=math.comb(n-candidate-1,k-position-1)
            if rank<block:
                result.append(candidate)
                previous=candidate
                break
            rank-=block
    return tuple(result)

def hypergeom_probabilities(top_k):
    denominator=math.comb(40,5)
    probs=[math.comb(top_k,h)*math.comb(40-top_k,5-h)/denominator for h in range(6)]
    if not math.isclose(math.fsum(probs),1.0,rel_tol=0,abs_tol=1e-14):
        fail("hypergeometric null probabilities do not sum to one")
    return probs

def build_chernoff_tail_table(targets,top_k):
    """Conservative upper bounds for P(sum_t Hypergeom(40, top_k, 5) >= s)."""
    if targets<=0 or top_k not in (5,10,20):
        raise ValueError("invalid Chernoff table parameters")
    probs=hypergeom_probabilities(top_k)
    log_probs=[math.log(p) for p in probs]
    maximum=5*targets
    table=np.ones(maximum+1,dtype=np.float64)
    mean_total=targets*math.fsum(h*p for h,p in enumerate(probs))
    def tilted_mean(lam):
        terms=[log_probs[h]+lam*h for h in range(6)]
        pivot=max(terms)
        weights=[math.exp(x-pivot) for x in terms]
        return math.fsum(h*w for h,w in enumerate(weights))/math.fsum(weights)
    def log_mgf(lam):
        terms=[log_probs[h]+lam*h for h in range(6)]
        pivot=max(terms)
        return pivot+math.log(math.fsum(math.exp(x-pivot) for x in terms))
    floor=math.log(1e-300)
    for successes in range(int(math.floor(mean_total))+1,maximum):
        target_mean=successes/targets
        lo,hi=0.0,1.0
        while tilted_mean(hi)<target_mean and hi<64.0:
            hi*=2.0
        if tilted_mean(hi)<target_mean:
            fail("Chernoff saddlepoint did not bracket observed mean")
        for _ in range(64):
            mid=(lo+hi)/2.0
            if tilted_mean(mid)<target_mean:
                lo=mid
            else:
                hi=mid
        lam=(lo+hi)/2.0
        log_bound=targets*log_mgf(lam)-lam*successes
        if log_bound>=0:
            bound=1.0
        elif log_bound<=floor:
            bound=1e-300
        else:
            bound=min(1.0,math.exp(log_bound)*(1.0+1e-12))
        table[successes]=max(1e-300,bound)
    log_max=targets*math.log(probs[5])
    table[maximum]=1.0 if log_max>=0 else max(1e-300,math.exp(max(floor,log_max)))
    return table

def apply_holm_inplace(pvalues,chunk_size=HOLM_CHUNK):
    tests=len(pvalues)
    order=np.argsort(pvalues,kind="stable")
    running=0.0
    for start in range(0,tests,chunk_size):
        end=min(start+chunk_size,tests)
        indices=order[start:end]
        multiplier=tests-np.arange(start,end,dtype=np.float64)
        adjusted=np.maximum.accumulate(multiplier*pvalues[indices])
        if running>0:
            adjusted=np.maximum(adjusted,running)
        adjusted=np.minimum(adjusted,1.0)
        running=float(adjusted[-1])
        pvalues[indices]=adjusted
    del order
    return pvalues

def select_validation_candidate(discovery_top,validation_rows):
    ids=[row["formula_id"] for row in discovery_top]
    if not ids or any(fid not in validation_rows for fid in ids):
        raise ValueError("Discovery candidates missing Validation rows")
    def key(fid):
        row=validation_rows[fid]
        parts=[int(x) for x in fid.split("_")[1:]]
        return (float(row["mean_number_hits_top5"]),
                -float(row["mean_rank_of_actual_numbers"]),
                -formula_rank(parts))
    return max(ids,key=key)

def compact_metric(row):
    keys=("formula_id","features","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20",
          "mean_rank_of_actual_numbers","p_top5_hypergeom_chernoff_bound","p_top10_hypergeom_chernoff_bound",
          "p_top20_hypergeom_chernoff_bound","holm_p_max_endpoint_family")
    return {k:(row[k] if k in ("formula_id","features") else float(row[k])) for k in keys}

def main():
    dates,draws=read_archive()
    source_sha=hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()
    expected=os.environ.get("SONAR_Q89_EXPECTED_ARCHIVE_SHA256",EXPECTED_ARCHIVE_SHA256)
    if source_sha!=expected:
        fail("canonical archive SHA differs from preregistered 2026-11-07 snapshot")
    scored=len(draws)-q80.MIN_HISTORY
    discovery=math.ceil(.60*scored)
    validation=math.ceil(.80*scored)
    expected_split={"discovery":discovery,"validation":validation-discovery,"blind_oos":scored-validation}
    total_rows=TOTAL*3
    tests=total_rows*3
    pvalues=np.empty(tests,dtype=np.float64)
    seen={s:np.zeros(TOTAL,dtype=np.bool_) for s in SPLITS}
    counts=Counter()
    headers=None
    cursor=0
    tails={(split,k):build_chernoff_tail_table(expected_split[split],k)
           for split in SPLITS for k in (5,10,20)}
    shard_sizes=[]
    for shard in range(SHARDS):
        start=(TOTAL*shard)//SHARDS
        end=(TOTAL*(shard+1))//SHARDS
        shard_size=end-start
        shard_sizes.append(shard_size)
        path=SHARD_DIR/f"shard_{shard}_metrics.csv"
        if not path.is_file():
            fail(f"missing metrics for shard {shard}")
        local=Counter()
        with path.open(newline="",encoding="utf-8-sig") as handle:
            reader=csv.DictReader(handle)
            if headers is None:
                headers=reader.fieldnames
            elif reader.fieldnames!=headers:
                fail("shard metric schemas differ")
            for row in reader:
                split=row.get("split")
                if split not in SPLITS:
                    fail("invalid split")
                try:
                    prefix,*tokens=row["formula_id"].split("_")
                    parts=[int(x) for x in tokens]
                    if prefix!="P9" or len(parts)!=9 or parts!=sorted(set(parts)) or parts[-1]>=27:
                        fail("invalid formula id")
                    if row["formula_id"]!=formula_id(parts):
                        fail("non-canonical formula id")
                    index=formula_rank(parts)
                    if not start<=index<end:
                        fail("formula outside its declared shard")
                    if seen[split][index]:
                        fail("duplicate formula within split")
                    seen[split][index]=True
                except Exception as exc:
                    if isinstance(exc,SystemExit):
                        raise
                    fail("cannot parse formula id: "+str(exc))
                if row.get("features")!="+".join(FEATURES[i] for i in parts) or int(row.get("feature_count",-1))!=9:
                    fail("feature schema mismatch")
                targets=int(row.get("targets",-1))
                if targets!=expected_split[split]:
                    fail("split target count mismatch")
                values=[]
                for endpoint in ("top5","top10","top20"):
                    value=int(row.get(f"number_hits_{endpoint}_total",-1))
                    if value<0 or value>5*targets:
                        fail("invalid number-hit total")
                    values.append(value)
                pvalues[cursor*3:cursor*3+3]=[
                    tails[(split,5)][values[0]],tails[(split,10)][values[1]],tails[(split,20)][values[2]]]
                local[split]+=1
                counts[split]+=1
                cursor+=1
        if local!={s:shard_size for s in SPLITS}:
            fail(f"shard {shard} formula/split count mismatch")
    if cursor!=total_rows or any(not seen[s].all() for s in SPLITS) or counts!={s:TOTAL for s in SPLITS}:
        fail("global formula coverage has a gap, overlap or split-count mismatch")
    pvalues=apply_holm_inplace(pvalues)
    row_holm=np.max(pvalues.reshape(total_rows,3),axis=1)
    p_fields=["p_top5_hypergeom_chernoff_bound","p_top10_hypergeom_chernoff_bound",
              "p_top20_hypergeom_chernoff_bound","holm_p_max_endpoint_family"]
    output_fields=headers+p_fields
    parts_manifest=[]
    part_index=-1
    text_handle=None
    raw_handle=None
    writer=None
    part_rows=0
    written=0
    discovery_heap=[]
    def open_part():
        nonlocal part_index,text_handle,raw_handle,writer,part_rows
        if text_handle:
            text_handle.close()
        if raw_handle:
            raw_handle.close()
        part_index+=1
        part_rows=0
        path=OUT/f"per_number_condition_9plus_formula_metrics_part_{part_index:03d}.csv.gz"
        raw_handle=path.open("wb")
        zipped=gzip.GzipFile(fileobj=raw_handle,mode="wb",mtime=0)
        text_handle=io.TextIOWrapper(zipped,encoding="utf-8",newline="")
        writer=csv.DictWriter(text_handle,fieldnames=output_fields)
        writer.writeheader()
    try:
        for shard in range(SHARDS):
            with (SHARD_DIR/f"shard_{shard}_metrics.csv").open(newline="",encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    if text_handle is None or part_rows>=CHUNK_ROWS:
                        open_part()
                    split=row["split"]
                    s5=int(row["number_hits_top5_total"])
                    s10=int(row["number_hits_top10_total"])
                    s20=int(row["number_hits_top20_total"])
                    row["p_top5_hypergeom_chernoff_bound"]=f"{tails[(split,5)][s5]:.17g}"
                    row["p_top10_hypergeom_chernoff_bound"]=f"{tails[(split,10)][s10]:.17g}"
                    row["p_top20_hypergeom_chernoff_bound"]=f"{tails[(split,20)][s20]:.17g}"
                    row["holm_p_max_endpoint_family"]=f"{row_holm[written]:.17g}"
                    writer.writerow(row)
                    if split=="discovery":
                        cols=[int(x) for x in row["formula_id"].split("_")[1:]]
                        index=formula_rank(cols)
                        key=(float(row["mean_number_hits_top5"]),-float(row["mean_rank_of_actual_numbers"]),-index)
                        item=(key,compact_metric(row))
                        if len(discovery_heap)<100:
                            heapq.heappush(discovery_heap,item)
                        elif key>discovery_heap[0][0]:
                            heapq.heapreplace(discovery_heap,item)
                    part_rows+=1
                    written+=1
    finally:
        if text_handle:
            text_handle.close()
        if raw_handle:
            raw_handle.close()
    if written!=total_rows:
        fail("chunked metrics row count mismatch")
    row_cursor=0
    for i in range(part_index+1):
        path=OUT/f"per_number_condition_9plus_formula_metrics_part_{i:03d}.csv.gz"
        with gzip.open(path,"rt",newline="",encoding="utf-8") as handle:
            count=sum(1 for _ in handle)-1
        raw=path.read_bytes()
        parts_manifest.append({"part_index":i,"path":str(path.relative_to(ROOT)),"rows":count,
            "row_start_inclusive":row_cursor,"row_end_exclusive":row_cursor+count,
            "bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
        row_cursor+=count
    discovery_top=[item[1] for item in sorted(discovery_heap,key=lambda x:x[0],reverse=True)]
    if len(discovery_top)!=100:
        fail("Discovery did not produce exactly 100 candidates")
    discovery_ids={row["formula_id"] for row in discovery_top}
    validation_rows={}
    for part in parts_manifest:
        with gzip.open(ROOT/part["path"],"rt",newline="",encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["split"]=="validation" and row["formula_id"] in discovery_ids:
                    validation_rows[row["formula_id"]]=row
    if len(validation_rows)!=100:
        fail("Discovery top-100 missing Validation rows")
    selected_id=select_validation_candidate(discovery_top,validation_rows)
    selected_discovery=next(x for x in discovery_top if x["formula_id"]==selected_id)
    selected_validation=compact_metric(validation_rows[selected_id])
    selected_blind=None
    for part in parts_manifest:
        with gzip.open(ROOT/part["path"],"rt",newline="",encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["split"]=="blind_oos" and row["formula_id"]==selected_id:
                    selected_blind=compact_metric(row)
                    break
        if selected_blind is not None:
            break
    if selected_blind is None:
        fail("frozen Validation candidate has no Blind OOS row")
    date_index={d:i for i,d in enumerate(dates)}
    best_by_date={}
    for shard in range(SHARDS):
        path=SHARD_DIR/f"shard_{shard}_target_ledger.csv"
        if not path.is_file():
            fail(f"missing target ledger for shard {shard}")
        with path.open(newline="",encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                d=row["target_date"]
                if d not in date_index:
                    fail("ledger target not found in archive")
                index=date_index[d]
                if row["cutoff_date"]!=dates[index-1] or int(row["prior_draws"])!=index:
                    fail("ledger strict-prior cutoff mismatch")
                if row["actual_quintet"]!=" ".join(map(str,draws[index])):
                    fail("ledger actual quintet mismatch")
                cols=[int(x) for x in row["best_formula_id"].split("_")[1:]]
                if len(cols)!=9 or row["best_formula_id"]!=formula_id(cols):
                    fail("ledger best formula id invalid")
                key=(int(row["best_rank_sum"]),int(row["best_number_hits_top20"]),
                     -int(row["best_number_hits_top5"]),row["best_formula_id"])
                old=best_by_date.get(d)
                if old is None or key<old[0]:
                    best_by_date[d]=(key,row)
    if len(best_by_date)!=scored:
        fail("global target ledger coverage mismatch")
    ledgers=[best_by_date[d][1] for d in dates[q80.MIN_HISTORY:]]
    with LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(ledgers[0].keys()))
        writer.writeheader()
        for d in dates[q80.MIN_HISTORY:]:
            row=dict(best_by_date[d][1])
            row["formula_count_tested"]=TOTAL
            writer.writerow(row)
    batches=[]
    for batch_index,start in enumerate(range(0,TOTAL,1024)):
        end=min(start+1024,TOTAL)
        batches.append({"batch_index":batch_index,"formula_start_inclusive":start,
            "formula_end_exclusive":end,"formula_count":end-start,
            "formula_id_first":formula_id(unrank_lex_combination(27,9,start)),
            "formula_id_last":formula_id(unrank_lex_combination(27,9,end-1))})
    parts_sha=hashlib.sha256(json.dumps(parts_manifest,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    protocol_sha=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report={"schema_version":"1.0","task_id":"Q89","status":"AGGREGATED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status":"PENDING_HUMAN_REVIEW_INTEGRATION","source_archive":"data/storico_daily.csv",
        "source_archive_sha256":source_sha,"protocol":"reports/sequence_agent/q89_protocol_2026-11-09.json",
        "protocol_sha256":protocol_sha,"target_count":len(draws),"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":q80.MIN_HISTORY,"scored_targets":scored,"split_counts":expected_split,
        "feature_count":27,"features":FEATURES,"formula_size":9,"formula_count":TOTAL,
        "formula_count_check":math.comb(27,9),"formula_grammar":"all 9-feature equal-weight combinations",
        "scoring_rule":"z-score each of 27 prior-only features over numbers 1..40, then average each unordered nine-feature subset",
        "formula_batch_size":1024,"formula_batch_count":len(batches),"batch_manifest":batches,
        "shard_count":SHARDS,"shard_formula_counts":shard_sizes,
        "metrics_storage":"chunked_csv_gzip_parts","metrics_rows":total_rows,"target_ledger_rows":scored,
        "metrics_parts":parts_manifest,
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":tests,
            "p_value_method":"conservative Chernoff upper bound for sums of per-target Hypergeometric(40,k,5) hit counts, conditional on past-only rankings"},
        "holm_adjusted_formula_split_rows_below_0_05":int(np.sum(row_holm<0.05)),
        "minimum_holm_p_max_endpoint_family":float(np.min(row_holm)),
        "uniform_number_rank_baseline":{"mean_number_hits_top5":0.125,"mean_number_hits_top10":0.25,
            "mean_number_hits_top20":0.5,"mean_rank_of_actual_numbers":20.5},
        "selection_protocol":{"discovery_top_k":100,
            "discovery_ranking":"mean_number_hits_top5 descending, mean_rank_of_actual_numbers ascending, formula lexicographic rank ascending",
            "validation_freeze":"select best Validation mean_number_hits_top5 among Discovery top-100 with same tie-breaks",
            "blind_oos_used_for_selection":False},
        "candidate_selection":{"status":"FROZEN_AFTER_VALIDATION_PENDING_HUMAN_REVIEW",
            "selected_formula_id":selected_id,"selected_features":selected_validation["features"],
            "discovery_metrics":selected_discovery,"validation_metrics":selected_validation,
            "blind_oos_metrics":selected_blind,"blind_oos_used_for_selection":False},
        "discovery_top_100":discovery_top,"best_per_target_ledger_is_retrospective_descriptive":True,
        "guardrails":["all target features use only draws strictly before the target",
            "all 40 numbers are ranked before scoring the actual quintet",
            "per-target best formula is retrospective/descriptive, never a prospective forecast",
            "candidate selection uses Discovery top-100 then Validation freeze; Blind OOS is read only for the frozen candidate",
            "global Holm covers every formula x split x endpoint test across the full nine-feature family",
            "Chernoff bounds are conservative under the registered uniform 5-of-40 conditional null",
            "finite nine-feature equal-weight grammar only; thresholded, nonlinear and interaction grammars remain open",
            "immutable prospective freezes are preserved; no automatic promotion or merge"],
        "outputs":{"metrics_parts":[x["path"] for x in parts_manifest],
            "metrics_manifest":"reports/sequence_agent/per_number_condition_9plus_formula_metrics_manifest.json",
            "metrics_parts_manifest_sha256":parts_sha,
            "target_ledger":"reports/sequence_agent/per_number_condition_9plus_target_ledger.csv"}}
    manifest={"schema_version":"1.0","task_id":"Q89","storage_format":"chunked_csv_gzip_parts",
        "source_archive_sha256":source_sha,"formula_count":TOTAL,"metrics_rows":total_rows,
        "part_count":len(parts_manifest),"parts_manifest_sha256":parts_sha,"parts":parts_manifest}
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    METRICS_MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SONAR_Q89_AGGREGATE_BEGIN")
    print(json.dumps({k:report[k] for k in ("task_id","status","target_count","last_date","scored_targets",
        "formula_count","metrics_rows","target_ledger_rows","multiple_testing",
        "holm_adjusted_formula_split_rows_below_0_05","minimum_holm_p_max_endpoint_family","candidate_selection")},
        ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q89_AGGREGATE_END")

if __name__=="__main__":
    main()
