#!/usr/bin/env python3
"""Deterministic combinadic utilities for the preregistered Q92 ten-feature catalog."""
from __future__ import annotations
import hashlib
import itertools
import math
from pathlib import Path
import sonar_q92_null_calibration as q92null

FEATURE_COUNT = 27
FORMULA_SIZE = 10
TOTAL_FORMULA_COUNT = math.comb(FEATURE_COUNT, FORMULA_SIZE)
SHARD_COUNT = 15
if TOTAL_FORMULA_COUNT % SHARD_COUNT:
    raise RuntimeError("Q92 formula universe is not evenly shardable")
SHARD_SIZE = TOTAL_FORMULA_COUNT // SHARD_COUNT
FORMULA_BATCH_SIZE = 4096

COMPACT_METRIC_FIELDS=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")
SOURCE_CODE_HASH_PATHS=(
    # Execution engine and strict-prior feature stack.
    "scripts/sonar_per_number_condition_10plus_shard.py",
    "scripts/sonar_q92_common.py",
    "scripts/sonar_q92_null_calibration.py",
    "scripts/sonar_per_number_condition_grammar.py",
    "scripts/sonar_per_number_condition_4plus_grammar.py",
    # Global selection, Holm replay and acceptance.
    "scripts/sonar_q92_aggregate_common.py",
    "scripts/aggregate_sonar_q92_ten_feature.py",
    "scripts/validate_sonar_q92_ten_feature.py",
    # Workflow definitions and preregistration are part of reproducibility.
    ".github/workflows/sonar-q92-ten-feature.yml",
    ".github/workflows/sonar-q92-aggregate-core.yml",
    "tests/benchmark_sonar_q92_rank_kernel.py",
    "tests/test_sonar_q92_walkforward_shard.py",
    "reports/sequence_agent/q92_preregistration_2026-11-09.json",
    # Canonical input archive; its Git/SHA-256 identities are recorded separately too.
    "data/storico_daily.csv",
)

def source_code_hashes(root: Path):
    root=Path(root)
    return {relative:hashlib.sha256((root/relative).read_bytes()).hexdigest() for relative in SOURCE_CODE_HASH_PATHS}

def integer_from_mean(value,denominator,label,tolerance=2e-6):
    raw=float(value)*int(denominator);rounded=int(round(raw))
    if not math.isfinite(raw) or abs(raw-rounded)>float(tolerance):
        raise ValueError(str(label)+" cannot be reconstructed as an exact integer count")
    return rounded

def compact_counts_from_raw_metrics(row,targets):
    targets=int(targets)
    if targets<=0:raise ValueError("compact metrics target count must be positive")
    return {
        "number_hits_top5":integer_from_mean(row["mean_number_hits_top5"],5*targets,"Top5 hits"),
        "number_hits_top10":integer_from_mean(row["mean_number_hits_top10"],5*targets,"Top10 hits"),
        "number_hits_top20":integer_from_mean(row["mean_number_hits_top20"],5*targets,"Top20 hits"),
        "all5_top5":integer_from_mean(row["all5_top5_rate"],targets,"All-five Top5"),
        "all5_top10":integer_from_mean(row["all5_top10_rate"],targets,"All-five Top10"),
        "all5_top20":integer_from_mean(row["all5_top20_rate"],targets,"All-five Top20"),
        "rank_sum":integer_from_mean(row["mean_rank_of_actual_numbers"],5*targets,"rank sum"),
    }

def metric_summary_from_compact_counts(counts,targets):
    targets=int(targets)
    if targets<=0:raise ValueError("compact metrics target count must be positive")
    def read_count(field,low,high):
        value=counts[field]
        if isinstance(value,bool):raise ValueError(field+" must be an integer, not bool")
        try:integer=int(value)
        except Exception as exc:raise ValueError(field+" must be an integer") from exc
        if isinstance(value,str) and value!=str(integer):raise ValueError(field+" is not canonical integer text")
        if isinstance(value,float) and (not math.isfinite(value) or value!=integer):raise ValueError(field+" is not an exact integer")
        if int(low)<=integer<=int(high):return integer
        raise ValueError(field+" outside declared range")
    s5=read_count("number_hits_top5",0,5*targets);s10=read_count("number_hits_top10",0,5*targets);s20=read_count("number_hits_top20",0,5*targets)
    a5=read_count("all5_top5",0,targets);a10=read_count("all5_top10",0,targets);a20=read_count("all5_top20",0,targets)
    rank_sum=read_count("rank_sum",5*targets,200*targets)
    return {
        "mean_number_hits_top5":s5/(5*targets),"mean_number_hits_top10":s10/(5*targets),"mean_number_hits_top20":s20/(5*targets),
        "all5_top5_rate":a5/targets,"all5_top10_rate":a10/targets,"all5_top20_rate":a20/targets,
        "mean_rank_of_actual_numbers":rank_sum/(5*targets),
        "p_top5_exact_hypergeom_sum":q92null.exact_upper_tail_pvalue(s5,targets,5),
        "p_top10_exact_hypergeom_sum":q92null.exact_upper_tail_pvalue(s10,targets,10),
        "p_top20_exact_hypergeom_sum":q92null.exact_upper_tail_pvalue(s20,targets,20),
    }


def formula_id(columns):
    columns = tuple(columns)
    if len(columns) != FORMULA_SIZE or tuple(sorted(set(columns))) != columns:
        raise ValueError("Q92 formula columns must be ten unique sorted indices")
    if columns[0] < 0 or columns[-1] >= FEATURE_COUNT:
        raise ValueError("Q92 formula index outside feature catalog")
    return "P10_" + "_".join(f"{value:02d}" for value in columns)

def formula_rank(columns):
    columns = tuple(columns)
    if len(columns) != FORMULA_SIZE or tuple(sorted(set(columns))) != columns:
        raise ValueError("Q92 formula columns must be ten unique sorted indices")
    if columns[0] < 0 or columns[-1] >= FEATURE_COUNT:
        raise ValueError("Q92 formula index outside feature catalog")
    rank = 0
    previous = -1
    for position, value in enumerate(columns):
        for candidate in range(previous + 1, value):
            rank += math.comb(FEATURE_COUNT - candidate - 1, FORMULA_SIZE - position - 1)
        previous = value
    return rank

def formula_unrank(rank):
    rank = int(rank)
    if rank < 0 or rank >= TOTAL_FORMULA_COUNT:
        raise ValueError("Q92 formula rank outside declared universe")
    remainder = rank
    columns = []
    previous = -1
    for position in range(FORMULA_SIZE):
        for candidate in range(previous + 1, FEATURE_COUNT):
            count = math.comb(FEATURE_COUNT - candidate - 1, FORMULA_SIZE - position - 1)
            if remainder < count:
                columns.append(candidate)
                previous = candidate
                break
            remainder -= count
        else:
            raise RuntimeError("Q92 combinadic unrank failed")
    result = tuple(columns)
    if formula_rank(result) != rank:
        raise RuntimeError("Q92 combinadic rank/unrank mismatch")
    return result

def next_formula(columns):
    """Return the next lexicographic ten-combination without enumerating prior ranks."""
    values = list(columns)
    if len(values) != FORMULA_SIZE:
        raise ValueError("Q92 combination length mismatch")
    if tuple(sorted(set(values))) != tuple(values) or values[0] < 0 or values[-1] >= FEATURE_COUNT:
        raise ValueError("Q92 combination is not canonical")
    for position in range(FORMULA_SIZE - 1, -1, -1):
        if values[position] < FEATURE_COUNT - FORMULA_SIZE + position:
            values[position] += 1
            for following in range(position + 1, FORMULA_SIZE):
                values[following] = values[following - 1] + 1
            return tuple(values)
    return None

def shard_bounds(shard_index):
    shard_index = int(shard_index)
    if shard_index < 0 or shard_index >= SHARD_COUNT:
        raise ValueError("Q92 shard index outside 0..14")
    start = shard_index * SHARD_SIZE
    return start, start + SHARD_SIZE

def iter_formula_slice(start, end):
    """Yield formula tuples in [start,end) via combinadic unrank plus successor."""
    start, end = int(start), int(end)
    if start < 0 or end < start or end > TOTAL_FORMULA_COUNT:
        raise ValueError("Q92 formula slice outside declared universe")
    if start == end:
        return
    columns = formula_unrank(start)
    for rank in range(start, end):
        yield columns
        if rank + 1 < end:
            columns = next_formula(columns)
            if columns is None:
                raise RuntimeError("Q92 combination successor ended early")

def batch_ranges(total, batch_size=FORMULA_BATCH_SIZE):
    if int(batch_size) <= 0:
        raise ValueError("Q92 batch size must be positive")
    return [(start, min(start + int(batch_size), int(total)))
            for start in range(0, int(total), int(batch_size))]

def hypergeom_upper_normal_p(successes, targets, top_k):
    """Continuity-corrected upper-tail normal approximation to summed Hypergeom(40,k,5)."""
    successes = int(successes)
    targets = int(targets)
    top_k = int(top_k)
    if targets <= 0 or top_k < 1 or top_k > 40:
        raise ValueError("Q92 hypergeometric test arguments invalid")
    probability = top_k / 40.0
    mean = targets * 5.0 * probability
    per_target_variance = 5.0 * probability * (1.0 - probability) * (40.0 - 5.0) / (40.0 - 1.0)
    variance = targets * per_target_variance
    if variance <= 0:
        return 1.0 if successes <= mean else 0.0
    z = (successes - 0.5 - mean) / math.sqrt(variance)
    return min(1.0, max(0.0, 0.5 * math.erfc(z / math.sqrt(2.0))))
