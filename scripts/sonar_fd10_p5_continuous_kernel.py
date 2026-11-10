#!/usr/bin/env python3
"""FD-10: strict-prior continuous-kernel model for the P5 order statistic.

For target t, the model conditions the next maximum on P5[t-1]. Historical
transitions (P5[j-1], P5[j]) are accumulated only after target j is scored.
The target's own P5 is never used in its own predictive distribution.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

BANDWIDTHS = (1.5, 3.0, 6.0, 12.0)
ALPHA = 200.0
WARMUP = 300
SPLIT_DISCOVERY_END = 1700
SPLIT_VALIDATION_END = 2550
BLOCK_LENGTH = 7
PRIMARY_SEED = 10102026
BOOTSTRAP_SEED = 10102027
LEDGER_FIELDS = [
    "target_index", "target_date", "history_cutoff", "previous_p5", "actual_p5", "split",
    "baseline_top5", "baseline_top5_hit", "baseline_top10_hit", "baseline_top20_hit",
    "baseline_rank", "baseline_brier", "baseline_log_loss",
] + [
    field
    for h in BANDWIDTHS
    for field in (
        f"h{h:g}_top5", f"h{h:g}_top5_hit", f"h{h:g}_top10_hit",
        f"h{h:g}_top20_hit", f"h{h:g}_rank", f"h{h:g}_brier", f"h{h:g}_log_loss",
    )
]


def exact_null_pmf() -> list[float]:
    denominator = math.comb(40, 5)
    return [math.comb(n - 1, 4) / denominator for n in range(5, 41)]


def rank_candidates(probabilities: list[float]) -> list[int]:
    if len(probabilities) != 36:
        raise ValueError("P5 probability vector must cover candidates 5..40")
    if any(not math.isfinite(p) or p < 0 for p in probabilities):
        raise ValueError("probabilities must be finite and non-negative")
    return sorted(range(5, 41), key=lambda n: (-probabilities[n - 5], -n))


def kernel_probabilities(
    transition_counts: list[list[int]],
    current_context: int,
    bandwidth: float,
    alpha: float = ALPHA,
) -> list[float]:
    if not 5 <= current_context <= 40:
        raise ValueError("previous P5 must be in 5..40")
    if bandwidth not in BANDWIDTHS:
        raise ValueError("bandwidth is outside the preregistered grid")
    if alpha <= 0:
        raise ValueError("Dirichlet shrinkage must be positive")
    if len(transition_counts) != 36 or any(len(row) != 36 for row in transition_counts):
        raise ValueError("transition table must be 36 x 36")

    null = exact_null_pmf()
    weighted = [0.0] * 36
    total_weight = 0.0
    for context in range(5, 41):
        weight = math.exp(-0.5 * ((context - current_context) / bandwidth) ** 2)
        row = transition_counts[context - 5]
        row_total = sum(row)
        total_weight += weight * row_total
        for outcome_index, count in enumerate(row):
            weighted[outcome_index] += weight * count

    denominator = alpha + total_weight
    result = [
        (alpha * null[i] + weighted[i]) / denominator
        for i in range(36)
    ]
    return result


def multiclass_metrics(actual: int, probabilities: list[float]) -> dict:
    ranking = rank_candidates(probabilities)
    rank = ranking.index(actual) + 1
    brier = math.fsum(
        (probabilities[n - 5] - (1.0 if n == actual else 0.0)) ** 2
        for n in range(5, 41)
    )
    log_loss = -math.log(max(probabilities[actual - 5], 1e-300))
    return {
        "top5": ranking[:5],
        "top5_hit": int(actual in ranking[:5]),
        "top10_hit": int(actual in ranking[:10]),
        "top20_hit": int(actual in ranking[:20]),
        "rank": rank,
        "brier": brier,
        "log_loss": log_loss,
    }


def split_name(target_index: int) -> str:
    if target_index < SPLIT_DISCOVERY_END:
        return "discovery"
    if target_index < SPLIT_VALIDATION_END:
        return "validation"
    return "blind_oos"


def build_walkforward(rows: list[dict], warmup: int = WARMUP) -> list[dict]:
    if len(rows) <= warmup:
        raise ValueError("archive does not contain targets beyond warmup")
    maxima = [int(row["numbers"][4]) for row in rows]
    if any(not 5 <= value <= 40 for value in maxima):
        raise ValueError("P5 values must be in 5..40")

    # counts[c-5][n-5] is the number of already-known transitions c -> n.
    transition_counts = [[0] * 36 for _ in range(36)]
    for j in range(1, warmup):
        transition_counts[maxima[j - 1] - 5][maxima[j] - 5] += 1

    null = exact_null_pmf()
    records = []
    for t in range(warmup, len(rows)):
        context = maxima[t - 1]
        actual = maxima[t]
        baseline = multiclass_metrics(actual, null)
        models = {}
        for bandwidth in BANDWIDTHS:
            probabilities = kernel_probabilities(
                transition_counts, context, bandwidth, ALPHA
            )
            models[bandwidth] = multiclass_metrics(actual, probabilities)

        records.append({
            "target_index": t,
            "target_date": rows[t]["date"],
            "history_cutoff": rows[t - 1]["date"],
            "previous_p5": context,
            "actual_p5": actual,
            "split": split_name(t),
            "baseline": baseline,
            "models": models,
        })

        # Only now, after scoring target t, add its transition for later targets.
        transition_counts[maxima[t - 1] - 5][maxima[t] - 5] += 1

    return records


def summarize(records: list[dict], model_key: str | None) -> dict:
    if not records:
        return {"targets": 0}
    values = [
        row["baseline"] if model_key is None else row["models"][float(model_key)]
        for row in records
    ]
    return {
        "targets": len(values),
        "top5_hits": sum(x["top5_hit"] for x in values),
        "top5_rate": sum(x["top5_hit"] for x in values) / len(values),
        "top10_hits": sum(x["top10_hit"] for x in values),
        "top10_rate": sum(x["top10_hit"] for x in values) / len(values),
        "top20_hits": sum(x["top20_hit"] for x in values),
        "top20_rate": sum(x["top20_hit"] for x in values) / len(values),
        "mean_rank": math.fsum(x["rank"] for x in values) / len(values),
        "mean_brier": math.fsum(x["brier"] for x in values) / len(values),
        "mean_log_loss": math.fsum(x["log_loss"] for x in values) / len(values),
    }


def holm_adjust(p_values: list[float]) -> list[float]:
    if any(not 0 <= p <= 1 for p in p_values):
        raise ValueError("p-values must be in [0,1]")
    m = len(p_values)
    order = sorted(range(m), key=lambda i: (p_values[i], i))
    adjusted = [1.0] * m
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


class XorShift32:
    """Small cross-language deterministic PRNG shared with the V8 replay."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF
        if self.state == 0:
            self.state = 0x9E3779B9

    def next_uint32(self) -> int:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state

    def getrandbits(self, bits: int) -> int:
        return self.next_uint32() >> (32 - bits)

    def randrange(self, stop: int) -> int:
        if stop <= 0:
            raise ValueError("stop must be positive")
        bits = stop.bit_length()
        while True:
            value = self.getrandbits(bits)
            if value < stop:
                return value


def block_signflip_family(
    endpoints: dict[str, list[float]],
    block_length: int = BLOCK_LENGTH,
    replicates: int = 50000,
    seed: int = PRIMARY_SEED,
) -> dict[str, float]:
    if not endpoints:
        return {}
    lengths = {len(values) for values in endpoints.values()}
    if len(lengths) != 1:
        raise ValueError("all paired endpoints must have the same target count")
    n = lengths.pop()
    if n == 0 or block_length < 1:
        raise ValueError("invalid block-signflip sample")
    names = list(endpoints)
    block_sums = {
        name: [
            math.fsum(values[start:start + block_length])
            for start in range(0, n, block_length)
        ]
        for name, values in endpoints.items()
    }
    observed = {name: math.fsum(values) for name, values in endpoints.items()}
    extreme = {name: 0 for name in names}
    rng = XorShift32(seed)

    for _ in range(replicates):
        statistics = {name: 0.0 for name in names}
        for block_index in range(len(next(iter(block_sums.values())))):
            sign = -1.0 if rng.getrandbits(1) else 1.0
            for name in names:
                statistics[name] += sign * block_sums[name][block_index]
        for name in names:
            if statistics[name] >= observed[name] - 1e-15:
                extreme[name] += 1

    return {
        name: (extreme[name] + 1) / (replicates + 1)
        for name in names
    }


def circular_block_bootstrap_mean_ci(
    values: list[float],
    block_length: int = BLOCK_LENGTH,
    replicates: int = 10000,
    seed: int = BOOTSTRAP_SEED,
) -> list[float]:
    n = len(values)
    if n < 2 or block_length < 1:
        raise ValueError("invalid bootstrap sample")
    rng = XorShift32(seed)
    means = []
    blocks_needed = math.ceil(n / block_length)
    for _ in range(replicates):
        total = 0.0
        count = 0
        for _block in range(blocks_needed):
            start = rng.randrange(n)
            take = min(block_length, n - count)
            for offset in range(take):
                total += values[(start + offset) % n]
            count += take
            if count == n:
                break
        means.append(total / n)
    means.sort()
    lo = means[int(0.025 * (replicates - 1))]
    hi = means[int(0.975 * (replicates - 1))]
    return [lo, hi]


def build_report(
    records: list[dict],
    source_blob_sha: str,
    source_first_date: str,
    source_last_date: str,
    permutations: int = 50000,
    bootstrap_replicates: int = 10000,
) -> dict:
    if not records:
        raise ValueError("no walk-forward records")
    split_records = {
        name: [row for row in records if row["split"] == name]
        for name in ("discovery", "validation", "blind_oos")
    }
    if any(not split_records[name] for name in split_records):
        raise ValueError("all three chronological splits must be represented")

    validation = split_records["validation"]
    selected = min(
        BANDWIDTHS,
        key=lambda h: (summarize(validation, str(h))["mean_brier"], -h),
    )
    blind = split_records["blind_oos"]
    baseline_blind = [row["baseline"] for row in blind]

    endpoints = {}
    for h in BANDWIDTHS:
        key = str(h)
        endpoints[f"h{h:g}_brier_improvement"] = [
            row["baseline"]["brier"] - row["models"][h]["brier"]
            for row in blind
        ]
        endpoints[f"h{h:g}_top5_improvement"] = [
            row["models"][h]["top5_hit"] - row["baseline"]["top5_hit"]
            for row in blind
        ]

    raw_p = block_signflip_family(
        endpoints, replicates=permutations, seed=PRIMARY_SEED
    )
    endpoint_names = list(endpoints)
    adjusted_values = holm_adjust([raw_p[name] for name in endpoint_names])
    adjusted_p = dict(zip(endpoint_names, adjusted_values))

    selected_brier_delta = endpoints[f"h{selected:g}_brier_improvement"]
    selected_top5_delta = endpoints[f"h{selected:g}_top5_improvement"]
    brier_ci = circular_block_bootstrap_mean_ci(
        selected_brier_delta, replicates=bootstrap_replicates,
        seed=BOOTSTRAP_SEED
    )
    top5_ci = circular_block_bootstrap_mean_ci(
        selected_top5_delta, replicates=bootstrap_replicates,
        seed=BOOTSTRAP_SEED + 1
    )

    split_results = {}
    for split_name_value, split_rows in split_records.items():
        split_results[split_name_value] = {
            "exact_null": summarize(split_rows, None),
            "bandwidths": {
                str(h): summarize(split_rows, str(h))
                for h in BANDWIDTHS
            },
        }

    selected_name = f"h{selected:g}"
    selected_brier_name = f"h{selected:g}_brier_improvement"
    selected_top5_name = f"h{selected:g}_top5_improvement"
    decision = (
        "HISTORICAL_SIGNAL_NOT_PROMOTABLE"
        if adjusted_p[selected_brier_name] < 0.05 and brier_ci[0] > 0
        else "NO_PREDICTIVE_LIFT_DEMONSTRATED"
    )

    null = exact_null_pmf()
    return {
        "schema_version": "1.0",
        "experiment_id": "SONAR-FD10-P5-CONTINUOUS-MARKOV-KERNEL-2026-11-10",
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY",
        "validation_status": "EXPLORATORY_NOT_PROMOTABLE",
        "source": {
            "path": "data/storico_daily.csv",
            "git_blob_sha": source_blob_sha,
            "first_date": source_first_date,
            "last_date": source_last_date,
            "draw_count": len(records) + WARMUP,
            "walkforward_targets": len(records),
        },
        "method": {
            "target": "P5, the maximum of the five drawn numbers",
            "state": "previous draw's P5 maximum",
            "kernel": "exp(-0.5*((historical_previous_P5-current_previous_P5)/bandwidth)^2)",
            "bandwidths": list(BANDWIDTHS),
            "dirichlet_shrinkage_ess": ALPHA,
            "selection": "minimum validation multiclass Brier; exact ties choose larger bandwidth",
            "ranking_tie_break": "descending probability, then descending candidate number",
            "cutoff": "all historical transitions j<t; target scored before transition t is added",
        },
        "exact_order_statistic_null": {
            "pmf": "C(n-1,4)/C(40,5), n=5..40",
            "top5_probability": math.fsum(null[-5:]),
            "top10_probability": math.fsum(null[-10:]),
            "top20_probability": math.fsum(null[-20:]),
            "expected_rank": math.fsum((i + 1) * p for i, p in enumerate(sorted(null, reverse=True))),
            "top5_candidates": [36, 37, 38, 39, 40],
        },
        "chronological_splits": {
            name: {
                "targets": len(split_records[name]),
                "first_target": split_records[name][0]["target_date"],
                "last_target": split_records[name][-1]["target_date"],
            }
            for name in split_records
        },
        "validation_selected_bandwidth": selected,
        "split_results": split_results,
        "blind_oos_inference": {
            "n": len(blind),
            "primary_endpoint": "paired Brier improvement (exact null minus kernel model)",
            "secondary_endpoint": "paired Top-5 hit indicator improvement",
            "raw_p_values": raw_p,
            "holm_adjusted_p_values": adjusted_p,
            "holm_family_size": len(endpoints),
            "selected_bandwidth": selected,
            "selected_brier_improvement_mean": math.fsum(selected_brier_delta) / len(selected_brier_delta),
            "selected_brier_improvement_block_bootstrap_ci95": brier_ci,
            "selected_brier_holm_p": adjusted_p[selected_brier_name],
            "selected_top5_improvement_mean": math.fsum(selected_top5_delta) / len(selected_top5_delta),
            "selected_top5_improvement_block_bootstrap_ci95": top5_ci,
            "selected_top5_holm_p": adjusted_p[selected_top5_name],
            "decision": decision,
        },
        "statistical_controls": {
            "block_signflip": {
                "block_length": BLOCK_LENGTH,
                "replicates": permutations,
                "seed": PRIMARY_SEED,
                "alternative": "positive paired improvement",
                "tail_block_retained": True,
            },
            "circular_block_bootstrap": {
                "block_length": BLOCK_LENGTH,
                "replicates": bootstrap_replicates,
                "seed_brier": BOOTSTRAP_SEED,
                "seed_top5": BOOTSTRAP_SEED + 1,
                "interval": "percentile 95%",
            },
            "multiple_testing": "Holm across 4 fixed bandwidths x 2 blind-OOS endpoints; no correction claimed for the wider historical SONAR search.",
        },
        "integrity": {
            "strict_prior_target_cutoffs": len(records),
            "target_scored_before_own_transition_update": True,
            "future_outcomes_used_for_predictors": False,
            "all_targets_cutoff_precedes_target": all(
                row["history_cutoff"] < row["target_date"] for row in records
            ),
            "missing_or_reconstructed_forecasts": 0,
        },
        "limitations": [
            "The chronological historical Blind OOS segment has been exposed to earlier laboratory work and is not a virgin holdout.",
            "The block sign-flip test assumes exchangeability of contiguous seven-target block signs under the null; strong nonstationarity can invalidate it.",
            "The model tests only one-step dependence of P5 on the previous P5; it does not establish a physical mechanism or causal relationship.",
            "The Holm family covers this fixed FD-10 bandwidth grid and two endpoints only, not all earlier SONAR experiments.",
            "No prospective freeze or future outcome is used; historical performance cannot validate future lottery predictions.",
        ],
        "decision_policy": {
            "promotion_allowed": False,
            "merge_allowed": False,
            "human_review_required": True,
        },
        "next_action": (
            "Keep FD-10 exploratory. If human review accepts the implementation, freeze the selected bandwidth "
            "as a separate prospective shadow model and evaluate only after at least 200 newly frozen targets; "
            "do not retune on this historical OOS."
        ),
    }


def read_archive(path: str) -> list[dict]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            raise ValueError("unexpected canonical archive header")
        rows = []
        previous_date = ""
        for row_number, row in enumerate(reader, start=2):
            date = row["data"]
            numbers = [int(row[f"n{i}"]) for i in range(1, 6)]
            if not date or (previous_date and date <= previous_date):
                raise ValueError(f"date order/uniqueness failure at row {row_number}")
            if len(set(numbers)) != 5 or any(not 1 <= n <= 40 for n in numbers):
                raise ValueError(f"invalid quintet at row {row_number}")
            if numbers != sorted(numbers):
                raise ValueError(f"quintet is not ascending at row {row_number}")
            rows.append({"date": date, "numbers": numbers})
            previous_date = date
    return rows


def write_outputs(report: dict, records: list[dict], report_path: str, ledger_path: str) -> None:
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(ledger_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with Path(ledger_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in records:
            baseline = row["baseline"]
            output = {
                "target_index": row["target_index"],
                "target_date": row["target_date"],
                "history_cutoff": row["history_cutoff"],
                "previous_p5": row["previous_p5"],
                "actual_p5": row["actual_p5"],
                "split": row["split"],
                "baseline_top5": "-".join(map(str, baseline["top5"])),
                "baseline_top5_hit": baseline["top5_hit"],
                "baseline_top10_hit": baseline["top10_hit"],
                "baseline_top20_hit": baseline["top20_hit"],
                "baseline_rank": baseline["rank"],
                "baseline_brier": f'{baseline["brier"]:.15g}',
                "baseline_log_loss": f'{baseline["log_loss"]:.15g}',
            }
            for h in BANDWIDTHS:
                model = row["models"][h]
                prefix = f"h{h:g}_"
                output.update({
                    prefix + "top5": "-".join(map(str, model["top5"])),
                    prefix + "top5_hit": model["top5_hit"],
                    prefix + "top10_hit": model["top10_hit"],
                    prefix + "top20_hit": model["top20_hit"],
                    prefix + "rank": model["rank"],
                    prefix + "brier": f'{model["brier"]:.15g}',
                    prefix + "log_loss": f'{model["log_loss"]:.15g}',
                })
            writer.writerow(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-csv", required=True)
    parser.add_argument("--source-blob-sha", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--ledger-out", required=True)
    parser.add_argument("--permutations", type=int, default=50000)
    parser.add_argument("--bootstrap-replicates", type=int, default=10000)
    args = parser.parse_args()

    rows = read_archive(args.archive_csv)
    if len(rows) != 3403 or rows[0]["date"] != "2017-07-17" or rows[-1]["date"] != "2026-11-09":
        raise ValueError("canonical archive count/bounds differ from preregistration")
    records = build_walkforward(rows)
    report = build_report(
        records,
        args.source_blob_sha,
        rows[0]["date"],
        rows[-1]["date"],
        permutations=args.permutations,
        bootstrap_replicates=args.bootstrap_replicates,
    )
    write_outputs(report, records, args.report_out, args.ledger_out)
    print("FD10_STATUS=" + report["status"])
    print("FD10_TARGETS=" + str(len(records)))
    print("FD10_SELECTED_BANDWIDTH=" + str(report["validation_selected_bandwidth"]))
    print("FD10_DECISION=" + report["blind_oos_inference"]["decision"])


if __name__ == "__main__":
    main()
