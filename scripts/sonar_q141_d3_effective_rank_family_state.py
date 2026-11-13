#!/usr/bin/env python3
"""Q141-D3: pre-target effective-rank state versus formula-family Top-5 advantage."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

Q90_ZIP_SHA256 = "12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"
A6_ZIP_SHA256 = "e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc"
Q90_ARCHIVE_BLOB = "5d2efd70684e918b27d8f06386d545647898336d"
WINDOW = 100
MAX_CENTERED_RANK = 39
BLOCK = 20
BOOTSTRAPS = 20000
SHIFTS = 20000
SEED = 14120261113
PRACTICAL_THRESHOLD = 0.005


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def effective_rank(matrix_40x59: np.ndarray) -> float:
    x = np.asarray(matrix_40x59, dtype=np.float64)
    if x.shape != (40, 59) or not np.isfinite(x).all():
        raise ValueError("expected finite 40x59 feature matrix")
    x = x - x.mean(axis=0, keepdims=True)
    cov = (x.T @ x) / 40.0
    tr = float(np.trace(cov))
    tr2 = float(np.sum(cov * cov))
    if tr2 <= 1e-24:
        return 0.0
    return (tr * tr) / tr2


def build_state(ranks: np.ndarray, window: int = WINDOW):
    ranks = np.asarray(ranks, dtype=np.float64)
    thresholds = np.full(len(ranks), np.nan, dtype=np.float64)
    high = np.full(len(ranks), -1, dtype=np.int8)
    for t in range(window, len(ranks)):
        thresholds[t] = float(np.median(ranks[t-window:t]))
        high[t] = int(ranks[t] > thresholds[t])
    return thresholds, high


def high_minus_low(values: np.ndarray, state: np.ndarray) -> float:
    values = np.asarray(values, dtype=np.float64)
    state = np.asarray(state, dtype=np.int8)
    hi = values[state == 1]
    lo = values[state == 0]
    if len(hi) == 0 or len(lo) == 0:
        return float("nan")
    return float(hi.mean() - lo.mean())


def circular_block_bootstrap_ci(values: np.ndarray, state: np.ndarray,
                                 replicates: int = BOOTSTRAPS,
                                 block: int = BLOCK, seed: int = SEED):
    y = np.asarray(values, dtype=np.float64)
    h = np.asarray(state, dtype=np.int8)
    n = len(y)
    rng = np.random.default_rng(seed)
    nblocks = int(math.ceil(n / block))
    effects = np.empty(replicates, dtype=np.float64)
    starts_all = rng.integers(0, n, size=(replicates, nblocks))
    offsets = np.arange(block, dtype=np.int64)
    for b in range(replicates):
        idx = ((starts_all[b, :, None] + offsets[None, :]) % n).reshape(-1)[:n]
        hb = h[idx]
        yb = y[idx]
        nh = int(hb.sum())
        nl = n - nh
        if nh == 0 or nl == 0:
            effects[b] = np.nan
        else:
            effects[b] = yb[hb == 1].mean() - yb[hb == 0].mean()
    effects = effects[np.isfinite(effects)]
    if len(effects) < int(replicates * 0.99):
        raise RuntimeError("too many degenerate bootstrap replicates")
    return [float(x) for x in np.quantile(effects, [0.025, 0.975])]


def circular_shift_p(values: np.ndarray, state: np.ndarray,
                     replicates: int = SHIFTS, seed: int = SEED + 1):
    y = np.asarray(values, dtype=np.float64)
    h = np.asarray(state, dtype=np.int8)
    n = len(y)
    observed = abs(high_minus_low(y, h))
    rng = np.random.default_rng(seed)
    shifts = rng.integers(1, n, size=replicates)
    extreme = 0
    for s in shifts:
        shifted = np.roll(h, int(s))
        effect = high_minus_low(y, shifted)
        if math.isfinite(effect) and abs(effect) >= observed - 1e-15:
            extreme += 1
    return float((extreme + 1) / (replicates + 1))


def hac_trend_sensitivity(values: np.ndarray, state: np.ndarray, max_lag: int = BLOCK):
    """OLS y ~ intercept + high-state + linear trend; Newey-West HAC, normal p."""
    y = np.asarray(values, dtype=np.float64)
    h = np.asarray(state, dtype=np.float64)
    n = len(y)
    trend = np.linspace(-0.5, 0.5, n, dtype=np.float64)
    x = np.column_stack([np.ones(n), h, trend])
    xtx_inv = np.linalg.pinv(x.T @ x)
    beta = xtx_inv @ (x.T @ y)
    resid = y - x @ beta
    scores = x * resid[:, None]
    meat = scores.T @ scores
    for lag in range(1, min(max_lag, n - 1) + 1):
        weight = 1.0 - lag / (max_lag + 1.0)
        gamma = scores[lag:].T @ scores[:-lag]
        meat += weight * (gamma + gamma.T)
    cov = xtx_inv @ meat @ xtx_inv
    se = math.sqrt(max(float(cov[1, 1]), 0.0))
    z = float(beta[1] / se) if se > 0 else float("inf")
    p = math.erfc(abs(z) / math.sqrt(2.0))
    return {"state_coefficient": float(beta[1]), "hac_se": se,
            "z_normal_approx": z, "p_two_sided_normal_approx": p,
            "trend_coefficient": float(beta[2]), "max_lag": max_lag}


def holm_adjust(pvalues):
    p = np.asarray(pvalues, dtype=np.float64)
    order = np.argsort(p)
    adjusted = np.empty(len(p), dtype=np.float64)
    running = 0.0
    m = len(p)
    for rank, idx in enumerate(order):
        value = min(1.0, (m - rank) * float(p[idx]))
        running = max(running, value)
        adjusted[idx] = running
    return adjusted.tolist()


def validate_inputs(q90_zip: Path, a6_zip: Path, preregistration: Path):
    if sha256_file(q90_zip) != Q90_ZIP_SHA256:
        raise ValueError("Q90 source ZIP SHA-256 mismatch")
    if sha256_file(a6_zip) != A6_ZIP_SHA256:
        raise ValueError("A6 source ZIP SHA-256 mismatch")
    if not preregistration.is_file():
        raise ValueError("preregistration file missing")
    with zipfile.ZipFile(q90_zip) as qz, zipfile.ZipFile(a6_zip) as az:
        with qz.open("adaptive_novelty_feature_matrix.npz") as f:
            npz = np.load(f)
            matrix = np.asarray(npz["feature_matrix"], dtype=np.float32)
            dates = np.asarray(npz["target_dates"]).astype(str)
            cutoffs = np.asarray(npz["cutoff_dates"]).astype(str)
            actual = np.asarray(npz["actual_quintets"], dtype=np.int64)
            archive_blob = str(npz["archive_blob_sha"].item())
            names = np.asarray(npz["feature_names"]).astype(str)
        ledger = pd.read_csv(az.open("q141_a6_target_ledger_2026-11-13.csv"))
        catalog = pd.read_csv(az.open("q141_a6_formula_catalog_2026-11-13.csv"))
        manifest = json.load(az.open("q141_a6_full59_covering_manifest_2026-11-13.json"))
    if archive_blob != Q90_ARCHIVE_BLOB:
        raise ValueError("Q90 NPZ archive blob mismatch")
    if matrix.shape != (3351, 40, 59) or len(names) != 59:
        raise ValueError("unexpected feature matrix shape or feature count")
    if not np.isfinite(matrix).all():
        raise ValueError("non-finite feature values")
    if actual.shape != (3351, 5):
        raise ValueError("unexpected actual quintet array")
    if len(ledger) != 3351 or len(dates) != 3351 or len(cutoffs) != 3351:
        raise ValueError("source row count mismatch")
    if ledger["target_date"].astype(str).tolist() != dates.tolist():
        raise ValueError("target-date alignment mismatch")
    if ledger["cutoff_date"].astype(str).tolist() != cutoffs.tolist():
        raise ValueError("cutoff-date alignment mismatch")
    actual_from_ledger = np.array([
        [int(v) for v in str(s).split()] for s in ledger["actual_quintet"]
    ], dtype=np.int64)
    if not np.array_equal(actual_from_ledger, actual):
        raise ValueError("actual quintet alignment mismatch")
    if not np.all(cutoffs < dates):
        raise ValueError("a cutoff is not strictly before its target")
    if not np.array_equal(ledger["target_index"].to_numpy(), np.arange(3351)):
        raise ValueError("target indices are not contiguous")
    if not np.array_equal(ledger["prior_draws"].to_numpy(), np.arange(3351) + 50):
        raise ValueError("prior draw counts do not reconcile")
    if ledger["split"].value_counts().to_dict() != {
        "discovery": 2011, "validation": 670, "blind_oos": 670
    }:
        raise ValueError("unexpected original split counts")
    expected_counts = {"linear_mean": 650, "pairwise_interaction": 2100, "conditional_gate": 2800}
    scoped_counts = {
        scope: counts.to_dict()
        for scope, counts in catalog.groupby("scope")["formula_type"].value_counts().groupby(level=0)
    }
    if set(scoped_counts) != {"full59", "selected20"} or any(scoped_counts[s] != expected_counts for s in scoped_counts):
        raise ValueError("A6 per-scope formula-type counts mismatch")
    if manifest["formula_sample"]["catalog_rows"] != 11100:
        raise ValueError("A6 manifest formula count mismatch")
    return matrix, dates, cutoffs, actual, ledger, catalog, names


def analyse(q90_zip: Path, a6_zip: Path, preregistration: Path, output_dir: Path):
    matrix, dates, cutoffs, actual, ledger, catalog, feature_names = validate_inputs(
        q90_zip, a6_zip, preregistration
    )
    n = len(matrix)
    ranks = np.array([effective_rank(matrix[t]) / MAX_CENTERED_RANK for t in range(n)])
    thresholds, state = build_state(ranks)
    linear = ledger["full59_linear_top5"].to_numpy(dtype=np.float64)
    interaction = ledger["full59_interaction_top5"].to_numpy(dtype=np.float64)
    gate = ledger["full59_gate_top5"].to_numpy(dtype=np.float64)
    nonlinear = 0.5 * (interaction + gate)
    outcomes = {
        "nonlinear_minus_linear": nonlinear - linear,
        "interaction_minus_linear": interaction - linear,
        "gate_minus_linear": gate - linear,
    }
    valid = np.arange(n) >= WINDOW
    split = ledger["split"].astype(str).to_numpy()
    split_names = ["discovery", "validation", "blind_oos"]
    split_summary = {}
    for sname in split_names:
        mask = valid & (split == sname)
        h = state[mask]
        item = {"targets": int(mask.sum()), "high_state_targets": int((h == 1).sum()),
                "low_state_targets": int((h == 0).sum()),
                "effective_rank_mean": float(ranks[mask].mean()),
                "effective_rank_median": float(np.median(ranks[mask]))}
        for name, yall in outcomes.items():
            y = yall[mask]
            item[name] = {
                "high_mean": float(y[h == 1].mean()),
                "low_mean": float(y[h == 0].mean()),
                "high_minus_low": high_minus_low(y, h),
                "unconditional_mean": float(y.mean()),
            }
        item["family_top5_means"] = {
            "linear": float(linear[mask].mean()),
            "interaction": float(interaction[mask].mean()),
            "gate": float(gate[mask].mean()),
            "nonlinear_equal_family": float(nonlinear[mask].mean()),
            "uniform_per_number_reference": 0.125,
        }
        split_summary[sname] = item

    blind_mask = valid & (split == "blind_oos")
    blind_state = state[blind_mask]
    blind_values = [outcomes[k][blind_mask] for k in outcomes]
    names = list(outcomes.keys())
    raw_ps, endpoint_rows = [], []
    for idx, (name, y) in enumerate(zip(names, blind_values)):
        effect = high_minus_low(y, blind_state)
        ci = circular_block_bootstrap_ci(y, blind_state, seed=SEED + 100 + idx)
        p = circular_shift_p(y, blind_state, seed=SEED + 200 + idx)
        hac = hac_trend_sensitivity(y, blind_state)
        raw_ps.append(p)
        endpoint_rows.append({
            "endpoint": name, "effect_high_minus_low": effect,
            "ci95_circular_block_bootstrap": ci,
            "p_circular_shift_two_sided": p,
            "hac_trend_sensitivity": hac,
            "practical_threshold": PRACTICAL_THRESHOLD,
        })
    adjusted = holm_adjust(raw_ps)
    for row, adj in zip(endpoint_rows, adjusted):
        row["holm_adjusted_p"] = float(adj)
    primary = endpoint_rows[0]
    passed = (
        primary["effect_high_minus_low"] >= PRACTICAL_THRESHOLD
        and primary["ci95_circular_block_bootstrap"][0] > 0
        and primary["holm_adjusted_p"] < 0.05
    )
    decision = "HIGH_EFFECTIVE_RANK_NONLINEAR_LIFT_DEMONSTRATED" if passed else "NO_EFFECTIVE_RANK_CONDITIONAL_LIFT_DEMONSTRATED"

    # Prefix mutation checks: changing all data after t cannot change current
    # matrix-derived state, rolling threshold, or signal at t.
    mutation_checks = []
    for t in [100, 250, 1000, 2000, 3000, 3350]:
        original_rank = ranks[t]
        original_threshold = thresholds[t]
        original_state = state[t]
        altered = matrix.copy()
        if t + 1 < n:
            altered[t+1:] = 0.0
        rank_t_mutated = effective_rank(altered[t]) / MAX_CENTERED_RANK
        threshold_t_mutated = float(np.median(
            np.array([effective_rank(altered[j]) / MAX_CENTERED_RANK for j in range(t-WINDOW, t)])
        ))
        state_t_mutated = int(rank_t_mutated > threshold_t_mutated)
        mutation_checks.append({
            "target_index": t,
            "rank_unchanged": bool(abs(rank_t_mutated - original_rank) < 1e-12),
            "threshold_unchanged": bool(abs(threshold_t_mutated - original_threshold) < 1e-12),
            "state_unchanged": bool(state_t_mutated == original_state),
        })
    if not all(x["rank_unchanged"] and x["threshold_unchanged"] and x["state_unchanged"] for x in mutation_checks):
        raise RuntimeError("future-suffix mutation check failed")

    target_ledger = pd.DataFrame({
        "target_index": np.arange(n),
        "target_date": dates,
        "cutoff_date": cutoffs,
        "prior_draws": ledger["prior_draws"].to_numpy(),
        "split": split,
        "actual_quintet": [" ".join(map(str, row)) for row in actual],
        "effective_rank": ranks,
        "prior100_effective_rank_median": thresholds,
        "high_effective_rank_state": [None if x < 0 else int(x) for x in state],
        "linear_top5": linear,
        "interaction_top5": interaction,
        "gate_top5": gate,
        "nonlinear_minus_linear": outcomes["nonlinear_minus_linear"],
        "interaction_minus_linear": outcomes["interaction_minus_linear"],
        "gate_minus_linear": outcomes["gate_minus_linear"],
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "q141_d3_effective_rank_family_state_target_ledger_2026-11-13.csv"
    target_ledger.to_csv(ledger_path, index=False, float_format="%.12g", lineterminator="\n")

    report = {
        "schema_version": "1.0", "task_id": "Q141-D3",
        "status": "COMPLETED_HISTORICAL_WALK_FORWARD",
        "decision": decision,
        "hypothesis": {
            "signal": "current effective rank of centered 40x59 feature covariance, normalized by 39",
            "state": "current normalized effective rank > median of previous 100 target effective ranks",
            "outcome": "mean(pairwise_interaction_top5, conditional_gate_top5) - linear_mean_top5",
            "primary_minimum_effect": PRACTICAL_THRESHOLD,
            "window": WINDOW, "direction": "high effective rank favours nonlinear families"
        },
        "source": {
            "q90_zip_sha256": Q90_ZIP_SHA256,
            "a6_zip_sha256": A6_ZIP_SHA256,
            "q90_archive_blob_sha1": Q90_ARCHIVE_BLOB,
            "matrix_shape": list(matrix.shape), "matrix_dtype": "float32",
            "feature_count": int(len(feature_names)), "feature_names": feature_names.tolist(),
            "target_count": n,
            "a6_formula_counts_by_scope": {scope: counts.to_dict() for scope, counts in catalog.groupby("scope")["formula_type"].value_counts().groupby(level=0)},
        },
        "walkforward": {
            "original_split_counts": {"discovery": 2011, "validation": 670, "blind_oos": 670},
            "warmup_targets": WINDOW,
            "evaluated_split_counts": {
                k: v["targets"] for k, v in split_summary.items()
            },
            "first_target": str(dates[0]), "last_target": str(dates[-1]),
            "strict_prior_alignment": True,
            "historical_blind_oos_not_virgin": True,
        },
        "split_results": split_summary,
        "blind_oos_inference": {
            "method": "20,000 circular moving-block bootstrap CI (block=20); 20,000 circular shifts of state relative to outcomes; Holm across three registered endpoints",
            "endpoints": endpoint_rows,
            "holm_family_size": len(endpoint_rows),
            "acceptance_rule": "primary effect >= 0.005 AND 95% CI lower > 0 AND Holm p < 0.05",
            "accepted": bool(passed),
        },
        "integrity": {
            "all_feature_values_finite": True,
            "matrix_ledger_dates_cutoffs_actuals_exactly_aligned": True,
            "all_cutoffs_strictly_before_targets": True,
            "prior_draws_equal_target_index_plus_50": True,
            "future_suffix_mutation_checks": mutation_checks,
            "formula_type_counts_verified": True,
            "target_level_inference_only": True,
        },
        "limitations": [
            "Historical Blind OOS has been exposed to prior SONAR research and is not virgin prospective evidence.",
            "Effective rank is a descriptive state statistic over 40 candidate numbers, not a causal or probability calibration.",
            "A6 formula-type aggregates are means over dependent deterministic formula samples (650 linear, 2100 interaction, 2800 gate formulas).",
            "The endpoint is per-number Top-5 hit share, not exact five-number ticket likelihood.",
            "Holm correction covers the three D3 endpoints only, not the full Q00-Q141 research family.",
        ],
        "next_action": "Keep D3 research-only. If the association is not confirmed, do not reverse the state definition; proceed with source-harmonized typed AST semantics and a prospective preregistration on new targets.",
    }
    report_path = output_dir / "q141_d3_effective_rank_family_state_report_2026-11-13.json"
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    prereg_bytes = preregistration.read_bytes()
    file_entries = {}
    for p in [preregistration, report_path, ledger_path]:
        data = p.read_bytes()
        file_entries[p.name] = {
            "path": p.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob_sha1": git_blob_sha1(data),
        }
    manifest = {
        "schema_version": "1.0", "task_id": "Q141-D3",
        "source_q90_zip_sha256": Q90_ZIP_SHA256,
        "source_a6_zip_sha256": A6_ZIP_SHA256,
        "preregistration_sha256": hashlib.sha256(prereg_bytes).hexdigest(),
        "target_rows": len(target_ledger),
        "evaluated_targets": int(valid.sum()),
        "files": file_entries,
    }
    manifest_path = output_dir / "q141_d3_effective_rank_family_state_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0", "task_id": "Q141-D3",
        "status": "LOCAL_REPLAY_COMPLETE_PENDING_REMOTE_READBACK",
        "decision": decision,
        "report_path": report_path.name, "ledger_path": ledger_path.name,
        "manifest_path": manifest_path.name,
        "report_sha256": sha256_file(report_path),
        "ledger_sha256": sha256_file(ledger_path),
        "manifest_sha256": sha256_file(manifest_path),
        "next_action": report["next_action"],
        "governance": {"research_only": True, "canonical_archive_mutated": False,
                       "q60_or_b11_freeze_mutated": False, "engine_promoted": False,
                       "merge": False, "protected_prs_6_7_8_untouched": True},
    }
    checkpoint_path = output_dir / "q141_d3_effective_rank_family_state_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report, target_ledger, manifest, checkpoint


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q90-zip", type=Path, required=True)
    ap.add_argument("--a6-zip", type=Path, required=True)
    ap.add_argument("--preregistration", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    report, ledger, manifest, checkpoint = analyse(
        args.q90_zip, args.a6_zip, args.preregistration, args.output_dir
    )
    print(json.dumps({
        "decision": report["decision"],
        "split_counts": report["walkforward"]["evaluated_split_counts"],
        "blind_oos": report["blind_oos_inference"]["endpoints"],
        "ledger_rows": len(ledger),
        "manifest_files": len(manifest["files"]),
        "checkpoint_status": checkpoint["status"],
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
