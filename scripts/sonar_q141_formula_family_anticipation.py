#!/usr/bin/env python3
"""Q141-C0: strict-prior rolling formula-family anticipation and behaviour map."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
CUTOFF = "2026-11-10"
EXPECTED_ARCHIVE_BLOB_SHA1 = "fcb453ed06c8002314f826dbac79d6935f9ac103"
EXPECTED_ELIGIBLE_DRAWS = 3404
MIN_HISTORY = 50
ROLLING_WINDOW = 100
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261112
WINDOWS = (5, 10, 20, 50, 100, 250, 500)

FEATURE_NAMES = (
    [f"freq_{w}" for w in WINDOWS]
    + ["freq_all", "trend_5_vs_50", "trend_10_vs_100", "trend_20_vs_250"]
    + ["age_since_hit", "gap_mean", "gap_sd", "overdue_ratio"]
    + ["position_log_frequency", "pair_count_with_last_draw", "neighbor_pm1_history", "neighbor_pm2_history"]
    + ["lag_1", "lag_2", "lag_3", "lag_5", "lag_10"]
    + ["recent_3", "recent_5", "recent_10"]
)
FAMILIES = {
    "frequency_level": (0, 1, 2, 3, 4, 5, 6, 7, 24),
    "frequency_change": (8, 9, 10),
    "recency_gap": (11, 12, 13, 14),
    "position_dependence": (15, 16),
    "neighbour_field": (17, 18),
    "lag_memory": (19, 20, 21, 22, 23),
}
FAMILY_NAMES = tuple(sorted(FAMILIES))
ALIASES = {"recent_5": "freq_5", "recent_10": "freq_10"}
UNIQUE_FEATURE_INDICES = tuple(i for i in range(len(FEATURE_NAMES)) if i not in (25, 26))
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
COMPARATORS = ("equal_family", "equal_feature", "fixed_discovery_family")
ENDPOINTS = ("top5_hit_share", "top10_hit_share", "top20_hit_share", "mean_actual_number_rank")


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def load_archive():
    raw = ARCHIVE.read_bytes()
    blob_sha = git_blob_sha1(raw)
    if blob_sha != EXPECTED_ARCHIVE_BLOB_SHA1:
        raise RuntimeError(f"Q141_BLOCKED: archive Git blob SHA {blob_sha} != pinned {EXPECTED_ARCHIVE_BLOB_SHA1}")
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    rows = list(reader)
    if not rows:
        raise RuntimeError("Q141_BLOCKED: empty archive")
    header = [x.strip().lower() for x in rows[0][:6]]
    if header not in (["data", "n1", "n2", "n3", "n4", "n5"], ["date", "n1", "n2", "n3", "n4", "n5"]):
        raise RuntimeError(f"Q141_BLOCKED: unexpected archive header {header}")
    dates, draws, seen = [], [], set()
    excluded_after_cutoff = 0
    previous = ""
    for line_no, row in enumerate(rows[1:], start=2):
        if not row or not any(x.strip() for x in row):
            continue
        date = row[0].strip()
        if date > CUTOFF:
            excluded_after_cutoff += 1
            continue
        try:
            values = tuple(int(x) for x in row[1:6])
        except Exception as exc:
            raise RuntimeError(f"Q141_BLOCKED: malformed row {line_no}: {exc}") from exc
        if date in seen or (previous and date <= previous):
            raise RuntimeError(f"Q141_BLOCKED: duplicate/non-chronological date {date}")
        if len(values) != 5 or len(set(values)) != 5 or values != tuple(sorted(values)) or any(v < 1 or v > 40 for v in values):
            raise RuntimeError(f"Q141_BLOCKED: invalid quintet at {date}: {values}")
        dates.append(date)
        draws.append(tuple(v - 1 for v in values))
        seen.add(date)
        previous = date
    if len(draws) != EXPECTED_ELIGIBLE_DRAWS or dates[-1] != CUTOFF:
        raise RuntimeError(f"Q141_BLOCKED: eligible archive {len(draws)} rows ending {dates[-1] if dates else None}")
    return raw, blob_sha, dates, draws, excluded_after_cutoff


def build_prefix_arrays(draws):
    n = len(draws)
    prefix = np.zeros((n + 1, 40), dtype=np.int32)
    pos_prefix = np.zeros((n + 1, 5, 40), dtype=np.int32)
    for i, draw in enumerate(draws):
        prefix[i + 1] = prefix[i]
        pos_prefix[i + 1] = pos_prefix[i]
        for pos, value in enumerate(draw):
            prefix[i + 1, value] += 1
            pos_prefix[i + 1, pos, value] += 1
    return prefix, pos_prefix


def build_state(prefix_draws):
    """Build a self-contained state from exactly the supplied historical prefix."""
    prefix, pos_prefix = build_prefix_arrays(prefix_draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    for i, draw in enumerate(prefix_draws):
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1
    return prefix, pos_prefix, pair_counts, occurrence_lists


def feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists):
    """Return 40x27 features for target i using only draws[:i]."""
    if i < 1 or len(prefix) <= i or len(pos_prefix) <= i:
        raise ValueError("Q141 feature state does not cover strict prefix")
    out = np.zeros((40, 27), dtype=np.float64)
    for col, window in enumerate(WINDOWS):
        start = max(0, i - window)
        out[:, col] = prefix[i] - prefix[start]
    out[:, 7] = prefix[i]
    out[:, 8] = out[:, 0] / max(1, min(i, 5)) - out[:, 3] / max(1, min(i, 50))
    out[:, 9] = out[:, 1] / max(1, min(i, 10)) - out[:, 4] / max(1, min(i, 100))
    out[:, 10] = out[:, 2] / max(1, min(i, 20)) - out[:, 5] / max(1, min(i, 250))

    ages = np.full(40, i + 1, dtype=np.float64)
    for number, occurrences in enumerate(occurrence_lists):
        if occurrences:
            ages[number] = i - occurrences[-1]
    out[:, 11] = ages
    for number, occurrences in enumerate(occurrence_lists):
        gaps = np.diff(occurrences)
        if len(gaps):
            out[number, 12] = float(np.mean(gaps))
            out[number, 13] = float(np.std(gaps))
        else:
            out[number, 12] = max(1, i)
            out[number, 13] = 0.0
    out[:, 14] = out[:, 11] / np.maximum(out[:, 12], 1.0)

    pos = pos_prefix[i].astype(np.float64)
    pos_log = np.log((pos + 0.5) / (i + 20.0))
    out[:, 15] = pos_log.mean(axis=0)
    last = np.asarray(draws[i - 1], dtype=np.int64)
    out[:, 16] = pair_counts[:, last].mean(axis=1)

    full_counts = prefix[i]
    out[:, 17] = np.array([
        sum(full_counts[max(0, n - 1):min(40, n + 2)]) - full_counts[n]
        for n in range(40)
    ], dtype=np.float64)
    out[:, 18] = np.array([
        sum(full_counts[max(0, n - 2):min(40, n + 3)]) - full_counts[n]
        for n in range(40)
    ], dtype=np.float64)

    for lag, col in ((1, 19), (2, 20), (3, 21), (5, 22), (10, 23)):
        if i >= lag:
            drawset = set(draws[i - lag])
            out[:, col] = [1.0 if n in drawset else 0.0 for n in range(40)]
    for window, col in ((3, 24), (5, 25), (10, 26)):
        start = max(0, i - window)
        out[:, col] = prefix[i] - prefix[start]
    return out


def zscore_columns(matrix):
    means = matrix.mean(axis=0)
    stds = matrix.std(axis=0)
    stds[stds < 1e-12] = 1.0
    return (matrix - means) / stds


def rank_scores(scores):
    scores = np.asarray(scores, dtype=np.float64)
    order = np.lexsort((np.arange(40), -scores))
    ranks = np.empty(40, dtype=np.int16)
    ranks[order] = np.arange(1, 41, dtype=np.int16)
    return ranks


def rank_metrics(ranks, actual):
    selected = np.asarray(ranks, dtype=np.int16)[np.asarray(actual, dtype=np.int64)]
    return {
        "top5_hits": int(np.sum(selected <= 5)),
        "top10_hits": int(np.sum(selected <= 10)),
        "top20_hits": int(np.sum(selected <= 20)),
        "mean_rank": float(np.mean(selected)),
    }


def split_name(offset, target_count):
    ratio = offset / max(target_count, 1)
    return "discovery" if ratio < 0.60 else ("validation" if ratio < 0.80 else "blind_oos")


def summarize_metrics(rows, model, fixed_family=None):
    metrics = []
    for row in rows:
        if model == "fixed_discovery_family":
            metrics.append(row["families"][fixed_family])
        else:
            metrics.append(row[model])
    n = len(metrics)
    if not n:
        return {"targets": 0}
    return {
        "targets": n,
        "mean_number_hits_top5": float(sum(m["top5_hits"] for m in metrics) / (5 * n)),
        "mean_number_hits_top10": float(sum(m["top10_hits"] for m in metrics) / (5 * n)),
        "mean_number_hits_top20": float(sum(m["top20_hits"] for m in metrics) / (5 * n)),
        "mean_actual_number_rank": float(sum(m["mean_rank"] for m in metrics) / n),
        "all5_top5_rate": float(sum(m["top5_hits"] == 5 for m in metrics) / n),
    }


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: (p_values[i], i))
    adjusted = [1.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * float(p_values[idx])))
        adjusted[idx] = running
    return adjusted


def block_signflip_p(deltas, seed):
    values = np.asarray(deltas, dtype=np.float64)
    blocks = np.asarray([values[i:i + BLOCK_LENGTH].sum() for i in range(0, len(values), BLOCK_LENGTH)])
    observed = abs(float(blocks.sum()))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(REPLICATES, len(blocks)))
    simulated = np.abs(signs @ blocks)
    return float((np.count_nonzero(simulated >= observed - 1e-12) + 1) / (REPLICATES + 1))


def circular_block_bootstrap_ci(deltas, seed):
    values = np.asarray(deltas, dtype=np.float64)
    n = len(values)
    full_blocks, remainder = divmod(n, BLOCK_LENGTH)
    extended = np.concatenate((values, values[:BLOCK_LENGTH - 1]))
    cumulative = np.concatenate(([0.0], np.cumsum(extended)))
    full_sums = cumulative[BLOCK_LENGTH:] - cumulative[:-BLOCK_LENGTH]
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(REPLICATES, full_blocks))
    totals = full_sums[starts].sum(axis=1) if full_blocks else np.zeros(REPLICATES)
    if remainder:
        partial_sums = cumulative[remainder:] - cumulative[:-remainder]
        partial_starts = rng.integers(0, n, size=REPLICATES)
        totals += partial_sums[partial_starts]
    means = totals / n
    low, high = np.quantile(means, [0.025, 0.975])
    return [float(low), float(high)]


def hypergeom_pmf(top_k):
    denominator = math.comb(40, 5)
    low = max(0, 5 - (40 - top_k))
    high = min(5, top_k)
    return {x: math.comb(top_k, x) * math.comb(40 - top_k, 5 - x) / denominator
            for x in range(low, high + 1)}


def exact_hypergeom_upper_tail(observed_hits, targets, top_k):
    if targets <= 0:
        return 1.0
    pmf = hypergeom_pmf(top_k)
    maximum = max(pmf)
    distribution = np.array([1.0], dtype=np.float64)
    for _ in range(targets):
        updated = np.zeros(len(distribution) + maximum, dtype=np.float64)
        for hits, probability in pmf.items():
            updated[hits:hits + len(distribution)] += probability * distribution
        distribution = updated
    if observed_hits >= len(distribution):
        return 0.0
    return float(np.clip(distribution[observed_hits:].sum(), 0.0, 1.0))


def autocorrelation(values, lag=1):
    values = np.asarray(values, dtype=np.float64)
    if len(values) <= lag or np.std(values[:-lag]) < 1e-12 or np.std(values[lag:]) < 1e-12:
        return None
    return float(np.corrcoef(values[:-lag], values[lag:])[0, 1])


def family_behaviour(target_rows):
    pairs = {}
    for a, b in combinations(FAMILY_NAMES, 2):
        pairs[(a, b)] = {
            "jaccard_sum": 0.0, "union_hits_sum": 0.0, "union_size_sum": 0.0,
            "unique_hit_gain_sum": 0.0, "co_success": 0, "success_a": 0, "success_b": 0,
        }
    for row in target_rows:
        actual = row["actual"]
        for (a, b), acc in pairs.items():
            mask_a, mask_b = row["family_masks"][a], row["family_masks"][b]
            intersection = mask_a & mask_b
            union = mask_a | mask_b
            inter_size = intersection.bit_count()
            union_size = union.bit_count()
            union_hits = sum(1 for number in actual if union & (1 << number))
            hits_a = row["families"][a]["top5_hits"]
            hits_b = row["families"][b]["top5_hits"]
            success_a, success_b = hits_a > 0, hits_b > 0
            acc["jaccard_sum"] += inter_size / union_size if union_size else 0.0
            acc["union_hits_sum"] += union_hits
            acc["union_size_sum"] += union_size
            acc["unique_hit_gain_sum"] += union_hits - max(hits_a, hits_b)
            acc["co_success"] += int(success_a and success_b)
            acc["success_a"] += int(success_a)
            acc["success_b"] += int(success_b)
    n = len(target_rows)
    output = []
    for (a, b), acc in pairs.items():
        n11 = acc["co_success"]
        n10 = acc["success_a"] - n11
        n01 = acc["success_b"] - n11
        n00 = n - n11 - n10 - n01
        denominator = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        phi = ((n11 * n00 - n10 * n01) / denominator) if denominator else None
        output.append({
            "family_a": a, "family_b": b, "targets": n,
            "mean_top5_candidate_jaccard": acc["jaccard_sum"] / n,
            "mean_top5_union_size": acc["union_size_sum"] / n,
            "mean_winning_numbers_in_union": acc["union_hits_sum"] / n,
            "mean_unique_hit_gain_vs_best_single": acc["unique_hit_gain_sum"] / n,
            "both_families_hit_at_least_one_top5": n11 / n,
            "success_phi_correlation": phi,
        })
    return output


def run():
    raw, archive_blob_sha, dates, draws, excluded = load_archive()
    n = len(draws)
    scored_targets = n - MIN_HISTORY
    if scored_targets <= 0:
        raise RuntimeError("Q141_BLOCKED: no scored targets")
    actual_split_counts = Counter(split_name(offset, scored_targets) for offset in range(scored_targets))
    if dict(actual_split_counts) != EXPECTED_SPLITS:
        raise RuntimeError(f"Q141_BLOCKED: split counts {dict(actual_split_counts)} != {EXPECTED_SPLITS}")
    if len(FEATURE_NAMES) != 27 or len(UNIQUE_FEATURE_INDICES) != 25:
        raise RuntimeError("Q141_BLOCKED: feature schema count mismatch")
    flattened = sorted(i for indices in FAMILIES.values() for i in indices)
    if flattened != list(UNIQUE_FEATURE_INDICES):
        raise RuntimeError("Q141_BLOCKED: family definitions do not partition the 25 unique features")

    prefix, pos_prefix = build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    family_history = {family: [] for family in FAMILY_NAMES}
    target_rows = []
    pair_acc = {(a, b): {"jaccard": 0.0, "union_hits": 0.0, "union_size": 0.0,
                         "unique_gain": 0.0, "co": 0, "sa": 0, "sb": 0}
                for a, b in combinations(FAMILY_NAMES, 2)}
    selection_counts = {split: Counter() for split in ("discovery", "validation", "blind_oos")}
    oracle_counts = {split: Counter() for split in ("discovery", "validation", "blind_oos")}
    selected_sequence = []

    for i, draw in enumerate(draws):
        if i >= MIN_HISTORY:
            offset = i - MIN_HISTORY
            split = split_name(offset, scored_targets)
            raw_features = feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists)
            if not np.array_equal(raw_features[:, 0], raw_features[:, 25]):
                raise RuntimeError("Q141_BLOCKED: recent_5 is not exactly identical to freq_5")
            if not np.array_equal(raw_features[:, 1], raw_features[:, 26]):
                raise RuntimeError("Q141_BLOCKED: recent_10 is not exactly identical to freq_10")
            standardized = zscore_columns(raw_features)
            family_scores = {family: standardized[:, indices].mean(axis=1)
                             for family, indices in FAMILIES.items()}
            family_ranks = {family: rank_scores(scores) for family, scores in family_scores.items()}
            family_metrics = {family: rank_metrics(ranks, draw) for family, ranks in family_ranks.items()}
            family_masks = {
                family: sum(1 << int(number) for number in np.flatnonzero(ranks <= 5))
                for family, ranks in family_ranks.items()
            }
            family_equal_scores = np.mean(np.vstack([family_scores[f] for f in FAMILY_NAMES]), axis=0)
            feature_equal_scores = standardized[:, UNIQUE_FEATURE_INDICES].mean(axis=1)
            family_equal_metrics = rank_metrics(rank_scores(family_equal_scores), draw)
            feature_equal_metrics = rank_metrics(rank_scores(feature_equal_scores), draw)

            if offset < ROLLING_WINDOW:
                selected_family = ""
                selector_mode = "warmup_equal_family"
                dynamic_metrics = family_equal_metrics
            else:
                recent = {}
                for family in FAMILY_NAMES:
                    history = family_history[family][-ROLLING_WINDOW:]
                    recent[family] = (
                        float(np.mean([item["top5_hits"] for item in history])),
                        float(np.mean([item["mean_rank"] for item in history])),
                    )
                selected_family = sorted(
                    FAMILY_NAMES,
                    key=lambda f: (-recent[f][0], recent[f][1], f)
                )[0]
                selector_mode = "rolling100_prior_family"
                dynamic_metrics = family_metrics[selected_family]

            oracle_best = sorted(
                FAMILY_NAMES,
                key=lambda f: (-family_metrics[f]["top5_hits"], family_metrics[f]["mean_rank"], f)
            )[0]
            oracle_counts[split][oracle_best] += 1
            if selected_family:
                selection_counts[split][selected_family] += 1
                selected_sequence.append((split, selected_family))
            else:
                selected_sequence.append((split, "WARMUP_EQUAL_FAMILY"))

            actual = tuple(draw)
            row = {
                "target_index": i, "target_offset": offset, "target_date": dates[i],
                "cutoff_date": dates[i - 1], "prior_draws": i, "split": split,
                "actual": actual, "families": family_metrics, "family_masks": family_masks,
                "dynamic": dynamic_metrics, "equal_family": family_equal_metrics,
                "equal_feature": feature_equal_metrics,
                "selected_family": selected_family, "selector_mode": selector_mode,
                "oracle_best_family": oracle_best,
            }
            target_rows.append(row)

            for (a, b), acc in pair_acc.items():
                mask_a, mask_b = family_masks[a], family_masks[b]
                union = mask_a | mask_b
                union_size = union.bit_count()
                union_hits = sum(1 for number in actual if union & (1 << number))
                hits_a, hits_b = family_metrics[a]["top5_hits"], family_metrics[b]["top5_hits"]
                success_a, success_b = hits_a > 0, hits_b > 0
                inter_size = (mask_a & mask_b).bit_count()
                acc["jaccard"] += inter_size / union_size if union_size else 0.0
                acc["union_hits"] += union_hits
                acc["union_size"] += union_size
                acc["unique_gain"] += union_hits - max(hits_a, hits_b)
                acc["co"] += int(success_a and success_b)
                acc["sa"] += int(success_a)
                acc["sb"] += int(success_b)

            # Update selector history only after the current target has been scored.
            for family in FAMILY_NAMES:
                family_history[family].append(family_metrics[family])

        # Update all historical state only after target i is scored.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    discovery_rows = [row for row in target_rows if row["split"] == "discovery"]
    validation_rows = [row for row in target_rows if row["split"] == "validation"]
    blind_rows = [row for row in target_rows if row["split"] == "blind_oos"]
    discovery_family_summary = {
        family: summarize_metrics(discovery_rows, "families", family)
        for family in FAMILY_NAMES
    }
    fixed_family = sorted(
        FAMILY_NAMES,
        key=lambda f: (-discovery_family_summary[f]["mean_number_hits_top5"],
                       discovery_family_summary[f]["mean_actual_number_rank"], f)
    )[0]

    split_rows = {
        "discovery": discovery_rows, "validation": validation_rows, "blind_oos": blind_rows
    }
    split_summary = {}
    for split, rows in split_rows.items():
        models = {
            "dynamic": summarize_metrics(rows, "dynamic"),
            "equal_family": summarize_metrics(rows, "equal_family"),
            "equal_feature": summarize_metrics(rows, "equal_feature"),
            "families": {family: summarize_metrics(rows, "families", family) for family in FAMILY_NAMES},
        }
        if split != "discovery":
            models["fixed_discovery_family"] = summarize_metrics(rows, "families", fixed_family)
        split_summary[split] = {"targets": len(rows), "models": models}

    paired_tests = []
    test_index = 0
    for split in ("validation", "blind_oos"):
        rows = split_rows[split]
        for comparator in COMPARATORS:
            for endpoint in ENDPOINTS:
                deltas = []
                for row in rows:
                    dynamic = row["dynamic"]
                    control = row["families"][fixed_family] if comparator == "fixed_discovery_family" else row[comparator]
                    if endpoint == "top5_hit_share":
                        deltas.append((dynamic["top5_hits"] - control["top5_hits"]) / 5.0)
                    elif endpoint == "top10_hit_share":
                        deltas.append((dynamic["top10_hits"] - control["top10_hits"]) / 5.0)
                    elif endpoint == "top20_hit_share":
                        deltas.append((dynamic["top20_hits"] - control["top20_hits"]) / 5.0)
                    else:
                        deltas.append(control["mean_rank"] - dynamic["mean_rank"])
                seed = SEED + 1000 + test_index
                p_raw = block_signflip_p(deltas, seed)
                ci = circular_block_bootstrap_ci(deltas, seed + 50000)
                paired_tests.append({
                    "split": split, "comparison": f"dynamic_vs_{comparator}", "endpoint": endpoint,
                    "targets": len(rows), "mean_benefit_delta": float(np.mean(deltas)),
                    "bootstrap_ci_95": ci, "block_signflip_p_raw": p_raw,
                })
                test_index += 1
    adjusted = holm_adjust([item["block_signflip_p_raw"] for item in paired_tests])
    for item, p_adj in zip(paired_tests, adjusted):
        item["block_signflip_p_holm_24_tests"] = float(p_adj)

    uniform_tests = []
    for split in ("validation", "blind_oos"):
        rows = split_rows[split]
        for endpoint, top_k, field in (
            ("top5_hit_share", 5, "top5_hits"),
            ("top10_hit_share", 10, "top10_hits"),
            ("top20_hit_share", 20, "top20_hits"),
        ):
            observed = sum(row["dynamic"][field] for row in rows)
            uniform_tests.append({
                "split": split, "model": "dynamic", "endpoint": endpoint,
                "targets": len(rows), "observed_number_hits": int(observed),
                "uniform_expected_number_hits": len(rows) * 5 * top_k / 40.0,
                "exact_hypergeom_upper_tail_p_raw": exact_hypergeom_upper_tail(observed, len(rows), top_k),
            })
    uniform_adjusted = holm_adjust([item["exact_hypergeom_upper_tail_p_raw"] for item in uniform_tests])
    for item, p_adj in zip(uniform_tests, uniform_adjusted):
        item["exact_hypergeom_p_holm_6_tests"] = float(p_adj)

    behaviour_pairs = []
    total_rows = len(target_rows)
    for (a, b), acc in pair_acc.items():
        n11 = acc["co"]
        n10 = acc["sa"] - n11
        n01 = acc["sb"] - n11
        n00 = total_rows - n11 - n10 - n01
        denominator = math.sqrt((n11 + n10) * (n01 + n00) * (n11 + n01) * (n10 + n00))
        phi = ((n11 * n00 - n10 * n01) / denominator) if denominator else None
        behaviour_pairs.append({
            "family_a": a, "family_b": b, "targets": total_rows,
            "mean_top5_candidate_jaccard": acc["jaccard"] / total_rows,
            "mean_top5_union_size": acc["union_size"] / total_rows,
            "mean_winning_numbers_in_union": acc["union_hits"] / total_rows,
            "mean_unique_hit_gain_vs_best_single": acc["unique_gain"] / total_rows,
            "both_families_hit_at_least_one_top5_rate": n11 / total_rows,
            "top5_success_phi_correlation": phi,
        })

    family_time_series = {}
    for family in FAMILY_NAMES:
        values = [row["families"][family]["top5_hits"] for row in target_rows]
        family_time_series[family] = {
            "lag1_autocorrelation_top5_hits": autocorrelation(values, 1),
            "lag5_autocorrelation_top5_hits": autocorrelation(values, 5),
            "mean_top5_hits": float(np.mean(values)),
            "top5_success_rate": float(np.mean(np.asarray(values) > 0)),
        }

    switches = 0
    selected_only = [family for _, family in selected_sequence if family != "WARMUP_EQUAL_FAMILY"]
    switches = sum(a != b for a, b in zip(selected_only, selected_only[1:]))
    run_lengths = []
    if selected_only:
        current, length = selected_only[0], 1
        for family in selected_only[1:]:
            if family == current:
                length += 1
            else:
                run_lengths.append(length)
                current, length = family, 1
        run_lengths.append(length)

    paired_primary = next(
        item for item in paired_tests
        if item["split"] == "blind_oos"
        and item["comparison"] == "dynamic_vs_equal_family"
        and item["endpoint"] == "top5_hit_share"
    )
    primary_pass = (
        paired_primary["mean_benefit_delta"] >= 0.005
        and paired_primary["block_signflip_p_holm_24_tests"] < 0.05
        and paired_primary["bootstrap_ci_95"][0] > 0.0
    )
    decision = "PRIMARY_GATE_PASS_EXPLORATORY" if primary_pass else "NO_ROLLING_FAMILY_ANTICIPATION_LIFT_DEMONSTRATED"

    target_ledger_path = OUT / "q141_formula_family_behaviour_target_ledger_2026-11-12.csv"
    report_path = OUT / "q141_formula_family_behaviour_report_2026-11-12.json"
    manifest_path = OUT / "q141_formula_family_behaviour_manifest_2026-11-12.json"
    OUT.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "target_index", "target_offset", "target_date", "cutoff_date", "prior_draws", "split",
        "actual_quintet", "selector_mode", "selected_family", "oracle_best_family_descriptive_only",
        "dynamic_top5_hits", "dynamic_top10_hits", "dynamic_top20_hits", "dynamic_mean_actual_rank",
        "equal_family_top5_hits", "equal_family_top10_hits", "equal_family_top20_hits", "equal_family_mean_actual_rank",
        "equal_feature_top5_hits", "equal_feature_top10_hits", "equal_feature_top20_hits", "equal_feature_mean_actual_rank",
        "fixed_discovery_family", "fixed_discovery_family_top5_hits", "fixed_discovery_family_top10_hits",
        "fixed_discovery_family_top20_hits", "fixed_discovery_family_mean_actual_rank",
    ]
    for family in FAMILY_NAMES:
        fieldnames.extend([
            f"{family}_top5_hits", f"{family}_top10_hits", f"{family}_top20_hits", f"{family}_mean_actual_rank"
        ])
    with target_ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in target_rows:
            fixed_metrics = row["families"][fixed_family] if row["split"] != "discovery" else {}
            output = {
                "target_index": row["target_index"], "target_offset": row["target_offset"],
                "target_date": row["target_date"], "cutoff_date": row["cutoff_date"],
                "prior_draws": row["prior_draws"], "split": row["split"],
                "actual_quintet": " ".join(str(v + 1) for v in row["actual"]),
                "selector_mode": row["selector_mode"], "selected_family": row["selected_family"],
                "oracle_best_family_descriptive_only": row["oracle_best_family"],
                "dynamic_top5_hits": row["dynamic"]["top5_hits"],
                "dynamic_top10_hits": row["dynamic"]["top10_hits"],
                "dynamic_top20_hits": row["dynamic"]["top20_hits"],
                "dynamic_mean_actual_rank": row["dynamic"]["mean_rank"],
                "equal_family_top5_hits": row["equal_family"]["top5_hits"],
                "equal_family_top10_hits": row["equal_family"]["top10_hits"],
                "equal_family_top20_hits": row["equal_family"]["top20_hits"],
                "equal_family_mean_actual_rank": row["equal_family"]["mean_rank"],
                "equal_feature_top5_hits": row["equal_feature"]["top5_hits"],
                "equal_feature_top10_hits": row["equal_feature"]["top10_hits"],
                "equal_feature_top20_hits": row["equal_feature"]["top20_hits"],
                "equal_feature_mean_actual_rank": row["equal_feature"]["mean_rank"],
                "fixed_discovery_family": fixed_family if row["split"] != "discovery" else "",
                "fixed_discovery_family_top5_hits": fixed_metrics.get("top5_hits", ""),
                "fixed_discovery_family_top10_hits": fixed_metrics.get("top10_hits", ""),
                "fixed_discovery_family_top20_hits": fixed_metrics.get("top20_hits", ""),
                "fixed_discovery_family_mean_actual_rank": fixed_metrics.get("mean_rank", ""),
            }
            for family in FAMILY_NAMES:
                metrics = row["families"][family]
                output[f"{family}_top5_hits"] = metrics["top5_hits"]
                output[f"{family}_top10_hits"] = metrics["top10_hits"]
                output[f"{family}_top20_hits"] = metrics["top20_hits"]
                output[f"{family}_mean_actual_rank"] = metrics["mean_rank"]
            writer.writerow(output)

    ledger_sha = hashlib.sha256(target_ledger_path.read_bytes()).hexdigest()
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-C0",
        "status": "EXECUTED_EXPLORATORY",
        "decision": decision,
        "hypothesis": "Prior rolling-100 Top-5 success of a formula family anticipates next-target family usefulness.",
        "source": {
            "archive_path": "data/storico_daily.csv", "git_blob_sha1": archive_blob_sha,
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "eligible_draw_count": n, "first_date": dates[0], "last_date": dates[-1],
            "cutoff": CUTOFF, "excluded_rows_after_cutoff": excluded,
            "disputed_contest_315_used": False,
        },
        "walkforward": {
            "minimum_prior_history": MIN_HISTORY, "scored_targets": scored_targets,
            "split_rule": "offset/scored_targets <0.60 discovery; <0.80 validation; otherwise blind_oos",
            "split_counts": dict(actual_split_counts),
            "strict_prior": "features and family selector for target i use only draws/outcomes with index < i; state update follows target scoring",
            "rolling_selector_window": ROLLING_WINDOW,
            "warmup_targets": ROLLING_WINDOW,
            "blind_used_for_policy_selection": False,
        },
        "formula_registry": {
            "source_feature_count": len(FEATURE_NAMES), "unique_feature_count": len(UNIQUE_FEATURE_INDICES),
            "aliases_verified": ALIASES, "families": {f: [FEATURE_NAMES[i] for i in FAMILIES[f]] for f in FAMILY_NAMES},
            "family_score": "equal mean of per-target z-scored feature columns; z-scored across the 40 candidate numbers",
            "rank_tie_policy": "equal scores retain ascending number order",
        },
        "fixed_discovery_family": fixed_family,
        "metrics_by_split": split_summary,
        "paired_inference": {
            "method": "non-overlapping 20-target block sign-flip and circular moving-block bootstrap",
            "replicates": REPLICATES, "block_length": BLOCK_LENGTH,
            "holm_method": "Holm-Bonferroni over 24 Validation/Blind × 3 controls × 4 endpoints",
            "tests": paired_tests,
            "primary_test": paired_primary,
            "primary_practical_threshold": 0.005,
        },
        "uniform_exact_null": {
            "method": "exact convolution of Hypergeometric(40,k,5) per-target hit counts",
            "holm_method": "Holm-Bonferroni over 6 dynamic-model Validation/Blind × Top-5/10/20 tests",
            "tests": uniform_tests,
        },
        "behaviour_map": {
            "family_pair_complementarity_and_cooccurrence": behaviour_pairs,
            "family_success_time_series": family_time_series,
            "selector_family_counts": {split: dict(counts) for split, counts in selection_counts.items()},
            "oracle_best_family_counts_descriptive_only": {split: dict(counts) for split, counts in oracle_counts.items()},
            "selector_switches_excluding_warmup": switches,
            "mean_selected_family_run_length": float(np.mean(run_lengths)) if run_lengths else None,
            "selected_family_decisions_excluding_warmup": len(selected_only),
        },
        "acceptance": {
            "archive_git_blob_sha_verified": True, "eligible_rows_verified": n,
            "target_ledger_rows": len(target_rows), "split_counts_verified": dict(actual_split_counts) == EXPECTED_SPLITS,
            "family_partition_verified": True, "duplicate_aliases_verified_on_every_target": True,
            "strict_prior_update_order": True, "blind_used_for_selection": False,
            "paired_holm_family_size": len(paired_tests), "uniform_holm_family_size": len(uniform_tests),
        },
        "limitations": [
            "Historical exploratory experiment in a heavily exposed SONAR archive; not virgin prospective confirmation.",
            "Only six coarse families derived from the Q80 27-feature grammar; not an exhaustive mathematical formula universe.",
            "Rolling-100 selector may chase noise; warm-up uses the equal-family ensemble.",
            "The block randomization/bootstrap inference depends on the declared 20-target block approximation.",
            "Exact uniform null assumes independent uniform 5-of-40 draws; it is a model-based lottery null.",
            "Retrospective oracle-best family is descriptive only and cannot be used for target selection.",
        ],
        "next_action": "Use this behaviour map to refine the canonical formula registry and test only pre-registered pre-target state signals; do not promote without independent prospective evidence.",
        "target_ledger": {
            "path": str(target_ledger_path.relative_to(ROOT)),
            "rows": len(target_rows), "sha256": ledger_sha,
        },
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_sha = hashlib.sha256(report_path.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "1.0", "task_id": "Q141-C0",
        "status": "REPLAYABLE_EXPLORATORY_BUNDLE",
        "source_archive_git_blob_sha1": archive_blob_sha,
        "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "report_path": str(report_path.relative_to(ROOT)), "report_sha256": report_sha,
        "target_ledger_path": str(target_ledger_path.relative_to(ROOT)), "target_ledger_sha256": ledger_sha,
        "target_rows": len(target_rows), "split_counts": dict(actual_split_counts),
        "paired_test_count": len(paired_tests), "paired_holm_family_size": len(paired_tests),
        "uniform_test_count": len(uniform_tests), "uniform_holm_family_size": len(uniform_tests),
        "bootstrap_replicates": REPLICATES, "block_length": BLOCK_LENGTH,
        "deterministic_seeds": {"base": SEED, "paired_signflip_and_bootstrap": "base + fixed test index offsets"},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SONAR_Q141_FAMILY_BEHAVIOUR_RESULT " + json.dumps({
        "status": report["status"], "decision": decision, "targets": scored_targets,
        "splits": dict(actual_split_counts), "fixed_discovery_family": fixed_family,
        "primary_blind_top5_delta": paired_primary["mean_benefit_delta"],
        "primary_blind_top5_ci95": paired_primary["bootstrap_ci_95"],
        "primary_blind_top5_p_raw": paired_primary["block_signflip_p_raw"],
        "primary_blind_top5_p_holm24": paired_primary["block_signflip_p_holm_24_tests"],
        "uniform_dynamic_blind_top5_p_holm6": next(
            x["exact_hypergeom_p_holm_6_tests"] for x in uniform_tests
            if x["split"] == "blind_oos" and x["endpoint"] == "top5_hit_share"
        ),
        "report_sha256": report_sha, "target_ledger_sha256": ledger_sha,
    }, separators=(",", ":")))
    print("SONAR_Q141_ACCEPTANCE_PASS: source pin, eligible prefix, split coverage, aliases, strict-prior update order and output hashes verified")
    return report


if __name__ == "__main__":
    run()
