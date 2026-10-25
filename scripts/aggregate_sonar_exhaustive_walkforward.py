#!/usr/bin/env python3
"""Validate and summarize the full 1,023-formula historical walk-forward rank matrix."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from array import array
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PARTS = ROOT / "reports" / "sequence_agent" / "exhaustive_formula_walkforward" / "parts"
METRICS_OUT = ROOT / "reports" / "sequence_agent" / "exhaustive_formula_walkforward_metrics.json"
MANIFEST_OUT = ROOT / "reports" / "sequence_agent" / "exhaustive_formula_walkforward_manifest.json"
CANDIDATE_COUNT = math.comb(40, 5)
FORMULA_COUNT = 1023
RANK_COLUMNS = [f"rank_mask_{mask:04d}" for mask in range(1, FORMULA_COUNT + 1)]
FEATURE_NAMES = (
    "number_frequency", "pair_interaction", "triple_interaction",
    "quadruple_interaction", "exact_quintet_recurrence",
    "sorted_position_frequency", "gap_pattern", "sum_distribution",
    "odd_count", "decade_profile",
)
TOP20_BASELINE = 20 / CANDIDATE_COUNT


def read_canonical():
    with ARCHIVE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows or [x.strip().lower() for x in rows[0][:6]] not in (
        ["data", "n1", "n2", "n3", "n4", "n5"],
        ["date", "n1", "n2", "n3", "n4", "n5"],
    ):
        raise SystemExit("WALKFORWARD_AGGREGATION_BLOCKED: invalid canonical archive header")
    result = []
    previous = ""
    seen = set()
    for line, row in enumerate(rows[1:], 2):
        if not row or not any(x.strip() for x in row):
            continue
        d = row[0].strip()
        nums = tuple(int(x) for x in row[1:6])
        if d in seen or (previous and d <= previous):
            raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: duplicate/non-chronological date at row {line}")
        if len(set(nums)) != 5 or nums != tuple(sorted(nums)) or any(x < 1 or x > 40 for x in nums):
            raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: invalid quintet at {d}")
        result.append((d, nums))
        seen.add(d)
        previous = d
    return result


def binomial_upper_tail(k, n, p):
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    terms = []
    for j in range(k, n + 1):
        terms.append(
            math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1)
            + j * math.log(p) + (n - j) * math.log1p(-p)
        )
    peak = max(terms)
    return min(1.0, math.exp(peak) * sum(math.exp(value - peak) for value in terms))


def holm_adjust(items):
    ordered = sorted(items, key=lambda item: item[1])
    result = {}
    running = 0.0
    total = len(ordered)
    for i, (key, pvalue) in enumerate(ordered):
        running = max(running, min(1.0, (total - i) * pvalue))
        result[key] = running
    return result


def main():
    canonical = read_canonical()
    total = len(canonical)
    d1, d2 = int(total * 0.60), int(total * 0.80)
    expected_starts = list(range(0, total, 100))
    expected_names = [f"part_{start:04d}_{min(start + 100, total):04d}.csv" for start in expected_starts]
    paths = sorted(PARTS.glob("part_*.csv"))
    actual_names = [path.name for path in paths]
    if actual_names != expected_names:
        raise SystemExit(
            "WALKFORWARD_AGGREGATION_BLOCKED: batch part list mismatch; "
            f"expected {len(expected_names)} parts, found {len(actual_names)}"
        )

    rank_values = [[array("I") for _ in range(3)] for _ in range(FORMULA_COUNT)]
    part_manifest = []
    target_count = 0
    previous_date = ""
    first_date = last_date = ""
    for path in paths:
        match = re.fullmatch(r"part_(\d{4})_(\d{4})\.csv", path.name)
        start, end = int(match.group(1)), int(match.group(2))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        row_count = 0
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + RANK_COLUMNS:
                raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: schema mismatch in {path.name}")
            for row in reader:
                index = target_count
                if index >= total or int(row["prior_draws"]) != index:
                    raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: wrong prior_draws at row {index}")
                target_date, nums = canonical[index]
                if row["target_date"] != target_date or tuple(int(x) for x in row["actual_quintet"].split()) != nums:
                    raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: canonical mismatch at {target_date}")
                expected_cutoff = canonical[index - 1][0] if index else ""
                if row["cutoff_date"] != expected_cutoff or (expected_cutoff and expected_cutoff >= target_date):
                    raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: cutoff/leakage violation at {target_date}")
                if index == 0:
                    if row["status"] != "INSUFFICIENT_HISTORY" or any(row[column] for column in RANK_COLUMNS):
                        raise SystemExit("WALKFORWARD_AGGREGATION_BLOCKED: first target must remain unscored")
                else:
                    if row["status"] != "SCORED":
                        raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: unexpected status at {target_date}")
                    split = 0 if index < d1 else (1 if index < d2 else 2)
                    for mask, column in enumerate(RANK_COLUMNS, start=1):
                        value = int(row[column])
                        if not 1 <= value <= CANDIDATE_COUNT:
                            raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: invalid rank for mask {mask} at {target_date}")
                        rank_values[mask - 1][split].append(value)
                if not first_date:
                    first_date = target_date
                last_date = target_date
                previous_date = target_date
                target_count += 1
                row_count += 1
        if row_count != end - start:
            raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: {path.name} expected {end-start} rows, found {row_count}")
        part_manifest.append({
            "path": str(path.relative_to(ROOT)),
            "start_index": start,
            "end_index_exclusive": end,
            "data_rows": row_count,
            "sha256": digest,
        })

    if target_count != total or not rank_values:
        raise SystemExit(f"WALKFORWARD_AGGREGATION_BLOCKED: expected {total} targets, found {target_count}")

    pvalues = []
    metrics = []
    split_names = ("discovery", "validation", "blind_oos")
    for mask in range(1, FORMULA_COUNT + 1):
        selected_features = [FEATURE_NAMES[i] for i in range(len(FEATURE_NAMES)) if mask & (1 << i)]
        split_metrics = {}
        for split_index, split_name in enumerate(split_names):
            values = rank_values[mask - 1][split_index]
            ordered = sorted(values)
            n = len(ordered)
            top20 = sum(value <= 20 for value in ordered)
            top100 = sum(value <= 100 for value in ordered)
            mean_rank = sum(ordered) / n if n else None
            median_rank = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2 if n else None
            pvalue = binomial_upper_tail(top20, n, TOP20_BASELINE) if n else 1.0
            key = f"{mask}:{split_name}"
            pvalues.append((key, pvalue))
            split_metrics[split_name] = {
                "targets_scored": n,
                "actual_quintet_rank_top20_hits": top20,
                "actual_quintet_rank_top100_hits": top100,
                "mean_actual_rank": mean_rank,
                "median_actual_rank": median_rank,
                "mean_rank_percentile": ((mean_rank - 0.5) / CANDIDATE_COUNT) if mean_rank is not None else None,
                "one_sided_binomial_p_vs_random_top20": pvalue,
            }
        metrics.append({
            "formula_mask": mask,
            "formula_id": f"F{mask:04d}",
            "features": selected_features,
            "feature_count": len(selected_features),
            "splits": split_metrics,
        })
    adjusted = holm_adjust(pvalues)
    for formula in metrics:
        for split_name in split_names:
            key = f"{formula['formula_mask']}:{split_name}"
            formula["splits"][split_name]["holm_p_across_3069_tests"] = adjusted[key]

    oos_ranked = sorted(metrics, key=lambda m: (
        -m["splits"]["blind_oos"]["actual_quintet_rank_top20_hits"],
        m["splits"]["blind_oos"]["mean_actual_rank"],
        m["formula_mask"],
    ))
    report = {
        "schema_version": "1.0",
        "status": "COMPLETE_EXHAUSTIVE_WALKFORWARD",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive": "data/storico_daily.csv",
        "target_count": total,
        "scored_target_count": total - 1,
        "first_target_date": first_date,
        "last_target_date": last_date,
        "candidate_universe_size": CANDIDATE_COUNT,
        "formula_count": FORMULA_COUNT,
        "formula_grammar": "All 1,023 non-empty subsets of the ten registered feature families, ranked across all 658,008 quintets for every historical target using only prior draws.",
        "split_sizes_including_first_unscored_target": {
            "discovery": d1,
            "validation": d2 - d1,
            "blind_oos": total - d2,
        },
        "split_sizes_scored": {
            "discovery": len(rank_values[0][0]),
            "validation": len(rank_values[0][1]),
            "blind_oos": len(rank_values[0][2]),
        },
        "random_baseline": {
            "top20_exact_quintet_probability": TOP20_BASELINE,
            "expected_top20_exact_hits_in_blind_oos": len(rank_values[0][2]) * TOP20_BASELINE,
        },
        "multiple_testing": {
            "tests": len(pvalues),
            "method": "Holm-Bonferroni across 1,023 formulas × 3 chronological splits",
        },
        "formula_metrics": metrics,
        "best_blind_oos_by_top20_then_mean_rank": oos_ranked[:25],
        "guardrails": [
            "Each target's feature counts use only draws strictly before its cutoff.",
            "The first archive row is explicitly INSUFFICIENT_HISTORY and is not scored.",
            "Ranks are exact within the full 658,008-combination candidate universe; ties are resolved by lexicographic quintet order after rounding scores to 10 decimals.",
            "All historical comparisons are exploratory because the formula grammar itself was defined during research; no formula is promoted automatically.",
            "A high historical rank score is not proof of future predictability in a random lottery.",
        ],
    }
    manifest = {
        "schema_version": "1.0",
        "status": "VALIDATED_COMPLETE",
        "target_count": total,
        "scored_target_count": total - 1,
        "formula_count": FORMULA_COUNT,
        "candidate_universe_size": CANDIDATE_COUNT,
        "parts": part_manifest,
        "metrics_path": str(METRICS_OUT.relative_to(ROOT)),
        "reassembly": "Concatenate the listed CSV parts in ascending start_index order; keep the header from the first part and skip repeated headers.",
        "cutoff_validation": "Every target row's cutoff equals the immediately preceding canonical archive date; prior_draws equals the zero-based target index.",
    }
    METRICS_OUT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    MANIFEST_OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "target_count": total,
        "scored_target_count": total - 1,
        "formula_count": FORMULA_COUNT,
        "candidate_universe_size": CANDIDATE_COUNT,
        "part_count": len(part_manifest),
        "metrics_path": str(METRICS_OUT.relative_to(ROOT)),
        "manifest_path": str(MANIFEST_OUT.relative_to(ROOT)),
        "top_oos": [
            {"formula_id": x["formula_id"], "features": x["features"],
             "top20_hits": x["splits"]["blind_oos"]["actual_quintet_rank_top20_hits"],
             "mean_rank": x["splits"]["blind_oos"]["mean_actual_rank"],
             "holm_p": x["splits"]["blind_oos"]["holm_p_across_3069_tests"]}
            for x in oos_ranked[:10]
        ],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
