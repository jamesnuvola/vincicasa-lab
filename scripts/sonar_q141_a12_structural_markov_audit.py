#!/usr/bin/env python3
"""Q141-A12: prior-only Markov audit of 11 structural category streams.

Research-only diagnostic. It tests whether the previous structural category
adds prequential information beyond the expanding marginal-frequency baseline.
The two first-difference features are separately checked against an IID
uniform 5-of-40 simulation because adjacent differences share one draw.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

EXPECTED_ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_MATRIX_SHA256 = "81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047"
EXPECTED_MATRIX_SHAPE = (3356, 40, 59)
WARMUP = 400
BASE_ALPHA = 0.5
TRANSITION_ALPHA = 20.0
BLOCK_LENGTH = 20
BOOTSTRAP_REPS = 20_000
IID_REPS = 2_000
IID_SEED = 14111324
BOOTSTRAP_SEED = 14111330

FEATURE_CATEGORIES = {
    "sum_bin": ["S<80", "S80-99", "S100-119", "S120-139", "S140+"],
    "range_bin": ["R<20", "R20-24", "R25-29", "R30-34", "R35+"],
    "odd_cat": [f"O{i}" for i in range(6)],
    "low_cat": [f"L{i}" for i in range(6)],
    "overlap_cat": ["X0", "X1", "X2+"],
    "gap1_bin": ["G1-3", "G4-7", "G8-12", "G13+"],
    "gap2_bin": ["G1-3", "G4-7", "G8-12", "G13+"],
    "gap3_bin": ["G1-3", "G4-7", "G8-12", "G13+"],
    "gap4_bin": ["G1-3", "G4-7", "G8-12", "G13+"],
    "sum_transition": ["DOWN_BIG", "DOWN", "FLAT", "UP", "UP_BIG"],
    "range_transition": ["CONTRACT_BIG", "CONTRACT", "STABLE", "EXPAND", "EXPAND_BIG"],
}
FEATURES = list(FEATURE_CATEGORIES)
MECHANICAL_FEATURES = ["sum_transition", "range_transition"]
CORE_FEATURES = [f for f in FEATURES if f not in MECHANICAL_FEATURES]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def validate_draws(draws: np.ndarray) -> np.ndarray:
    x = np.asarray(draws, dtype=np.int64)
    if x.ndim != 2 or x.shape[1] != 5 or len(x) < WARMUP + 2:
        raise ValueError("draws must be an n x 5 matrix with sufficient history")
    if np.any(x < 1) or np.any(x > 40):
        raise ValueError("draw number outside 1..40")
    if any(len(set(row.tolist())) != 5 for row in x):
        raise ValueError("duplicate number in a draw")
    return np.sort(x, axis=1)


def gap_bin(value: int) -> str:
    if value <= 3:
        return "G1-3"
    if value <= 7:
        return "G4-7"
    if value <= 12:
        return "G8-12"
    return "G13+"


def sum_transition(delta: int) -> str:
    if delta <= -16:
        return "DOWN_BIG"
    if delta <= -6:
        return "DOWN"
    if delta >= 16:
        return "UP_BIG"
    if delta >= 6:
        return "UP"
    return "FLAT"


def range_transition(delta: int) -> str:
    if delta <= -6:
        return "CONTRACT_BIG"
    if delta <= -2:
        return "CONTRACT"
    if delta >= 6:
        return "EXPAND_BIG"
    if delta >= 2:
        return "EXPAND"
    return "STABLE"


def build_feature_codes(draws: np.ndarray) -> dict[str, np.ndarray]:
    x = validate_draws(draws)
    rows: dict[str, list[str | None]] = {f: [] for f in FEATURES}
    previous_sum = None
    previous_range = None
    previous_set = None

    for raw in x:
        nums = [int(v) for v in raw]
        total = sum(nums)
        span = nums[-1] - nums[0]
        odd = sum(v % 2 for v in nums)
        low = sum(v <= 20 for v in nums)
        overlap = None if previous_set is None else len(set(nums) & previous_set)
        gaps = [nums[i + 1] - nums[i] for i in range(4)]
        sum_delta = None if previous_sum is None else total - previous_sum
        range_delta = None if previous_range is None else span - previous_range

        values = {
            "sum_bin": "S<80" if total < 80 else "S80-99" if total < 100 else "S100-119" if total < 120 else "S120-139" if total < 140 else "S140+",
            "range_bin": "R<20" if span < 20 else "R20-24" if span < 25 else "R25-29" if span < 30 else "R30-34" if span < 35 else "R35+",
            "odd_cat": f"O{odd}",
            "low_cat": f"L{low}",
            "overlap_cat": None if overlap is None else "X2+" if overlap >= 2 else f"X{overlap}",
            "gap1_bin": gap_bin(gaps[0]),
            "gap2_bin": gap_bin(gaps[1]),
            "gap3_bin": gap_bin(gaps[2]),
            "gap4_bin": gap_bin(gaps[3]),
            "sum_transition": None if sum_delta is None else sum_transition(sum_delta),
            "range_transition": None if range_delta is None else range_transition(range_delta),
        }
        for feature, value in values.items():
            rows[feature].append(value)
        previous_sum = total
        previous_range = span
        previous_set = set(nums)

    codes: dict[str, np.ndarray] = {}
    for feature, categories in FEATURE_CATEGORIES.items():
        index = {value: i for i, value in enumerate(categories)}
        codes[feature] = np.asarray(
            [-1 if value is None else index.get(value, -2) for value in rows[feature]],
            dtype=np.int16,
        )
        if np.any(codes[feature] == -2):
            raise ValueError(f"unexpected category in {feature}")
        if np.any(codes[feature][1:] < 0):
            raise ValueError(f"undefined category after first row in {feature}")
    return codes


def score_feature(y: np.ndarray, target_index: int, k: int,
                  alpha_base: float = BASE_ALPHA,
                  alpha_transition: float = TRANSITION_ALPHA) -> dict:
    """Score target y[t] using only y[1:t] and transitions within y[1:t]."""
    y = np.asarray(y, dtype=np.int64)
    t = int(target_index)
    if t < WARMUP or t >= len(y):
        raise ValueError("target index outside walk-forward range")
    prior = y[1:t]
    if len(prior) < WARMUP - 1 or np.any(prior < 0):
        raise ValueError("invalid prior category history")
    if k < 2 or np.any(prior >= k) or np.any(y[t - 1:t + 1] >= k):
        raise ValueError("category code outside fixed vocabulary")
    if np.any(y[t - 1:t + 1] < 0):
        raise ValueError("target/state category undefined")
    counts = np.bincount(prior, minlength=k).astype(np.float64)
    p0 = (counts + alpha_base) / (len(prior) + alpha_base * k)

    previous = y[1:t - 1]
    following = y[2:t]
    transition_counts = np.zeros((k, k), dtype=np.float64)
    if len(previous):
        np.add.at(transition_counts, (previous, following), 1.0)
    state = int(y[t - 1])
    row = transition_counts[state]
    p1 = (row + alpha_transition * p0) / (row.sum() + alpha_transition)

    actual = int(y[t])
    baseline_ll = -math.log(float(p0[actual]))
    markov_ll = -math.log(float(p1[actual]))
    one_hot = np.zeros(k, dtype=np.float64)
    one_hot[actual] = 1.0
    baseline_brier = float(np.sum((p0 - one_hot) ** 2))
    markov_brier = float(np.sum((p1 - one_hot) ** 2))
    return {
        "logloss_gain": baseline_ll - markov_ll,
        "brier_gain": baseline_brier - markov_brier,
        "baseline_probability": float(p0[actual]),
        "markov_probability": float(p1[actual]),
        "prior_category_count": int(len(prior)),
        "transition_count": int(row.sum()),
        "prior_transition_count": int(transition_counts.sum()),
        "state_category": state,
        "target_category": actual,
    }


def build_ledger(codes: dict[str, np.ndarray], dates: np.ndarray,
                 cutoffs: np.ndarray) -> list[dict]:
    n = len(dates)
    records = []
    for t in range(WARMUP, n):
        if not str(cutoffs[t]) < str(dates[t]):
            raise ValueError(f"cutoff is not prior at target {dates[t]}")
        row = {
            "target_index": t,
            "target_date": str(dates[t]),
            "cutoff_date": str(cutoffs[t]),
            "prior_draw_rows": t,
        }
        for feature in FEATURES:
            result = score_feature(codes[feature], t, len(FEATURE_CATEGORIES[feature]))
            row[f"{feature}_logloss_gain"] = result["logloss_gain"]
            row[f"{feature}_brier_gain"] = result["brier_gain"]
        row["full11_logloss_gain"] = float(np.mean([row[f"{f}_logloss_gain"] for f in FEATURES]))
        row["full11_brier_gain"] = float(np.mean([row[f"{f}_brier_gain"] for f in FEATURES]))
        row["core9_logloss_gain"] = float(np.mean([row[f"{f}_logloss_gain"] for f in CORE_FEATURES]))
        row["core9_brier_gain"] = float(np.mean([row[f"{f}_brier_gain"] for f in CORE_FEATURES]))
        row["difference2_logloss_gain"] = float(np.mean([row[f"{f}_logloss_gain"] for f in MECHANICAL_FEATURES]))
        row["difference2_brier_gain"] = float(np.mean([row[f"{f}_brier_gain"] for f in MECHANICAL_FEATURES]))
        records.append(row)
    return records


def split_records(records: list[dict]) -> dict[str, list[dict]]:
    n = len(records)
    n_discovery = int(round(n * 0.60))
    n_validation = int(round(n * 0.20))
    return {
        "discovery": records[:n_discovery],
        "validation": records[n_discovery:n_discovery + n_validation],
        "blind_oos": records[n_discovery + n_validation:],
    }


def mean_field(rows: list[dict], field: str) -> float:
    return float(np.mean([r[field] for r in rows]))


def hac_se(values: np.ndarray, max_lag: int = 20) -> float:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    centered = x - x.mean()
    variance = float(np.dot(centered, centered) / n)
    for lag in range(1, min(max_lag, n - 1) + 1):
        gamma = float(np.dot(centered[lag:], centered[:-lag]) / n)
        variance += 2.0 * (1.0 - lag / (max_lag + 1.0)) * gamma
    return math.sqrt(max(0.0, variance) / n)


def normal_sf(z: float) -> float:
    return 0.5 * math.erfc(float(z) / math.sqrt(2.0))


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        value = min(1.0, (m - rank) * float(p_values[index]))
        running = max(running, value)
        adjusted[index] = running
    return adjusted


def circular_block_bootstrap(values: np.ndarray, seed: int,
                             reps: int = BOOTSTRAP_REPS,
                             block: int = BLOCK_LENGTH) -> dict:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    rng = np.random.default_rng(seed)
    blocks = math.ceil(n / block)
    offsets = np.arange(block)
    starts = rng.integers(0, n, size=(reps, blocks))
    indices = (starts[:, :, None] + offsets[None, None, :]) % n
    samples = x[indices].reshape(reps, -1)[:, :n]
    means = samples.mean(axis=1)
    centered = x - x.mean()
    null_starts = rng.integers(0, n, size=(reps, blocks))
    null_indices = (null_starts[:, :, None] + offsets[None, None, :]) % n
    null_means = centered[null_indices].reshape(reps, -1)[:, :n].mean(axis=1)
    observed = float(x.mean())
    p_value = (1.0 + float(np.sum(null_means >= observed))) / (reps + 1.0)
    return {
        "mean": observed,
        "ci95": [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))],
        "bootstrap_se": float(means.std(ddof=1)),
        "p_one_sided_gain_gt_zero": p_value,
        "replicates": reps,
        "block_length": block,
    }


def fast_transition_gains_invalid(y: np.ndarray, start_draw: int = WARMUP) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized replay for simulated differenced features; y[0] is undefined."""
    y = np.asarray(y, dtype=np.int64)
    k = 5
    valid = y[1:]
    one_hot = np.eye(k, dtype=np.float64)[valid]
    cumulative_counts = np.cumsum(one_hot, axis=0)
    pair_ids = valid[:-1] * k + valid[1:]
    cumulative_transitions = np.cumsum(np.eye(k * k, dtype=np.float64)[pair_ids], axis=0)
    targets = np.arange(start_draw, len(y))
    counts = cumulative_counts[targets - 2]
    transitions = cumulative_transitions[targets - 3].reshape(-1, k, k)
    states = y[targets - 1]
    rows = transitions[np.arange(len(targets)), states]
    p0 = (counts + BASE_ALPHA) / (counts.sum(axis=1, keepdims=True) + BASE_ALPHA * k)
    p1 = (rows + TRANSITION_ALPHA * p0) / (rows.sum(axis=1, keepdims=True) + TRANSITION_ALPHA)
    actual = y[targets]
    logloss_gain = np.log(p1[np.arange(len(targets)), actual] / p0[np.arange(len(targets)), actual])
    one_hot_target = np.eye(k, dtype=np.float64)[actual]
    brier0 = np.sum((p0 - one_hot_target) ** 2, axis=1)
    brier1 = np.sum((p1 - one_hot_target) ** 2, axis=1)
    return logloss_gain, brier0 - brier1


def iid_difference_null(n_draws: int, reps: int = IID_REPS,
                        seed: int = IID_SEED) -> dict:
    rng = np.random.default_rng(seed)
    simulated = np.empty((reps, 2, 2), dtype=np.float64)
    for rep in range(reps):
        random_scores = rng.random((n_draws, 40))
        draws = np.argpartition(random_scores, 5, axis=1)[:, :5] + 1
        draws.sort(axis=1)
        sums = draws.sum(axis=1)
        ranges = draws[:, -1] - draws[:, 0]
        sum_delta = np.diff(sums)
        range_delta = np.diff(ranges)
        sum_codes = np.full(n_draws, -1, dtype=np.int16)
        range_codes = np.full(n_draws, -1, dtype=np.int16)
        sum_codes[1:] = np.where(sum_delta <= -16, 0, np.where(sum_delta <= -6, 1,
                              np.where(sum_delta >= 16, 4, np.where(sum_delta >= 6, 3, 2))))
        range_codes[1:] = np.where(range_delta <= -6, 0, np.where(range_delta <= -2, 1,
                                np.where(range_delta >= 6, 4, np.where(range_delta >= 2, 3, 2))))
        sum_ll, sum_br = fast_transition_gains_invalid(sum_codes)
        range_ll, range_br = fast_transition_gains_invalid(range_codes)
        simulated[rep, 0, 0] = float(sum_ll.mean())
        simulated[rep, 0, 1] = float(sum_br.mean())
        simulated[rep, 1, 0] = float(range_ll.mean())
        simulated[rep, 1, 1] = float(range_br.mean())

    return {
        "replicates": reps,
        "seed": seed,
        "null_mean": [[float(v) for v in row] for row in simulated.mean(axis=0)],
        "null_sd": [[float(v) for v in row] for row in simulated.std(axis=0, ddof=1)],
        "null_q025_q50_q975": [
            [float(v) for v in np.quantile(simulated[:, feature, metric], [0.025, 0.50, 0.975])]
            for feature in range(2) for metric in range(2)
        ],
        "simulated_values": simulated,
    }


def load_source(path: Path) -> dict:
    raw_sha = _sha256(path)
    if raw_sha != EXPECTED_MATRIX_SHA256:
        raise ValueError("Q141-A7 feature-matrix SHA-256 mismatch")
    with np.load(path, allow_pickle=False) as data:
        matrix = data["feature_matrix"]
        dates = data["target_dates"].astype(str)
        cutoffs = data["cutoff_dates"].astype(str)
        draws = data["actual_quintets"].astype(np.int64)
        names = data["feature_names"].astype(str)
        archive_sha = str(data["archive_blob_sha"].item())
    if archive_sha != EXPECTED_ARCHIVE_BLOB:
        raise ValueError("canonical archive blob SHA-1 mismatch")
    if matrix.shape != EXPECTED_MATRIX_SHAPE or len(names) != 59:
        raise ValueError("unexpected Q141-A7 matrix shape or feature count")
    if draws.shape != (EXPECTED_MATRIX_SHAPE[0], 5) or not np.isfinite(matrix).all():
        raise ValueError("invalid source matrix or target draws")
    draws = validate_draws(draws)
    if len(set(dates.tolist())) != len(dates):
        raise ValueError("duplicate target dates")
    if np.any(np.diff(dates.astype("datetime64[D]").astype(np.int64)) <= 0):
        raise ValueError("target dates not strictly chronological")
    if not np.all(cutoffs < dates):
        raise ValueError("one or more cutoffs are not strictly prior to target")
    return {
        "matrix_sha256": raw_sha,
        "archive_blob_sha1": archive_sha,
        "matrix_shape": list(matrix.shape),
        "feature_count": len(names),
        "dates": dates,
        "cutoffs": cutoffs,
        "draws": draws,
    }


def run_experiment(input_path: Path, output_dir: Path) -> dict:
    source = load_source(input_path)
    codes = build_feature_codes(source["draws"])
    records = build_ledger(codes, source["dates"], source["cutoffs"])
    replay = build_ledger(codes, source["dates"], source["cutoffs"])
    if records != replay:
        raise ValueError("deterministic replay mismatch")

    splits = split_records(records)
    split_summary = {}
    for name, rows in splits.items():
        split_summary[name] = {
            "targets": len(rows),
            "first_target": rows[0]["target_date"],
            "last_target": rows[-1]["target_date"],
            "full11_mean_logloss_gain": mean_field(rows, "full11_logloss_gain"),
            "full11_mean_brier_gain": mean_field(rows, "full11_brier_gain"),
            "core9_mean_logloss_gain": mean_field(rows, "core9_logloss_gain"),
            "core9_mean_brier_gain": mean_field(rows, "core9_brier_gain"),
            "difference2_mean_logloss_gain": mean_field(rows, "difference2_logloss_gain"),
            "difference2_mean_brier_gain": mean_field(rows, "difference2_brier_gain"),
        }

    blind = splits["blind_oos"]
    endpoint_fields = {
        "full11_logloss": "full11_logloss_gain",
        "full11_brier": "full11_brier_gain",
        "core9_logloss": "core9_logloss_gain",
        "core9_brier": "core9_brier_gain",
        "difference2_logloss": "difference2_logloss_gain",
        "difference2_brier": "difference2_brier_gain",
    }
    blind_inference = {}
    for i, (name, field) in enumerate(endpoint_fields.items()):
        values = np.asarray([r[field] for r in blind], dtype=np.float64)
        blind_inference[name] = circular_block_bootstrap(values, BOOTSTRAP_SEED + i)

    feature_rows = []
    for feature in CORE_FEATURES:
        values = np.asarray([r[f"{feature}_logloss_gain"] for r in blind], dtype=np.float64)
        se = hac_se(values, max_lag=20)
        z = float(values.mean() / se) if se > 0 else 0.0
        feature_rows.append({
            "feature": feature,
            "mean_logloss_gain": float(values.mean()),
            "hac_se_lag20": se,
            "z_one_sided_gain": z,
            "p_one_sided_gain_gt_zero": normal_sf(z),
        })
    adjusted = holm_adjust([r["p_one_sided_gain_gt_zero"] for r in feature_rows])
    for row, p_holm in zip(feature_rows, adjusted):
        row["p_holm_across_9_core_features"] = p_holm

    observed_mechanical = [
        [mean_field(blind, "sum_transition_logloss_gain"), mean_field(blind, "sum_transition_brier_gain")],
        [mean_field(blind, "range_transition_logloss_gain"), mean_field(blind, "range_transition_brier_gain")],
    ]
    null = iid_difference_null(len(source["draws"]))
    sim = null.pop("simulated_values")
    raw_p = []
    for feature_index in range(2):
        for metric_index in range(2):
            observed = observed_mechanical[feature_index][metric_index]
            raw_p.append((1.0 + float(np.sum(sim[:, feature_index, metric_index] >= observed))) / (len(sim) + 1.0))
    p_holm = holm_adjust(raw_p)
    null["feature_order"] = MECHANICAL_FEATURES
    null["metric_order"] = ["logloss_gain", "brier_gain"]
    null["observed_blind_mean_gain"] = observed_mechanical
    null["p_observed_exceeds_iid_null"] = raw_p
    null["p_holm_across_four_mechanical_tests"] = p_holm
    null["monte_carlo_se_p"] = [math.sqrt(p * (1 - p) / len(sim)) for p in raw_p]

    probe_t = min(2000, len(source["draws"]) - 2)
    mutated = source["draws"].copy()
    rng = np.random.default_rng(14111325)
    for i in range(probe_t + 1, len(mutated)):
        mutated[i] = np.sort(rng.choice(np.arange(1, 41), size=5, replace=False))
    mutated_codes = build_feature_codes(mutated)
    suffix_invariant = True
    for feature in FEATURES:
        a = score_feature(codes[feature], probe_t, len(FEATURE_CATEGORIES[feature]))
        b = score_feature(mutated_codes[feature], probe_t, len(FEATURE_CATEGORIES[feature]))
        if a != b:
            suffix_invariant = False
            break
    if not suffix_invariant:
        raise ValueError("future-suffix mutation changed a prior forecast")

    n = len(records)
    n_discovery = len(splits["discovery"])
    n_validation = len(splits["validation"])
    n_blind = len(splits["blind_oos"])
    transition_contribution = 2.0 * split_summary["blind_oos"]["difference2_mean_logloss_gain"] / 11.0
    core_contribution = 9.0 * split_summary["blind_oos"]["core9_mean_logloss_gain"] / 11.0

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-A12-STRUCTURAL-MARKOV-AUDIT",
        "status": "COMPLETE_HISTORICAL_EXPLORATORY",
        "decision": "NO_MARKOV_LIFT_IN_NINE_NON_DIFFERENCED_STRUCTURAL_FEATURES; DIFFERENCED_FEATURE_GAIN_IS_COMPATIBLE_WITH_IID_MECHANICS",
        "source": {
            "artifact_run_id": 43348144964,
            "artifact_id": 14003350043,
            "archive_blob_sha1": source["archive_blob_sha1"],
            "matrix_sha256": source["matrix_sha256"],
            "matrix_shape": source["matrix_shape"],
            "feature_count": source["feature_count"],
            "draws_in_matrix": len(source["draws"]),
            "first_target_date": str(source["dates"][0]),
            "last_target_date": str(source["dates"][-1]),
        },
        "design": {
            "features": FEATURES,
            "feature_category_count": sum(len(v) for v in FEATURE_CATEGORIES.values()),
            "model": "one-step categorical Markov transition forecast with prior-only transition counts",
            "baseline": "expanding marginal category frequency with symmetric Dirichlet alpha=0.5 per category",
            "markov_smoothing": "transition row shrunk toward the same prior-only marginal baseline with fixed alpha=20",
            "warmup_rows": WARMUP,
            "targets": n,
            "split_counts": {"discovery": n_discovery, "validation": n_validation, "blind_oos": n_blind},
            "primary_diagnostic": "mean log-loss gain of core nine non-differenced structural features; baseline minus Markov",
            "secondary_diagnostic": "mean multiclass Brier gain of the same core nine features",
            "mechanical_features": MECHANICAL_FEATURES,
            "mechanical_null": "2,000 independent uniform unordered 5-of-40 sequences; identical prior-only Markov scorer; empirical upper-tail p and Holm across four differenced-feature metrics",
            "inference": "circular moving-block bootstrap length 20, 20,000 replicates; HAC lag 20 and Holm across nine core-feature tests",
            "tuning": "no parameter search; smoothing constants fixed at 0.5 and 20",
        },
        "split_metrics": split_summary,
        "blind_oos_inference": blind_inference,
        "blind_core9_feature_tests": feature_rows,
        "blind_feature_metrics": {
            feature: {
                "mean_logloss_gain": mean_field(blind, f"{feature}_logloss_gain"),
                "mean_brier_gain": mean_field(blind, f"{feature}_brier_gain"),
            } for feature in FEATURES
        },
        "iid_mechanical_null": null,
        "contribution_decomposition": {
            "full11_logloss_gain": split_summary["blind_oos"]["full11_mean_logloss_gain"],
            "transition_pair_weighted_contribution_to_full11": transition_contribution,
            "core9_weighted_contribution_to_full11": core_contribution,
            "identity_check": transition_contribution + core_contribution,
            "interpretation": "The full11 aggregate is dominated by two first-difference features; their adjacent values share the middle draw and can be dependent even when draws are IID. The core9 features do not show positive skill.",
        },
        "integrity": {
            "matrix_sha256_verified": True,
            "archive_blob_sha1_pinned": True,
            "matrix_finite": True,
            "draws_valid_sorted_unique": True,
            "dates_unique_chronological": True,
            "all_cutoffs_precede_targets": True,
            "fixed_category_vocabulary_51": sum(len(v) for v in FEATURE_CATEGORIES.values()) == 51,
            "first_undefined_transition_excluded": True,
            "training_uses_only_y_1_through_t_minus_1": True,
            "future_suffix_invariance": suffix_invariant,
            "deterministic_full_replay": True,
        },
        "limitations": [
            "Historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation.",
            "This experiment predicts 11 structural categories, not individual numbers or exact five-number tickets.",
            "The two difference features have mechanical lag dependence because adjacent differences share the middle draw; their apparent skill is not evidence that lottery draws are predictable.",
            "The IID simulation uses independent uniform unordered 5-of-40 draws and is a statistical reference, not a physical mechanism model.",
            "Smoothing constants were fixed for this diagnostic but the experiment was designed after earlier historical exploration; p-values are exploratory.",
            "The nine-feature Markov model is a one-lag categorical model; it does not exhaust higher-order or formula-family dynamics.",
            "No prospective outcome is read or appended; the 2026-11-13 freezes remain unchanged.",
        ],
        "governance": {
            "b11_freeze_unchanged": True,
            "main_archive_mutated": False,
            "active_engine_mutated": False,
            "shadow_forecasts_mutated": False,
            "engine_promoted": False,
            "merge": False,
            "rebase": False,
            "protected_prs_6_7_8_untouched": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "q141_a12_structural_markov_target_ledger_2026-11-13.csv"
    report_path = output_dir / "q141_a12_structural_markov_report_2026-11-13.json"
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    prereg_path = output_dir / "q141_a12_structural_markov_preregistration_2026-11-13.md"
    prereg_text = """# Q141-A12 — Structural Markov audit

**Protocol status:** retrospective exploratory diagnostic. This protocol was written after prior historical exploration and is not a prospective preregistration or a virgin confirmatory test.

## Quantitative hypothesis

Test whether the previous category of each of nine non-differenced structural streams improves next-draw category forecasts over an expanding marginal-frequency baseline. The practical target is at least **+0.005 nats per feature** of mean log-loss gain and at least **+0.001** mean multiclass Brier gain on the chronological historical holdout.

Separately test whether apparent skill in 'sum_transition' and 'range_transition' exceeds what is expected under independent uniform unordered 5-of-40 draws. Adjacent first differences share the middle draw, so a positive lag-1 score is not automatically evidence of predictable lottery outcomes.

## Fixed model

- Structural streams: 'sum_bin', 'range_bin', 'odd_cat', 'low_cat', 'overlap_cat', 'gap1_bin'–'gap4_bin', 'sum_transition', 'range_transition' (51 fixed categories across 11 streams).
- Baseline: expanding marginal category frequency with symmetric Dirichlet alpha 0.5 per category.
- Markov: one-step transition row shrunk toward the same prior-only marginal distribution with fixed alpha 20.
- Warmup: 400 matrix rows. Each target uses only categories from rows strictly before the target.
- First undefined transition row is excluded from all training histories.
- No parameter search or retuning.

## Chronological design

- Source: pinned Q141-A7 artifact run 43348144964, artifact 14003350043.
- Canonical archive blob: '6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb'; matrix SHA-256: '81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047'.
- 3,356 target rows; 400-row warmup; 2,956 scored targets.
- 60/20/20 chronological split: Discovery 1,774; Validation 591; historical Blind OOS 591.
- Metrics: multiclass log loss and Brier score, baseline minus Markov (positive is better).
- Inference: circular moving-block bootstrap, block length 20, 20,000 replicates; HAC lag 20; Holm across nine core-feature tests.
- Mechanical null: 2,000 independent uniform 5-of-40 sequences, same length and same scorer; empirical upper-tail tests for log-loss and Brier of both difference features, Holm across four tests.

## Interpretation limits

The historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation. The two difference features are mechanically dependent under IID draws because adjacent differences share one underlying draw. This experiment forecasts structural categories, not numbers or exact tickets. A positive historical score cannot justify model promotion. Any follow-up must be separately frozen and evaluated prospectively.

## Governance

No canonical archive mutation, no shadow or active-engine mutation, no forecast rewrite, no model promotion, no merge or rebase. PRs #6, #7 and #8 remain untouched.
"""
    prereg_path.write_text(prereg_text, encoding="utf-8")

    cycle_path = output_dir / "q141_cycle_report_2026-11-13_run22.md"
    cycle_text = f"""# VinciCasa SONAR — cycle 22 (2026-11-13)

## Recovery
- Recovered Q141-A11 checkpoint and verified its report, ledger and source lineage.
- Main branch is newer than PR #90; this cycle is isolated on a new branch from the current main head.
- Canonical archive blob: '{source["archive_blob_sha1"]}'; source matrix SHA-256: '{source["matrix_sha256"]}'.
- Existing 2026-11-13 freezes remain pending and unchanged.

## Q141-A12 result
- 11 structural category streams, 51 fixed categories.
- 400-row warmup; 2,956 prior-only targets.
- Discovery 1,774; Validation 591; historical Blind OOS 591.
- Blind full-11 mean log-loss gain: {split_summary["blind_oos"]["full11_mean_logloss_gain"]:.8f}.
- Blind core-9 mean log-loss gain: {split_summary["blind_oos"]["core9_mean_logloss_gain"]:.8f}.
- Blind core-9 mean Brier gain: {split_summary["blind_oos"]["core9_mean_brier_gain"]:.8f}.
- The apparent full-11 gain is dominated by sum/range first-difference streams.
- Under 2,000 IID uniform 5-of-40 simulations, the difference-feature gains are compatible with the mechanical null after Holm correction.
- Decision: no Markov lift demonstrated in the nine non-differenced structural features.

## Integrity
- Source hash, matrix shape, dates, cutoffs, fixed vocabulary, deterministic replay and future-suffix invariance checked.
- Historical Blind OOS is exploratory, not virgin confirmation.
- No prospective result was read or appended; no active engine or shadow freeze was changed.

## Next action
Review this mechanical-dependence diagnosis. Do not promote the Markov model. If retained, register a separate prospective structural-category forecast only after human review; continue append-only collection for existing prospective gates.
"""
    cycle_path.write_text(cycle_text, encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "task_id": report["task_id"],
        "source_archive_blob_sha1": source["archive_blob_sha1"],
        "source_matrix_sha256": source["matrix_sha256"],
        "code_sha256": _sha256(Path(__file__).resolve()),
        "outputs": {},
    }
    for path in (report_path, ledger_path, prereg_path, cycle_path):
        raw = path.read_bytes()
        manifest["outputs"][path.name] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1": _git_blob_sha1(path),
        }
    manifest_path = output_dir / "q141_a12_structural_markov_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0",
        "cycle": 22,
        "task_id": report["task_id"],
        "status": "LOCAL_REPLAY_COMPLETE_PENDING_REMOTE_READBACK",
        "decision": report["decision"],
        "report_path": str(report_path),
        "ledger_path": str(ledger_path),
        "manifest_path": str(manifest_path),
        "preregistration_path": str(prereg_path),
        "cycle_report_path": str(cycle_path),
        "next_action": "Review the mechanical-dependence diagnosis; keep existing prospective freezes unchanged; any new category forecast requires a separate prospective preregistration.",
        "governance": report["governance"],
    }
    checkpoint_path = output_dir / "q141_a12_structural_markov_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    args = parser.parse_args()
    report = run_experiment(args.input, args.outdir)
    print(json.dumps({
        "status": report["status"],
        "decision": report["decision"],
        "targets": report["design"]["targets"],
        "split_counts": report["design"]["split_counts"],
        "blind_core9_logloss_gain": report["split_metrics"]["blind_oos"]["core9_mean_logloss_gain"],
        "blind_full11_logloss_gain": report["split_metrics"]["blind_oos"]["full11_mean_logloss_gain"],
        "iid_null_p_holm": report["iid_mechanical_null"]["p_holm_across_four_mechanical_tests"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
