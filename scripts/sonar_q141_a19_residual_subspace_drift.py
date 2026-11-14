#!/usr/bin/env python3
"""Q141-A19: prequential residual-subspace drift as a forecast of next-profile capture."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from sonar_q141_a17_full_universe_spectral import (
    FORMULAS, TARGETS, WARMUP, block_bootstrap_ci, csv_write,
    fit_basis, git_blob_sha1, holm_adjust, load_sources, project_capture,
    row_center_and_scale, sha256_bytes, write_json,
)
from sonar_q141_a18_mask_lattice_residual import (
    build_mask_design, residualize_rows, subspace_overlap,
)

DATE = "2026-11-14"
OUT_PREFIX = f"q141_a19_residual_subspace_drift_{DATE}"
Q7_HEAD = "7a37cab601c5f9386131a00246963f8e4aeabf74"
K = 6
WINDOW = 400
SKETCH_DIM = 64
SKETCH_SEED = 1419001
NULL_REPLICATES = 999
BOOTSTRAP_REPLICATES = 20000
BLOCK = 20
SIGNFLIP_REPLICATES = 20000
SEED_NULL = 1419002
SEED_BOOTSTRAP = 1419003
SEED_SIGNFLIP = 1419004
PRACTICAL_MSE_GAIN = 0.001
SPLIT_NAMES = ("discovery", "validation", "blind_oos")


def build_projection(input_dim: int, sketch_dim: int = SKETCH_DIM, seed: int = SKETCH_SEED):
    if input_dim < sketch_dim or sketch_dim < K:
        raise ValueError("A19_BLOCKED: invalid projection dimensions")
    rng = np.random.default_rng(seed)
    gaussian = rng.standard_normal((input_dim, sketch_dim))
    q, _ = np.linalg.qr(gaussian, mode="reduced")
    for j in range(q.shape[1]):
        pivot = int(np.argmax(np.abs(q[:, j])))
        if q[pivot, j] < 0:
            q[:, j] *= -1.0
    error = float(np.max(np.abs(q.T @ q - np.eye(sketch_dim))))
    if error > 1e-11:
        raise ValueError(f"A19_BLOCKED: sketch projection is not orthonormal ({error})")
    return q, error


def drift_at(projected: np.ndarray, target_index: int, window: int = WINDOW, k: int = K):
    x = np.asarray(projected, dtype=np.float64)
    t = int(target_index)
    if x.ndim != 2 or t < 2 * window or t >= x.shape[0]:
        raise ValueError("A19_BLOCKED: drift target lacks two strictly prior windows")
    old_basis, _ = fit_basis(x[t - 2 * window:t - window], k)
    recent_basis, _ = fit_basis(x[t - window:t], k)
    drift = 1.0 - subspace_overlap(old_basis, recent_basis)
    return float(np.clip(drift, 0.0, 1.0)), recent_basis


def compute_drift_capture(projected: np.ndarray, window: int = WINDOW, k: int = K):
    x = np.asarray(projected, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] <= 3 * window:
        raise ValueError("A19_BLOCKED: insufficient projected target history")
    drift = np.full(x.shape[0], np.nan, dtype=np.float64)
    capture = np.full(x.shape[0], np.nan, dtype=np.float64)
    for t in range(2 * window, x.shape[0]):
        value, recent_basis = drift_at(x, t, window, k)
        drift[t] = value
        capture[t] = float(project_capture(x[t:t + 1], recent_basis)[0])
        if (t + 1) % 250 == 0:
            print(f"A19_PREQUENTIAL_PROGRESS {t + 1}/{x.shape[0]}", flush=True)
    return drift, capture


def predict_one(drift: np.ndarray, capture: np.ndarray, target_index: int, window: int = WINDOW):
    t = int(target_index)
    x_train = np.asarray(drift[t - window:t], dtype=np.float64)
    y_train = np.asarray(capture[t - window:t], dtype=np.float64)
    x_now = float(drift[t])
    if x_train.shape != (window,) or y_train.shape != (window,):
        raise ValueError("A19_BLOCKED: rolling regression window shape mismatch")
    if not np.isfinite(x_train).all() or not np.isfinite(y_train).all() or not math.isfinite(x_now):
        raise ValueError("A19_BLOCKED: non-finite prior feature or label")
    x_mean = float(x_train.mean())
    y_mean = float(y_train.mean())
    x_centered = x_train - x_mean
    denominator = float(np.dot(x_centered, x_centered))
    if denominator <= 1e-14:
        slope = 0.0
    else:
        slope = float(np.dot(x_centered, y_train - y_mean) / denominator)
    prediction = float(np.clip(y_mean + slope * (x_now - x_mean), 0.0, 1.0))
    baseline_400 = y_mean
    baseline_20 = float(y_train[-20:].mean())
    return prediction, baseline_400, baseline_20, slope, x_mean


def rolling_predictions(drift: np.ndarray, capture: np.ndarray, start: int, window: int = WINDOW):
    n = len(drift)
    prediction = np.full(n, np.nan, dtype=np.float64)
    baseline_400 = np.full(n, np.nan, dtype=np.float64)
    baseline_20 = np.full(n, np.nan, dtype=np.float64)
    slope = np.full(n, np.nan, dtype=np.float64)
    x_mean = np.full(n, np.nan, dtype=np.float64)
    for t in range(int(start), n):
        values = predict_one(drift, capture, t, window)
        prediction[t], baseline_400[t], baseline_20[t], slope[t], x_mean[t] = values
    return prediction, baseline_400, baseline_20, slope, x_mean


def block_signflip_p(values, seed: int, replicates: int = SIGNFLIP_REPLICATES, block: int = BLOCK):
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or len(x) == 0 or not np.isfinite(x).all():
        raise ValueError("A19_BLOCKED: sign-flip input must be a finite non-empty vector")
    block_sums = np.asarray([x[i:i + block].sum() for i in range(0, len(x), block)], dtype=np.float64)
    rng = np.random.default_rng(seed)
    signs = rng.integers(0, 2, size=(replicates, len(block_sums)), dtype=np.int8) * 2 - 1
    null_means = (signs @ block_sums) / len(x)
    observed = float(x.mean())
    p_value = float((1 + np.sum(null_means >= observed)) / (replicates + 1))
    return p_value, observed, int(len(block_sums))


def safe_corr(x: np.ndarray, y: np.ndarray):
    a = np.asarray(x, dtype=np.float64)
    b = np.asarray(y, dtype=np.float64)
    if len(a) != len(b) or len(a) < 3 or np.std(a) <= 1e-14 or np.std(b) <= 1e-14:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def circular_shift_corr_null(drift_values, capture_values, seed: int, replicates: int = NULL_REPLICATES):
    x = np.asarray(drift_values, dtype=np.float64)
    y = np.asarray(capture_values, dtype=np.float64)
    if len(x) != len(y) or len(x) < 50:
        raise ValueError("A19_BLOCKED: correlation null requires matched series of length >= 50")
    observed = safe_corr(x, y)
    rng = np.random.default_rng(seed)
    low = max(20, int(len(x) * 0.05))
    high = len(x) - low
    if high <= low:
        raise ValueError("A19_BLOCKED: no admissible circular shifts")
    null = np.empty(replicates, dtype=np.float64)
    for b in range(replicates):
        shift = int(rng.integers(low, high))
        null[b] = safe_corr(np.roll(x, shift), y)
    p_value = float((1 + np.sum(np.abs(null) >= abs(observed))) / (replicates + 1))
    return observed, null, p_value


def split_ranges(n: int, start: int):
    evaluated = n - start
    discovery = int(math.floor(evaluated * 0.60))
    validation = int(math.floor(evaluated * 0.20))
    blind = evaluated - discovery - validation
    ranges = {
        "discovery": slice(start, start + discovery),
        "validation": slice(start + discovery, start + discovery + validation),
        "blind_oos": slice(start + discovery + validation, n),
    }
    counts = {name: sl.stop - sl.start for name, sl in ranges.items()}
    if sum(counts.values()) != evaluated or any(v <= 0 for v in counts.values()):
        raise ValueError("A19_BLOCKED: invalid chronological split")
    return ranges, counts


def verify_future_invariance(projected, drift, capture, probe_indices, window=WINDOW):
    x = np.asarray(projected, dtype=np.float64)
    d = np.asarray(drift, dtype=np.float64)
    y = np.asarray(capture, dtype=np.float64)
    checks = []
    for t in probe_indices:
        original_drift, _ = drift_at(x, int(t), window, K)
        mutated = x.copy()
        rng = np.random.default_rng(SEED_SKETCH + int(t))
        mutated[int(t):] = rng.normal(loc=50.0, scale=7.0, size=mutated[int(t):].shape)
        changed_drift, _ = drift_at(mutated, int(t), window, K)
        if not np.isclose(original_drift, changed_drift, rtol=0.0, atol=1e-13):
            return False, checks
        original_prediction = predict_one(d, y, int(t), window)[0]
        changed_drift_series = d.copy()
        changed_capture_series = y.copy()
        changed_drift_series[int(t) + 1:] = 0.123456
        changed_capture_series[int(t):] = 0.987654
        changed_prediction = predict_one(changed_drift_series, changed_capture_series, int(t), window)[0]
        if not np.isclose(original_prediction, changed_prediction, rtol=0.0, atol=1e-13):
            return False, checks
        checks.append({"target_index_zero_based": int(t), "drift_unchanged": True, "prediction_unchanged": True})
    return True, checks


def build_report(source_dir: Path, out: Path):
    ranks, dates, cutoffs, actuals, formulas, lineage = load_sources(source_dir)
    if ranks.shape != (TARGETS, FORMULAS) or not np.isfinite(ranks).all():
        raise SystemExit("A19_BLOCKED: source rank matrix shape/finite check failed")

    design, mask_q, mask_meta = build_mask_design(formulas)
    standardized, train_means, train_scales = row_center_and_scale(ranks, WARMUP)
    residual = residualize_rows(standardized, mask_q)
    residual_orthogonality = float(np.max(np.abs(residual @ mask_q)))
    if residual_orthogonality > 1e-9:
        raise SystemExit(f"A19_BLOCKED: mask residual orthogonality error {residual_orthogonality}")

    projection, projection_error = build_projection(residual.shape[1], SKETCH_DIM, SKETCH_SEED)
    projected = residual @ projection
    if projected.shape != (TARGETS, SKETCH_DIM):
        raise SystemExit("A19_BLOCKED: projected residual shape mismatch")

    drift, capture = compute_drift_capture(projected, WINDOW, K)
    evaluation_start = 3 * WINDOW
    ranges, counts = split_ranges(TARGETS, evaluation_start)
    prediction, baseline_400, baseline_20, slopes, x_means = rolling_predictions(
        drift, capture, evaluation_start, WINDOW
    )
    if not np.isfinite(prediction[evaluation_start:]).all():
        raise SystemExit("A19_BLOCKED: non-finite prequential predictions")

    probes = [evaluation_start, evaluation_start + (TARGETS - evaluation_start) // 2, TARGETS - 1]
    future_invariance, invariance_checks = verify_future_invariance(
        projected, drift, capture, probes, WINDOW
    )
    if not future_invariance:
        raise SystemExit("A19_BLOCKED: future suffix altered a pre-target drift or prediction")

    raw_p = []
    p_keys = []
    split_metrics = {}
    null_rows = []
    null_series = {}
    for split_index, name in enumerate(SPLIT_NAMES):
        sl = ranges[name]
        idx = np.arange(sl.start, sl.stop, dtype=np.int64)
        d = drift[sl]
        y = capture[sl]
        pred = prediction[sl]
        b400 = baseline_400[sl]
        b20 = baseline_20[sl]
        gain400 = (y - b400) ** 2 - (y - pred) ** 2
        gain20 = (y - b20) ** 2 - (y - pred) ** 2
        metrics = {
            "targets": int(len(idx)),
            "first_target_date": dates[int(idx[0])],
            "last_target_date": dates[int(idx[-1])],
            "mean_drift": float(d.mean()),
            "sd_drift": float(d.std(ddof=1)),
            "mean_realized_capture": float(y.mean()),
            "mean_predicted_capture": float(pred.mean()),
            "drift_capture_pearson": safe_corr(d, y),
            "mse_model": float(np.mean((y - pred) ** 2)),
            "mse_rolling_mean_400": float(np.mean((y - b400) ** 2)),
            "mse_rolling_mean_20": float(np.mean((y - b20) ** 2)),
            "mae_model": float(np.mean(np.abs(y - pred))),
            "mae_rolling_mean_400": float(np.mean(np.abs(y - b400))),
            "mae_rolling_mean_20": float(np.mean(np.abs(y - b20))),
            "mse_gain_vs_rolling_mean_400": float(gain400.mean()),
            "mse_gain_vs_rolling_mean_20": float(gain20.mean()),
            "bootstrap_95_ci_gain_vs_mean_400_block20": block_bootstrap_ci(
                gain400, SEED_BOOTSTRAP + split_index, BOOTSTRAP_REPLICATES, BLOCK
            ),
            "bootstrap_95_ci_gain_vs_mean_20_block20": block_bootstrap_ci(
                gain20, SEED_BOOTSTRAP + 10 + split_index, BOOTSTRAP_REPLICATES, BLOCK
            ),
        }
        if name in ("validation", "blind_oos"):
            p400, observed400, blocks400 = block_signflip_p(
                gain400, SEED_SIGNFLIP + split_index, SIGNFLIP_REPLICATES, BLOCK
            )
            p20, observed20, blocks20 = block_signflip_p(
                gain20, SEED_SIGNFLIP + 10 + split_index, SIGNFLIP_REPLICATES, BLOCK
            )
            corr, corr_null, corr_p = circular_shift_corr_null(
                d, y, SEED_NULL + split_index, NULL_REPLICATES
            )
            metrics.update({
                "signflip_p_gain_vs_mean_400_raw": p400,
                "signflip_blocks_mean_400": blocks400,
                "signflip_p_gain_vs_mean_20_raw": p20,
                "signflip_blocks_mean_20": blocks20,
                "circular_shift_correlation_p_raw": corr_p,
                "circular_shift_correlation_null_mean": float(corr_null.mean()),
                "circular_shift_correlation_null_q99_abs": float(np.quantile(np.abs(corr_null), 0.99)),
            })
            for key, value in (
                (f"{name}_mse_vs_mean400", p400),
                (f"{name}_mse_vs_mean20", p20),
                (f"{name}_drift_capture_corr", corr_p),
            ):
                p_keys.append(key)
                raw_p.append(value)
            null_series[name] = corr_null
        split_metrics[name] = metrics

        for local, global_idx in enumerate(idx):
            t = int(global_idx)
            if cutoffs[t] >= dates[t]:
                raise SystemExit(f"A19_BLOCKED: non-strict cutoff at target index {t + 1}")
            null_rows.append({
                "split": name,
                "target_index": t + 1,
                "target_date": dates[t],
                "drift": f"{drift[t]:.12f}",
                "capture": f"{capture[t]:.12f}",
                "model_prediction": f"{prediction[t]:.12f}",
                "baseline_mean400": f"{baseline_400[t]:.12f}",
                "baseline_mean20": f"{baseline_20[t]:.12f}",
                "model_mse_gain_vs_mean400": f"{gain400[local]:.12f}",
                "model_mse_gain_vs_mean20": f"{gain20[local]:.12f}",
            })

    adjusted = holm_adjust(raw_p)
    p_map = {
        key: {"raw": float(raw_p[i]), "holm": float(adjusted[i])}
        for i, key in enumerate(p_keys)
    }
    primary_pass = all(
        split_metrics[name]["mse_gain_vs_rolling_mean_400"] >= PRACTICAL_MSE_GAIN
        and split_metrics[name]["bootstrap_95_ci_gain_vs_mean_400_block20"][0] > 0.0
        and p_map[f"{name}_mse_vs_mean400"]["holm"] < 0.05
        for name in ("validation", "blind_oos")
    )
    decision = "RESIDUAL_DRIFT_HAS_PREQUENTIAL_CAPTURE_SKILL_EXPLORATORY" if primary_pass else "RESIDUAL_DRIFT_PREDICTIVE_VALUE_NOT_CONFIRMED"

    ledger_rows = []
    for row in null_rows:
        t = int(row["target_index"]) - 1
        ledger_rows.append({
            **row,
            "cutoff_date": cutoffs[t],
            "prior_draws": t + 1,
            "actual_quintet": actuals[t],
            "old_basis_start_index_zero_based": t - 2 * WINDOW,
            "old_basis_end_index_exclusive": t - WINDOW,
            "recent_basis_start_index_zero_based": t - WINDOW,
            "recent_basis_end_index_exclusive": t,
            "model_train_start_index_zero_based": t - WINDOW,
            "model_train_end_index_exclusive": t,
            "model_training_pairs": WINDOW,
            "strict_prior": "true",
        })

    shift_rows = []
    for name, values in null_series.items():
        for i, value in enumerate(values):
            shift_rows.append({
                "split": name,
                "replicate": i + 1,
                "null_pearson_correlation": f"{float(value):.12f}",
            })

    ledger_path = out / f"{OUT_PREFIX}_target_ledger.csv"
    csv_write(ledger_path, list(ledger_rows[0].keys()), ledger_rows)
    null_path = out / f"{OUT_PREFIX}_circular_shift_null.csv"
    csv_write(null_path, ["split", "replicate", "null_pearson_correlation"], shift_rows)
    source_path = out / f"{OUT_PREFIX}_source_lineage.json"
    write_json(source_path, lineage)

    report = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A19",
        "status": "COMPLETED_HISTORICAL_PREQUENTIAL_RESIDUAL_DRIFT_TEST",
        "decision": decision,
        "hypothesis": {
            "primary": "A fixed 64-dimensional deterministic sketch of the A18 mask-residual profiles yields a pre-target subspace-drift statistic that improves one-step-ahead capture MSE over the prior-400 mean by at least 0.001 in both Validation and historical Blind OOS, with positive block-bootstrap lower bounds and Holm-adjusted block-signflip p<0.05.",
            "practical_mse_gain_threshold": PRACTICAL_MSE_GAIN,
            "primary_pass": bool(primary_pass),
        },
        "source": lineage,
        "design": {
            "target_rows": TARGETS,
            "formula_count": FORMULAS,
            "mask_design_rank": int(mask_meta["design_rank"]),
            "mask_residual_dimensions": int(residual.shape[1]),
            "warmup_scaler_rows": WARMUP,
            "subspace_window": WINDOW,
            "model_training_window": WINDOW,
            "projection_dimension": SKETCH_DIM,
            "projection_seed": SKETCH_SEED,
            "projection_sha256": hashlib.sha256(np.asarray(projection, dtype="<f8").tobytes()).hexdigest(),
            "k": K,
            "first_feature_target_index_zero_based": 2 * WINDOW,
            "first_scored_target_index_zero_based": evaluation_start,
            "evaluated_targets": int(TARGETS - evaluation_start),
            "split_counts": counts,
            "null_replicates_per_holdout": NULL_REPLICATES,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_block_length": BLOCK,
            "signflip_replicates": SIGNFLIP_REPLICATES,
            "multiple_testing": "Holm across 6 registered holdout tests: two MSE baselines and one drift/capture circular-shift correlation per holdout",
        },
        "preprocessing": {
            "rank_normalization_and_scaling": "Q7 A17 row_center_and_scale; per-target median centering; column means and sample SDs fit on first 400 targets only",
            "mask_residualization": "Q7 A18 intercept + 10 family main effects + 45 pairwise interactions; fixed known mask design",
            "sketch": "fixed seeded Gaussian matrix orthonormalized by QR; 64-dimensional projection of the 967-dimensional residual profile",
            "drift": "1 - six-dimensional principal-subspace overlap between the two adjacent 400-target windows ending strictly before the target",
            "capture_label": "fraction of the target residual-sketch energy captured by the recent-window six-dimensional basis; used only as the response, never as the same-target predictor",
            "predictor": "ordinary least squares with intercept, fit on the prior 400 (drift, capture) pairs; one fixed feature, no tuning; prediction clipped to [0,1]",
            "baseline_primary": "mean capture over the prior 400 observed target pairs",
            "baseline_secondary": "mean capture over the prior 20 observed target pairs",
        },
        "split_metrics": split_metrics,
        "multiple_testing": p_map,
        "integrity": {
            "source_lineage_verified": True,
            "all_3386_target_rows_loaded_and_reconciled": True,
            "all_1023_formula_masks_loaded_and_reconciled": True,
            "strict_prior_cutoffs": True,
            "drift_windows_end_before_target": True,
            "model_training_pairs_end_before_target": True,
            "current_target_capture_used_only_as_response": True,
            "future_suffix_invariance": bool(future_invariance),
            "future_suffix_probe_checks": invariance_checks,
            "mask_residual_orthogonality_max_error": residual_orthogonality,
            "sketch_projection_orthogonality_max_error": projection_error,
            "deterministic_projection": True,
            "deterministic_null_and_signflip_seeds": True,
            "full_replay_byte_identity": "PENDING_WORKFLOW_REPLAY",
        },
        "interpretation": "A19 tests whether pre-target drift in a compressed residual formula-profile subspace predicts the next target's structural capture score. It does not predict candidate numbers or an exact five-number ticket. Historical Blind OOS is exposed exploratory evidence, not virgin prospective confirmation.",
        "limitations": [
            "The 64-dimensional Gaussian sketch is a fixed approximation to the 967-dimensional residual space; results are conditional on the registered seed and projection.",
            "The 400-row windows overlap heavily, so observations are serially dependent; block bootstrap and block sign-flip are used, but sign-flip inference assumes block-level symmetry.",
            "The circular-shift correlation null preserves the marginal sequence of drift and capture within each holdout but does not preserve all cross-window dependence.",
            "The A19 design follows inspection of A18; historical Blind OOS is not virgin confirmation.",
            "Capture is a structural fit statistic derived from realized formula-rank profiles, not a measure of exact-ticket predictive accuracy.",
            "No production engine, canonical archive, forecast freeze or Q60 gate is modified.",
        ],
    }
    report_path = out / f"{OUT_PREFIX}_report.json"
    write_json(report_path, report)
    md = [
        "# Q141-A19 — Residual Subspace Drift Detection",
        "",
        f"**Decision:** {decision}",
        "",
        "## Frozen quantitative hypothesis",
        "",
        f"Pre-target drift in a fixed {SKETCH_DIM}-dimensional sketch must improve one-step-ahead capture MSE by at least {PRACTICAL_MSE_GAIN:.3f} versus the prior-{WINDOW} mean in both Validation and historical Blind OOS, with positive block-bootstrap lower bounds and Holm-adjusted block-signflip p<0.05.",
        "",
        "## Design",
        "",
        f"- Source: Q7 commit {Q7_HEAD}; {FORMULAS:,} masks and {TARGETS:,} target rows.",
        f"- Mask-lattice residual dimension: {residual.shape[1]}; deterministic sketch dimension: {SKETCH_DIM}; k={K}.",
        f"- Drift: overlap change between adjacent {WINDOW}-target windows, both ending before the target.",
        f"- Prediction: rolling one-feature OLS on the prior {WINDOW} drift/capture pairs.",
        f"- Scored targets: {TARGETS - evaluation_start:,}; splits {counts}.",
        "",
        "## Results",
        "",
        "| Split | Targets | Mean drift | Mean capture | MSE gain vs mean400 | 95% block CI | MSE gain vs mean20 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in SPLIT_NAMES:
        m = split_metrics[name]
        ci = m["bootstrap_95_ci_gain_vs_mean_400_block20"]
        md.append(
            f"| {name} | {m['targets']} | {m['mean_drift']:.6f} | {m['mean_realized_capture']:.6f} | "
            f"{m['mse_gain_vs_rolling_mean_400']:.6f} | [{ci[0]:.6f}, {ci[1]:.6f}] | "
            f"{m['mse_gain_vs_rolling_mean_20']:.6f} |"
        )
    md += [
        "",
        "## Registered holdout tests",
        "",
        "| Test | Raw p | Holm p |",
        "|---|---:|---:|",
    ]
    for key, value in p_map.items():
        md.append(f"| {key} | {value['raw']:.6f} | {value['holm']:.6f} |")
    md += [
        "",
        "## Leakage and reproducibility",
        "",
        "- Both subspace windows end at target index t (exclusive); the target profile is used only as the response.",
        "- The rolling regression uses only the preceding 400 drift/capture pairs.",
        "- Future-suffix mutation checks cover the pre-target drift and prediction at three target indices.",
        "- Full deterministic replay and remote Git readback are delegated to the dedicated workflow.",
        "",
        "## Limitations",
        "",
    ]
    md.extend(f"- {item}" for item in report["limitations"])
    md += ["", "## Next action", "", "Keep A19 research-only. If results are not confirmed, do not tune the sketch seed or windows on this historical panel; instead freeze a prospective drift monitor and evaluate it unchanged."]
    md_path = out / f"{OUT_PREFIX}_report.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    outputs = {}
    for path in (report_path, md_path, ledger_path, null_path, source_path):
        raw = path.read_bytes()
        outputs[path.name] = {"bytes": len(raw), "sha256": sha256_bytes(raw), "git_blob_sha1": git_blob_sha1(raw)}
    manifest = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A19",
        "status": "COMPUTED_PENDING_DEDICATED_CI",
        "branch": "research/q141-a19-residual-subspace-drift-20261114",
        "outputs": outputs,
    }
    manifest_path = out / f"{OUT_PREFIX}_manifest.json"
    write_json(manifest_path, manifest)
    checkpoint = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A19",
        "status": "COMPUTED_PENDING_DEDICATED_CI",
        "decision": decision,
        "q7_head": Q7_HEAD,
        "target_rows": TARGETS,
        "evaluated_targets": TARGETS - evaluation_start,
        "formula_count": FORMULAS,
        "split_counts": counts,
        "replay_verified": False,
        "remote_readback": None,
        "next_action": "Run dedicated replay and readback; then request human review without merge or engine promotion.",
    }
    checkpoint_path = out / f"{OUT_PREFIX}_checkpoint.json"
    write_json(checkpoint_path, checkpoint)
    print("A19_REPORT_READY", json.dumps({"decision": decision, "splits": counts, "outputs": list(outputs)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="q7-source")
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    build_report(Path(args.source_dir), out)


if __name__ == "__main__":
    main()
