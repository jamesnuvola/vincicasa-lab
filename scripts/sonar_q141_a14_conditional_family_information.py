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
