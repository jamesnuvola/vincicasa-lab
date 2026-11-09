#!/usr/bin/env python3
"""Reproducible throughput experiment for the Q92 formula-major rank kernel."""
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
FORMULA_COUNT=4096
BASELINE_BATCH=1024
REPEATS=25
MIN_SPEEDUP=1.10

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
    ranks=rng.choice(q92.TOTAL_FORMULA_COUNT,size=FORMULA_COUNT,replace=False)
    formulas=[q92.formula_unrank(int(rank)) for rank in ranks]
    standardized=rng.normal(size=(40,27)).astype(np.float64)
    old_weights=np.zeros((27,FORMULA_COUNT),dtype=np.float64)
    new_weights=np.zeros((FORMULA_COUNT,27),dtype=np.float64)
    for index,columns in enumerate(formulas):
        old_weights[list(columns),index]=1.0/q92.FORMULA_SIZE
        new_weights[index,list(columns)]=1.0/q92.FORMULA_SIZE

    old_scores=standardized@old_weights[:,:BASELINE_BATCH]
    old_ranks=old_rank_matrix(old_scores)
    new_scores=new_weights[:BASELINE_BATCH]@standardized.T
    new_ranks=runner.rank_matrix(new_scores)
    if not np.array_equal(old_ranks,new_ranks.T):
        raise SystemExit("Q92_RANK_KERNEL_BENCH_BLOCKED: rank vectors differ on common formulas")

    old_time,old_min,old_max=timed_median(lambda:old_rank_matrix(standardized@old_weights[:,:BASELINE_BATCH]))
    new_time,new_min,new_max=timed_median(lambda:runner.rank_matrix(new_weights@standardized.T))
    old_throughput=BASELINE_BATCH/old_time
    new_throughput=FORMULA_COUNT/new_time
    speedup=new_throughput/old_throughput
    result={
        "experiment":"Q92-RANK-KERNEL-01",
        "seed":SEED,
        "formula_sample_count":FORMULA_COUNT,
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
        "decision":"PASS" if speedup>=MIN_SPEEDUP else "FAIL",
        "scope":"synthetic kernel benchmark only; no historical lottery outcomes evaluated"
    }
    print("SONAR_Q92_RANK_KERNEL_BENCH_BEGIN")
    print(json.dumps(result,sort_keys=True,separators=(",",":")))
    print("SONAR_Q92_RANK_KERNEL_BENCH_END")
    if speedup<MIN_SPEEDUP:
        raise SystemExit("Q92_RANK_KERNEL_BENCH_BLOCKED: throughput speedup below preregistered 1.10")

if __name__=="__main__":
    main()
