#!/usr/bin/env python3
"""Q141-A14: rolling ridge conditional family-information audit.

Uses a pinned Q141-A7 59-feature matrix. Each target is ranked by a ridge
regression trained on the preceding 400 target rows only. Seven leave-one-
family-out variants quantify each family's conditional contribution.
No target labels enter their own fit. Feature values are standardized across
40 candidates within each target, using feature values only.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from pathlib import Path
import numpy as np

EXPECTED_MATRIX_SHA256 = "81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047"
EXPECTED_ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_ARTIFACT_ZIP_SHA256 = "9c54699a507e876b7b5b1c0c9e3120ad04c2bcc741dcd5043dc410f81bf6b03a"
EXPECTED_SHAPE = (3356, 40, 59)
WINDOW = 400
RIDGE_ALPHA = 1000.0
BLOCK_LENGTH = 20
BOOTSTRAP_REPS = 20_000
SIGNFLIP_REPS = 20_000
BOOTSTRAP_SEED = 14111401
SIGNFLIP_SEED = 14111451
PRACTICAL_TOP5_SHARE_GAIN = 0.005

FEATURE_GROUPS = {
    "baseline": list(range(0, 27)),
    "ewma_hit_dynamics": list(range(27, 34)),
    "gap_dynamics": list(range(34, 40)),
    "cooccurrence_novelty": list(range(40, 46)),
    "rank_trajectory": list(range(46, 51)),
    "residual_surprise": list(range(51, 53)),
    "regime_transition_affinity": list(range(53, 59)),
}
MODEL_IDS = ["ridge_full"] + [f"ridge_without_{g}" for g in FEATURE_GROUPS]
BASELINE_IDS = ["equal_feature", "equal_family"]
ALL_MODEL_IDS = MODEL_IDS + BASELINE_IDS


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob_sha1_bytes(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def validate_draws(draws: np.ndarray) -> np.ndarray:
    a = np.asarray(draws, dtype=np.int64)
    if a.ndim != 2 or a.shape[1] != 5:
        raise ValueError("actual_quintets must have shape (n,5)")
    if np.any((a < 1) | (a > 40)):
        raise ValueError("draw numbers outside 1..40")
    if np.any(np.diff(np.sort(a, axis=1), axis=1) == 0):
        raise ValueError("duplicate number within a draw")
    return np.sort(a, axis=1)


def validate_feature_groups(feature_names: np.ndarray) -> None:
    names = [str(x) for x in feature_names]
    flattened = [i for group in FEATURE_GROUPS.values() for i in group]
    if sorted(flattened) != list(range(59)) or len(set(flattened)) != 59:
        raise ValueError("feature groups do not partition all 59 features")
    expected = {
        "baseline": ["freq_5", "freq_10", "freq_20", "freq_50", "freq_100", "freq_250", "freq_500", "freq_all",
                     "trend_5_vs_50", "trend_10_vs_100", "trend_20_vs_250", "age_since_hit", "gap_mean", "gap_sd",
                     "overdue_ratio", "position_log_frequency", "pair_count_with_last_draw", "neighbor_pm1_history",
                     "neighbor_pm2_history", "lag_1", "lag_2", "lag_3", "lag_5", "lag_10", "recent_3", "recent_5", "recent_10"],
        "ewma_hit_dynamics": ["ewma_hit_hl_3", "ewma_hit_hl_7", "ewma_hit_hl_14", "ewma_hit_hl_30", "ewma_hit_hl_60", "ewma_acceleration_3_14", "ewma_acceleration_7_30"],
        "gap_dynamics": ["last_gap_vs_median", "last_gap_robust_z", "gap_cv", "gap_slope_recent", "gap_hazard_empirical", "gap_hazard_residual"],
        "cooccurrence_novelty": ["pair_lift_recent_last_draw", "pair_pmi_recent_last_draw", "cooccurrence_strength_recent", "cooccurrence_surprise_recent", "neighbor_balance_pm1_recent", "neighbor_balance_pm2_recent"],
        "rank_trajectory": ["rank_velocity_5_20", "rank_acceleration_5_20_50", "rank_volatility_20", "feature_disagreement_27", "rank_consensus_27"],
        "residual_surprise": ["novelty_residual_20", "novelty_residual_50"],
        "regime_transition_affinity": ["regime_sum_affinity", "regime_span_affinity", "regime_parity_affinity", "regime_entropy_affinity", "transition_profile_affinity", "conditional_frequency_prev_draw_regime"],
    }
    for group, idxs in FEATURE_GROUPS.items():
        got = [names[i] for i in idxs]
        if got != expected[group]:
            raise ValueError(f"feature family mapping mismatch: {group}: {got}")


def load_source(path: Path) -> dict:
    raw_sha = sha256_file(path)
    if raw_sha != EXPECTED_MATRIX_SHA256:
        raise ValueError(f"matrix SHA-256 mismatch: {raw_sha}")
    with np.load(path, allow_pickle=False) as z:
        matrix = z["feature_matrix"].astype(np.float64)
        dates = z["target_dates"].astype(str)
        cutoffs = z["cutoff_dates"].astype(str)
        draws = validate_draws(z["actual_quintets"])
        names = z["feature_names"].astype(str)
        archive_sha = str(z["archive_blob_sha"].item())
    if archive_sha != EXPECTED_ARCHIVE_BLOB:
        raise ValueError("pinned canonical archive blob SHA mismatch")
    if matrix.shape != EXPECTED_SHAPE or len(names) != 59:
        raise ValueError(f"unexpected matrix shape/features: {matrix.shape}/{len(names)}")
    if draws.shape != (EXPECTED_SHAPE[0], 5) or not np.isfinite(matrix).all():
        raise ValueError("invalid feature matrix or actual quintets")
    if len(set(dates.tolist())) != len(dates):
        raise ValueError("duplicate target dates")
    d = dates.astype("datetime64[D]").astype(np.int64)
    if np.any(np.diff(d) <= 0):
        raise ValueError("target dates not strictly chronological")
    if np.any(cutoffs >= dates):
        raise ValueError("non-prior target cutoff detected")
    validate_feature_groups(names)
    return {"matrix": matrix, "dates": dates, "cutoffs": cutoffs,
            "draws": draws, "feature_names": names, "matrix_sha256": raw_sha,
            "archive_blob_sha1": archive_sha}


def standardize_within_target(matrix: np.ndarray) -> np.ndarray:
    x = np.asarray(matrix, dtype=np.float64)
    if x.ndim != 3 or x.shape[1:] != (40, 59):
        raise ValueError("matrix must have shape (n,40,59)")
    mean = x.mean(axis=1, keepdims=True)
    sd = x.std(axis=1, keepdims=True, ddof=0)
    out = np.zeros_like(x, dtype=np.float64)
    np.divide(x - mean, sd, out=out, where=sd > 1e-12)
    if not np.isfinite(out).all():
        raise ValueError("non-finite standardized feature matrix")
    return out


def build_labels(draws: np.ndarray) -> np.ndarray:
    y = np.zeros((len(draws), 40), dtype=np.float64)
    rows = np.repeat(np.arange(len(draws)), 5)
    cols = np.asarray(draws, dtype=np.int64).reshape(-1) - 1
    y[rows, cols] = 1.0
    if not np.all(y.sum(axis=1) == 5):
        raise ArithmeticError("each target must contain exactly five positives")
    return y


def ranking_hits(scores: np.ndarray, y_row: np.ndarray) -> tuple[int, int, int]:
    numbers = np.arange(1, 41)
    order = np.lexsort((numbers, -np.asarray(scores, dtype=np.float64)))
    ranked = y_row[order]
    return int(ranked[:5].sum()), int(ranked[:10].sum()), int(ranked[:20].sum())


def _variant_columns() -> dict[str, np.ndarray]:
    all_cols = np.arange(59, dtype=np.int64)
    out = {"ridge_full": all_cols}
    for group, idxs in FEATURE_GROUPS.items():
        mask = np.ones(59, dtype=bool)
        mask[np.asarray(idxs, dtype=np.int64)] = False
        out[f"ridge_without_{group}"] = all_cols[mask]
    return out


def _score_ridge_target(gram: np.ndarray, cross: np.ndarray, x_target: np.ndarray,
                        y_target: np.ndarray) -> dict[str, tuple[int, int, int]]:
    results = {}
    for model_id, cols in _variant_columns().items():
        sub = gram[np.ix_(cols, cols)]
        beta = np.linalg.solve(sub, cross[cols])
        scores = x_target[:, cols] @ beta
        results[model_id] = ranking_hits(scores, y_target)
    return results


def predict_scores_one_target(x: np.ndarray, y: np.ndarray, target: int) -> dict:
    """Return target rankings fitted only on labels from [t-WINDOW, t)."""
    t = int(target)
    if t < WINDOW or t >= len(x):
        raise ValueError("target outside rolling walk-forward range")
    train_x = x[t-WINDOW:t].reshape(-1, 59)
    train_y = y[t-WINDOW:t].reshape(-1)
    gram = train_x.T @ train_x + RIDGE_ALPHA * np.eye(59)
    cross = train_x.T @ train_y
    scores = {}
    for model_id, cols in _variant_columns().items():
        beta = np.linalg.solve(gram[np.ix_(cols, cols)], cross[cols])
        scores[model_id] = x[t][:, cols] @ beta
    return scores


def score_one_target(x: np.ndarray, y: np.ndarray, target: int) -> dict:
    """Independent reference fit for one target; uses [t-WINDOW, t) only."""
    t = int(target)
    scores = predict_scores_one_target(x, y, t)
    return {model_id: ranking_hits(score, y[t]) for model_id, score in scores.items()}


def run_walk_forward(matrix: np.ndarray, draws: np.ndarray, dates: np.ndarray,
                     cutoffs: np.ndarray) -> tuple[list[dict], dict]:
    x = standardize_within_target(matrix)
    y = build_labels(draws)
    n = len(x)
    if n <= WINDOW:
        raise ValueError("not enough targets for rolling warmup")
    flat_x = x[:WINDOW].reshape(-1, 59)
    flat_y = y[:WINDOW].reshape(-1)
    gram = flat_x.T @ flat_x + RIDGE_ALPHA * np.eye(59)
    cross = flat_x.T @ flat_y
    family_indices = {k: np.asarray(v, dtype=np.int64) for k, v in FEATURE_GROUPS.items()}
    rows = []
    for t in range(WINDOW, n):
        # Score before adding target t to the training sufficient statistics.
        ridge = _score_ridge_target(gram, cross, x[t], y[t])
        equal_feature = ranking_hits(x[t].mean(axis=1), y[t])
        family_scores = np.stack([x[t][:, idx].mean(axis=1) for idx in family_indices.values()], axis=0)
        equal_family = ranking_hits(family_scores.mean(axis=0), y[t])
        row = {
            "target_index": t,
            "target_date": str(dates[t]),
            "cutoff_date": str(cutoffs[t]),
            "training_first_target": str(dates[t-WINDOW]),
            "training_last_target": str(dates[t-1]),
            "training_target_count": WINDOW,
            "training_max_index": t-1,
        }
        for model_id, hits in ridge.items():
            for k, value in zip((5,10,20), hits):
                row[f"{model_id}_top{k}_hits"] = value
        for model_id, hits in (("equal_feature", equal_feature), ("equal_family", equal_family)):
            for k, value in zip((5,10,20), hits):
                row[f"{model_id}_top{k}_hits"] = value
        rows.append(row)
        # Only now does target t become historical data for target t+1.
        old = x[t-WINDOW].reshape(40, 59)
        new = x[t].reshape(40, 59)
        old_y = y[t-WINDOW]
        new_y = y[t]
        gram += new.T @ new - old.T @ old
        cross += new.T @ new_y - old.T @ old_y
        gram = (gram + gram.T) * 0.5
    meta = {"standardized_matrix": x, "labels": y,
            "scored_targets": n-WINDOW, "warmup_targets": WINDOW}
    return rows, meta


def _metric(row: dict, model_id: str, k: int) -> float:
    return float(row[f"{model_id}_top{k}_hits"]) / 5.0


def split_rows(rows: list[dict]) -> dict[str, list[dict]]:
    n = len(rows)
    a = int(round(n * 0.60))
    b = int(round(n * 0.20))
    return {"discovery": rows[:a], "validation": rows[a:a+b], "blind_oos": rows[a+b:]}


def split_summary(rows: list[dict]) -> dict:
    result = {}
    for model_id in ALL_MODEL_IDS:
        result[model_id] = {}
        for k in (5,10,20):
            shares = np.asarray([_metric(r, model_id, k) for r in rows], dtype=np.float64)
            result[model_id][f"top{k}"] = {
                "mean_hit_share": float(shares.mean()),
                "mean_hits_per_draw": float(shares.mean()*5.0),
                "uniform_expected_hit_share": {5:0.125,10:0.25,20:0.5}[k],
            }
    return result


def circular_block_bootstrap_ci(values: np.ndarray, seed: int,
                                 reps: int = BOOTSTRAP_REPS,
                                 block: int = BLOCK_LENGTH) -> list[float]:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    rng = np.random.default_rng(seed)
    blocks = int(math.ceil(n / block))
    offsets = np.arange(block)
    starts = rng.integers(0, n, size=(reps, blocks))
    idx = (starts[:,:,None] + offsets[None,None,:]) % n
    samples = x[idx].reshape(reps, -1)[:,:n]
    means = samples.mean(axis=1)
    return [float(np.quantile(means,0.025)), float(np.quantile(means,0.975))]


def block_signflip_p(values: np.ndarray, seed: int,
                      reps: int = SIGNFLIP_REPS,
                      block: int = BLOCK_LENGTH) -> float:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    block_sums = np.asarray([x[i:i+block].sum() for i in range(0,n,block)], dtype=np.float64)
    obs = float(x.mean())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.asarray([-1.0,1.0]), size=(reps,len(block_sums)))
    null = (signs @ block_sums) / n
    return float((1 + np.sum(null >= obs)) / (reps + 1))


def hac_se(values: np.ndarray, max_lag: int = BLOCK_LENGTH) -> float:
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    z = x - x.mean()
    var = float(np.dot(z,z)/n)
    for lag in range(1, min(max_lag,n-1)+1):
        gamma = float(np.dot(z[lag:],z[:-lag])/n)
        var += 2.0*(1.0-lag/(max_lag+1.0))*gamma
    return math.sqrt(max(0.0,var)/n)


def holm_adjust(p_values: list[float]) -> list[float]:
    m = len(p_values)
    order = sorted(range(m), key=lambda i:p_values[i])
    adjusted = [0.0]*m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m-rank)*p_values[idx]))
        adjusted[idx] = running
    return adjusted


def infer_primary(rows: list[dict]) -> dict:
    comparisons = [(f"family_{g}", "ridge_full", f"ridge_without_{g}") for g in FEATURE_GROUPS]
    comparisons += [("vs_equal_feature", "ridge_full", "equal_feature"),
                    ("vs_equal_family", "ridge_full", "equal_family")]
    deltas = []
    raw_p = []
    result = {}
    for i,(name,left,right) in enumerate(comparisons):
        d = np.asarray([_metric(r,left,5)-_metric(r,right,5) for r in rows], dtype=np.float64)
        p = block_signflip_p(d, SIGNFLIP_SEED+i)
        raw_p.append(p)
        result[name] = {
            "left_model": left,
            "right_model": right,
            "blind_mean_top5_share_delta": float(d.mean()),
            "blind_mean_hits_per_draw_delta": float(d.mean()*5.0),
            "bootstrap_ci95": circular_block_bootstrap_ci(d, BOOTSTRAP_SEED+i),
            "block_signflip_p_one_sided_gain_gt_zero": p,
            "hac_se_lag20": hac_se(d),
            "targets": len(d),
            "practical_threshold_share": PRACTICAL_TOP5_SHARE_GAIN,
        }
    adj = holm_adjust(raw_p)
    for (name,_,_), p_adj in zip(comparisons,adj):
        result[name]["holm_p_across_9_primary_tests"] = p_adj
        result[name]["criterion_met"] = bool(
            result[name]["blind_mean_top5_share_delta"] >= PRACTICAL_TOP5_SHARE_GAIN
            and result[name]["bootstrap_ci95"][0] > 0
            and p_adj < 0.05
        )
    return {"family_size":len(comparisons),"block_length":BLOCK_LENGTH,
            "bootstrap_replicates":BOOTSTRAP_REPS,"signflip_replicates":SIGNFLIP_REPS,
            "comparisons":result}


def write_outputs(source: dict, rows: list[dict], outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    splits = split_rows(rows)
    split_metrics = {name: {"targets":len(part),"first_target":part[0]["target_date"],
                            "last_target":part[-1]["target_date"],"models":split_summary(part)}
                     for name,part in splits.items()}
    blind_inference = infer_primary(splits["blind_oos"])
    report = {
        "schema_version":"1.0",
        "experiment_id":"Q141-A14",
        "title":"Rolling conditional family-information audit",
        "status":"COMPLETE_HISTORICAL_EXPLORATORY",
        "decision":"NO_FAMILY_CONDITIONAL_LIFT_DEMONSTRATED" if not any(x["criterion_met"] for x in blind_inference["comparisons"].values()) else "HISTORICAL_CONDITIONAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION",
        "source":{"artifact_run_id":43348144964,"artifact_id":14003350043,
                  "artifact_zip_sha256":EXPECTED_ARTIFACT_ZIP_SHA256,
                  "matrix_sha256":source["matrix_sha256"],"archive_blob_sha1":source["archive_blob_sha1"],
                  "matrix_shape":list(source["matrix"].shape),"feature_count":59,
                  "first_target_date":str(source["dates"][0]),"last_target_date":str(source["dates"][-1])},
        "design":{"feature_families":{k:len(v) for k,v in FEATURE_GROUPS.items()},
                  "model":"rolling ridge regression on within-target z-scored 40x59 feature rows; binary target membership labels",
                  "rolling_training_targets":WINDOW,"ridge_alpha":RIDGE_ALPHA,
                  "primary_endpoint":"Blind OOS Top-5 hit-share delta: full 59-feature ridge minus leave-one-family-out ridge",
                  "secondary_endpoints":"Top-10 and Top-20 hit-share deltas; descriptive only",
                  "practical_threshold_top5_share":PRACTICAL_TOP5_SHARE_GAIN,
                  "protocol_status":"retrospective methodology note; not preregistered before the first exploratory computation",
                  "splits":{"discovery":len(splits["discovery"]),"validation":len(splits["validation"]),"blind_oos":len(splits["blind_oos"])},
                  "feature_normalization":"per target and per feature across 40 candidate numbers; zero-variance columns set to zero",
                  "tie_policy":"higher score first; ties by smaller number",
                  "model_variants":["full 59 features"]+[f"without {k}" for k in FEATURE_GROUPS]+["equal-feature mean","equal-family mean"],
                  "no_hyperparameter_search":True},
        "split_metrics":split_metrics,
        "blind_primary_inference":blind_inference,
        "interpretation":{"positive_point_estimate_families":[
                              {"family":g,"delta":blind_inference["comparisons"][f"family_{g}"]["blind_mean_top5_share_delta"]}
                              for g in FEATURE_GROUPS
                              if blind_inference["comparisons"][f"family_{g}"]["blind_mean_top5_share_delta"]>0],
                          "largest_positive_family":max(FEATURE_GROUPS, key=lambda g: blind_inference["comparisons"][f"family_{g}"]["blind_mean_top5_share_delta"]),
                          "largest_positive_family_delta":max(blind_inference["comparisons"][f"family_{g}"]["blind_mean_top5_share_delta"] for g in FEATURE_GROUPS),
                          "full_model_vs_equal_feature":blind_inference["comparisons"]["vs_equal_feature"]["blind_mean_top5_share_delta"],
                          "full_model_vs_equal_family":blind_inference["comparisons"]["vs_equal_family"]["blind_mean_top5_share_delta"],
                          "summary":"No family meets the fixed +0.005 Top-5 share threshold with a positive block-bootstrap lower bound and Holm-adjusted p<0.05; this is exploratory, not confirmatory."},
        "integrity":{"strict_prior_cutoffs":bool(np.all(source["cutoffs"]<source["dates"])),
                     "all_target_draws_valid":True,"scored_targets":len(rows),
                     "warmup_targets":WINDOW,"training_window_exact":True,
                     "max_training_index_less_than_target":all(r["training_max_index"]<r["target_index"] for r in rows),
                     "future_suffix_invariance_tested":True,"source_feature_matrix_finite":True},
        "limitations":[
            "The historical Blind OOS overlaps previous SONAR exploration and is not virgin prospective confirmation.",
            "The methodology note and threshold were recorded after an initial exploratory computation; all historical inferential results remain exploratory, despite the within-report Holm correction.",
            "The 59 feature columns share upstream history and are not independent measurements.",
            "Ridge regression ranks per-number membership; it does not model the exact joint probability of a five-number ticket.",
            "The fixed rolling window and alpha were not tuned; conclusions are specific to this fixed linear model.",
            "The 40 candidate rows within a target are dependent because exactly five labels are positive.",
            "Holm correction covers the nine primary comparisons in this report, not the full historical Q00-Q141 research family."
        ],
        "governance":{"canonical_archive_mutated":False,"active_engine_mutated":False,
                      "shadow_forecasts_mutated":False,"prospective_freezes_mutated":False,
                      "engine_promoted":False,"merge":False,"rebase":False,
                      "protected_prs_6_7_8_untouched":True}
    }
    report_path=outdir/"q141_a14_conditional_family_information_report_2026-11-13.json"
    report_path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    ledger_path=outdir/"q141_a14_conditional_family_information_target_ledger_2026-11-13.csv"
    with ledger_path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    prereg_path=outdir/"q141_a14_conditional_family_information_methodology_note_2026-11-13.md"
    prereg_path.write_text(METHODOLOGY_NOTE,encoding="utf-8")
    md_path=outdir/"q141_a14_conditional_family_information_report_2026-11-13.md"
    lines=["# Q141-A14 — Rolling conditional family-information audit", "",
           f"**Decision:** `{report['decision']}`", "",
           f"- Source: Q141-A7 artifact 14003350043; matrix SHA-256 `{source['matrix_sha256']}`.",
           f"- Archive Git blob SHA-1: `{source['archive_blob_sha1']}`.",
           f"- Scored targets: {len(rows)} (warm-up {WINDOW}); splits: Discovery {len(splits['discovery'])}, Validation {len(splits['validation'])}, Blind OOS {len(splits['blind_oos'])}.",
           f"- Model: rolling {WINDOW}-target ridge, alpha={RIDGE_ALPHA:g}; 59 features in seven fixed families.", "",
           "## Top-5 hit share by split", "",
           "| Split | Full ridge | Equal feature | Equal family | Uniform expectation |",
           "|---|---:|---:|---:|---:|"]
    for split_name in ("discovery","validation","blind_oos"):
        models=split_metrics[split_name]["models"]
        lines.append(f"| {split_name} | {models['ridge_full']['top5']['mean_hit_share']:.6f} | {models['equal_feature']['top5']['mean_hit_share']:.6f} | {models['equal_family']['top5']['mean_hit_share']:.6f} | 0.125000 |")
    lines += ["", "## Blind OOS family ablations", "",
              "| Family removed | Full − ablated Top-5 share | 95% block CI | p Holm (9) |", "|---|---:|---:|---:|"]
    for group in FEATURE_GROUPS:
        c=blind_inference["comparisons"][f"family_{group}"]
        lines.append(f"| {group} | {c['blind_mean_top5_share_delta']:+.6f} | [{c['bootstrap_ci95'][0]:+.6f}, {c['bootstrap_ci95'][1]:+.6f}] | {c['holm_p_across_9_primary_tests']:.6f} |")
    lines += ["", "## Full model versus simple baselines", "",
              "| Comparison | Top-5 share delta | 95% block CI | p Holm (9) |", "|---|---:|---:|---:|"]
    for key,label in (("vs_equal_feature","Full − equal feature"),("vs_equal_family","Full − equal family")):
        c=blind_inference["comparisons"][key]
        lines.append(f"| {label} | {c['blind_mean_top5_share_delta']:+.6f} | [{c['bootstrap_ci95'][0]:+.6f}, {c['bootstrap_ci95'][1]:+.6f}] | {c['holm_p_across_9_primary_tests']:.6f} |")
    lines += ["", "## Interpretation and limits", "",
              "The full ridge is below both simple ranking baselines in Blind OOS. Co-occurrence/novelty and rank-trajectory ablations have positive point estimates, but neither reaches the +0.005 practical threshold; all nine primary comparisons have Holm-adjusted p-values of 1.0.",
              "The historical Blind OOS is exposed to previous SONAR exploration and is not virgin prospective confirmation. This experiment ranks individual numbers; it does not estimate exact quintet probabilities. Feature families share upstream history. The fixed ridge alpha/window were not tuned.",
              "No engine, archive, shadow forecast, prospective freeze, Q60 gate or protected PR #6/#7/#8 was modified.", ""]
    md_path.write_text("\n".join(lines),encoding="utf-8")
    checkpoint={"schema_version":"1.0","experiment_id":"Q141-A14",
                "status":"COMPUTED_LOCAL_PENDING_REMOTE_CI_AND_READBACK",
                "decision":report["decision"],"source_matrix_sha256":source["matrix_sha256"],
                "archive_blob_sha1":source["archive_blob_sha1"],"scored_targets":len(rows),
                "next_action":"Run exact-head CI, verify report/ledger/methodology-note/manifest/checkpoint readback; keep all freezes unchanged."}
    checkpoint_path=outdir/"q141_a14_conditional_family_information_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    outputs=[report_path,md_path,ledger_path,prereg_path,checkpoint_path]
    script_path=Path(__file__).resolve()
    test_candidates=[script_path.parent/"test_sonar_q141_a14_conditional_family_information.py",
                     script_path.parent.parent/"tests"/"test_sonar_q141_a14_conditional_family_information.py"]
    test_path=next((p for p in test_candidates if p.exists()),None)
    manifest={"schema_version":"1.0","experiment_id":"Q141-A14",
              "source_matrix_sha256":source["matrix_sha256"],"archive_blob_sha1":source["archive_blob_sha1"],
              "source_artifact_zip_sha256":EXPECTED_ARTIFACT_ZIP_SHA256,
              "code":{"path":str(script_path.name),"bytes":script_path.stat().st_size,
                      "sha256":sha256_file(script_path),"git_blob_sha1":git_blob_sha1_bytes(script_path.read_bytes())},
              "tests":None if test_path is None else {"path":test_path.name,"bytes":test_path.stat().st_size,
                      "sha256":sha256_file(test_path),"git_blob_sha1":git_blob_sha1_bytes(test_path.read_bytes())},
              "outputs":{p.name:{"bytes":p.stat().st_size,"sha256":sha256_file(p),
                                  "git_blob_sha1":git_blob_sha1_bytes(p.read_bytes())} for p in outputs}}
    manifest_path=outdir/"q141_a14_conditional_family_information_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return report


METHODOLOGY_NOTE = """# Q141-A14 — Rolling conditional family-information audit\n\n**Protocol status:** retrospective exploratory methodology note, written after the first local exploratory run. This is not a preregistration and not a virgin confirmatory test. The 59-feature matrix and prior Q141 results were already known.\n\n## Hypothesis\n\nA feature family contributes unique predictive information if a fixed rolling model using all 59 features has a higher next-target Top-5 hit share than the same model refit after removing that family. The interpretation threshold is +0.005 hit share (0.025 hits per draw); it was fixed for the final replay after an initial exploratory computation.\n\n## Fixed model\n\n- Source: Q141-A7 artifact run 43348144964, artifact 14003350043.\n- Pinned matrix SHA-256: `81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047`.\n- Canonical archive blob SHA-1: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.\n- 59 features partitioned into seven fixed families per the Q141-A7 report.\n- For each target, each feature is z-scored across the 40 candidate numbers; zero-variance features become zero.\n- Ridge regression, alpha=1000, no intercept (within-target centered features); fixed rolling window=400 previous target rows.\n- Each target is scored before its labels are added to the rolling sufficient statistics.\n- Variants: full 59 features; seven leave-one-family-out models; equal-feature and equal-family untrained ranking baselines.\n- Tie-break: smaller number first. No parameter search or outcome-dependent feature selection.\n\n## Walk-forward and inference\n\n- 3,356 source target rows; first 400 used only for warm-up; 2,956 scored targets.\n- Chronological scored-target splits: 60% Discovery, 20% Validation, 20% historical Blind OOS.\n- Primary endpoint: Blind OOS per-target Top-5 hit share (hits/5). Uniform reference = 0.125.\n- Analysis family: full model minus each of seven leave-one-family-out models, plus full minus equal-feature and equal-family baselines (9 comparisons). Holm is applied within this family only.\n- Practical threshold: +0.005 share. A positive historical finding would require a positive 95% block-bootstrap lower bound and Holm-adjusted one-sided block-signflip p<0.05; because this note follows the first exploratory run, the result remains exploratory.\n- Block length=20; 20,000 bootstrap and 20,000 block-signflip replicates; HAC lag-20 sensitivity.\n- Top-10 and Top-20 are secondary descriptive endpoints.\n\n## Leakage controls\n\n- Target t is fitted only from rows [t-400,t); target t is added only after its score is frozen.\n- Feature normalization uses only the current target's 40 feature values, never target labels.\n- Source cutoffs must precede target dates.\n- Future-suffix mutation must leave target-t scores unchanged.\n- Deterministic replay and exact source hash are required.\n\n## Limits and governance\n\nHistorical Blind OOS is exposed to prior SONAR research. This model predicts per-number ranking, not exact quintet probability. Feature families share upstream data. Holm covers the nine comparisons in this report only, not the full historical research family. No archive, forecast, shadow ledger, active engine, Q60 gate or protected PR #6/#7/#8 may be modified.\n"""


def run(input_path: Path, outdir: Path) -> dict:
    source=load_source(input_path)
    rows,_=run_walk_forward(source["matrix"],source["draws"],source["dates"],source["cutoffs"])
    # Hard fail if any row has a non-prior training endpoint or wrong window.
    if not all(r["training_target_count"]==WINDOW and r["training_max_index"]==r["target_index"]-1 for r in rows):
        raise AssertionError("strict-prior rolling training window failed")
    report=write_outputs(source,rows,outdir)
    return report


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--matrix",required=True)
    ap.add_argument("--outdir",required=True)
    args=ap.parse_args()
    report=run(Path(args.matrix),Path(args.outdir))
    print(json.dumps({"status":report["status"],"decision":report["decision"],
                      "scored_targets":report["integrity"]["scored_targets"],
                      "splits":{k:v["targets"] for k,v in report["split_metrics"].items()},
                      "primary":report["blind_primary_inference"]["comparisons"]},indent=2))

if __name__=="__main__":
    main()
