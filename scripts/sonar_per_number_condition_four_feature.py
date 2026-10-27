#!/usr/bin/env python3
"""Q81: walk-forward evaluation of every four-feature equal-weight formula.

This is the next finite grammar after Q80: all C(27,4)=17,550 four-feature
combinations. Scoring is batched across formulas to keep memory bounded.
Features are built strictly from draws before the target. The per-target best
formula is retrospective/descriptive, never an ex-ante forecast.
"""
from __future__ import annotations

import csv
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
METRICS = OUT / "per_number_condition_four_feature_metrics.csv"
TARGET_LEDGER = OUT / "per_number_condition_four_feature_target_ledger.csv"
REPORT = OUT / "per_number_condition_four_feature_grammar.json"
BATCH_SIZE = 1024

SPEC = importlib.util.spec_from_file_location(
    "sonar_q80", ROOT / "scripts" / "sonar_per_number_condition_grammar.py"
)
Q80 = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(Q80)

FEATURE_NAMES = Q80.FEATURE_NAMES
MIN_HISTORY = Q80.MIN_HISTORY
FORMULAS = list(itertools.combinations(range(len(FEATURE_NAMES)), 4))
FORMULA_IDS = ["P4_" + "_".join(f"{i:02d}" for i in cols) for cols in FORMULAS]
FORMULA_COLUMNS = np.asarray(FORMULAS, dtype=np.int16)
EXPECTED_FORMULAS = math.comb(len(FEATURE_NAMES), 4)


def rank_formula_batch(standardized: np.ndarray, formula_columns: np.ndarray) -> np.ndarray:
    """Return 40 x batch ranks; ties deterministically favor the lower number."""
    scores = standardized[:, formula_columns].mean(axis=2)
    order = np.argsort(-scores, axis=0, kind="stable")
    return np.argsort(order, axis=0, kind="stable") + 1


def new_accumulator(formula_count: int) -> dict:
    return {
        "targets": 0,
        "hits5": np.zeros(formula_count, dtype=np.int64),
        "hits10": np.zeros(formula_count, dtype=np.int64),
        "hits20": np.zeros(formula_count, dtype=np.int64),
        "all5": np.zeros(formula_count, dtype=np.int64),
        "all10": np.zeros(formula_count, dtype=np.int64),
        "all20": np.zeros(formula_count, dtype=np.int64),
        "rank_sum": np.zeros(formula_count, dtype=np.int64),
    }


def validate_generated(dates, draws, metric_rows, target_rows, summary):
    errors = []
    n = len(draws)
    scored = n - MIN_HISTORY
    if len(FORMULAS) != EXPECTED_FORMULAS or len(set(FORMULAS)) != EXPECTED_FORMULAS:
        errors.append("four-feature formula universe count/uniqueness mismatch")
    if summary.get("formula_count") != EXPECTED_FORMULAS or summary.get("formula_count_check") != EXPECTED_FORMULAS:
        errors.append("four-feature formula count check mismatch")
    if len(metric_rows) != EXPECTED_FORMULAS * 3:
        errors.append("four-feature metrics row count mismatch")
    if len(target_rows) != scored:
        errors.append("four-feature target ledger row count mismatch")
    expected_splits = {"discovery": int(scored * 0.60) + (1 if (int(scored * 0.60) / max(scored, 1)) < 0.60 else 0),
                       "validation": 0, "blind_oos": 0}
    # Use the registered Q80 splitter as the source of truth for boundary rounding.
    split_counts = {name: sum(Q80.split_name(i, scored) == name for i in range(scored))
                    for name in ("discovery", "validation", "blind_oos")}
    if sum(split_counts.values()) != scored:
        errors.append("four-feature split coverage mismatch")
    if summary.get("split_counts") != split_counts:
        errors.append("four-feature summary split counts mismatch")
    for index, row in enumerate(target_rows):
        archive_index = index + MIN_HISTORY
        if row.get("target_date") != dates[archive_index]:
            errors.append("target order mismatch at " + str(row.get("target_date")))
            break
        if row.get("cutoff_date") != dates[archive_index - 1] or int(row.get("prior_draws", -1)) != archive_index:
            errors.append("strict prior cutoff mismatch at " + dates[archive_index])
            break
        if row.get("actual_quintet") != " ".join(map(str, draws[archive_index])):
            errors.append("actual quintet mismatch at " + dates[archive_index])
            break
        if row.get("status") != "SCORED" or int(row.get("formula_count_tested", -1)) != EXPECTED_FORMULAS:
            errors.append("target scoring status/formula count mismatch at " + dates[archive_index])
            break
        ranks = json.loads(row["best_actual_number_ranks"])
        if (len(ranks) != 5 or any(rank < 1 or rank > 40 for rank in ranks)
                or sum(ranks) != int(row["best_rank_sum"])
                or sum(rank <= 5 for rank in ranks) != int(row["best_number_hits_top5"])
                or sum(rank <= 10 for rank in ranks) != int(row["best_number_hits_top10"])
                or sum(rank <= 20 for rank in ranks) != int(row["best_number_hits_top20"])):
            errors.append("best-rank ledger inconsistency at " + dates[archive_index])
            break
    counts = {name: 0 for name in ("discovery", "validation", "blind_oos")}
    ids = {name: set() for name in counts}
    for row in metric_rows:
        split = row["split"]
        if split not in counts or int(row["feature_count"]) != 4:
            errors.append("invalid split or feature count in four-feature metrics")
            break
        counts[split] += 1
        ids[split].add(row["formula_id"])
        if int(row["targets"]) != split_counts[split]:
            errors.append("four-feature metric target count mismatch in " + split)
            break
    for split in counts:
        if counts[split] != EXPECTED_FORMULAS or len(ids[split]) != EXPECTED_FORMULAS:
            errors.append("four-feature formula coverage mismatch in " + split)
    if summary.get("metrics_rows") != len(metric_rows) or summary.get("target_ledger_rows") != len(target_rows):
        errors.append("four-feature summary/output dimensions mismatch")
    if errors:
        raise SystemExit("Q81_BLOCKED: " + "; ".join(errors))


def main():
    dates, draws = Q80.load_archive()
    n = len(draws)
    if n <= MIN_HISTORY:
        raise SystemExit("Q81_BLOCKED: archive has no scored targets")
    if EXPECTED_FORMULAS != 17550 or len(FORMULAS) != EXPECTED_FORMULAS:
        raise SystemExit("Q81_BLOCKED: formula universe is not C(27,4)=17550")

    prefix = np.zeros((n + 1, 40), dtype=np.int32)
    pos_prefix = np.zeros((n + 1, 5, 40), dtype=np.int32)
    for i, draw in enumerate(draws):
        prefix[i + 1] = prefix[i]
        pos_prefix[i + 1] = pos_prefix[i]
        for pos, value in enumerate(draw):
            v = value - 1
            prefix[i + 1, v] += 1
            pos_prefix[i + 1, pos, v] += 1

    prior_pairs = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    gap_sum = np.zeros(40, dtype=np.float64)
    gap_sq_sum = np.zeros(40, dtype=np.float64)
    gap_n = np.zeros(40, dtype=np.float64)
    splits = ("discovery", "validation", "blind_oos")
    accumulators = {split: new_accumulator(EXPECTED_FORMULAS) for split in splits}
    target_rows = []
    scored = n - MIN_HISTORY

    for i, (target_date, actual) in enumerate(zip(dates, draws)):
        if i >= MIN_HISTORY:
            raw = Q80.feature_matrix(i, draws, prefix, pos_prefix, prior_pairs,
                                     occurrence_lists, gap_sum, gap_sq_sum, gap_n)
            standardized = Q80.zscore_columns(raw)
            actual_idx = np.asarray(actual, dtype=np.int16) - 1
            split = Q80.split_name(i - MIN_HISTORY, scored)
            acc = accumulators[split]
            acc["targets"] += 1
            best_key = None
            best_formula_index = None
            best_ranks = None

            for start in range(0, EXPECTED_FORMULAS, BATCH_SIZE):
                stop = min(start + BATCH_SIZE, EXPECTED_FORMULAS)
                ranks = rank_formula_batch(standardized, FORMULA_COLUMNS[start:stop])
                actual_ranks = ranks[actual_idx, :]
                h5 = np.count_nonzero(actual_ranks <= 5, axis=0)
                h10 = np.count_nonzero(actual_ranks <= 10, axis=0)
                h20 = np.count_nonzero(actual_ranks <= 20, axis=0)
                rank_sums = np.sum(actual_ranks, axis=0)
                acc["hits5"][start:stop] += h5
                acc["hits10"][start:stop] += h10
                acc["hits20"][start:stop] += h20
                acc["all5"][start:stop] += (h5 == 5)
                acc["all10"][start:stop] += (h10 == 5)
                acc["all20"][start:stop] += (h20 == 5)
                acc["rank_sum"][start:stop] += rank_sums

                # Same descriptive tie-break as Q80; earliest formula wins exact ties.
                local_order = np.lexsort((-h5, h20, rank_sums))
                local = int(local_order[0])
                key = (int(rank_sums[local]), int(h20[local]), -int(h5[local]))
                if best_key is None or key < best_key:
                    best_key = key
                    best_formula_index = start + local
                    best_ranks = actual_ranks[:, local].astype(int).tolist()

            target_rows.append({
                "target_date": target_date,
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "actual_quintet": " ".join(map(str, actual)),
                "status": "SCORED",
                "formula_count_tested": EXPECTED_FORMULAS,
                "best_formula_id": FORMULA_IDS[best_formula_index],
                "best_formula_features": "+".join(FEATURE_NAMES[c] for c in FORMULAS[best_formula_index]),
                "best_actual_number_ranks": json.dumps(best_ranks, separators=(",", ":")),
                "best_number_hits_top5": sum(rank <= 5 for rank in best_ranks),
                "best_number_hits_top10": sum(rank <= 10 for rank in best_ranks),
                "best_number_hits_top20": sum(rank <= 20 for rank in best_ranks),
                "best_rank_sum": sum(best_ranks),
            })

        # Update history only after scoring this target.
        for value in draws[i]:
            v = value - 1
            occurrence_lists[v].append(i)
            if len(occurrence_lists[v]) >= 2:
                gap = i - occurrence_lists[v][-2]
                gap_sum[v] += gap
                gap_sq_sum[v] += gap * gap
                gap_n[v] += 1
        if i < n - 1:
            for a, b in itertools.combinations(draws[i], 2):
                prior_pairs[a - 1, b - 1] += 1
                prior_pairs[b - 1, a - 1] += 1

    metric_rows = []
    p_records = []
    for split in splits:
        acc = accumulators[split]
        t = acc["targets"]
        for fi, cols in enumerate(FORMULAS):
            row = {
                "split": split,
                "formula_id": FORMULA_IDS[fi],
                "feature_count": 4,
                "features": "+".join(FEATURE_NAMES[c] for c in cols),
                "targets": t,
                "mean_number_hits_top5": int(acc["hits5"][fi]) / (5 * t),
                "mean_number_hits_top10": int(acc["hits10"][fi]) / (5 * t),
                "mean_number_hits_top20": int(acc["hits20"][fi]) / (5 * t),
                "all5_top5_rate": int(acc["all5"][fi]) / t,
                "all5_top10_rate": int(acc["all10"][fi]) / t,
                "all5_top20_rate": int(acc["all20"][fi]) / t,
                "mean_rank_of_actual_numbers": int(acc["rank_sum"][fi]) / (5 * t),
            }
            for endpoint, k, successes in (
                ("top5", 5, int(acc["hits5"][fi])),
                ("top10", 10, int(acc["hits10"][fi])),
                ("top20", 20, int(acc["hits20"][fi])),
            ):
                row[f"p_{endpoint}_normal_approx"] = Q80.binomial_upper_normal_p(successes, 5 * t, k / 40)
                p_records.append((len(metric_rows), row[f"p_{endpoint}_normal_approx"]))
            metric_rows.append(row)

    adjusted = Q80.holm_adjust([p for _, p in p_records])
    for (row_index, _), adj in zip(p_records, adjusted):
        metric_rows[row_index]["holm_p_max_endpoint_family"] = max(
            metric_rows[row_index].get("holm_p_max_endpoint_family", 0.0), adj
        )

    split_counts = {split: accumulators[split]["targets"] for split in splits}
    blind_rows = [row for row in metric_rows if row["split"] == "blind_oos"]
    best_blind = sorted(
        blind_rows,
        key=lambda row: (row["mean_number_hits_top5"], row["mean_number_hits_top10"],
                         -row["mean_rank_of_actual_numbers"]),
        reverse=True,
    )[:10]
    summary = {
        "schema_version": "1.0",
        "task_id": "Q81",
        "status": "VALIDATED_FINITE_GRAMMAR_COMPLETE",
        "review_status": "PENDING_HUMAN_REVIEW_INTEGRATION",
        "source_archive": "data/storico_daily.csv",
        "target_count": n,
        "first_date": dates[0],
        "last_date": dates[-1],
        "minimum_prior_history": MIN_HISTORY,
        "scored_targets": len(target_rows),
        "feature_count": len(FEATURE_NAMES),
        "features": FEATURE_NAMES,
        "formula_count": len(FORMULAS),
        "formula_count_check": EXPECTED_FORMULAS,
        "formula_grammar": "all unordered four-feature equal-weight combinations from the 27 registered prior-only features",
        "batch_size": BATCH_SIZE,
        "metrics_rows": len(metric_rows),
        "target_ledger_rows": len(target_rows),
        "split_counts": split_counts,
        "uniform_number_rank_baseline": {
            "mean_number_hits_top5": 0.125,
            "mean_number_hits_top10": 0.25,
            "mean_number_hits_top20": 0.5,
            "mean_rank_of_actual_numbers": 20.5,
        },
        "blind_oos_top10_descriptive_only": best_blind,
        "multiple_testing": {
            "method": "Holm-Bonferroni",
            "test_count": len(p_records),
            "p_value_method": "continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test",
        },
        "guardrails": [
            "features at target i use only draws with index < i",
            "all formula scores rank 40 numbers with deterministic tie handling",
            "formula universe is exhaustive only within the declared four-feature grammar",
            "best-per-target and blind-OOS leaderboard selections are retrospective/descriptive, not prospective forecasts",
            "Q80 single/pair/triple results remain separate and unchanged",
            "five-feature, conditional-threshold, nonlinear and interaction grammars remain subsequent research stages",
            "immutable forecast freezes are never read for writing or overwritten",
        ],
        "outputs": {
            "metrics": str(METRICS.relative_to(ROOT)),
            "target_ledger": str(TARGET_LEDGER.relative_to(ROOT)),
            "report": str(REPORT.relative_to(ROOT)),
        },
    }
    validate_generated(dates, draws, metric_rows, target_rows, summary)
    OUT.mkdir(parents=True, exist_ok=True)
    with METRICS.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(target_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_rows)
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Re-read persisted outputs before declaring the computational stage valid.
    with METRICS.open(newline="", encoding="utf-8") as handle:
        persisted_metrics = list(csv.DictReader(handle))
    with TARGET_LEDGER.open(newline="", encoding="utf-8") as handle:
        persisted_targets = list(csv.DictReader(handle))
    persisted_report = json.loads(REPORT.read_text(encoding="utf-8"))
    if (len(persisted_metrics) != EXPECTED_FORMULAS * 3
            or len(persisted_targets) != n - MIN_HISTORY
            or persisted_report.get("formula_count_check") != EXPECTED_FORMULAS):
        raise SystemExit("Q81_BLOCKED: persisted output read-back failed")

    print("SONAR_Q81_SUMMARY_BEGIN")
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("features", "blind_oos_top10_descriptive_only", "guardrails")},
                     ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q81_SUMMARY_END")
    print("SONAR_Q81_REPORT_BEGIN")
    print(REPORT.read_text(encoding="utf-8"), end="")
    print("SONAR_Q81_REPORT_END")
    print("SONAR_Q81_BLIND_OOS_TOP10_BEGIN")
    print(json.dumps(best_blind, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q81_BLIND_OOS_TOP10_END")


if __name__ == "__main__":
    main()
