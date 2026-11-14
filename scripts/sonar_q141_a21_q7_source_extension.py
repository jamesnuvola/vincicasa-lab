#!/usr/bin/env python3
"""Q141-A21 append-only Q7 source extension and prior-only next-target monitor."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from datetime import date
from pathlib import Path

import numpy as np

import sonar_q141_a17_full_universe_spectral as a17
import sonar_q141_a18_mask_lattice_residual as a18
import sonar_q141_a19_residual_subspace_drift as a19
import sonar_q141_a20_drift_quantile_state as a20

DATE = "2026-11-14"
PREFIX = f"q141_a21_q7_source_extension_{DATE}"
EXPECTED_OLD_DRAWS = 3387
EXPECTED_CURRENT_DRAWS = 3407
EXPECTED_EXTENSION_ROWS = 20
EXPECTED_OLD_TARGETS = 3386
EXPECTED_A19_ROWS = 2186
WINDOW = 400
K = 6
MIN_STATE = 25
QUANTILE = 0.75
PRACTICAL_GAIN = 0.001
MAIN_SOURCE_COMMIT = "0a376c60dc4c33761d3807d59aebf90d3026980a"
Q7_HEAD = "7a37cab601c5f9386131a00246963f8e4aeabf74"


def lower_quantile(values, q=QUANTILE):
    x = np.sort(np.asarray(values, dtype=np.float64))
    if x.ndim != 1 or len(x) < 1 or not np.isfinite(x).all():
        raise ValueError("A21_BLOCKED: quantile requires finite non-empty vector")
    return float(x[math.floor((len(x) - 1) * q)])


def forecast_next_state(prior_drift, prior_capture, next_drift):
    d = np.asarray(prior_drift, dtype=np.float64)
    c = np.asarray(prior_capture, dtype=np.float64)
    if d.shape != c.shape or d.ndim != 1 or len(d) < WINDOW:
        raise ValueError("A21_BLOCKED: next-state forecast requires 400 matched prior pairs")
    if not np.isfinite(d[-WINDOW:]).all() or not np.isfinite(c[-WINDOW:]).all() or not math.isfinite(float(next_drift)):
        raise ValueError("A21_BLOCKED: non-finite prior or next drift")
    x = d[-WINDOW:]
    y = c[-WINDOW:]
    threshold = lower_quantile(x)
    high = float(next_drift) >= threshold
    selected = y[(x >= threshold) == high]
    fallback = len(selected) < MIN_STATE
    prediction = float(np.mean(y if fallback else selected))
    return {
        "prediction": min(1.0, max(0.0, prediction)),
        "threshold": threshold,
        "state": "high" if high else "low",
        "prior_high_count": int(np.sum(x >= threshold)),
        "prior_low_count": int(np.sum(x < threshold)),
        "selected_count": int(len(selected)),
        "fallback": bool(fallback),
    }


def forecast_next_ols(prior_drift, prior_capture, next_drift):
    x = np.asarray(prior_drift, dtype=np.float64)[-WINDOW:]
    y = np.asarray(prior_capture, dtype=np.float64)[-WINDOW:]
    if x.shape != (WINDOW,) or y.shape != (WINDOW,) or not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("A21_BLOCKED: OLS forecast requires 400 finite prior pairs")
    xm = float(x.mean())
    ym = float(y.mean())
    centered = x - xm
    denominator = float(np.dot(centered, centered))
    slope = 0.0 if denominator <= 1e-14 else float(np.dot(centered, y - ym) / denominator)
    prediction = float(np.clip(ym + slope * (float(next_drift) - xm), 0.0, 1.0))
    return {
        "prediction": prediction,
        "slope": slope,
        "prior_mean400": ym,
        "prior_mean20": float(y[-20:].mean()),
        "prior_drift_mean400": xm,
    }


def read_extension(path, current_dates, current_draws):
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        expected = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + [
            f"rank_mask_{i:04d}" for i in range(1, a17.FORMULAS + 1)
        ]
        if reader.fieldnames != expected:
            raise ValueError("A21_BLOCKED: extension rank header/order mismatch")
        for row in reader:
            rows.append(row)
    if len(rows) != EXPECTED_EXTENSION_ROWS:
        raise ValueError(f"A21_BLOCKED: expected 20 extension rows, got {len(rows)}")
    rank_matrix = np.empty((len(rows), a17.FORMULAS), dtype=np.int32)
    metadata = []
    for j, row in enumerate(rows):
        archive_index = EXPECTED_OLD_DRAWS + j
        target_index = int(row["prior_draws"])
        target = tuple(int(v) for v in row["actual_quintet"].split())
        expected_actual = current_draws[archive_index]
        if target_index != archive_index:
            raise ValueError(f"A21_BLOCKED: prior_draws/index mismatch at extension row {j}")
        if row["status"] != "SCORED":
            raise ValueError(f"A21_BLOCKED: unscored extension row at {row['target_date']}")
        if row["target_date"] != current_dates[archive_index]:
            raise ValueError(f"A21_BLOCKED: target date mismatch at {row['target_date']}")
        if row["cutoff_date"] != current_dates[archive_index - 1]:
            raise ValueError(f"A21_BLOCKED: cutoff mismatch at {row['target_date']}")
        if not row["cutoff_date"] < row["target_date"]:
            raise ValueError(f"A21_BLOCKED: non-strict cutoff at {row['target_date']}")
        if target != expected_actual:
            raise ValueError(f"A21_BLOCKED: actual quintet mismatch at {row['target_date']}")
        values = np.fromiter(
            (int(row[f"rank_mask_{i:04d}"]) for i in range(1, a17.FORMULAS + 1)),
            dtype=np.int32,
            count=a17.FORMULAS,
        )
        if values.shape != (a17.FORMULAS,) or np.any(values < 1) or np.any(values > a17.CANDIDATES):
            raise ValueError(f"A21_BLOCKED: invalid rank range at {row['target_date']}")
        rank_matrix[j] = values
        metadata.append({
            "target_index": target_index,
            "target_date": row["target_date"],
            "cutoff_date": row["cutoff_date"],
            "prior_draws": target_index,
            "actual_quintet": " ".join(map(str, target)),
        })
    return rank_matrix, metadata, rows


def read_a19_rows(path):
    rows, raw = a20.load_rows(path)
    if len(rows) != EXPECTED_A19_ROWS:
        raise ValueError("A21_BLOCKED: A19 source row count mismatch")
    if [r["target_index"] for r in rows] != list(range(1201, 3387)):
        raise ValueError("A21_BLOCKED: A19 target index sequence mismatch")
    return rows, raw


def reproduce_a20_historical(rows, a20_report):
    drift = [r["drift"] for r in rows]
    capture = [r["capture"] for r in rows]
    predictions = [None] * len(rows)
    for t in range(WINDOW, len(rows)):
        predictions[t] = a20.forecast_at(drift, capture, t)["prediction"]
    replay = {}
    for split in a20.SPLITS:
        selected = [(i, r) for i, r in enumerate(rows) if r["split"] == split and predictions[i] is not None]
        if not selected:
            raise ValueError(f"A21_BLOCKED: no scored historical rows for {split}")
        gain400 = []
        gain_a19 = []
        for i, r in selected:
            y = r["capture"]
            p = predictions[i]
            b = r["baseline_mean400"]
            a = r["model_prediction"]
            gain400.append((y - b) ** 2 - (y - p) ** 2)
            gain_a19.append((y - a) ** 2 - (y - p) ** 2)
        actual = a20_report["split_metrics"][split]
        g400 = float(np.mean(gain400))
        ga19 = float(np.mean(gain_a19))
        if abs(g400 - actual["mse_gain_vs_mean400"]) > 1e-10:
            raise ValueError(f"A21_BLOCKED: A20 historical replay mismatch vs mean400 in {split}")
        if abs(ga19 - actual["mse_gain_vs_a19_ols"]) > 1e-10:
            raise ValueError(f"A21_BLOCKED: A20 historical replay mismatch vs A19 in {split}")
        replay[split] = {
            "targets": len(selected),
            "mse_gain_vs_mean400_replayed": g400,
            "mse_gain_vs_a19_ols_replayed": ga19,
            "a20_report_mse_gain_vs_mean400": actual["mse_gain_vs_mean400"],
            "a20_report_mse_gain_vs_a19_ols": actual["mse_gain_vs_a19_ols"],
            "holm_tests_inherited_from_a20": [
                x for x in a20_report["registered_tests"] if x["key"].startswith(split + "_")
            ],
            "historical_inference_reused_not_retested": True,
        }
    return replay


def next_target_drift(projected):
    x = np.asarray(projected, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < 2 * WINDOW:
        raise ValueError("A21_BLOCKED: insufficient projected history for next drift")
    old_basis, _ = a19.fit_basis(x[-2 * WINDOW:-WINDOW], K)
    recent_basis, _ = a19.fit_basis(x[-WINDOW:], K)
    value = 1.0 - a18.subspace_overlap(old_basis, recent_basis)
    return float(np.clip(value, 0.0, 1.0))


def run(source_dir, extension_path, a19_path, a20_report_path, current_archive, out_dir, freeze_at):
    source_dir = Path(source_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    current_archive = Path(current_archive)

    old_matrix, old_dates, old_cutoffs, old_actuals, formulas, q7_lineage = a17.load_sources(source_dir)
    current_dates, current_draws = a17.read_archive(current_archive)
    old_dates_archive, old_draws_archive = a17.read_archive(source_dir / "data/storico_daily.csv")
    if len(old_dates_archive) != EXPECTED_OLD_DRAWS or len(old_matrix) != EXPECTED_OLD_TARGETS:
        raise ValueError("A21_BLOCKED: old Q7 source dimensions mismatch")
    if len(current_dates) != EXPECTED_CURRENT_DRAWS or current_dates[-1] != "2026-11-13":
        raise ValueError("A21_BLOCKED: pinned main archive is not the expected 3,407-draw source")
    if current_dates[:EXPECTED_OLD_DRAWS] != old_dates_archive or current_draws[:EXPECTED_OLD_DRAWS] != old_draws_archive:
        raise ValueError("A21_BLOCKED: current archive does not preserve the complete Q7 prefix")
    if old_dates[-1] != "2026-10-24" or old_cutoffs[-1] >= old_dates[-1]:
        raise ValueError("A21_BLOCKED: old Q7 terminal date/cutoff mismatch")

    new_ranks, extension_meta, extension_rows = read_extension(extension_path, current_dates, current_draws)
    if new_ranks.shape != (EXPECTED_EXTENSION_ROWS, a17.FORMULAS):
        raise ValueError("A21_BLOCKED: extension rank matrix shape mismatch")
    ranks = np.vstack((old_matrix, new_ranks))
    if ranks.shape != (EXPECTED_CURRENT_DRAWS - 1, a17.FORMULAS):
        raise ValueError("A21_BLOCKED: combined rank matrix shape mismatch")

    a19_rows, a19_raw = read_a19_rows(a19_path)
    a20_report_raw = Path(a20_report_path).read_bytes()
    a20_report = json.loads(a20_report_raw)
    if a20_report.get("experiment_id") != "Q141-A20" or a20_report.get("decision") != "DRIFT_Q75_STATE_CAPTURE_SKILL_NOT_CONFIRMED":
        raise ValueError("A21_BLOCKED: unexpected A20 reference report")
    historical_replay = reproduce_a20_historical(a19_rows, a20_report)

    standardized, train_means, train_scales = a17.row_center_and_scale(ranks, a17.WARMUP)
    _, mask_q, mask_meta = a18.build_mask_design(formulas)
    residual = a18.residualize_rows(standardized, mask_q)
    complement, cross_error, complement_error = a19.build_residual_complement(mask_q)
    coordinates = residual @ complement
    reconstruction_error = float(np.max(np.abs(coordinates @ complement.T - residual)))
    if coordinates.shape != (EXPECTED_CURRENT_DRAWS - 1, 967) or reconstruction_error > 1e-9:
        raise ValueError("A21_BLOCKED: residual complement reconstruction failed")
    projection, projection_error = a19.build_projection(coordinates.shape[1], a19.SKETCH_DIM, a19.SKETCH_SEED)
    projected = coordinates @ projection
    if projected.shape != (EXPECTED_CURRENT_DRAWS - 1, a19.SKETCH_DIM):
        raise ValueError("A21_BLOCKED: projected source dimensions mismatch")

    # Reproduce the last A19 row before appending any new response.
    terminal_t = EXPECTED_OLD_TARGETS - 1
    terminal_drift, terminal_basis = a19.drift_at(projected[:EXPECTED_OLD_TARGETS], terminal_t, WINDOW, K)
    terminal_capture = float(a17.project_capture(projected[terminal_t:terminal_t + 1], terminal_basis)[0])
    terminal_source = a19_rows[-1]
    terminal_reproduced = (
        abs(terminal_drift - terminal_source["drift"]) <= 2e-9
        and abs(terminal_capture - terminal_source["capture"]) <= 2e-9
    )
    if not terminal_reproduced:
        raise ValueError("A21_BLOCKED: appended source does not reproduce A19 terminal drift/capture")

    drift_all = [r["drift"] for r in a19_rows]
    capture_all = [r["capture"] for r in a19_rows]
    extension_ledger = []
    for j, meta in enumerate(extension_meta):
        target_index = meta["target_index"]
        global_t = target_index - 1
        drift_value, recent_basis = a19.drift_at(projected, global_t, WINDOW, K)
        capture_value = float(a17.project_capture(projected[global_t:global_t + 1], recent_basis)[0])
        local_t = len(drift_all)
        drift_for_prediction = np.asarray(drift_all + [drift_value], dtype=np.float64)
        # The current target response is deliberately a placeholder until both forecasts are made.
        capture_for_prediction = np.asarray(capture_all + [0.0], dtype=np.float64)
        q75 = a20.forecast_at(drift_for_prediction, capture_for_prediction, local_t)
        ols = a19.predict_one(drift_for_prediction, capture_for_prediction, local_t, WINDOW)
        baseline400 = float(np.mean(capture_all[-WINDOW:]))
        baseline20 = float(np.mean(capture_all[-20:]))
        # Target-response mutation must not alter either pre-target forecast.
        mutated_capture = capture_for_prediction.copy()
        mutated_capture[local_t] = 1.0
        q75_mutated = a20.forecast_at(drift_for_prediction, mutated_capture, local_t)
        ols_mutated = a19.predict_one(drift_for_prediction, mutated_capture, local_t, WINDOW)
        if abs(q75["prediction"] - q75_mutated["prediction"]) > 1e-14 or abs(ols[0] - ols_mutated[0]) > 1e-14:
            raise ValueError("A21_BLOCKED: current target response leaked into a forecast")
        row = {
            **meta,
            "drift": f"{drift_value:.12f}",
            "capture_response": f"{capture_value:.12f}",
            "a20_q75_prediction": f"{q75['prediction']:.12f}",
            "a19_ols_prediction": f"{ols[0]:.12f}",
            "baseline_mean400": f"{baseline400:.12f}",
            "baseline_mean20": f"{baseline20:.12f}",
            "q75_threshold": f"{q75['threshold']:.12f}",
            "q75_state": q75["state"],
            "q75_selected_prior_count": q75["selected_count"],
            "q75_fallback": str(q75["fallback"]).lower(),
            "mse_gain_q75_vs_mean400": f"{(capture_value-baseline400)**2-(capture_value-q75['prediction'])**2:.12f}",
            "mse_gain_q75_vs_a19_ols": f"{(capture_value-ols[0])**2-(capture_value-q75['prediction'])**2:.12f}",
            "strict_prior": "true",
            "forecast_response_placeholder_mutation_invariant": "true",
        }
        extension_ledger.append(row)
        drift_all.append(drift_value)
        capture_all.append(capture_value)

    if len(drift_all) != EXPECTED_A19_ROWS + EXPECTED_EXTENSION_ROWS:
        raise ValueError("A21_BLOCKED: combined drift/capture sequence length mismatch")

    extension_capture = np.asarray([float(r["capture_response"]) for r in extension_ledger])
    q75_prediction = np.asarray([float(r["a20_q75_prediction"]) for r in extension_ledger])
    ols_prediction = np.asarray([float(r["a19_ols_prediction"]) for r in extension_ledger])
    baseline400 = np.asarray([float(r["baseline_mean400"]) for r in extension_ledger])
    baseline20 = np.asarray([float(r["baseline_mean20"]) for r in extension_ledger])
    gain400 = (extension_capture - baseline400) ** 2 - (extension_capture - q75_prediction) ** 2
    gain20 = (extension_capture - baseline20) ** 2 - (extension_capture - q75_prediction) ** 2
    gain_ols = (extension_capture - ols_prediction) ** 2 - (extension_capture - q75_prediction) ** 2
    high_count = sum(r["q75_state"] == "high" for r in extension_ledger)

    next_drift = next_target_drift(projected)
    next_q75 = forecast_next_state(drift_all, capture_all, next_drift)
    next_ols = forecast_next_ols(drift_all, capture_all, next_drift)
    next_target_date = "2026-11-14"
    cutoff_date = current_dates[-1]
    if not cutoff_date < next_target_date or date.fromisoformat(freeze_at[:10]) != date.fromisoformat(next_target_date):
        raise ValueError("A21_BLOCKED: next-target freeze date/cutoff mismatch")
    freeze = {
        "experiment_id": "Q141-A21",
        "status": "FROZEN_PENDING_TARGET",
        "target_date": next_target_date,
        "cutoff_date": cutoff_date,
        "prior_draws": len(current_draws),
        "frozen_at": freeze_at,
        "forecast_type": "structural-capture response only; not candidate numbers, a quintet ranking, or a win probability",
        "model": {
            "a20_q75_state": {
                **next_q75,
                "window": WINDOW,
                "quantile": QUANTILE,
                "minimum_state_count": MIN_STATE,
            },
            "a19_linear_drift_ols": {
                **next_ols,
                "window": WINDOW,
            },
            "baseline_mean400": float(np.mean(capture_all[-WINDOW:])),
            "baseline_mean20": float(np.mean(capture_all[-20:])),
        },
        "next_pre_target_drift": next_drift,
        "source_last_date": current_dates[-1],
        "source_draw_count": len(current_draws),
        "target_response_included": False,
        "actual_numbers": None,
        "retuning_after_a20": False,
    }

    extension_gain = float(np.mean(gain400))
    decision = (
        "Q75_EXTENSION_GAIN_THRESHOLD_MET_DESCRIPTIVE_ONLY"
        if extension_gain >= PRACTICAL_GAIN
        else "Q75_EXTENSION_GAIN_THRESHOLD_NOT_MET"
    )
    source_lineage = {
        "experiment_id": "Q141-A21",
        "main_source_commit": MAIN_SOURCE_COMMIT,
        "main_archive": {
            "path": "data/storico_daily.csv",
            "git_blob_sha1": a17.git_blob_sha1(current_archive.read_bytes()),
            "sha256": a17.sha256_bytes(current_archive.read_bytes()),
            "draws": len(current_draws),
            "first_date": current_dates[0],
            "last_date": current_dates[-1],
        },
        "q7_source_lineage": q7_lineage,
        "q7_extension_rank_file": {
            "path": str(extension_path),
            "git_blob_sha1": a17.git_blob_sha1(Path(extension_path).read_bytes()),
            "sha256": a17.sha256_bytes(Path(extension_path).read_bytes()),
            "rows": len(extension_rows),
            "first_target_date": extension_meta[0]["target_date"],
            "last_target_date": extension_meta[-1]["target_date"],
        },
        "a19_source_ledger": {
            "path": str(a19_path),
            "git_blob_sha1": a17.git_blob_sha1(a19_raw),
            "sha256": a17.sha256_bytes(a19_raw),
            "rows": len(a19_rows),
        },
        "a20_reference_report": {
            "path": str(a20_report_path),
            "git_blob_sha1": a17.git_blob_sha1(a20_report_raw),
            "sha256": a17.sha256_bytes(a20_report_raw),
        },
    }

    report = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A21",
        "status": "COMPLETED_APPEND_ONLY_Q7_SOURCE_EXTENSION_AND_NEXT_TARGET_FREEZE",
        "decision": decision,
        "hypothesis": {
            "primary": "Without changing the A19/A20 transforms, the appended 20-target Q7 extension retains the A20 q75-state MSE gain of at least 0.001 versus the prior-400 capture mean.",
            "minimum_mse_gain": PRACTICAL_GAIN,
            "observed_mse_gain_vs_mean400": extension_gain,
            "threshold_met": bool(extension_gain >= PRACTICAL_GAIN),
            "registered_before_extension_execution": True,
            "confirmatory_inference_allowed": False,
        },
        "design": {
            "old_q7_draws": EXPECTED_OLD_DRAWS,
            "current_draws": EXPECTED_CURRENT_DRAWS,
            "old_q7_scored_targets": EXPECTED_OLD_TARGETS,
            "appended_targets": EXPECTED_EXTENSION_ROWS,
            "formula_masks": a17.FORMULAS,
            "candidate_universe_size": a17.CANDIDATES,
            "mask_lattice_design_rank": int(mask_meta["design_rank"]),
            "residual_dimensions": int(coordinates.shape[1]),
            "projection_dimensions": int(projected.shape[1]),
            "projection_seed": a19.SKETCH_SEED,
            "a19_prior_window": WINDOW,
            "a20_state_quantile": QUANTILE,
            "a20_minimum_state_count": MIN_STATE,
            "extension_period": [extension_meta[0]["target_date"], extension_meta[-1]["target_date"]],
            "historical_splits": "Original A20 Discovery/Validation/Blind OOS boundaries retained unchanged; no appended row is folded into the old blind split.",
            "extension_inference": "Descriptive only; n=20 is insufficient for confirmatory block inference and no new p-values are reported.",
        },
        "historical_a20_replay": historical_replay,
        "historical_a20_reference": {
            "decision": a20_report["decision"],
            "split_metrics": a20_report["split_metrics"],
            "registered_tests": a20_report["registered_tests"],
            "source_last_date": a20_report["source"]["last_target_date"],
            "note": "Historical split results are replayed against the pinned A19 ledger; Holm-adjusted inference is inherited, not reselected.",
        },
        "extension_metrics": {
            "targets": len(extension_ledger),
            "first_target_date": extension_meta[0]["target_date"],
            "last_target_date": extension_meta[-1]["target_date"],
            "mean_capture_response": float(extension_capture.mean()),
            "mean_drift": float(np.mean([float(r["drift"]) for r in extension_ledger])),
            "q75_high_state_targets": int(high_count),
            "q75_high_state_rate": float(high_count / len(extension_ledger)),
            "mse_q75": float(np.mean((extension_capture - q75_prediction) ** 2)),
            "mse_ols": float(np.mean((extension_capture - ols_prediction) ** 2)),
            "mse_mean400": float(np.mean((extension_capture - baseline400) ** 2)),
            "mse_mean20": float(np.mean((extension_capture - baseline20) ** 2)),
            "mse_gain_q75_vs_mean400": extension_gain,
            "mse_gain_q75_vs_mean20": float(np.mean(gain20)),
            "mse_gain_q75_vs_a19_ols": float(np.mean(gain_ols)),
            "mae_q75": float(np.mean(np.abs(extension_capture - q75_prediction))),
            "mae_mean400": float(np.mean(np.abs(extension_capture - baseline400))),
            "inference": "Descriptive only; no p-value or confidence interval is used to claim validation on 20 rows.",
        },
        "prospective_freeze": {
            "path": f"{PREFIX}_next_target_freeze.json",
            "target_date": next_target_date,
            "cutoff_date": cutoff_date,
            "prior_draws": len(current_draws),
            "frozen_at": freeze_at,
            "next_pre_target_drift": next_drift,
            "a20_q75_state_prediction": next_q75["prediction"],
            "a19_ols_prediction": next_ols["prediction"],
            "baseline_mean400": freeze["model"]["baseline_mean400"],
            "baseline_mean20": freeze["model"]["baseline_mean20"],
            "actual_numbers": None,
        },
        "integrity": {
            "q7_prefix_reconciled": True,
            "extension_rows_strict_prior": True,
            "all_1023_formula_ranks_in_range": True,
            "a19_terminal_drift_capture_reproduced": terminal_reproduced,
            "a20_historical_split_metrics_reproduced": True,
            "residual_complement_reconstruction_max_error": reconstruction_error,
            "mask_complement_cross_orthogonality_max_error": cross_error,
            "mask_complement_orthogonality_max_error": complement_error,
            "sketch_projection_orthogonality_max_error": projection_error,
            "target_response_mutation_invariance": True,
            "next_target_freeze_uses_only_pre_target_data": True,
            "next_target_freeze_contains_no_actual_numbers": freeze["actual_numbers"] is None,
            "replay_byte_identity": "PENDING_DEDICATED_CI",
        },
        "source": source_lineage,
        "limitations": [
            "Only 20 new target profiles extend the Q7 panel; this is a source-extension audit, not a confirmatory OOS sample.",
            "The A20 q75 threshold was selected after reviewing A19; the appended historical period is exposed exploratory evidence.",
            "The six-component/64-dimensional residual sketch is retained unchanged; results remain conditional on the fixed projection seed.",
            "Structural capture is a formula-profile fit statistic, not exact-ticket accuracy or probability of winning.",
            "The Q7 grammar is exhaustive over 1,023 subsets of ten declared families, not over all possible mathematical formulas.",
            "The 14 November freeze forecasts structural capture only and does not replace the 42 candidate shadow forecasts already frozen in main.",
        ],
        "next_action": "Keep A21 research-only. After the official 2026-11-14 result is added to the canonical archive, append its Q7 rank row and evaluate the unchanged structural-capture freeze; do not retune q75 or the 400-row window.",
    }

    ledger_path = out / f"{PREFIX}_extension_target_ledger.csv"
    a17.csv_write(ledger_path, list(extension_ledger[0].keys()), extension_ledger)
    rank_copy_path = out / f"{PREFIX}_q7_rank_extension.csv"
    rank_copy_path.write_bytes(Path(extension_path).read_bytes())
    freeze_path = out / f"{PREFIX}_next_target_freeze.json"
    a17.write_json(freeze_path, freeze)
    lineage_path = out / f"{PREFIX}_source_lineage.json"
    a17.write_json(lineage_path, source_lineage)
    report_path = out / f"{PREFIX}_report.json"
    a17.write_json(report_path, report)

    md = [
        "# Q141-A21 — Q7 Source Extension and Prospective Structural Monitor",
        "",
        f"**Decision:** {decision}",
        "",
        "## Source extension",
        "",
        f"- Q7 prefix: {EXPECTED_OLD_DRAWS} draws through 2026-10-24.",
        f"- Main archive: {len(current_draws)} draws through {current_dates[-1]}.",
        f"- Appended strict-prior rank rows: {len(extension_ledger)} for {extension_meta[0]['target_date']}–{extension_meta[-1]['target_date']}.",
        f"- Formula masks: {a17.FORMULAS}; candidate quintets per target: {a17.CANDIDATES}.",
        "",
        "## Historical Discovery / Validation / Blind OOS",
        "",
        "| Split | N | Q75 MSE gain vs mean400 | Q75 MSE gain vs A19 OLS | Holm p vs mean400 |",
        "|---|---:|---:|---:|---:|",
    ]
    for split in a20.SPLITS:
        old = a20_report["split_metrics"][split]
        test = next(x for x in a20_report["registered_tests"] if x["key"] == split + "_mse_gain_vs_mean400")
        md.append(
            f"| {split} | {historical_replay[split]['targets']} | "
            f"{historical_replay[split]['mse_gain_vs_mean400_replayed']:.6f} | "
            f"{historical_replay[split]['mse_gain_vs_a19_ols_replayed']:.6f} | {test['p_holm']:.6f} |"
        )
    md += [
        "",
        "Historical split metrics are replayed from the pinned A19 ledger. The old split boundaries and Holm family are unchanged.",
        "",
        "## Appended 20-target extension",
        "",
        f"- Mean capture response: {extension_capture.mean():.6f}.",
        f"- Q75 MSE gain vs prior-400 mean: {extension_gain:.6f}.",
        f"- Q75 MSE gain vs prior-20 mean: {np.mean(gain20):.6f}.",
        f"- Q75 MSE gain vs A19 OLS: {np.mean(gain_ols):.6f}.",
        f"- High-drift state: {high_count}/20.",
        "- No p-values or confidence intervals are used for the 20-row extension.",
        "",
        "## Prospective freeze — 2026-11-14",
        "",
        f"- Cutoff: {cutoff_date}; prior draws: {len(current_draws)}.",
        f"- Frozen at: {freeze_at}.",
        f"- Next pre-target drift: {next_drift:.12f}.",
        f"- A20 q75-state structural-capture forecast: {next_q75['prediction']:.12f} ({next_q75['state']}).",
        f"- A19 OLS structural-capture forecast: {next_ols['prediction']:.12f}.",
        f"- Prior-400 mean baseline: {freeze['model']['baseline_mean400']:.12f}.",
        "- No candidate numbers or actual target response are included.",
        "",
        "## Integrity and limitations",
        "",
        "- Q7 archive prefix and all 1,023 rank masks reconciled.",
        "- Every appended target uses the immediately preceding archive prefix; cutoff is strictly earlier.",
        "- The terminal A19 drift/capture pair is reproduced before appending new rows.",
        "- Historical A20 Discovery/Validation/Blind OOS metrics are replayed and matched to the pinned report.",
        "- Mutating the current target response placeholder does not change either forecast.",
        "- The 20-row extension is descriptive, not confirmatory; historical Blind OOS is not virgin evidence.",
        "",
        "## Next action",
        "",
        report["next_action"],
    ]
    md_path = out / f"{PREFIX}_report.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    checkpoint = {
        "experiment_id": "Q141-A21",
        "status": "COMPUTED_PENDING_DEDICATED_CI",
        "decision": decision,
        "main_source_commit": MAIN_SOURCE_COMMIT,
        "q7_source_commit": Q7_HEAD,
        "source_draws": len(current_draws),
        "source_last_date": current_dates[-1],
        "appended_targets": len(extension_ledger),
        "extension_first_date": extension_meta[0]["target_date"],
        "extension_last_date": extension_meta[-1]["target_date"],
        "prospective_freeze_target": next_target_date,
        "prospective_freeze_cutoff": cutoff_date,
        "replay_verified": False,
        "remote_readback": None,
        "next_action": "Run focused tests, deterministic replay, remote readback, and create a draft research PR only after CI succeeds.",
    }
    checkpoint_path = out / f"{PREFIX}_checkpoint.json"
    a17.write_json(checkpoint_path, checkpoint)

    script_path = Path(__file__)
    protocol_path = Path("reports/sequence_agent") / f"{PREFIX}_protocol.md"
    manifest_paths = [
        report_path, md_path, ledger_path, rank_copy_path, freeze_path,
        lineage_path, checkpoint_path, protocol_path, script_path,
    ]
    manifest = {
        "experiment_id": "Q141-A21",
        "status": "COMPUTED_PENDING_DEDICATED_CI",
        "outputs": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": a17.sha256_bytes(p.read_bytes()),
                "git_blob_sha1": a17.git_blob_sha1(p.read_bytes()),
            }
            for p in manifest_paths
        },
    }
    manifest_path = out / f"{PREFIX}_manifest.json"
    a17.write_json(manifest_path, manifest)
    print("Q141_A21_REPORT_READY " + json.dumps({
        "decision": decision,
        "extension_targets": len(extension_ledger),
        "extension_q75_mse_gain_vs_mean400": extension_gain,
        "next_target": next_target_date,
        "next_q75_state": next_q75["state"],
        "next_q75_prediction": next_q75["prediction"],
    }, sort_keys=True))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--extension-ledger", required=True)
    parser.add_argument("--a19-ledger", required=True)
    parser.add_argument("--a20-report", required=True)
    parser.add_argument("--current-archive", required=True)
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    parser.add_argument("--freeze-at", required=True)
    args = parser.parse_args()
    run(
        args.source_dir, args.extension_ledger, args.a19_ledger,
        args.a20_report, args.current_archive, args.out_dir, args.freeze_at
    )


if __name__ == "__main__":
    main()
