#!/usr/bin/env python3
"""FD-06: audit Q90 pooled P5 logistic ranking against the exact order-statistic baseline.

Input files are extracted from the immutable Q90 GitHub Actions artifact bundle:
  adaptive_novelty_feature_matrix.npz
  q90_target_ledger.csv

All target features are checked against their strict-prior cutoff metadata. The
primary holdout reproduces the previously reported train-through-2024-12-31,
test-2025-01-01..2026-11-04 logistic model. Secondary Q90 chronological split
results use one fixed C=.05 model fitted at each split boundary; the discovery
split uses a 200-target warm-up and evaluates the remainder of discovery.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
from datetime import date, timedelta
import numpy as np
import pandas as pd
from scipy.stats import binomtest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

EXPECTED_ARCHIVE_SHA = "dc555356fe6543e17c3d7c91969da10491fe8b4e"
EXPECTED_MATRIX_SHA256 = "3520db2c9441b9fc48bd091c746564a6de261b18a0cb2eea293bb465bbcfd824"
EXPECTED_LEDGER_SHA256 = "290a4da31f05bb4d73f4155ec1408b0a0c2e9e6df1479fafb6bd1c410c285404"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def exact_order_stat_baseline() -> dict:
    den = math.comb(40, 5)
    pmf = {n: math.comb(n - 1, 4) / den for n in range(5, 41)}
    return {
        "pmf_formula": "P(P5=n)=C(n-1,4)/C(40,5), n=5..40",
        "top5": sum(pmf[n] for n in range(36, 41)),
        "top10": sum(pmf[n] for n in range(31, 41)),
        "top20": sum(pmf[n] for n in range(21, 41)),
        "mean_rank": sum((41 - n) * pmf[n] for n in range(5, 41)),
    }


def validate_inputs(npz_path: Path, ledger_path: Path, expected_archive_sha: str) -> tuple:
    matrix_sha = sha256(npz_path)
    ledger_sha = sha256(ledger_path)
    if EXPECTED_MATRIX_SHA256 and matrix_sha != EXPECTED_MATRIX_SHA256:
        raise ValueError(f"feature matrix SHA256 mismatch: {matrix_sha}")
    if EXPECTED_LEDGER_SHA256 and ledger_sha != EXPECTED_LEDGER_SHA256:
        raise ValueError(f"target ledger SHA256 mismatch: {ledger_sha}")
    with np.load(npz_path, allow_pickle=False) as z:
        required = {"feature_matrix", "target_dates", "cutoff_dates", "actual_quintets", "feature_names", "archive_blob_sha"}
        if not required.issubset(set(z.files)):
            raise ValueError(f"NPZ missing keys: {sorted(required-set(z.files))}")
        X = z["feature_matrix"]
        dates = z["target_dates"].astype(str)
        cutoffs = z["cutoff_dates"].astype(str)
        nums = z["actual_quintets"].astype(int)
        names = z["feature_names"].astype(str).tolist()
        archive_sha = str(z["archive_blob_sha"].item())
    if archive_sha != expected_archive_sha:
        raise ValueError(f"archive blob SHA mismatch: {archive_sha}")
    if X.shape != (3348, 40, 59) or nums.shape != (3348, 5) or len(dates) != 3348 or len(cutoffs) != 3348 or len(names) != 59:
        raise ValueError(f"unexpected shapes: X={X.shape}, nums={nums.shape}, dates={len(dates)}, cutoffs={len(cutoffs)}, names={len(names)}")
    if len(set(names)) != 59:
        raise ValueError("feature names are not unique")
    if not np.isfinite(X).all():
        raise ValueError("feature matrix contains NaN or infinite values")
    dts = pd.to_datetime(dates)
    cts = pd.to_datetime(cutoffs)
    if not (dts[1:].values > dts[:-1].values).all():
        raise ValueError("target dates are not strictly increasing")
    if not (cts.values == (dts - pd.Timedelta(days=1)).values).all():
        raise ValueError("a target cutoff is not the preceding calendar date")
    if not ((nums[:, 1:] > nums[:, :-1]).all() and (nums >= 1).all() and (nums <= 40).all()):
        raise ValueError("actual quintets are not five distinct ascending values in 1..40")
    ledger = pd.read_csv(ledger_path, dtype={"target_date": str, "cutoff_date": str, "actual_quintet": str})
    if len(ledger) != 3348:
        raise ValueError(f"target ledger row count mismatch: {len(ledger)}")
    quintets = [" ".join(map(str, row)) for row in nums]
    if not np.array_equal(ledger.target_date.to_numpy(), dates):
        raise ValueError("target dates do not align with Q90 ledger")
    if not np.array_equal(ledger.cutoff_date.to_numpy(), cutoffs):
        raise ValueError("cutoff dates do not align with Q90 ledger")
    if not np.array_equal(ledger.actual_quintet.to_numpy(), np.asarray(quintets)):
        raise ValueError("actual quintets do not align with Q90 ledger")
    expected_prior = 50 + np.arange(3348)
    if not np.array_equal(ledger.prior_draws.to_numpy(dtype=int), expected_prior):
        raise ValueError("prior_draws lineage is not consistent with the 50-draw warm-up")
    expected_split = np.array(["discovery"] * 2009 + ["validation"] * 670 + ["blind_oos"] * 669)
    if not np.array_equal(ledger.split.to_numpy(), expected_split):
        raise ValueError("Q90 split labels/counts mismatch")
    audit = {
        "archive_blob_sha": archive_sha,
        "matrix_sha256": matrix_sha,
        "ledger_sha256": ledger_sha,
        "targets": int(len(dates)),
        "feature_matrix_shape": list(X.shape),
        "feature_count": int(len(names)),
        "first_target": dates[0],
        "last_target": dates[-1],
        "strict_prior_cutoff_all_targets": True,
        "target_cutoff_is_previous_calendar_date": True,
        "target_ledger_dates_cutoffs_quintets_aligned": True,
        "prior_draws_consistent": True,
        "q90_split_counts": {"discovery": 2009, "validation": 670, "blind_oos": 669},
        "finite_feature_matrix": True,
    }
    return X, dates, cutoffs, nums, names, ledger, audit


def fit_ranks(X: np.ndarray, nums: np.ndarray, train_idx: np.ndarray, test_idx: np.ndarray, C: float = 0.05) -> np.ndarray:
    y = (nums.max(axis=1)[:, None] == np.arange(1, 41)[None, :]).astype(np.int8)
    X_train = X[train_idx].reshape(-1, X.shape[-1])
    y_train = y[train_idx].reshape(-1)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X[test_idx].reshape(-1, X.shape[-1]))
    model = LogisticRegression(C=C, max_iter=300, solver="lbfgs")
    model.fit(X_train_s, y_train)
    prob = model.predict_proba(X_test_s)[:, 1].reshape(-1, 40)
    order = np.argsort(-prob, axis=1, kind="stable")  # candidate-number ascending breaks exact ties
    ranks = np.empty_like(order)
    ranks[np.arange(len(order))[:, None], order] = np.arange(1, 41)[None, :]
    max_actual = nums[test_idx].max(axis=1)
    return ranks[np.arange(len(test_idx)), max_actual - 1]


def metrics(model_rank: np.ndarray, max_actual: np.ndarray) -> dict:
    baseline_rank = 41 - max_actual
    model_top5 = model_rank <= 5
    base_top5 = baseline_rank <= 5
    diff = model_top5.astype(int) - base_top5.astype(int)
    return {
        "targets": int(len(max_actual)),
        "model": {
            "top1": float(np.mean(model_rank <= 1)), "top5": float(np.mean(model_rank <= 5)),
            "top10": float(np.mean(model_rank <= 10)), "top20": float(np.mean(model_rank <= 20)),
            "mean_rank": float(np.mean(model_rank)), "top1_hits": int(np.sum(model_rank <= 1)),
            "top5_hits": int(np.sum(model_rank <= 5)), "top10_hits": int(np.sum(model_rank <= 10)),
            "top20_hits": int(np.sum(model_rank <= 20)),
        },
        "numeric_order_baseline": {
            "top1": float(np.mean(baseline_rank <= 1)), "top5": float(np.mean(baseline_rank <= 5)),
            "top10": float(np.mean(baseline_rank <= 10)), "top20": float(np.mean(baseline_rank <= 20)),
            "mean_rank": float(np.mean(baseline_rank)), "top1_hits": int(np.sum(baseline_rank <= 1)),
            "top5_hits": int(np.sum(baseline_rank <= 5)), "top10_hits": int(np.sum(baseline_rank <= 10)),
            "top20_hits": int(np.sum(baseline_rank <= 20)),
        },
        "top5_delta_model_minus_numeric": float(np.mean(diff)),
        "rank_delta_model_minus_numeric": float(np.mean(model_rank - baseline_rank)),
        "paired_top5_model_only_wins": int(np.sum(diff == 1)),
        "paired_top5_numeric_only_wins": int(np.sum(diff == -1)),
        "paired_top5_discordant": int(np.sum(diff != 0)),
        "top5_difference_per_target": diff.tolist(),
        "rank_difference_per_target": (model_rank - baseline_rank).astype(int).tolist(),
    }


def block_signflip_p(diff: np.ndarray, block: int, reps: int, seed: int) -> dict:
    sums = np.asarray([np.sum(diff[i:i+block]) for i in range(0, len(diff), block)], dtype=float)
    observed = float(np.sum(sums))
    rng = np.random.default_rng(seed)
    extreme = 0
    for start in range(0, reps, 10000):
        nrep = min(10000, reps - start)
        signs = rng.choice(np.array([-1, 1], dtype=np.int8), size=(nrep, len(sums)))
        permuted = signs @ sums
        extreme += int(np.sum(np.abs(permuted) >= abs(observed)))
    return {"method": "two-sided block sign-flip permutation on non-overlapping chronological block sums", "block_length": block,
            "blocks": int(len(sums)), "replicates": reps, "seed": seed, "observed_hit_delta": int(observed),
            "p_two_sided": float((extreme + 1) / (reps + 1))}


def circular_mbb_ci(values: np.ndarray, block: int, reps: int, seed: int) -> list[float]:
    rng = np.random.default_rng(seed)
    n = len(values)
    out = np.empty(reps, dtype=float)
    offsets = np.arange(block)
    for r in range(reps):
        idx = []
        while len(idx) < n:
            s = int(rng.integers(0, n))
            idx.extend(((s + offsets) % n).tolist())
        out[r] = np.mean(values[np.asarray(idx[:n], dtype=int)])
    out.sort()
    return [float(out[int(0.025 * reps)]), float(out[int(0.975 * reps)])]


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    adjusted = {}
    running = 0.0
    for i, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p))
        adjusted[key] = float(running)
    return adjusted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", type=Path, required=True, help="Q89 adaptive novelty feature matrix NPZ")
    ap.add_argument("--ledger", type=Path, required=True, help="Q90 target ledger CSV")
    ap.add_argument("--output", type=Path, required=True, help="FD-06 JSON output path")
    ap.add_argument("--expected-archive-sha", default=EXPECTED_ARCHIVE_SHA)
    args = ap.parse_args()

    X, dates, cutoffs, nums, names, ledger, integrity = validate_inputs(args.matrix, args.ledger, args.expected_archive_sha)
    date_index = pd.to_datetime(dates)
    max_actual = nums.max(axis=1)
    q90_splits = {"discovery": (0, 2009), "validation": (2009, 2679), "blind_oos": (2679, 3348)}
    split_eval = {}
    split_tests = {}
    for j, (name, (start, end)) in enumerate(q90_splits.items()):
        if name == "discovery":
            train_idx = np.arange(0, 200)
            test_idx = np.arange(200, end)
        else:
            train_idx = np.arange(0, start)
            test_idx = np.arange(start, end)
        ranks = fit_ranks(X, nums, train_idx, test_idx)
        m = metrics(ranks, max_actual[test_idx])
        m.update({"train_targets": int(len(train_idx)), "train_end": dates[int(train_idx[-1])],
                  "test_start": dates[int(test_idx[0])], "test_end": dates[int(test_idx[-1])],
                  "warmup_note": "first 200 Q90 discovery target rows are training warm-up; remaining discovery targets evaluated" if name == "discovery" else None})
        p_exact = binomtest(m["paired_top5_model_only_wins"], m["paired_top5_discordant"], p=0.5, alternative="two-sided").pvalue
        m["paired_top5_mcnemar_exact_two_sided"] = float(p_exact)
        m["paired_top5_block_signflip"] = block_signflip_p(np.asarray(m["top5_difference_per_target"], dtype=int), 7, 100000, 20261111 + j)
        split_eval[name] = m
        split_tests[name] = m["paired_top5_block_signflip"]["p_two_sided"]
    split_holm = holm_adjust(split_tests)
    for name in split_eval:
        split_eval[name]["paired_top5_block_signflip_holm_three_splits"] = split_holm[name]

    train_mask = date_index <= pd.Timestamp("2024-12-31")
    test_mask = (date_index >= pd.Timestamp("2025-01-01")) & (date_index <= pd.Timestamp("2026-11-04"))
    train_idx = np.flatnonzero(train_mask)
    test_idx = np.flatnonzero(test_mask)
    ranks = fit_ranks(X, nums, train_idx, test_idx)
    primary = metrics(ranks, max_actual[test_idx])
    diff = np.asarray(primary["top5_difference_per_target"], dtype=int)
    rank_diff = np.asarray(primary["rank_difference_per_target"], dtype=int)
    primary["train_targets"] = int(len(train_idx))
    primary["train_start"] = dates[int(train_idx[0])]
    primary["train_end"] = dates[int(train_idx[-1])]
    primary["test_start"] = dates[int(test_idx[0])]
    primary["test_end"] = dates[int(test_idx[-1])]
    primary["paired_top5_mcnemar_exact_two_sided"] = float(binomtest(primary["paired_top5_model_only_wins"], primary["paired_top5_discordant"], p=0.5, alternative="two-sided").pvalue)
    primary["paired_top5_block_signflip"] = block_signflip_p(diff, 7, 200000, 20261108)
    primary["moving_block_bootstrap_95_ci_top5_delta"] = circular_mbb_ci(diff, 7, 20000, 20261109)
    primary["moving_block_bootstrap_95_ci_rank_delta"] = circular_mbb_ci(rank_diff, 7, 20000, 20261110)

    result = {
        "protocol": "FD-06 Q90 pooled P5 logistic reproduction and paired exact order-statistic baseline audit; exploratory, no promotion",
        "model": {"algorithm": "StandardScaler + LogisticRegression", "C": 0.05, "max_iter": 300, "solver": "lbfgs", "features": 59,
                  "target": "per target, positive label is the actual maximum P5 among candidate numbers 1..40", "rank_tie_policy": "stable sort; candidate number ascending"},
        "integrity": integrity,
        "exact_order_statistic_null": exact_order_stat_baseline(),
        "primary_registered_holdout": primary,
        "q90_chronological_split_evaluation": split_eval,
        "secondary_family": {"endpoint": "paired Top5 hit-share difference model minus numeric-order baseline", "block_length": 7,
                             "split_p_values_two_sided": split_tests, "holm_adjustment": split_holm,
                             "note": "secondary/exploratory; discovery test excludes 200-target warm-up used to fit the first model"},
        "decision": "NO_PREDICTIVE_LIFT; logistic P5 ranker is inferior to descending numeric order on the primary holdout and on all three secondary chronological evaluations",
        "limitations": ["Q90 feature matrix artifact ends at 2026-11-04; later archive rows are not in this audit.",
                        "Block sign-flip assumes exchangeable block signs under the null; paired McNemar is also reported but assumes target-level independence.",
                        "The analysis audits one fixed C=0.05 logistic specification; it does not correct across every prior model or feature search in the wider SONAR project.",
                        "No engine promotion, merge, or PR modification is authorized."],
        "next_action": "Keep numeric order as the P5 order-statistic reference; audit feature families only against this baseline and preserve the next prospective freeze append-only."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "primary_top5_delta": primary["top5_delta_model_minus_numeric"],
                      "primary_block_p": primary["paired_top5_block_signflip"]["p_two_sided"],
                      "split_holm": split_holm}, indent=2))


if __name__ == "__main__":
    main()
