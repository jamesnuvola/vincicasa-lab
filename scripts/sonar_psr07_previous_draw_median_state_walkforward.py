#!/usr/bin/env python3
"""SONAR PSR-07: previous-draw P3 median-state conditional position marginals.

Research-only. Strict expanding-prefix walk-forward, validation-only alpha
selection, exact order-statistic prior, block-aware blind-OOS inference.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

EXPECTED_ARCHIVE_GIT_BLOB_SHA = "5d2efd70684e918b27d8f06386d545647898336d"
ALPHA_GRID = (100, 300, 1000)
WARMUP = 300
BOOTSTRAP_REPLICATES = 2000
BLOCK_LENGTH = 7
SEED_BASE = 20261108
SPLIT_NAMES = ("discovery", "validation", "blind_oos")
POSITION_NAMES = ("P1", "P2", "P3", "P4", "P5")


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def parse_archive_text(text: str) -> tuple[list[str], np.ndarray]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "data,n1,n2,n3,n4,n5":
        raise ValueError("Canonical archive header mismatch")
    dates: list[str] = []
    draws: list[list[int]] = []
    previous_date: dt.date | None = None
    for line_no, line in enumerate(lines[1:], start=2):
        fields = line.split(",")
        if len(fields) != 6:
            raise ValueError(f"CSV field count mismatch at line {line_no}")
        try:
            parsed_date = dt.date.fromisoformat(fields[0])
            numbers = [int(value) for value in fields[1:]]
        except Exception as exc:
            raise ValueError(f"Invalid date/number at line {line_no}") from exc
        if parsed_date.isoformat() != fields[0]:
            raise ValueError(f"Date is not canonical ISO format at line {line_no}")
        if len(numbers) != 5 or any(n < 1 or n > 40 for n in numbers):
            raise ValueError(f"Number domain failure at line {line_no}")
        if len(set(numbers)) != 5 or numbers != sorted(numbers):
            raise ValueError(f"Draw must contain five sorted distinct numbers at line {line_no}")
        if previous_date is not None and parsed_date <= previous_date:
            raise ValueError(f"Dates must be unique and strictly chronological at line {line_no}")
        previous_date = parsed_date
        dates.append(fields[0])
        draws.append(numbers)
    if len(draws) < 2:
        raise ValueError("Insufficient archive rows")
    return dates, np.asarray(draws, dtype=np.int16)


def read_archive(path: Path, expected_sha: str | None = EXPECTED_ARCHIVE_GIT_BLOB_SHA) -> tuple[list[str], np.ndarray, str]:
    raw = path.read_bytes()
    blob_sha = git_blob_sha(raw)
    if expected_sha and blob_sha != expected_sha:
        raise ValueError(f"Archive Git blob SHA mismatch: expected {expected_sha}, got {blob_sha}")
    dates, draws = parse_archive_text(raw.decode("utf-8"))
    return dates, draws, blob_sha


def order_statistic_prior(position: int) -> tuple[np.ndarray, np.ndarray]:
    if position < 1 or position > 5:
        raise ValueError("Position must be in 1..5")
    denominator = math.comb(40, 5)
    domain = np.arange(position, 36 + position, dtype=np.int16)
    probabilities = np.asarray(
        [
            math.comb(int(n) - 1, position - 1)
            * math.comb(40 - int(n), 5 - position)
            / denominator
            for n in domain
        ],
        dtype=np.float64,
    )
    if not np.isclose(probabilities.sum(), 1.0, atol=1e-12, rtol=0.0):
        raise AssertionError(f"Order-statistic prior does not normalize for P{position}")
    return domain, probabilities


def exact_p3_quartile_states() -> tuple[tuple[int, int, int], tuple[float, float, float, float]]:
    denominator = math.comb(40, 5)
    values = range(3, 39)
    counts = {m: math.comb(m - 1, 2) * math.comb(40 - m, 2) for m in values}
    if sum(counts.values()) != denominator:
        raise AssertionError("Exact P3 marginal count normalization failure")
    cuts: list[int] = []
    for quantile in (0.25, 0.50, 0.75):
        cumulative = 0
        cut = None
        for m in values:
            cumulative += counts[m]
            if cumulative >= denominator * quantile:
                cut = m
                break
        if cut is None:
            raise AssertionError("Theoretical P3 quartile could not be calculated")
        cuts.append(cut)
    if tuple(cuts) != (15, 20, 26):
        raise AssertionError(f"Unexpected theoretical P3 cutpoints: {cuts}")
    masses = (
        sum(counts[m] for m in range(3, 16)) / denominator,
        sum(counts[m] for m in range(16, 21)) / denominator,
        sum(counts[m] for m in range(21, 27)) / denominator,
        sum(counts[m] for m in range(27, 39)) / denominator,
    )
    if not np.isclose(sum(masses), 1.0, atol=1e-12, rtol=0.0):
        raise AssertionError("P3 state mass normalization failure")
    return tuple(cuts), tuple(float(x) for x in masses)


STATE_LABELS = (
    "P3_Q1_M<=15",
    "P3_Q2_M=16..20",
    "P3_Q3_M=21..26",
    "P3_Q4_M>=27",
)


def p3_state(value: int, cuts: tuple[int, int, int]) -> int:
    if value < 3 or value > 38:
        raise ValueError(f"P3 value outside theoretical domain: {value}")
    if value <= cuts[0]:
        return 0
    if value <= cuts[1]:
        return 1
    if value <= cuts[2]:
        return 2
    return 3


def posterior_probability(counts: np.ndarray, prior: np.ndarray, alpha: int) -> np.ndarray:
    if alpha <= 0 or counts.shape != prior.shape:
        raise ValueError("Invalid counts/prior/alpha")
    denominator = float(counts.sum()) + alpha
    if denominator <= 0:
        raise ValueError("Posterior denominator must be positive")
    probability = (counts.astype(np.float64) + alpha * prior) / denominator
    if np.any(probability < 0.0) or not np.isclose(probability.sum(), 1.0, atol=1e-10, rtol=0.0):
        raise AssertionError("Posterior probability normalization failure")
    return probability


def score_probability(probability: np.ndarray, actual_index: int) -> dict[str, float | int]:
    if probability.ndim != 1 or actual_index < 0 or actual_index >= len(probability):
        raise ValueError("Invalid probability vector or actual index")
    if np.any(probability < 0.0) or not np.isclose(probability.sum(), 1.0, atol=1e-10, rtol=0.0):
        raise AssertionError("Scoring received non-normalized probabilities")
    actual_probability = float(probability[actual_index])
    brier = float(math.fsum(float(value) * float(value) for value in probability) - 2.0 * actual_probability + 1.0)
    order = np.lexsort((np.arange(len(probability)), -probability))
    rank = int(np.flatnonzero(order == actual_index)[0]) + 1
    return {
        "brier": brier,
        "logloss": -math.log(max(actual_probability, 1e-15)),
        "rank": rank,
        "top1": int(rank <= 1),
        "top5": int(rank <= 5),
        "top10": int(rank <= 10),
        "top20": int(rank <= 20),
        "actual_probability": actual_probability,
        "pick": int(order[0]),
    }


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, p_value) in enumerate(ordered):
        value = min(1.0, p_value * (count - rank))
        running_max = max(running_max, value)
        adjusted[name] = running_max
    return adjusted


def circular_block_means(values: np.ndarray, replicates: int, block_length: int, seed: int) -> np.ndarray:
    if values.ndim != 1 or len(values) < 1 or replicates < 1 or block_length < 1:
        raise ValueError("Invalid bootstrap inputs")
    n = len(values)
    rng = np.random.default_rng(seed)
    result = np.empty(replicates, dtype=np.float64)
    offsets = np.arange(block_length, dtype=np.int64)
    for replicate in range(replicates):
        sampled: list[np.ndarray] = []
        total = 0
        while total < n:
            start = int(rng.integers(0, n))
            take = min(block_length, n - total)
            sampled.append(values[(start + offsets[:take]) % n])
            total += take
        result[replicate] = math.fsum(float(value) for value in np.concatenate(sampled)) / n
    return result


def block_bootstrap_inference(
    differences: np.ndarray,
    replicates: int = BOOTSTRAP_REPLICATES,
    block_length: int = BLOCK_LENGTH,
    seed: int = SEED_BASE,
) -> dict[str, float | int]:
    if differences.ndim != 1 or len(differences) < 2:
        raise ValueError("Blind OOS needs at least two paired observations")
    observed_mean = math.fsum(float(value) for value in differences) / len(differences)
    ci_draws = circular_block_means(differences, replicates, block_length, seed)
    lower, upper = np.quantile(ci_draws, (0.025, 0.975), method="linear")
    centered = differences - observed_mean
    null_draws = circular_block_means(centered, replicates, block_length, seed + 1)
    p_value = (int(np.count_nonzero(null_draws >= observed_mean)) + 1) / (replicates + 1)
    return {
        "n": int(len(differences)),
        "mean_brier_improvement_vs_global": observed_mean,
        "ci95_lower": float(lower),
        "ci95_upper": float(upper),
        "raw_one_sided_centered_block_p": float(p_value),
        "bootstrap_replicates": int(replicates),
        "block_length": int(block_length),
        "seed": int(seed),
    }


def rounded(value: Any, digits: int = 9) -> Any:
    if isinstance(value, (np.floating, float)):
        return float(round(float(value), digits))
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def canonicalize(value: Any) -> Any:
    """Canonical JSON numeric representation to suppress sub-ulp runner drift."""
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return {key: canonicalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, (np.floating, float)):
        return float(format(float(value), ".12g"))
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def mean_metric(records: list[dict[str, Any]], key: str) -> float:
    if not records:
        raise ValueError(f"Empty metric group: {key}")
    return math.fsum(float(record[key]) for record in records) / len(records)


def run_walkforward(
    dates: list[str],
    draws: np.ndarray,
    warmup: int = WARMUP,
    alpha_grid: tuple[int, ...] = ALPHA_GRID,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES,
    block_length: int = BLOCK_LENGTH,
    seed_base: int = SEED_BASE,
    archive_sha: str = EXPECTED_ARCHIVE_GIT_BLOB_SHA,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if draws.ndim != 2 or draws.shape[1] != 5 or len(dates) != len(draws):
        raise ValueError("Archive shape must be date list plus N×5 draws")
    if warmup < 5 or len(draws) <= warmup + 5:
        raise ValueError("Insufficient rows for warmup and chronological splits")
    if any(alpha <= 0 for alpha in alpha_grid) or tuple(sorted(set(alpha_grid))) != alpha_grid:
        raise ValueError("Alpha grid must be positive, unique, and ascending")
    if any(draws[i].tolist() != sorted(draws[i].tolist()) or len(set(draws[i].tolist())) != 5 for i in range(len(draws))):
        raise ValueError("Input draws must be sorted and distinct")

    cuts, state_masses = exact_p3_quartile_states()
    domains: list[np.ndarray] = []
    priors: list[np.ndarray] = []
    for position in range(1, 6):
        domain, prior = order_statistic_prior(position)
        domains.append(domain)
        priors.append(prior)

    target_count = len(draws) - warmup
    discovery_end = target_count // 2
    validation_end = (target_count * 3) // 4
    split_counts = {
        "discovery": discovery_end,
        "validation": validation_end - discovery_end,
        "blind_oos": target_count - validation_end,
    }
    split_dates = {
        "discovery": [dates[warmup], dates[warmup + discovery_end - 1]],
        "validation": [dates[warmup + discovery_end], dates[warmup + validation_end - 1]],
        "blind_oos": [dates[warmup + validation_end], dates[-1]],
    }

    global_counts = [np.zeros(36, dtype=np.int64) for _ in range(5)]
    state_counts = [[np.zeros(36, dtype=np.int64) for _ in range(4)] for _ in range(5)]
    state_training_n = np.zeros(4, dtype=np.int64)
    training_n = 0

    def add_training_target(j: int) -> None:
        nonlocal training_n
        if j < 2 or j >= len(draws):
            raise AssertionError(f"Invalid training target index {j}")
        state = p3_state(int(draws[j - 1, 2]), cuts)
        training_n += 1
        state_training_n[state] += 1
        for position_index in range(5):
            actual = int(draws[j, position_index])
            actual_index = actual - int(domains[position_index][0])
            if actual_index < 0 or actual_index >= 36:
                raise AssertionError(f"Position support failure P{position_index + 1}")
            global_counts[position_index][actual_index] += 1
            state_counts[position_index][state][actual_index] += 1

    for j in range(2, warmup):
        add_training_target(j)

    grid: list[dict[str, Any]] = []
    state_counts_by_split = {split: [0, 0, 0, 0] for split in SPLIT_NAMES}
    train_n_checks = 0
    cutoff_checks = 0
    probability_normalization_checks = 0
    max_probability_normalization_error = 0.0

    def split_of(target_index: int) -> str:
        offset = target_index - warmup
        if offset < discovery_end:
            return "discovery"
        if offset < validation_end:
            return "validation"
        return "blind_oos"

    for target_index in range(warmup, len(draws)):
        if training_n != target_index - 2:
            raise AssertionError(
                f"Strict-prefix train_n=t-2 failure at target {target_index}: {training_n}"
            )
        if dates[target_index - 1] >= dates[target_index]:
            raise AssertionError(f"Target/cutoff chronology failure at index {target_index}")
        train_n_checks += 1
        cutoff_checks += 1

        split = split_of(target_index)
        target_state = p3_state(int(draws[target_index - 1, 2]), cuts)
        state_counts_by_split[split][target_state] += 1
        state_n = int(state_training_n[target_state])
        if state_n < 0 or state_n > training_n:
            raise AssertionError("Conditional state training count is invalid")

        for position_index in range(5):
            position = position_index + 1
            domain = domains[position_index]
            prior = priors[position_index]
            actual = int(draws[target_index, position_index])
            actual_index = actual - int(domain[0])
            if actual_index < 0 or actual_index >= 36:
                raise AssertionError(f"Target support failure at P{position}")

            for alpha in alpha_grid:
                global_probability = posterior_probability(global_counts[position_index], prior, alpha)
                state_probability = posterior_probability(
                    state_counts[position_index][target_state], prior, alpha
                )
                probability_normalization_checks += 2
                max_probability_normalization_error = max(
                    max_probability_normalization_error,
                    abs(float(global_probability.sum()) - 1.0),
                    abs(float(state_probability.sum()) - 1.0),
                )
                global_score = score_probability(global_probability, actual_index)
                state_score = score_probability(state_probability, actual_index)
                prior_score = score_probability(prior, actual_index)

                grid.append(
                    {
                        "date": dates[target_index],
                        "target_index": target_index,
                        "cutoff_date": dates[target_index - 1],
                        "last_training_target_date": dates[target_index - 1],
                        "split": split,
                        "position": position,
                        "previous_draw_p3": int(draws[target_index - 1, 2]),
                        "median_state": STATE_LABELS[target_state],
                        "state_training_n": state_n,
                        "global_training_n": training_n,
                        "alpha": alpha,
                        "actual": actual,
                        "state_pick": int(domain[int(state_score["pick"])]),
                        "global_pick": int(domain[int(global_score["pick"])]),
                        "prior_pick": int(domain[int(prior_score["pick"])]),
                        "state_rank": int(state_score["rank"]),
                        "global_rank": int(global_score["rank"]),
                        "prior_rank": int(prior_score["rank"]),
                        "state_top1": int(state_score["top1"]),
                        "global_top1": int(global_score["top1"]),
                        "prior_top1": int(prior_score["top1"]),
                        "state_top5": int(state_score["top5"]),
                        "global_top5": int(global_score["top5"]),
                        "prior_top5": int(prior_score["top5"]),
                        "state_top10": int(state_score["top10"]),
                        "global_top10": int(global_score["top10"]),
                        "prior_top10": int(prior_score["top10"]),
                        "state_top20": int(state_score["top20"]),
                        "global_top20": int(global_score["top20"]),
                        "prior_top20": int(prior_score["top20"]),
                        "state_probability_actual": float(state_score["actual_probability"]),
                        "global_probability_actual": float(global_score["actual_probability"]),
                        "prior_probability_actual": float(prior_score["actual_probability"]),
                        "state_brier": float(state_score["brier"]),
                        "global_brier": float(global_score["brier"]),
                        "prior_brier": float(prior_score["brier"]),
                        "brier_improvement_vs_global": float(global_score["brier"] - state_score["brier"]),
                        "brier_improvement_vs_prior": float(prior_score["brier"] - state_score["brier"]),
                        "state_logloss": float(state_score["logloss"]),
                        "global_logloss": float(global_score["logloss"]),
                        "prior_logloss": float(prior_score["logloss"]),
                        "logloss_improvement_vs_global": float(global_score["logloss"] - state_score["logloss"]),
                        "logloss_improvement_vs_prior": float(prior_score["logloss"] - state_score["logloss"]),
                        "top1_delta_vs_global": float(state_score["top1"] - global_score["top1"]),
                        "top5_delta_vs_global": float(state_score["top5"] - global_score["top5"]),
                        "mean_rank_improvement_vs_global": float(global_score["rank"] - state_score["rank"]),
                    }
                )
        # Update only after scoring this target; the current outcome cannot enter its forecast.
        add_training_target(target_index)

    expected_grid_rows = target_count * 5 * len(alpha_grid)
    if len(grid) != expected_grid_rows:
        raise AssertionError(f"Grid row count mismatch: {len(grid)} vs {expected_grid_rows}")
    grid_keys = [(r["date"], r["position"], r["alpha"]) for r in grid]
    if len(set(grid_keys)) != len(grid_keys):
        raise AssertionError("Duplicate target-position-alpha grid keys")
    expected_validation_rows = split_counts["validation"] * 5 * len(alpha_grid)
    actual_validation_rows = sum(1 for r in grid if r["split"] == "validation")
    if actual_validation_rows != expected_validation_rows:
        raise AssertionError("Validation grid cardinality mismatch")

    validation_selection: list[dict[str, Any]] = []
    selected_alpha: dict[int, int] = {}
    for position in range(1, 6):
        candidate_metrics: list[dict[str, Any]] = []
        for alpha in alpha_grid:
            records = [
                r for r in grid
                if r["position"] == position and r["split"] == "validation" and r["alpha"] == alpha
            ]
            candidate_metrics.append(
                {
                    "alpha": alpha,
                    "n": len(records),
                    "mean_brier_improvement_vs_global": mean_metric(records, "brier_improvement_vs_global"),
                    "mean_brier_improvement_vs_prior": mean_metric(records, "brier_improvement_vs_prior"),
                    "mean_logloss_improvement_vs_global": mean_metric(records, "logloss_improvement_vs_global"),
                    "top1_delta_vs_global": mean_metric(records, "top1_delta_vs_global"),
                    "top5_delta_vs_global": mean_metric(records, "top5_delta_vs_global"),
                    "mean_rank_improvement_vs_global": mean_metric(records, "mean_rank_improvement_vs_global"),
                }
            )
        best = candidate_metrics[0]
        for candidate in candidate_metrics[1:]:
            delta = candidate["mean_brier_improvement_vs_global"] - best["mean_brier_improvement_vs_global"]
            if delta > 1e-15 or (abs(delta) <= 1e-15 and candidate["alpha"] < best["alpha"]):
                best = candidate
        selected_alpha[position] = int(best["alpha"])
        validation_selection.append(
            {
                "position": position,
                "selected_alpha": int(best["alpha"]),
                "selection_metric": "validation maximum mean Brier improvement vs global shrinkage with same alpha; ties choose smaller alpha",
                "selected_validation_brier_improvement_vs_global": float(best["mean_brier_improvement_vs_global"]),
                "candidates": candidate_metrics,
            }
        )

    selected_grid = [
        record for record in grid if record["alpha"] == selected_alpha[record["position"]]
    ]
    if len(selected_grid) != target_count * 5:
        raise AssertionError("Selected target ledger row count mismatch")
    selected_keys = [(r["date"], r["position"]) for r in selected_grid]
    if len(set(selected_keys)) != len(selected_keys):
        raise AssertionError("Duplicate selected target-position keys")

    split_metrics: list[dict[str, Any]] = []
    for position in range(1, 6):
        for split in SPLIT_NAMES:
            records = [
                r for r in selected_grid if r["position"] == position and r["split"] == split
            ]
            split_metrics.append(
                {
                    "position": position,
                    "selected_alpha": selected_alpha[position],
                    "split": split,
                    "n": len(records),
                    "first_target": records[0]["date"],
                    "last_target": records[-1]["date"],
                    "mean_state_training_n": mean_metric(records, "state_training_n"),
                    "min_state_training_n": min(r["state_training_n"] for r in records),
                    "max_state_training_n": max(r["state_training_n"] for r in records),
                    "brier_improvement_vs_global": mean_metric(records, "brier_improvement_vs_global"),
                    "brier_improvement_vs_prior": mean_metric(records, "brier_improvement_vs_prior"),
                    "logloss_improvement_vs_global": mean_metric(records, "logloss_improvement_vs_global"),
                    "logloss_improvement_vs_prior": mean_metric(records, "logloss_improvement_vs_prior"),
                    "state_top1_rate": mean_metric(records, "state_top1"),
                    "global_top1_rate": mean_metric(records, "global_top1"),
                    "prior_top1_rate": mean_metric(records, "prior_top1"),
                    "top1_delta_vs_global": mean_metric(records, "top1_delta_vs_global"),
                    "state_top5_rate": mean_metric(records, "state_top5"),
                    "global_top5_rate": mean_metric(records, "global_top5"),
                    "prior_top5_rate": mean_metric(records, "prior_top5"),
                    "top5_delta_vs_global": mean_metric(records, "top5_delta_vs_global"),
                    "mean_rank_improvement_vs_global": mean_metric(records, "mean_rank_improvement_vs_global"),
                }
            )

    primary_inference: list[dict[str, Any]] = []
    raw_p_values: dict[str, float] = {}
    for position in range(1, 6):
        records = [
            r for r in selected_grid if r["position"] == position and r["split"] == "blind_oos"
        ]
        differences = np.asarray(
            [r["brier_improvement_vs_global"] for r in records], dtype=np.float64
        )
        inference = block_bootstrap_inference(
            differences,
            replicates=bootstrap_replicates,
            block_length=block_length,
            seed=seed_base + position * 1009,
        )
        raw_p_values[f"P{position}"] = float(inference["raw_one_sided_centered_block_p"])
        primary_inference.append(
            {
                "position": position,
                "selected_alpha": selected_alpha[position],
                **inference,
            }
        )
    adjusted_p_values = holm_adjust(raw_p_values)
    for item in primary_inference:
        item["holm_adjusted_p_5_positions"] = adjusted_p_values[f"P{item['position']}"]
        item["primary_endpoint"] = "blind-OOS paired Brier improvement vs global shrinkage with same selected alpha"
        item["survives_holm_0_05"] = bool(item["holm_adjusted_p_5_positions"] < 0.05)

    state_distribution: list[dict[str, Any]] = []
    for split in SPLIT_NAMES:
        observed = state_counts_by_split[split]
        split_n = split_counts[split]
        state_distribution.append(
            {
                "split": split,
                "n": split_n,
                "observed_state_counts": observed,
                "expected_counts_from_exact_p3_prior": [float(split_n * mass) for mass in state_masses],
                "state_labels": list(STATE_LABELS),
                "interpretation": "descriptive marginal state-frequency control; not a dependence or predictive test",
            }
        )

    report: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": "SONAR_PSR07_PREVIOUS_DRAW_P3_MEDIAN_STATE",
        "status": "EXPLORATORY_NO_PROMOTION",
        "hypothesis": {
            "feature": "P3 (middle ordered statistic) of the immediately preceding draw",
            "target": "next draw ordered-position marginal P1..P5",
            "quantitative_claim": "state-conditioned position marginals improve blind-OOS Brier score over same-alpha global position shrinkage",
            "null_expectation": "under independent uniform 5-subset draws, preceding P3 state has no incremental predictive information",
        },
        "archive": {
            "git_blob_sha": archive_sha,
            "draws": int(len(draws)),
            "first_date": dates[0],
            "last_date": dates[-1],
        },
        "protocol": {
            "warmup_target_index": int(warmup),
            "scored_targets": int(target_count),
            "alpha_grid": list(alpha_grid),
            "selection": "validation-only maximum mean Brier improvement vs global shrinkage with same alpha; ties choose smaller alpha",
            "split_rule": "chronological 50% discovery / 25% validation / 25% final blind OOS",
            "bootstrap": {
                "method": "circular moving-block bootstrap; centered-null one-sided p and percentile 95% CI",
                "replicates": int(bootstrap_replicates),
                "block_length": int(block_length),
                "seed_base": int(seed_base),
                "holm_family": "five predeclared position-level primary Brier endpoints",
            },
        },
        "theoretical_p3_state": {
            "exact_quartile_cutpoints": list(cuts),
            "state_labels": list(STATE_LABELS),
            "exact_prior_state_masses": list(state_masses),
        },
        "walk_forward": {
            "split_counts": split_counts,
            "split_dates": split_dates,
            "state_distribution_by_split": state_distribution,
        },
        "validation_selection": validation_selection,
        "split_metrics": split_metrics,
        "blind_oos_primary_inference": primary_inference,
        "integrity": {
            "strict_prefix_train_n_t_minus_2_checks": int(train_n_checks),
            "target_cutoff_before_target_date_checks": int(cutoff_checks),
            "expected_grid_rows": int(expected_grid_rows),
            "actual_grid_rows": int(len(grid)),
            "expected_selected_ledger_rows": int(target_count * 5),
            "actual_selected_ledger_rows": int(len(selected_grid)),
            "expected_validation_grid_rows": int(expected_validation_rows),
            "actual_validation_grid_rows": int(actual_validation_rows),
            "duplicate_grid_keys": 0,
            "duplicate_selected_target_position_keys": 0,
            "exact_order_statistic_prior_normalization_checks": 5,
            "candidate_and_global_probability_normalization_checks": int(probability_normalization_checks),
            "max_probability_normalization_error": float(max_probability_normalization_error),
            "selected_alpha_by_position": {f"P{p}": selected_alpha[p] for p in range(1, 6)},
            "last_training_target_index_rule": "target_index - 1; outcome date equals cutoff date and is strictly before target date",
            "train_n_rule": "target_index - 2, training target indices 2..target_index-1 inclusive",
        },
        "reproducibility": {
            "deterministic": True,
            "numpy_rng": "PCG64 via numpy.random.default_rng",
            "fixed_seed": int(seed_base),
            "no_generated_timestamp": True,
            "ledger_format": "CSV with stable field order and LF line endings",
        },
        "limitations": [
            "The historical blind partition overlaps previous SONAR research; it is not independent lab-wide confirmation.",
            "The five ordered-position marginals are dependent; this experiment does not produce or validate a joint ticket.",
            "A prior-draw association, if observed, is not causal and can arise from historical selection or sampling noise.",
            "Top-1, Top-5, log-loss and rank diagnostics are secondary/descriptive; only five position-level Brier endpoints form the Holm primary family.",
            "This is a discrete statistical state experiment, not a physical Navier–Stokes field or a claim that fluid dynamics governs VinciCasa.",
            "No engine promotion, merge, or prospective gate completion is authorized.",
        ],
    }

    survivors = [
        item["position"] for item in primary_inference
        if item["survives_holm_0_05"] and item["mean_brier_improvement_vs_global"] > 0
    ]
    if survivors:
        report["next_action"] = (
            "Keep the Holm-surviving position(s) fixed and register an append-only prospective shadow protocol; "
            "do not tune on this reused historical blind slice. Require at least 200 paired prospective targets "
            "and human review before promotion consideration."
        )
    else:
        report["next_action"] = (
            "No primary position survives Holm at 0.05. Preserve PSR-07 as a valid null/exploratory result; "
            "do not tune the median-state cutpoints or alpha grid on blind OOS. The next research iteration "
            "should move to a separately registered joint-dependence diagnostic or independent prospective shadow evidence."
        )
    return report, selected_grid


def render_markdown(report: dict[str, Any]) -> str:
    archive = report["archive"]
    state = report["theoretical_p3_state"]
    protocol = report["protocol"]
    lines: list[str] = [
        "# SONAR PSR-07 — Previous-draw median-state position marginals",
        "",
        "**Status:** EXPLORATORY / NO PROMOTION",
        f"**Archive:** {archive['draws']} draws, {archive['first_date']}–{archive['last_date']}; Git blob SHA {archive['git_blob_sha']}",
        f"**Targets:** {protocol['scored_targets']}; warmup {protocol['warmup_target_index']}; discovery {report['walk_forward']['split_counts']['discovery']}, validation {report['walk_forward']['split_counts']['validation']}, blind OOS {report['walk_forward']['split_counts']['blind_oos']}",
        "",
        "## Hypothesis and exact state",
        "",
        "The preceding draw's P3 (middle order statistic) is a fixed, prior-only conditioning state for the next ordered-position marginal. Under independent uniform 5-subset draws it should not add predictive information.",
        "",
        r"\(\pi_3(m)=\binom{m-1}{2}\binom{40-m}{2}/\binom{40}{5}\), \(m=3,\ldots,38\).",
        f"Theoretical quartile cutpoints: **{state['exact_quartile_cutpoints']}**; exact state masses: **{[round(x*100, 4) for x in state['exact_prior_state_masses']]}%**.",
        "",
        r"\(\pi_i(n)=\binom{n-1}{i-1}\binom{40-n}{5-i}/\binom{40}{5}\), \(n=i,\ldots,35+i\).",
        r"\(q_{i,t}(n|s)=[c_{i,t,s}(n)+\alpha\pi_i(n)]/[N_{t,s}+\alpha]\); global comparator uses the same \(\alpha\) and training rows.",
        f"Alpha grid: {protocol['alpha_grid']}; chosen per position on validation only by maximum Brier improvement vs same-alpha global shrinkage. Tie: smaller alpha.",
        "",
        "## Chronological walk-forward",
        "",
        "| Split | Targets | Date range |",
        "|---|---:|---|",
    ]
    for split in SPLIT_NAMES:
        count = report["walk_forward"]["split_counts"][split]
        dates = report["walk_forward"]["split_dates"][split]
        lines.append(f"| {split} | {count} | {dates[0]} – {dates[1]} |")
    lines += [
        "",
        "Training target indices are 2..t−1; every target asserts train_n=t−2 and cutoff date < target date. The target feature is P3 from draw t−1.",
        "",
        "## Validation alpha selection",
        "",
        "| P | Selected alpha | Validation ΔBrier vs global | α=100 | α=300 | α=1000 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in report["validation_selection"]:
        candidates = {c["alpha"]: c["mean_brier_improvement_vs_global"] for c in item["candidates"]}
        lines.append(
            f"| P{item['position']} | {item['selected_alpha']} | "
            f"{item['selected_validation_brier_improvement_vs_global']:.9f} | "
            f"{candidates[100]:.9f} | {candidates[300]:.9f} | {candidates[1000]:.9f} |"
        )
    lines += [
        "",
        "## Selected model by split",
        "",
        "| P | α | Split | N | ΔBrier vs global | ΔBrier vs prior | ΔLog-loss vs global | Top-1 Δ pp | Top-5 Δ pp | Mean rank improvement |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["split_metrics"]:
        lines.append(
            f"| P{item['position']} | {item['selected_alpha']} | {item['split']} | {item['n']} | "
            f"{item['brier_improvement_vs_global']:.9f} | {item['brier_improvement_vs_prior']:.9f} | "
            f"{item['logloss_improvement_vs_global']:.9f} | {item['top1_delta_vs_global']*100:.4f} | "
            f"{item['top5_delta_vs_global']*100:.4f} | {item['mean_rank_improvement_vs_global']:.6f} |"
        )
    lines += [
        "",
        "## Blind OOS primary inference",
        "",
        "| P | α | ΔBrier vs global | 95% block CI | Raw centered one-sided p | Holm p (5) | Survives 0.05 |",
        "|---|---:|---:|---|---:|---:|---|",
    ]
    for item in report["blind_oos_primary_inference"]:
        lines.append(
            f"| P{item['position']} | {item['selected_alpha']} | {item['mean_brier_improvement_vs_global']:.9f} | "
            f"[{item['ci95_lower']:.9f}, {item['ci95_upper']:.9f}] | "
            f"{item['raw_one_sided_centered_block_p']:.6f} | "
            f"{item['holm_adjusted_p_5_positions']:.6f} | "
            f"{'YES' if item['survives_holm_0_05'] else 'NO'} |"
        )
    lines += [
        "",
        "Primary family: five predeclared position-level Brier improvements. Bootstrap is circular moving-block length 7 with "
        f"{protocol['bootstrap']['replicates']:,} replicates. Secondary metrics are descriptive and do not alter this family.",
        "",
        "## Previous-P3 state frequency control",
        "",
        "| Split | N | Observed counts Q1–Q4 | Expected counts from exact P3 prior |",
        "|---|---:|---|---|",
    ]
    for item in report["walk_forward"]["state_distribution_by_split"]:
        expected = [round(x, 2) for x in item["expected_counts_from_exact_p3_prior"]]
        lines.append(f"| {item['split']} | {item['n']} | {item['observed_state_counts']} | {expected} |")
    lines += [
        "",
        "This is a descriptive marginal-frequency control only; it does not test predictive dependence or causal effects.",
        "",
        "## Integrity and reproducibility",
        "",
        f"- Strict-prefix train_n=t−2 checks: {report['integrity']['strict_prefix_train_n_t_minus_2_checks']} / {protocol['scored_targets']}; PASS.",
        f"- Target cutoff before target date checks: {report['integrity']['target_cutoff_before_target_date_checks']} / {protocol['scored_targets']}; PASS.",
        f"- Grid rows: {report['integrity']['actual_grid_rows']} / {report['integrity']['expected_grid_rows']}; selected ledger rows: {report['integrity']['actual_selected_ledger_rows']} / {report['integrity']['expected_selected_ledger_rows']}; PASS.",
        f"- Validation grid rows: {report['integrity']['actual_validation_grid_rows']} / {report['integrity']['expected_validation_grid_rows']}; duplicate keys: 0; PASS.",
        f"- Exact order-statistic prior normalization checks: {report['integrity']['exact_order_statistic_prior_normalization_checks']}; candidate/global probability normalization checks: {report['integrity']['candidate_and_global_probability_normalization_checks']}; max normalization error {report['integrity']['max_probability_normalization_error']:.3e}.",
        f"- Selected target ledger SHA-256: {report['integrity']['selected_ledger_sha256']}.",
        "- Fixed bootstrap seed, alpha grid, chronological splits, archive SHA pin, and stable CSV field order; no generated timestamp.",
        "",
        "## Decision, limits, and next action",
        "",
        report["next_action"],
        "",
    ]
    for limitation in report["limitations"]:
        lines.append(f"- {limitation}")
    lines += [
        "",
        "No engine replacement, promotion, merge, or edits to PR #6/#7/#8/#13.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(
    report: dict[str, Any],
    selected_grid: list[dict[str, Any]],
    out_dir: Path,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "PSR07_results_20261108.json"
    markdown_path = out_dir / "PSR07_results_20261108.md"
    ledger_path = out_dir / "PSR07_target_ledger_20261108.csv"

    selected_ledger: list[dict[str, Any]] = [
        {key: rounded(value) for key, value in record.items()}
        for record in selected_grid
    ]
    fieldnames = list(selected_ledger[0].keys())
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(selected_ledger)

    ledger_bytes = ledger_path.read_bytes()
    report["integrity"]["selected_ledger_rows"] = len(selected_ledger)
    report["integrity"]["selected_ledger_sha256"] = hashlib.sha256(ledger_bytes).hexdigest()
    json_path.write_text(json.dumps(canonicalize(report), indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path, "ledger": ledger_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SONAR PSR-07 prior median-state walk-forward lab.")
    parser.add_argument("--input", type=Path, default=Path("data/storico_daily.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("reports/position_specific_range_residual"))
    parser.add_argument("--expected-archive-sha", default=EXPECTED_ARCHIVE_GIT_BLOB_SHA)
    parser.add_argument("--warmup", type=int, default=WARMUP)
    parser.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES)
    parser.add_argument("--block-length", type=int, default=BLOCK_LENGTH)
    parser.add_argument("--seed-base", type=int, default=SEED_BASE)
    args = parser.parse_args()

    dates, draws, archive_sha = read_archive(args.input, args.expected_archive_sha)
    report, selected_grid = run_walkforward(
        dates,
        draws,
        warmup=args.warmup,
        alpha_grid=ALPHA_GRID,
        bootstrap_replicates=args.bootstrap_replicates,
        block_length=args.block_length,
        seed_base=args.seed_base,
        archive_sha=archive_sha,
    )
    paths = write_outputs(report, selected_grid, args.out_dir)
    print(json.dumps(
        {
            "status": report["status"],
            "archive_git_blob_sha": archive_sha,
            "scored_targets": report["protocol"]["scored_targets"],
            "split_counts": report["walk_forward"]["split_counts"],
            "selected_alpha_by_position": report["integrity"]["selected_alpha_by_position"],
            "primary_inference": report["blind_oos_primary_inference"],
            "outputs": {name: str(path) for name, path in paths.items()},
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
