#!/usr/bin/env python3
"""Deterministic Q92 global-Holm, candidate-freeze and paired-inference helpers."""
from __future__ import annotations
import math
import numpy as np

FEATURE_COUNT = 27
FORMULA_SIZE = 10
FORMULA_PREFIX = "P10_"
COMPACT_METRIC_FIELDS=("number_hits_top5","number_hits_top10","number_hits_top20","all5_top5","all5_top10","all5_top20","rank_sum")

def parse_formula_id(formula_id: str) -> tuple[int, ...]:
    if not isinstance(formula_id, str) or not formula_id.startswith(FORMULA_PREFIX):
        raise ValueError("Q92 formula ID prefix mismatch")
    columns = tuple(int(value) for value in formula_id[len(FORMULA_PREFIX):].split("_"))
    if len(columns) != FORMULA_SIZE or tuple(sorted(set(columns))) != columns:
        raise ValueError("Q92 formula ID columns are not canonical")
    if columns[0] < 0 or columns[-1] >= FEATURE_COUNT:
        raise ValueError("Q92 formula ID index outside feature catalog")
    if FORMULA_PREFIX + "_".join(f"{value:02d}" for value in columns) != formula_id:
        raise ValueError("Q92 formula ID canonicalization mismatch")
    return columns

def holm_adjust_in_place(pvalues, chunk_size: int = 500_000):
    """Apply global Holm in place with chunked cumulative maxima.

    The p-value array is mutated from raw p-values to adjusted values in its
    original formula×split×endpoint order. The stable argsort is deterministic.
    Chunking bounds temporary memory; the sorted index remains O(m).
    """
    values = np.asarray(pvalues, dtype=np.float64)
    if values.ndim != 1 or values.size == 0:
        raise ValueError("Holm requires a non-empty one-dimensional p-value array")
    if int(chunk_size) <= 0:
        raise ValueError("Holm chunk size must be positive")
    if not np.isfinite(values).all() or float(values.min()) < 0.0 or float(values.max()) > 1.0:
        raise ValueError("Holm input contains non-finite or out-of-range p-values")
    tests = int(values.size)
    order = np.argsort(values, kind="stable")
    carry = 0.0
    for start in range(0, tests, int(chunk_size)):
        end = min(start + int(chunk_size), tests)
        chunk = np.take(values, order[start:end])
        factors = tests - np.arange(start, end, dtype=np.float64)
        np.multiply(chunk, factors, out=chunk)
        if carry > 0.0:
            np.maximum(chunk, carry, out=chunk)
        np.maximum.accumulate(chunk, out=chunk)
        np.clip(chunk, 0.0, 1.0, out=chunk)
        values[order[start:end]] = chunk
        carry = float(chunk[-1])
    return values

def discovery_top_k(rows, k: int = 100):
    """Select deterministic Discovery candidates by Top-5 share, mean rank, ID."""
    if int(k) <= 0:
        raise ValueError("candidate k must be positive")
    materialized = list(rows)
    if len(materialized) < int(k):
        raise ValueError("candidate pool smaller than requested k")
    ordered = sorted(materialized, key=lambda row: (
        -float(row["mean_number_hits_top5"]),
        float(row["mean_rank_of_actual_numbers"]),
        str(row["formula_id"]),
    ))
    return ordered[:int(k)]

def validation_freeze(discovery_candidates):
    """Freeze one candidate on Validation using the registered tie-break."""
    rows = list(discovery_candidates)
    if not rows:
        raise ValueError("Validation candidate set is empty")
    ordered = sorted(rows, key=lambda row: (
        -float(row["validation_mean_number_hits_top5"]),
        float(row["validation_mean_rank_of_actual_numbers"]),
        str(row["formula_id"]),
    ))
    return ordered[0], ordered

def circular_moving_block_bootstrap_ci(deltas, replicates: int = 20_000,
                                      block_length: int = 7, seed: int = 920027,
                                      confidence_level: float = 0.95):
    values = np.asarray(deltas, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("bootstrap deltas must be finite non-empty vector")
    if int(replicates) <= 0 or int(block_length) <= 0 or not 0.0 < confidence_level < 1.0:
        raise ValueError("bootstrap parameters invalid")
    n = int(values.size)
    blocks = int(math.ceil(n / int(block_length)))
    offsets = np.arange(int(block_length), dtype=np.int64)
    rng = np.random.default_rng(int(seed))
    means = np.empty(int(replicates), dtype=np.float64)
    for replicate in range(int(replicates)):
        starts = rng.integers(0, n, size=blocks, dtype=np.int64)
        indices = ((starts[:, None] + offsets[None, :]) % n).ravel()[:n]
        means[replicate] = float(values[indices].mean())
    alpha = (1.0 - float(confidence_level)) / 2.0
    low, high = np.quantile(means, [alpha, 1.0 - alpha], method="linear")
    return float(low), float(high)

def circular_block_signflip_pvalue(deltas, replicates: int = 20_000,
                                   block_length: int = 7, seed: int = 920028):
    """Two-sided circular block sign-flip randomization p-value for paired mean."""
    values = np.asarray(deltas, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("sign-flip deltas must be finite non-empty vector")
    if int(replicates) <= 0 or int(block_length) <= 0:
        raise ValueError("sign-flip parameters invalid")
    n = int(values.size)
    blocks = int(math.ceil(n / int(block_length)))
    observed = abs(float(values.mean()))
    rng = np.random.default_rng(int(seed))
    exceed = 0
    for _ in range(int(replicates)):
        offset = int(rng.integers(0, int(block_length)))
        shifted = np.roll(values, offset)
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=blocks)
        block_signs = np.repeat(signs, int(block_length))[:n]
        statistic = abs(float(np.mean(shifted * block_signs)))
        if statistic >= observed - 1e-15:
            exceed += 1
    return float((exceed + 1) / (int(replicates) + 1))

def paired_endpoint_inference(endpoint_deltas, replicates: int = 20_000,
                              block_length: int = 7, bootstrap_seed: int = 920027,
                              signflip_seed: int = 920028,
                              confidence_level: float = 0.95):
    """Return reproducible paired bootstrap CI, raw sign-flip p and Holm p."""
    names = list(endpoint_deltas)
    if len(names) != 4:
        raise ValueError("Q92 paired inference requires exactly four preregistered endpoints")
    summaries = {}
    raw_pvalues = []
    for name in names:
        values = np.asarray(endpoint_deltas[name], dtype=np.float64)
        if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
            raise ValueError("Q92 paired endpoint contains invalid deltas: " + str(name))
        low, high = circular_moving_block_bootstrap_ci(
            values, replicates=replicates, block_length=block_length,
            seed=bootstrap_seed, confidence_level=confidence_level)
        p_raw = circular_block_signflip_pvalue(
            values, replicates=replicates, block_length=block_length,
            seed=signflip_seed)
        summaries[name] = {
            "n_targets": int(values.size),
            "mean_delta": float(values.mean()),
            "bootstrap_ci_95_low": low,
            "bootstrap_ci_95_high": high,
            "signflip_p_raw": p_raw,
        }
        raw_pvalues.append(p_raw)
    adjusted = holm_adjust_in_place(np.asarray(raw_pvalues, dtype=np.float64), chunk_size=4)
    for index, name in enumerate(names):
        summaries[name]["signflip_p_holm"] = float(adjusted[index])
    primary = summaries[names[0]]
    decision = "SIGNIFICANT_POSITIVE_GAIN" if primary["signflip_p_holm"] < 0.05 and primary["mean_delta"] > 0.0 and primary["bootstrap_ci_95_low"] > 0.0 else "NO_SIGNIFICANT_GAIN"
    return {
        "method": "circular moving-block bootstrap percentile CI and circular block sign-flip randomization",
        "replicates": int(replicates),
        "block_length": int(block_length),
        "bootstrap_seed": int(bootstrap_seed),
        "signflip_seed": int(signflip_seed),
        "confidence_level": float(confidence_level),
        "multiple_testing": {"method": "Holm-Bonferroni", "family_size": 4, "endpoints": names},
        "endpoints": summaries,
        "primary_decision": decision,
    }
