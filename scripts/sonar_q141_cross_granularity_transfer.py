#!/usr/bin/env python3
"""Q141-C4: strict-prior transfer from Q80 per-number family state to Q7 quintet-rank quality."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
DATE = "2026-11-12"

PREREG = OUT / "q141_cross_granularity_transfer_preregistration_2026-11-12.json"
PREREG_MD = OUT / "q141_cross_granularity_transfer_preregistration_2026-11-12.md"
C0_REPORT = OUT / "q141_formula_family_behaviour_report_2026-11-12.json"
C0_MANIFEST = OUT / "q141_formula_family_behaviour_manifest_2026-11-12.json"
C0_LEDGER = OUT / "q141_formula_family_behaviour_target_ledger_2026-11-12.csv"
Q7_REPORT = OUT / "q7_formula_complexity_walkforward_report_2026-11-12.json"
Q7_MANIFEST = OUT / "q141_q7_ast_complexity_manifest_2026-11-12.json"
Q7_LEDGER = OUT / "q7_formula_complexity_walkforward_target_ledger_2026-11-12.csv"

REPORT = OUT / "q141_cross_granularity_transfer_report_2026-11-12.json"
LEDGER = OUT / "q141_cross_granularity_transfer_target_ledger_2026-11-12.csv"
MANIFEST = OUT / "q141_cross_granularity_transfer_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_cross_granularity_transfer_checkpoint_2026-11-12.json"

EXPECTED_Q141_ARCHIVE_BLOB = "fcb453ed06c8002314f826dbac79d6935f9ac103"
EXPECTED_Q7_ARCHIVE_BLOB = "7dab05ba49ace909fe8783eef729605049c65e50"
FAMILY_COLUMNS = (
    "frequency_change_top5_hits",
    "frequency_level_top5_hits",
    "lag_memory_top5_hits",
    "neighbour_field_top5_hits",
    "position_dependence_top5_hits",
    "recency_gap_top5_hits",
)
WINDOW = 50
DISCOVERY_END = 1972
VALIDATION_END = 2629
EXPECTED_Q7_ROWS = 3286
EXPECTED_C0_ROWS = 3354
RIDGE_ALPHA = 1.0
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261124
PRACTICAL_THRESHOLD = 0.005

FEATURE_A = ("q7_roll50_mean_percentile",)
FEATURE_B = (
    "q7_roll50_mean_percentile",
    "q80_roll50_equal_family_top5_hits",
    "q80_roll50_family_dispersion",
    "q80_roll50_family_entropy_normalized",
    "q80_equal_family_recent25_minus_previous25",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_sources() -> dict:
    prereg = read_json(PREREG)
    c0_report = read_json(C0_REPORT)
    c0_manifest = read_json(C0_MANIFEST)
    q7_report = read_json(Q7_REPORT)
    q7_manifest = read_json(Q7_MANIFEST)

    if prereg.get("task_id") != "Q141-C4":
        raise RuntimeError("Q141-C4 preregistration task id mismatch")
    if c0_report.get("task_id") != "Q141-C0" or c0_report.get("status") != "EXECUTED_EXPLORATORY":
        raise RuntimeError("Q141-C4 blocked: Q80 C0 report is not the expected completed exploratory bundle")
    if c0_report["source"].get("git_blob_sha1") != EXPECTED_Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q80 C0 source archive identity mismatch")
    if c0_manifest.get("source_archive_git_blob_sha1") != EXPECTED_Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q80 C0 manifest source archive mismatch")
    if c0_report["walkforward"].get("scored_targets") != EXPECTED_C0_ROWS:
        raise RuntimeError("Q141-C4 blocked: unexpected Q80 C0 target count")
    if "index < i" not in c0_report["walkforward"].get("strict_prior", ""):
        raise RuntimeError("Q141-C4 blocked: Q80 C0 strict-prior contract not present")
    if "state update follows target scoring" not in c0_report["walkforward"].get("strict_prior", ""):
        raise RuntimeError("Q141-C4 blocked: Q80 C0 update order not verified")
    c0_ledger_sha = sha256_bytes(C0_LEDGER.read_bytes())
    if c0_ledger_sha != c0_manifest.get("target_ledger_sha256"):
        raise RuntimeError("Q141-C4 blocked: Q80 C0 target ledger SHA-256 mismatch")

    q7_source = q7_report.get("source", {})
    if q7_report.get("task_id") != "Q141-B8" or q7_report.get("status") != "WALKFORWARD_COMPLETE":
        raise RuntimeError("Q141-C4 blocked: Q7 B8 report is not complete")
    if q7_source.get("q7_archive_blob_sha1") != EXPECTED_Q7_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q7 source archive identity mismatch")
    if q7_source.get("q141_archive_blob_sha1") != EXPECTED_Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q7/Q141 archive lineage mismatch")
    if q7_source.get("q7_is_exact_q141_prefix") is not True:
        raise RuntimeError("Q141-C4 blocked: Q7 exact-prefix provenance not verified")
    if q7_report.get("walkforward", {}).get("strict_prior") is not True:
        raise RuntimeError("Q141-C4 blocked: Q7 strict-prior status missing")
    if q7_manifest.get("source_archive_blob_sha1") != EXPECTED_Q7_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q7 manifest source archive mismatch")
    if q7_manifest.get("q141_archive_blob_sha1") != EXPECTED_Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C4 blocked: Q7 manifest Q141 archive mismatch")
    if q7_manifest.get("eligible_targets") != EXPECTED_Q7_ROWS:
        raise RuntimeError("Q141-C4 blocked: Q7 manifest target count mismatch")
    rank_order = q7_manifest.get("runner_order_offsets", {})
    if not (
        rank_order.get("loop_offset", 0)
        < rank_order.get("score_offset", 0)
        < rank_order.get("write_offset", 0)
        < rank_order.get("state_update_offset", 0)
    ):
        raise RuntimeError("Q141-C4 blocked: Q7 runner score/write/update order mismatch")
    q7_ledger_record = q7_manifest.get("files", {}).get(Q7_LEDGER.name)
    if not q7_ledger_record:
        raise RuntimeError("Q141-C4 blocked: Q7 ledger missing from its manifest")
    q7_ledger_sha = sha256_bytes(Q7_LEDGER.read_bytes())
    if q7_ledger_sha != q7_ledger_record.get("sha256"):
        raise RuntimeError("Q141-C4 blocked: Q7 target ledger SHA-256 mismatch")

    return {
        "preregistration": prereg,
        "c0_report": c0_report,
        "c0_manifest": c0_manifest,
        "q7_report": q7_report,
        "q7_manifest": q7_manifest,
        "source_hashes": {
            "q141_archive_blob_sha1": EXPECTED_Q141_ARCHIVE_BLOB,
            "q7_archive_blob_sha1": EXPECTED_Q7_ARCHIVE_BLOB,
            "c0_ledger_sha256": c0_ledger_sha,
            "q7_ledger_sha256": q7_ledger_sha,
        },
    }


def validate_and_join(q7_rows: list[dict[str, str]], c0_rows: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    if len(q7_rows) != EXPECTED_Q7_ROWS:
        raise RuntimeError(f"Q141-C4 expected {EXPECTED_Q7_ROWS} Q7 rows, found {len(q7_rows)}")
    if len(c0_rows) != EXPECTED_C0_ROWS:
        raise RuntimeError(f"Q141-C4 expected {EXPECTED_C0_ROWS} Q80 C0 rows, found {len(c0_rows)}")

    c0_by_index = {int(row["target_index"]): row for row in c0_rows}
    c0_indices = sorted(c0_by_index)
    if len(c0_by_index) != len(c0_rows):
        raise RuntimeError("Q141-C4 duplicate Q80 C0 target_index")
    if c0_indices != list(range(c0_indices[0], c0_indices[-1] + 1)):
        raise RuntimeError("Q141-C4 Q80 C0 target indices are not contiguous")

    q7_dates = [row["target_date"] for row in q7_rows]
    if q7_dates != sorted(q7_dates) or len(set(q7_dates)) != len(q7_dates):
        raise RuntimeError("Q141-C4 Q7 target dates are not strictly chronological")

    split_counts = {"discovery": 0, "validation": 0, "blind_oos": 0}
    joined = []
    for row in q7_rows:
        target_index = int(row["prior_draws"])
        c0 = c0_by_index.get(target_index)
        if c0 is None:
            raise RuntimeError(f"Q141-C4 missing Q80 C0 row for Q7 target index {target_index}")
        for field in ("target_date", "cutoff_date", "actual_quintet"):
            if row[field] != c0[field]:
                raise RuntimeError(f"Q141-C4 cross-granularity join mismatch at {row['target_date']} field {field}")
        if target_index != int(c0["target_index"]):
            raise RuntimeError("Q141-C4 target-index identity mismatch")
        if row["target_date"] <= row["cutoff_date"]:
            raise RuntimeError("Q141-C4 target date is not after its cutoff")
        split = row["split"]
        if split not in split_counts:
            raise RuntimeError(f"Q141-C4 unexpected Q7 split label: {split}")
        split_counts[split] += 1
        joined.append({"q7": row, "c0": c0, "target_index": target_index})

    expected = {"discovery": 1972, "validation": 657, "blind_oos": 657}
    if split_counts != expected:
        raise RuntimeError(f"Q141-C4 Q7 split counts mismatch: {split_counts}")

    return joined, c0_rows


def build_features(q7_rows: list[dict[str, str]], c0_rows: list[dict[str, str]]) -> tuple[np.ndarray, list[dict]]:
    c0_indices = [int(row["target_index"]) for row in c0_rows]
    feature_rows: list[dict] = []
    matrix = np.full((len(q7_rows), len(FEATURE_B)), np.nan, dtype=np.float64)

    for i, q7 in enumerate(q7_rows):
        target_index = int(q7["prior_draws"])
        c0_cut = bisect.bisect_left(c0_indices, target_index)
        c0_prior = c0_rows[max(0, c0_cut - WINDOW):c0_cut]
        if len(c0_prior) != WINDOW:
            raise RuntimeError(f"Q141-C4 target {q7['target_date']} has fewer than {WINDOW} prior Q80 rows")
        if int(c0_prior[-1]["target_index"]) != target_index - 1:
            raise RuntimeError(f"Q141-C4 Q80 prior window is not contiguous before {q7['target_date']}")
        if any(int(row["target_index"]) >= target_index for row in c0_prior):
            raise RuntimeError(f"Q141-C4 Q80 current/future row entered predictors for {q7['target_date']}")

        if i < WINDOW:
            feature_rows.append({"available": False, "q80_last_prior_index": target_index - 1})
            continue

        q7_prior = q7_rows[i - WINDOW:i]
        if len(q7_prior) != WINDOW:
            raise RuntimeError("Q141-C4 Q7 prior window length mismatch")
        q7_prior_y = np.asarray([float(row["mean_percentile_all_formulas"]) for row in q7_prior], dtype=np.float64)
        if not np.isfinite(q7_prior_y).all():
            raise RuntimeError("Q141-C4 non-finite Q7 prior target outcome")
        if any(row["target_date"] >= q7["target_date"] for row in q7_prior):
            raise RuntimeError("Q141-C4 Q7 current/future outcome entered predictors")

        equal_hits = np.asarray([float(row["equal_family_top5_hits"]) for row in c0_prior], dtype=np.float64)
        family_matrix = np.asarray(
            [[float(row[column]) for column in FAMILY_COLUMNS] for row in c0_prior],
            dtype=np.float64,
        )
        if not np.isfinite(equal_hits).all() or not np.isfinite(family_matrix).all():
            raise RuntimeError("Q141-C4 non-finite Q80 family metric")
        if np.any(equal_hits < 0) or np.any(equal_hits > 5) or np.any(family_matrix < 0) or np.any(family_matrix > 5):
            raise RuntimeError("Q141-C4 Q80 Top-5 hit count outside [0,5]")

        family_means = family_matrix.mean(axis=0)
        total = float(family_means.sum())
        if total <= 0:
            entropy = 0.0
        else:
            probabilities = family_means / total
            positive = probabilities > 0
            entropy = float(-np.sum(probabilities[positive] * np.log(probabilities[positive])) / math.log(len(FAMILY_COLUMNS)))
        trend = float(equal_hits[-25:].mean() - equal_hits[:25].mean())
        values = np.asarray(
            [
                float(q7_prior_y.mean()),
                float(equal_hits.mean()),
                float(family_means.std(ddof=0)),
                entropy,
                trend,
            ],
            dtype=np.float64,
        )
        if not np.isfinite(values).all():
            raise RuntimeError(f"Q141-C4 non-finite predictor for {q7['target_date']}")
        matrix[i] = values
        feature_rows.append(
            {
                "available": True,
                "q7_last_prior_target_date": q7_prior[-1]["target_date"],
                "q80_last_prior_target_index": int(c0_prior[-1]["target_index"]),
                "q7_roll50_mean_percentile": float(values[0]),
                "q80_roll50_equal_family_top5_hits": float(values[1]),
                "q80_roll50_family_dispersion": float(values[2]),
                "q80_roll50_family_entropy_normalized": float(values[3]),
                "q80_equal_family_recent25_minus_previous25": float(values[4]),
            }
        )

    return matrix, feature_rows


def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float = RIDGE_ALPHA) -> dict:
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y) or len(y) < 2:
        raise ValueError("invalid ridge training dimensions")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("ridge training data contain non-finite values")
    mean = x.mean(axis=0)
    scale = x.std(axis=0, ddof=0)
    scale[scale < 1e-12] = 1.0
    standardized = (x - mean) / scale
    design = np.column_stack([np.ones(len(y)), standardized])
    penalty = np.eye(design.shape[1], dtype=np.float64) * float(alpha)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {
        "mean": mean,
        "scale": scale,
        "coefficients": coefficients,
        "alpha": float(alpha),
        "training_rows": int(len(y)),
    }


def predict_ridge(model: dict, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    standardized = (x - model["mean"]) / model["scale"]
    design = np.column_stack([np.ones(len(x)), standardized])
    return np.clip(design @ model["coefficients"], 0.0, 1.0)


def metric_summary(y: np.ndarray, prediction: np.ndarray) -> dict:
    error = prediction - y
    if len(y) == 0:
        raise ValueError("empty metric segment")
    if np.std(y) < 1e-15 or np.std(prediction) < 1e-15:
        correlation = None
    else:
        correlation = float(np.corrcoef(y, prediction)[0, 1])
    return {
        "targets": int(len(y)),
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(error ** 2))),
        "mean_prediction_error": float(np.mean(error)),
        "pearson_correlation": correlation,
    }


def block_signflip_p(values: np.ndarray, block_length: int, replicates: int, seed: int) -> float:
    values = np.asarray(values, dtype=np.float64)
    blocks = [values[i:i + block_length] for i in range(0, len(values), block_length)]
    block_sums = np.asarray([block.sum() for block in blocks], dtype=np.float64)
    observed = float(values.mean())
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(replicates):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=len(block_sums))
        null_mean = float(np.dot(signs, block_sums) / len(values))
        if null_mean >= observed:
            exceed += 1
    return float((exceed + 1) / (replicates + 1))


def moving_block_bootstrap_ci(values: np.ndarray, block_length: int, replicates: int, seed: int) -> list[float]:
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    blocks_needed = int(math.ceil(n / block_length))
    rng = np.random.default_rng(seed)
    means = np.empty(replicates, dtype=np.float64)
    offsets = np.arange(block_length, dtype=np.int64)
    for r in range(replicates):
        starts = rng.integers(0, n, size=blocks_needed)
        indices = np.concatenate([(start + offsets) % n for start in starts])[:n]
        means[r] = values[indices].mean()
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    source = verify_sources()
    c0_rows = read_csv(C0_LEDGER)
    q7_rows = read_csv(Q7_LEDGER)
    joined, _ = validate_and_join(q7_rows, c0_rows)
    feature_matrix, feature_rows = build_features(q7_rows, c0_rows)
    y = np.asarray([float(row["mean_percentile_all_formulas"]) for row in q7_rows], dtype=np.float64)
    if not np.isfinite(y).all() or np.any(y < 0) or np.any(y > 1):
        raise RuntimeError("Q141-C4 Q7 target percentile outside [0,1] or non-finite")

    n = len(q7_rows)
    if n != EXPECTED_Q7_ROWS or DISCOVERY_END != 1972 or VALIDATION_END != 2629:
        raise RuntimeError("Q141-C4 split constants do not match pinned Q7 source")
    if not np.isfinite(feature_matrix[WINDOW:]).all():
        raise RuntimeError("Q141-C4 predictors missing after rolling warmup")

    pred_a = np.full(n, np.nan, dtype=np.float64)
    pred_b = np.full(n, np.nan, dtype=np.float64)
    train_counts = np.zeros(n, dtype=np.int32)
    model_mode = ["warmup"] * n

    # Discovery predictions are genuinely prequential: each fit sees only earlier Discovery outcomes.
    for i in range(100, DISCOVERY_END):
        train_indices = np.arange(WINDOW, i, dtype=np.int64)
        if len(train_indices) < WINDOW:
            raise RuntimeError("Q141-C4 Discovery prequential fit has fewer than 50 prior training rows")
        model_a = fit_ridge(feature_matrix[train_indices][:, [0]], y[train_indices])
        model_b = fit_ridge(feature_matrix[train_indices], y[train_indices])
        pred_a[i] = float(predict_ridge(model_a, feature_matrix[i:i + 1, [0]])[0])
        pred_b[i] = float(predict_ridge(model_b, feature_matrix[i:i + 1])[0])
        train_counts[i] = len(train_indices)
        model_mode[i] = "expanding_prequential_discovery"

    # Freeze coefficients at the end of Discovery; never refit on Validation or Blind OOS.
    discovery_train = np.arange(WINDOW, DISCOVERY_END, dtype=np.int64)
    frozen_a = fit_ridge(feature_matrix[discovery_train][:, [0]], y[discovery_train])
    frozen_b = fit_ridge(feature_matrix[discovery_train], y[discovery_train])
    for i in range(DISCOVERY_END, n):
        pred_a[i] = float(predict_ridge(frozen_a, feature_matrix[i:i + 1, [0]])[0])
        pred_b[i] = float(predict_ridge(frozen_b, feature_matrix[i:i + 1])[0])
        train_counts[i] = len(discovery_train)
        model_mode[i] = "frozen_discovery_coefficients_prequential_features"

    if not np.isfinite(pred_a[100:]).all() or not np.isfinite(pred_b[100:]).all():
        raise RuntimeError("Q141-C4 prediction ledger contains non-finite values")

    split_slices = {
        "discovery": (100, DISCOVERY_END),
        "validation": (DISCOVERY_END, VALIDATION_END),
        "blind_oos": (VALIDATION_END, n),
    }
    metrics_by_split = {}
    ledger_rows = []
    for split, (start, end) in split_slices.items():
        indices = np.arange(start, end, dtype=np.int64)
        if len(indices) == 0:
            raise RuntimeError(f"Q141-C4 empty {split} evaluation segment")
        metrics_by_split[split] = {
            "targets": int(len(indices)),
            "constant_random_reference_0_5": metric_summary(y[indices], np.full(len(indices), 0.5)),
            "q7_roll50_mean_percentile": metric_summary(y[indices], feature_matrix[indices, 0]),
            "q7_only_ridge": metric_summary(y[indices], pred_a[indices]),
            "cross_granularity_ridge": metric_summary(y[indices], pred_b[indices]),
            "cross_granularity_minus_q7_only_mae": float(
                np.mean(np.abs(y[indices] - pred_a[indices])) - np.mean(np.abs(y[indices] - pred_b[indices]))
            ),
        }
        for i in indices:
            q7 = q7_rows[i]
            feature = feature_rows[i]
            error_a = float(pred_a[i] - y[i])
            error_b = float(pred_b[i] - y[i])
            ledger_rows.append(
                {
                    "target_index": int(q7["prior_draws"]),
                    "target_date": q7["target_date"],
                    "cutoff_date": q7["cutoff_date"],
                    "prior_draws": int(q7["prior_draws"]),
                    "split": split,
                    "actual_quintet": q7["actual_quintet"],
                    "q7_mean_percentile_all_formulas": float(y[i]),
                    "q7_roll50_mean_percentile": feature["q7_roll50_mean_percentile"],
                    "q80_roll50_equal_family_top5_hits": feature["q80_roll50_equal_family_top5_hits"],
                    "q80_roll50_family_dispersion": feature["q80_roll50_family_dispersion"],
                    "q80_roll50_family_entropy_normalized": feature["q80_roll50_family_entropy_normalized"],
                    "q80_equal_family_recent25_minus_previous25": feature["q80_equal_family_recent25_minus_previous25"],
                    "q80_last_prior_target_index": feature["q80_last_prior_target_index"],
                    "q7_last_prior_target_date": feature["q7_last_prior_target_date"],
                    "q7_only_ridge_prediction": float(pred_a[i]),
                    "cross_granularity_ridge_prediction": float(pred_b[i]),
                    "q7_only_absolute_error": abs(error_a),
                    "cross_granularity_absolute_error": abs(error_b),
                    "paired_absolute_error_improvement": abs(error_a) - abs(error_b),
                    "model_mode": model_mode[i],
                    "training_rows": int(train_counts[i]),
                }
            )

    blind_indices = np.arange(VALIDATION_END, n, dtype=np.int64)
    paired_improvement = np.abs(y[blind_indices] - pred_a[blind_indices]) - np.abs(y[blind_indices] - pred_b[blind_indices])
    primary_mean = float(paired_improvement.mean())
    primary_p = block_signflip_p(paired_improvement, BLOCK_LENGTH, REPLICATES, SEED)
    primary_ci = moving_block_bootstrap_ci(paired_improvement, BLOCK_LENGTH, REPLICATES, SEED + 1)
    accepted = primary_mean >= PRACTICAL_THRESHOLD and primary_p < 0.05
    decision = "FLAG_FOR_INDEPENDENT_PROSPECTIVE_REPLICATION_ONLY" if accepted else "NO_CROSS_GRANULARITY_TRANSFER_LIFT_DEMONSTRATED"

    final_model_summary = {
        "q7_only_ridge": {
            "features": list(FEATURE_A),
            "alpha": RIDGE_ALPHA,
            "training_rows": frozen_a["training_rows"],
            "training_offsets": [WINDOW, DISCOVERY_END - 1],
            "standardization_mean": frozen_a["mean"].tolist(),
            "standardization_scale": frozen_a["scale"].tolist(),
            "coefficients_intercept_then_features": frozen_a["coefficients"].tolist(),
        },
        "cross_granularity_ridge": {
            "features": list(FEATURE_B),
            "alpha": RIDGE_ALPHA,
            "training_rows": frozen_b["training_rows"],
            "training_offsets": [WINDOW, DISCOVERY_END - 1],
            "standardization_mean": frozen_b["mean"].tolist(),
            "standardization_scale": frozen_b["scale"].tolist(),
            "coefficients_intercept_then_features": frozen_b["coefficients"].tolist(),
        },
    }

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-C4",
        "status": "WALKFORWARD_COMPLETE",
        "decision": decision,
        "hypothesis": source["preregistration"]["hypothesis"],
        "estimand": source["preregistration"]["estimand"],
        "source": {
            **source["source_hashes"],
            "q80_c0_report_git_blob_sha1": git_blob_sha1(C0_REPORT.read_bytes()),
            "q80_c0_manifest_git_blob_sha1": git_blob_sha1(C0_MANIFEST.read_bytes()),
            "q7_b8_report_git_blob_sha1": git_blob_sha1(Q7_REPORT.read_bytes()),
            "q7_b8_manifest_git_blob_sha1": git_blob_sha1(Q7_MANIFEST.read_bytes()),
            "q7_archive_cutoff": "2026-10-24",
            "q141_archive_cutoff": "2026-11-10",
            "q7_exact_prefix_of_q141": True,
            "contest_315_used": False,
            "q141_suffix_rows_after_q7_prefix_excluded": 18,
        },
        "join_audit": {
            "q80_c0_rows": len(c0_rows),
            "q7_rows": len(q7_rows),
            "matched_rows": len(joined),
            "mismatches": 0,
            "q7_split_counts": {"discovery": 1972, "validation": 657, "blind_oos": 657},
            "q80_c0_split_labels_compared": False,
            "reason_split_labels_not_compared": "Different target-universe lengths create different 60/20/20 boundaries; Q7 split is authoritative.",
            "target_index_identity_verified": True,
            "date_cutoff_quintet_alignment_verified": True,
        },
        "walkforward": {
            "strict_prior": True,
            "rolling_window": WINDOW,
            "feature_warmup_targets": WINDOW,
            "discovery_prequential_start_offset": 100,
            "original_split_counts": {"discovery": 1972, "validation": 657, "blind_oos": 657},
            "evaluated_split_counts": {"discovery": 1872, "validation": 657, "blind_oos": 657},
            "discovery_fit": "Expanding prequential; each Discovery target is scored before it can enter later training.",
            "validation_blind_fit": "Coefficients frozen after Discovery; rolling predictors update only from strictly prior target outcomes.",
            "validation_blind_refit": False,
            "discovery_training_rows_for_frozen_models": int(len(discovery_train)),
            "target_update_order": "Build prior-only features and predict target, score the frozen Q7 outcome, then allow that outcome into later rolling windows.",
            "blind_used_for_model_selection": False,
        },
        "models": {
            "q7_only_ridge": {"features": list(FEATURE_A), "alpha": RIDGE_ALPHA, "role": "same-granularity baseline"},
            "cross_granularity_ridge": {"features": list(FEATURE_B), "alpha": RIDGE_ALPHA, "role": "Q80-to-Q7 transfer model"},
            "final_discovery_fit": final_model_summary,
            "no_hyperparameter_tuning": True,
            "prediction_clip": [0.0, 1.0],
        },
        "metrics_by_split": metrics_by_split,
        "primary_inference": {
            "endpoint": "Blind OOS MAE(q7_only_ridge) - MAE(cross_granularity_ridge)",
            "mean_improvement": primary_mean,
            "ci95_circular_moving_block": primary_ci,
            "one_sided_block_signflip_p": primary_p,
            "block_length": BLOCK_LENGTH,
            "signflip_replicates": REPLICATES,
            "bootstrap_replicates": REPLICATES,
            "seed": SEED,
            "minimum_practical_effect": PRACTICAL_THRESHOLD,
            "multiplicity": "One preregistered confirmatory endpoint; secondary metrics descriptive only.",
            "passes_preregistered_gate": accepted,
        },
        "leakage_audit": {
            "all_q7_targets_match_q80_prior_target_index": True,
            "q80_predictors_use_exactly_previous_50_target_rows": True,
            "q7_rolling_baseline_uses_exactly_previous_50_target_outcomes": True,
            "current_target_excluded_from_predictors": True,
            "future_suffix_excluded_from_predictors": True,
            "discovery_predictions_use_prior_discovery_only": True,
            "validation_and_blind_coefficients_frozen_after_discovery": True,
            "validation_and_blind_outcomes_not_used_for_refitting": True,
            "q80_split_labels_ignored_due_different_partition_boundaries": True,
        },
        "limitations": [
            "The predicted outcome is Q7 formula-universe rank quality, not the winning quintet or number-hit count.",
            "Historical Blind OOS is exposed by prior SONAR research and is not virgin prospective evidence.",
            "Q80 C0 contains six coarse family aggregates; this does not cover the full 59-feature Q89/Q90 grammar.",
            "Q7 and Q141 have different source windows; exact prefix and target-level alignment were verified, but the 18-row Q141 suffix is excluded.",
            "A null transfer result does not prove that all cross-granularity interactions are absent.",
        ],
        "next_action": "If the registered transfer gate is not met, retain the null result and extend the descriptive cross-granularity atlas only after feature-level lineage is reconciled; do not tune on this historical Blind OOS.",
        "governance": {"no_merge": True, "no_auto_promotion": True, "no_shadow_insertion": True, "no_canonical_archive_mutation": True, "protected_prs": [6, 7, 8]},
        "target_ledger": {"path": LEDGER.relative_to(ROOT).as_posix(), "rows": len(ledger_rows)},
    }

    ledger_columns = [
        "target_index", "target_date", "cutoff_date", "prior_draws", "split", "actual_quintet",
        "q7_mean_percentile_all_formulas", "q7_roll50_mean_percentile",
        "q80_roll50_equal_family_top5_hits", "q80_roll50_family_dispersion",
        "q80_roll50_family_entropy_normalized", "q80_equal_family_recent25_minus_previous25",
        "q80_last_prior_target_index", "q7_last_prior_target_date",
        "q7_only_ridge_prediction", "cross_granularity_ridge_prediction",
        "q7_only_absolute_error", "cross_granularity_absolute_error",
        "paired_absolute_error_improvement", "model_mode", "training_rows",
    ]
    ledger_path = output_dir / LEDGER.name
    report_path = output_dir / REPORT.name
    manifest_path = output_dir / MANIFEST.name
    checkpoint_path = output_dir / CHECKPOINT.name
    write_csv(ledger_path, ledger_rows, ledger_columns)
    report["target_ledger"]["sha256"] = sha256_bytes(ledger_path.read_bytes())
    report["target_ledger"]["git_blob_sha1"] = git_blob_sha1(ledger_path.read_bytes())
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    lineage_paths = {
        "preregistration_json": PREREG,
        "preregistration_markdown": PREREG_MD,
        "runner_script": Path(__file__).resolve(),
        "unit_tests": ROOT / "tests" / "test_sonar_q141_cross_granularity_transfer.py",
        "workflow": ROOT / ".github" / "workflows" / "q141-c4-cross-granularity-transfer.yml",
        "q80_c0_report": C0_REPORT,
        "q80_c0_manifest": C0_MANIFEST,
        "q80_c0_ledger": C0_LEDGER,
        "q7_b8_report": Q7_REPORT,
        "q7_b8_manifest": Q7_MANIFEST,
        "q7_b8_ledger": Q7_LEDGER,
    }
    code_lineage = {}
    for label, path in lineage_paths.items():
        data = path.read_bytes()
        code_lineage[label] = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "git_blob_sha1": git_blob_sha1(data),
            "sha256": sha256_bytes(data),
        }

    files = {}
    for label, path in (("report", report_path), ("target_ledger", ledger_path)):
        data = path.read_bytes()
        files[label] = {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "git_blob_sha1": git_blob_sha1(data),
        }
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-C4",
        "status": "COMPUTED_PENDING_REMOTE_GIT_READBACK",
        "source_archive_blob_sha1": EXPECTED_Q141_ARCHIVE_BLOB,
        "q7_source_archive_blob_sha1": EXPECTED_Q7_ARCHIVE_BLOB,
        "q7_targets": len(q7_rows),
        "evaluated_targets": len(ledger_rows),
        "files": files,
        "code_lineage": code_lineage,
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    manifest_data = manifest_path.read_bytes()
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-C4_CHECKPOINT",
        "status": "COMPUTED_PENDING_REMOTE_GIT_READBACK",
        "decision": decision,
        "report_path": report_path.relative_to(ROOT).as_posix(),
        "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "manifest_sha256": sha256_bytes(manifest_data),
        "manifest_git_blob_sha1": git_blob_sha1(manifest_data),
        "next_action": report["next_action"],
        "governance": report["governance"],
    }
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        head = "unavailable"
    print(json.dumps({
        "task_id": "Q141-C4",
        "status": "COMPUTED_PENDING_REMOTE_GIT_READBACK",
        "decision": decision,
        "evaluated_targets": len(ledger_rows),
        "metrics_by_split": {
            key: {
                "targets": value["targets"],
                "q7_only_mae": value["q7_only_ridge"]["mae"],
                "cross_granularity_mae": value["cross_granularity_ridge"]["mae"],
                "mae_improvement": value["cross_granularity_minus_q7_only_mae"],
            }
            for key, value in metrics_by_split.items()
        },
        "blind_primary_mean_improvement": primary_mean,
        "blind_primary_p": primary_p,
        "blind_primary_ci95": primary_ci,
        "branch_head": head,
        "manifest": manifest_path.relative_to(ROOT).as_posix(),
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
