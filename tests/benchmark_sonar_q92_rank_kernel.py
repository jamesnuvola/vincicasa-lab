#!/usr/bin/env python3
"""Seeded throughput experiment for Q92 exact selective actual-number ranking."""
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

    old_scores=standardized@weights[:,:BASELINE_BATCH]
    old_ranks=old_rank_matrix(old_scores)[actual_indices,:]
    new_scores=standardized@weights
    new_ranks=runner.rank_actual_numbers(new_scores,actual_indices)
    if not np.array_equal(old_ranks,new_ranks[:,:BASELINE_BATCH]):
        raise SystemExit("Q92_SELECTIVE_RANK_BENCH_BLOCKED: common actual-number ranks differ")
    full_old=old_rank_matrix(standardized@weights)[actual_indices,:]
    full_new=runner.rank_actual_numbers(standardized@weights,actual_indices)
    if not np.array_equal(full_old,full_new):
        raise SystemExit("Q92_SELECTIVE_RANK_BENCH_BLOCKED: full seeded sample actual-number ranks differ")

    old_time,old_min,old_max=timed_median(lambda:old_rank_matrix(standardized@weights[:,:BASELINE_BATCH])[actual_indices,:])
    new_time,new_min,new_max=timed_median(lambda:runner.rank_actual_numbers(standardized@weights,actual_indices))
    old_throughput=BASELINE_BATCH/old_time
    new_throughput=FORMULA_COUNT/new_time
    speedup=new_throughput/old_throughput
    result={
        "experiment":"Q92-RANK-KERNEL-02",
        "seed":SEED,
        "actual_number_seed":ACTUAL_SEED,
        "formula_sample_count":FORMULA_COUNT,
        "actual_number_indices":actual_indices.tolist(),
        "baseline_batch_size":BASELINE_BATCH,
        "candidate_batch_size":FORMULA_COUNT,
        "repeats":REPEATS,
        "baseline_median_seconds":old_time,
        "baseline_min_seconds":old_min,
        "baseline_max_seconds":old_max,
        "candidate_median_seconds":new_time,
        "candidate_min_seconds":new_min,
        "candidate_max_seconds":new_max,
        "baseline_formulas_per_second":old_throughput,
        "candidate_formulas_per_second":new_throughput,
        "throughput_speedup":speedup,
        "minimum_registered_speedup":MIN_SPEEDUP,
        "rank_vectors_exactly_equal":True,
        "full_sample_rank_vectors_exactly_equal":True,
        "decision":"PASS" if speedup>=MIN_SPEEDUP else "FAIL",
        "scope":"synthetic selective-rank benchmark only; no historical lottery outcomes evaluated"
    }
    print("SONAR_Q92_SELECTIVE_RANK_BENCH_BEGIN")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    print("SONAR_Q92_SELECTIVE_RANK_BENCH_END")
    if speedup<MIN_SPEEDUP:
        raise SystemExit("Q92_SELECTIVE_RANK_BENCH_BLOCKED: throughput speedup below preregistered 1.25")

if __name__=="__main__":
    main()
