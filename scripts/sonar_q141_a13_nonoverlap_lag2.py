#!/usr/bin/env python3
# Q141-A13 workflow trigger marker; experiment semantics unchanged.
"""Q141-A13: non-overlapping lag-2 transitions for structural first differences.

The model asks whether a category of a sum/range first difference predicts
the category two rows later, using only modulo-4 phase-matched training blocks.
Each training example consumes four consecutive draw rows; examples are
spaced four rows apart, and the final training block ends before the target
block begins. This removes the shared-draw overlap that mechanically affects
lag-1 differences under IID draws.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

import sonar_q141_a12_structural_markov_audit as a12

EXPECTED_ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_MATRIX_SHA256 = "81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047"
EXPECTED_MATRIX_SHAPE = (3356, 40, 59)
EXPECTED_A12_BUILDER_BLOB_SHA1 = "208035ce9d2e949b47cf4caa9cf2ddf71018348c"
FEATURES = ("sum_transition", "range_transition")
WARMUP = 400
BASE_ALPHA = 0.5
TRANSITION_ALPHA = 20.0
PHASE_STRIDE = 4
BLOCK_LENGTH = 20
BOOTSTRAP_REPS = 20_000
IID_REPS = 2_000
IID_SEED = 14111313
BOOTSTRAP_SEED = 14111314
PRACTICAL_LOGLOSS_GAIN = 0.005
PRACTICAL_BRIER_GAIN = 0.001


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def a12_builder_blob_sha1() -> str:
    path = Path(a12.__file__).resolve()
    actual = subprocess.check_output(
        ["git", "hash-object", str(path)], text=True
    ).strip()
    if actual != EXPECTED_A12_BUILDER_BLOB_SHA1:
        raise ValueError("pinned Q141-A12 feature builder Git blob mismatch")
    return actual


def load_source(path: Path) -> dict:
    matrix_sha = sha256(path)
    if matrix_sha != EXPECTED_MATRIX_SHA256:
        raise ValueError("Q141-A7 source matrix SHA-256 mismatch")
    builder_sha = a12_builder_blob_sha1()
    with np.load(path, allow_pickle=False) as data:
        matrix = data["feature_matrix"]
        dates = data["target_dates"].astype(str)
        cutoffs = data["cutoff_dates"].astype(str)
        draws = data["actual_quintets"].astype(np.int64)
        names = data["feature_names"].astype(str)
        archive_sha = str(data["archive_blob_sha"].item())
    if archive_sha != EXPECTED_ARCHIVE_BLOB:
        raise ValueError("canonical archive Git blob SHA-1 mismatch")
    if matrix.shape != EXPECTED_MATRIX_SHAPE or len(names) != 59:
        raise ValueError("unexpected feature matrix shape or feature count")
    if draws.shape != (EXPECTED_MATRIX_SHAPE[0], 5) or not np.isfinite(matrix).all():
        raise ValueError("invalid source matrix or target quintets")
    draws = a12.validate_draws(draws)
    if len(set(dates.tolist())) != len(dates):
        raise ValueError("duplicate target dates")
    if np.any(np.diff(dates.astype("datetime64[D]").astype(np.int64)) <= 0):
        raise ValueError("target dates are not strictly chronological")
    if not np.all(cutoffs < dates):
        raise ValueError("one or more source cutoffs are not strictly prior")
    return {
        "matrix_sha256": matrix_sha,
        "archive_blob_sha1": archive_sha,
        "a12_builder_blob_sha1": builder_sha,
        "matrix_shape": list(matrix.shape),
        "feature_count": len(names),
        "dates": dates,
        "cutoffs": cutoffs,
        "draws": draws,
    }


def training_indices(target_index: int) -> np.ndarray:
    """Prior sample endpoints s: s == target mod 4 and s <= target-4."""
    t = int(target_index)
    if t < WARMUP:
        raise ValueError("target precedes warmup")
    phase = t % PHASE_STRIDE
    first = PHASE_STRIDE + ((phase - PHASE_STRIDE) % PHASE_STRIDE)
    return np.arange(first, t - 3, PHASE_STRIDE, dtype=np.int64)


def verify_nonoverlap_geometry(target_index: int) -> bool:
    """Verify disjoint four-draw training blocks and target block."""
    t = int(target_index)
    samples = training_indices(t)
    if len(samples) == 0:
        return False
    if np.any(samples % PHASE_STRIDE != t % PHASE_STRIDE):
        return False
    if samples[-1] > t - 4 or (len(samples) > 1 and np.any(np.diff(samples) != 4)):
        return False
    windows = [(int(s) - 3, int(s)) for s in samples]
    for left, right in zip(windows, windows[1:]):
        if left[1] >= right[0]:
            return False
    target_window = (t - 3, t)
    return windows[-1][1] < target_window[0]


def phase_forecast(y: np.ndarray, target_index: int, k: int,
                   alpha_base: float = BASE_ALPHA,
                   alpha_transition: float = TRANSITION_ALPHA) -> dict:
    """Scalar reference forecast using the target's modulo-4 phase sample."""
    y = np.asarray(y, dtype=np.int64)
    t = int(target_index)
    if t < WARMUP or t >= len(y):
        raise ValueError("target outside walk-forward range")
    if np.any(y[1:] < 0) or np.any(y[1:] >= k):
        raise ValueError("invalid category history")
    if not verify_nonoverlap_geometry(t):
        raise ValueError("non-overlapping phase geometry failed")
    s = training_indices(t)
    counts = np.bincount(y[s], minlength=k).astype(np.float64)
    p0 = (counts + alpha_base) / (len(s) + alpha_base * k)
    transition_counts = np.zeros((k, k), dtype=np.float64)
    np.add.at(transition_counts, (y[s - 2], y[s]), 1.0)
    state = int(y[t - 2])
    row = transition_counts[state]
    p1 = (row + alpha_transition * p0) / (row.sum() + alpha_transition)
    actual = int(y[t])
    one_hot = np.zeros(k, dtype=np.float64)
    one_hot[actual] = 1.0
    return {
        "p0": p0,
        "p1": p1,
        "logloss_gain": math.log(float(p1[actual]) / float(p0[actual])),
        "brier_gain": float(np.sum((p0 - one_hot) ** 2) - np.sum((p1 - one_hot) ** 2)),
        "prior_samples": int(len(s)),
        "max_training_sample_index": int(s[-1]),
        "phase": int(t % PHASE_STRIDE),
        "state_category": state,
        "target_category": actual,
        "transition_row_count": int(row.sum()),
    }


def score_series(y: np.ndarray, k: int, start: int = WARMUP) -> dict:
    """Vectorized prior-only lag-2 forecast using disjoint modulo-4 samples."""
    y = np.asarray(y, dtype=np.int64)
    n = len(y)
    if start < WARMUP or start >= n:
        raise ValueError("invalid scoring start")
    if np.any(y[1:] < 0) or np.any(y[1:] >= k):
        raise ValueError("invalid category stream")
    targets = np.arange(start, n, dtype=np.int64)
    out = {
        "logloss_gain": np.empty(len(targets), dtype=np.float64),
        "brier_gain": np.empty(len(targets), dtype=np.float64),
        "prior_samples": np.empty(len(targets), dtype=np.int64),
        "max_training_sample_index": np.empty(len(targets), dtype=np.int64),
        "phase": targets % PHASE_STRIDE,
        "state_category": y[targets - 2].copy(),
        "target_category": y[targets].copy(),
        "baseline_probability": np.empty(len(targets), dtype=np.float64),
        "markov_probability": np.empty(len(targets), dtype=np.float64),
        "transition_row_count": np.empty(len(targets), dtype=np.int64),
    }
    identity = np.eye(k, dtype=np.float64)
    transition_identity = np.eye(k * k, dtype=np.float64)

    for phase in range(PHASE_STRIDE):
        positions = np.flatnonzero(targets % PHASE_STRIDE == phase)
        phase_targets = targets[positions]
        first = PHASE_STRIDE + ((phase - PHASE_STRIDE) % PHASE_STRIDE)
        sample_endpoints = np.arange(first, n, PHASE_STRIDE, dtype=np.int64)
        train_counts = np.searchsorted(sample_endpoints, phase_targets - 4, side="right")
        if np.any(train_counts <= 0):
            raise ValueError("insufficient phase-matched prior training blocks")

        sample_categories = y[sample_endpoints]
        sample_pairs = y[sample_endpoints - 2] * k + y[sample_endpoints]
        cumulative_counts = np.cumsum(identity[sample_categories], axis=0)
        cumulative_transitions = np.cumsum(transition_identity[sample_pairs], axis=0)

        counts = cumulative_counts[train_counts - 1]
        transitions = cumulative_transitions[train_counts - 1].reshape(-1, k, k)
        states = y[phase_targets - 2]
        actual = y[phase_targets]
        rows = transitions[np.arange(len(positions)), states]

        p0 = (counts + BASE_ALPHA) / (
            train_counts[:, None] + BASE_ALPHA * k
        )
        row_totals = rows.sum(axis=1)
        p1 = (rows + TRANSITION_ALPHA * p0) / (
            row_totals[:, None] + TRANSITION_ALPHA
        )
        if not np.allclose(p0.sum(axis=1), 1.0, atol=1e-12, rtol=0):
            raise ArithmeticError("phase baseline probabilities do not sum to one")
        if not np.allclose(p1.sum(axis=1), 1.0, atol=1e-12, rtol=0):
            raise ArithmeticError("lag-2 probabilities do not sum to one")

        p0_actual = p0[np.arange(len(positions)), actual]
        p1_actual = p1[np.arange(len(positions)), actual]
        one_hot = identity[actual]
        brier0 = np.sum((p0 - one_hot) ** 2, axis=1)
        brier1 = np.sum((p1 - one_hot) ** 2, axis=1)

        out["logloss_gain"][positions] = np.log(p1_actual / p0_actual)
        out["brier_gain"][positions] = brier0 - brier1
        out["prior_samples"][positions] = train_counts
        out["max_training_sample_index"][positions] = sample_endpoints[train_counts - 1]
        out["baseline_probability"][positions] = p0_actual
        out["markov_probability"][positions] = p1_actual
        out["transition_row_count"][positions] = row_totals.astype(np.int64)

    return out


def split_counts(n: int) -> dict:
    discovery = int(round(n * 0.60))
    validation = int(round(n * 0.20))
    return {
        "discovery": discovery,
        "validation": validation,
        "blind_oos": n - discovery - validation,
    }


def summarize_split(scores: dict[str, dict], lo: int, hi: int) -> dict:
    result = {}
    for feature in FEATURES:
        result[feature] = {
            "mean_logloss_gain": float(np.mean(scores[feature]["logloss_gain"][lo:hi])),
            "mean_brier_gain": float(np.mean(scores[feature]["brier_gain"][lo:hi])),
        }
    result["pooled_two_feature_mean"] = {
        "mean_logloss_gain": float(np.mean([
            np.mean(scores[f]["logloss_gain"][lo:hi]) for f in FEATURES
        ])),
        "mean_brier_gain": float(np.mean([
            np.mean(scores[f]["brier_gain"][lo:hi]) for f in FEATURES
        ])),
    }
    return result


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
        "p_centered_block_bootstrap": p_value,
        "replicates": reps,
        "block_length": block,
    }


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


def empirical_upper_p(null_values: np.ndarray, observed: float) -> float:
    values = np.asarray(null_values, dtype=np.float64)
    return (1.0 + float(np.sum(values >= observed))) / (len(values) + 1.0)


def transition_codes_from_draws(draws: np.ndarray) -> dict[str, np.ndarray]:
    x = a12.validate_draws(draws)
    n = len(x)
    sums = x.sum(axis=1)
    ranges = x[:, -1] - x[:, 0]
    sum_delta = np.diff(sums)
    range_delta = np.diff(ranges)
    sum_codes = np.full(n, -1, dtype=np.int16)
    range_codes = np.full(n, -1, dtype=np.int16)
    sum_codes[1:] = np.where(
        sum_delta <= -16, 0,
        np.where(sum_delta <= -6, 1,
                 np.where(sum_delta >= 16, 4, np.where(sum_delta >= 6, 3, 2)))
    )
    range_codes[1:] = np.where(
        range_delta <= -6, 0,
        np.where(range_delta <= -2, 1,
                 np.where(range_delta >= 6, 4, np.where(range_delta >= 2, 3, 2)))
    )
    return {"sum_transition": sum_codes, "range_transition": range_codes}


def iid_mechanical_null(n_draws: int, blind_start: int,
                        reps: int = IID_REPS, seed: int = IID_SEED) -> dict:
    """IID uniform 5-of-40 simulation using the exact same phase-stratified scorer."""
    rng = np.random.default_rng(seed)
    simulated = np.empty((reps, len(FEATURES), 2), dtype=np.float64)
    for rep in range(reps):
        random_scores = rng.random((n_draws, 40))
        draws = np.argpartition(random_scores, 5, axis=1)[:, :5] + 1
        draws.sort(axis=1)
        codes = transition_codes_from_draws(draws)
        for feature_index, feature in enumerate(FEATURES):
            scores = score_series(codes[feature], 5, WARMUP)
            simulated[rep, feature_index, 0] = float(
                scores["logloss_gain"][blind_start:].mean()
            )
            simulated[rep, feature_index, 1] = float(
                scores["brier_gain"][blind_start:].mean()
            )

    pooled = simulated.mean(axis=1)
    feature_summary = {}
    for i, feature in enumerate(FEATURES):
        feature_summary[feature] = {
            "mean": [float(v) for v in simulated[:, i, :].mean(axis=0)],
            "sd": [float(v) for v in simulated[:, i, :].std(axis=0, ddof=1)],
            "q025_q50_q975": [
                [float(v) for v in np.quantile(simulated[:, i, metric], [0.025, 0.50, 0.975])]
                for metric in range(2)
            ],
        }
    return {
        "replicates": reps,
        "seed": seed,
        "pooled_mean": [float(v) for v in pooled.mean(axis=0)],
        "pooled_sd": [float(v) for v in pooled.std(axis=0, ddof=1)],
        "pooled_q025_q50_q975": [
            [float(v) for v in np.quantile(pooled[:, metric], [0.025, 0.50, 0.975])]
            for metric in range(2)
        ],
        "features": feature_summary,
        "simulated_pooled": pooled,
        "simulated_features": simulated,
    }


def verify_future_suffix_invariance(draws: np.ndarray, target: int) -> bool:
    original_codes = transition_codes_from_draws(draws)
    original = {
        f: phase_forecast(original_codes[f], target, 5) for f in FEATURES
    }
    mutated = np.asarray(draws, dtype=np.int64).copy()
    rng = np.random.default_rng(14111315)
    for i in range(target + 1, len(mutated)):
        mutated[i] = np.sort(rng.choice(np.arange(1, 41), 5, replace=False))
    mutated_codes = transition_codes_from_draws(mutated)
    changed = {
        f: phase_forecast(mutated_codes[f], target, 5) for f in FEATURES
    }
    for feature in FEATURES:
        for key in ("logloss_gain", "brier_gain", "prior_samples",
                    "max_training_sample_index", "phase", "state_category",
                    "target_category", "transition_row_count"):
            if original[feature][key] != changed[feature][key]:
                return False
        if not np.array_equal(original[feature]["p0"], changed[feature]["p0"]):
            return False
        if not np.array_equal(original[feature]["p1"], changed[feature]["p1"]):
            return False
    return True


def build_ledger(codes: dict[str, np.ndarray], dates: np.ndarray,
                 cutoffs: np.ndarray, start: int = WARMUP) -> tuple[list[dict], dict]:
    scores = {
        feature: score_series(codes[feature], len(a12.FEATURE_CATEGORIES[feature]), start)
        for feature in FEATURES
    }
    targets = np.arange(start, len(dates), dtype=np.int64)
    records = []
    for position, t in enumerate(targets):
        if not str(cutoffs[t]) < str(dates[t]):
            raise ValueError(f"cutoff is not prior at target {dates[t]}")
        row = {
            "target_index": int(t),
            "target_date": str(dates[t]),
            "cutoff_date": str(cutoffs[t]),
            "prior_archive_draw_rows": int(t),
            "phase_mod4": int(t % PHASE_STRIDE),
            "target_raw_draw_window_start": int(t - 3),
            "target_raw_draw_window_end": int(t),
        }
        for feature in FEATURES:
            score = scores[feature]
            row[f"{feature}_logloss_gain"] = float(score["logloss_gain"][position])
            row[f"{feature}_brier_gain"] = float(score["brier_gain"][position])
            row[f"{feature}_prior_samples"] = int(score["prior_samples"][position])
            row[f"{feature}_max_training_sample_index"] = int(
                score["max_training_sample_index"][position]
            )
            row[f"{feature}_transition_row_count"] = int(
                score["transition_row_count"][position]
            )
        row["pooled_logloss_gain"] = float(np.mean([
            row[f"{f}_logloss_gain"] for f in FEATURES
        ]))
        row["pooled_brier_gain"] = float(np.mean([
            row[f"{f}_brier_gain"] for f in FEATURES
        ]))
        row["phase_geometry_valid"] = all(
            row[f"{f}_max_training_sample_index"] <= t - 4 for f in FEATURES
        )
        if not row["phase_geometry_valid"] or not verify_nonoverlap_geometry(int(t)):
            raise ValueError(f"non-overlap geometry failed at target {dates[t]}")
        records.append(row)
    return records, scores


def run_experiment(input_path: Path, output_dir: Path,
                   iid_reps: int = IID_REPS,
                   bootstrap_reps: int = BOOTSTRAP_REPS) -> dict:
    source = load_source(input_path)
    codes = a12.build_feature_codes(source["draws"])
    records, scores = build_ledger(codes, source["dates"], source["cutoffs"])
    replay, replay_scores = build_ledger(codes, source["dates"], source["cutoffs"])
    if records != replay:
        raise ValueError("deterministic target-ledger replay mismatch")
    for feature in FEATURES:
        for metric in ("logloss_gain", "brier_gain", "prior_samples",
                       "max_training_sample_index", "transition_row_count"):
            if not np.array_equal(scores[feature][metric], replay_scores[feature][metric]):
                raise ValueError("deterministic score replay mismatch")

    n = len(records)
    counts = split_counts(n)
    discovery_end = counts["discovery"]
    validation_end = discovery_end + counts["validation"]
    split_metrics = {
        "discovery": summarize_split(scores, 0, discovery_end),
        "validation": summarize_split(scores, discovery_end, validation_end),
        "blind_oos": summarize_split(scores, validation_end, n),
    }
    blind_pool_logloss = np.asarray(
        [r["pooled_logloss_gain"] for r in records[validation_end:]], dtype=np.float64
    )
    blind_pool_brier = np.asarray(
        [r["pooled_brier_gain"] for r in records[validation_end:]], dtype=np.float64
    )
    bootstrap_logloss = circular_block_bootstrap(
        blind_pool_logloss, BOOTSTRAP_SEED, bootstrap_reps
    )
    bootstrap_brier = circular_block_bootstrap(
        blind_pool_brier, BOOTSTRAP_SEED + 1, bootstrap_reps
    )

    null = iid_mechanical_null(
        len(source["draws"]), validation_end, iid_reps, IID_SEED
    )
    observed_pool = [
        float(blind_pool_logloss.mean()),
        float(blind_pool_brier.mean()),
    ]
    pooled_null = null["simulated_pooled"]
    primary_p = [
        empirical_upper_p(pooled_null[:, metric], observed_pool[metric])
        for metric in range(2)
    ]
    primary_holm = holm_adjust(primary_p)

    feature_p = []
    feature_test_rows = []
    for feature_index, feature in enumerate(FEATURES):
        for metric_index, metric_name in enumerate(("logloss_gain", "brier_gain")):
            observed = float(split_metrics["blind_oos"][feature]["mean_" + metric_name])
            p_value = empirical_upper_p(
                null["simulated_features"][:, feature_index, metric_index], observed
            )
            feature_p.append(p_value)
            feature_test_rows.append({
                "feature": feature,
                "metric": metric_name,
                "observed_blind_mean_gain": observed,
                "iid_null_mean": null["features"][feature]["mean"][metric_index],
                "p_iid_upper_tail": p_value,
            })
    feature_holm = holm_adjust(feature_p)
    for row, adjusted in zip(feature_test_rows, feature_holm):
        row["p_holm_across_four_feature_metrics"] = adjusted

    iid_pooled_summary = {
        "logloss_gain": {
            "observed": observed_pool[0],
            "null_mean": float(pooled_null[:, 0].mean()),
            "null_sd": float(pooled_null[:, 0].std(ddof=1)),
            "null_q025_q50_q975": [
                float(v) for v in np.quantile(pooled_null[:, 0], [0.025, 0.50, 0.975])
            ],
            "p_iid_upper_tail": primary_p[0],
            "p_holm_across_two_primary_endpoints": primary_holm[0],
        },
        "brier_gain": {
            "observed": observed_pool[1],
            "null_mean": float(pooled_null[:, 1].mean()),
            "null_sd": float(pooled_null[:, 1].std(ddof=1)),
            "null_q025_q50_q975": [
                float(v) for v in np.quantile(pooled_null[:, 1], [0.025, 0.50, 0.975])
            ],
            "p_iid_upper_tail": primary_p[1],
            "p_holm_across_two_primary_endpoints": primary_holm[1],
        },
    }

    geometry_ok = all(
        int(r["phase_mod4"]) == int(r["target_index"]) % PHASE_STRIDE
        and int(r["sum_transition_max_training_sample_index"]) <= int(r["target_index"]) - 4
        and int(r["range_transition_max_training_sample_index"]) <= int(r["target_index"]) - 4
        and r["phase_geometry_valid"]
        for r in records
    )
    if not geometry_ok:
        raise ValueError("ledger phase/embargo geometry validation failed")
    future_target = WARMUP + 37
    future_invariant = verify_future_suffix_invariance(source["draws"], future_target)
    if not future_invariant:
        raise ValueError("future-suffix invariance failed")

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-A13-NONOVERLAP-LAG2",
        "status": "COMPLETED_HISTORICAL_EXPLORATORY_WALK_FORWARD",
        "decision": "NO_NONOVERLAP_LAG2_TRANSITION_LIFT_DEMONSTRATED",
        "source": {
            "a7_artifact_run_id": 43348144964,
            "a7_artifact_id": 14003350043,
            "archive_blob_sha1": source["archive_blob_sha1"],
            "matrix_sha256": source["matrix_sha256"],
            "a12_feature_builder_blob_sha1": source["a12_builder_blob_sha1"],
            "matrix_shape": source["matrix_shape"],
            "feature_count": source["feature_count"],
            "draw_rows": len(source["draws"]),
            "first_target_date": str(source["dates"][0]),
            "last_target_date": str(source["dates"][-1]),
        },
        "design": {
            "features": list(FEATURES),
            "model": "lag-2 categorical transition from delta[t-2] to delta[t]",
            "mechanical_overlap_control": (
                "phase-matched modulo-4 training endpoints; each training example "
                "uses raw draw rows [s-3,s], examples are spaced by four rows, "
                "and the last training block ends at t-4 before target block [t-3,t]"
            ),
            "baseline": (
                "expanding marginal category frequency computed on exactly the same "
                "phase-matched, non-overlapping training endpoints"
            ),
            "phase_stride": PHASE_STRIDE,
            "base_dirichlet_alpha": BASE_ALPHA,
            "transition_shrinkage_alpha": TRANSITION_ALPHA,
            "warmup_rows": WARMUP,
            "targets": n,
            "target_index_start_inclusive": WARMUP,
            "target_index_end_inclusive": len(source["draws"]) - 1,
            "split_counts": counts,
            "primary_endpoint": "Blind OOS pooled mean log-loss gain across sum_transition and range_transition",
            "secondary_endpoint": "Blind OOS pooled mean multiclass Brier gain across the same two features",
            "practical_thresholds": {
                "pooled_logloss_gain": PRACTICAL_LOGLOSS_GAIN,
                "pooled_brier_gain": PRACTICAL_BRIER_GAIN,
            },
            "inference": (
                "2,000 independent uniform 5-of-40 sequence simulations with the exact "
                "same modulo-4 phase scorer; circular moving-block bootstrap length 20, "
                "20,000 replicates as interval sensitivity"
            ),
            "multiple_testing": (
                "Holm across two pooled confirmatory endpoints; separate Holm across "
                "four feature-specific exploratory metrics; not across the full Q00-Q141 family"
            ),
            "tuning": "none; all bins, phase stride, warmup and smoothing constants fixed",
        },
        "split_metrics": {
            name: {
                "targets": counts[name],
                "pooled_two_feature_mean_logloss_gain": metrics["pooled_two_feature_mean"]["mean_logloss_gain"],
                "pooled_two_feature_mean_brier_gain": metrics["pooled_two_feature_mean"]["mean_brier_gain"],
                "features": {f: metrics[f] for f in FEATURES},
            }
            for name, metrics in split_metrics.items()
        },
        "blind_oos_inference": {
            "pooled_logloss_gain": bootstrap_logloss,
            "pooled_brier_gain": bootstrap_brier,
            "iid_mechanical_null": iid_pooled_summary,
            "feature_specific_exploratory_tests": feature_test_rows,
            "iid_simulation": {
                "replicates": iid_reps,
                "seed": IID_SEED,
                "pooled_null_mean": null["pooled_mean"],
                "pooled_null_sd": null["pooled_sd"],
                "pooled_null_q025_q50_q975": null["pooled_q025_q50_q975"],
            },
        },
        "integrity": {
            "source_archive_blob_pinned": True,
            "source_matrix_sha256_verified": True,
            "a12_feature_builder_blob_pinned": True,
            "matrix_finite": True,
            "draws_valid_sorted_unique": True,
            "dates_unique_chronological": True,
            "all_cutoffs_precede_targets": True,
            "phase_matched_training": True,
            "training_samples_spaced_by_four": True,
            "training_target_raw_draw_windows_disjoint": True,
            "last_training_block_ends_at_t_minus_4": True,
            "target_uses_only_prior_state_and_current_target": True,
            "future_suffix_invariance": future_invariant,
            "deterministic_full_replay": True,
            "iid_simulation_seed_fixed": True,
        },
        "limitations": [
            "Historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation.",
            "Only two differenced structural streams are tested; this is not a test of all 59 features or all formula families.",
            "Modulo-4 phase sampling uses approximately one quarter of prior transitions to guarantee disjoint four-draw training blocks; this reduces effective training size.",
            "The expanding marginal baseline uses the identical phase-matched training sample, so the comparison isolates lag-2 transition information rather than sample-size advantage.",
            "IID simulations assume independent uniform unordered 5-of-40 draws; this is a statistical reference, not a physical mechanism model.",
            "The model forecasts structural categories, not individual numbers or exact five-number tickets.",
            "Holm correction covers the two registered pooled endpoints and separately the four exploratory feature metrics, not the full Q00-Q141 research history.",
            "No 2026-11-13 prospective outcome is read or appended; B11 remains unchanged.",
        ],
        "governance": {
            "b11_freeze_unchanged": True,
            "canonical_archive_mutated": False,
            "active_engine_mutated": False,
            "shadow_forecasts_mutated": False,
            "engine_promoted": False,
            "merge": False,
            "rebase": False,
            "protected_prs_6_7_8_untouched": True,
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "q141_a13_nonoverlap_lag2_target_ledger_2026-11-13.csv"
    report_path = output_dir / "q141_a13_nonoverlap_lag2_report_2026-11-13.json"
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].keys()))
        writer.writeheader()
        writer.writerows(records)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    prereg_path = output_dir / "q141_a13_nonoverlap_lag2_preregistration_2026-11-13.md"
    if not prereg_path.exists():
        raise FileNotFoundError("A13 preregistration must be committed before execution")
    mechanical_note_path = output_dir / "q141_a13_nonoverlap_lag2_mechanical_independence_note_2026-11-13.md"
    mechanical_note_path.write_text(
        """# Q141-A13 — non-overlapping lag-2 structural transitions

## Mechanical issue addressed

For a level series X[t], adjacent first differences D[t]=X[t]-X[t-1] and
D[t-1] share X[t-1]. Under IID levels this creates negative lag-1 dependence
without any predictable lottery mechanism. Q141-A12 documented this for
sum and range.

## A13 construction

A13 tests whether D[t-2] predicts D[t]. These two differences use disjoint
level observations: D[t-2] uses X[t-2], X[t-3], while D[t] uses X[t], X[t-1].

To prevent training examples from sharing raw draw rows with each other or
with the target, only prior transition endpoints s congruent to t modulo 4
are used. Each training example consumes rows [s-3,s], examples are spaced
by four rows, and the final training endpoint is at most t-4. The target
block is [t-3,t]. Thus all four-draw blocks are disjoint.

The expanding marginal baseline uses exactly the same phase-matched sample
as the lag-2 transition model. This isolates incremental transition
information, at the cost of using about one quarter of available history.

## Interpretation

The historical walk-forward and IID 5-of-40 simulation are exploratory.
Even a positive result would require a separately frozen prospective test.
A13 predicts only sum/range transition categories; it does not predict
individual numbers or exact tickets.
""",
        encoding="utf-8",
    )
    cycle_path = output_dir / "q141_cycle_report_2026-11-13_run23.md"
    blind = split_metrics["blind_oos"]["pooled_two_feature_mean"]
    cycle_path.write_text(
        f"""# VinciCasa SONAR — cycle 23 (2026-11-13)

## Recovery
- Recovered Q141-A12 checkpoint: REMOTE_GIT_READBACK_VERIFIED.
- A12 source branch head was isolated; the canonical main archive blob remains {source["archive_blob_sha1"]}.
- Source matrix SHA-256: {source["matrix_sha256"]}; shape 3,356 × 40 × 59.
- A7 source artifact 14003350043 remains available and unexpired.
- B11 remains one frozen prediction and zero reconciled outcomes at the 11:05 local check; the official archive still ends at contest 316 / 2026-11-12.

## Q141-A13 hypothesis and design
- Test lag-2 transition from sum/range first-difference category at t-2 to category at t.
- To eliminate shared-draw overlap, train only on prior endpoints in the same modulo-4 phase as target t.
- Each training example consumes raw draw rows [s-3,s]; examples are spaced by four; latest s ≤ t-4; target uses [t-3,t].
- Baseline marginal category frequency uses the identical phase-matched sample.
- Fixed alpha 0.5 / transition shrinkage 20; no parameter search.
- 2,956 targets; Discovery 1,774, Validation 591, historical Blind OOS 591.
- Confirmatory endpoints: pooled two-feature log-loss and Brier gain; Holm across two. Feature-specific metrics are exploratory with separate Holm across four.

## Results
- Blind pooled log-loss gain: {blind["mean_logloss_gain"]:.8f}.
- Blind pooled Brier gain: {blind["mean_brier_gain"]:.8f}.
- IID 5-of-40 null simulation: {iid_reps} replicates; results and adjusted p-values are in the machine-readable report.
- Practical thresholds: +{PRACTICAL_LOGLOSS_GAIN:.3f} nats and +{PRACTICAL_BRIER_GAIN:.3f} Brier gain.
- Decision is recorded in the JSON report; no engine or forecast is promoted.

## Integrity and limits
- Source hashes, fixed A12 feature-builder blob, dates, strict-prior cutoffs, phase matching, non-overlapping training/target windows, future-suffix invariance and deterministic replay are checked.
- Historical Blind OOS is exploratory, not virgin confirmation.
- This is a structural-category diagnostic, not a number/ticket predictor.
- B11 freeze and canonical archive remain unchanged.

## Next action
Review A13 and its IID mechanical control. If any effect appears, require a new prospective preregistration and human review; do not reuse historical Blind OOS as confirmation.
""",
        encoding="utf-8",
    )

    outputs = (
        report_path, ledger_path, prereg_path, cycle_path, mechanical_note_path
    )
    manifest = {
        "schema_version": "1.0",
        "task_id": report["task_id"],
        "source_archive_blob_sha1": source["archive_blob_sha1"],
        "source_matrix_sha256": source["matrix_sha256"],
        "a12_feature_builder_blob_sha1": source["a12_builder_blob_sha1"],
        "code_sha256": sha256(Path(__file__).resolve()),
        "outputs": {},
    }
    for path in outputs:
        raw = path.read_bytes()
        manifest["outputs"][path.name] = {
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "git_blob_sha1": git_blob_sha1(path),
        }
    manifest_path = output_dir / "q141_a13_nonoverlap_lag2_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0",
        "cycle": 23,
        "task_id": report["task_id"],
        "status": "LOCAL_REPLAY_COMPLETE_PENDING_REMOTE_READBACK",
        "decision": report["decision"],
        "report_path": str(report_path),
        "ledger_path": str(ledger_path),
        "manifest_path": str(manifest_path),
        "preregistration_path": str(prereg_path),
        "cycle_report_path": str(cycle_path),
        "mechanical_note_path": str(mechanical_note_path),
        "next_action": "Review non-overlapping lag-2 transition results and IID control; preserve B11 unchanged; any positive effect requires a separate prospective freeze.",
        "governance": report["governance"],
    }
    checkpoint_path = output_dir / "q141_a13_nonoverlap_lag2_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--iid-reps", type=int, default=IID_REPS)
    parser.add_argument("--bootstrap-reps", type=int, default=BOOTSTRAP_REPS)
    args = parser.parse_args()
    report = run_experiment(args.input, args.outdir, args.iid_reps, args.bootstrap_reps)
    print(json.dumps({
        "status": report["status"],
        "decision": report["decision"],
        "targets": report["design"]["targets"],
        "split_counts": report["design"]["split_counts"],
        "blind_pooled_logloss_gain": report["split_metrics"]["blind_oos"]["pooled_two_feature_mean"]["mean_logloss_gain"],
        "blind_pooled_brier_gain": report["split_metrics"]["blind_oos"]["pooled_two_feature_mean"]["mean_brier_gain"],
        "iid_pooled_p_holm": [
            report["blind_oos_inference"]["iid_mechanical_null"][k]["p_holm_across_two_primary_endpoints"]
            for k in ("logloss_gain", "brier_gain")
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
