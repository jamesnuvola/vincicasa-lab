#!/usr/bin/env python3
"""Q84 causal flow-state strategy atlas for VinciCasa SONAR.

Every target is scored from the strict historical prefix. Adaptive rule weights
use only already-scored prior targets whose pre-target flow states are similar.
"""
from __future__ import annotations
import csv, gzip, hashlib, json, math, os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

from sonar_sequence_agent import (
    CONFIGS, BASE_RULES, MIN_HISTORY, NUMBERS, read_draws,
    feature_scores, rank_numbers, combine_scores, cascade_rank,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
ACTIVE_REPORT = OUT / "active_engine_walkforward.json"
PROTOCOL_PATH = OUT / "strategy_atlas_protocol_2026-11-09.json"
CATALOG_PATH = OUT / "strategy_atlas_catalog.jsonl"
LEDGER_PATH = OUT / "strategy_atlas_target_ledger.csv.gz"
LIFECYCLE_PATH = OUT / "strategy_atlas_lifecycle.json"
REPORT_PATH = OUT / "strategy_atlas_report.json"
MANIFEST_PATH = OUT / "strategy_atlas_manifest.json"
CHECKPOINT_PATH = OUT / "strategy_atlas_checkpoint_2026-11-09.json"
VALIDATION_PATH = OUT / "strategy_atlas_validation.json"
AMENDMENT_PATH = OUT / "strategy_atlas_diagnostic_amendment_2026-11-09.json"

FLOW_FEATURES = (
    "sum_velocity_5", "sum_acceleration_5", "range_velocity_5",
    "range_acceleration_5", "gap_velocity_5", "odd_velocity_5",
    "overlap_velocity_5", "sum_dispersion_delta_20_80",
    "range_dispersion_delta_20_80", "frequency_total_variation_20_80",
    "frequency_concentration_delta_20_80", "decade_entropy_delta_20_80",
    "overlap_dispersion_delta_20_80",
)
LOOKBACK = 250
NEIGHBORS = 50
MIN_ANALOGS = 30
SHRINKAGE = 30.0
BASELINE_TOP20 = 2.5
TEMPERATURE = 0.35
WEIGHT_CLIP = (0.5, 2.0)
BLOCK_LENGTH = 20
BOOTSTRAP_REPS = 2000
SEED = 84
ENDPOINTS = (("top5", 5), ("top10", 10), ("top20", 20))
GLOBAL_IDS = [c[0] for c in CONFIGS] + ["ENSEMBLE::EQUAL_WEIGHT_42", "ENSEMBLE::FLOW_STATE_ADAPTIVE"]
FLOW_ID = "ENSEMBLE::FLOW_STATE_ADAPTIVE"
EQUAL_ID = "ENSEMBLE::EQUAL_WEIGHT_42"
ORACLE_ID = "ORACLE::BEST_RULE_PER_TARGET"


def json_dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def mean(values):
    return float(np.mean(np.asarray(values, dtype=float)))


def std(values):
    return float(np.std(np.asarray(values, dtype=float), ddof=0))


def entropy_from_counts(counts):
    total = float(sum(counts))
    if total <= 0:
        return 0.0
    probs = [x / total for x in counts if x > 0]
    return float(-sum(p * math.log(p) for p in probs) / math.log(len(counts)))


def flow_state(history):
    """13-dimensional state from the prior prefix only; the target is not accepted."""
    if len(history) < 100:
        raise ValueError("Q84 flow state requires at least 100 prior draws")
    window = history[-101:]
    sums, ranges, gaps, odds, overlaps = [], [], [], [], []
    for j in range(1, len(window)):
        nums = window[j]["nums"]
        prev = window[j - 1]["nums"]
        sums.append(float(sum(nums)))
        ranges.append(float(nums[-1] - nums[0]))
        gaps.append(float(sum(b - a for a, b in zip(nums, nums[1:])) / 4.0))
        odds.append(float(sum(n % 2 for n in nums)))
        overlaps.append(float(len(set(nums) & set(prev))))
    sums = np.asarray(sums, dtype=float)
    ranges = np.asarray(ranges, dtype=float)
    gaps = np.asarray(gaps, dtype=float)
    odds = np.asarray(odds, dtype=float)
    overlaps = np.asarray(overlaps, dtype=float)

    def velocity(x):
        return mean(x[-5:]) - mean(x[-10:-5])

    def acceleration(x):
        a = mean(x[-5:]) - mean(x[-10:-5])
        b = mean(x[-10:-5]) - mean(x[-15:-10])
        return a - b

    last20 = history[-20:]
    prev80 = history[-100:-20]

    def number_counts(draws):
        counts = np.zeros(40, dtype=float)
        for draw in draws:
            for number in draw["nums"]:
                counts[number - 1] += 1
        return counts

    c20, c80 = number_counts(last20), number_counts(prev80)
    p20, p80 = c20 / 100.0, c80 / 400.0
    tv = 0.5 * float(np.abs(p20 - p80).sum())
    concentration_delta = float(np.square(p20).sum() - np.square(p80).sum())

    def decade_counts(draws):
        counts = [0, 0, 0, 0]
        for draw in draws:
            for number in draw["nums"]:
                counts[min(3, (number - 1) // 10)] += 1
        return counts

    decade_delta = entropy_from_counts(decade_counts(last20)) - entropy_from_counts(decade_counts(prev80))
    vector = np.asarray([
        velocity(sums), acceleration(sums),
        velocity(ranges), acceleration(ranges),
        velocity(gaps), velocity(odds), velocity(overlaps),
        std(sums[-20:]) - std(sums[-100:-20]),
        std(ranges[-20:]) - std(ranges[-100:-20]),
        tv, concentration_delta, decade_delta,
        std(overlaps[-20:]) - std(overlaps[-100:-20]),
    ], dtype=float)
    if len(vector) != len(FLOW_FEATURES) or not np.isfinite(vector).all():
        raise ValueError("Q84 invalid flow state")
    return vector


def robust_center_scale(states):
    center = np.median(states, axis=0)
    mad = np.median(np.abs(states - center), axis=0) * 1.4826
    fallback = np.std(states, axis=0)
    scale = np.where(mad > 1e-8, mad, fallback)
    scale = np.where(scale > 1e-8, scale, 1.0)
    return center, scale


def prior_flow_context(current_state, prior_states, prior_hits, prior_turbulence):
    """All analogs and thresholds are drawn strictly from already-scored targets."""
    if len(prior_states) != len(prior_hits) or len(prior_states) != len(prior_turbulence):
        raise ValueError("Q84 prior memory arrays are misaligned")
    if len(prior_states) < MIN_ANALOGS:
        return np.ones(len(CONFIGS)), np.full(len(CONFIGS), BASELINE_TOP20), 0, 0.0, None, "UNCLASSIFIED"

    states = np.asarray(prior_states[-LOOKBACK:], dtype=float)
    hit_memory = np.asarray(prior_hits[-LOOKBACK:], dtype=float)
    center, scale = robust_center_scale(states)
    z_current = (current_state - center) / scale
    distances = np.sqrt(np.mean(np.square((states - current_state) / scale), axis=1))
    k = min(NEIGHBORS, len(states))
    nearest = np.argsort(distances, kind="stable")[:k]
    bandwidth = max(float(np.median(distances[nearest])), 1e-6)
    kernel = np.exp(-0.5 * np.square(distances[nearest] / bandwidth))
    if float(kernel.sum()) <= 1e-12:
        kernel = np.ones(k, dtype=float)
    local = np.average(hit_memory[nearest], axis=0, weights=kernel)
    effective_n = float(kernel.sum() ** 2 / np.square(kernel).sum())
    shrunk = (effective_n * local + SHRINKAGE * BASELINE_TOP20) / (effective_n + SHRINKAGE)
    weights = np.clip(np.exp((shrunk - BASELINE_TOP20) / TEMPERATURE), WEIGHT_CLIP[0], WEIGHT_CLIP[1])

    turbulence = float(np.sqrt(np.mean(np.square(z_current))))
    recent_turbulence = np.asarray([x for x in prior_turbulence[-LOOKBACK:] if x is not None], dtype=float)
    if len(recent_turbulence) < MIN_ANALOGS:
        regime = "UNCLASSIFIED"
    else:
        q20, q80 = np.quantile(recent_turbulence, [0.2, 0.8])
        if turbulence <= q20:
            regime = "LOW_TURBULENCE"
        elif turbulence >= q80:
            regime = "HIGH_TURBULENCE"
        else:
            regime = "MID_TURBULENCE"
    return weights, local, k, effective_n, turbulence, regime


def rank_vector_from_order(order):
    out = np.empty(40, dtype=np.int8)
    for pos, number in enumerate(order, start=1):
        out[number - 1] = pos
    if sorted(out.tolist()) != list(range(1, 41)):
        raise ValueError("Q84 ranking is not a permutation of 1..40")
    return out


def weighted_borda_rank(rank_matrix, weights):
    points = 41.0 - rank_matrix.astype(float)
    scores = np.average(points, axis=0, weights=weights)
    order = np.lexsort((np.arange(1, 41), -scores))
    return rank_vector_from_order((order + 1).tolist())


def normal_upper_tail(z):
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def hypergeom_screen_p(total_hits, n_targets, k):
    """Conditional null: exactly five distinct winners among 40 for every target."""
    if n_targets <= 0:
        return 1.0
    expected = n_targets * 5.0 * k / 40.0
    variance_one = k * (5.0 / 40.0) * (35.0 / 40.0) * ((40.0 - k) / 39.0)
    variance = n_targets * variance_one
    if variance <= 0:
        return 1.0
    z = (float(total_hits) - expected - 0.5) / math.sqrt(variance)
    return max(0.0, min(1.0, normal_upper_tail(z)))


def holm_adjust(items):
    """Return Holm-Bonferroni adjusted p-values, preserving original item IDs."""
    ordered = sorted(items, key=lambda x: (x["p_raw"], x["test_id"]))
    m = len(ordered)
    running = 0.0
    adjusted = {}
    for i, item in enumerate(ordered):
        value = min(1.0, (m - i) * float(item["p_raw"]))
        running = max(running, value)
        adjusted[item["test_id"]] = running
    return adjusted


def bootstrap_paired(a, b, seed):
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(diff)
    if n < BLOCK_LENGTH:
        return {"n": n, "mean_difference": mean(diff), "ci95": [None, None], "p_two_sided": None}
    rng = np.random.default_rng(seed)
    samples = np.empty(BOOTSTRAP_REPS, dtype=float)
    blocks_needed = math.ceil(n / BLOCK_LENGTH)
    offsets = np.arange(BLOCK_LENGTH)
    for r in range(BOOTSTRAP_REPS):
        starts = rng.integers(0, n, size=blocks_needed)
        idx = np.concatenate([(s + offsets) % n for s in starts])[:n]
        samples[r] = float(np.mean(diff[idx]))
    lo, hi = np.quantile(samples, [0.025, 0.975])
    p = 2.0 * min(float(np.mean(samples <= 0)), float(np.mean(samples >= 0)))
    return {
        "n": n, "mean_difference": float(np.mean(diff)),
        "ci95": [float(lo), float(hi)], "p_two_sided": min(1.0, p),
        "block_length": BLOCK_LENGTH, "replicates": BOOTSTRAP_REPS, "seed": seed,
    }


def split_name(index, total):
    discovery_end = int(0.60 * total)
    validation_end = int(0.80 * total)
    if index < discovery_end:
        return "discovery"
    if index < validation_end:
        return "validation"
    return "blind_oos"


def strategy_order(base, config):
    config_id, config_type, sequence = config
    if config_type == "chain":
        return cascade_rank(base, sequence)
    if len(sequence) == 1:
        return rank_numbers(base[sequence[0]])[0]
    return rank_numbers(combine_scores(base, sequence))[0]


def metric_row(strategy_id, split, indices, hits, actual_ranks, ptest_rows, family_kind="GLOBAL", regime=None):
    n = len(indices)
    if n:
        selected = hits[indices]
        ranks = actual_ranks[indices]
        mean_hits = [float(selected[:, j].mean()) for j in range(3)]
        all5 = int(np.sum(selected[:, 2] == 5))
        fourplus = int(np.sum(selected[:, 2] >= 4))
        mean_rank = float(ranks.mean())
        distribution = {str(k): int(np.sum(selected[:, 2] == k)) for k in range(6)}
    else:
        mean_hits, all5, fourplus, mean_rank, distribution = [None] * 3, 0, 0, None, {}
    row = {
        "strategy_id": strategy_id, "family_kind": family_kind, "regime": regime,
        "split": split, "targets": n, "mean_hits_top5": mean_hits[0],
        "mean_hits_top10": mean_hits[1], "mean_hits_top20": mean_hits[2],
        "top20_4plus": fourplus, "top20_5of5": all5,
        "top20_5of5_rate": all5 / n if n else None,
        "top20_5of5_random_expected": n * (math.comb(20, 5) / math.comb(40, 5)) if n else 0.0,
        "mean_rank_actual_numbers": mean_rank,
        "top20_hit_distribution": distribution,
    }
    for j, (endpoint, k) in enumerate(ENDPOINTS):
        total_hits = int(np.sum(hits[indices, j])) if n else 0
        p = hypergeom_screen_p(total_hits, n, k) if n >= 30 else 1.0
        test_id = family_kind + "|" + strategy_id + "|" + (regime or "") + "|" + split + "|" + endpoint
        ptest_rows.append({"test_id": test_id, "p_raw": p, "strategy_id": strategy_id,
                           "split": split, "endpoint": endpoint, "family_kind": family_kind,
                           "regime": regime, "targets": n})
    return row


def classify_relationship(rho, overlap_mean, a_low_count, b_low_count,
                           mean_a, mean_b, b_when_a_low, a_when_b_low):
    """Conservative descriptive complementarity label based on paired-miss lift."""
    a_lift = None if a_when_b_low is None else float(a_when_b_low - mean_a)
    b_lift = None if b_when_a_low is None else float(b_when_a_low - mean_b)
    if rho >= 0.995 and overlap_mean >= 0.98:
        label = "NEAR_EQUIVALENT"
    elif rho <= -0.10 and overlap_mean <= 0.50:
        label = "ANTAGONISTIC"
    else:
        a_covers_b = (b_low_count >= 30 and a_when_b_low is not None
                      and a_when_b_low >= 2.5 and a_lift >= 0.10)
        b_covers_a = (a_low_count >= 30 and b_when_a_low is not None
                      and b_when_a_low >= 2.5 and b_lift >= 0.10)
        if a_covers_b and b_covers_a:
            label = "COMPLEMENTARY_BOTH_WAYS"
        elif a_covers_b:
            label = "COMPLEMENTARY_A_COVERS_B"
        elif b_covers_a:
            label = "COMPLEMENTARY_B_COVERS_A"
        else:
            label = "MIXED"
    return label, a_lift, b_lift


def contiguous_intervals(indices, dates):
    if not indices:
        return []
    groups, start, prev = [], indices[0], indices[0]
    for idx in indices[1:]:
        if idx != prev + 1:
            groups.append({"start": dates[start], "end": dates[prev], "targets": prev - start + 1})
            start = idx
        prev = idx
    groups.append({"start": dates[start], "end": dates[prev], "targets": prev - start + 1})
    return groups


def catalog_entry(strategy_id, strategy_class, formula_ast, canonical_formula, feature_ids,
                  operators, threshold_source_split, parent_ids, cluster_id, target_uses_outcome=False):
    payload = {
        "strategy_id": strategy_id, "grammar_version": "Q84_FLOW_STATE_V1",
        "formula_ast": formula_ast, "canonical_formula": canonical_formula,
        "feature_ids": list(feature_ids), "operators": list(operators),
        "threshold_source_split": threshold_source_split,
        "parameters_frozen_at": "2026-11-09T19:00:00Z",
        "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
        "information_cutoff_rule": "strict_prefix_draws_before_target; prior_scored_targets_only_for_adaptation",
        "strategy_class": strategy_class,
        "target_selection_used_outcome": bool(target_uses_outcome),
        "parent_strategy_ids": list(parent_ids),
        "equivalence_cluster_id": cluster_id,
    }
    payload["hash"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if len(CONFIGS) != 42:
        raise SystemExit("Q84_BLOCKED: registered fixed-rule count changed; protocol must be revised")
    draws = read_draws()
    dates = [d["date"].isoformat() for d in draws]
    actuals = np.asarray([d["nums"] for d in draws[MIN_HISTORY:]], dtype=np.int16)
    target_dates = dates[MIN_HISTORY:]
    total = len(target_dates)
    if total < 1000:
        raise SystemExit("Q84_BLOCKED: unexpectedly short walk-forward target set")
    archive_sha1 = git_blob_sha1(ARCHIVE)
    archive_sha256 = sha256_file(ARCHIVE)
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if protocol["source_archive_git_blob_sha1"] != archive_sha1:
        raise SystemExit("Q84_BLOCKED: canonical archive blob differs from preregistered protocol")
    latest_metrics = json.loads((OUT / "latest_metrics.json").read_text(encoding="utf-8"))
    if (latest_metrics.get("total_draws") != len(draws)
            or latest_metrics.get("data_last_date") != dates[-1]
            or (latest_metrics.get("source_git_blob_sha") and latest_metrics.get("source_git_blob_sha") != archive_sha1)):
        raise SystemExit("Q84_BLOCKED: latest metrics cutoff/count are not aligned to canonical archive")
    active_report = json.loads(ACTIVE_REPORT.read_text(encoding="utf-8"))
    if active_report.get("source_git_blob_sha") != archive_sha1 or active_report.get("data", {}).get("total_draws") != len(draws):
        raise SystemExit("Q84_BLOCKED: exact app-engine comparator is not aligned to canonical archive")

    n_strategies = len(GLOBAL_IDS)
    ranks_all = np.empty((total, n_strategies, 40), dtype=np.int8)
    hits_all = np.empty((total, n_strategies, 3), dtype=np.int8)
    actual_rank_all = np.empty((total, n_strategies, 5), dtype=np.int8)
    states, prior_hits, prior_turbulence = [], [], []
    local_means = np.full((total, len(CONFIGS)), BASELINE_TOP20, dtype=float)
    flow_weights_all = np.ones((total, len(CONFIGS)), dtype=float)
    turbulence_all = np.full(total, np.nan, dtype=float)
    regime_all = ["UNCLASSIFIED"] * total
    analog_count_all = np.zeros(total, dtype=np.int16)
    effective_n_all = np.zeros(total, dtype=float)
    split_all = [split_name(i, total) for i in range(total)]
    oracle_parent = []

    for t, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        target = draws[draw_index]
        state = flow_state(history)
        weights, local, analog_count, effective_n, turbulence, regime = prior_flow_context(
            state, states, prior_hits, prior_turbulence
        )
        base = feature_scores(history)
        fixed_ranks = np.empty((len(CONFIGS), 40), dtype=np.int8)
        for s, config in enumerate(CONFIGS):
            fixed_ranks[s] = rank_vector_from_order(strategy_order(base, config))
        equal_rank = weighted_borda_rank(fixed_ranks, np.ones(len(CONFIGS), dtype=float))
        flow_rank = weighted_borda_rank(fixed_ranks, weights)
        current_ranks = np.vstack([fixed_ranks, equal_rank, flow_rank])
        actual = np.asarray(target["nums"], dtype=np.int16)
        actual_ranks = current_ranks[:, actual - 1]
        current_hits = np.column_stack([
            np.sum(actual_ranks <= 5, axis=1),
            np.sum(actual_ranks <= 10, axis=1),
            np.sum(actual_ranks <= 20, axis=1),
        ]).astype(np.int8)

        ranks_all[t] = current_ranks
        hits_all[t] = current_hits
        actual_rank_all[t] = actual_ranks
        local_means[t] = local
        flow_weights_all[t] = weights
        if turbulence is not None:
            turbulence_all[t] = turbulence
        regime_all[t] = regime
        analog_count_all[t] = analog_count
        effective_n_all[t] = effective_n

        best = min(range(len(CONFIGS)), key=lambda s: (
            -int(current_hits[s, 2]), float(np.mean(actual_ranks[s])), s
        ))
        oracle_parent.append(best)

        # The current target is admitted to analog memory only after its ranks and
        # outcomes have been computed. This ordering is the core leakage guard.
        states.append(state)
        prior_hits.append(current_hits[:len(CONFIGS), 2].astype(float))
        prior_turbulence.append(turbulence)

    # Split-level global tests: 44 strategies x 3 splits x 3 endpoints.
    ptests = []
    global_metrics = []
    global_indices = {s: np.asarray([i for i, x in enumerate(split_all) if x == s], dtype=int)
                      for s in ("discovery", "validation", "blind_oos")}
    for si, strategy_id in enumerate(GLOBAL_IDS):
        for split in ("discovery", "validation", "blind_oos"):
            row = metric_row(strategy_id, split, global_indices[split],
                             hits_all[:, si, :], actual_rank_all[:, si, :], ptests)
            global_metrics.append(row)

    # Conditional variants: each fixed rule is eligible only in a prior-only
    # high- or low-turbulence state. All 84 variants remain in the registered family.
    conditional_metrics = []
    for parent_index, parent_id in enumerate([c[0] for c in CONFIGS]):
        for regime in ("HIGH_TURBULENCE", "LOW_TURBULENCE"):
            strategy_id = "COND::" + parent_id + "::" + regime
            for split in ("discovery", "validation", "blind_oos"):
                idx = np.asarray([i for i, x in enumerate(split_all)
                                  if x == split and regime_all[i] == regime], dtype=int)
                row = metric_row(strategy_id, split, idx, hits_all[:, parent_index, :],
                                 actual_rank_all[:, parent_index, :], ptests,
                                 family_kind="CONDITIONAL", regime=regime)
                row["parent_strategy_id"] = parent_id
                row["eligibility_rule"] = "prior_flow_turbulence_expanding_quantile"
                conditional_metrics.append(row)

    expected_family = (len(GLOBAL_IDS) + 2 * len(CONFIGS)) * 3 * 3
    if len(ptests) != expected_family:
        raise SystemExit(f"Q84_BLOCKED: registered test family mismatch {len(ptests)} != {expected_family}")
    adjusted = holm_adjust(ptests)
    for row in global_metrics + conditional_metrics:
        row["p_values_holm"] = {}
        row["p_values_raw"] = {}
    p_lookup = {x["test_id"]: x for x in ptests}
    for row in global_metrics:
        for endpoint, _ in ENDPOINTS:
            key = "GLOBAL|" + row["strategy_id"] + "||" + row["split"] + "|" + endpoint
            row["p_values_raw"][endpoint] = p_lookup[key]["p_raw"]
            row["p_values_holm"][endpoint] = adjusted[key]
    for row in conditional_metrics:
        for endpoint, _ in ENDPOINTS:
            key = "CONDITIONAL|" + row["strategy_id"] + "|" + row["regime"] + "|" + row["split"] + "|" + endpoint
            row["p_values_raw"][endpoint] = p_lookup[key]["p_raw"]
            row["p_values_holm"][endpoint] = adjusted[key]

    # Freeze a fixed-rule comparator using discovery only; it is never reselected.
    discovery_idx = global_indices["discovery"]
    selected_fixed_index = max(range(len(CONFIGS)), key=lambda s: (
        float(hits_all[discovery_idx, s, 2].mean()),
        -float(actual_rank_all[discovery_idx, s, :].mean()),
        -s,
    ))
    selected_fixed_id = CONFIGS[selected_fixed_index][0]
    paired = {}
    for split in ("discovery", "validation", "blind_oos"):
        idx = global_indices[split]
        paired[split] = {
            "flow_vs_equal": {
                endpoint: bootstrap_paired(hits_all[idx, len(CONFIGS) + 1, j],
                                           hits_all[idx, len(CONFIGS), j], SEED + j + len(idx))
                for j, (endpoint, _) in enumerate(ENDPOINTS)
            },
            "flow_vs_discovery_selected_fixed": {
                "comparator_strategy_id": selected_fixed_id,
                "endpoints": {
                    endpoint: bootstrap_paired(hits_all[idx, len(CONFIGS) + 1, j],
                                               hits_all[idx, selected_fixed_index, j], SEED + 100 + j + len(idx))
                    for j, (endpoint, _) in enumerate(ENDPOINTS)
                },
            },
        }

    # Pairwise relationship atlas over the 44 ex-ante global strategies.
    flat_ranks = ranks_all.transpose(1, 0, 2).reshape(n_strategies, -1).astype(float)
    rank_corr = np.corrcoef(flat_ranks)
    top20_masks = ranks_all <= 20
    actual_mask = np.zeros((total, 40), dtype=bool)
    actual_mask[np.arange(total)[:, None], actuals - 1] = True
    relationships = []
    parent = list(range(n_strategies))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for a in range(n_strategies):
        for b in range(a + 1, n_strategies):
            overlap = np.logical_and(top20_masks[:, a, :], top20_masks[:, b, :]).sum(axis=1) / 20.0
            a_unique = int(np.logical_and(np.logical_and(top20_masks[:, a, :], ~top20_masks[:, b, :]), actual_mask).sum())
            b_unique = int(np.logical_and(np.logical_and(top20_masks[:, b, :], ~top20_masks[:, a, :]), actual_mask).sum())
            ah, bh = hits_all[:, a, 2].astype(float), hits_all[:, b, 2].astype(float)
            hit_corr = float(np.corrcoef(ah, bh)[0, 1]) if std(ah) > 0 and std(bh) > 0 else None
            rho = float(rank_corr[a, b])
            overlap_mean = float(overlap.mean())
            a_low = ah <= 2
            b_low = bh <= 2
            b_when_a_low = float(bh[a_low].mean()) if np.any(a_low) else None
            a_when_b_low = float(ah[b_low].mean()) if np.any(b_low) else None
            relation, a_lift, b_lift = classify_relationship(
                rho, overlap_mean, int(a_low.sum()), int(b_low.sum()),
                float(ah.mean()), float(bh.mean()), b_when_a_low, a_when_b_low
            )
            if relation == "NEAR_EQUIVALENT":
                union(a, b)
            relationships.append({
                "strategy_a": GLOBAL_IDS[a], "strategy_b": GLOBAL_IDS[b],
                "rank_spearman_rho": rho, "top20_overlap_fraction": overlap_mean,
                "hit_count_correlation": hit_corr,
                "a_unique_actual_hits_outside_b_top20": a_unique,
                "b_unique_actual_hits_outside_a_top20": b_unique,
                "a_targets_with_2_or_fewer": int(a_low.sum()),
                "b_targets_with_2_or_fewer": int(b_low.sum()),
                "b_mean_hits_when_a_has_2_or_fewer": b_when_a_low,
                "a_mean_hits_when_b_has_2_or_fewer": a_when_b_low,
                "a_conditional_lift_when_b_low": a_lift,
                "b_conditional_lift_when_a_low": b_lift,
                "relation_class": relation,
            })

    cluster_roots = {}
    for i in range(n_strategies):
        root = find(i)
        cluster_roots.setdefault(root, []).append(GLOBAL_IDS[i])
    cluster_ids = {}
    for number, members in enumerate(sorted(cluster_roots.values(), key=lambda x: x[0]), start=1):
        for sid in members:
            cluster_ids[sid] = f"EQ{number:03d}"

    # Rule lifecycle and detectability before success.
    lifecycle = {}
    for si, strategy_id in enumerate(GLOBAL_IDS):
        success = [i for i in range(total) if hits_all[i, si, 2] >= 4]
        all5 = [i for i in range(total) if hits_all[i, si, 2] == 5]
        gaps = [b - a for a, b in zip(success, success[1:])]
        streak = 0
        for i in range(total - 1, -1, -1):
            if hits_all[i, si, 2] >= 4:
                streak += 1
            else:
                break
        failure_streak = 0
        for i in range(total - 1, -1, -1):
            if hits_all[i, si, 2] < 4:
                failure_streak += 1
            else:
                break
        if si < len(CONFIGS):
            detectable = [i for i in success if local_means[i, si] > BASELINE_TOP20]
            detectability = len(detectable) / len(success) if success else None
        else:
            detectable, detectability = [], None
        lifecycle[strategy_id] = {
            "active_or_inactive": "ACTIVE_LAST_50" if any(hits_all[i, si, 2] >= 4 for i in range(max(0, total - 50), total)) else "INACTIVE_LAST_50",
            "success_definition": "Top20 hit_count >= 4",
            "success_count_top20_4plus": len(success),
            "all5_top20_count": len(all5),
            "first_ex_ante_success": target_dates[success[0]] if success else None,
            "last_success": target_dates[success[-1]] if success else None,
            "success_streak": streak, "failure_streak": failure_streak,
            "targets_since_success": (total - 1 - success[-1]) if success else None,
            "success_intervals": contiguous_intervals(success, target_dates),
            "recurrence_gaps_in_targets": gaps,
            "mean_recurrence_gap": float(np.mean(gaps)) if gaps else None,
            "median_recurrence_gap": float(np.median(gaps)) if gaps else None,
            "condition_state_at_success": [{"target_date": target_dates[i], "regime": regime_all[i],
                                             "flow_state": [float(x) for x in states[i]]} for i in success],
            "pre_target_detectability": {
                "successes_with_local_prior_analog_mean_above_2_5": len(detectable),
                "share_of_successes": detectability,
                "interpretation": "Descriptive only; local analog statistics are computed strictly before each target."
            },
            "retrospective_only_flag": False,
        }

    # Build catalog: 42 fixed rules, 2 ensembles, 84 conditional variants, 1 oracle.
    catalog = []
    for i, (sid, kind, sequence) in enumerate(CONFIGS):
        if kind == "chain":
            ast = {"op": "ordered_cascade", "features": list(sequence)}
            ops = ["ordered_filter"]
        elif len(sequence) == 1:
            ast = {"op": "single_feature_rank", "feature": sequence[0]}
            ops = ["rank"]
        else:
            ast = {"op": "equal_weight_borda", "features": list(sequence)}
            ops = ["rank", "borda_mean"]
        catalog.append(catalog_entry(sid, "EX_ANTE_GENERAL", ast, sid + "::" + ">".join(sequence),
                                     sequence, ops, "FIXED_BEFORE_WALKFORWARD", [], cluster_ids[sid]))
    catalog.append(catalog_entry(EQUAL_ID, "EX_ANTE_GENERAL",
        {"op": "equal_weight_borda", "parent_strategy_ids": [c[0] for c in CONFIGS]},
        "equal_weight_borda(all_42_fixed_rules)", BASE_RULES, ["rank", "borda_mean"],
        "FIXED_BEFORE_WALKFORWARD", [c[0] for c in CONFIGS], cluster_ids[EQUAL_ID]))
    catalog.append(catalog_entry(FLOW_ID, "EX_ANTE_CONDITIONAL",
        {"op": "state_analog_weighted_borda", "state_features": list(FLOW_FEATURES),
         "lookback_targets": LOOKBACK, "nearest_neighbors": NEIGHBORS,
         "minimum_prior_analogs": MIN_ANALOGS, "shrinkage_pseudocount": SHRINKAGE,
         "baseline_top20_hits": BASELINE_TOP20, "temperature": TEMPERATURE,
         "weight_clip": list(WEIGHT_CLIP)},
        "flow_state_analog_weighted_borda(all_42_fixed_rules)", list(FLOW_FEATURES) + list(BASE_RULES),
        ["robust_scale", "nearest_neighbor", "gaussian_kernel", "shrinkage", "weighted_borda"],
        "PREREGISTERED_PARAMETERS_2026-11-09", [c[0] for c in CONFIGS], cluster_ids[FLOW_ID]))
    for sid, _, sequence in CONFIGS:
        for regime in ("HIGH_TURBULENCE", "LOW_TURBULENCE"):
            cid = "COND::" + sid + "::" + regime
            catalog.append(catalog_entry(cid, "EX_ANTE_CONDITIONAL",
                {"op": "eligibility_gate", "condition": "prior_flow_regime == " + regime,
                 "parent_strategy_id": sid},
                "IF(prior_flow_regime==" + regime + ") THEN " + sid,
                list(sequence) + list(FLOW_FEATURES), ["prior_only_state_gate", "inherit_parent_rank"],
                "EXPANDING_PRIOR_STATE_QUANTILE_20_80", [sid], cluster_ids[sid] + "_" + regime))
    catalog.append(catalog_entry(ORACLE_ID, "RETROSPECTIVE_DESCRIPTIVE",
        {"op": "argmax_actual_top20_hits_per_target", "parent_strategy_ids": [c[0] for c in CONFIGS]},
        "RETROSPECTIVE_ORACLE(argmax_target_top20_hits)", BASE_RULES,
        ["target_outcome_selection"], "TARGET_OUTCOME_USED", [c[0] for c in CONFIGS],
        "RETROSPECTIVE_ONLY", True))

    # Persist a complete event-level ledger. The oracle is explicitly ineligible ex ante.
    ledger_rows = 0
    ledger_fields = [
        "target_date", "prior_cutoff_date", "prior_draw_count", "strategy_id",
        "strategy_class", "eligible_ex_ante", "eligibility_reason",
        "rank_by_number_1_to_40", "actual_quintet", "actual_number_ranks",
        "hits_top5", "hits_top10", "hits_top20", "mean_actual_rank", "split",
        "state_features_prior_only", "flow_regime_prior_only", "flow_turbulence",
        "analog_neighbor_count", "analog_effective_n", "flow_strategy_weights",
        "forecast_freeze_id", "target_selection_used_outcome",
    ]
    with gzip.open(LEDGER_PATH, "wt", newline="", encoding="utf-8", compresslevel=6) as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger_fields)
        writer.writeheader()
        for t in range(total):
            actual = actuals[t].tolist()
            state_json = json.dumps([float(x) for x in states[t]], separators=(",", ":"))
            base_row = {
                "target_date": target_dates[t],
                "prior_cutoff_date": dates[MIN_HISTORY + t - 1],
                "prior_draw_count": MIN_HISTORY + t,
                "actual_quintet": " ".join(map(str, actual)),
                "split": split_all[t],
                "state_features_prior_only": state_json,
                "flow_regime_prior_only": regime_all[t],
                "flow_turbulence": "" if np.isnan(turbulence_all[t]) else round(float(turbulence_all[t]), 8),
                "analog_neighbor_count": int(analog_count_all[t]),
                "analog_effective_n": round(float(effective_n_all[t]), 6),
                "forecast_freeze_id": "",
            }
            for s, sid in enumerate(GLOBAL_IDS):
                ranks = ranks_all[t, s]
                actual_ranks = actual_rank_all[t, s].tolist()
                row = dict(base_row)
                row.update({
                    "strategy_id": sid,
                    "strategy_class": "EX_ANTE_CONDITIONAL" if sid == FLOW_ID else "EX_ANTE_GENERAL",
                    "eligible_ex_ante": "true",
                    "eligibility_reason": "ALWAYS_ELIGIBLE" if sid != FLOW_ID else "CURRENT_PRIOR_FLOW_STATE_READ",
                    "rank_by_number_1_to_40": json.dumps(ranks.tolist(), separators=(",", ":")),
                    "actual_number_ranks": json.dumps(actual_ranks, separators=(",", ":")),
                    "hits_top5": int(hits_all[t, s, 0]), "hits_top10": int(hits_all[t, s, 1]),
                    "hits_top20": int(hits_all[t, s, 2]),
                    "mean_actual_rank": round(float(np.mean(actual_ranks)), 6),
                    "flow_strategy_weights": (json.dumps([round(float(x), 8) for x in flow_weights_all[t]], separators=(",", ":"))
                                              if sid == FLOW_ID else ""),
                    "target_selection_used_outcome": "false",
                })
                writer.writerow(row); ledger_rows += 1
            if regime_all[t] in ("HIGH_TURBULENCE", "LOW_TURBULENCE"):
                parent_index = 0 if regime_all[t] == "HIGH_TURBULENCE" else 1
                regime = regime_all[t]
                for s, config in enumerate(CONFIGS):
                    cid = "COND::" + config[0] + "::" + regime
                    ranks = ranks_all[t, s]
                    actual_ranks = actual_rank_all[t, s].tolist()
                    row = dict(base_row)
                    row.update({
                        "strategy_id": cid, "strategy_class": "EX_ANTE_CONDITIONAL",
                        "eligible_ex_ante": "true", "eligibility_reason": "PRIOR_STATE_REGIME_" + regime,
                        "rank_by_number_1_to_40": json.dumps(ranks.tolist(), separators=(",", ":")),
                        "actual_number_ranks": json.dumps(actual_ranks, separators=(",", ":")),
                        "hits_top5": int(hits_all[t, s, 0]), "hits_top10": int(hits_all[t, s, 1]),
                        "hits_top20": int(hits_all[t, s, 2]),
                        "mean_actual_rank": round(float(np.mean(actual_ranks)), 6),
                        "flow_strategy_weights": "",
                        "target_selection_used_outcome": "false",
                    })
                    writer.writerow(row); ledger_rows += 1
            best = oracle_parent[t]
            ranks = ranks_all[t, best]
            actual_ranks = actual_rank_all[t, best].tolist()
            row = dict(base_row)
            row.update({
                "strategy_id": ORACLE_ID, "strategy_class": "RETROSPECTIVE_DESCRIPTIVE",
                "eligible_ex_ante": "false",
                "eligibility_reason": "RETROSPECTIVE_SELECTION_AFTER_TARGET_OUTCOME",
                "rank_by_number_1_to_40": json.dumps(ranks.tolist(), separators=(",", ":")),
                "actual_number_ranks": json.dumps(actual_ranks, separators=(",", ":")),
                "hits_top5": int(hits_all[t, best, 0]), "hits_top10": int(hits_all[t, best, 1]),
                "hits_top20": int(hits_all[t, best, 2]),
                "mean_actual_rank": round(float(np.mean(actual_ranks)), 6),
                "flow_strategy_weights": "", "target_selection_used_outcome": "true",
            })
            writer.writerow(row); ledger_rows += 1

    # Apply adjusted p-values and lifecycle outcome labels to catalog records.
    catalog_by_id = {x["strategy_id"]: x for x in catalog}
    blind_by_id = {x["strategy_id"]: x for x in global_metrics if x["split"] == "blind_oos"}
    for sid, entry in catalog_by_id.items():
        if sid in blind_by_id:
            m = blind_by_id[sid]
            p = m["p_values_holm"]["top20"]
            value = m["mean_hits_top20"]
            entry["blind_oos_outcome_class"] = (
                "FAMILYWISE_SIGNAL" if value is not None and value > 2.5 and p < 0.05
                else ("NULL_OR_NEGATIVE" if value is not None and value <= 2.5 else "EXPLORATORY_ABOVE_BASELINE")
            )
        elif sid.startswith("COND::"):
            m = next((x for x in conditional_metrics if x["strategy_id"] == sid and x["split"] == "blind_oos"), None)
            entry["blind_oos_outcome_class"] = "INSUFFICIENT" if not m or m["targets"] < 30 else (
                "NULL_OR_NEGATIVE" if (m["mean_hits_top20"] or 0) <= 2.5 else "EXPLORATORY_ABOVE_BASELINE")
        elif sid == ORACLE_ID:
            entry["blind_oos_outcome_class"] = "RETROSPECTIVE_ONLY_NOT_INFERENTIAL"

    with CATALOG_PATH.open("w", encoding="utf-8", newline="") as f:
        for entry in catalog:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    json_dump(LIFECYCLE_PATH, {
        "schema_version": "1.0", "task_id": "Q84",
        "strategy_lifecycle": lifecycle,
        "pairwise_relationships": relationships,
        "near_equivalence_clusters": cluster_roots,
        "relationship_summary": {
            "pair_count": len(relationships),
            "near_equivalent_pairs": sum(x["relation_class"] == "NEAR_EQUIVALENT" for x in relationships),
            "complementary_pairs": sum(x["relation_class"].startswith("COMPLEMENTARY") for x in relationships),
            "complementary_both_ways": sum(x["relation_class"] == "COMPLEMENTARY_BOTH_WAYS" for x in relationships),
            "complementary_one_way": sum(x["relation_class"] in ("COMPLEMENTARY_A_COVERS_B", "COMPLEMENTARY_B_COVERS_A") for x in relationships),
            "antagonistic_pairs": sum(x["relation_class"] == "ANTAGONISTIC" for x in relationships),
        },
        "relationship_method": {
            "version": "Q84_RELATIONSHIP_DIAGNOSTIC_V2",
            "complementarity_rule": "at least 30 paired targets where the counterpart has <=2 Top20 hits; the candidate must average >=2.5 Top20 hits and exceed its own full-period mean by >=0.10 on those targets",
            "amendment_reason": "The initial any-unique-hit rule was too permissive and labelled almost every pair complementary; v2 requires measurable paired-miss conditional lift.",
            "status": "DESCRIPTIVE_EXPLORATORY_NOT_INFERENTIAL",
        },
        "guardrail": "Relationship and lifecycle labels are descriptive; they do not establish causal or predictive effects."
    })

    def pick_metric(sid, split):
        return next(x for x in global_metrics if x["strategy_id"] == sid and x["split"] == split)

    report = {
        "schema_version": "1.0", "task_id": "Q84",
        "status": "RETROSPECTIVE_WALKFORWARD_COMPLETE_PENDING_VALIDATOR",
        "validation_status": "EXPLORATORY_NOT_PROMOTABLE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_code_commit_sha": os.environ.get("GITHUB_SHA") or "LOCAL_UNPINNED",
        "source_archive": {
            "path": "data/storico_daily.csv", "git_blob_sha1": archive_sha1,
            "sha256": archive_sha256, "draw_count": len(draws),
            "first_date": dates[0], "last_date": dates[-1],
            "latest_quintet": list(draws[-1]["nums"]),
        },
        "walk_forward": {
            "minimum_prior_draws": MIN_HISTORY, "target_count": total,
            "first_target": target_dates[0], "last_target": target_dates[-1],
            "split_counts": {s: len(global_indices[s]) for s in global_indices},
            "strict_prefix_verified_by_runner": True,
            "adaptive_memory_rule": "current target enters analog memory only after its forecast and outcome have been scored",
        },
        "hypothesis": protocol["hypothesis"],
        "flow_state": {
            "features": list(FLOW_FEATURES), "lookback_targets": LOOKBACK,
            "nearest_neighbors": NEIGHBORS, "minimum_prior_analogs": MIN_ANALOGS,
            "shrinkage_pseudocount": SHRINKAGE, "temperature": TEMPERATURE,
            "regime_quantiles": [0.2, 0.8], "regime_counts": dict(Counter(regime_all)),
            "mean_analog_effective_n": float(np.mean(effective_n_all)),
            "mean_weight_cv": float(np.mean(np.std(flow_weights_all, axis=1) / np.maximum(np.mean(flow_weights_all, axis=1), 1e-12))),
            "mean_absolute_weight_deviation_from_one": float(np.mean(np.abs(flow_weights_all - 1.0))),
            "mean_minimum_rule_weight": float(np.mean(np.min(flow_weights_all, axis=1))),
            "mean_maximum_rule_weight": float(np.mean(np.max(flow_weights_all, axis=1))),
            "share_of_rule_weights_at_clip": float(np.mean((flow_weights_all <= WEIGHT_CLIP[0] + 1e-8) | (flow_weights_all >= WEIGHT_CLIP[1] - 1e-8))),
        },
        "baseline": {
            "mean_hits_top5": 0.625, "mean_hits_top10": 1.25, "mean_hits_top20": 2.5,
            "top20_5of5_probability": math.comb(20, 5) / math.comb(40, 5),
        },
        "registered_test_family": {
            "global_strategies": len(GLOBAL_IDS), "conditional_variants": 2 * len(CONFIGS),
            "splits": 3, "endpoints": 3, "tests": len(ptests),
            "holm_adjusted_tests_below_0_05": sum(v < 0.05 for v in adjusted.values()),
            "null": "conditional Hypergeometric(40, 5, k) per target; continuity-corrected normal screen; one global Holm family",
        },
        "global_metrics": global_metrics,
        "conditional_metrics": conditional_metrics,
        "discovery_selected_fixed_comparator": {
            "strategy_id": selected_fixed_id,
            "selection_rule": "highest discovery mean Top20 hits; ties by lower mean actual rank then stable order",
            "validation": pick_metric(selected_fixed_id, "validation"),
            "blind_oos": pick_metric(selected_fixed_id, "blind_oos"),
        },
        "paired_block_bootstrap": paired,
        "paired_bootstrap_inference_note": "These paired block-bootstrap p-values and intervals are descriptive comparisons; they are not part of the 1,152-test Holm family and must not be treated as adjusted significance.",
        "relationship_summary": {
            "pairwise_global_strategy_relationships": len(relationships),
            "near_equivalent_pairs": sum(x["relation_class"] == "NEAR_EQUIVALENT" for x in relationships),
            "complementary_pairs": sum(x["relation_class"].startswith("COMPLEMENTARY") for x in relationships),
            "complementary_both_ways": sum(x["relation_class"] == "COMPLEMENTARY_BOTH_WAYS" for x in relationships),
            "complementary_one_way": sum(x["relation_class"] in ("COMPLEMENTARY_A_COVERS_B", "COMPLEMENTARY_B_COVERS_A") for x in relationships),
            "antagonistic_pairs": sum(x["relation_class"] == "ANTAGONISTIC" for x in relationships),
        },
        "relationship_method": {
            "version": "Q84_RELATIONSHIP_DIAGNOSTIC_V2",
            "complementarity_rule": "at least 30 paired targets where the counterpart has <=2 Top20 hits; the candidate must average >=2.5 Top20 hits and exceed its own full-period mean by >=0.10 on those targets",
            "amendment_reason": "The initial any-unique-hit rule was too permissive and labelled almost every pair complementary; v2 requires measurable paired-miss conditional lift.",
            "status": "DESCRIPTIVE_EXPLORATORY_NOT_INFERENTIAL",
        },
        "external_active_app_engine_v2_comparator": {
            "model_id": active_report.get("model_id"),
            "source_archive_git_blob_sha1": active_report.get("source_git_blob_sha"),
            "splits": active_report.get("splits"),
            "note": "Aggregate comparator only; Q84 does not claim paired per-target comparison with the app engine."
        },
        "oracle_guardrail": "The per-target oracle chooses a rule after seeing the target; it is retrospective-only and excluded from all inferential tests.",
        "holdout_guardrail": "Q84 blind_oos is chronological and not tuned by Q84, but the same dates were already inspected by earlier SONAR research; it is not a virgin research-wide holdout.",
        "promotion_guardrail": "No automatic promotion. Prospective shadow evidence and human review remain required.",
        "ledger_rows": ledger_rows,
        "next_action": "Inspect validation report; then freeze a separate Q84 shadow only before a future target draw and accumulate at least 200 complete prospective paired cases."
    }
    json_dump(REPORT_PATH, report)

    manifest = {
        "schema_version": "1.0", "task_id": "Q84", "status": "OUTPUTS_WRITTEN_PENDING_VALIDATOR",
        "source_archive_git_blob_sha1": archive_sha1, "source_archive_sha256": archive_sha256,
        "source_code_commit_sha": os.environ.get("GITHUB_SHA") or "LOCAL_UNPINNED",
        "target_count": total, "global_strategy_count": len(GLOBAL_IDS),
        "conditional_strategy_count": 2 * len(CONFIGS),
        "oracle_rows": total, "ledger_rows": ledger_rows,
        "holm_test_family_size": len(ptests),
        "files": {},
    }
    for name, path, rows in [
        ("catalog", CATALOG_PATH, len(catalog)),
        ("target_ledger", LEDGER_PATH, ledger_rows),
        ("lifecycle", LIFECYCLE_PATH, len(lifecycle)),
        ("report", REPORT_PATH, 1),
        ("diagnostic_amendment", AMENDMENT_PATH, 1),
    ]:
        manifest["files"][name] = {"path": str(path.relative_to(ROOT)), "rows": rows,
                                   "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    json_dump(MANIFEST_PATH, manifest)
    checkpoint = {
        "schema_version": "1.0", "project": "VinciCasa SONAR",
        "checkpoint_id": "SONAR-Q84-FLOW-STATE-2026-11-09",
        "status": "OUTPUTS_WRITTEN_PENDING_VALIDATOR",
        "source_archive_git_blob_sha1": archive_sha1,
        "source_archive_sha256": archive_sha256,
        "source_code_commit_sha": os.environ.get("GITHUB_SHA") or "LOCAL_UNPINNED",
        "draw_count": len(draws),
        "last_date": dates[-1], "target_count": total,
        "global_strategy_count": len(GLOBAL_IDS),
        "conditional_strategy_count": 2 * len(CONFIGS),
        "ledger_rows": ledger_rows, "holm_test_family_size": len(ptests),
        "immutable_target_2026_10_25_freeze_overwritten": False,
        "next_action": report["next_action"],
    }
    json_dump(CHECKPOINT_PATH, checkpoint)
    print("SONAR_Q84_SUMMARY_BEGIN")
    print(json.dumps({
        "status": report["status"], "archive_draws": len(draws), "archive_last_date": dates[-1],
        "targets": total, "split_counts": report["walk_forward"]["split_counts"],
        "global_strategies": len(GLOBAL_IDS), "conditional_variants": 2 * len(CONFIGS),
        "ledger_rows": ledger_rows, "holm_tests": len(ptests),
        "holm_significant": report["registered_test_family"]["holm_adjusted_tests_below_0_05"],
        "flow_oos": pick_metric(FLOW_ID, "blind_oos"),
        "equal_oos": pick_metric(EQUAL_ID, "blind_oos"),
        "selected_fixed": selected_fixed_id,
    }, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q84_SUMMARY_END")


if __name__ == "__main__":
    main()
