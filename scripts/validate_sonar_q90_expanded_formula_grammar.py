#!/usr/bin/env python3
"""Fail-closed acceptance validator for Q90 expanded formula grammar outputs."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from scipy.special import erfc
import sonar_per_number_condition_grammar as q80

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
Q89_MATRIX = OUT / "adaptive_novelty_feature_matrix.npz"
Q89_MANIFEST = OUT / "adaptive_novelty_formula_metrics_manifest.json"
MANIFEST_PATH = OUT / "q90_formula_metrics_manifest.json"
CATALOG_PATH = OUT / "q90_formula_catalog.csv"
METRICS_PATH = OUT / "q90_split_metrics.csv"
LEDGER_PATH = OUT / "q90_target_ledger.csv"
SELECTION_PATH = OUT / "q90_feature_selection.json"
FAMILY_PATH = OUT / "q90_formula_family_split_summary.json"
FORMULA_COUNT = 330429
MIN_HISTORY = 50
SPLITS = ("discovery", "validation", "blind_oos")
TYPE_NAMES = ("linear_mean", "pairwise_interaction", "conditional_gate")


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upper_top5_hypergeometric_p(successes, targets):
    mean_per_draw = 5.0 * (5.0 / 40.0)
    variance_per_draw = 5.0 * (5.0 / 40.0) * (1.0 - 5.0 / 40.0) * (40.0 - 5.0) / (40.0 - 1.0)
    z = (successes.astype(np.float64) - 0.5 - targets * mean_per_draw) / math.sqrt(targets * variance_per_draw)
    return np.clip(0.5 * erfc(z / math.sqrt(2.0)), 0.0, 1.0)


def lower_mean_rank_p(rank_sum, targets):
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


def check_rank_vector(raw, prefix, formula_map, expected_type=None, expected_size=None):
    formula_id = raw[f"{prefix}_formula_id"]
    if formula_id not in formula_map:
        raise AssertionError(f"unknown formula ID {formula_id}")
    formula_type, formula_size = formula_map[formula_id]
    if expected_type is not None and formula_type != expected_type:
        raise AssertionError(f"{prefix}: type {formula_type} != {expected_type}")
    if expected_size is not None and formula_size != expected_size:
        raise AssertionError(f"{prefix}: size {formula_size} != {expected_size}")
    ranks = [int(x) for x in json.loads(raw[f"{prefix}_actual_number_ranks"])]
    if len(ranks) != 5 or any(x < 1 or x > 40 for x in ranks):
        raise AssertionError(f"{prefix}: invalid actual ranks")
    for k in (5, 10, 20):
        hits = sum(x <= k for x in ranks)
        if int(raw[f"{prefix}_number_hits_top{k}"]) != hits:
            raise AssertionError(f"{prefix}: top{k} hit count mismatch")
    if int(raw[f"{prefix}_rank_sum"]) != sum(ranks):
        raise AssertionError(f"{prefix}: rank sum mismatch")
    return formula_id, ranks


def main():
    dates, draws = q80.load_archive()
    n = len(draws)
    expected_targets = n - MIN_HISTORY
    expected_blob = subprocess.check_output(
        ["git", "rev-parse", "HEAD:data/storico_daily.csv"], cwd=ROOT, text=True
    ).strip()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    q89_manifest = json.loads(Q89_MANIFEST.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    family_summary = json.loads(FAMILY_PATH.read_text(encoding="utf-8"))

    assert manifest["task_id"] == "Q90"
    assert manifest["archive"]["blob_sha"] == expected_blob
    assert manifest["archive"]["draw_count"] == n and manifest["archive"]["last_date"] == dates[-1]
    assert manifest["scored_targets"] == expected_targets
    assert manifest["formula_grammar"]["formula_count"] == FORMULA_COUNT
    assert manifest["formula_grammar"]["formula_count_check"] == FORMULA_COUNT
    assert manifest["metrics_rows"] == FORMULA_COUNT * 3
    assert manifest["target_ledger_rows"] == expected_targets
    assert "finite-population" in manifest["multiple_testing"]["p_value_method"]
    assert manifest["q89_feature_matrix"]["sha256"] == q89_manifest["feature_matrix_sha256"]
    assert q89_manifest["archive_blob_sha"] == expected_blob
    assert sha256_file(Q89_MATRIX) == q89_manifest["feature_matrix_sha256"]

    expected_hashes = {
        "formula_catalog_sha256": CATALOG_PATH,
        "split_metrics_sha256": METRICS_PATH,
        "target_ledger_sha256": LEDGER_PATH,
        "feature_selection_sha256": SELECTION_PATH,
        "family_summary_sha256": FAMILY_PATH
    }
    for field, path in expected_hashes.items():
        assert manifest[field] == sha256_file(path), f"SHA mismatch: {field}"

    assert len(selection["selected_features"]) == 20
    selected_names = [x["feature"] for x in selection["selected_features"]]
    assert len(set(selected_names)) == 20
    expected_quotas = {
        "baseline": 3, "cooccurrence_novelty": 3, "ewma_hit_dynamics": 3,
        "gap_dynamics": 3, "rank_trajectory": 3,
        "regime_transition_affinity": 3, "residual_surprise": 2
    }
    assert selection["family_quotas"] == expected_quotas
    assert manifest["selected_feature_families"] == expected_quotas

    with np.load(Q89_MATRIX, allow_pickle=False) as z:
        fm = z["feature_matrix"]
        td = z["target_dates"].tolist()
        cd = z["cutoff_dates"].tolist()
        aq = z["actual_quintets"].astype(int).tolist()
        matrix_sha = str(z["archive_blob_sha"].item())
        names = z["feature_names"].tolist()
    assert fm.shape == (expected_targets, 40, 59) and fm.dtype == np.float32
    assert np.isfinite(fm).all()
    assert np.max(np.abs(fm.mean(axis=1))) < 1e-5
    assert matrix_sha == expected_blob
    assert td == dates[MIN_HISTORY:]
    assert cd == dates[MIN_HISTORY - 1:n - 1]
    assert aq == [list(x) for x in draws[MIN_HISTORY:]]
    assert len(names) == 59

    expected_formula_counts = {
        ("linear_mean", 4): 4845, ("linear_mean", 5): 15504,
        ("linear_mean", 6): 38760, ("linear_mean", 7): 77520,
        ("linear_mean", 8): 125970, ("pairwise_interaction", 4): 29070,
        ("conditional_gate", 4): 38760
    }
    formula_ids = []
    formula_map = {}
    observed_counts = {}
    with CATALOG_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            formula_id = row["formula_id"]
            if formula_id in formula_map:
                raise AssertionError(f"duplicate formula ID {formula_id}")
            formula_type = row["formula_type"]
            formula_size = int(row["formula_size"])
            indices = [int(x) for x in row["feature_indices"].split(";")]
            if len(indices) != formula_size or any(x < 0 or x >= 59 for x in indices):
                raise AssertionError(f"invalid feature index list for {formula_id}")
            formula_map[formula_id] = (formula_type, formula_size)
            formula_ids.append(formula_id)
            key = (formula_type, formula_size)
            observed_counts[key] = observed_counts.get(key, 0) + 1
    assert len(formula_ids) == FORMULA_COUNT
    assert observed_counts == expected_formula_counts
    assert manifest["formula_grammar"]["formula_type_counts"] == {
        "linear_mean": 262599, "pairwise_interaction": 29070, "conditional_gate": 38760
    }

    targets_by_split = {
        split: sum(q80.split_name(t, expected_targets) == split for t in range(expected_targets))
        for split in SPLITS
    }
    assert manifest["split_target_counts"] == targets_by_split
    expected_metric_rows = FORMULA_COUNT * len(SPLITS)

    for split in SPLITS:
        targets = targets_by_split[split]
        trials = 5 * targets
        hits5 = np.empty(FORMULA_COUNT, dtype=np.int64)
        hits10 = np.empty(FORMULA_COUNT, dtype=np.int64)
        hits20 = np.empty(FORMULA_COUNT, dtype=np.int64)
        rank_sum = np.empty(FORMULA_COUNT, dtype=np.int64)
        all5_5 = np.empty(FORMULA_COUNT, dtype=np.int64)
        all5_10 = np.empty(FORMULA_COUNT, dtype=np.int64)
        all5_20 = np.empty(FORMULA_COUNT, dtype=np.int64)
        file_p5 = np.empty(FORMULA_COUNT, dtype=np.float64)
        file_holm5 = np.empty(FORMULA_COUNT, dtype=np.float64)
        file_prank = np.empty(FORMULA_COUNT, dtype=np.float64)
        file_holmrank = np.empty(FORMULA_COUNT, dtype=np.float64)
        with METRICS_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            split_index = SPLITS.index(split)
            for _ in range(FORMULA_COUNT * split_index):
                next(reader)
            for idx in range(FORMULA_COUNT):
                row = next(reader)
                if row["split"] != split or row["formula_id"] != formula_ids[idx]:
                    raise AssertionError(f"formula metrics order/coverage mismatch at {split}/{idx}")
                formula_type, formula_size = formula_map[row["formula_id"]]
                if row["formula_type"] != formula_type or int(row["formula_size"]) != formula_size:
                    raise AssertionError("formula metrics type/size mismatch")
                if int(row["targets"]) != targets:
                    raise AssertionError("formula metrics target count mismatch")
                hits5[idx] = int(row["number_hits_top5"])
                hits10[idx] = int(row["number_hits_top10"])
                hits20[idx] = int(row["number_hits_top20"])
                rank_sum[idx] = int(row["rank_sum"])
                all5_5[idx] = int(row["all5_top5_count"])
                all5_10[idx] = int(row["all5_top10_count"])
                all5_20[idx] = int(row["all5_top20_count"])
                if not (0 <= hits5[idx] <= trials and 0 <= hits10[idx] <= trials and 0 <= hits20[idx] <= trials):
                    raise AssertionError("number-hit count out of range")
                if not (0 <= all5_5[idx] <= targets and 0 <= all5_10[idx] <= targets and 0 <= all5_20[idx] <= targets):
                    raise AssertionError("all-five hit count out of range")
                if not (trials <= rank_sum[idx] <= 200 * targets):
                    raise AssertionError("rank sum out of range")
                for field, expected in (
                    ("mean_number_hits_top5", hits5[idx] / trials),
                    ("mean_number_hits_top10", hits10[idx] / trials),
                    ("mean_number_hits_top20", hits20[idx] / trials),
                    ("all5_top5_rate", all5_5[idx] / targets),
                    ("all5_top10_rate", all5_10[idx] / targets),
                    ("all5_top20_rate", all5_20[idx] / targets),
                    ("mean_actual_number_rank", rank_sum[idx] / trials)
                ):
                    if abs(float(row[field]) - expected) > 1e-12:
                        raise AssertionError(f"formula metric mismatch {field}")
                file_p5[idx] = float(row["p_top5"])
                file_holm5[idx] = float(row["holm_top5"])
                file_prank[idx] = float(row["p_rank_lower"])
                file_holmrank[idx] = float(row["holm_rank_lower"])
            if split == "blind_oos" and next(reader, None) is not None:
                raise AssertionError("unexpected extra formula metrics rows")
        p5 = upper_top5_hypergeometric_p(hits5, targets)
        prank = lower_mean_rank_p(rank_sum, targets)
        if np.max(np.abs(file_p5 - p5)) > 1e-12 or np.max(np.abs(file_prank - prank)) > 1e-12:
            raise AssertionError(f"raw p-value recomputation mismatch in {split}")
        holm5 = holm_adjust_array(p5)
        holmrank = holm_adjust_array(prank)
        if np.max(np.abs(file_holm5 - holm5)) > 1e-12 or np.max(np.abs(file_holmrank - holmrank)) > 1e-12:
            raise AssertionError(f"Holm adjustment mismatch in {split}")

    ledger_rows = 0
    group_expectations = {
        "L4": ("linear_mean", 4), "L5": ("linear_mean", 5),
        "L6": ("linear_mean", 6), "L7": ("linear_mean", 7),
        "L8": ("linear_mean", 8), "I4": ("pairwise_interaction", 4),
        "G4": ("conditional_gate", 4)
    }
    with LEDGER_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for t, row in enumerate(reader):
            i = t + MIN_HISTORY
            if t >= expected_targets:
                raise AssertionError("target ledger has extra rows")
            expected_split = q80.split_name(t, expected_targets)
            expected_actual = " ".join(map(str, draws[i]))
            if (row["target_date"] != dates[i] or row["cutoff_date"] != dates[i - 1]
                    or int(row["prior_draws"]) != i or row["split"] != expected_split
                    or row["actual_quintet"] != expected_actual
                    or int(row["formula_count_tested"]) != FORMULA_COUNT):
                raise AssertionError(f"target chronology mismatch at index {t}")
            check_rank_vector(row, "oracle", formula_map)
            for group, (formula_type, formula_size) in group_expectations.items():
                check_rank_vector(row, f"best_{group}", formula_map, formula_type, formula_size)
            ledger_rows += 1
    assert ledger_rows == expected_targets

    assert family_summary["task_id"] == "Q90"
    assert family_summary["formula_count"] == FORMULA_COUNT
    assert family_summary["split_target_counts"] == targets_by_split
    assert len(family_summary["family_split_summary"]) == 21
    print("Q90_FORMULA_ACCEPTANCE_PASS",
          FORMULA_COUNT, expected_metric_rows, ledger_rows,
          expected_blob, dates[-1], manifest["formula_catalog_sha256"],
          manifest["split_metrics_sha256"], manifest["target_ledger_sha256"])


if __name__ == "__main__":
    main()
