#!/usr/bin/env python3
"""Exact chronological rank backtest for every formula in the finite SONAR grammar.

Each target is scored using only earlier draws. For every target, all 658,008
possible quintets are ranked under all 1,023 formula masks; only the actual
quintet's exact deterministic rank is persisted, avoiding a multi-terabyte
long-form candidate dump. This is research evidence, not a prediction guarantee.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from itertools import combinations
from pathlib import Path

import numpy as np

from sonar_exhaustive_formula_lab import (
    ALPHA, EXPECTED_CANDIDATES, FAMILY_NAMES, K_VALUES, colex_rank,
    decade_code, gap_code, rank_matrix, read_archive, subset_rank, zscore,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent" / "exhaustive_formula_walkforward"
FORMULA_COUNT = (1 << len(FAMILY_NAMES)) - 1
RANK_COLUMNS = [f"rank_mask_{mask:04d}" for mask in range(1, FORMULA_COUNT + 1)]


def lex_rank(values):
    """Zero-based rank in itertools.combinations(range(1, 41), 5) order."""
    rank = 0
    previous = 1
    for position, value in enumerate(values):
        for candidate in range(previous, value):
            rank += math.comb(40 - candidate, 4 - position)
        previous = value + 1
    return rank


def empty_state():
    return {
        "subset_counts": {k: np.zeros(math.comb(40, k), dtype=np.int32) for k in K_VALUES},
        "position_counts": np.zeros((5, 40), dtype=np.int32),
        "gap_lookup": np.zeros(40 ** 4, dtype=np.int32),
        "sum_lookup": np.zeros(191, dtype=np.int32),
        "odd_lookup": np.zeros(6, dtype=np.int32),
        "decade_lookup": np.zeros(6 ** 4, dtype=np.int32),
        "gap_counts": {},
        "sum_counts": {},
        "odd_counts": {},
        "decade_counts": {},
    }


def add_draw(state, draw):
    ranked = subset_rank(draw)
    for k in K_VALUES:
        state["subset_counts"][k][ranked[k]] += 1
    for position, number in enumerate(draw):
        state["position_counts"][position, number - 1] += 1
    gcode = gap_code(draw)
    scode = sum(draw)
    ocode = sum(number % 2 for number in draw)
    dcode = decade_code(draw)
    state["gap_lookup"][gcode] += 1
    state["sum_lookup"][scode] += 1
    state["odd_lookup"][ocode] += 1
    state["decade_lookup"][dcode] += 1
    state["gap_counts"][gcode] = state["gap_counts"].get(gcode, 0) + 1
    state["sum_counts"][scode] = state["sum_counts"].get(scode, 0) + 1
    state["odd_counts"][ocode] = state["odd_counts"].get(ocode, 0) + 1
    state["decade_counts"][dcode] = state["decade_counts"].get(dcode, 0) + 1


def build_candidate_space():
    candidates = np.asarray(list(combinations(range(1, 41), 5)), dtype=np.int16)
    if len(candidates) != EXPECTED_CANDIDATES:
        raise SystemExit(f"WALKFORWARD_BLOCKED: candidate count {len(candidates)}")
    comb_table = np.zeros((40, 6), dtype=np.int32)
    for value in range(40):
        for order in range(6):
            comb_table[value, order] = math.comb(value, order) if value >= order else 0
    indices = {k: rank_matrix(candidates, k, comb_table) for k in K_VALUES}
    gap_matrix = np.diff(candidates.astype(np.int16), axis=1).astype(np.int32)
    gap_codes = (((gap_matrix[:, 0] * 40 + gap_matrix[:, 1]) * 40 + gap_matrix[:, 2]) * 40 + gap_matrix[:, 3])
    sums = candidates.sum(axis=1).astype(np.int32)
    odd_counts = (candidates % 2).sum(axis=1).astype(np.int32)
    decade_matrix = np.column_stack([(((candidates - 1) // 10) == decade).sum(axis=1) for decade in range(4)]).astype(np.int32)
    decade_codes = decade_matrix[:, 0] + 6 * decade_matrix[:, 1] + 36 * decade_matrix[:, 2] + 216 * decade_matrix[:, 3]
    return candidates, indices, gap_codes, sums, odd_counts, decade_codes


def standardized_family_scores(prior_n, state, indices, gap_codes, sums, odd_values, decade_codes):
    candidates_count = EXPECTED_CANDIDATES
    raw = []
    subset_counts = state["subset_counts"]
    for k in K_VALUES:
        denominator = prior_n * math.comb(5, k) + ALPHA * math.comb(40, k)
        log_prob = np.log((subset_counts[k].astype(np.float64) + ALPHA) / denominator)
        raw.append(np.mean(log_prob[indices[k]], axis=1))

    position_log = np.log((state["position_counts"].astype(np.float64) + ALPHA) / (prior_n + ALPHA * 40))
    # Rebuild candidate numbers in sorted-position order from rank-matrix source.
    # The position feature is number-specific at each of the five sorted positions.
    # Candidate quintets are the lexicographically ordered complete universe.
    candidates = np.asarray(list(combinations(range(1, 41), 5)), dtype=np.int16)
    raw.append(np.mean(np.column_stack([position_log[p, candidates[:, p] - 1] for p in range(5)]), axis=1))

    feasible_gap_patterns = math.comb(39, 4)
    raw.append(np.log((state["gap_lookup"][gap_codes].astype(np.float64) + ALPHA) / (prior_n + ALPHA * feasible_gap_patterns)))
    raw.append(np.log((state["sum_lookup"][sums].astype(np.float64) + ALPHA) / (prior_n + ALPHA * 176)))
    raw.append(np.log((state["odd_lookup"][odd_values].astype(np.float64) + ALPHA) / (prior_n + ALPHA * 6)))
    raw.append(np.log((state["decade_lookup"][decade_codes].astype(np.float64) + ALPHA) / (prior_n + ALPHA * 56)))
    if len(raw) != len(FAMILY_NAMES):
        raise SystemExit(f"WALKFORWARD_BLOCKED: feature family count {len(raw)}")
    standardized = [zscore(values)[0] for values in raw]
    return standardized


def ranks_for_actual(standardized, actual_lex_index, candidate_indices):
    score = np.zeros(EXPECTED_CANDIDATES, dtype=np.float64)
    ranked_scores = np.empty(EXPECTED_CANDIDATES, dtype=np.float64)
    ranks = np.zeros(FORMULA_COUNT, dtype=np.int32)
    previous_gray = 0
    for i in range(1, 1 << len(FAMILY_NAMES)):
        gray = i ^ (i >> 1)
        changed = gray ^ previous_gray
        bit = changed.bit_length() - 1
        if gray & changed:
            score += standardized[bit]
        else:
            score -= standardized[bit]
        np.round(score, 10, out=ranked_scores)
        actual_score = ranked_scores[actual_lex_index]
        greater = int(np.count_nonzero(ranked_scores > actual_score))
        equal_indices = np.flatnonzero(ranked_scores == actual_score)
        equal_before = int(np.searchsorted(equal_indices, actual_lex_index, side="left"))
        ranks[gray - 1] = 1 + greater + equal_before
        previous_gray = gray
    if np.any(ranks < 1) or np.any(ranks > EXPECTED_CANDIDATES):
        raise SystemExit("WALKFORWARD_BLOCKED: rank outside complete candidate universe")
    return ranks


def run_batch(start_index, count):
    dates, draws = read_archive()
    total = len(draws)
    if start_index < 0 or start_index >= total:
        raise SystemExit(f"WALKFORWARD_BLOCKED: invalid start index {start_index} for {total} targets")
    end_index = min(total, start_index + count)
    candidates, indices, gap_codes, sums, odd_values, decade_codes = build_candidate_space()
    candidate_indices = np.arange(len(candidates), dtype=np.int32)
    state = empty_state()
    for draw in draws[:start_index]:
        add_draw(state, draw)

    OUT.mkdir(parents=True, exist_ok=True)
    output = OUT / f"part_{start_index:04d}_{end_index:04d}.csv"
    fieldnames = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + RANK_COLUMNS
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for i in range(start_index, end_index):
            draw = draws[i]
            row = {
                "target_date": dates[i],
                "cutoff_date": dates[i - 1] if i else "",
                "prior_draws": i,
                "actual_quintet": " ".join(map(str, draw)),
                "status": "INSUFFICIENT_HISTORY" if i == 0 else "SCORED",
            }
            if i == 0:
                row.update({column: "" for column in RANK_COLUMNS})
            else:
                standardized = standardized_family_scores(i, state, indices, gap_codes, sums, odd_values, decade_codes)
                actual_index = lex_rank(draw)
                if tuple(candidates[actual_index].tolist()) != tuple(draw):
                    raise SystemExit(f"WALKFORWARD_BLOCKED: lex rank mismatch at {dates[i]}")
                ranks = ranks_for_actual(standardized, actual_index, candidate_indices)
                row.update({f"rank_mask_{mask:04d}": int(ranks[mask - 1]) for mask in range(1, FORMULA_COUNT + 1)})
            writer.writerow(row)
            add_draw(state, draw)

    summary = {
        "status": "BATCH_COMPLETE",
        "batch_start_index": start_index,
        "batch_end_index_exclusive": end_index,
        "targets_in_batch": end_index - start_index,
        "scored_targets": max(0, end_index - max(start_index, 1)),
        "history_draws": total,
        "candidate_universe_size": EXPECTED_CANDIDATES,
        "formula_count_per_target": FORMULA_COUNT,
        "first_target_date": dates[start_index],
        "last_target_date": dates[end_index - 1],
        "output_path": str(output.relative_to(ROOT)),
    }
    print("SONAR_EXHAUSTIVE_WALKFORWARD_SUMMARY_BEGIN")
    print(json.dumps(summary, separators=(",", ":")))
    print("SONAR_EXHAUSTIVE_WALKFORWARD_SUMMARY_END")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-index", type=int, required=True, help="Zero-based target row start, inclusive")
    parser.add_argument("--count", type=int, default=100, help="Maximum number of targets in this batch")
    args = parser.parse_args()
    if args.count < 1 or args.count > 100:
        raise SystemExit("--count must be between 1 and 100")
    run_batch(args.start_index, args.count)


if __name__ == "__main__":
    main()
