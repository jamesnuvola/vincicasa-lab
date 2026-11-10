#!/usr/bin/env python3
"""Prior-only H102 analysis for the fixed Q60 H101 RRF shadow cohort.

The disagreement predictor is built exclusively from the two parent Top20
freezes. Canonical outcomes are joined only for scoring after publication.
No forecast or freeze is written or modified by this program.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo
from math import comb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.sonar_q60_h101_rrf import reciprocal_rank_fusion

ROME = ZoneInfo("Europe/Rome")
DRAW_TIME = time(19, 0)
N = 20
REQUIRED = 200
SPLITS = (("discovery", 0, 100), ("validation", 100, 150), ("blind_oos", 150, 200))
LEDGER_FIELDS = [
    "target_date", "history_cutoff", "global_frozen_at", "positional_frozen_at",
    "h101_frozen_at", "parent_overlap", "disagreement_slots", "global_hits",
    "positional_hits", "h101_hits", "h101_minus_global", "h101_minus_positional",
]


def read_csv(path: str) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def parse_nums(value: str, expected: int, label: str) -> list[int]:
    try:
        nums = [int(x) for x in value.split()]
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{label}: invalid space-separated integer list") from exc
    if len(nums) != expected or len(set(nums)) != expected:
        raise ValueError(f"{label}: expected {expected} distinct values")
    if any(n < 1 or n > 40 for n in nums):
        raise ValueError(f"{label}: values must be in 1..40")
    return nums


def parse_timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("freeze timestamps must include a timezone offset")
    return dt.astimezone(ROME)


def unique_parent(rows: list[dict[str, str]], target: str, config: str) -> dict[str, str]:
    matches = [r for r in rows if r.get("target_date") == target and r.get("config_id") == config]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {config} freeze for {target}; found {len(matches)}")
    row = matches[0]
    if row.get("status") not in {"FROZEN_PENDING", "EVALUATED"}:
        raise ValueError(f"{config} {target}: unrecognized status {row.get('status')!r}")
    return row


def archive_map(rows: list[dict[str, str]]) -> dict[str, list[int]]:
    result: dict[str, list[int]] = {}
    previous = ""
    for row in rows:
        date = row.get("data", "")
        if not date or date in result or (previous and date <= previous):
            raise ValueError("canonical archive dates must be unique and strictly chronological")
        actual = [int(row[f"n{i}"]) for i in range(1, 6)]
        if len(set(actual)) != 5 or any(n < 1 or n > 40 for n in actual):
            raise ValueError(f"invalid canonical outcome on {date}")
        result[date] = actual
        previous = date
    return result


def build_ledger(global_rows, positional_rows, h101_rows, archive_rows):
    outcomes = archive_map(archive_rows)
    archive_dates = sorted(outcomes)
    records = []
    pending = []
    seen = set()

    for hrow in h101_rows:
        target = hrow.get("target_date", "")
        if not target or target in seen:
            raise ValueError("H101 target dates must be present and unique")
        seen.add(target)
        if hrow.get("config_id") != "q60_h101_rrf_k20_v1":
            raise ValueError(f"unexpected H101 config id on {target}")
        if hrow.get("status") not in {"FROZEN_PENDING", "EVALUATED"}:
            raise ValueError(f"unrecognized H101 status on {target}")

        prior_dates = [d for d in archive_dates if d < target]
        if not prior_dates:
            raise ValueError(f"no canonical prior history for {target}")
        expected_cutoff = prior_dates[-1]
        cutoff = hrow.get("history_cutoff", "")
        if cutoff != expected_cutoff:
            raise ValueError(f"{target}: H101 cutoff {cutoff} != latest prior canonical date {expected_cutoff}")

        hfreeze = parse_timestamp(hrow["frozen_at"])
        if hfreeze.date().isoformat() != target or hfreeze.timetz().replace(tzinfo=None) >= DRAW_TIME:
            raise ValueError(f"{target}: H101 freeze is not pre-draw on target date")

        grow = unique_parent(global_rows, target, "freq_100")
        prow = unique_parent(positional_rows, target, "position_seed_mix_top20_v1")
        gfreeze = parse_timestamp(grow["frozen_at"])
        pfreeze = parse_timestamp(prow["frozen_at"])
        if gfreeze.date().isoformat() != target or pfreeze.date().isoformat() != target:
            raise ValueError(f"{target}: parent freeze date mismatch")
        if gfreeze.timetz().replace(tzinfo=None) >= DRAW_TIME or pfreeze.timetz().replace(tzinfo=None) >= DRAW_TIME:
            raise ValueError(f"{target}: parent freeze is not pre-draw")
        if not (gfreeze < hfreeze and pfreeze < hfreeze):
            raise ValueError(f"{target}: H101 freeze must follow both parent freezes")
        if grow.get("history_cutoff") != cutoff or prow.get("history_cutoff") != cutoff:
            raise ValueError(f"{target}: parent cutoff mismatch")

        gtop = parse_nums(grow["top20"], N, f"{target} global Top20")
        ptop = parse_nums(prow["top20"], N, f"{target} positional Top20")
        rtop = parse_nums(hrow["top20"], N, f"{target} H101 Top20")
        expected_rrf = reciprocal_rank_fusion(gtop, ptop, k=N)
        if rtop != expected_rrf:
            raise ValueError(f"{target}: H101 Top20 does not reproduce from frozen parent ranks")

        if target not in outcomes:
            if any(hrow.get(k, "") for k in ("actual_numbers", "hit_numbers", "hit_count", "all5_top20")):
                raise ValueError(f"{target}: non-canonical outcome fields present before archive publication")
            pending.append(target)
            continue

        actual = outcomes[target]
        if hrow.get("actual_numbers"):
            stored_actual = parse_nums(hrow["actual_numbers"], 5, f"{target} stored actual")
            if set(stored_actual) != set(actual):
                raise ValueError(f"{target}: shadow outcome differs from canonical archive")
        winning = set(actual)
        overlap = len(set(gtop) & set(ptop))
        gh = len(winning & set(gtop))
        ph = len(winning & set(ptop))
        rh = len(winning & set(rtop))
        records.append({
            "target_date": target,
            "history_cutoff": cutoff,
            "global_frozen_at": grow["frozen_at"],
            "positional_frozen_at": prow["frozen_at"],
            "h101_frozen_at": hrow["frozen_at"],
            "parent_overlap": overlap,
            "disagreement_slots": N - overlap,
            "global_hits": gh,
            "positional_hits": ph,
            "h101_hits": rh,
            "h101_minus_global": rh - gh,
            "h101_minus_positional": rh - ph,
        })

    records.sort(key=lambda r: r["target_date"])
    if len(records) + len(pending) != len(h101_rows):
        raise AssertionError("every H101 row must be either scored or pending")
    return records, pending, archive_dates[-1] if archive_dates else None


def ols_slope(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    mx = sum(x) / len(x)
    my = sum(y) / len(y)
    den = sum((v - mx) ** 2 for v in x)
    if den == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / den


def exact_signflip_p(differences):
    observed = sum(differences)
    dist = {0: 1}
    for d in differences:
        nxt = defaultdict(int)
        for total, count in dist.items():
            nxt[total + d] += count
            nxt[total - d] += count
        dist = nxt
    extreme = sum(count for total, count in dist.items() if abs(total) >= abs(observed))
    return extreme / (2 ** len(differences))


def hypergeom_upper_p(observed_total, n):
    weights = [comb(20, k) * comb(20, 5 - k) for k in range(6)]
    denominator = comb(40, 5)
    dist = [1]
    for _ in range(n):
        nxt = [0] * (len(dist) + 5)
        for total, count in enumerate(dist):
            if count:
                for k, weight in enumerate(weights):
                    nxt[total + k] += count * weight
        dist = nxt
    if observed_total <= 0:
        return 1.0
    return sum(dist[observed_total:]) / (denominator ** n)


def holm_adjust(pvalues):
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [1.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * pvalues[idx])
        adjusted[idx] = min(1.0, running)
    return adjusted


def block_permutation_slope_p(x, y, block_length=20, permutations=9999, seed=1022026):
    n = len(x)
    if n != len(y) or n % block_length:
        raise ValueError("block permutation requires equal arrays divisible by block length")
    observed = ols_slope(x, y)
    if observed is None:
        raise ValueError("disagreement predictor has zero variance")
    blocks = [y[i:i + block_length] for i in range(0, n, block_length)]
    rng = random.Random(seed)
    extreme = 0
    for _ in range(permutations):
        order = list(range(len(blocks)))
        rng.shuffle(order)
        shuffled = [v for j in order for v in blocks[j]]
        statistic = ols_slope(x, shuffled)
        if statistic >= observed - 1e-15:
            extreme += 1
    return (extreme + 1) / (permutations + 1)


def circular_block_bootstrap_slope_ci(x, y, block_length=20, replicates=10000, seed=1022027):
    n = len(x)
    if len(y) != n or n < block_length:
        raise ValueError("invalid arrays for circular block bootstrap")
    rng = random.Random(seed)
    slopes = []
    for _ in range(replicates):
        indices = []
        while len(indices) < n:
            start = rng.randrange(n)
            indices.extend((start + j) % n for j in range(block_length))
        indices = indices[:n]
        slope = ols_slope([x[i] for i in indices], [y[i] for i in indices])
        if slope is not None:
            slopes.append(5.0 * slope)
    if not slopes:
        return None
    slopes.sort()
    lo = slopes[int(0.025 * (len(slopes) - 1))]
    hi = slopes[int(0.975 * (len(slopes) - 1))]
    return [lo, hi]


def summarize_split(records):
    x = [r["disagreement_slots"] for r in records]
    y = [r["h101_minus_global"] for r in records]
    slope = ols_slope(x, y)
    return {
        "targets": len(records),
        "mean_disagreement_slots": sum(x) / len(x) if x else None,
        "mean_h101_top20_hits": sum(r["h101_hits"] for r in records) / len(records) if records else None,
        "mean_global_top20_hits": sum(r["global_hits"] for r in records) / len(records) if records else None,
        "mean_positional_top20_hits": sum(r["positional_hits"] for r in records) / len(records) if records else None,
        "mean_h101_minus_global": sum(y) / len(y) if y else None,
        "slope_per_five_disagreement_slots": 5.0 * slope if slope is not None else None,
    }


def build_report(records, pending, latest_archive_date):
    report = {
        "schema_version": "1.0",
        "experiment_id": "Q60-H102-RRF-DISAGREEMENT-2026-11-10",
        "status": "PENDING_INSUFFICIENT_COMPLETE_TARGETS",
        "latest_canonical_draw": latest_archive_date,
        "complete_target_count": len(records),
        "pending_target_dates": pending,
        "required_target_count": REQUIRED,
        "reporting_splits": {"discovery": 100, "validation": 50, "blind_oos": 50},
        "inference_executed": False,
        "inference": None,
        "guardrails": {
            "forecast_rows_modified": False,
            "missing_freezes_reconstructed": False,
            "target_outcomes_used_for_predictors": False,
            "interim_inferential_looks": False,
            "engine_promotion_allowed": False,
        },
        "next_action": "Wait for canonical outcomes, append-only score existing H101 freezes, and run the one final analysis only after 200 complete targets."
    }
    if len(records) < REQUIRED:
        return report
    if len(records) > REQUIRED:
        raise ValueError("more than 200 complete targets found; reconcile cohort boundary before inference")

    report["status"] = "FINAL_INFERENCE_COMPLETE"
    report["reporting_split_results"] = {
        name: summarize_split(records[start:end]) for name, start, end in SPLITS
    }
    x = [r["disagreement_slots"] for r in records]
    y_global = [r["h101_minus_global"] for r in records]
    y_pos = [r["h101_minus_positional"] for r in records]
    slope = ols_slope(x, y_global)
    if slope is None:
        raise ValueError("no variance in parent disagreement; H102 slope is not estimable")
    beta5 = 5.0 * slope
    blind_slope = report["reporting_split_results"]["blind_oos"]["slope_per_five_disagreement_slots"]
    raw_p = [
        exact_signflip_p(y_global),
        exact_signflip_p(y_pos),
        hypergeom_upper_p(sum(r["h101_hits"] for r in records), len(records)),
        block_permutation_slope_p(x, y_global),
    ]
    adjusted = holm_adjust(raw_p)
    ci = circular_block_bootstrap_slope_ci(x, y_global)
    report["inference_executed"] = True
    report["inference"] = {
        "n": REQUIRED,
        "beta5_hits_per_target_per_five_disagreement_slots": beta5,
        "block_permutation_one_sided_p": raw_p[3],
        "bootstrap_block20_ci95": ci,
        "blind_oos_slope_per_five_disagreement_slots": blind_slope,
        "registered_pvalue_family": [
            "H101 minus global mean Top20 hits",
            "H101 minus positional mean Top20 hits",
            "H101 absolute Top20 hits versus exact Hypergeometric(40,20,5) convolution",
            "H102 disagreement slope"
        ],
        "raw_p_values": raw_p,
        "holm_adjusted_p_values": adjusted,
        "decision": (
            "MECHANISTIC_SUPPORT_ONLY"
            if beta5 >= 0.10 and adjusted[3] < 0.05 and ci[0] > 0 and blind_slope is not None and blind_slope > 0
            else "NOT_SUPPORTED"
        ),
        "engine_promotion_allowed": False,
    }
    return report


def write_outputs(report, records, report_out, ledger_out):
    Path(report_out).parent.mkdir(parents=True, exist_ok=True)
    Path(ledger_out).parent.mkdir(parents=True, exist_ok=True)
    Path(report_out).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with Path(ledger_out).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-csv", required=True)
    parser.add_argument("--positional-csv", required=True)
    parser.add_argument("--h101-csv", required=True)
    parser.add_argument("--archive-csv", required=True)
    parser.add_argument("--report-out", required=True)
    parser.add_argument("--ledger-out", required=True)
    args = parser.parse_args()

    records, pending, latest = build_ledger(
        read_csv(args.global_csv),
        read_csv(args.positional_csv),
        read_csv(args.h101_csv),
        read_csv(args.archive_csv),
    )
    report = build_report(records, pending, latest)
    write_outputs(report, records, args.report_out, args.ledger_out)
    print(f"H102_STATUS={report['status']}")
    print(f"H102_COMPLETE_TARGETS={len(records)}")
    print(f"H102_PENDING_TARGETS={len(pending)}")


if __name__ == "__main__":
    main()
