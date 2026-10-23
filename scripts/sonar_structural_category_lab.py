#!/usr/bin/env python3
"""Leakage-safe frequency-vs-age structural category tests for VinciCasa SONAR.

Predictions are prequential: every target is scored from the preceding archive
only. The OOS null simulates independent uniform 5-of-40 sequences and refits
the same online feature state for each replicate, preserving five hits per draw.
"""
from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent" / "structural_category_oos.json"
BASELINE = 5 / 40
WARMUP = 500
FREQUENCY_WINDOW = 100
FREQUENCY_PRIOR_STRENGTH = 30.0
AGE_PRIOR_STRENGTH = 100.0
PERMUTATIONS = 499
SEED = 20261023
MODEL_NAMES = ("frequency_100", "age_bucket_hazard", "frequency_plus_age_equal_weight")
SPLIT_NAMES = ("discovery", "validation", "oos")
EPSILON = 1e-9


def load_archive():
    if not DATA.is_file():
        raise SystemExit("STRUCTURAL CATEGORY BLOCKED: canonical archive missing")
    dates, draws = [], []
    with DATA.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            raise SystemExit(f"STRUCTURAL CATEGORY BLOCKED: unexpected CSV header {reader.fieldnames}")
        for line, row in enumerate(reader, 2):
            try:
                draw_date = row["data"]
                nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            except Exception as exc:
                raise SystemExit(f"STRUCTURAL CATEGORY BLOCKED: malformed line {line}: {exc}")
            if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n < 1 or n > 40 for n in nums):
                raise SystemExit(f"STRUCTURAL CATEGORY BLOCKED: invalid quintet at {draw_date}")
            if dates and draw_date <= dates[-1]:
                raise SystemExit(f"STRUCTURAL CATEGORY BLOCKED: dates not strictly increasing at {draw_date}")
            dates.append(draw_date)
            draws.append(nums)
    if len(draws) <= WARMUP + 20:
        raise SystemExit("STRUCTURAL CATEGORY BLOCKED: insufficient history for chronological OOS")
    return dates, draws


def age_bucket(age):
    if age <= 4:
        return 0
    if age <= 9:
        return 1
    if age <= 19:
        return 2
    return 3


def normalise_to_five(raw):
    total = sum(raw)
    if total <= 0 or not math.isfinite(total):
        raise SystemExit("STRUCTURAL CATEGORY BLOCKED: invalid probability mass")
    probs = [min(1.0 - EPSILON, max(EPSILON, 5.0 * value / total)) for value in raw]
    # Normalization must retain the expected five selected numbers, up to rounding.
    if abs(sum(probs) - 5.0) > 1e-5:
        raise SystemExit("STRUCTURAL CATEGORY BLOCKED: marginal probabilities do not sum to five")
    return probs


def prequential_forecasts(dates, draws, collect_start_index=WARMUP):
    """Return forecasts made before each target; no target labels enter its own features."""
    last_seen = [None] * 40
    frequency_counts = [0] * 40
    age_trials = [0] * 4
    age_hits = [0] * 4
    forecasts = []

    for t, draw in enumerate(draws):
        actual = set(draw)
        ages = []
        buckets = []
        if t > 0:
            for idx in range(40):
                last = last_seen[idx]
                age = 10**9 if last is None else (t - 1 - last)
                ages.append(age)
                buckets.append(age_bucket(age))
        else:
            ages = [10**9] * 40
            buckets = [3] * 40

        if t >= collect_start_index:
            history_len = min(FREQUENCY_WINDOW, t)
            denom = history_len + FREQUENCY_PRIOR_STRENGTH
            frequency_raw = [
                (frequency_counts[idx] + FREQUENCY_PRIOR_STRENGTH * BASELINE) / denom
                for idx in range(40)
            ]
            frequency_probs = normalise_to_five(frequency_raw)

            age_raw = [
                (age_hits[buckets[idx]] + AGE_PRIOR_STRENGTH * BASELINE)
                / (age_trials[buckets[idx]] + AGE_PRIOR_STRENGTH)
                for idx in range(40)
            ]
            age_probs = normalise_to_five(age_raw)
            combined_probs = normalise_to_five([
                (frequency_probs[idx] + age_probs[idx]) / 2.0 for idx in range(40)
            ])
            forecasts.append({
                "index": t,
                "date": dates[t],
                "actual": tuple(draw),
                "probs": {
                    "frequency_100": frequency_probs,
                    "age_bucket_hazard": age_probs,
                    "frequency_plus_age_equal_weight": combined_probs,
                },
            })

        # Update age-hazard training only after the current target has been scored.
        if t > 0:
            for idx, bucket in enumerate(buckets):
                age_trials[bucket] += 1
                if idx + 1 in actual:
                    age_hits[bucket] += 1

        # Maintain the trailing-100 frequency window for the next target.
        if t >= FREQUENCY_WINDOW:
            for number in draws[t - FREQUENCY_WINDOW]:
                frequency_counts[number - 1] -= 1
        for number in draw:
            frequency_counts[number - 1] += 1
            last_seen[number - 1] = t

    return forecasts


def score_model(records, model_name):
    n = len(records)
    if not n:
        raise SystemExit(f"STRUCTURAL CATEGORY BLOCKED: empty split for {model_name}")
    brier_sum = 0.0
    logloss_sum = 0.0
    top1_hits = 0
    top2_any = 0
    top2_hits = 0
    for row in records:
        probs = row["probs"][model_name]
        actual = set(row["actual"])
        ranked = sorted(range(40), key=lambda idx: (-probs[idx], idx + 1))
        top1_hits += int(ranked[0] + 1 in actual)
        selected2 = {ranked[0] + 1, ranked[1] + 1}
        hits2 = len(selected2 & actual)
        top2_any += int(hits2 > 0)
        top2_hits += hits2
        for idx, prob in enumerate(probs):
            y = int(idx + 1 in actual)
            p = min(1.0 - EPSILON, max(EPSILON, prob))
            brier_sum += (p - y) ** 2
            logloss_sum -= math.log(p) if y else math.log1p(-p)
    opportunities = 40 * n
    baseline_brier = (5 * (1 - BASELINE) ** 2 + 35 * BASELINE**2) / 40
    baseline_logloss = -(5 * math.log(BASELINE) + 35 * math.log1p(-BASELINE)) / 40
    return {
        "targets": n,
        "brier_score": brier_sum / opportunities,
        "uniform_brier_baseline": baseline_brier,
        "brier_improvement_vs_uniform": baseline_brier - brier_sum / opportunities,
        "log_loss": logloss_sum / opportunities,
        "uniform_log_loss_baseline": baseline_logloss,
        "log_loss_improvement_vs_uniform": baseline_logloss - logloss_sum / opportunities,
        "top1_hit_rate": top1_hits / n,
        "top1_random_baseline": BASELINE,
        "top2_any_hit_rate": top2_any / n,
        "top2_any_hit_random_baseline": 1 - math.comb(38, 5) / math.comb(40, 5),
        "top2_mean_hits": top2_hits / n,
        "top2_mean_hits_random_baseline": 2 * BASELINE,
    }


def brier_improvement(records, model_name):
    n = len(records)
    brier_sum = 0.0
    for row in records:
        probs = row["probs"][model_name]
        actual = set(row["actual"])
        positive_sum = sum(probs[number - 1] for number in actual)
        brier_sum += (sum(p * p for p in probs) + 5 - 2 * positive_sum) / 40
    baseline_brier = (5 * (1 - BASELINE) ** 2 + 35 * BASELINE**2) / 40
    return baseline_brier - brier_sum / n


def holm_adjust(p_values):
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted = {}
    running = 0.0
    m = len(ordered)
    for i, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p_value))
        adjusted[key] = running
    return adjusted


def quantile(sorted_values, q):
    if not sorted_values:
        return None
    return sorted_values[round((len(sorted_values) - 1) * q)]


def main():
    dates, draws = load_archive()
    forecasts = prequential_forecasts(dates, draws, WARMUP)
    n = len(forecasts)
    cut1, cut2 = int(n * 0.60), int(n * 0.80)
    split_bounds = {
        "discovery": (0, cut1),
        "validation": (cut1, cut2),
        "oos": (cut2, n),
    }
    split_records = {
        name: forecasts[lo:hi] for name, (lo, hi) in split_bounds.items()
    }
    metrics = {
        model: {
            split: score_model(split_records[split], model)
            for split in SPLIT_NAMES
        }
        for model in MODEL_NAMES
    }

    oos_start_index = forecasts[cut2]["index"]
    rng = random.Random(SEED)
    null_improvements = {model: [] for model in MODEL_NAMES}
    for _ in range(PERMUTATIONS):
        simulated = [tuple(sorted(rng.sample(range(1, 41), 5))) for _ in draws]
        null_rows = prequential_forecasts(dates, simulated, oos_start_index)
        if len(null_rows) != len(split_records["oos"]):
            raise SystemExit("STRUCTURAL CATEGORY BLOCKED: randomized OOS size mismatch")
        for model in MODEL_NAMES:
            null_improvements[model].append(brier_improvement(null_rows, model))

    observed = {
        model: metrics[model]["oos"]["brier_improvement_vs_uniform"]
        for model in MODEL_NAMES
    }
    raw_p = {
        model: (1 + sum(value >= observed[model] - 1e-15 for value in null_improvements[model]))
        / (PERMUTATIONS + 1)
        for model in MODEL_NAMES
    }
    adjusted_p = holm_adjust(raw_p)
    permutation_summary = {}
    for model in MODEL_NAMES:
        null_values = sorted(null_improvements[model])
        permutation_summary[model] = {
            "observed_oos_brier_improvement": observed[model],
            "null_mean_brier_improvement": sum(null_values) / len(null_values),
            "null_2_5_percentile": quantile(null_values, 0.025),
            "null_97_5_percentile": quantile(null_values, 0.975),
            "p_one_sided_improvement": raw_p[model],
            "p_holm_across_three_oos_models": adjusted_p[model],
            "significant_at_0_05_after_holm": adjusted_p[model] < 0.05,
        }

    report = {
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY",
        "source": "data/storico_daily.csv",
        "draws": len(draws),
        "first_date": dates[0],
        "last_date": dates[-1],
        "warmup_draws": WARMUP,
        "frequency_window": FREQUENCY_WINDOW,
        "age_buckets": ["0-4", "5-9", "10-19", "20+"],
        "scored_targets": n,
        "chronological_splits": {
            name: {
                "targets": hi - lo,
                "first_target": forecasts[lo]["date"],
                "last_target": forecasts[hi - 1]["date"],
            }
            for name, (lo, hi) in split_bounds.items()
        },
        "models": metrics,
        "permutation_null_test": {
            "method": "Independent uniform 5-of-40 sequences; recompute prior-only frequency and age features in every replicate; compare OOS Brier improvement against the uniform baseline.",
            "permutations": PERMUTATIONS,
            "seed": SEED,
            "family_size": len(MODEL_NAMES),
            "family_definition": "Three fixed model comparisons on the blind OOS split; Holm-Bonferroni correction.",
            "results": permutation_summary,
        },
        "guardrail": "Exploratory only. The model family and parameters are fixed, but historical OOS and permutation results do not prove future predictability. Prospective promotion remains disabled; use at least 100 complete prospective cases and manual review.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "draws": len(draws),
        "scored_targets": n,
        "last_date": dates[-1],
        "oos_targets": split_records["oos"].__len__(),
        "permutations": PERMUTATIONS,
        "holm_p": {model: round(adjusted_p[model], 5) for model in MODEL_NAMES},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
