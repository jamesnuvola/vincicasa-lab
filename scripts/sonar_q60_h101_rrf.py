#!/usr/bin/env python3
"""Generate one append-only Q60 H101 reciprocal-rank-fusion shadow freeze.

Only the two already-frozen parent Top20 lists are inputs. The canonical
outcome archive is read solely to verify its latest date/cutoff; no outcome
numbers are read by the fusion scorer.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
N = 20
DRAW_TIME = time(19, 0)
GLOBAL_CONFIG = "freq_100"
POSITIONAL_CONFIG = "position_seed_mix_top20_v1"
OUTPUT_FIELDS = [
    "target_date", "frozen_at", "history_cutoff", "config_id", "model_version",
    "rrf_k", "top20", "top10", "top5", "source_global_frozen_at",
    "source_positional_frozen_at", "source_global_history_cutoff",
    "source_positional_history_cutoff", "status", "actual_numbers",
    "hit_numbers", "hit_count", "all5_top20", "evaluated_at",
    "evaluated_at_data_through", "timeliness_note",
]


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("freeze timestamps must include a timezone offset")
    return dt.astimezone(ROME)


def parse_top20(value: str) -> list[int]:
    numbers = [int(x) for x in value.split()]
    if len(numbers) != N or len(set(numbers)) != N:
        raise ValueError("each parent ranking must contain exactly 20 unique numbers")
    if any(n < 1 or n > 40 for n in numbers):
        raise ValueError("candidate numbers must be in 1..40")
    return numbers


def reciprocal_rank_fusion(global_top20: list[int], positional_top20: list[int],
                           k: int = N) -> list[int]:
    if len(global_top20) != N or len(positional_top20) != N:
        raise ValueError("both parent rankings must contain 20 numbers")
    if len(set(global_top20)) != N or len(set(positional_top20)) != N:
        raise ValueError("parent rankings must not contain duplicates")
    if any(n < 1 or n > 40 for n in global_top20 + positional_top20):
        raise ValueError("candidate numbers must be in 1..40")
    rg = {number: rank for rank, number in enumerate(global_top20, start=1)}
    rp = {number: rank for rank, number in enumerate(positional_top20, start=1)}
    universe = set(global_top20) | set(positional_top20)

    def score(number: int) -> float:
        return (1.0 / (k + rg[number]) if number in rg else 0.0) + (
            1.0 / (k + rp[number]) if number in rp else 0.0
        )

    return sorted(universe, key=lambda number: (-score(number), number))[:N]


def unique_parent(rows: list[dict[str, str]], target_date: str,
                  config_id: str) -> dict[str, str]:
    matches = [
        row for row in rows
        if row.get("target_date") == target_date and row.get("config_id") == config_id
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one {config_id} row for {target_date}; found {len(matches)}")
    row = matches[0]
    if row.get("status") not in {"FROZEN_PENDING", "EVALUATED"}:
        raise ValueError(f"parent {config_id} row is not a recognized frozen/evaluated record")
    return row


def build_freeze_row(global_rows: list[dict[str, str]],
                     positional_rows: list[dict[str, str]],
                     archive_rows: list[dict[str, str]],
                     target_date: str, frozen_at: str) -> dict[str, str]:
    if not archive_rows or "data" not in archive_rows[0]:
        raise ValueError("canonical archive must contain a data date column")
    latest_cutoff = max(row["data"] for row in archive_rows)
    target = datetime.fromisoformat(target_date).date()
    if target.isoformat() != target_date or target_date <= latest_cutoff:
        raise ValueError("target must be a valid date strictly after the canonical archive cutoff")

    freeze_dt = parse_dt(frozen_at)
    if freeze_dt.date().isoformat() != target_date:
        raise ValueError("fusion freeze must occur on the target calendar date")
    if freeze_dt.timetz().replace(tzinfo=None) >= DRAW_TIME:
        raise ValueError("fusion freeze must precede the nominal 19:00 Europe/Rome draw time")

    global_row = unique_parent(global_rows, target_date, GLOBAL_CONFIG)
    positional_row = unique_parent(positional_rows, target_date, POSITIONAL_CONFIG)
    if global_row.get("history_cutoff") != latest_cutoff:
        raise ValueError("global parent cutoff does not equal the latest canonical archive date")
    if positional_row.get("history_cutoff") != latest_cutoff:
        raise ValueError("positional parent cutoff does not equal the latest canonical archive date")

    global_frozen = parse_dt(global_row["frozen_at"])
    positional_frozen = parse_dt(positional_row["frozen_at"])
    if global_frozen.date().isoformat() != target_date or positional_frozen.date().isoformat() != target_date:
        raise ValueError("both parent forecasts must have been frozen on the target date")
    if not (global_frozen < freeze_dt and positional_frozen < freeze_dt):
        raise ValueError("fusion freeze must occur after both parent freezes")
    if global_frozen.timetz().replace(tzinfo=None) >= DRAW_TIME or positional_frozen.timetz().replace(tzinfo=None) >= DRAW_TIME:
        raise ValueError("both parent freezes must precede the nominal draw time")

    global_top20 = parse_top20(global_row["top20"])
    positional_top20 = parse_top20(positional_row["top20"])
    fused = reciprocal_rank_fusion(global_top20, positional_top20, k=N)
    return {
        "target_date": target_date,
        "frozen_at": frozen_at,
        "history_cutoff": latest_cutoff,
        "config_id": "q60_h101_rrf_k20_v1",
        "model_version": "q60-h101-rrf-k20-v1",
        "rrf_k": str(N),
        "top20": " ".join(map(str, fused)),
        "top10": " ".join(map(str, fused[:10])),
        "top5": " ".join(map(str, fused[:5])),
        "source_global_frozen_at": global_row["frozen_at"],
        "source_positional_frozen_at": positional_row["frozen_at"],
        "source_global_history_cutoff": global_row["history_cutoff"],
        "source_positional_history_cutoff": positional_row["history_cutoff"],
        "status": "FROZEN_PENDING",
        "actual_numbers": "",
        "hit_numbers": "",
        "hit_count": "",
        "all5_top20": "",
        "evaluated_at": "",
        "evaluated_at_data_through": "",
        "timeliness_note": "New research-only pre-target RRF freeze; both parent lists were already frozen; cutoff is canonical latest date.",
    }


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-csv", required=True)
    parser.add_argument("--positional-csv", required=True)
    parser.add_argument("--archive-csv", required=True)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--frozen-at", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    row = build_freeze_row(
        read_csv(args.global_csv),
        read_csv(args.positional_csv),
        read_csv(args.archive_csv),
        args.target_date,
        args.frozen_at,
    )
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)
    print("Q60_H101_RRF_FREEZE_PASS")
    print(row["top20"])


if __name__ == "__main__":
    main()
