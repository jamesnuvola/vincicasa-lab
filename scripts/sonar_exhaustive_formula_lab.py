#!/usr/bin/env python3
"""Exhaustive finite-grammar SONAR formula catalog.

For each historical target, records subset-interaction and structural conditions
using only draws strictly before that target. For the next target, scores every
one of C(40,5)=658,008 possible quintets under all 2^10-1=1,023 non-empty
equal-weight combinations of the registered feature families.

This is exhaustive over the declared finite grammar, not over the mathematically
infinite set of all possible formulas. It is research-only and never replaces a
pre-existing immutable forecast freeze.
"""
from __future__ import annotations

import csv
import itertools
import json
import math
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
LEDGER = OUT / "exhaustive_formula_condition_ledger.csv"
REPORT = OUT / "exhaustive_formula_catalog.json"
ALPHA = 0.5
K_VALUES = (1, 2, 3, 4, 5)
WINDOWS = (10, 25, 50, 100, 250, 500)
FAMILY_NAMES = (
    "number_frequency",
    "pair_interaction",
    "triple_interaction",
    "quadruple_interaction",
    "exact_quintet_recurrence",
    "sorted_position_frequency",
    "gap_pattern",
    "sum_distribution",
    "odd_count",
    "decade_profile",
)
EXPECTED_CANDIDATES = math.comb(40, 5)
EXPECTED_FORMULAS = (1 << len(FAMILY_NAMES)) - 1


def read_archive():
    if not ARCHIVE.is_file():
        raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: archive missing: {ARCHIVE}")
    with ARCHIVE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if len(rows) < 2:
        raise SystemExit("EXHAUSTIVE_LAB_BLOCKED: archive empty")
    header = [x.strip().lower() for x in rows[0][:6]]
    if header not in (
        ["data", "n1", "n2", "n3", "n4", "n5"],
        ["date", "n1", "n2", "n3", "n4", "n5"],
    ):
        raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: unexpected header {rows[0][:6]}")
    dates, draws, seen = [], [], set()
    previous = ""
    for line, row in enumerate(rows[1:], start=2):
        if not row or not any(x.strip() for x in row):
            continue
        if len(row) < 6:
            raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: malformed row {line}")
        d = row[0].strip()
        try:
            date.fromisoformat(d)
            nums = tuple(int(v) for v in row[1:6])
        except Exception as exc:
            raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: invalid row {line}: {exc}")
        if d in seen or (previous and d <= previous):
            raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: duplicate/non-chronological date {d}")
        if len(set(nums)) != 5 or nums != tuple(sorted(nums)) or any(n < 1 or n > 40 for n in nums):
            raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: invalid quintet at {d}: {nums}")
        seen.add(d)
        previous = d
        dates.append(d)
        draws.append(nums)
    if len(draws) != EXPECTED_CANDIDATES and len(draws) < 500:
        raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: too few verified draws: {len(draws)}")
    return dates, draws


def colex_rank(values):
    """Combinadic/colex rank for 1-based sorted values."""
    return sum(math.comb(v - 1, i) for i, v in enumerate(values, start=1))


def subset_rank(values):
    return {k: [colex_rank(s) for s in itertools.combinations(values, k)] for k in K_VALUES}


def decade_code(values):
    counts = [0, 0, 0, 0]
    for n in values:
        counts[(n - 1) // 10] += 1
    return sum(counts[i] * (6 ** i) for i in range(4))


def gap_code(values):
    gaps = [values[i + 1] - values[i] for i in range(4)]
    code = 0
    for g in gaps:
        code = code * 40 + g
    return code


def build_condition_ledger(dates, draws):
    """One row per historical target; only dates strictly before it are used."""
    n = len(draws)
    prefix = np.zeros((n + 1, 40), dtype=np.int32)
    for i, draw in enumerate(draws):
        prefix[i + 1] = prefix[i]
        for value in draw:
            prefix[i + 1, value - 1] += 1

    subset_counts = {k: np.zeros(math.comb(40, k), dtype=np.int32) for k in K_VALUES}
    position_counts = np.zeros((5, 40), dtype=np.int32)
    gap_counts, sum_counts, odd_counts, decade_counts = Counter(), Counter(), Counter(), Counter()
    rows = []
    for i, (target_date, draw) in enumerate(zip(dates, draws)):
        prior_n = i
        prior_num_counts = prefix[i]
        ranked = subset_rank(draw)
        subset_detail = {}
        for k in K_VALUES:
            vals = []
            for subset, idx in zip(itertools.combinations(draw, k), ranked[k]):
                vals.append({"numbers": list(subset), "prior_draw_count": int(subset_counts[k][idx])})
            subset_detail[str(k)] = vals
        pos_detail = [int(position_counts[p, number - 1]) for p, number in enumerate(draw)]
        window_detail = {}
        for w in WINDOWS:
            start = max(0, i - w)
            counts = prefix[i] - prefix[start]
            window_detail[str(w)] = [int(counts[number - 1]) for number in draw]
        gaps = [draw[p + 1] - draw[p] for p in range(4)]
        odd_count = sum(number % 2 for number in draw)
        decade_counts_this = [sum((number - 1) // 10 == decade for number in draw) for decade in range(4)]
        dcode = decade_code(draw)
        gcode = gap_code(draw)
        exact_rank = ranked[5][0]
        rows.append({
            "target_date": target_date,
            "cutoff_date": dates[i - 1] if i else "",
            "prior_draws": prior_n,
            "actual_quintet": " ".join(map(str, draw)),
            "prior_number_counts_for_actual": json.dumps([int(prior_num_counts[number - 1]) for number in draw], separators=(",", ":")),
            "prior_position_counts_for_actual": json.dumps(pos_detail, separators=(",", ":")),
            "prior_frequency_windows_for_actual": json.dumps(window_detail, separators=(",", ":")),
            "gaps": json.dumps(gaps, separators=(",", ":")),
            "prior_gap_pattern_count": int(gap_counts[gcode]),
            "sum": sum(draw),
            "prior_sum_count": int(sum_counts[sum(draw)]),
            "odd_count": odd_count,
            "prior_odd_count_pattern_count": int(odd_counts[odd_count]),
            "decade_profile": json.dumps(decade_counts_this, separators=(",", ":")),
            "prior_decade_profile_count": int(decade_counts[dcode]),
            "prior_exact_quintet_count": int(subset_counts[5][exact_rank]),
            "all_subset_interaction_counts": json.dumps(subset_detail, separators=(",", ":")),
        })
        for k in K_VALUES:
            for idx in ranked[k]:
                subset_counts[k][idx] += 1
        for p, number in enumerate(draw):
            position_counts[p, number - 1] += 1
        gap_counts[gcode] += 1
        sum_counts[sum(draw)] += 1
        odd_counts[odd_count] += 1
        decade_counts[dcode] += 1

    OUT.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with LEDGER.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "rows": rows,
        "prefix_counts": prefix,
        "subset_counts": subset_counts,
        "position_counts": position_counts,
        "gap_counts": gap_counts,
        "sum_counts": sum_counts,
        "odd_counts": odd_counts,
        "decade_counts": decade_counts,
    }


def rank_matrix(values, k, comb_table):
    """Vectorized colex ranks for every k-subset of each candidate quintet."""
    positions = list(itertools.combinations(range(5), k))
    result = np.empty((len(values), len(positions)), dtype=np.int32)
    for j, positions_tuple in enumerate(positions):
        rank = np.zeros(len(values), dtype=np.int32)
        for order, col in enumerate(positions_tuple, start=1):
            rank += comb_table[values[:, col] - 1, order]
        result[:, j] = rank
    return result


def zscore(values):
    mean = float(np.mean(values))
    std = float(np.std(values))
    if not math.isfinite(std) or std < 1e-12:
        return np.zeros_like(values, dtype=np.float64), {"mean": mean, "std": std, "constant": True}
    return (values - mean) / std, {"mean": mean, "std": std, "constant": False}


def top_indices(scores, limit=20):
    n = len(scores)
    threshold = float(np.partition(scores, n - limit)[n - limit])
    above = np.flatnonzero(scores > threshold)
    equal = np.flatnonzero(scores == threshold)
    if len(above) >= limit:
        chosen = above[np.lexsort((above, -scores[above]))[:limit]]
    else:
        chosen = np.concatenate((above, equal[:limit - len(above)]))
        chosen = chosen[np.lexsort((chosen, -scores[chosen]))]
    return chosen[:limit]


def score_next_target(dates, draws, state):
    """Score every possible quintet for every formula in the finite feature grammar."""
    total_prior = len(draws)
    candidates = np.asarray(list(itertools.combinations(range(1, 41), 5)), dtype=np.int16)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise SystemExit(f"EXHAUSTIVE_LAB_BLOCKED: candidate universe {len(candidates)} != {EXPECTED_CANDIDATES}")
    # Binomial coefficient lookup C(x,r), with x in 0..39 and r in 0..5.
    comb_table = np.zeros((40, 6), dtype=np.int32)
    for x in range(40):
        for r in range(6):
            comb_table[x, r] = math.comb(x, r) if x >= r else 0

    raw_families = []
    family_meta = []
    counts = state["subset_counts"]
    for k, family_name in zip(K_VALUES, FAMILY_NAMES[:5]):
        index_matrix = rank_matrix(candidates, k, comb_table)
        alpha = ALPHA
        denominator = total_prior * math.comb(5, k) + alpha * math.comb(40, k)
        log_prob = np.log((counts[k].astype(np.float64) + alpha) / denominator)
        family_score = np.mean(log_prob[index_matrix], axis=1)
        raw_families.append(family_score)
        family_meta.append({"name": family_name, "definition": f"mean smoothed log occurrence probability across all C(5,{k}) subsets of order {k}"})

    # Sorted position-specific number frequency.
    pos_counts = state["position_counts"].astype(np.float64)
    pos_log = np.log((pos_counts + ALPHA) / (total_prior + ALPHA * 40))
    raw_families.append(np.mean(np.column_stack([pos_log[p, candidates[:, p] - 1] for p in range(5)]), axis=1))
    family_meta.append({"name": FAMILY_NAMES[5], "definition": "mean smoothed log frequency of each number at its sorted position"})

    # Gap-pattern likelihood, with all feasible gap vectors represented by base-40 encoding.
    gap_lookup = np.zeros(40 ** 4, dtype=np.int32)
    for code, count in state["gap_counts"].items():
        gap_lookup[code] = count
    gaps = np.diff(candidates.astype(np.int16), axis=1).astype(np.int32)
    gap_codes = (((gaps[:, 0] * 40 + gaps[:, 1]) * 40 + gaps[:, 2]) * 40 + gaps[:, 3])
    feasible_gap_patterns = math.comb(39, 4)
    raw_families.append(np.log((gap_lookup[gap_codes].astype(np.float64) + ALPHA) / (total_prior + ALPHA * feasible_gap_patterns)))
    family_meta.append({"name": FAMILY_NAMES[6], "definition": "smoothed empirical likelihood of the exact four-gap vector"})

    sums = candidates.sum(axis=1).astype(np.int32)
    sum_lookup = np.zeros(191, dtype=np.int32)
    for value, count in state["sum_counts"].items():
        sum_lookup[value] = count
    raw_families.append(np.log((sum_lookup[sums].astype(np.float64) + ALPHA) / (total_prior + ALPHA * 176)))
    family_meta.append({"name": FAMILY_NAMES[7], "definition": "smoothed empirical likelihood of the exact sum (15..190)"})

    odd = (candidates % 2).sum(axis=1).astype(np.int32)
    odd_lookup = np.zeros(6, dtype=np.int32)
    for value, count in state["odd_counts"].items():
        odd_lookup[value] = count
    raw_families.append(np.log((odd_lookup[odd].astype(np.float64) + ALPHA) / (total_prior + ALPHA * 6)))
    family_meta.append({"name": FAMILY_NAMES[8], "definition": "smoothed empirical likelihood of the number of odd values"})

    decade_matrix = np.column_stack([(((candidates - 1) // 10) == d).sum(axis=1) for d in range(4)]).astype(np.int32)
    decade_codes = decade_matrix[:, 0] + 6 * decade_matrix[:, 1] + 36 * decade_matrix[:, 2] + 216 * decade_matrix[:, 3]
    decade_lookup = np.zeros(6 ** 4, dtype=np.int32)
    for code, count in state["decade_counts"].items():
        decade_lookup[code] = count
    raw_families.append(np.log((decade_lookup[decade_codes].astype(np.float64) + ALPHA) / (total_prior + ALPHA * 56)))
    family_meta.append({"name": FAMILY_NAMES[9], "definition": "smoothed empirical likelihood of counts in the four ten-number bands"})

    standardized = []
    normalization = {}
    for name, values in zip(FAMILY_NAMES, raw_families):
        standardized_values, meta = zscore(values)
        standardized.append(standardized_values)
        normalization[name] = meta

    target_date = (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat()
    formula_results = []
    prev_gray = 0
    score = np.zeros(len(candidates), dtype=np.float64)
    for i in range(1, 1 << len(FAMILY_NAMES)):
        gray = i ^ (i >> 1)
        changed = gray ^ prev_gray
        bit = changed.bit_length() - 1
        if gray & changed:
            score += standardized[bit]
        else:
            score -= standardized[bit]
        prev_gray = gray
        selected = [FAMILY_NAMES[j] for j in range(len(FAMILY_NAMES)) if gray & (1 << j)]
        chosen = top_indices(score, 20)
        top = [{"numbers": candidates[idx].astype(int).tolist(), "score": round(float(score[idx]), 8)} for idx in chosen]
        formula_results.append({
            "formula_mask": gray,
            "formula_id": f"F{gray:04d}",
            "features": selected,
            "feature_count": len(selected),
            "top20": top,
        })

    # A consensus ranking is an additional explicitly defined formula, not a selection claim.
    top20_sets = [set(tuple(x["numbers"]) for x in item["top20"]) for item in formula_results]
    candidate_votes = Counter()
    for top in top20_sets:
        candidate_votes.update(top)
    consensus = [{"numbers": list(combo), "top20_votes": votes} for combo, votes in candidate_votes.most_common(100)]
    return {
        "schema_version": "1.0",
        "status": "EXHAUSTIVE_FINITE_GRAMMAR_COMPLETE",
        "source_archive": "data/storico_daily.csv",
        "history_draws": total_prior,
        "history_first_date": dates[0],
        "history_last_date": dates[-1],
        "target_date": target_date,
        "target_cutoff_date": dates[-1],
        "target_note": "Research-only ranking. Does not replace or modify any pre-existing frozen forecast.",
        "candidate_universe_size": len(candidates),
        "candidate_universe_definition": "all sorted distinct 5-number subsets of 1..40",
        "feature_families": family_meta,
        "feature_score_normalization": "Each family score is z-normalized across all 658,008 candidate quintets; every selected family receives equal weight.",
        "formula_count": len(formula_results),
        "formula_grammar": "Every non-empty subset of the 10 declared feature families; all 1,023 formulas enumerated by Gray-code traversal.",
        "smoothing": {"method": "additive", "alpha": ALPHA},
        "family_score_normalization": normalization,
        "formulas": formula_results,
        "consensus_top100_by_formula_top20_votes": consensus,
        "guardrails": [
            "Every historical condition-ledger row uses only draws strictly before its target date.",
            "Every one of the 658,008 possible quintets is scored under each of the 1,023 formulas for the next target.",
            "The grammar is exhaustive only within the declared 10-family finite grammar; the universe of all mathematical formulas is infinite.",
            "Historical formula rankings are exploratory and require chronological walk-forward evaluation; no formula is promoted based on the next-target ranking alone.",
            "The catalog is separate from immutable freeze records and must never overwrite them.",
        ],
    }


def main():
    dates, draws = read_archive()
    state = build_condition_ledger(dates, draws)
    report = score_next_target(dates, draws, state)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    summary = {
        "status": report["status"],
        "history_draws": report["history_draws"],
        "history_last_date": report["history_last_date"],
        "target_date": report["target_date"],
        "candidate_universe_size": report["candidate_universe_size"],
        "formula_count": report["formula_count"],
        "historical_condition_rows": len(state["rows"]),
        "ledger_path": str(LEDGER.relative_to(ROOT)),
        "report_path": str(REPORT.relative_to(ROOT)),
    }
    print("SONAR_EXHAUSTIVE_FORMULA_SUMMARY_BEGIN")
    print(json.dumps(summary, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_EXHAUSTIVE_FORMULA_SUMMARY_END")
    if os.environ.get("SONAR_EMIT_REPORTS") == "1":
        print("SONAR_EXHAUSTIVE_LEDGER_BEGIN")
        with LEDGER.open(encoding="utf-8") as f:
            print(f.read(), end="")
        print("SONAR_EXHAUSTIVE_LEDGER_END")
        print("SONAR_EXHAUSTIVE_CATALOG_BEGIN")
        print(REPORT.read_text(encoding="utf-8"), end="")
        print("SONAR_EXHAUSTIVE_CATALOG_END")


if __name__ == "__main__":
    main()
