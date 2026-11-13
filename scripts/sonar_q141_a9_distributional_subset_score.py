#!/usr/bin/env python3
"""Q141-A9: calibrated proper scoring of complete 5-of-40 subsets from Q141-A7 scores."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
import sonar_q141_a7_fresh59_behaviour as a7

N_NUMBERS = 40
DRAW_SIZE = 5
EXPECTED_ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_TARGETS = 3356
EXPECTED_SPLITS = {"discovery": 2014, "validation": 671, "blind_oos": 671}
TEMPERATURE_GRID = [0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 13.0, 21.0, 34.0]
BLOCK = 20
REPLICATES = 20_000
SEED = 14111319


def log_esym(log_weights: np.ndarray, degree: int) -> float:
    """Log elementary symmetric polynomial using a stable O(n*k) recurrence."""
    x = np.asarray(log_weights, dtype=np.float64)
    if degree < 0 or degree > len(x):
        raise ValueError("invalid elementary-symmetric degree")
    dp = np.full(degree + 1, -np.inf, dtype=np.float64)
    dp[0] = 0.0
    for i, value in enumerate(x):
        for j in range(min(degree, i + 1), 0, -1):
            dp[j] = np.logaddexp(dp[j], dp[j - 1] + value)
    return float(dp[degree])


def log_esym_and_marginals(log_weights: np.ndarray, degree: int):
    """Return log e_k(exp(x)) and exact fixed-size subset inclusion marginals."""
    x = np.asarray(log_weights, dtype=np.float64)
    n = len(x)
    if degree < 0 or degree > n:
        raise ValueError("invalid elementary-symmetric degree")
    neg_inf = -np.inf
    prefix = np.full((n + 1, degree + 1), neg_inf, dtype=np.float64)
    suffix = np.full((n + 1, degree + 1), neg_inf, dtype=np.float64)
    prefix[0, 0] = 0.0
    suffix[n, 0] = 0.0
    for i in range(n):
        prefix[i + 1, 0] = 0.0
        for j in range(1, min(degree, i + 1) + 1):
            prefix[i + 1, j] = np.logaddexp(prefix[i, j], prefix[i, j - 1] + x[i])
    for i in range(n - 1, -1, -1):
        suffix[i, 0] = 0.0
        for j in range(1, min(degree, n - i) + 1):
            suffix[i, j] = np.logaddexp(suffix[i + 1, j], suffix[i + 1, j - 1] + x[i])
    log_z = float(prefix[n, degree])
    marginals = np.zeros(n, dtype=np.float64)
    for i in range(n):
        terms = []
        for left_degree in range(degree):
            right_degree = degree - 1 - left_degree
            if left_degree <= i and right_degree <= n - i - 1:
                terms.append(prefix[i, left_degree] + suffix[i + 1, right_degree])
        if terms:
            log_excluding = float(np.logaddexp.reduce(np.asarray(terms)))
            marginals[i] = math.exp(float(x[i]) + log_excluding - log_z)
    return log_z, marginals


def subset_nll(scores: np.ndarray, actual: tuple[int, ...], temperature: float) -> float:
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    x = np.asarray(scores, dtype=np.float64) / temperature
    if x.shape != (N_NUMBERS,) or not np.isfinite(x).all():
        raise ValueError("scores must be 40 finite values")
    chosen = np.asarray(actual, dtype=np.int64) - 1
    if len(chosen) != DRAW_SIZE or len(set(chosen.tolist())) != DRAW_SIZE or np.any(chosen < 0) or np.any(chosen >= N_NUMBERS):
        raise ValueError("actual must be a valid 5-of-40 subset")
    return log_esym(x, DRAW_SIZE) - float(x[chosen].sum())


def subset_marginals(scores: np.ndarray, temperature: float) -> np.ndarray:
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and positive")
    x = np.asarray(scores, dtype=np.float64) / temperature
    if x.shape != (N_NUMBERS,) or not np.isfinite(x).all():
        raise ValueError("scores must be 40 finite values")
    _, p = log_esym_and_marginals(x, DRAW_SIZE)
    return p


def choose_temperature(score_rows: np.ndarray, actual_rows: list[tuple[int, ...]], indices: list[int]):
    """Fit temperature on Discovery only; deterministic grid search."""
    if not indices:
        raise ValueError("temperature calibration requires non-empty Discovery")
    results = []
    for temperature in TEMPERATURE_GRID:
        losses = [subset_nll(score_rows[i], actual_rows[i], temperature) for i in indices]
        results.append({"temperature": temperature, "mean_joint_nll": float(np.mean(losses))})
    best = min(results, key=lambda row: (row["mean_joint_nll"], row["temperature"]))
    return float(best["temperature"]), results


def build_score_rows(matrix: np.ndarray):
    family_scores = np.stack(
        [matrix[:, :, a7.FAMILY_INDICES[name]].mean(axis=2) for name in a7.FAMILIES],
        axis=1,
    )
    n_targets = len(matrix)
    ranks = np.empty((n_targets, len(a7.FAMILIES), N_NUMBERS), dtype=np.int16)
    for t in range(n_targets):
        for f in range(len(a7.FAMILIES)):
            ranks[t, f] = a7.rank_desc(family_scores[t, f])
    m0 = family_scores.mean(axis=1)
    m1 = np.empty((n_targets, N_NUMBERS), dtype=np.float64)
    weight_rows = np.empty((n_targets, len(a7.FAMILIES)), dtype=np.float64)
    for t in range(n_targets):
        if t >= 5:
            weights, _ = a7.weights_from_history(ranks[t - 5:t])
        else:
            weights = np.full(len(a7.FAMILIES), 1.0 / len(a7.FAMILIES))
        weight_rows[t] = weights
        m1[t] = np.sum(family_scores[t] * weights[:, None], axis=0)
    return m0, m1, weight_rows


def score_all_targets(m0, m1, actual_rows, t0, t1):
    n = len(actual_rows)
    out = {
        "m0_joint_nll": np.empty(n),
        "m1_joint_nll": np.empty(n),
        "uniform_joint_nll": np.full(n, math.log(math.comb(N_NUMBERS, DRAW_SIZE))),
        "m0_marginal_brier": np.empty(n),
        "m1_marginal_brier": np.empty(n),
        "uniform_marginal_brier": np.empty(n),
    }
    uniform_p = DRAW_SIZE / N_NUMBERS
    for i, actual in enumerate(actual_rows):
        y = np.zeros(N_NUMBERS, dtype=np.float64)
        y[np.asarray(actual, dtype=np.int64) - 1] = 1.0
        out["m0_joint_nll"][i] = subset_nll(m0[i], actual, t0)
        out["m1_joint_nll"][i] = subset_nll(m1[i], actual, t1)
        p0 = subset_marginals(m0[i], t0)
        p1 = subset_marginals(m1[i], t1)
        out["m0_marginal_brier"][i] = float(np.mean((p0 - y) ** 2))
        out["m1_marginal_brier"][i] = float(np.mean((p1 - y) ** 2))
        out["uniform_marginal_brier"][i] = float(np.mean((uniform_p - y) ** 2))
    return out


def holm_adjust(p_values):
    p = np.asarray(p_values, dtype=np.float64)
    order = np.argsort(p)
    adjusted = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * float(p[idx]))
        adjusted[idx] = min(1.0, running)
    return adjusted.tolist()


def block_signflip_one_sided(values: np.ndarray, seed: int, replicates: int = REPLICATES):
    d = np.asarray(values, dtype=np.float64)
    blocks = np.asarray([d[i:i + BLOCK].sum() for i in range(0, len(d), BLOCK)])
    observed = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(replicates, len(blocks)))
    simulated = (signs * blocks).sum(axis=1) / len(d)
    p = (int(np.sum(simulated >= observed - 1e-15)) + 1) / (replicates + 1)
    return float(p), len(blocks), observed


def circular_block_ci(values: np.ndarray, seed: int, replicates: int = REPLICATES):
    d = np.asarray(values, dtype=np.float64)
    n = len(d)
    rng = np.random.default_rng(seed)
    n_blocks = math.ceil(n / BLOCK)
    offsets = np.arange(BLOCK)
    samples = np.empty(replicates, dtype=np.float64)
    for start in range(0, replicates, 1000):
        batch = min(1000, replicates - start)
        starts = rng.integers(0, n, size=(batch, n_blocks))
        idx = (starts[:, :, None] + offsets[None, None, :]) % n
        flat = idx.reshape(batch, -1)[:, :n]
        samples[start:start + batch] = d[flat].mean(axis=1)
    return [float(x) for x in np.quantile(samples, [0.025, 0.975])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", default="data/storico_daily.csv")
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dates, draws = a7.load_archive(args.archive)
    archive_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:data/storico_daily.csv"], text=True
    ).strip()
    if archive_blob != EXPECTED_ARCHIVE_BLOB:
        raise SystemExit(f"A9_BLOCKED: archive blob {archive_blob} != pinned {EXPECTED_ARCHIVE_BLOB}")
    if len(draws) != 3406 or dates[-1] != "2026-11-12":
        raise SystemExit("A9_BLOCKED: archive count/date mismatch")

    matrix = a7.compute_feature_matrix(draws)
    if matrix.shape != (EXPECTED_TARGETS, N_NUMBERS, 59) or not np.isfinite(matrix).all():
        raise SystemExit(f"A9_BLOCKED: unexpected matrix shape/values {matrix.shape}")
    m0, m1, weights = build_score_rows(matrix)
    actual_rows = draws[a7.MIN_HISTORY:]
    if len(actual_rows) != EXPECTED_TARGETS:
        raise SystemExit("A9_BLOCKED: target count mismatch")

    split_indices = {name: [i for i in range(EXPECTED_TARGETS) if a7.split_name(i, EXPECTED_TARGETS) == name]
                     for name in EXPECTED_SPLITS}
    observed_counts = {name: len(indices) for name, indices in split_indices.items()}
    if observed_counts != EXPECTED_SPLITS:
        raise SystemExit(f"A9_BLOCKED: split mismatch {observed_counts}")

    t0, grid0 = choose_temperature(m0, actual_rows, split_indices["discovery"])
    t1, grid1 = choose_temperature(m1, actual_rows, split_indices["discovery"])
    scored = score_all_targets(m0, m1, actual_rows, t0, t1)

    split_metrics = {}
    for name, indices in split_indices.items():
        split_metrics[name] = {
            "targets": len(indices),
            "m0_joint_nll": float(np.mean(scored["m0_joint_nll"][indices])),
            "m1_joint_nll": float(np.mean(scored["m1_joint_nll"][indices])),
            "uniform_joint_nll": float(np.mean(scored["uniform_joint_nll"][indices])),
            "m0_marginal_brier": float(np.mean(scored["m0_marginal_brier"][indices])),
            "m1_marginal_brier": float(np.mean(scored["m1_marginal_brier"][indices])),
            "uniform_marginal_brier": float(np.mean(scored["uniform_marginal_brier"][indices])),
        }

    blind = split_indices["blind_oos"]
    endpoints = {
        "m1_vs_m0_joint_nll_gain": scored["m0_joint_nll"][blind] - scored["m1_joint_nll"][blind],
        "m1_vs_uniform_joint_nll_gain": scored["uniform_joint_nll"][blind] - scored["m1_joint_nll"][blind],
        "m0_vs_uniform_joint_nll_gain": scored["uniform_joint_nll"][blind] - scored["m0_joint_nll"][blind],
        "m1_vs_m0_marginal_brier_gain": scored["m0_marginal_brier"][blind] - scored["m1_marginal_brier"][blind],
        "m1_vs_uniform_marginal_brier_gain": scored["uniform_marginal_brier"][blind] - scored["m1_marginal_brier"][blind],
        "m0_vs_uniform_marginal_brier_gain": scored["uniform_marginal_brier"][blind] - scored["m0_marginal_brier"][blind],
    }
    inference = {}
    raw_p = []
    for i, (name, values) in enumerate(endpoints.items()):
        p, n_blocks, mean_gain = block_signflip_one_sided(values, SEED + i)
        ci = circular_block_ci(values, SEED + 100 + i)
        raw_p.append(p)
        inference[name] = {
            "mean_gain": mean_gain,
            "ci95_circular_block_bootstrap": ci,
            "p_one_sided_block_signflip": p,
            "block_count": n_blocks,
            "block_length": BLOCK,
            "replicates": REPLICATES,
        }
    adjusted = holm_adjust(raw_p)
    for (name, _), p_adj in zip(endpoints.items(), adjusted):
        inference[name]["p_holm_six_endpoint_family"] = p_adj

    primary = inference["m1_vs_m0_joint_nll_gain"]
    decision = "NO_INCREMENTAL_JOINT_SUBSET_SCORE_DEMONSTRATED"
    if primary["mean_gain"] >= 0.005 and primary["ci95_circular_block_bootstrap"][0] > 0 and primary["p_holm_six_endpoint_family"] < 0.05:
        decision = "HISTORICAL_SIGNAL_REQUIRES_NEW_PROSPECTIVE_CONFIRMATION"

    rows = []
    for i, actual in enumerate(actual_rows):
        target_index = i + a7.MIN_HISTORY
        rows.append({
            "target_index": i,
            "target_date": dates[target_index],
            "cutoff_date": dates[target_index - 1],
            "prior_draws": target_index,
            "split": a7.split_name(i, EXPECTED_TARGETS),
            "actual_quintet": " ".join(map(str, actual)),
            "m0_joint_nll": f"{scored['m0_joint_nll'][i]:.12f}",
            "m1_joint_nll": f"{scored['m1_joint_nll'][i]:.12f}",
            "uniform_joint_nll": f"{scored['uniform_joint_nll'][i]:.12f}",
            "m0_marginal_brier": f"{scored['m0_marginal_brier'][i]:.12f}",
            "m1_marginal_brier": f"{scored['m1_marginal_brier'][i]:.12f}",
            "uniform_marginal_brier": f"{scored['uniform_marginal_brier'][i]:.12f}",
            "m1_vs_m0_joint_gain": f"{scored['m0_joint_nll'][i] - scored['m1_joint_nll'][i]:.12f}",
            "m1_family_weights_json": json.dumps(weights[i].tolist(), separators=(",", ":")),
        })
    ledger_path = out_dir / "q141_a9_distributional_subset_score_target_ledger_2026-11-13.csv"
    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-A9-DISTRIBUTIONAL-SUBSET-SCORE",
        "status": "COMPLETED_HISTORICAL_EXPLORATORY_WALK_FORWARD",
        "decision": decision,
        "source": {
            "archive_blob_sha1": archive_blob,
            "draw_count": len(draws),
            "first_date": dates[0],
            "last_date": dates[-1],
            "feature_matrix_shape": list(matrix.shape),
            "feature_count": 59,
            "source_scorer": "Q141-A7 exact family definitions and strict-prior feature builder",
        },
        "design": {
            "targets": EXPECTED_TARGETS,
            "split_counts": observed_counts,
            "models": ["M0 equal-family", "M1 five-prior-target stability-weighted", "U exact uniform 5-of-40"],
            "subset_distribution": "P(S|s,T) proportional to exp(sum(s_i/T for i in S)); normalized by the fifth elementary symmetric polynomial",
            "temperature_grid": TEMPERATURE_GRID,
            "temperature_fit_split": "Discovery only; frozen before Validation and Blind OOS",
            "primary_endpoint": "Blind OOS joint NLL gain M1 versus M0; positive favours M1",
            "practical_threshold_primary_nats_per_draw": 0.005,
            "secondary_endpoints": list(endpoints.keys())[1:],
            "block_length": BLOCK,
            "bootstrap_replicates": REPLICATES,
            "signflip_replicates": REPLICATES,
            "holm_family_size": len(endpoints),
        },
        "calibration": {
            "m0_selected_temperature": t0,
            "m1_selected_temperature": t1,
            "m0_discovery_grid": grid0,
            "m1_discovery_grid": grid1,
        },
        "split_metrics": split_metrics,
        "blind_oos_inference": inference,
        "integrity": {
            "strict_prior_feature_builder": True,
            "score_before_state_update": True,
            "archive_blob_pinned": True,
            "matrix_finite": bool(np.isfinite(matrix).all()),
            "all_cutoffs_precede_targets": all(dates[i + a7.MIN_HISTORY - 1] < dates[i + a7.MIN_HISTORY] for i in range(EXPECTED_TARGETS)),
            "temperature_fit_uses_discovery_only": True,
            "future_suffix_invariance_tested_in_unit_tests": True,
            "deterministic_seed": SEED,
        },
        "limitations": [
            "Historical Blind OOS has been exposed to earlier SONAR research; this is exploratory, not virgin confirmatory evidence.",
            "Holm correction covers the six A9 endpoints only, not the full Q00-Q141 research family.",
            "The fixed-size exponential-family distribution is a score-to-probability representation, not a physical model of the lottery.",
            "Temperature calibration is selected on Discovery and may be misspecified; Discovery metrics are calibration-sample diagnostics.",
            "The marginal Brier score evaluates 40 inclusion marginals and does not replace the joint subset log score.",
            "No B11 prospective outcome is read or used; no existing prediction freeze is changed.",
        ],
    }
    report_path = out_dir / "q141_a9_distributional_subset_score_report_2026-11-13.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    outputs = [ledger_path, report_path]
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-A9-DISTRIBUTIONAL-SUBSET-SCORE",
        "status": "COMPLETED_WALK_FORWARD_OUTPUTS",
        "source_archive_blob_sha1": archive_blob,
        "source_draw_count": len(draws),
        "source_last_date": dates[-1],
        "outputs": {
            p.name: {
                "bytes": p.stat().st_size,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "git_blob_sha1": subprocess.check_output(["git", "hash-object", str(p)], text=True).strip(),
            } for p in outputs
        },
    }
    manifest_path = out_dir / "q141_a9_distributional_subset_score_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checkpoint = {
        "schema_version": "1.0",
        "cycle": 19,
        "task_id": "Q141-A9-DISTRIBUTIONAL-SUBSET-SCORE",
        "status": "COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
        "decision": decision,
        "source_archive_blob_sha1": archive_blob,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "report_path": str(report_path),
        "ledger_path": str(ledger_path),
        "manifest_path": str(manifest_path),
        "next_action": "Review the exploratory joint-subset scoring results; keep B11 unchanged and do not promote. Any positive historical result requires a separately preregistered prospective replication.",
        "governance": {
            "pr6_untouched": True, "pr7_untouched": True, "pr8_untouched": True,
            "pr89_untouched": True, "no_merge": True, "no_rebase": True,
            "no_canonical_archive_mutation": True, "no_b11_mutation": True, "no_engine_promotion": True,
        },
    }
    checkpoint_path = out_dir / "q141_a9_distributional_subset_score_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cycle_report = {
        "cycle": 19,
        "date": "2026-11-13",
        "task": "Q141-A9 distributional subset scoring",
        "status": "COMPLETED_HISTORICAL_EXPLORATORY_WALK_FORWARD",
        "decision": decision,
        "split_metrics": split_metrics,
        "blind_oos_inference": inference,
        "limitations": report["limitations"],
        "next_action": checkpoint["next_action"],
    }
    cycle_report_path = out_dir / "q141_cycle_report_2026-11-13_run19.json"
    cycle_report_path.write_text(json.dumps(cycle_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": decision,
        "split_metrics": split_metrics,
        "blind_oos_inference": inference,
        "temperatures": {"m0": t0, "m1": t1},
        "outputs": [str(p) for p in [report_path, ledger_path, manifest_path, checkpoint_path, cycle_report_path]],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
