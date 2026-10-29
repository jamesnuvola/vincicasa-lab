#!/usr/bin/env python3
"""Distributed walk-forward evaluation of every 6-feature equal-weight formula (Q86)."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import sonar_per_number_condition_grammar as q80
import sonar_per_number_condition_5plus_grammar as q83

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
DEFAULT_OUT = ROOT / "reports" / "sequence_agent" / "q86_shards"
MIN_HISTORY = q80.MIN_HISTORY
FEATURE_NAMES = q80.FEATURE_NAMES
FEATURE_COUNT = len(FEATURE_NAMES)
FORMULA_SIZE = 6
FORMULA_COUNT = math.comb(FEATURE_COUNT, FORMULA_SIZE)
SPLITS = ("discovery", "validation", "blind_oos")


def formula_slice(start: int, end: int):
    if start < 0 or end < start or end > FORMULA_COUNT:
        raise ValueError("invalid Q86 formula slice")
    formulas = list(itertools.islice(
        itertools.combinations(range(FEATURE_COUNT), FORMULA_SIZE), start, end
    ))
    if len(formulas) != end - start:
        raise RuntimeError("Q86 formula slice has missing combinations")
    return formulas


def formula_id(index: int, columns) -> str:
    return "P6_" + "_".join(f"{column:02d}" for column in columns)


def formula_features(columns) -> str:
    return "+".join(FEATURE_NAMES[column] for column in columns)


def build_formula_weight_matrix(formulas):
    weights = np.zeros((FEATURE_COUNT, len(formulas)), dtype=np.float64)
    for local_index, columns in enumerate(formulas):
        weights[list(columns), local_index] = 1.0 / FORMULA_SIZE
    return weights


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, default=16)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        raise SystemExit("Q86_BLOCKED: invalid shard index/count")

    dates, draws = q80.load_archive()
    target_count = len(draws)
    scored_targets = target_count - MIN_HISTORY
    if scored_targets <= 0:
        raise SystemExit("Q86_BLOCKED: archive has no targets with sufficient prior history")
    if FORMULA_COUNT != math.comb(FEATURE_COUNT, FORMULA_SIZE):
        raise SystemExit("Q86_BLOCKED: formula universe count mismatch")

    formula_start = (FORMULA_COUNT * args.shard_index) // args.shard_count
    formula_end = (FORMULA_COUNT * (args.shard_index + 1)) // args.shard_count
    formulas = formula_slice(formula_start, formula_end)
    if not formulas:
        raise SystemExit("Q86_BLOCKED: empty formula shard")
    weights = build_formula_weight_matrix(formulas)
    standardized_stack = q83.build_feature_stack(draws)
    expected_shape = (scored_targets, 40, FEATURE_COUNT)
    if standardized_stack.shape != expected_shape:
        raise SystemExit(f"Q86_BLOCKED: feature stack shape {standardized_stack.shape} != {expected_shape}")

    metric_fields = (
        "number_hits_top5", "number_hits_top10", "number_hits_top20",
        "all5_top5", "all5_top10", "all5_top20", "rank_sum",
    )
    accum = {
        split: {field: np.zeros(len(formulas), dtype=np.int64) for field in metric_fields}
        for split in SPLITS
    }
    split_counts = Counter()
    target_rows = []

    for target_offset, target_index in enumerate(range(MIN_HISTORY, target_count)):
        standardized = standardized_stack[target_offset]
        actual_indices = np.asarray(draws[target_index], dtype=np.int64) - 1
        split = q80.split_name(target_offset, scored_targets)
        split_counts[split] += 1
        ranks = q83.rank_matrix(standardized @ weights)
        actual_ranks = ranks[actual_indices, :]
        rank_sum = actual_ranks.sum(axis=0, dtype=np.int64)
        hits5 = np.sum(actual_ranks <= 5, axis=0, dtype=np.int64)
        hits10 = np.sum(actual_ranks <= 10, axis=0, dtype=np.int64)
        hits20 = np.sum(actual_ranks <= 20, axis=0, dtype=np.int64)
        bucket = accum[split]
        bucket["number_hits_top5"] += hits5
        bucket["number_hits_top10"] += hits10
        bucket["number_hits_top20"] += hits20
        bucket["all5_top5"] += np.all(actual_ranks <= 5, axis=0)
        bucket["all5_top10"] += np.all(actual_ranks <= 10, axis=0)
        bucket["all5_top20"] += np.all(actual_ranks <= 20, axis=0)
        bucket["rank_sum"] += rank_sum

        # Keep the Q80-Q83 retrospective tie-break ordering for comparability.
        local_best = int(np.lexsort((-hits5, hits20, rank_sum))[0])
        best_ranks = actual_ranks[:, local_best].astype(int).tolist()
        best_columns = formulas[local_best]
        single_ledger = ""
        if args.shard_index == 0:
            single_ranks = q83.rank_matrix(standardized)[actual_indices, :]
            single_items = []
            for column, name in enumerate(FEATURE_NAMES):
                values = single_ranks[:, column].astype(int).tolist()
                single_items.append({
                    "feature": name,
                    "ranks": values,
                    "hits_top5": sum(value <= 5 for value in values),
                    "hits_top10": sum(value <= 10 for value in values),
                    "hits_top20": sum(value <= 20 for value in values),
                    "rank_sum": sum(values),
                })
            single_ledger = json.dumps(single_items, separators=(",", ":"))

        global_best_index = formula_start + local_best
        target_rows.append({
            "target_date": dates[target_index],
            "cutoff_date": dates[target_index - 1],
            "prior_draws": target_index,
            "actual_quintet": " ".join(map(str, draws[target_index])),
            "status": "SCORED",
            "shard_index": args.shard_index,
            "best_formula_index": global_best_index,
            "best_formula_id": formula_id(global_best_index, best_columns),
            "best_formula_features": formula_features(best_columns),
            "best_actual_number_ranks": json.dumps(best_ranks, separators=(",", ":")),
            "best_number_hits_top5": sum(value <= 5 for value in best_ranks),
            "best_number_hits_top10": sum(value <= 10 for value in best_ranks),
            "best_number_hits_top20": sum(value <= 20 for value in best_ranks),
            "best_rank_sum": sum(best_ranks),
            "single_feature_rank_ledger": single_ledger,
        })

    metric_rows = []
    for split in SPLITS:
        targets = int(split_counts[split])
        if targets <= 0:
            raise SystemExit("Q86_BLOCKED: empty chronological split " + split)
        bucket = accum[split]
        for local_index, columns in enumerate(formulas):
            global_index = formula_start + local_index
            metric_rows.append({
                "formula_index": global_index,
                "split": split,
                "formula_id": formula_id(global_index, columns),
                "feature_count": FORMULA_SIZE,
                "features": formula_features(columns),
                "targets": targets,
                "number_hits_top5": int(bucket["number_hits_top5"][local_index]),
                "number_hits_top10": int(bucket["number_hits_top10"][local_index]),
                "number_hits_top20": int(bucket["number_hits_top20"][local_index]),
                "all5_top5": int(bucket["all5_top5"][local_index]),
                "all5_top10": int(bucket["all5_top10"][local_index]),
                "all5_top20": int(bucket["all5_top20"][local_index]),
                "rank_sum": int(bucket["rank_sum"][local_index]),
                "p_top5_normal_approx": q80.binomial_upper_normal_p(
                    int(bucket["number_hits_top5"][local_index]), 5 * targets, 5 / 40
                ),
                "p_top10_normal_approx": q80.binomial_upper_normal_p(
                    int(bucket["number_hits_top10"][local_index]), 5 * targets, 10 / 40
                ),
                "p_top20_normal_approx": q80.binomial_upper_normal_p(
                    int(bucket["number_hits_top20"][local_index]), 5 * targets, 20 / 40
                ),
            })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"q86_shard_{args.shard_index:02d}"
    metrics_path = args.out_dir / f"{prefix}_metrics_raw.csv"
    targets_path = args.out_dir / f"{prefix}_target_candidates.csv"
    meta_path = args.out_dir / f"{prefix}_meta.json"
    write_csv(metrics_path, metric_rows, list(metric_rows[0].keys()))
    write_csv(targets_path, target_rows, list(target_rows[0].keys()))
    meta = {
        "task_id": "Q86",
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "formula_start_inclusive": formula_start,
        "formula_end_exclusive": formula_end,
        "formula_count": len(formulas),
        "formula_count_universe": FORMULA_COUNT,
        "formula_id_first": formula_id(formula_start, formulas[0]),
        "formula_id_last": formula_id(formula_end - 1, formulas[-1]),
        "source_archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "target_count": target_count,
        "first_date": dates[0],
        "last_date": dates[-1],
        "minimum_prior_history": MIN_HISTORY,
        "scored_targets": scored_targets,
        "feature_count": FEATURE_COUNT,
        "metrics_rows": len(metric_rows),
        "target_ledger_rows": len(target_rows),
        "split_counts": {split: int(split_counts[split]) for split in SPLITS},
        "outputs": [metrics_path.name, targets_path.name, meta_path.name],
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if len(metric_rows) != len(formulas) * len(SPLITS) or len(target_rows) != scored_targets:
        raise SystemExit("Q86_BLOCKED: shard output dimensions mismatch")
    print("SONAR_Q86_SHARD_SUMMARY " + json.dumps({
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "formula_start_inclusive": formula_start,
        "formula_end_exclusive": formula_end,
        "formula_count": len(formulas),
        "metrics_rows": len(metric_rows),
        "target_ledger_rows": len(target_rows),
        "archive_sha256": meta["source_archive_sha256"],
        "last_date": dates[-1],
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
