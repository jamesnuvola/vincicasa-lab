#!/usr/bin/env python3
"""Rebuild the structural recurrence catalogue from the canonical VinciCasa archive.

The legacy daily_lab signature prefix is used as an independent parity check.
This is descriptive recurrence accounting, not a predictive model.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "storico_daily.csv"
LEGACY_SIGNATURES = ROOT / "reports" / "daily_lab" / "structural_signatures.csv"
LEGACY_RECURRENCE = ROOT / "reports" / "daily_lab" / "structural_recurrence.csv"
OUT = ROOT / "reports" / "sequence_agent"
OUT_CSV = OUT / "structural_recurrence_current.csv"
OUT_JSON = OUT / "structural_recurrence_current.json"
SIGNATURE_FIELDS = [
    "date", "numbers", "sum", "range", "odd", "even", "low_le20", "high_gt20",
    "overlap_prev1", "gap1", "gap2", "gap3", "gap4", "sum_bin", "range_bin",
    "odd_cat", "low_cat", "overlap_cat", "gap1_bin", "gap2_bin", "gap3_bin",
    "gap4_bin", "sum_delta", "range_delta", "sum_transition", "range_transition",
    "mean_gap",
]
FEATURES = [
    "sum_bin", "range_bin", "odd_cat", "low_cat", "overlap_cat",
    "gap1_bin", "gap2_bin", "gap3_bin", "gap4_bin",
    "sum_transition", "range_transition",
]
RECURRENCE_FIELDS = [
    "feature", "category", "occurrences", "last_occurrence_date", "age_since_last",
    "age_if_repeating_next_draw", "interval_count", "interval_mean", "interval_median",
    "interval_q25", "interval_q50", "interval_q75", "interval_q90", "interval_q95",
    "hazard_at_next_age", "status", "current_category", "hazard_by_age_json",
]


def blocked(message: str) -> None:
    raise SystemExit(f"STRUCTURAL RECURRENCE BLOCKED: {message}")


def gap_bin(value: int) -> str:
    if value <= 3:
        return "G1-3"
    if value <= 7:
        return "G4-7"
    if value <= 12:
        return "G8-12"
    return "G13+"


def sum_transition(delta: int) -> str:
    if delta <= -16:
        return "DOWN_BIG"
    if delta <= -6:
        return "DOWN"
    if delta >= 16:
        return "UP_BIG"
    if delta >= 6:
        return "UP"
    return "FLAT"


def range_transition(delta: int) -> str:
    if delta <= -6:
        return "CONTRACT_BIG"
    if delta <= -2:
        return "CONTRACT"
    if delta >= 6:
        return "EXPAND_BIG"
    if delta >= 2:
        return "EXPAND"
    return "STABLE"


def read_archive():
    if not DATA.is_file():
        blocked("data/storico_daily.csv missing")
    raw = DATA.read_bytes()
    blob_sha = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    rows = []
    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            blocked(f"unexpected CSV header: {reader.fieldnames}")
        for line_no, row in enumerate(reader, 2):
            try:
                draw_date = date.fromisoformat(row["data"])
                numbers = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            except Exception as exc:
                blocked(f"invalid row {line_no}: {exc}")
            if len(set(numbers)) != 5 or tuple(sorted(numbers)) != numbers or any(n < 1 or n > 40 for n in numbers):
                blocked(f"invalid five-number draw at line {line_no}: {numbers}")
            if rows and draw_date != rows[-1][0] + timedelta(days=1):
                blocked(f"non-consecutive date at line {line_no}: {draw_date}")
            rows.append((draw_date, numbers))
    if len(rows) < 1000:
        blocked(f"insufficient archive rows: {len(rows)}")
    return rows, blob_sha


def make_signatures(rows):
    signatures = []
    previous_sum = None
    previous_range = None
    previous_numbers = set()
    for draw_date, numbers in rows:
        total = sum(numbers)
        span = numbers[-1] - numbers[0]
        odd = sum(n % 2 for n in numbers)
        low = sum(n <= 20 for n in numbers)
        overlap = len(set(numbers) & previous_numbers) if signatures else 0
        gaps = [numbers[i + 1] - numbers[i] for i in range(4)]
        sum_delta = total - previous_sum if previous_sum is not None else None
        range_delta = span - previous_range if previous_range is not None else None
        row = {
            "date": draw_date.isoformat(),
            "numbers": "-".join(map(str, numbers)),
            "sum": str(total),
            "range": str(span),
            "odd": str(odd),
            "even": str(5 - odd),
            "low_le20": str(low),
            "high_gt20": str(5 - low),
            "overlap_prev1": str(overlap),
            "gap1": str(gaps[0]),
            "gap2": str(gaps[1]),
            "gap3": str(gaps[2]),
            "gap4": str(gaps[3]),
            "sum_bin": "S<80" if total < 80 else "S80-99" if total < 100 else "S100-119" if total < 120 else "S120-139" if total < 140 else "S140+",
            "range_bin": "R<20" if span < 20 else "R20-24" if span < 25 else "R25-29" if span < 30 else "R30-34" if span < 35 else "R35+",
            "odd_cat": f"O{odd}",
            "low_cat": f"L{low}",
            "overlap_cat": "X2+" if overlap >= 2 else f"X{overlap}",
            "gap1_bin": gap_bin(gaps[0]),
            "gap2_bin": gap_bin(gaps[1]),
            "gap3_bin": gap_bin(gaps[2]),
            "gap4_bin": gap_bin(gaps[3]),
            "sum_delta": "" if sum_delta is None else str(sum_delta),
            "range_delta": "" if range_delta is None else str(range_delta),
            "sum_transition": "NA" if sum_delta is None else sum_transition(sum_delta),
            "range_transition": "NA" if range_delta is None else range_transition(range_delta),
            "mean_gap": str(sum(gaps) / 4),
        }
        signatures.append(row)
        previous_sum = total
        previous_range = span
        previous_numbers = set(numbers)
    return signatures


def verify_legacy_prefix(signatures):
    if not LEGACY_SIGNATURES.is_file() or not LEGACY_RECURRENCE.is_file():
        blocked("legacy structural prefix needed for parity audit is missing")
    with LEGACY_SIGNATURES.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != SIGNATURE_FIELDS:
            blocked("legacy structural signature schema changed")
        legacy = list(reader)
    if len(legacy) > len(signatures):
        blocked("legacy signature file is longer than canonical archive")
    mismatches = []
    for i, old in enumerate(legacy):
        new = signatures[i]
        for field in SIGNATURE_FIELDS:
            if old[field] != new[field]:
                mismatches.append({"row": i + 1, "field": field, "legacy": old[field], "recomputed": new[field]})
                if len(mismatches) >= 5:
                    break
        if mismatches:
            break
    if mismatches:
        blocked("legacy prefix parity failed: " + json.dumps(mismatches, ensure_ascii=False))
    return len(legacy)


def quantile(sorted_values, probability):
    if not sorted_values:
        return 0.0
    position = probability * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def build_recurrence(signatures):
    current = signatures[-1]
    rows = []
    feature_summary = {}
    for feature in FEATURES:
        categories = sorted({row[feature] for row in signatures if row[feature] != "NA"})
        feature_summary[feature] = []
        for category in categories:
            indices = [i for i, row in enumerate(signatures) if row[feature] == category]
            if len(indices) < 2:
                blocked(f"category has fewer than two occurrences: {feature}={category}")
            intervals = sorted(indices[i] - indices[i - 1] for i in range(1, len(indices)))
            age = len(signatures) - 1 - indices[-1]
            next_age = age + 1
            mean_interval = sum(intervals) / len(intervals)
            q25, q50, q75, q90, q95 = (quantile(intervals, p) for p in (0.25, 0.50, 0.75, 0.90, 0.95))
            hazard_by_age = []
            for interval_age in range(1, intervals[-1] + 1):
                events = sum(value == interval_age for value in intervals)
                at_risk = sum(value >= interval_age for value in intervals)
                hazard_by_age.append({
                    "age": interval_age,
                    "events": events,
                    "at_risk": at_risk,
                    "hazard": events / at_risk if at_risk else 0.0,
                })
            next_events = sum(value == next_age for value in intervals)
            next_at_risk = sum(value >= next_age for value in intervals)
            hazard_next = next_events / next_at_risk if next_at_risk else 0.0
            status = "OVERDUE_BY_Q95" if age >= q95 else "REGULAR" if mean_interval > 30 else "FREQUENT"
            row = {
                "feature": feature,
                "category": category,
                "occurrences": len(indices),
                "last_occurrence_date": signatures[indices[-1]]["date"],
                "age_since_last": age,
                "age_if_repeating_next_draw": next_age,
                "interval_count": len(intervals),
                "interval_mean": mean_interval,
                "interval_median": q50,
                "interval_q25": q25,
                "interval_q50": q50,
                "interval_q75": q75,
                "interval_q90": q90,
                "interval_q95": q95,
                "hazard_at_next_age": hazard_next,
                "status": status,
                "current_category": int(current[feature] == category),
                "hazard_by_age_json": json.dumps(hazard_by_age, separators=(",", ":"), ensure_ascii=False),
            }
            rows.append(row)
            feature_summary[feature].append({
                "category": category,
                "occurrences": len(indices),
                "last_occurrence_date": row["last_occurrence_date"],
                "age_since_last": age,
                "interval_mean": mean_interval,
                "interval_q95": q95,
                "hazard_at_next_age": hazard_next,
                "status": status,
                "current_category": row["current_category"],
            })
    return rows, feature_summary


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    archive, source_blob_sha = read_archive()
    signatures = make_signatures(archive)
    legacy_prefix_rows = verify_legacy_prefix(signatures)
    recurrence, feature_summary = build_recurrence(signatures)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECURRENCE_FIELDS)
        writer.writeheader()
        writer.writerows(recurrence)
    summary = {
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY",
        "source": "data/storico_daily.csv",
        "source_git_blob_sha": source_blob_sha,
        "first_date": archive[0][0].isoformat(),
        "last_date": archive[-1][0].isoformat(),
        "draws": len(archive),
        "feature_count": len(FEATURES),
        "category_count": len(recurrence),
        "legacy_prefix_reconciliation": {
            "legacy_signature_rows": legacy_prefix_rows,
            "recomputed_rows_compared": legacy_prefix_rows,
            "field_count": len(SIGNATURE_FIELDS),
            "mismatches": 0,
            "result": "EXACT_MATCH",
        },
        "features": feature_summary,
        "guardrail": "Recurrence ages, intervals and empirical hazards are descriptive historical summaries. They are not calibrated probabilities of the next draw and do not establish predictive lift.",
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": summary["status"],
        "source_git_blob_sha": source_blob_sha,
        "draws": len(archive),
        "cutoff": archive[-1][0].isoformat(),
        "categories": len(recurrence),
        "legacy_prefix_rows_exact": legacy_prefix_rows,
        "mismatches": 0,
        "outputs": [str(OUT_CSV.relative_to(ROOT)), str(OUT_JSON.relative_to(ROOT))],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
