#!/usr/bin/env python3
"""Q90 expanded, strict-prior-only formula grammar over the Q89 feature matrix.

Exhaustive only within the discovery-selected 20-feature subset and the declared
4-8 variable linear, 4-variable pair-interaction, and 4-variable conditional-gate
families. Retrospective per-target oracle records are descriptive, not forecasts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from itertools import combinations
from pathlib import Path

import numpy as np
from scipy.special import erfc
import sonar_per_number_condition_grammar as q80

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
Q89_MATRIX = OUT / "adaptive_novelty_feature_matrix.npz"
Q89_MANIFEST = OUT / "adaptive_novelty_formula_metrics_manifest.json"
Q89_CATALOG = OUT / "adaptive_novelty_feature_catalog.json"
Q89_SPLIT_METRICS = OUT / "adaptive_novelty_split_metrics.csv"
MIN_HISTORY = 50
LINEAR_SIZES = (4, 5, 6, 7, 8)
INTERACTION_WEIGHT = 0.25
GATE_BONUS = 0.25
GATE_THRESHOLDS = (0.5, 1.0)
EXPECTED_SELECTED_FEATURES = 20
TYPE_NAMES = ("linear_mean", "pairwise_interaction", "conditional_gate")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def average_ranks(rows, field, ascending=True):
    order = sorted(range(len(rows)), key=lambda i: (float(rows[i][field]) if ascending else -float(rows[i][field]), rows[i]["feature"]))
    result = [0.0] * len(rows)
    i = 0
    while i < len(order):
        j = i + 1
        value = float(rows[order[i]][field])
        while j < len(order) and float(rows[order[j]][field]) == value:
            j += 1
        average = ((i + 1) + j) / 2.0
        for k in range(i, j):
            result[order[k]] = average
        i = j
    return result


def select_features(split_rows, family_by_feature):
    discovery = [r for r in split_rows if r["split"] == "discovery"]
    if len(discovery) != len(family_by_feature):
        raise ValueError(f"Q90_BLOCKED: discovery feature rows {len(discovery)} != {len(family_by_feature)}")
    rank_rank = average_ranks(discovery, "mean_actual_number_rank", ascending=True)
    top5_rank = average_ranks(discovery, "mean_number_hits_top5", ascending=False)
    enriched = []
    for i, row in enumerate(discovery):
        enriched.append({**row, "family": family_by_feature[row["feature"]],
                         "rank_mean_actual": rank_rank[i], "rank_hits_top5": top5_rank[i],
                         "composite_rank": (rank_rank[i] + top5_rank[i]) / 2.0})
    selected = []
    quotas = {}
    family_rankings = {}
    for family in sorted(set(family_by_feature.values())):
        group = sorted([r for r in enriched if r["family"] == family],
                       key=lambda r: (r["composite_rank"], r["feature"]))
        quota = 2 if family == "residual_surprise" else 3
        if len(group) < quota:
            raise ValueError(f"Q90_BLOCKED: family {family} has {len(group)} features, quota {quota}")
        quotas[family] = quota
        family_rankings[family] = [{k: r[k] for k in
            ("feature", "family", "mean_actual_number_rank", "mean_number_hits_top5",
             "rank_mean_actual", "rank_hits_top5", "composite_rank")} for r in group]
        selected.extend(group[:quota])
    if len(selected) != EXPECTED_SELECTED_FEATURES:
        raise ValueError(f"Q90_BLOCKED: selected {len(selected)} features != 20")
    selected_names = [r["feature"] for r in selected]
    return selected_names, {
        "schema_version": "1.0", "task_id": "Q90",
        "selection_split": "discovery",
        "selection_rule": "Within each family, average the rank of mean_actual_number_rank (ascending) and mean_number_hits_top5 (descending); select top 3, except residual_surprise top 2. Validation and blind_oos outcomes do not enter feature selection.",
        "family_quotas": quotas,
        "selected_features": [{k: r[k] for k in
            ("feature", "family", "mean_actual_number_rank", "mean_number_hits_top5",
             "rank_mean_actual", "rank_hits_top5", "composite_rank")} for r in selected],
        "full_discovery_family_rankings": family_rankings,
        "guardrails": ["feature selection uses discovery split only",
                       "formula metrics on discovery are search diagnostics",
                       "validation and blind_oos are held chronologically",
                       "no formula promotion; per-target oracle is retrospective"]
    }


def build_formula_catalog(selected_indices, feature_names):
    if len(selected_indices) != EXPECTED_SELECTED_FEATURES:
        raise ValueError("Q90_BLOCKED: formula catalog requires exactly 20 selected features")

    linear_local = {}
    linear_feature_arrays = []
    linear_type_arrays = []
    linear_size_arrays = []
    linear_aux_combo_arrays = []
    linear_aux_pair_arrays = []
    linear_gate_pos_arrays = []
    linear_gate_threshold_arrays = []
    linear_counts = {}
    weight_columns = sum(math.comb(20, k) for k in LINEAR_SIZES)
    weights = np.zeros((20, weight_columns), dtype=np.float64)
    group_slices = {}
    cursor = 0

    for k in LINEAR_SIZES:
        local = np.asarray(list(combinations(range(20), k)), dtype=np.uint8)
        linear_local[k] = local
        global_features = selected_indices[local]
        count = len(local)
        end = cursor + count
        columns = np.arange(count)
        for j in range(k):
            weights[local[:, j], cursor + columns] = 1.0 / k
        feature_rows = np.full((count, 8), 255, dtype=np.uint8)
        feature_rows[:, :k] = global_features
        linear_feature_arrays.append(feature_rows)
        linear_type_arrays.append(np.zeros(count, dtype=np.uint8))
        linear_size_arrays.append(np.full(count, k, dtype=np.uint8))
        linear_aux_combo_arrays.append(np.full(count, 255, dtype=np.uint32))
        linear_aux_pair_arrays.append(np.full(count, 65535, dtype=np.uint16))
        linear_gate_pos_arrays.append(np.full(count, 255, dtype=np.uint8))
        linear_gate_threshold_arrays.append(np.full(count, np.nan, dtype=np.float32))
        group_slices[f"L{k}"] = (cursor, end)
        linear_counts[k] = count
        cursor = end

    linear_formula_count = cursor
    combo4_local = linear_local[4]
    combo4_global = selected_indices[combo4_local]
    pair_positions = list(combinations(range(4), 2))
    selected_pairs_global = [
        tuple(sorted((int(selected_indices[a]), int(selected_indices[b]))))
        for a, b in combinations(range(20), 2)
    ]
    pair_lookup = {pair: i for i, pair in enumerate(selected_pairs_global)}

    inter_features = np.repeat(combo4_global, len(pair_positions), axis=0)
    inter_aux_combo = np.repeat(np.arange(len(combo4_global), dtype=np.uint32), len(pair_positions))
    inter_aux_pair = []
    for combo in combo4_global:
        for a, b in pair_positions:
            inter_aux_pair.append(pair_lookup[tuple(sorted((int(combo[a]), int(combo[b]))))])
    inter_aux_pair = np.asarray(inter_aux_pair, dtype=np.uint16)
    inter_count = len(inter_features)
    inter_feature_rows = np.full((inter_count, 8), 255, dtype=np.uint8)
    inter_feature_rows[:, :4] = inter_features
    linear_feature_arrays.append(inter_feature_rows)
    linear_type_arrays.append(np.ones(inter_count, dtype=np.uint8))
    linear_size_arrays.append(np.full(inter_count, 4, dtype=np.uint8))
    linear_aux_combo_arrays.append(inter_aux_combo)
    linear_aux_pair_arrays.append(inter_aux_pair)
    linear_gate_pos_arrays.append(np.full(inter_count, 255, dtype=np.uint8))
    linear_gate_threshold_arrays.append(np.full(inter_count, np.nan, dtype=np.float32))
    group_slices["I4"] = (cursor, cursor + inter_count)
    cursor += inter_count

    gate_features = np.repeat(combo4_global, 4 * len(GATE_THRESHOLDS), axis=0)
    gate_aux_combo = np.repeat(np.arange(len(combo4_global), dtype=np.uint32), 4 * len(GATE_THRESHOLDS))
    gate_pos = np.tile(np.repeat(np.arange(4, dtype=np.uint8), len(GATE_THRESHOLDS)), len(combo4_global))
    gate_threshold = np.tile(np.asarray(GATE_THRESHOLDS, dtype=np.float32), 4 * len(combo4_global))
    gate_count = len(gate_features)
    gate_feature_rows = np.full((gate_count, 8), 255, dtype=np.uint8)
    gate_feature_rows[:, :4] = gate_features
    linear_feature_arrays.append(gate_feature_rows)
    linear_type_arrays.append(np.full(gate_count, 2, dtype=np.uint8))
    linear_size_arrays.append(np.full(gate_count, 4, dtype=np.uint8))
    linear_aux_combo_arrays.append(gate_aux_combo)
    linear_aux_pair_arrays.append(np.full(gate_count, 65535, dtype=np.uint16))
    linear_gate_pos_arrays.append(gate_pos)
    linear_gate_threshold_arrays.append(gate_threshold)
    group_slices["G4"] = (cursor, cursor + gate_count)
    cursor += gate_count

    feature_ids = np.concatenate(linear_feature_arrays, axis=0)
    type_codes = np.concatenate(linear_type_arrays)
    sizes = np.concatenate(linear_size_arrays)
    aux_combo = np.concatenate(linear_aux_combo_arrays)
    aux_pair = np.concatenate(linear_aux_pair_arrays)
    gate_positions = np.concatenate(linear_gate_pos_arrays)
    gate_thresholds = np.concatenate(linear_gate_threshold_arrays)
    formula_count = len(feature_ids)

    expected_linear = sum(math.comb(20, k) for k in LINEAR_SIZES)
    expected_interaction = math.comb(20, 4) * math.comb(4, 2)
    expected_gate = math.comb(20, 4) * 4 * len(GATE_THRESHOLDS)
    if (linear_formula_count != expected_linear or inter_count != expected_interaction
            or gate_count != expected_gate or formula_count != expected_linear + expected_interaction + expected_gate):
        raise ValueError(f"Q90_BLOCKED: formula count mismatch: {formula_count}")

    formula_ids = []
    feature_strings = []
    for i in range(formula_count):
        ids = [int(x) for x in feature_ids[i, :int(sizes[i])]]
        names = [feature_names[x] for x in ids]
        features = "+".join(names)
        feature_strings.append(features)
        encoded = "_".join(f"{x:02d}" for x in ids)
        code = int(type_codes[i])
        if code == 0:
            formula_ids.append(f"L{int(sizes[i])}_{encoded}")
        elif code == 1:
            a, b = selected_pairs_global[int(aux_pair[i])]
            formula_ids.append(f"I4_{encoded}_P{a:02d}_{b:02d}_W025")
        else:
            pos = int(gate_positions[i])
            threshold_code = "05" if abs(float(gate_thresholds[i]) - 0.5) < 1e-9 else "10"
            formula_ids.append(f"G4_{encoded}_F{pos}_T{threshold_code}_B025")
    if len(set(formula_ids)) != formula_count:
        raise ValueError("Q90_BLOCKED: formula IDs are not unique")

    return {
        "weights": weights, "selected_indices": np.asarray(selected_indices, dtype=np.uint8),
        "feature_ids": feature_ids, "type_codes": type_codes,
        "sizes": sizes, "aux_combo": aux_combo, "aux_pair": aux_pair,
        "gate_positions": gate_positions, "gate_thresholds": gate_thresholds,
        "formula_ids": formula_ids, "feature_strings": feature_strings,
        "group_slices": group_slices, "selected_pairs_global": selected_pairs_global,
        "linear_counts": linear_counts, "linear_formula_count": linear_formula_count,
        "interaction_count": inter_count, "gate_count": gate_count,
        "formula_count": formula_count
    }


def write_formula_catalog(path, spec, feature_names):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["formula_id", "formula_type", "formula_size", "feature_indices",
                         "features", "interaction_pair", "gate_feature", "gate_threshold",
                         "weight", "search_source"])
        for i, formula_id in enumerate(spec["formula_ids"]):
            code = int(spec["type_codes"][i])
            size = int(spec["sizes"][i])
            ids = [int(x) for x in spec["feature_ids"][i, :size]]
            interaction_pair = ""
            gate_feature = ""
            threshold = ""
            weight = ""
            if code == 1:
                a, b = spec["selected_pairs_global"][int(spec["aux_pair"][i])]
                interaction_pair = f"{feature_names[a]}*{feature_names[b]}"
                weight = INTERACTION_WEIGHT
            elif code == 2:
                pos = int(spec["gate_positions"][i])
                gate_feature = feature_names[ids[pos]]
                threshold = float(spec["gate_thresholds"][i])
                weight = GATE_BONUS
            writer.writerow([formula_id, TYPE_NAMES[code], size, ";".join(map(str, ids)),
                             spec["feature_strings"][i], interaction_pair, gate_feature,
                             threshold, weight, "discovery_selected_feature_subset"])


def score_target(X, spec):
    feature_count = spec["linear_formula_count"]
    scores = np.empty((40, spec["formula_count"]), dtype=np.float64)
    # Preserve discovery-selected feature order used to build the weight matrix.
    X_selected = X[:, spec["selected_indices"]].astype(np.float64, copy=False)
    linear_scores = X_selected @ spec["weights"]
    scores[:, :feature_count] = linear_scores
    np.round(scores[:, :feature_count], 12, out=scores[:, :feature_count])

    l4_start, l4_end = spec["group_slices"]["L4"]
    base4 = scores[:, l4_start:l4_end]
    pairz = np.empty((40, len(spec["selected_pairs_global"])), dtype=np.float64)
    for j, (a, b) in enumerate(spec["selected_pairs_global"]):
        product = X[:, a] * X[:, b]
        sd = float(product.std())
        if sd < 1e-12:
            sd = 1.0
        pairz[:, j] = (product - product.mean()) / sd

    i_start, i_end = spec["group_slices"]["I4"]
    scores[:, i_start:i_end] = (
        base4[:, spec["aux_combo"][i_start:i_end]]
        + INTERACTION_WEIGHT * pairz[:, spec["aux_pair"][i_start:i_end]]
    )
    np.round(scores[:, i_start:i_end], 12, out=scores[:, i_start:i_end])

    g_start, g_end = spec["group_slices"]["G4"]
    gate_feature_ids = spec["feature_ids"][g_start:g_end, spec["gate_positions"][g_start:g_end]]
    scores[:, g_start:g_end] = (
        base4[:, spec["aux_combo"][g_start:g_end]]
        + GATE_BONUS * (X[:, gate_feature_ids] >= spec["gate_thresholds"][g_start:g_end][None, :])
    )
    np.round(scores[:, g_start:g_end], 12, out=scores[:, g_start:g_end])
    return scores


def rank_actuals(scores, actual_indices):
    formula_count = scores.shape[1]
    ranks = np.empty((5, formula_count), dtype=np.int16)
    candidate_indices = np.arange(40)[:, None]
    for j, actual in enumerate(actual_indices):
        actual_score = scores[int(actual), :][None, :]
        greater = (scores > actual_score).sum(axis=0)
        equal_lower = ((scores == actual_score) & (candidate_indices < int(actual))).sum(axis=0)
        ranks[j] = 1 + greater + equal_lower
    return ranks


def best_formula_index(start, end, rank_sum, hits5, hits10, hits20):
    local_rank = rank_sum[start:end]
    minimum = local_rank.min()
    candidates = np.flatnonzero(local_rank == minimum)
    if len(candidates) > 1:
        local_h5 = hits5[start:end][candidates]
        candidates = candidates[local_h5 == local_h5.max()]
    if len(candidates) > 1:
        local_h10 = hits10[start:end][candidates]
        candidates = candidates[local_h10 == local_h10.max()]
    if len(candidates) > 1:
        local_h20 = hits20[start:end][candidates]
        candidates = candidates[local_h20 == local_h20.max()]
    return start + int(candidates[0])


def upper_top5_hypergeometric_p(successes, targets):
    if targets <= 0:
        return np.ones_like(successes, dtype=np.float64)
    mean_per_draw = 5.0 * (5.0 / 40.0)
    variance_per_draw = 5.0 * (5.0 / 40.0) * (1.0 - 5.0 / 40.0) * (40.0 - 5.0) / (40.0 - 1.0)
    z = (successes.astype(np.float64) - 0.5 - targets * mean_per_draw) / math.sqrt(targets * variance_per_draw)
    return np.clip(0.5 * erfc(z / math.sqrt(2.0)), 0.0, 1.0)


def lower_mean_rank_p(rank_sum, targets):
    if targets <= 0:
        return np.ones_like(rank_sum, dtype=np.float64)
    mean_per_draw = 5.0 * 20.5
    variance_per_draw = 5.0 * 133.25 * (40.0 - 5.0) / (40.0 - 1.0)
    z = (rank_sum.astype(np.float64) - 0.5 - targets * mean_per_draw) / math.sqrt(targets * variance_per_draw)
    return np.clip(0.5 * erfc(-z / math.sqrt(2.0)), 0.0, 1.0)


def holm_adjust_array(p_values):
    order = np.argsort(p_values, kind="mergesort")
    sorted_values = p_values[order]
    adjusted_sorted = np.maximum.accumulate(np.minimum(1.0, (len(p_values) - np.arange(len(p_values))) * sorted_values))
    adjusted = np.empty_like(adjusted_sorted)
    adjusted[order] = adjusted_sorted
    return adjusted


def build_family_summary(split, acc, targets_by_split, spec):
    rows = []
    trials = 5 * targets_by_split[split]
    for code, type_name in enumerate(TYPE_NAMES):
        sizes_for_type = sorted(set(int(x) for x in spec["sizes"][spec["type_codes"] == code]))
        for size in sizes_for_type:
            mask = (spec["type_codes"] == code) & (spec["sizes"] == size)
            idx = np.flatnonzero(mask)
            if not len(idx):
                continue
            rank_sum = acc[split]["rank_sum"][idx]
            h5 = acc[split]["hits5"][idx]
            h10 = acc[split]["hits10"][idx]
            h20 = acc[split]["hits20"][idx]
            holm5 = acc[split]["holm_top5"][idx]
            holmrank = acc[split]["holm_rank_lower"][idx]
            order = np.argsort(rank_sum / trials, kind="mergesort")[:10]
            top10 = []
            for local in order:
                fi = int(idx[local])
                top10.append({"formula_id": spec["formula_ids"][fi],
                              "mean_actual_number_rank": float(rank_sum[local] / trials),
                              "mean_number_hits_top5": float(h5[local] / trials),
                              "holm_top5": float(holm5[local]),
                              "holm_rank_lower": float(holmrank[local])})
            rows.append({
                "split": split, "formula_type": type_name, "formula_size": size,
                "formula_count": int(len(idx)),
                "mean_formula_number_hits_top5": float(np.mean(h5 / trials)),
                "mean_formula_number_hits_top10": float(np.mean(h10 / trials)),
                "mean_formula_number_hits_top20": float(np.mean(h20 / trials)),
                "mean_formula_actual_number_rank": float(np.mean(rank_sum / trials)),
                "holm_top5_below_0_05": int(np.sum(holm5 < 0.05)),
                "holm_rank_lower_below_0_05": int(np.sum(holmrank < 0.05)),
                "top10_by_mean_actual_number_rank": top10
            })
    return rows


def main():
    dates, draws = q80.load_archive()
    n = len(draws)
    if n <= MIN_HISTORY:
        raise SystemExit("Q90_BLOCKED: archive too short")
    archive_blob_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD:data/storico_daily.csv"], cwd=ROOT, text=True
    ).strip()
    q89_manifest = json.loads(Q89_MANIFEST.read_text(encoding="utf-8"))
    q89_catalog = json.loads(Q89_CATALOG.read_text(encoding="utf-8"))
    if q89_manifest["archive_blob_sha"] != archive_blob_sha:
        raise SystemExit("Q90_BLOCKED: Q89 matrix manifest archive SHA differs from current archive")
    if sha256_file(Q89_MATRIX) != q89_manifest["feature_matrix_sha256"]:
        raise SystemExit("Q90_BLOCKED: Q89 feature matrix SHA mismatch")
    with np.load(Q89_MATRIX, allow_pickle=False) as z:
        feature_matrix = z["feature_matrix"]
        target_dates = z["target_dates"].tolist()
        cutoff_dates = z["cutoff_dates"].tolist()
        actual_quintets = z["actual_quintets"].astype(np.int16)
        feature_names = z["feature_names"].tolist()
        matrix_archive_sha = str(z["archive_blob_sha"].item())
    expected_targets = n - MIN_HISTORY
    if feature_matrix.shape != (expected_targets, 40, 59) or feature_matrix.dtype != np.float32:
        raise SystemExit(f"Q90_BLOCKED: Q89 matrix shape/dtype mismatch {feature_matrix.shape}/{feature_matrix.dtype}")
    if matrix_archive_sha != archive_blob_sha or feature_names != q89_catalog["baseline_features"] + q89_catalog["new_features"]:
        raise SystemExit("Q90_BLOCKED: Q89 matrix lineage/schema mismatch")
    if target_dates != dates[MIN_HISTORY:] or cutoff_dates != dates[MIN_HISTORY - 1:n - 1]:
        raise SystemExit("Q90_BLOCKED: Q89 matrix target/cutoff chronology mismatch")
    if actual_quintets.tolist() != [list(x) for x in draws[MIN_HISTORY:]]:
        raise SystemExit("Q90_BLOCKED: Q89 matrix actual quintets mismatch")

    family_by_feature = {name: "baseline" for name in q89_catalog["baseline_features"]}
    family_by_feature.update(q89_catalog["new_feature_family_map"])
    with Q89_SPLIT_METRICS.open(newline="", encoding="utf-8") as f:
        split_rows = list(csv.DictReader(f))
    selected_names, selection_report = select_features(split_rows, family_by_feature)
    selected_indices = np.asarray([feature_names.index(name) for name in selected_names], dtype=np.uint8)
    spec = build_formula_catalog(selected_indices, feature_names)

    OUT.mkdir(parents=True, exist_ok=True)
    catalog_path = OUT / "q90_formula_catalog.csv"
    split_metrics_path = OUT / "q90_split_metrics.csv"
    target_ledger_path = OUT / "q90_target_ledger.csv"
    feature_selection_path = OUT / "q90_feature_selection.json"
    family_summary_path = OUT / "q90_formula_family_split_summary.json"
    manifest_path = OUT / "q90_formula_metrics_manifest.json"
    checkpoint_path = OUT / f"q90_checkpoint_{dates[-1]}.json"

    feature_selection_path.write_text(json.dumps(selection_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_formula_catalog(catalog_path, spec, feature_names)

    split_names = ("discovery", "validation", "blind_oos")
    targets_by_split = {split: sum(q80.split_name(t, expected_targets) == split for t in range(expected_targets))
                         for split in split_names}
    fields = ("rank_sum", "hits5", "hits10", "hits20", "all5_top5", "all5_top10", "all5_top20")
    acc = {split: {field: np.zeros(spec["formula_count"], dtype=np.int64) for field in fields}
            for split in split_names}
    target_rows = []
    group_names = tuple(spec["group_slices"].keys())

    for t in range(expected_targets):
        X = feature_matrix[t].astype(np.float64)
        scores = score_target(X, spec)
        actual_indices = actual_quintets[t].astype(int) - 1
        ranks = rank_actuals(scores, actual_indices)
        rank_sum = ranks.sum(axis=0, dtype=np.int64)
        hits5 = (ranks <= 5).sum(axis=0, dtype=np.int64)
        hits10 = (ranks <= 10).sum(axis=0, dtype=np.int64)
        hits20 = (ranks <= 20).sum(axis=0, dtype=np.int64)
        all5_top5 = (ranks <= 5).all(axis=0).astype(np.int64)
        all5_top10 = (ranks <= 10).all(axis=0).astype(np.int64)
        all5_top20 = (ranks <= 20).all(axis=0).astype(np.int64)
        split = q80.split_name(t, expected_targets)
        a = acc[split]
        a["rank_sum"] += rank_sum
        a["hits5"] += hits5
        a["hits10"] += hits10
        a["hits20"] += hits20
        a["all5_top5"] += all5_top5
        a["all5_top10"] += all5_top10
        a["all5_top20"] += all5_top20

        oracle_idx = best_formula_index(0, spec["formula_count"], rank_sum, hits5, hits10, hits20)
        row = {
            "target_date": target_dates[t], "cutoff_date": cutoff_dates[t],
            "prior_draws": t + MIN_HISTORY, "split": split,
            "actual_quintet": " ".join(map(str, actual_quintets[t].tolist())),
            "formula_count_tested": spec["formula_count"],
            "oracle_best_formula_id": spec["formula_ids"][oracle_idx],
            "oracle_best_formula_type": TYPE_NAMES[int(spec["type_codes"][oracle_idx])],
            "oracle_best_formula_size": int(spec["sizes"][oracle_idx]),
            "oracle_best_features": spec["feature_strings"][oracle_idx],
            "oracle_actual_number_ranks": json.dumps(ranks[:, oracle_idx].tolist(), separators=(",", ":")),
            "oracle_number_hits_top5": int(hits5[oracle_idx]),
            "oracle_number_hits_top10": int(hits10[oracle_idx]),
            "oracle_number_hits_top20": int(hits20[oracle_idx]),
            "oracle_rank_sum": int(rank_sum[oracle_idx])
        }
        for group in group_names:
            start, end = spec["group_slices"][group]
            fi = best_formula_index(start, end, rank_sum, hits5, hits10, hits20)
            prefix = f"best_{group}"
            row[f"{prefix}_formula_id"] = spec["formula_ids"][fi]
            row[f"{prefix}_formula_type"] = TYPE_NAMES[int(spec["type_codes"][fi])]
            row[f"{prefix}_formula_size"] = int(spec["sizes"][fi])
            row[f"{prefix}_features"] = spec["feature_strings"][fi]
            row[f"{prefix}_actual_number_ranks"] = json.dumps(ranks[:, fi].tolist(), separators=(",", ":"))
            row[f"{prefix}_number_hits_top5"] = int(hits5[fi])
            row[f"{prefix}_number_hits_top10"] = int(hits10[fi])
            row[f"{prefix}_number_hits_top20"] = int(hits20[fi])
            row[f"{prefix}_rank_sum"] = int(rank_sum[fi])
        target_rows.append(row)

    with target_ledger_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(target_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_rows)

    metric_fields = ["split", "formula_id", "formula_type", "formula_size", "targets",
                     "number_hits_top5", "number_hits_top10", "number_hits_top20",
                     "all5_top5_count", "all5_top10_count", "all5_top20_count", "rank_sum",
                     "mean_number_hits_top5", "mean_number_hits_top10", "mean_number_hits_top20",
                     "all5_top5_rate", "all5_top10_rate", "all5_top20_rate",
                     "mean_actual_number_rank", "p_top5", "holm_top5",
                     "p_rank_lower", "holm_rank_lower"]
    family_summary = []
    for split in split_names:
        targets = targets_by_split[split]
        trials = 5 * targets
        a = acc[split]
        p_top5 = upper_top5_hypergeometric_p(a["hits5"], targets)
        p_rank = lower_mean_rank_p(a["rank_sum"], targets)
        holm_top5 = holm_adjust_array(p_top5)
        holm_rank = holm_adjust_array(p_rank)
        a["holm_top5"] = holm_top5
        a["holm_rank_lower"] = holm_rank
        family_summary.extend(build_family_summary(split, a, targets_by_split, spec))

    with split_metrics_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=metric_fields)
        writer.writeheader()
        for split in split_names:
            targets = targets_by_split[split]
            trials = 5 * targets
            a = acc[split]
            for i, formula_id in enumerate(spec["formula_ids"]):
                code = int(spec["type_codes"][i])
                size = int(spec["sizes"][i])
                writer.writerow({
                    "split": split, "formula_id": formula_id, "formula_type": TYPE_NAMES[code],
                    "formula_size": size, "targets": targets,
                    "number_hits_top5": int(a["hits5"][i]),
                    "number_hits_top10": int(a["hits10"][i]),
                    "number_hits_top20": int(a["hits20"][i]),
                    "all5_top5_count": int(a["all5_top5"][i]),
                    "all5_top10_count": int(a["all5_top10"][i]),
                    "all5_top20_count": int(a["all5_top20"][i]),
                    "rank_sum": int(a["rank_sum"][i]),
                    "mean_number_hits_top5": float(a["hits5"][i] / trials),
                    "mean_number_hits_top10": float(a["hits10"][i] / trials),
                    "mean_number_hits_top20": float(a["hits20"][i] / trials),
                    "all5_top5_rate": float(a["all5_top5"][i] / targets),
                    "all5_top10_rate": float(a["all5_top10"][i] / targets),
                    "all5_top20_rate": float(a["all5_top20"][i] / targets),
                    "mean_actual_number_rank": float(a["rank_sum"][i] / trials),
                    "p_top5": float(p_top5[i]), "holm_top5": float(holm_top5[i]),
                    "p_rank_lower": float(p_rank[i]), "holm_rank_lower": float(holm_rank[i])
                })

    family_summary_path.write_text(json.dumps({
        "schema_version": "1.0", "task_id": "Q90",
        "status": "EXPLORATORY_FORMULA_FAMILY_SUMMARY_PENDING_ACCEPTANCE",
        "formula_count": spec["formula_count"], "split_target_counts": targets_by_split,
        "family_split_summary": family_summary,
        "guardrails": ["means summarize the catalog and do not promote formulas",
                       "top formulas are retrospective within each split",
                       "Holm correction is across the full formula catalog within split and endpoint"]
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    formula_type_counts = {name: int(np.sum(spec["type_codes"] == code)) for code, name in enumerate(TYPE_NAMES)}
    formula_size_counts = {f"L{k}": int(spec["linear_counts"][k]) for k in LINEAR_SIZES}
    formula_size_counts.update({"I4": int(spec["interaction_count"]), "G4": int(spec["gate_count"])})
    manifest = {
        "schema_version": "1.0", "task_id": "Q90",
        "status": "FORMULA_ENGINE_EXECUTED_PENDING_ACCEPTANCE",
        "archive": {"path": "data/storico_daily.csv", "blob_sha": archive_blob_sha,
                    "draw_count": n, "first_date": dates[0], "last_date": dates[-1]},
        "q89_feature_matrix": {"path": str(Q89_MATRIX.relative_to(ROOT)),
                               "sha256": q89_manifest["feature_matrix_sha256"],
                               "shape": [expected_targets, 40, 59], "dtype": "float32"},
        "scored_targets": expected_targets, "selected_feature_count": len(selected_names),
        "selected_features": selected_names, "selected_feature_families": selection_report["family_quotas"],
        "formula_grammar": {
            "scope": "Exhaustive within the discovery-selected 20-feature subset and declared formula variants; not all 59-feature combinations or all mathematical formulas.",
            "linear_equal_weight_sizes": list(LINEAR_SIZES),
            "linear_formula_counts_by_size": formula_size_counts,
            "pairwise_interaction_grammar": "4-feature mean + 0.25*zscore(product of one selected feature pair); all six pairs for every 4-feature combination",
            "conditional_gate_grammar": "4-feature mean + 0.25*indicator(feature >= threshold); each of four component features gated at thresholds 0.5 and 1.0",
            "interaction_weight": INTERACTION_WEIGHT, "gate_bonus": GATE_BONUS,
            "gate_thresholds": list(GATE_THRESHOLDS),
            "formula_type_counts": formula_type_counts, "formula_count": spec["formula_count"],
            "formula_count_check": sum(math.comb(20, k) for k in LINEAR_SIZES)
                                  + math.comb(20, 4) * math.comb(4, 2)
                                  + math.comb(20, 4) * 4 * len(GATE_THRESHOLDS)
        },
        "split_target_counts": targets_by_split,
        "metrics_rows": spec["formula_count"] * len(split_names),
        "target_ledger_rows": len(target_rows),
        "formula_catalog_sha256": sha256_file(catalog_path),
        "split_metrics_sha256": sha256_file(split_metrics_path),
        "target_ledger_sha256": sha256_file(target_ledger_path),
        "feature_selection_sha256": sha256_file(feature_selection_path),
        "family_summary_sha256": sha256_file(family_summary_path),
        "multiple_testing": {"method": "Holm-Bonferroni",
                             "adjustment_family": "all 330429 formulas within each chronological split",
                             "endpoints": ["top5 number-hit upper-tail", "mean actual rank lower-tail"],
                             "p_value_method": "continuity-corrected normal approximations with finite-population hypergeometric variance; exploratory"},
        "guardrails": ["Q89 features are strict prior-only at each target",
                       "feature subset selection uses discovery split only",
                       "formula scores use only the Q89 matrix for that target",
                       "per-target oracle formula uses actual target ranks and is retrospective",
                       "no formula or model promotion",
                       "immutable target-2026-10-25 freeze remains untouched"],
        "pending": ["nested walk-forward ex-ante formula anticipation and calibration",
                    "expand conditional gates and interactions beyond the 4-feature slice",
                    "independent persisted-artifact readback",
                    "exact-head CI and human review"]
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0", "task_id": "Q90",
        "status": "FORMULA_ENGINE_EXECUTED_PENDING_ACCEPTANCE",
        "checkpoint_date": dates[-1], "archive_blob_sha": archive_blob_sha,
        "draw_count": n, "scored_targets": expected_targets,
        "selected_feature_count": len(selected_names), "formula_count": spec["formula_count"],
        "formula_catalog_sha256": manifest["formula_catalog_sha256"],
        "split_metrics_sha256": manifest["split_metrics_sha256"],
        "target_ledger_sha256": manifest["target_ledger_sha256"],
        "pending": manifest["pending"]
    }
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SONAR_Q90_SUMMARY_BEGIN")
    print(json.dumps({k: manifest[k] for k in
        ("task_id", "status", "archive", "scored_targets", "selected_feature_count",
         "formula_grammar", "split_target_counts", "metrics_rows", "target_ledger_rows")},
        ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q90_SUMMARY_END")


if __name__ == "__main__":
    main()
