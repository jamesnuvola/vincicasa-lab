#!/usr/bin/env python3
"""Q141-C5: strict-prior incremental Q90-family transfer into Q7 meta-quality."""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
WINDOW = 50
DISCOVERY_END = 1972
VALIDATION_END = 2629
EXPECTED_Q7_ROWS = 3286
EXPECTED_Q80_ROWS = 3354
EXPECTED_Q90_ROWS = 3351
RIDGE_ALPHA = 1.0
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261125
PRACTICAL_THRESHOLD = 0.005

Q7_REPORT = OUT / "q7_formula_complexity_walkforward_report_2026-11-12.json"
Q7_MANIFEST = OUT / "q141_q7_ast_complexity_manifest_2026-11-12.json"
Q7_LEDGER = OUT / "q7_formula_complexity_walkforward_target_ledger_2026-11-12.csv"
Q80_REPORT = OUT / "q141_formula_family_behaviour_report_2026-11-12.json"
Q80_MANIFEST = OUT / "q141_formula_family_behaviour_manifest_2026-11-12.json"
Q80_LEDGER = OUT / "q141_formula_family_behaviour_target_ledger_2026-11-12.csv"
Q90_REPORT = OUT / "q141_q90_family_persistence_report_2026-11-12.json"
Q90_MANIFEST = OUT / "q141_q90_family_persistence_manifest_2026-11-12.json"
Q90_LEDGER = OUT / "q141_q90_family_persistence_target_ledger_2026-11-12.csv"

PREREG = OUT / "q141_q90_to_q7_transfer_preregistration_2026-11-12.json"
PREREG_MD = OUT / "q141_q90_to_q7_transfer_preregistration_2026-11-12.md"
REPORT = OUT / "q141_q90_to_q7_transfer_report_2026-11-12.json"
LEDGER = OUT / "q141_q90_to_q7_transfer_target_ledger_2026-11-12.csv"
MANIFEST = OUT / "q141_q90_to_q7_transfer_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_q90_to_q7_transfer_checkpoint_2026-11-12.json"

Q141_ARCHIVE_BLOB = "fcb453ed06c8002314f826dbac79d6935f9ac103"
Q7_ARCHIVE_BLOB = "7dab05ba49ace909fe8783eef729605049c65e50"
Q90_ARCHIVE_BLOB = "5d2efd70684e918b27d8f06386d545647898336d"
Q90_ARTIFACT_SHA256 = "12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"

Q80_COLUMNS = (
    "frequency_change_top5_hits",
    "frequency_level_top5_hits",
    "lag_memory_top5_hits",
    "neighbour_field_top5_hits",
    "position_dependence_top5_hits",
    "recency_gap_top5_hits",
)
Q90_COLUMNS = (
    "linear_mean_L4",
    "linear_mean_L5",
    "linear_mean_L6",
    "linear_mean_L7",
    "linear_mean_L8",
    "pairwise_interaction_I4",
    "conditional_gate_G4",
)
Q7_X_NAMES = ("q7_roll50_mean_percentile",)
Q80_X_NAMES = (
    "q80_roll50_equal_family_top5_hits",
    "q80_roll50_family_dispersion",
    "q80_roll50_family_entropy_normalized",
    "q80_equal_family_recent25_minus_previous25",
)
Q90_X_NAMES = (
    "q90_roll50_equal_family_top5_share",
    "q90_roll50_family_dispersion",
    "q90_roll50_family_entropy_normalized",
    "q90_equal_family_recent25_minus_previous25",
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

def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def verify_sources() -> dict:
    prereg = read_json(PREREG)
    q7_report, q7_manifest = read_json(Q7_REPORT), read_json(Q7_MANIFEST)
    q80_report, q80_manifest = read_json(Q80_REPORT), read_json(Q80_MANIFEST)
    q90_report, q90_manifest = read_json(Q90_REPORT), read_json(Q90_MANIFEST)

    if prereg.get("task_id") != "Q141-C5" or prereg.get("status") != "PREREGISTERED_BEFORE_EXECUTION":
        raise RuntimeError("Q141-C5 preregistration missing or invalid")
    if q7_report.get("task_id") != "Q141-B8" or q7_report.get("decision") != "COMPLEXITY_ASSOCIATION_NOT_DEMONSTRATED":
        raise RuntimeError("Q141-C5 Q7 source report mismatch")
    q7_source = q7_report.get("source", {})
    if q7_source.get("q7_archive_blob_sha1") != Q7_ARCHIVE_BLOB or q7_source.get("q141_archive_blob_sha1") != Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C5 Q7 archive lineage mismatch")
    if q7_source.get("q7_is_exact_q141_prefix") is not True or q7_report.get("walkforward", {}).get("strict_prior") is not True:
        raise RuntimeError("Q141-C5 Q7 strict-prior/exact-prefix evidence missing")
    if q7_manifest.get("source_archive_blob_sha1") != Q7_ARCHIVE_BLOB or q7_manifest.get("q141_archive_blob_sha1") != Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C5 Q7 manifest archive mismatch")
    if q7_manifest.get("eligible_targets") != EXPECTED_Q7_ROWS or q7_manifest.get("formula_count") != 1023:
        raise RuntimeError("Q141-C5 Q7 universe dimensions mismatch")

    if q80_report.get("task_id") != "Q141-C0" or q80_report.get("status") != "EXECUTED_EXPLORATORY":
        raise RuntimeError("Q141-C5 Q80 C0 report mismatch")
    if q80_report.get("source", {}).get("git_blob_sha1") != Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141-C5 Q80 archive mismatch")
    if q80_manifest.get("source_archive_git_blob_sha1") != Q141_ARCHIVE_BLOB or q80_manifest.get("target_rows") != EXPECTED_Q80_ROWS:
        raise RuntimeError("Q141-C5 Q80 manifest mismatch")
    strict_text = q80_report.get("walkforward", {}).get("strict_prior", "")
    if "index < i" not in strict_text or "state update follows target scoring" not in strict_text:
        raise RuntimeError("Q141-C5 Q80 strict-prior/update-order evidence missing")

    if q90_report.get("task_id") != "Q141-B7" or q90_report.get("status") != "COMPUTED":
        raise RuntimeError("Q141-C5 Q90 report mismatch")
    q90_source = q90_report.get("source", {})
    if q90_source.get("archive_blob_sha1") != Q90_ARCHIVE_BLOB or q90_source.get("artifact_sha256") != Q90_ARTIFACT_SHA256:
        raise RuntimeError("Q141-C5 Q90 archive/artifact identity mismatch")
    if q90_report.get("formula_universe", {}).get("full_catalog_count") != 330429:
        raise RuntimeError("Q141-C5 Q90 full catalog count mismatch")
    if q90_report.get("formula_universe", {}).get("sample_count") != 700:
        raise RuntimeError("Q141-C5 Q90 fixed sample count mismatch")
    if q90_manifest.get("artifact_sha256") != Q90_ARTIFACT_SHA256 or q90_manifest.get("target_count") != EXPECTED_Q90_ROWS:
        raise RuntimeError("Q141-C5 Q90 manifest mismatch")
    if q90_manifest.get("formula_sample_count") != 700 or q90_manifest.get("ledger_rows") != EXPECTED_Q90_ROWS:
        raise RuntimeError("Q141-C5 Q90 sample/ledger dimensions mismatch")
    if q90_report.get("walkforward", {}).get("strict_prior") is not True:
        raise RuntimeError("Q141-C5 Q90 strict-prior evidence missing")

    q7_ledger_sha = sha256_bytes(Q7_LEDGER.read_bytes())
    q80_ledger_sha = sha256_bytes(Q80_LEDGER.read_bytes())
    q90_ledger_sha = sha256_bytes(Q90_LEDGER.read_bytes())
    q7_expected = q7_manifest["files"][Q7_LEDGER.name]["sha256"]
    q80_expected = q80_manifest["target_ledger_sha256"]
    q90_expected = q90_manifest["ledger_sha256"]
    if (q7_ledger_sha, q80_ledger_sha, q90_ledger_sha) != (q7_expected, q80_expected, q90_expected):
        raise RuntimeError("Q141-C5 source ledger SHA-256 mismatch")

    return {
        "preregistration": prereg,
        "q7_report": q7_report,
        "q7_manifest": q7_manifest,
        "q80_report": q80_report,
        "q80_manifest": q80_manifest,
        "q90_report": q90_report,
        "q90_manifest": q90_manifest,
        "source_hashes": {
            "q141_archive_git_blob_sha1": Q141_ARCHIVE_BLOB,
            "q7_archive_git_blob_sha1": Q7_ARCHIVE_BLOB,
            "q90_archive_git_blob_sha1": Q90_ARCHIVE_BLOB,
            "q90_artifact_sha256": Q90_ARTIFACT_SHA256,
            "q7_ledger_sha256": q7_ledger_sha,
            "q80_ledger_sha256": q80_ledger_sha,
            "q90_ledger_sha256": q90_ledger_sha,
        },
    }

def prior_window(rows: list[dict[str, str]], keys: list[int], target_index: int, window: int, key_name: str) -> list[dict[str, str]]:
    cut = bisect.bisect_left(keys, target_index)
    prior = rows[max(0, cut - window):cut]
    if len(prior) != window:
        raise RuntimeError(f"target {target_index}: expected {window} prior rows in {key_name}, found {len(prior)}")
    if int(prior[-1][key_name]) != target_index - 1:
        raise RuntimeError(f"target {target_index}: {key_name} prior window is not contiguous")
    if any(int(row[key_name]) >= target_index for row in prior):
        raise RuntimeError(f"target {target_index}: current/future row entered {key_name} features")
    return prior

def family_state(rows: list[dict[str, str]], columns: tuple[str, ...], scale_max: float) -> tuple[float, float, float, float]:
    matrix = np.asarray([[float(row[column]) for column in columns] for row in rows], dtype=np.float64)
    if not np.isfinite(matrix).all() or np.any(matrix < 0) or np.any(matrix > scale_max):
        raise RuntimeError("family state contains invalid values")
    family_means = matrix.mean(axis=0)
    equal_by_target = matrix.mean(axis=1)
    total = float(family_means.sum())
    if total <= 0:
        entropy = 0.0
    else:
        probabilities = family_means / total
        positive = probabilities > 0
        entropy = float(-np.sum(probabilities[positive] * np.log(probabilities[positive])) / math.log(len(columns)))
    trend = float(equal_by_target[-25:].mean() - equal_by_target[:25].mean())
    return float(equal_by_target.mean()), float(family_means.std(ddof=0)), entropy, trend

def build_features(q7_rows: list[dict[str, str]], q80_rows: list[dict[str, str]], q90_rows: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict]]:
    q80_keys = [int(row["target_index"]) for row in q80_rows]
    q90_keys = [int(row["prior_draws"]) for row in q90_rows]
    if q80_keys != sorted(q80_keys) or len(set(q80_keys)) != len(q80_keys):
        raise RuntimeError("Q141-C5 Q80 keys are not unique and ordered")
    if q90_keys != sorted(q90_keys) or len(set(q90_keys)) != len(q90_keys):
        raise RuntimeError("Q141-C5 Q90 keys are not unique and ordered")

    x0 = np.full((len(q7_rows), 1), np.nan, dtype=np.float64)
    x1 = np.full((len(q7_rows), 1 + len(Q80_X_NAMES)), np.nan, dtype=np.float64)
    x2 = np.full((len(q7_rows), 1 + len(Q80_X_NAMES) + len(Q90_X_NAMES)), np.nan, dtype=np.float64)
    feature_rows: list[dict] = []

    for i, q7 in enumerate(q7_rows):
        target_index = int(q7["prior_draws"])
        if i < WINDOW:
            feature_rows.append({"available": False})
            continue
        q7_prior = q7_rows[i - WINDOW:i]
        if len(q7_prior) != WINDOW or any(row["target_date"] >= q7["target_date"] for row in q7_prior):
            raise RuntimeError(f"target {q7['target_date']}: Q7 current/future outcome entered rolling feature")
        y_prior = np.asarray([float(row["mean_percentile_all_formulas"]) for row in q7_prior], dtype=np.float64)
        if not np.isfinite(y_prior).all():
            raise RuntimeError("Q7 prior target outcomes are non-finite")

        q80_prior = prior_window(q80_rows, q80_keys, target_index, WINDOW, "target_index")
        q90_prior = prior_window(q90_rows, q90_keys, target_index, WINDOW, "prior_draws")
        for prior in q80_prior + q90_prior:
            if prior["target_date"] > q7["cutoff_date"]:
                raise RuntimeError(f"target {q7['target_date']}: source row after cutoff entered features")

        q80_equal, q80_dispersion, q80_entropy, q80_trend = family_state(q80_prior, Q80_COLUMNS, 5.0)
        q90_equal, q90_dispersion, q90_entropy, q90_trend = family_state(q90_prior, Q90_COLUMNS, 1.0)
        values0 = [float(y_prior.mean())]
        values1 = values0 + [q80_equal, q80_dispersion, q80_entropy, q80_trend]
        values2 = values1 + [q90_equal, q90_dispersion, q90_entropy, q90_trend]
        if not np.isfinite(values2).all():
            raise RuntimeError(f"target {q7['target_date']}: non-finite predictor")
        x0[i], x1[i], x2[i] = values0, values1, values2
        feature_rows.append({
            "available": True,
            "q7_last_prior_target_date": q7_prior[-1]["target_date"],
            "q80_last_prior_target_index": int(q80_prior[-1]["target_index"]),
            "q90_last_prior_draws": int(q90_prior[-1]["prior_draws"]),
            "q7_roll50_mean_percentile": values0[0],
            "q80_roll50_equal_family_top5_hits": q80_equal,
            "q80_roll50_family_dispersion": q80_dispersion,
            "q80_roll50_family_entropy_normalized": q80_entropy,
            "q80_equal_family_recent25_minus_previous25": q80_trend,
            "q90_roll50_equal_family_top5_share": q90_equal,
            "q90_roll50_family_dispersion": q90_dispersion,
            "q90_roll50_family_entropy_normalized": q90_entropy,
            "q90_equal_family_recent25_minus_previous25": q90_trend,
        })
    return x0, x1, x2, feature_rows

def fit_ridge(x: np.ndarray, y: np.ndarray, alpha: float = RIDGE_ALPHA) -> dict:
    x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y) or len(y) < 2:
        raise ValueError("invalid ridge training dimensions")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("non-finite ridge training values")
    mean = x.mean(axis=0)
    scale = x.std(axis=0, ddof=0)
    scale[scale < 1e-12] = 1.0
    design = np.column_stack([np.ones(len(y)), (x - mean) / scale])
    penalty = np.eye(design.shape[1], dtype=np.float64) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return {"mean": mean, "scale": scale, "coef": coef, "alpha": float(alpha), "training_rows": int(len(y))}

def predict_ridge(model: dict, x: np.ndarray) -> np.ndarray:
    z = (np.asarray(x, dtype=np.float64) - model["mean"]) / model["scale"]
    design = np.column_stack([np.ones(len(z)), z])
    return np.clip(design @ model["coef"], 0.0, 1.0)

def metric_summary(y: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - y
    return {
        "targets": int(len(y)),
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mean_prediction_error": float(err.mean()),
        "pearson_correlation": None if np.std(y) < 1e-15 or np.std(pred) < 1e-15 else float(np.corrcoef(y, pred)[0, 1]),
    }

def block_signflip_p(values: np.ndarray, block_length: int, replicates: int, seed: int) -> float:
    values = np.asarray(values, dtype=np.float64)
    sums = np.asarray([values[i:i + block_length].sum() for i in range(0, len(values), block_length)], dtype=np.float64)
    observed = float(values.mean())
    rng = np.random.default_rng(seed)
    exceed = 0
    for _ in range(replicates):
        signs = rng.choice(np.asarray([-1.0, 1.0]), size=len(sums))
        if float(np.dot(signs, sums) / len(values)) >= observed:
            exceed += 1
    return float((exceed + 1) / (replicates + 1))

def moving_block_ci(values: np.ndarray, block_length: int, replicates: int, seed: int) -> list[float]:
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    needed = int(math.ceil(n / block_length))
    rng = np.random.default_rng(seed)
    means = np.empty(replicates, dtype=np.float64)
    offsets = np.arange(block_length, dtype=np.int64)
    for r in range(replicates):
        starts = rng.integers(0, n, size=needed)
        idx = np.concatenate([(s + offsets) % n for s in starts])[:n]
        means[r] = values[idx].mean()
    return [float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))]

def mean(values: list[float]) -> float:
    return float(np.mean(np.asarray(values, dtype=np.float64)))

def safe_corr(a: list[float], b: list[float]) -> float | None:
    aa, bb = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if len(aa) < 3 or np.std(aa) < 1e-15 or np.std(bb) < 1e-15:
        return None
    return float(np.corrcoef(aa, bb)[0, 1])

def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0
        for k in range(i, j):
            out[order[k]] = avg
        i = j
    return out

def spearman(a: list[float], b: list[float]) -> float | None:
    return safe_corr(ranks(a), ranks(b))

def lag1(values: list[float]) -> float | None:
    return safe_corr(values[:-1], values[1:]) if len(values) > 3 else None

def transition_summary(values: list[str]) -> dict:
    seq = [v for v in values if v and v not in {"EQUAL_WARMUP", "warmup_equal_family"}]
    if not seq:
        return {"n": 0, "switches": 0, "switch_rate": None, "distinct": 0, "mean_run_length": None, "max_run_length": 0}
    runs = []
    current, length = seq[0], 1
    switches = 0
    for value in seq[1:]:
        if value == current:
            length += 1
        else:
            runs.append(length)
            switches += 1
            current, length = value, 1
    runs.append(length)
    return {
        "n": len(seq),
        "switches": switches,
        "switch_rate": float(switches / max(1, len(seq) - 1)),
        "distinct": len(set(seq)),
        "mean_run_length": float(np.mean(runs)),
        "max_run_length": int(max(runs)),
        "family_counts": {k: seq.count(k) for k in sorted(set(seq))},
    }

def correlation_summary(columns: tuple[str, ...], matrix: np.ndarray) -> dict:
    pairs = []
    for i in range(len(columns)):
        for j in range(i + 1, len(columns)):
            c = safe_corr(matrix[:, i].tolist(), matrix[:, j].tolist())
            if c is not None:
                pairs.append({"family_a": columns[i], "family_b": columns[j], "pearson": c})
    ordered = sorted(pairs, key=lambda x: x["pearson"])
    return {
        "pair_count": len(pairs),
        "mean_absolute_pairwise_correlation": float(np.mean([abs(x["pearson"]) for x in pairs])) if pairs else None,
        "most_negative_pair": ordered[0] if ordered else None,
        "most_positive_pair": ordered[-1] if ordered else None,
        "interpretation": "descriptive co-movement only; no p-values or causal claims",
    }

def validate_and_join(q7: list[dict[str, str]], q80: list[dict[str, str]], q90: list[dict[str, str]]) -> list[dict]:
    if (len(q7), len(q80), len(q90)) != (EXPECTED_Q7_ROWS, EXPECTED_Q80_ROWS, EXPECTED_Q90_ROWS):
        raise RuntimeError("Q141-C5 source row counts differ from preregistration")
    q80_by = {int(r["target_index"]): r for r in q80}
    q90_by = {int(r["prior_draws"]): r for r in q90}
    if len(q80_by) != len(q80) or len(q90_by) != len(q90):
        raise RuntimeError("duplicate Q80 or Q90 target key")
    joined = []
    counts = {"discovery": 0, "validation": 0, "blind_oos": 0}
    for row in q7:
        ix = int(row["prior_draws"])
        a, b = q80_by.get(ix), q90_by.get(ix)
        if a is None or b is None:
            raise RuntimeError(f"missing source row for Q7 prior_draws={ix}")
        for source_name, source in (("Q80", a), ("Q90", b)):
            for field in ("target_date", "cutoff_date", "actual_quintet"):
                if row[field] != source[field]:
                    raise RuntimeError(f"{source_name}/Q7 alignment mismatch at {row['target_date']} field {field}")
        if row["target_date"] <= row["cutoff_date"]:
            raise RuntimeError("target date is not after cutoff")
        if int(a["target_index"]) != ix or int(b["prior_draws"]) != ix:
            raise RuntimeError("target index identity mismatch")
        if row["split"] not in counts:
            raise RuntimeError("unexpected Q7 split label")
        counts[row["split"]] += 1
        joined.append({"q7": row, "q80": a, "q90": b, "index": ix})
    if counts != {"discovery": 1972, "validation": 657, "blind_oos": 657}:
        raise RuntimeError(f"Q7 split counts mismatch: {counts}")
    return joined

def build_atlas(joined: list[dict], q7_rows: list[dict[str, str]]) -> dict:
    out = {}
    split_ranges = {
        "discovery": (0, DISCOVERY_END),
        "validation": (DISCOVERY_END, VALIDATION_END),
        "blind_oos": (VALIDATION_END, len(q7_rows)),
    }
    for split, (start, end) in split_ranges.items():
        arr = joined[start:end]
        y = [float(x["q7"]["mean_percentile_all_formulas"]) for x in arr]
        q80_equal = [float(x["q80"]["equal_family_top5_hits"]) for x in arr]
        q90_equal = [float(np.mean([float(x["q90"][c]) for c in Q90_COLUMNS])) for x in arr]
        q90_disp = [float(np.std([float(x["q90"][c]) for c in Q90_COLUMNS])) for x in arr]
        q90_ent = []
        for x in arr:
            v = np.asarray([float(x["q90"][c]) for c in Q90_COLUMNS], dtype=np.float64)
            total = float(v.sum())
            if total <= 0:
                q90_ent.append(0.0)
            else:
                p = v / total
                q90_ent.append(float(-np.sum(p[p > 0] * np.log(p[p > 0])) / math.log(len(Q90_COLUMNS))))
        q80_matrix = np.asarray([[float(x["q80"][c]) for c in Q80_COLUMNS] for x in arr], dtype=np.float64)
        q90_matrix = np.asarray([[float(x["q90"][c]) for c in Q90_COLUMNS] for x in arr], dtype=np.float64)
        out[split] = {
            "targets": len(arr),
            "q7_mean_formula_percentile": mean(y),
            "q80_equal_family_top5_hits_mean": mean(q80_equal),
            "q90_equal_family_top5_share_mean": mean(q90_equal),
            "q90_family_dispersion_mean": mean(q90_disp),
            "q90_family_entropy_normalized_mean": mean(q90_ent),
            "contemporaneous_associations": {
                "pearson_q80_equal_hits_vs_q7_percentile": safe_corr(q80_equal, y),
                "spearman_q80_equal_hits_vs_q7_percentile": spearman(q80_equal, y),
                "pearson_q90_equal_share_vs_q7_percentile": safe_corr(q90_equal, y),
                "spearman_q90_equal_share_vs_q7_percentile": spearman(q90_equal, y),
                "pearson_q80_equal_hits_vs_q90_equal_share": safe_corr(q80_equal, q90_equal),
                "pearson_q90_dispersion_vs_q7_percentile": safe_corr(q90_disp, y),
                "pearson_q90_entropy_vs_q7_percentile": safe_corr(q90_ent, y),
            },
            "q80_family_lag1": {c: lag1([float(x["q80"][c]) for x in arr]) for c in Q80_COLUMNS},
            "q90_family_lag1": {c: lag1([float(x["q90"][c]) for x in arr]) for c in Q90_COLUMNS},
            "within_source_family_co_movement": {
                "q80": correlation_summary(Q80_COLUMNS, q80_matrix),
                "q90": correlation_summary(Q90_COLUMNS, q90_matrix),
            },
            "selector_transitions": {
                "q80": transition_summary([x["q80"]["selected_family"] for x in arr]),
                "q90": transition_summary([x["q90"]["selected_family"] for x in arr]),
            },
        }
    return out

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source = verify_sources()
    q7, q80, q90 = read_csv(Q7_LEDGER), read_csv(Q80_LEDGER), read_csv(Q90_LEDGER)
    joined = validate_and_join(q7, q80, q90)
    x0, x1, x2, feature_rows = build_features(q7, q80, q90)
    y = np.asarray([float(r["mean_percentile_all_formulas"]) for r in q7], dtype=np.float64)
    if not np.isfinite(y).all() or np.any(y < 0) or np.any(y > 1):
        raise RuntimeError("Q7 target percentile outside [0,1]")
    if not (np.isfinite(x0[WINDOW:]).all() and np.isfinite(x1[WINDOW:]).all() and np.isfinite(x2[WINDOW:]).all()):
        raise RuntimeError("rolling feature matrix has missing/non-finite values after warm-up")

    n = len(q7)
    predictions = {name: np.full(n, np.nan, dtype=np.float64) for name in ("m0", "m1", "m2")}
    train_counts = np.zeros(n, dtype=np.int32)
    modes = ["warmup"] * n
    for i in range(100, DISCOVERY_END):
        train = np.arange(WINDOW, i, dtype=np.int64)
        if len(train) < WINDOW:
            raise RuntimeError("Discovery fit has fewer than 50 strictly prior training targets")
        for name, matrix in (("m0", x0), ("m1", x1), ("m2", x2)):
            model = fit_ridge(matrix[train], y[train])
            predictions[name][i] = float(predict_ridge(model, matrix[i:i+1])[0])
        train_counts[i] = len(train)
        modes[i] = "expanding_prequential_discovery"

    discovery_train = np.arange(WINDOW, DISCOVERY_END, dtype=np.int64)
    frozen = {name: fit_ridge(matrix[discovery_train], y[discovery_train]) for name, matrix in (("m0", x0), ("m1", x1), ("m2", x2))}
    for i in range(DISCOVERY_END, n):
        for name, matrix in (("m0", x0), ("m1", x1), ("m2", x2)):
            predictions[name][i] = float(predict_ridge(frozen[name], matrix[i:i+1])[0])
        train_counts[i] = len(discovery_train)
        modes[i] = "frozen_discovery_coefficients_prequential_features"

    if any(not np.isfinite(v[100:]).all() for v in predictions.values()):
        raise RuntimeError("prediction ledger contains non-finite values")

    split_slices = {
        "discovery": (100, DISCOVERY_END),
        "validation": (DISCOVERY_END, VALIDATION_END),
        "blind_oos": (VALIDATION_END, n),
    }
    metrics = {}
    ledger_rows = []
    for split, (start, end) in split_slices.items():
        idx = np.arange(start, end, dtype=np.int64)
        metrics[split] = {
            "targets": int(len(idx)),
            "constant_0_5_reference": metric_summary(y[idx], np.full(len(idx), 0.5)),
            "q7_roll50_mean_percentile": metric_summary(y[idx], x0[idx, 0]),
            "m0_q7_only_ridge": metric_summary(y[idx], predictions["m0"][idx]),
            "m1_q7_q80_ridge": metric_summary(y[idx], predictions["m1"][idx]),
            "m2_q7_q80_q90_ridge": metric_summary(y[idx], predictions["m2"][idx]),
            "primary_mae_improvement_m1_minus_m2": float(
                np.mean(np.abs(y[idx] - predictions["m1"][idx])) - np.mean(np.abs(y[idx] - predictions["m2"][idx]))
            ),
            "descriptive_mae_improvement_m0_minus_m2": float(
                np.mean(np.abs(y[idx] - predictions["m0"][idx])) - np.mean(np.abs(y[idx] - predictions["m2"][idx]))
            ),
        }
        for i in idx:
            row = q7[i]
            f = feature_rows[i]
            ledger_rows.append({
                "target_index": int(row["prior_draws"]),
                "target_date": row["target_date"],
                "cutoff_date": row["cutoff_date"],
                "prior_draws": int(row["prior_draws"]),
                "split": split,
                "actual_quintet": row["actual_quintet"],
                "q7_mean_percentile_all_formulas": float(y[i]),
                **{k: f[k] for k in Q7_X_NAMES + Q80_X_NAMES + Q90_X_NAMES},
                "pred_m0_q7_only": float(predictions["m0"][i]),
                "pred_m1_q7_q80": float(predictions["m1"][i]),
                "pred_m2_q7_q80_q90": float(predictions["m2"][i]),
                "abs_error_m0": float(abs(predictions["m0"][i] - y[i])),
                "abs_error_m1": float(abs(predictions["m1"][i] - y[i])),
                "abs_error_m2": float(abs(predictions["m2"][i] - y[i])),
                "primary_improvement_m1_minus_m2": float(abs(predictions["m1"][i] - y[i]) - abs(predictions["m2"][i] - y[i])),
                "model_mode": modes[i],
                "training_rows": int(train_counts[i]),
                "last_q7_prior_target_date": f["q7_last_prior_target_date"],
                "last_q80_prior_target_index": f["q80_last_prior_target_index"],
                "last_q90_prior_draws": f["q90_last_prior_draws"],
            })

    blind = np.asarray([r["primary_improvement_m1_minus_m2"] for r in ledger_rows if r["split"] == "blind_oos"], dtype=np.float64)
    effect = float(blind.mean())
    ci = moving_block_ci(blind, BLOCK_LENGTH, REPLICATES, SEED + 1)
    p = block_signflip_p(blind, BLOCK_LENGTH, REPLICATES, SEED)
    supported = effect >= PRACTICAL_THRESHOLD and p < 0.05 and ci[0] > 0.0
    atlas = build_atlas(joined, q7)
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-C5",
        "status": "WALKFORWARD_COMPLETE",
        "decision": "Q90_INCREMENTAL_TRANSFER_LIFT_DEMONSTRATED" if supported else "NO_Q90_INCREMENTAL_TRANSFER_LIFT_DEMONSTRATED",
        "hypothesis": source["preregistration"]["hypothesis"],
        "estimand": source["preregistration"]["estimand"],
        "source": {
            **source["source_hashes"],
            "q7_rows": len(q7), "q80_rows": len(q80), "q90_rows": len(q90),
            "q90_full_catalog_count": 330429, "q90_fixed_sample_count": 700, "q90_family_sample_size": 100,
            "q7_cutoff": "2026-10-24", "q80_cutoff": "2026-11-10", "q90_cutoff": "2026-11-07",
            "contest_315_excluded": True,
        },
        "alignment": {
            "matched_rows": len(joined), "mismatches": 0,
            "q7_split_counts": {"discovery": 1972, "validation": 657, "blind_oos": 657},
            "join_keys": ["prior_draws/target_index", "target_date", "cutoff_date", "actual_quintet"],
            "q7_split_authoritative": True,
        },
        "walkforward": {
            "strict_prior": True, "window": WINDOW, "discovery_prequential_start_offset": 100,
            "discovery_end_offset": DISCOVERY_END, "validation_end_offset": VALIDATION_END,
            "evaluated_targets": {"discovery": 1872, "validation": 657, "blind_oos": 657, "total": 3186},
            "coefficients_frozen_after_discovery": True, "ridge_alpha_fixed": RIDGE_ALPHA,
            "standardization": "training rows only",
            "update_order": "score current target; only then allow its outcome into future rolling state",
        },
        "metrics_by_split": metrics,
        "primary_blind_oos": {
            "comparison": "M1 Q7+Q80 versus M2 Q7+Q80+Q90",
            "mae_improvement": effect, "practical_threshold": PRACTICAL_THRESHOLD,
            "ci95_circular_moving_block": ci, "one_sided_block_signflip_p": p,
            "block_length": BLOCK_LENGTH, "replicates": REPLICATES,
            "confirmatory_endpoint_count": 1,
            "multiplicity_correction": "Not required within this preregistration: one confirmatory endpoint; all other comparisons/correlations descriptive.",
            "criteria_met": supported,
        },
        "behaviour_atlas_descriptive": atlas,
        "limitations": [
            "The target is Q7 formula-universe meta-quality, not the winning quintet or number hits.",
            "Q90 uses a fixed 700-formula sample (100 per family) from 330,429 catalog formulas; it is not a full-catalog replay.",
            "Q90's 20-feature subset was Discovery-selected within Q90; this experiment does not expand it to all 59 source features.",
            "Q7, Q80 and Q90 source cutoffs differ; every joined target is reconciled by target date, cutoff, actual quintet and prior-draw index, and Q7 defines the evaluation split.",
            "Historical Blind OOS is exposed to prior SONAR research and is not virgin prospective evidence.",
            "Atlas correlations, lag-1 values and selector transitions are descriptive and do not establish causality or anticipation.",
        ],
        "governance": {"no_engine_promotion": True, "no_shadow_insertion": True, "no_canonical_archive_mutation": True, "no_merge": True, "protected_prs": [6, 7, 8]},
    }

    ledger_columns = list(ledger_rows[0].keys())
    ledger_path = output_dir / LEDGER.name
    report_path = output_dir / REPORT.name
    write_csv(ledger_path, ledger_rows, ledger_columns)
    write_json(report_path, report)

    script_path = ROOT / "scripts" / "sonar_q141_q90_to_q7_transfer.py"
    test_path = ROOT / "tests" / "test_sonar_q141_q90_to_q7_transfer.py"
    workflow_path = ROOT / ".github" / "workflows" / "q141-c5-q90-to-q7-transfer.yml"
    lineage_paths = {
        "q7_report": Q7_REPORT, "q7_manifest": Q7_MANIFEST, "q7_ledger": Q7_LEDGER,
        "q80_report": Q80_REPORT, "q80_manifest": Q80_MANIFEST, "q80_ledger": Q80_LEDGER,
        "q90_report": Q90_REPORT, "q90_manifest": Q90_MANIFEST, "q90_ledger": Q90_LEDGER,
        "preregistration_json": PREREG, "preregistration_markdown": PREREG_MD,
        "runner": script_path, "tests": test_path, "workflow": workflow_path,
    }
    code_lineage = {}
    for label, path in lineage_paths.items():
        raw = path.read_bytes()
        code_lineage[label] = {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": sha256_bytes(raw), "git_blob_sha1": git_blob_sha1(raw)}
    files = {}
    for label, path in (("report", report_path), ("target_ledger", ledger_path)):
        raw = path.read_bytes()
        files[label] = {
            "path": f"reports/sequence_agent/{path.name}", "bytes": len(raw),
            "sha256": sha256_bytes(raw), "git_blob_sha1": git_blob_sha1(raw),
            "rows": len(ledger_rows) if label == "target_ledger" else None,
        }
    manifest = {
        "schema_version": "1.0", "task_id": "Q141-C5", "status": "OUTPUTS_COMPUTED_PENDING_REMOTE_READBACK",
        "source_archive_git_blob_sha1": Q141_ARCHIVE_BLOB, "q7_archive_git_blob_sha1": Q7_ARCHIVE_BLOB,
        "q90_archive_git_blob_sha1": Q90_ARCHIVE_BLOB, "q90_artifact_sha256": Q90_ARTIFACT_SHA256,
        "target_count": len(ledger_rows), "split_counts": {"discovery": 1872, "validation": 657, "blind_oos": 657},
        "files": files, "code_lineage": code_lineage,
    }
    manifest_path = output_dir / MANIFEST.name
    write_json(manifest_path, manifest)
    checkpoint = {
        "schema_version": "1.0", "task_id": "Q141-C5_CHECKPOINT",
        "status": "OUTPUTS_COMPUTED_PENDING_REMOTE_READBACK", "decision": report["decision"],
        "branch": os.environ.get("GITHUB_REF_NAME", "research/q141-formula-universe-behaviour-mapping-20261112"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_archive_git_blob_sha1": Q141_ARCHIVE_BLOB, "target_count": len(ledger_rows),
        "blind_oos_effect": effect, "blind_oos_ci95": ci, "blind_oos_p": p,
        "report_path": f"reports/sequence_agent/{REPORT.name}",
        "ledger_path": f"reports/sequence_agent/{LEDGER.name}",
        "manifest_path": f"reports/sequence_agent/{MANIFEST.name}",
        "next_action": "Review Q90 incremental transfer and descriptive atlas; if no lift, reconcile full Q90 AST/feature lineage before any new selector hypothesis.",
    }
    write_json(output_dir / CHECKPOINT.name, checkpoint)
    print(json.dumps({
        "task_id": "Q141-C5", "decision": report["decision"], "matched_rows": len(joined),
        "blind_oos_effect": effect, "blind_oos_ci95": ci, "blind_oos_p": p,
        "output_dir": str(output_dir), "report_sha256": sha256_bytes(report_path.read_bytes()),
        "ledger_sha256": sha256_bytes(ledger_path.read_bytes()),
    }, sort_keys=True))

if __name__ == "__main__":
    main()
