#!/usr/bin/env python3
"""Deterministic combinadic utilities for the preregistered Q92 ten-feature catalog."""
from __future__ import annotations
import itertools
import math

FEATURE_COUNT = 27
FORMULA_SIZE = 10
TOTAL_FORMULA_COUNT = math.comb(FEATURE_COUNT, FORMULA_SIZE)
SHARD_COUNT = 15
if TOTAL_FORMULA_COUNT % SHARD_COUNT:
    raise RuntimeError("Q92 formula universe is not evenly shardable")
SHARD_SIZE = TOTAL_FORMULA_COUNT // SHARD_COUNT
FORMULA_BATCH_SIZE = 1024

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
