#!/usr/bin/env python3
"""Seeded fixed-sample throughput sweep for Q92 exact selective actual-number ranking."""
from __future__ import annotations
import json
import statistics
import time
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q92_common as q92
import sonar_per_number_condition_10plus_shard as runner

SEED=920092
ACTUAL_SEED=920093
FORMULA_COUNT=4096
BASELINE_BATCH=1024
CANDIDATE_BATCH_SIZES=(512,1024,2048,4096)
REPEATS=25
MIN_SPEEDUP=1.25

def old_rank_matrix(scores):
    order=np.argsort(-scores,axis=0,kind="stable")
    ranks=np.empty(order.shape,dtype=np.int16)
    ranks[order,np.arange(scores.shape[1])]=np.arange(1,scores.shape[0]+1,dtype=np.int16)[:,None]
    return ranks

def timed_median(function):
    for _ in range(3):
        function()
    samples=[]
    for _ in range(REPEATS):
        started=time.perf_counter()
        function()
        samples.append(time.perf_counter()-started)
    return statistics.median(samples),min(samples),max(samples)

def baseline_sample(standardized,weights,actual_indices):
    outputs=[]
    for start in range(0,FORMULA_COUNT,BASELINE_BATCH):
        end=min(start+BASELINE_BATCH,FORMULA_COUNT)
        scores=standardized@weights[:,start:end]
        outputs.append(old_rank_matrix(scores)[actual_indices,:])
    return outputs

def candidate_sample(standardized,weights,actual_indices,batch_size):
    outputs=[]
    for start in range(0,FORMULA_COUNT,int(batch_size)):
        end=min(start+int(batch_size),FORMULA_COUNT)
        scores=standardized@weights[:,start:end]
        outputs.append(runner.rank_actual_numbers(scores,actual_indices))
    return outputs

def main():
    rng=np.random.default_rng(SEED)
    formula_ranks=rng.choice(q92.TOTAL_FORMULA_COUNT,size=FORMULA_COUNT,replace=False)
    formulas=[q92.formula_unrank(int(rank)) for rank in formula_ranks]
    standardized=rng.normal(size=(40,27)).astype(np.float64)
    weights=np.zeros((27,FORMULA_COUNT),dtype=np.float64)
    for index,columns in enumerate(formulas):
        weights[list(columns),index]=1.0/q92.FORMULA_SIZE
    actual_rng=np.random.default_rng(ACTUAL_SEED)
    actual_indices=np.sort(actual_rng.choice(40,size=5,replace=False))

    full_scores=standardized@weights
    full_old=old_rank_matrix(full_scores)[actual_indices,:]
    full_new=runner.rank_actual_numbers(full_scores,actual_indices)
    if not np.array_equal(full_old,full_new):
        raise SystemExit("Q92_BATCH_SWEEP_BLOCKED: full-sample actual-number ranks differ")

    baseline_time,baseline_min,baseline_max=timed_median(lambda:baseline_sample(standardized,weights,actual_indices))
    baseline_throughput=FORMULA_COUNT/baseline_time
    candidate_results=[]
    for batch_size in CANDIDATE_BATCH_SIZES:
        chunks=candidate_sample(standardized,weights,actual_indices,batch_size)
        observed=np.concatenate(chunks,axis=1)
        if not np.array_equal(full_old,observed):
            raise SystemExit("Q92_BATCH_SWEEP_BLOCKED: rank parity failed for batch "+str(batch_size))
        candidate_time,candidate_min,candidate_max=timed_median(lambda: candidate_sample(standardized,weights,actual_indices,batch_size))
        throughput=FORMULA_COUNT/candidate_time
        candidate_results.append({
            "batch_size":batch_size,
            "batch_count":len(chunks),
            "median_seconds":candidate_time,
            "min_seconds":candidate_min,
            "max_seconds":candidate_max,
            "formulas_per_second":throughput,
            "speedup_vs_baseline":throughput/baseline_throughput,
            "exact_rank_parity":True
        })
    best=max(candidate_results,key=lambda row:row["formulas_per_second"])
    result={
        "experiment":"Q92-RANK-KERNEL-03",
        "seed":SEED,
        "actual_number_seed":ACTUAL_SEED,
        "formula_sample_count":FORMULA_COUNT,
        "actual_number_indices":actual_indices.tolist(),
        "baseline_batch_size":BASELINE_BATCH,
        "baseline_batch_count":FORMULA_COUNT//BASELINE_BATCH,
        "repeats":REPEATS,
        "baseline_median_seconds":baseline_time,
        "baseline_min_seconds":baseline_min,
        "baseline_max_seconds":baseline_max,
        "baseline_formulas_per_second":baseline_throughput,
        "candidate_batch_results":candidate_results,
        "selected_batch_size":best["batch_size"],
        "selected_batch_speedup":best["speedup_vs_baseline"],
        "minimum_registered_speedup":MIN_SPEEDUP,
        "full_sample_rank_vectors_exactly_equal":True,
        "decision":"PASS" if best["speedup_vs_baseline"]>=MIN_SPEEDUP else "FAIL",
        "selection_rule":"max median formula throughput among fixed batch sizes 512,1024,2048,4096; no historical outcomes used",
        "scope":"synthetic engineering sweep only; no historical lottery outcomes evaluated"
    }
    print("SONAR_Q92_BATCH_SWEEP_BEGIN")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    print("SONAR_Q92_BATCH_SWEEP_END")
    if best["speedup_vs_baseline"]<MIN_SPEEDUP:
        raise SystemExit("Q92_BATCH_SWEEP_BLOCKED: no candidate batch reached preregistered 1.25x speedup")

if __name__=="__main__":
    main()
