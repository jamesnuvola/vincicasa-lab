#!/usr/bin/env python3
"""Aggregate and globally validate the distributed Q86 six-feature walk-forward search."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sonar_per_number_condition_grammar as q80
from sonar_per_number_condition_6plus_grammar import (
    FEATURE_COUNT, FEATURE_NAMES, FORMULA_COUNT, FORMULA_SIZE, MIN_HISTORY, SPLITS,
    formula_features, formula_id,
)

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
DEFAULT_SHARDS = ROOT / ".q86-shards"
OUT = ROOT / "reports" / "sequence_agent"
METRICS_PARTS = 16


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV header missing: " + str(path))
        return reader.fieldnames, list(reader)


def write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def expected_split_counts(scored_targets: int):
    counts = Counter(q80.split_name(offset, scored_targets) for offset in range(scored_targets))
    return {split: int(counts[split]) for split in SPLITS}


def holm_adjust_matrix(p_values: np.ndarray) -> np.ndarray:
    flat = p_values.reshape(-1)
    if not np.all(np.isfinite(flat)) or np.any(flat < 0) or np.any(flat > 1):
        raise SystemExit("Q86_BLOCKED: non-finite/out-of-range raw p-values")
    order = np.argsort(flat, kind="stable")
    m = flat.size
    adjusted_sorted = np.maximum.accumulate(
        np.minimum(1.0, (m - np.arange(m, dtype=np.float64)) * flat[order])
    )
    adjusted = np.empty_like(flat)
    adjusted[order] = adjusted_sorted
    return adjusted.reshape(p_values.shape)


def validate_rank_vector(raw: str, expected_count: int = 5):
    try:
        values = json.loads(raw)
    except Exception as exc:
        raise SystemExit("Q86_BLOCKED: invalid rank-vector JSON: " + str(exc))
    if not isinstance(values, list) or len(values) != expected_count:
        raise SystemExit("Q86_BLOCKED: rank vector length mismatch")
    if any(not isinstance(value, int) or value < 1 or value > 40 for value in values):
        raise SystemExit("Q86_BLOCKED: rank outside 1..40")
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shard-dir", type=Path, default=DEFAULT_SHARDS)
    parser.add_argument("--out-dir", type=Path, default=OUT)
    parser.add_argument("--shard-count", type=int, default=METRICS_PARTS)
    args = parser.parse_args()
    if args.shard_count != METRICS_PARTS:
        raise SystemExit(f"Q86_BLOCKED: expected {METRICS_PARTS} shards, got {args.shard_count}")

    dates, draws = q80.load_archive()
    target_count = len(draws)
    scored_targets = target_count - MIN_HISTORY
    if scored_targets <= 0:
        raise SystemExit("Q86_BLOCKED: no scored targets")
    archive_sha = sha256(ARCHIVE)
    split_counts = expected_split_counts(scored_targets)
    formula_count = math.comb(FEATURE_COUNT, FORMULA_SIZE)
    if formula_count != FORMULA_COUNT or formula_count != 296010:
        raise SystemExit("Q86_BLOCKED: six-feature formula count mismatch")
    formulas = list(itertools.combinations(range(FEATURE_COUNT), FORMULA_SIZE))
    if len(formulas) != formula_count or len(set(formulas)) != formula_count:
        raise SystemExit("Q86_BLOCKED: formula universe is not complete/unique")

    shard_meta = []
    shard_paths = []
    p_values = np.full((len(SPLITS) * formula_count, 3), np.nan, dtype=np.float64)
    seen = np.zeros((len(SPLITS), formula_count), dtype=np.bool_)
    p_column_names = ("p_top5_normal_approx", "p_top10_normal_approx", "p_top20_normal_approx")

    for shard_index in range(args.shard_count):
        prefix = f"q86_shard_{shard_index:02d}"
        meta_path = args.shard_dir / f"{prefix}_meta.json"
        metrics_path = args.shard_dir / f"{prefix}_metrics_raw.csv"
        targets_path = args.shard_dir / f"{prefix}_target_candidates.csv"
        for path in (meta_path, metrics_path, targets_path):
            if not path.is_file():
                raise SystemExit("Q86_BLOCKED: missing shard artifact " + str(path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected_start = formula_count * shard_index // args.shard_count
        expected_end = formula_count * (shard_index + 1) // args.shard_count
        expected = {
            "task_id": "Q86",
            "shard_index": shard_index,
            "shard_count": args.shard_count,
            "formula_start_inclusive": expected_start,
            "formula_end_exclusive": expected_end,
            "formula_count": expected_end - expected_start,
            "formula_count_universe": formula_count,
            "source_archive_sha256": archive_sha,
            "target_count": target_count,
            "first_date": dates[0],
            "last_date": dates[-1],
            "minimum_prior_history": MIN_HISTORY,
            "scored_targets": scored_targets,
            "feature_count": FEATURE_COUNT,
            "metrics_rows": (expected_end - expected_start) * len(SPLITS),
            "target_ledger_rows": scored_targets,
            "split_counts": split_counts,
        }
        for key, value in expected.items():
            if meta.get(key) != value:
                raise SystemExit(f"Q86_BLOCKED: shard {shard_index} metadata {key}={meta.get(key)!r}, expected {value!r}")
        if meta.get("formula_id_first") != formula_id(expected_start, formulas[expected_start]):
            raise SystemExit("Q86_BLOCKED: shard first formula ID mismatch")
        if meta.get("formula_id_last") != formula_id(expected_end - 1, formulas[expected_end - 1]):
            raise SystemExit("Q86_BLOCKED: shard last formula ID mismatch")
        shard_meta.append(meta)
        shard_paths.append((metrics_path, targets_path, expected_start, expected_end))

        fields, rows = read_csv(metrics_path)
        if len(rows) != expected["metrics_rows"]:
            raise SystemExit(f"Q86_BLOCKED: shard {shard_index} metric row count mismatch")
        for row in rows:
            try:
                formula_index = int(row["formula_index"])
                split_index = SPLITS.index(row["split"])
                feature_count = int(row["feature_count"])
                targets = int(row["targets"])
                counts = [int(row[name]) for name in (
                    "number_hits_top5", "number_hits_top10", "number_hits_top20",
                    "all5_top5", "all5_top10", "all5_top20", "rank_sum",
                )]
                raw_ps = [float(row[name]) for name in p_column_names]
            except Exception as exc:
                raise SystemExit("Q86_BLOCKED: malformed raw metric row: " + str(exc))
            if not expected_start <= formula_index < expected_end:
                raise SystemExit("Q86_BLOCKED: formula index outside its shard range")
            if feature_count != FORMULA_SIZE or targets != split_counts[row["split"]]:
                raise SystemExit("Q86_BLOCKED: feature count or target count mismatch")
            columns = formulas[formula_index]
            if row["formula_id"] != formula_id(formula_index, columns):
                raise SystemExit("Q86_BLOCKED: formula ID/index mismatch")
            if row["features"] != formula_features(columns):
                raise SystemExit("Q86_BLOCKED: formula feature labels/index mismatch")
            if len(set(columns)) != FORMULA_SIZE:
                raise SystemExit("Q86_BLOCKED: repeated feature in formula")
            if any(value < 0 for value in counts):
                raise SystemExit("Q86_BLOCKED: negative metric count")
            if any(value > 5 * targets for value in counts[:3]) or any(value > targets for value in counts[3:6]):
                raise SystemExit("Q86_BLOCKED: metric count exceeds its denominator")
            if not 0 <= counts[6] <= 200 * targets:
                raise SystemExit("Q86_BLOCKED: rank sum outside possible bounds")
            if any(not math.isfinite(value) or not 0 <= value <= 1 for value in raw_ps):
                raise SystemExit("Q86_BLOCKED: raw p-value outside [0,1]")
            if seen[split_index, formula_index]:
                raise SystemExit("Q86_BLOCKED: duplicate formula/split metric row")
            seen[split_index, formula_index] = True
            row_index = split_index * formula_count + formula_index
            p_values[row_index, :] = raw_ps

    if not np.all(seen):
        missing = int(seen.size - int(seen.sum()))
        raise SystemExit(f"Q86_BLOCKED: missing {missing} formula×split rows")
    if not np.all(np.isfinite(p_values)):
        raise SystemExit("Q86_BLOCKED: incomplete global p-value matrix")

    adjusted = holm_adjust_matrix(p_values)
    holm_max = adjusted.max(axis=1)
    significant_rows = int(np.sum(holm_max < 0.05))
    minimum_holm = float(np.min(holm_max))

    # Merge shard-local best candidates into one globally best descriptive rule per target.
    archive_index = {date: index for index, date in enumerate(dates)}
    best_by_date = {}
    single_ledger_by_date = {}
    expected_target_dates = dates[MIN_HISTORY:]
    for shard_index, (_, targets_path, start, end) in enumerate(shard_paths):
        fields, rows = read_csv(targets_path)
        if len(rows) != scored_targets:
            raise SystemExit(f"Q86_BLOCKED: shard {shard_index} target row count mismatch")
        row_dates = [row.get("target_date", "") for row in rows]
        if row_dates != expected_target_dates:
            raise SystemExit(f"Q86_BLOCKED: shard {shard_index} target date coverage/order mismatch")
        for row in rows:
            target_date = row["target_date"]
            target_index = archive_index.get(target_date)
            if target_index is None or target_index < MIN_HISTORY:
                raise SystemExit("Q86_BLOCKED: unknown target date")
            expected_quintet = " ".join(map(str, draws[target_index]))
            if row.get("cutoff_date") != dates[target_index - 1]:
                raise SystemExit("Q86_BLOCKED: target cutoff mismatch")
            if int(row.get("prior_draws", "-1")) != target_index:
                raise SystemExit("Q86_BLOCKED: prior-draw count mismatch")
            if row.get("actual_quintet") != expected_quintet:
                raise SystemExit("Q86_BLOCKED: actual quintet mismatch")
            if row.get("status") != "SCORED" or int(row.get("shard_index", "-1")) != shard_index:
                raise SystemExit("Q86_BLOCKED: target status/shard index mismatch")
            formula_index = int(row["best_formula_index"])
            if not start <= formula_index < end:
                raise SystemExit("Q86_BLOCKED: local best formula index outside shard")
            columns = formulas[formula_index]
            if row["best_formula_id"] != formula_id(formula_index, columns):
                raise SystemExit("Q86_BLOCKED: target best formula ID/index mismatch")
            if row["best_formula_features"] != formula_features(columns):
                raise SystemExit("Q86_BLOCKED: target best formula feature labels mismatch")
            ranks = validate_rank_vector(row["best_actual_number_ranks"])
            rank_sum = int(row["best_rank_sum"])
            hits5 = int(row["best_number_hits_top5"])
            hits10 = int(row["best_number_hits_top10"])
            hits20 = int(row["best_number_hits_top20"])
            if rank_sum != sum(ranks) or hits5 != sum(value <= 5 for value in ranks) or hits10 != sum(value <= 10 for value in ranks) or hits20 != sum(value <= 20 for value in ranks):
                raise SystemExit("Q86_BLOCKED: local-best rank metrics do not reconcile")
            single_ledger = row.get("single_feature_rank_ledger", "")
            if shard_index == 0:
                try:
                    single_items = json.loads(single_ledger)
                except Exception as exc:
                    raise SystemExit("Q86_BLOCKED: shard 0 single-feature ledger invalid: " + str(exc))
                if len(single_items) != FEATURE_COUNT:
                    raise SystemExit("Q86_BLOCKED: single-feature ledger width mismatch")
                for column, item in enumerate(single_items):
                    if item.get("feature") != FEATURE_NAMES[column]:
                        raise SystemExit("Q86_BLOCKED: single-feature ledger order mismatch")
                    single_ranks = validate_rank_vector(json.dumps(item.get("ranks", [])))
                    if item.get("rank_sum") != sum(single_ranks):
                        raise SystemExit("Q86_BLOCKED: single-feature rank sum mismatch")
                    for key, threshold in (("hits_top5", 5), ("hits_top10", 10), ("hits_top20", 20)):
                        if item.get(key) != sum(value <= threshold for value in single_ranks):
                            raise SystemExit("Q86_BLOCKED: single-feature hit count mismatch")
                if target_date in single_ledger_by_date and single_ledger_by_date[target_date] != single_ledger:
                    raise SystemExit("Q86_BLOCKED: duplicate shard-0 single-feature ledger differs")
                single_ledger_by_date[target_date] = single_ledger
            elif single_ledger:
                raise SystemExit("Q86_BLOCKED: nonzero shard unexpectedly duplicated single-feature ledger")
            key = (rank_sum, hits20, -hits5, formula_index)
            candidate = {
                "formula_index": formula_index,
                "formula_id": row["best_formula_id"],
                "features": row["best_formula_features"],
                "ranks": ranks,
                "rank_sum": rank_sum,
                "hits5": hits5,
                "hits10": hits10,
                "hits20": hits20,
                "key": key,
            }
            current = best_by_date.get(target_date)
            if current is None or key < current["key"]:
                best_by_date[target_date] = {
                    **candidate,
                    "cutoff_date": row["cutoff_date"],
                    "prior_draws": target_index,
                    "actual_quintet": expected_quintet,
                }

    if list(best_by_date.keys()) != expected_target_dates:
        raise SystemExit("Q86_BLOCKED: merged target ledger coverage/order mismatch")
    target_rows = []
    for target_date in expected_target_dates:
        best = best_by_date[target_date]
        target_rows.append({
            "target_date": target_date,
            "cutoff_date": best["cutoff_date"],
            "prior_draws": best["prior_draws"],
            "actual_quintet": best["actual_quintet"],
            "status": "SCORED",
            "formula_count_tested": formula_count,
            "best_formula_index": best["formula_index"],
            "best_formula_id": best["formula_id"],
            "best_formula_features": best["features"],
            "best_actual_number_ranks": json.dumps(best["ranks"], separators=(",", ":")),
            "best_number_hits_top5": best["hits5"],
            "best_number_hits_top10": best["hits10"],
            "best_number_hits_top20": best["hits20"],
            "best_rank_sum": best["rank_sum"],
            "single_feature_rank_ledger": single_ledger_by_date.get(target_date, ""),
        })

    args.out_dir.mkdir(parents=True, exist_ok=True)
    final_fields = [
        "formula_index", "split", "formula_id", "feature_count", "features", "targets",
        "mean_number_hits_top5", "mean_number_hits_top10", "mean_number_hits_top20",
        "all5_top5_rate", "all5_top10_rate", "all5_top20_rate",
        "mean_rank_of_actual_numbers", "p_top5_normal_approx", "p_top10_normal_approx",
        "p_top20_normal_approx", "holm_p_top5", "holm_p_top10", "holm_p_top20",
        "holm_p_max_endpoint_family",
    ]
    best_rank_candidates = []
    best_top5_candidates = []
    metric_row_count = 0
    for shard_index, (metrics_path, _, start, end) in enumerate(shard_paths):
        _, rows = read_csv(metrics_path)
        final_path = args.out_dir / f"per_number_condition_6plus_formula_metrics_part_{shard_index:02d}.csv"
        with final_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=final_fields)
            writer.writeheader()
            for row in rows:
                formula_index = int(row["formula_index"])
                split_index = SPLITS.index(row["split"])
                targets = int(row["targets"])
                denominator = 5 * targets
                row_index = split_index * formula_count + formula_index
                adj = adjusted[row_index]
                final = {
                    "formula_index": formula_index,
                    "split": row["split"],
                    "formula_id": row["formula_id"],
                    "feature_count": FORMULA_SIZE,
                    "features": row["features"],
                    "targets": targets,
                    "mean_number_hits_top5": int(row["number_hits_top5"]) / denominator,
                    "mean_number_hits_top10": int(row["number_hits_top10"]) / denominator,
                    "mean_number_hits_top20": int(row["number_hits_top20"]) / denominator,
                    "all5_top5_rate": int(row["all5_top5"]) / targets,
                    "all5_top10_rate": int(row["all5_top10"]) / targets,
                    "all5_top20_rate": int(row["all5_top20"]) / targets,
                    "mean_rank_of_actual_numbers": int(row["rank_sum"]) / denominator,
                    "p_top5_normal_approx": row["p_top5_normal_approx"],
                    "p_top10_normal_approx": row["p_top10_normal_approx"],
                    "p_top20_normal_approx": row["p_top20_normal_approx"],
                    "holm_p_top5": float(adj[0]),
                    "holm_p_top10": float(adj[1]),
                    "holm_p_top20": float(adj[2]),
                    "holm_p_max_endpoint_family": float(np.max(adj)),
                }
                writer.writerow(final)
                metric_row_count += 1
                if row["split"] == "blind_oos":
                    compact = {
                        "formula_id": final["formula_id"],
                        "features": final["features"],
                        "mean_number_hits_top5": final["mean_number_hits_top5"],
                        "mean_number_hits_top10": final["mean_number_hits_top10"],
                        "mean_number_hits_top20": final["mean_number_hits_top20"],
                        "mean_rank_of_actual_numbers": final["mean_rank_of_actual_numbers"],
                        "holm_p_max_endpoint_family": final["holm_p_max_endpoint_family"],
                    }
                    best_rank_candidates.append(compact)
                    best_top5_candidates.append(compact)
        best_rank_candidates = sorted(
            best_rank_candidates,
            key=lambda item: (item["mean_rank_of_actual_numbers"], -item["mean_number_hits_top5"]),
        )[:10]
        best_top5_candidates = sorted(
            best_top5_candidates,
            key=lambda item: (-item["mean_number_hits_top5"], item["mean_rank_of_actual_numbers"]),
        )[:10]

    if metric_row_count != formula_count * len(SPLITS):
        raise SystemExit("Q86_BLOCKED: final metric row count mismatch")
    ledger_path = args.out_dir / "per_number_condition_6plus_target_ledger.csv"
    ledger_fields = list(target_rows[0].keys())
    write_csv(ledger_path, target_rows, ledger_fields)
    metrics_manifest = []
    for shard_index in range(args.shard_count):
        path = args.out_dir / f"per_number_condition_6plus_formula_metrics_part_{shard_index:02d}.csv"
        expected_rows = (shard_meta[shard_index]["formula_count"]) * len(SPLITS)
        with path.open(newline="", encoding="utf-8") as handle:
            actual_rows = sum(1 for _ in csv.DictReader(handle))
        if actual_rows != expected_rows:
            raise SystemExit("Q86_BLOCKED: final metrics part row count mismatch: " + path.name)
        metrics_manifest.append({
            "path": str(path.relative_to(ROOT)),
            "rows": actual_rows,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "formula_start_inclusive": shard_meta[shard_index]["formula_start_inclusive"],
            "formula_end_exclusive": shard_meta[shard_index]["formula_end_exclusive"],
        })

    blind_count = split_counts["blind_oos"]
    best_target_ranks = [json.loads(row["best_actual_number_ranks"]) for row in target_rows]
    best_target_summary = {
        "targets": len(target_rows),
        "mean_number_hits_top5": sum(sum(value <= 5 for value in ranks) for ranks in best_target_ranks) / (5 * len(best_target_ranks)),
        "mean_number_hits_top10": sum(sum(value <= 10 for value in ranks) for ranks in best_target_ranks) / (5 * len(best_target_ranks)),
        "mean_number_hits_top20": sum(sum(value <= 20 for value in ranks) for ranks in best_target_ranks) / (5 * len(best_target_ranks)),
        "mean_rank_of_actual_numbers": sum(sum(ranks) for ranks in best_target_ranks) / (5 * len(best_target_ranks)),
        "warning": "retrospective per-target optimum across 296,010 formulas; descriptive only and not an ex-ante forecast",
    }
    report = {
        "schema_version": "1.0",
        "task_id": "Q86",
        "status": "VALIDATED_PENDING_HUMAN_REVIEW",
        "review_status": "PENDING_HUMAN_REVIEW_INTEGRATION",
        "source_archive": "data/storico_daily.csv",
        "source_archive_sha256": archive_sha,
        "target_count": target_count,
        "first_date": dates[0],
        "last_date": dates[-1],
        "latest_quintet": list(draws[-1]),
        "minimum_prior_history": MIN_HISTORY,
        "scored_targets": scored_targets,
        "feature_count": FEATURE_COUNT,
        "features": FEATURE_NAMES,
        "formula_count": formula_count,
        "formula_count_check": math.comb(FEATURE_COUNT, FORMULA_SIZE),
        "formula_grammar": "all unique unordered 6-feature equal-weight combinations from the 27 registered prior-only features",
        "scoring_rule": "for each target, z-score each feature over numbers 1..40 using only prior draws, then average each 6-feature subset",
        "shard_count": args.shard_count,
        "shard_manifest": [{
            "shard_index": item["shard_index"],
            "formula_start_inclusive": item["formula_start_inclusive"],
            "formula_end_exclusive": item["formula_end_exclusive"],
            "formula_count": item["formula_count"],
            "formula_id_first": item["formula_id_first"],
            "formula_id_last": item["formula_id_last"],
        } for item in shard_meta],
        "metrics_rows": metric_row_count,
        "target_ledger_rows": len(target_rows),
        "split_counts": split_counts,
        "uniform_number_rank_baseline": {
            "mean_number_hits_top5": 0.125,
            "mean_number_hits_top10": 0.25,
            "mean_number_hits_top20": 0.5,
            "mean_rank_of_actual_numbers": 20.5,
        },
        "multiple_testing": {
            "method": "Holm-Bonferroni",
            "test_count": int(p_values.size),
            "p_value_method": "continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test",
        },
        "holm_adjusted_formula_split_rows_below_0_05": significant_rows,
        "minimum_holm_p_max_endpoint_family": minimum_holm,
        "best_blind_oos_by_mean_rank": best_rank_candidates,
        "best_blind_oos_by_mean_top5_hits": best_top5_candidates,
        "retrospective_best_per_target_summary": best_target_summary,
        "immutable_target_2026_10_25_freeze_overwritten": False,
        "human_review_required": True,
        "automatic_promotion": False,
        "outputs": {
            "metrics_parts": metrics_manifest,
            "target_ledger": {
                "path": str(ledger_path.relative_to(ROOT)),
                "rows": len(target_rows),
                "bytes": ledger_path.stat().st_size,
                "sha256": sha256(ledger_path),
            },
            "report": "reports/sequence_agent/per_number_condition_6plus_grammar.json",
            "checkpoint": "reports/sequence_agent/per_number_condition_6plus_checkpoint.json",
        },
        "guardrails": [
            "features for target i use only draws with index strictly less than i",
            "all 40 numbers are ranked before the target quintet is evaluated",
            "the formula universe is exhaustive only for the declared 6-feature equal-weight grammar",
            "best-per-target formula is retrospective/descriptive and never a prospective forecast",
            "immutable historical and prospective freezes are never overwritten or reconstructed",
            "higher feature counts and other formula families remain open research; this is not the infinite formula universe",
            "no formula is promoted automatically; human review/integration remains required",
        ],
    }
    report_path = args.out_dir / "per_number_condition_6plus_grammar.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0",
        "project": "VinciCasa SONAR",
        "task_id": "Q86",
        "status": "VALIDATED_PENDING_HUMAN_REVIEW",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "archive_snapshot": {
            "source_archive": "data/storico_daily.csv",
            "source_sha256": archive_sha,
            "draw_count": target_count,
            "first_date": dates[0],
            "last_date": dates[-1],
            "latest_quintet": list(draws[-1]),
            "immutable_target_2026_10_25_freeze_overwritten": False,
        },
        "formula_universe": {
            "feature_count": FEATURE_COUNT,
            "formula_size": FORMULA_SIZE,
            "formula_count": formula_count,
            "shard_count": args.shard_count,
            "metrics_rows": metric_row_count,
            "target_ledger_rows": len(target_rows),
            "multiple_testing_test_count": int(p_values.size),
        },
        "validation": {
            "shard_partition_complete": True,
            "formula_split_coverage_complete": True,
            "chronological_cutoffs_reconciled": True,
            "actual_quintets_reconciled": True,
            "holm_adjustment_global": True,
            "persisted_bytes_verified": False,
            "exact_head_ci_status": "PENDING",
            "human_review_required": True,
            "automatic_promotion": False,
        },
        "outputs": {
            "report_sha256": sha256(report_path),
            "target_ledger_sha256": sha256(ledger_path),
            "metrics_parts": [{"path": item["path"], "sha256": item["sha256"], "bytes": item["bytes"]} for item in metrics_manifest],
        },
        "next_action": "Persist all Q86 outputs via Git Data API, reread and byte-compare every artifact, then pass exact-head CI and human review.",
    }
    checkpoint_path = args.out_dir / "per_number_condition_6plus_checkpoint.json"
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SONAR_Q86_AGGREGATE_SUMMARY " + json.dumps({
        "task_id": "Q86",
        "status": report["status"],
        "review_status": report["review_status"],
        "archive_cutoff": report["last_date"],
        "target_count": target_count,
        "scored_targets": scored_targets,
        "formula_count": formula_count,
        "metrics_rows": metric_row_count,
        "target_ledger_rows": len(target_rows),
        "split_counts": split_counts,
        "holm_test_count": int(p_values.size),
        "holm_adjusted_rows_below_0_05": significant_rows,
        "minimum_holm_p_max_endpoint_family": minimum_holm,
        "metrics_parts": len(metrics_manifest),
        "target_ledger_sha256": sha256(ledger_path),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
