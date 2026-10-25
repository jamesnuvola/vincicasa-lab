#!/usr/bin/env python3
"""Append-only structural signature projection for the VinciCasa SONAR archive.

Existing signature rows are immutable. The generator verifies the archive/date/number
prefix, then appends only targets missing from the end of the signature ledger.
"""
from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "storico_daily.csv"
SIGNATURES = ROOT / "reports" / "daily_lab" / "structural_signatures.csv"
REPORT = ROOT / "reports" / "daily_lab" / "structural_recurrence_lab.json"

FIELDS = (
    "date numbers sum range odd even low_le20 high_gt20 overlap_prev1 "
    "gap1 gap2 gap3 gap4 sum_bin range_bin odd_cat low_cat overlap_cat "
    "gap1_bin gap2_bin gap3_bin gap4_bin sum_delta range_delta "
    "sum_transition range_transition mean_gap"
).split()
WIDTH = 27


def read_archive():
    dates = []
    draws = []
    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        expected = ["data", "n1", "n2", "n3", "n4", "n5"]
        if reader.fieldnames != expected:
            raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: unexpected archive header {reader.fieldnames}")
        for line, row in enumerate(reader, 2):
            try:
                target = date.fromisoformat(row["data"])
                nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            except Exception as exc:
                raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: malformed archive row {line}: {exc}")
            if dates and target <= dates[-1]:
                raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: dates not strictly increasing at {target}")
            if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n < 1 or n > 40 for n in nums):
                raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: invalid quintet at {target}")
            dates.append(target)
            draws.append(nums)
    if not draws:
        raise SystemExit("STRUCTURAL SIGNATURE BLOCKED: canonical archive is empty")
    return dates, draws


def category(value, edges, labels):
    for edge, label in zip(edges, labels):
        if value < edge:
            return label
    return labels[-1]


def gap_category(value):
    if value <= 3:
        return "G1-3"
    if value <= 7:
        return "G4-7"
    if value <= 12:
        return "G8-12"
    return "G13+"


def transition_sum(delta):
    if delta > 15:
        return "UP_BIG"
    if delta >= 6:
        return "UP"
    if delta < -15:
        return "DOWN_BIG"
    if delta <= -6:
        return "DOWN"
    return "FLAT"


def transition_range(delta):
    if delta >= 6:
        return "EXPAND_BIG"
    if delta >= 2:
        return "EXPAND"
    if delta <= -6:
        return "CONTRACT_BIG"
    if delta <= -2:
        return "CONTRACT"
    return "STABLE"


def fmt_number(value):
    return format(value, "g")


def make_signature(target, nums, previous):
    total = sum(nums)
    spread = nums[-1] - nums[0]
    odd = sum(n % 2 for n in nums)
    even = 5 - odd
    low = sum(n <= 20 for n in nums)
    high = 5 - low
    overlap = len(set(nums) & set(previous)) if previous is not None else 0
    gaps = [nums[i + 1] - nums[i] for i in range(4)]
    sum_bins = ((80, "S<80"), (100, "S80-99"), (120, "S100-119"), (140, "S120-139"))
    sum_bin = category(total, [x[0] for x in sum_bins], [x[1] for x in sum_bins] + ["S140+"])
    range_bin = category(spread, [20, 25, 30, 35], ["R<20", "R20-24", "R25-29", "R30-34", "R35-39"])
    if previous is None:
        sum_delta = ""
        range_delta = ""
        sum_transition = "NA"
        range_transition = "NA"
    else:
        sum_delta = total - sum(previous)
        range_delta = spread - (previous[-1] - previous[0])
        sum_transition = transition_sum(sum_delta)
        range_transition = transition_range(range_delta)
    mean_gap = fmt_number(sum(gaps) / 4)
    return [
        target.isoformat(),
        "-".join(map(str, nums)),
        str(total),
        str(spread),
        str(odd),
        str(even),
        str(low),
        str(high),
        str(overlap),
        *map(str, gaps),
        sum_bin,
        range_bin,
        f"O{odd}",
        f"L{low}",
        "X0" if overlap == 0 else "X1" if overlap == 1 else "X2+",
        *map(gap_category, gaps),
        str(sum_delta),
        str(range_delta),
        sum_transition,
        range_transition,
        mean_gap,
    ]


def main():
    dates, draws = read_archive()
    if not SIGNATURES.is_file():
        raise SystemExit("STRUCTURAL SIGNATURE BLOCKED: append-only signature ledger is missing")
    with SIGNATURES.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        existing = list(reader)
    if header != FIELDS:
        raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: unexpected signature header ({len(header)} columns)")
    if any(len(row) != WIDTH for row in existing):
        raise SystemExit("STRUCTURAL SIGNATURE BLOCKED: an existing signature row does not have 27 columns")
    if len(existing) > len(draws):
        raise SystemExit("STRUCTURAL SIGNATURE BLOCKED: signatures extend beyond the canonical archive")

    # Do not rewrite existing rows: only validate their ordered date/number prefix.
    for index, row in enumerate(existing):
        expected_date = dates[index].isoformat()
        expected_numbers = "-".join(map(str, draws[index]))
        if row[0] != expected_date:
            raise SystemExit(
                f"STRUCTURAL SIGNATURE BLOCKED: non-prefix signature date at row {index + 2}: "
                f"expected {expected_date}, found {row[0]}"
            )
        if row[1] != expected_numbers:
            raise SystemExit(f"STRUCTURAL SIGNATURE BLOCKED: numbers mismatch for {expected_date}")

    appended = []
    for index in range(len(existing), len(draws)):
        previous = draws[index - 1] if index else None
        appended.append(make_signature(dates[index], draws[index], previous))

    if appended:
        with SIGNATURES.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerows(appended)

    signature_count = len(existing) + len(appended)
    report = {
        "status": "COMPLETE_APPEND_ONLY",
        "source": "data/storico_daily.csv",
        "archive_rows": len(draws),
        "signature_rows": signature_count,
        "column_count": WIDTH,
        "first_signature_date": dates[0].isoformat(),
        "last_signature_date": dates[-1].isoformat(),
        "appended_rows_this_run": len(appended),
        "appended_dates_this_run": [row[0] for row in appended],
        "existing_prefix_preserved": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
