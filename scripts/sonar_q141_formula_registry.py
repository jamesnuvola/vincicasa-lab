#!/usr/bin/env python3
"""Q141-B1: canonical weighted-mean formula registry and strict-prior alias audit."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base

OUT = ROOT / "reports" / "sequence_agent"
PREREG = OUT / "q141_formula_alias_canonicalization_preregistration_2026-11-12.json"
REGISTRY = OUT / "q141_formula_registry.json"
REPORT = OUT / "q141_formula_alias_walkforward_report_2026-11-12.json"
LEDGER = OUT / "q141_formula_alias_walkforward_target_ledger_2026-11-12.csv"
MANIFEST = OUT / "q141_formula_registry_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_formula_registry_checkpoint_2026-11-12.json"
SEED = 14120261112
SCORE_TOLERANCE = 1e-12
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
TASK_BY_SIZE = {
    1: "Q80", 2: "Q80", 3: "Q80", 4: "Q81", 5: "Q83",
    6: "Q86", 7: "Q87", 8: "Q88", 9: "Q89", 10: "Q92",
}
SOURCE_BY_SIZE = {
    1: {"branch": "research/q91-nested-formula-walkforward-20261105", "commit": "3934bb67b607515df616e2b280b9488cd2a5a99a", "path": "scripts/sonar_per_number_condition_grammar.py", "blob": "e5d008f974af0ac21cc15d71037e976dfb061399"},
    2: {"branch": "research/q91-nested-formula-walkforward-20261105", "commit": "3934bb67b607515df616e2b280b9488cd2a5a99a", "path": "scripts/sonar_per_number_condition_grammar.py", "blob": "e5d008f974af0ac21cc15d71037e976dfb061399"},
    3: {"branch": "research/q91-nested-formula-walkforward-20261105", "commit": "3934bb67b607515df616e2b280b9488cd2a5a99a", "path": "scripts/sonar_per_number_condition_grammar.py", "blob": "e5d008f974af0ac21cc15d71037e976dfb061399"},
    4: {"branch": "research/per-number-condition-grammar-q81-20261027", "commit": "5ae18cf8e46081f76402212ac0aaddc00d7d82dc", "path": "scripts/sonar_per_number_condition_four_feature.py", "blob": "d83e7dbc1f8723f4a4ece326ce269b5e14118579"},
    5: {"branch": "research/per-number-condition-grammar-20261026", "commit": "11dd29053a38f595da2812e23ba604fd07451da9", "path": "scripts/sonar_per_number_condition_5plus_grammar.py", "blob": "bf04e9e23bfabe35006406274acdc9e2e6778fd1"},
    6: {"branch": "research/per-number-condition-grammar-20261026", "commit": "11dd29053a38f595da2812e23ba604fd07451da9", "path": "scripts/sonar_per_number_condition_6plus_grammar.py", "blob": "4045f7823b22ce827185522c597026bff1bc4103"},
    7: {"branch": "research/per-number-condition-grammar-20261026", "commit": "11dd29053a38f595da2812e23ba604fd07451da9", "path": "scripts/sonar_per_number_condition_7plus_shard.py", "blob": "a65b436b9eb9a1f2a922eadfe5cf6eb2f4d21e1b"},
    8: {"branch": "research/per-number-condition-grammar-20261026", "commit": "11dd29053a38f595da2812e23ba604fd07451da9", "path": "scripts/sonar_per_number_condition_8plus_shard.py", "blob": "a524dbdeee0d57ea839cd7aec43198e24a465f53"},
    9: {"branch": "research/sonar-q89-nine-feature-20261108", "commit": "5e7301fe2f3bdeb3c85cfd9a4ee810cfdc9c9f77", "path": "scripts/sonar_per_number_condition_9plus_shard.py", "blob": "d109ec1ea1dc8429f787c01867a57abb9d8b6c5a"},
    10: {"branch": "research/sonar-q92-exact-null-calibration-20261109", "commit": "9a04379ed3abdb96c835b5251a91fd972f0c06eb", "path": "scripts/sonar_per_number_condition_10plus_shard.py", "blob": "d9cf7bbe1a8d3db7cddaac6628ef3cde989a7a56"},
}
Q80_SOURCE = {
    "branch": "research/q91-nested-formula-walkforward-20261105",
    "commit": "3934bb67b607515df616e2b280b9488cd2a5a99a",
    "path": "scripts/sonar_per_number_condition_grammar.py",
    "blob": "e5d008f974af0ac21cc15d71037e976dfb061399",
}
Q89_EXTENSION_SOURCE = {
    "branch": "research/q90-expanded-formula-grammar-20261103",
    "commit": "c41eb3b5127aee5b473da69d78bc5aa1fdd3eccc",
    "path": "scripts/sonar_adaptive_novelty_rule_anticipation.py",
    "blob": "c332aa7198f01004480e411956e1a64599236884",
}
Q90_SOURCE = {
    "branch": "research/q90-expanded-formula-grammar-20261103",
    "commit": "c41eb3b5127aee5b473da69d78bc5aa1fdd3eccc",
    "path": "scripts/sonar_q90_expanded_formula_grammar.py",
    "blob": "cbb553839e4c35ec494c35cbc94496a255a6a90a",
}
Q7_SOURCE = {
    "branch": "research/exhaustive-formula-catalog-20261025",
    "commit": "7a37cab601c5f9386131a00246963f8e4aeabf74",
    "path": "scripts/sonar_exhaustive_formula_lab.py",
    "blob": "c2a3664ed5148ae526442d1f189ae40a130e1c5a",
}
Q91_SOURCE = {
    "branch": "research/q91-nested-formula-walkforward-20261105",
    "commit": "3934bb67b607515df616e2b280b9488cd2a5a99a",
    "path": "scripts/sonar_q91_nested_walkforward.py",
    "blob": "ada7f02b260453ac4b15e27f8651ec37f7a72451",
}
Q92_COMMON_SOURCE = {
    "branch": "research/sonar-q92-exact-null-calibration-20261109",
    "commit": "9a04379ed3abdb96c835b5251a91fd972f0c06eb",
    "path": "scripts/sonar_q92_common.py",
    "blob": "647025282b57938ca66549757ef512e2bfd3dfb5",
}
Q89_COMMON_SOURCE = {
    "branch": "research/sonar-q89-nine-feature-20261108",
    "commit": "5e7301fe2f3bdeb3c85cfd9a4ee810cfdc9c9f77",
    "path": "scripts/sonar_q89_common.py",
    "blob": "f3b6f253c6c34d1ea9bd99985437835a1dd06317",
}

ALIASES = {"recent_5": "freq_5", "recent_10": "freq_10"}
RAW_FEATURE_NAMES = list(base.FEATURE_NAMES)
if len(RAW_FEATURE_NAMES) != 27:
    raise RuntimeError("Q141_B1_BLOCKED: Q80 feature count is not 27")
CANONICAL_FEATURE_NAMES = []
for name in RAW_FEATURE_NAMES:
    canonical = ALIASES.get(name, name)
    if canonical not in CANONICAL_FEATURE_NAMES:
        CANONICAL_FEATURE_NAMES.append(canonical)
CANONICAL_NAME_TO_INDEX = {name: i for i, name in enumerate(CANONICAL_FEATURE_NAMES)}
RAW_TO_CANONICAL = [CANONICAL_NAME_TO_INDEX[ALIASES.get(name, name)] for name in RAW_FEATURE_NAMES]
if len(CANONICAL_FEATURE_NAMES) != 25:
    raise RuntimeError("Q141_B1_BLOCKED: expected 25 exact canonical Q80 features")

Q89_NEW_FEATURES = [
    "ewma_hit_hl_3", "ewma_hit_hl_7", "ewma_hit_hl_14", "ewma_hit_hl_30", "ewma_hit_hl_60",
    "ewma_acceleration_3_14", "ewma_acceleration_7_30",
    "last_gap_vs_median", "last_gap_robust_z", "gap_cv", "gap_slope_recent",
    "gap_hazard_empirical", "gap_hazard_residual",
    "pair_lift_recent_last_draw", "pair_pmi_recent_last_draw",
    "cooccurrence_strength_recent", "cooccurrence_surprise_recent",
    "neighbor_balance_pm1_recent", "neighbor_balance_pm2_recent",
    "rank_velocity_5_20", "rank_acceleration_5_20_50", "rank_volatility_20",
    "feature_disagreement_27", "rank_consensus_27",
    "novelty_residual_20", "novelty_residual_50",
    "regime_sum_affinity", "regime_span_affinity", "regime_parity_affinity",
    "regime_entropy_affinity", "transition_profile_affinity",
    "conditional_frequency_prev_draw_regime",
]
Q89_NEW_FAMILIES = (
    ["ewma_hit_dynamics"] * 7
    + ["gap_dynamics"] * 6
    + ["cooccurrence_novelty"] * 6
    + ["rank_trajectory"] * 5
    + ["residual_surprise"] * 2
    + ["regime_transition_affinity"] * 6
)
if len(Q89_NEW_FEATURES) != 32 or len(Q89_NEW_FAMILIES) != 32:
    raise RuntimeError("Q141_B1_BLOCKED: Q89 59-feature extension schema mismatch")

Q80_DESCRIPTIONS = {
    "freq_5": "Count of appearances in the preceding 5 draws.",
    "freq_10": "Count of appearances in the preceding 10 draws.",
    "freq_20": "Count of appearances in the preceding 20 draws.",
    "freq_50": "Count of appearances in the preceding 50 draws.",
    "freq_100": "Count of appearances in the preceding 100 draws.",
    "freq_250": "Count of appearances in the preceding 250 draws.",
    "freq_500": "Count of appearances in the preceding 500 draws.",
    "freq_all": "Cumulative appearances in the strict historical prefix.",
    "trend_5_vs_50": "Rate in the preceding 5 draws minus rate in the preceding 50 draws.",
    "trend_10_vs_100": "Rate in the preceding 10 draws minus rate in the preceding 100 draws.",
    "trend_20_vs_250": "Rate in the preceding 20 draws minus rate in the preceding 250 draws.",
    "age_since_hit": "Number of prior draws since the number last appeared.",
    "gap_mean": "Mean inter-arrival interval in the strict historical prefix.",
    "gap_sd": "Population standard deviation of inter-arrival intervals in the strict historical prefix.",
    "overdue_ratio": "Current age divided by mean inter-arrival interval.",
    "position_log_frequency": "Mean smoothed log-frequency across the five sorted draw positions.",
    "pair_count_with_last_draw": "Mean historical pair count with the five numbers in the immediately preceding draw.",
    "neighbor_pm1_history": "Historical frequency of adjacent numbers at distance one, excluding self.",
    "neighbor_pm2_history": "Historical frequency of numbers within distance two, excluding self.",
    "lag_1": "Indicator that the number appeared in the immediately preceding draw.",
    "lag_2": "Indicator that the number appeared two draws before the target.",
    "lag_3": "Indicator that the number appeared three draws before the target.",
    "lag_5": "Indicator that the number appeared five draws before the target.",
    "lag_10": "Indicator that the number appeared ten draws before the target.",
    "recent_3": "Count of appearances in the preceding 3 draws.",
    "recent_5": "Exact alias of freq_5.",
    "recent_10": "Exact alias of freq_10.",
}
Q89_DESCRIPTIONS = {
    "ewma_hit_hl_3": "Exponentially weighted prior hit indicator with half-life 3.",
    "ewma_hit_hl_7": "Exponentially weighted prior hit indicator with half-life 7.",
    "ewma_hit_hl_14": "Exponentially weighted prior hit indicator with half-life 14.",
    "ewma_hit_hl_30": "Exponentially weighted prior hit indicator with half-life 30.",
    "ewma_hit_hl_60": "Exponentially weighted prior hit indicator with half-life 60.",
    "ewma_acceleration_3_14": "Difference between EWMA hit states with half-lives 3 and 14.",
    "ewma_acceleration_7_30": "Difference between EWMA hit states with half-lives 7 and 30.",
    "last_gap_vs_median": "Current age relative to the median historical inter-arrival gap.",
    "last_gap_robust_z": "Current age minus median gap, scaled by 1.4826 times the median absolute deviation.",
    "gap_cv": "Standard deviation of inter-arrival gaps divided by their mean.",
    "gap_slope_recent": "Linear slope of the most recent eight inter-arrival gaps.",
    "gap_hazard_empirical": "Smoothed empirical probability of a hit at the current age conditional on survival to that age.",
    "gap_hazard_residual": "Empirical gap hazard minus a median-gap reference hazard.",
    "pair_lift_recent_last_draw": "Mean recent pair lift between a candidate and numbers in the immediately preceding draw.",
    "pair_pmi_recent_last_draw": "Mean recent pointwise mutual information for pairs with the immediately preceding draw.",
    "cooccurrence_strength_recent": "Recent co-occurrence rate with numbers in the immediately preceding draw.",
    "cooccurrence_surprise_recent": "Recent pair log-rate relative to its longer-run pair log-rate.",
    "neighbor_balance_pm1_recent": "Recent frequency in the candidate's immediate numeric neighbourhood.",
    "neighbor_balance_pm2_recent": "Recent frequency within distance two of the candidate.",
    "rank_velocity_5_20": "Change in mean historical rank over the 5-draw versus 20-draw windows.",
    "rank_acceleration_5_20_50": "Difference between 5-vs-20 and 20-vs-50 rank movement.",
    "rank_volatility_20": "Standard deviation of prior ranks over the recent 20-target history.",
    "feature_disagreement_27": "Cross-feature dispersion of the 27 Q80 feature ranks for the candidate.",
    "rank_consensus_27": "Median rank across the 27 Q80 features.",
    "novelty_residual_20": "Recent 20-draw hit count residual relative to its prior-frequency expectation.",
    "novelty_residual_50": "Recent 50-draw hit count residual relative to its prior-frequency expectation.",
    "regime_sum_affinity": "Prior frequency conditional on matching the previous draw's sum regime.",
    "regime_span_affinity": "Prior frequency conditional on matching the previous draw's span regime.",
    "regime_parity_affinity": "Prior frequency conditional on the previous draw's odd-count regime.",
    "regime_entropy_affinity": "Prior frequency conditional on the previous draw's parity-entropy category.",
    "transition_profile_affinity": "Prior frequency conditional on the previous regime-transition pair.",
    "conditional_frequency_prev_draw_regime": "Prior frequency conditional on the previous draw's composite regime.",
}

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canonicalize_formula(columns):
    cols = tuple(sorted(set(int(x) for x in columns)))
    if not cols or len(cols) != len(columns) or cols[0] < 0 or cols[-1] >= 27:
        raise ValueError("Q141_B1: raw formula must contain unique Q80 feature indices")
    counts = Counter(RAW_TO_CANONICAL[x] for x in cols)
    divisor = math.gcd(*counts.values())
    signature = tuple((idx, weight // divisor) for idx, weight in sorted(counts.items()))
    return signature, divisor

def canonical_formula_id(signature):
    return "EWMEAN1|" + ";".join(
        f"{CANONICAL_FEATURE_NAMES[idx]}={weight}" for idx, weight in signature
    )

def unique_within_size(k):
    pair_count = lambda total: sum(1 for a in range(3) for b in range(3) if a + b == total)
    return sum(math.comb(23, s) * pair_count(k - s) for s in range(0, min(23, k) + 1))

def unique_global_count(max_size=10):
    total = 5  # five primitive ratios when no singleton feature is present
    for singleton_count in range(1, min(23, max_size) + 1):
        pair_count = sum(
            1 for a in range(3) for b in range(3)
            if 1 <= singleton_count + a + b <= max_size
        )
        total += math.comb(23, singleton_count) * pair_count
    return total

def sample_formulas():
    rng = random.Random(SEED)
    all_samples = []
    for k in range(1, 11):
        candidates = []
        seen = set()
        def add(values):
            values = tuple(sorted(values))
            if len(values) == k and len(set(values)) == k and values[0] >= 0 and values[-1] < 27 and values not in seen:
                seen.add(values)
                candidates.append(values)
        if k == 1:
            for value in (0, 25, 1, 26, 2):
                add((value,))
        else:
            add(tuple(range(k)))
            add(tuple(range(27 - k, 27)))
            add((0, 25) + tuple(range(2, k)))
            add((1, 26) + tuple(range(2, k)))
            if k >= 4:
                add((0, 1, 25, 26) + tuple(range(2, k - 2)))
            add((0, 1) + tuple(range(2, k)))
        while len(candidates) < 12:
            add(rng.sample(range(27), k))
        all_samples.extend(sorted(candidates[:12]))
    if len(all_samples) != 120:
        raise RuntimeError("Q141_B1_BLOCKED: deterministic sample size mismatch")
    return all_samples

def stable_raw_scores(matrix, columns):
    """Evaluate the raw expression with order-stable summation."""
    result = np.empty(40, dtype=np.float64)
    for number in range(40):
        result[number] = math.fsum(float(matrix[number, idx]) for idx in columns) / len(columns)
    return result

def canonical_scores(matrix, signature, scale):
    weights = [(idx, weight * scale) for idx, weight in signature]
    denominator = sum(weight for _, weight in weights)
    result = np.empty(40, dtype=np.float64)
    for number in range(40):
        terms = []
        for idx, weight in weights:
            terms.extend([float(matrix[number, idx])] * weight)
        result[number] = math.fsum(terms) / denominator
    return result

def q80_family(name):
    if name.startswith("freq_") or name.startswith("recent_"):
        return "frequency_level"
    if name.startswith("trend_"):
        return "frequency_change"
    if name in {"age_since_hit", "gap_mean", "gap_sd", "overdue_ratio"}:
        return "recency_gap"
    if name in {"position_log_frequency", "pair_count_with_last_draw"}:
        return "position_dependence"
    if name.startswith("neighbor_"):
        return "neighbour_field"
    if name.startswith("lag_"):
        return "lag_memory"
    raise ValueError("Unclassified Q80 feature: " + name)

def build_feature_registry():
    raw_features = []
    for index, name in enumerate(RAW_FEATURE_NAMES):
        canonical_name = ALIASES.get(name, name)
        raw_features.append({
            "raw_index": index,
            "raw_feature_id": f"Q80:{index:02d}:{name}",
            "name": name,
            "family": q80_family(name),
            "description": Q80_DESCRIPTIONS[name],
            "canonical_feature_id": f"Q80:{CANONICAL_NAME_TO_INDEX[canonical_name]:02d}:{canonical_name}",
            "exact_alias_of": canonical_name if name != canonical_name else None,
            "source": Q80_SOURCE,
        })
    extension = []
    for index, (name, family) in enumerate(zip(Q89_NEW_FEATURES, Q89_NEW_FAMILIES)):
        extension.append({
            "feature_id": f"Q89:{index:02d}:{name}",
            "name": name,
            "family": family,
            "description": Q89_DESCRIPTIONS[name],
            "source": Q89_EXTENSION_SOURCE,
            "exact_semantic_alias_proven": False,
        })
    return raw_features, extension

def build_formula_grammars():
    rows = []
    for k in range(1, 11):
        raw_count = math.comb(27, k)
        unique_k = unique_within_size(k)
        rows.append({
            "task_id": TASK_BY_SIZE[k],
            "feature_universe": "Q80:27 raw columns",
            "feature_count": 27,
            "formula_size": k,
            "grammar": "all unordered k-feature subsets; equal arithmetic mean of per-target standardized feature columns",
            "nominal_formula_count": raw_count,
            "unique_canonical_formula_count_within_size": unique_k,
            "raw_alias_redundancy_within_size": raw_count - unique_k,
            "source": SOURCE_BY_SIZE[k],
            "combinadic_common_source": Q89_COMMON_SOURCE if k == 9 else (Q92_COMMON_SOURCE if k == 10 else None),
            "performance_lineage": "Historical metrics use branch-specific archive versions; do not pool or compare until source hashes are reconciled.",
        })
    return rows

def build_registry(archive_blob_sha, dates):
    raw_features, extension = build_feature_registry()
    nominal = sum(math.comb(27, k) for k in range(1, 11))
    unique = unique_global_count(10)
    per_size_unique = sum(unique_within_size(k) for k in range(1, 11))
    return {
        "schema_version": "1.0",
        "task_id": "Q141-B1",
        "status": "CANONICAL_BASE_GRAMMAR_REGISTERED_ALIAS_SCOPE_ONLY",
        "generated_by": "scripts/sonar_q141_formula_registry.py",
        "source_archive": {
            "path": "data/storico_daily.csv",
            "git_blob_sha1": archive_blob_sha,
            "eligible_draws": len(dates),
            "cutoff": dates[-1],
            "minimum_prior_history": base.MIN_HISTORY,
        },
        "feature_universes": {
            "q80_raw": {"feature_count": 27, "features": raw_features, "source": Q80_SOURCE},
            "q80_canonical": {
                "feature_count": 25,
                "feature_names": CANONICAL_FEATURE_NAMES,
                "exact_aliases": ALIASES,
                "canonicalization": "Exact source-code equality; raw multiplicity retained as integer weights then reduced by GCD.",
            },
            "q89_extension": {
                "feature_count": 32,
                "combined_feature_count": 59,
                "features": extension,
                "source": Q89_EXTENSION_SOURCE,
                "deduplication_status": "No exact semantic aliases asserted; rank correlation or rank duplication is not proof of function equivalence.",
            },
        },
        "canonical_ast": {
            "type": "weighted_mean",
            "version": 1,
            "serialization": "EWMEAN1|feature_name=primitive_integer_weight;...",
            "stable_evaluation": "math.fsum over the primitive weighted terms; raw and canonical expressions use the same order-stable summation semantics.",
            "legacy_evaluation_note": "Historical NumPy mean may differ by sub-tolerance floating-point amounts and alter exact ranks for near-ties; retain as a separate compatibility diagnostic until a tie policy is reviewed.",
            "equivalence": "Two raw equal-weight subset formulas are equivalent iff their canonical feature multiplicity vectors are proportional; divide by GCD to obtain the unique primitive integer vector.",
            "multiplicity_is_semantic": True,
            "correlation_based_deduplication": False,
            "example_equivalences": [
                {"raw": [[0], [0, 25]], "canonical_id": canonical_formula_id(canonicalize_formula((0,))[0])},
                {"raw": [[1], [1, 26]], "canonical_id": canonical_formula_id(canonicalize_formula((1,))[0])},
                {"raw": [[0, 1], [0, 1, 25, 26]], "canonical_id": canonical_formula_id(canonicalize_formula((0, 1))[0])},
            ],
            "example_non_equivalence": {
                "raw": [[0, 1], [0, 1, 25]],
                "reason": "The latter has primitive weights freq_5:2 and freq_10:1; naive alias deletion would incorrectly change the weighting.",
            },
        },
        "formula_grammars": build_formula_grammars(),
        "cross_size_formula_universe": {
            "formula_sizes": list(range(1, 11)),
            "nominal_raw_formula_count": nominal,
            "sum_of_unique_counts_within_each_size": per_size_unique,
            "cross_size_equivalences": per_size_unique - unique,
            "unique_canonical_weighted_mean_count": unique,
            "redundant_raw_formula_ids": nominal - unique,
            "reduction_fraction": (nominal - unique) / nominal,
            "reduction_percent": 100.0 * (nominal - unique) / nominal,
            "exact_count_method": "Combinatorial count over 23 singleton features and two alias classes with multiplicities 0,1,2; no 16.6-million-row materialization.",
        },
        "other_formula_and_selector_families": [
            {
                "task_id": "Q7",
                "formula_count": 1023,
                "grammar": "all non-empty subsets of 10 declared feature families",
                "output_type": "candidate_quintet_ranking",
                "source": Q7_SOURCE,
                "not_comparable_to": "per-number ranking formula counts",
            },
            {
                "task_id": "Q90",
                "formula_count": 330429,
                "feature_universe": "Q89 59-feature matrix; discovery-selected subset of 20",
                "formula_types": {"equal_weight_linear_mean_sizes_4_to_8": 262599, "four_feature_pairwise_interactions": 29070, "four_feature_conditional_gates": 38760},
                "source": Q90_SOURCE,
                "checkpoint": {"archive_blob_sha1": "5d2efd70684e918b27d8f06386d545647898336d", "draw_count": 3401, "scored_targets": 3351},
                "canonical_ast_status": "Interaction/gate ASTs not yet imported or semantically deduplicated.",
            },
            {
                "task_id": "Q91",
                "formula_count": 3303,
                "meta_policy_count": 6,
                "grammar": "Q80 formula catalog plus six nested strict-prior formula-selection policies",
                "source": Q91_SOURCE,
                "is_new_formula_universe": False,
            },
            {
                "task_id": "Q141-C0/C1/C2",
                "family_count": 6,
                "feature_count_raw": 27,
                "feature_count_exact_unique": 25,
                "grammar": "Coarse Q80-derived family aggregation, pair unions and current-state margin selector",
                "is_new_formula_universe": False,
            },
        ],
        "archive_lineage": [
            {"tasks": ["Q83", "Q86"], "archive_sha256": "4c79ac53c482a84a36f60b9823f2ad7c6dad69c75c7472fa760caf4f8c654b44", "status": "older source"},
            {"tasks": ["Q87", "Q88_metrics"], "archive_sha256": "3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed", "status": "older source"},
            {"tasks": ["Q88_checkpoint"], "archive_sha256": "e8d09197b2ee22f8355f84c22893bb72eeae4c14caf55342a1ed5fe681123011", "archive_blob_sha1": "1c9c3824d8caa3fe7d0e888c1875402cc2156a2a", "status": "manifest/checkpoint mismatch; do not pool"},
            {"tasks": ["Q90"], "archive_blob_sha1": "5d2efd70684e918b27d8f06386d545647898336d", "status": "older source"},
            {"tasks": ["Q91"], "archive_blob_sha1": "dc555356fe6543e17c3d7c91969da10491fe8b4e", "status": "older source"},
            {"tasks": ["Q92"], "archive_blob_sha1": "77ca692a6082809fcc6c471501617433ec7c36cf", "status": "older source; combinadic core only"},
            {"tasks": ["Q141-B1"], "archive_blob_sha1": archive_blob_sha, "status": "current eligible source prefix"},
        ],
        "deduplication_scope": {
            "proven_exact_aliases": ALIASES,
            "q80_q92_equal_weight_mean_grammars": "canonicalized exactly",
            "q89_extension": "no additional exact aliases asserted",
            "q90_interactions_and_gates": "pending typed AST import",
            "q7_candidate_quintet_grammar": "separate output type; pending AST import",
            "graph_field_and_other_operator_families": "not yet imported",
        },
        "governance": {
            "historical_blind_oos_is_not_virgin": True,
            "no_predictive_lift_claim": True,
            "no_auto_merge": True,
            "no_engine_promotion": True,
            "no_shadow_insertion": True,
            "no_archive_mutation": True,
            "protected_prs": [6, 7, 8],
        },
    }

def main():
    if not PREREG.is_file():
        raise SystemExit("Q141_B1_BLOCKED: preregistration file missing")
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg.get("task_id") != "Q141-B1" or prereg.get("status") != "PREREGISTERED_EXECUTION_PENDING":
        raise SystemExit("Q141_B1_BLOCKED: preregistration is not frozen and pending")
    raw_archive, archive_blob_sha, dates, draws, excluded = base.load_archive()
    if archive_blob_sha != prereg["source"]["git_blob_sha1"]:
        raise SystemExit("Q141_B1_BLOCKED: source archive hash differs from preregistration")
    target_count = len(draws) - base.MIN_HISTORY
    if target_count != prereg["walkforward"]["expected_targets"]:
        raise SystemExit("Q141_B1_BLOCKED: target count differs from preregistration")
    split_counts = Counter(base.split_name(offset, target_count) for offset in range(target_count))
    if dict(split_counts) != EXPECTED_SPLITS:
        raise SystemExit(f"Q141_B1_BLOCKED: split counts {dict(split_counts)}")
    raw_count = sum(math.comb(27, k) for k in range(1, 11))
    unique_count = unique_global_count(10)
    if raw_count != 16628808 or unique_count != 9808263:
        raise SystemExit("Q141_B1_BLOCKED: exact combinatorial count mismatch")
    samples = sample_formulas()
    sample_signatures = [canonicalize_formula(columns) for columns in samples]
    sample_unique = len({signature for signature, _ in sample_signatures})

    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    split_acc = {
        split: {
            "targets": 0, "alias_pair_checks": 0, "alias_mismatches": 0,
            "formula_score_comparisons": 0, "score_mismatches": 0,
            "rank_comparisons": 0, "rank_mismatches": 0,
            "max_abs_score_delta": 0.0,
            "legacy_numpy_score_mismatches": 0, "legacy_numpy_rank_mismatches": 0,
            "legacy_numpy_max_abs_score_delta": 0.0, "legacy_numpy_max_rank_displacement": 0,
            "legacy_numpy_max_flipped_pair_score_gap": 0.0,
            "raw_top5_hits": 0, "canonical_top5_hits": 0, "legacy_top5_hits": 0,
            "raw_top10_hits": 0, "canonical_top10_hits": 0, "legacy_top10_hits": 0,
            "raw_top20_hits": 0, "canonical_top20_hits": 0, "legacy_top20_hits": 0,
            "raw_rank_sum": 0.0, "canonical_rank_sum": 0.0, "legacy_rank_sum": 0.0,
        } for split in EXPECTED_SPLITS
    }
    ledger_rows = []
    total_alias_checks = 0
    total_alias_mismatches = 0
    total_score_comparisons = 0
    total_score_mismatches = 0
    total_rank_comparisons = 0
    total_rank_mismatches = 0
    total_legacy_numpy_score_mismatches = 0
    total_legacy_numpy_rank_mismatches = 0
    global_max_delta = 0.0
    global_legacy_numpy_max_delta = 0.0
    global_legacy_numpy_max_rank_displacement = 0
    global_legacy_numpy_max_flipped_pair_score_gap = 0.0

    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, target_count)
            features = base.feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists)
            aliases_ok = (
                np.array_equal(features[:, 0], features[:, 25])
                and np.array_equal(features[:, 1], features[:, 26])
            )
            alias_mismatches = 0 if aliases_ok else 1
            standardized = base.zscore_columns(features)
            standardized_aliases_ok = (
                np.array_equal(standardized[:, 0], standardized[:, 25])
                and np.array_equal(standardized[:, 1], standardized[:, 26])
            )
            if not standardized_aliases_ok:
                alias_mismatches += 1
            total_alias_checks += 2
            total_alias_mismatches += alias_mismatches
            acc = split_acc[split]
            acc["targets"] += 1
            acc["alias_pair_checks"] += 2
            acc["alias_mismatches"] += alias_mismatches
            target_score_mismatches = 0
            target_rank_mismatches = 0
            target_legacy_numpy_score_mismatches = 0
            target_legacy_numpy_rank_mismatches = 0
            target_max_delta = 0.0
            target_legacy_numpy_max_delta = 0.0
            target_legacy_numpy_max_rank_displacement = 0
            target_legacy_numpy_max_flipped_pair_score_gap = 0.0
            raw_hits = Counter()
            canonical_hits = Counter()
            legacy_hits = Counter()
            raw_rank_sum = 0.0
            canonical_rank_sum = 0.0
            legacy_rank_sum = 0.0
            for columns, (signature, scale) in zip(samples, sample_signatures):
                # Legacy NumPy mean is measured separately because near-ties can be
                # reordered by floating-point summation order despite equal scores.
                legacy_scores = standardized[:, list(columns)].mean(axis=1)
                raw_scores = stable_raw_scores(standardized, columns)
                canon_scores = canonical_scores(standardized, signature, scale)
                delta = float(np.max(np.abs(raw_scores - canon_scores)))
                legacy_delta = float(np.max(np.abs(legacy_scores - canon_scores)))
                target_max_delta = max(target_max_delta, delta)
                target_legacy_numpy_max_delta = max(target_legacy_numpy_max_delta, legacy_delta)
                global_max_delta = max(global_max_delta, delta)
                global_legacy_numpy_max_delta = max(global_legacy_numpy_max_delta, legacy_delta)
                score_ok = bool(np.allclose(raw_scores, canon_scores, rtol=0.0, atol=SCORE_TOLERANCE))
                legacy_score_ok = bool(np.allclose(legacy_scores, canon_scores, rtol=0.0, atol=SCORE_TOLERANCE))
                if not score_ok:
                    target_score_mismatches += 1
                if not legacy_score_ok:
                    target_legacy_numpy_score_mismatches += 1
                raw_ranks = base.rank_scores(raw_scores)
                canon_ranks = base.rank_scores(canon_scores)
                legacy_ranks = base.rank_scores(legacy_scores)
                rank_ok = bool(np.array_equal(raw_ranks, canon_ranks))
                legacy_rank_ok = bool(np.array_equal(legacy_ranks, canon_ranks))
                if not rank_ok:
                    target_rank_mismatches += 1
                if not legacy_rank_ok:
                    target_legacy_numpy_rank_mismatches += 1
                    pair_i, pair_j = np.triu_indices(40, 1)
                    legacy_order = legacy_scores[pair_i] >= legacy_scores[pair_j]
                    canonical_order = canon_scores[pair_i] >= canon_scores[pair_j]
                    flipped = legacy_order != canonical_order
                    if np.any(flipped):
                        legacy_gaps = np.abs(legacy_scores[pair_i[flipped]] - legacy_scores[pair_j[flipped]])
                        canonical_gaps = np.abs(canon_scores[pair_i[flipped]] - canon_scores[pair_j[flipped]])
                        gaps = np.maximum(legacy_gaps, canonical_gaps)
                        flip_gap = float(np.max(gaps))
                        target_legacy_numpy_max_flipped_pair_score_gap = max(target_legacy_numpy_max_flipped_pair_score_gap, flip_gap)
                        global_legacy_numpy_max_flipped_pair_score_gap = max(global_legacy_numpy_max_flipped_pair_score_gap, flip_gap)
                legacy_displacement = int(np.max(np.abs(legacy_ranks.astype(int) - canon_ranks.astype(int))))
                target_legacy_numpy_max_rank_displacement = max(target_legacy_numpy_max_rank_displacement, legacy_displacement)
                global_legacy_numpy_max_rank_displacement = max(global_legacy_numpy_max_rank_displacement, legacy_displacement)
                raw_metric = base.rank_metrics(raw_ranks, draw)
                canon_metric = base.rank_metrics(canon_ranks, draw)
                legacy_metric = base.rank_metrics(legacy_ranks, draw)
                for k in (5, 10, 20):
                    raw_hits[k] += raw_metric[f"top{k}_hits"]
                    canonical_hits[k] += canon_metric[f"top{k}_hits"]
                    legacy_hits[k] += legacy_metric[f"top{k}_hits"]
                raw_rank_sum += sum(int(raw_ranks[value]) for value in draw)
                canonical_rank_sum += sum(int(canon_ranks[value]) for value in draw)
                legacy_rank_sum += sum(int(legacy_ranks[value]) for value in draw)

            comparisons = len(samples)
            total_score_comparisons += comparisons
            total_rank_comparisons += comparisons
            total_score_mismatches += target_score_mismatches
            total_rank_mismatches += target_rank_mismatches
            total_legacy_numpy_score_mismatches += target_legacy_numpy_score_mismatches
            total_legacy_numpy_rank_mismatches += target_legacy_numpy_rank_mismatches
            acc["formula_score_comparisons"] += comparisons
            acc["score_mismatches"] += target_score_mismatches
            acc["rank_comparisons"] += comparisons
            acc["rank_mismatches"] += target_rank_mismatches
            acc["max_abs_score_delta"] = max(acc["max_abs_score_delta"], target_max_delta)
            acc["legacy_numpy_score_mismatches"] += target_legacy_numpy_score_mismatches
            acc["legacy_numpy_rank_mismatches"] += target_legacy_numpy_rank_mismatches
            acc["legacy_numpy_max_abs_score_delta"] = max(acc["legacy_numpy_max_abs_score_delta"], target_legacy_numpy_max_delta)
            acc["legacy_numpy_max_rank_displacement"] = max(acc["legacy_numpy_max_rank_displacement"], target_legacy_numpy_max_rank_displacement)
            acc["legacy_numpy_max_flipped_pair_score_gap"] = max(acc["legacy_numpy_max_flipped_pair_score_gap"], target_legacy_numpy_max_flipped_pair_score_gap)
            for k in (5, 10, 20):
                acc[f"raw_top{k}_hits"] += raw_hits[k]
                acc[f"canonical_top{k}_hits"] += canonical_hits[k]
                acc[f"legacy_top{k}_hits"] += legacy_hits[k]
            acc["raw_rank_sum"] += raw_rank_sum
            acc["canonical_rank_sum"] += canonical_rank_sum
            acc["legacy_rank_sum"] += legacy_rank_sum
            ledger_rows.append({
                "target_index": i,
                "target_offset": offset,
                "target_date": dates[i],
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "split": split,
                "actual_quintet": " ".join(str(x + 1) for x in draw),
                "alias_freq5_recent5_equal": int(np.array_equal(features[:, 0], features[:, 25])),
                "alias_freq10_recent10_equal": int(np.array_equal(features[:, 1], features[:, 26])),
                "standardized_aliases_equal": int(standardized_aliases_ok),
                "formula_sample_count": comparisons,
                "stable_raw_vs_canonical_score_mismatches": target_score_mismatches,
                "stable_raw_vs_canonical_rank_mismatches": target_rank_mismatches,
                "legacy_numpy_score_mismatches": target_legacy_numpy_score_mismatches,
                "legacy_numpy_rank_mismatches": target_legacy_numpy_rank_mismatches,
                "stable_raw_vs_canonical_max_abs_score_delta": f"{target_max_delta:.17g}",
                "legacy_numpy_max_abs_score_delta": f"{target_legacy_numpy_max_delta:.17g}",
                "legacy_numpy_max_rank_displacement": target_legacy_numpy_max_rank_displacement,
                "legacy_numpy_max_flipped_pair_score_gap": f"{target_legacy_numpy_max_flipped_pair_score_gap:.17g}",
                "stable_raw_top5_hit_share": f"{raw_hits[5] / (5 * comparisons):.12g}",
                "canonical_top5_hit_share": f"{canonical_hits[5] / (5 * comparisons):.12g}",
                "legacy_numpy_top5_hit_share": f"{legacy_hits[5] / (5 * comparisons):.12g}",
                "stable_raw_top10_hit_share": f"{raw_hits[10] / (5 * comparisons):.12g}",
                "canonical_top10_hit_share": f"{canonical_hits[10] / (5 * comparisons):.12g}",
                "legacy_numpy_top10_hit_share": f"{legacy_hits[10] / (5 * comparisons):.12g}",
                "stable_raw_top20_hit_share": f"{raw_hits[20] / (5 * comparisons):.12g}",
                "canonical_top20_hit_share": f"{canonical_hits[20] / (5 * comparisons):.12g}",
                "legacy_numpy_top20_hit_share": f"{legacy_hits[20] / (5 * comparisons):.12g}",
            })
        # Strict-prior state update: target i is appended only after all its formulas are scored.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    if len(ledger_rows) != target_count:
        raise SystemExit("Q141_B1_BLOCKED: target ledger incomplete")
    if total_alias_mismatches or total_score_mismatches or total_rank_mismatches:
        raise SystemExit(
            "Q141_B1_BLOCKED: alias/score/rank invariance failure "
            f"{total_alias_mismatches}/{total_score_mismatches}/{total_rank_mismatches}"
        )

    split_metrics = {}
    for split, acc in split_acc.items():
        targets = acc["targets"]
        denom = 5 * targets * len(samples)
        split_metrics[split] = {
            "targets": targets,
            "alias_pair_checks": acc["alias_pair_checks"],
            "alias_mismatches": acc["alias_mismatches"],
            "formula_score_comparisons": acc["formula_score_comparisons"],
            "score_mismatches": acc["score_mismatches"],
            "rank_comparisons": acc["rank_comparisons"],
            "rank_mismatches": acc["rank_mismatches"],
            "max_abs_score_delta": acc["max_abs_score_delta"],
            "legacy_numpy_score_mismatches": acc["legacy_numpy_score_mismatches"],
            "legacy_numpy_rank_mismatches": acc["legacy_numpy_rank_mismatches"],
            "legacy_numpy_max_abs_score_delta": acc["legacy_numpy_max_abs_score_delta"],
            "legacy_numpy_max_rank_displacement": acc["legacy_numpy_max_rank_displacement"],
            "legacy_numpy_max_flipped_pair_score_gap": acc["legacy_numpy_max_flipped_pair_score_gap"],
            "stable_raw_mean_top5_hit_share": acc["raw_top5_hits"] / denom,
            "canonical_mean_top5_hit_share": acc["canonical_top5_hits"] / denom,
            "legacy_numpy_mean_top5_hit_share": acc["legacy_top5_hits"] / denom,
            "stable_raw_mean_top10_hit_share": acc["raw_top10_hits"] / denom,
            "canonical_mean_top10_hit_share": acc["canonical_top10_hits"] / denom,
            "legacy_numpy_mean_top10_hit_share": acc["legacy_top10_hits"] / denom,
            "stable_raw_mean_top20_hit_share": acc["raw_top20_hits"] / denom,
            "canonical_mean_top20_hit_share": acc["canonical_top20_hits"] / denom,
            "legacy_numpy_mean_top20_hit_share": acc["legacy_top20_hits"] / denom,
            "stable_raw_mean_actual_rank": acc["raw_rank_sum"] / (targets * len(samples) * 5),
            "canonical_mean_actual_rank": acc["canonical_rank_sum"] / (targets * len(samples) * 5),
            "legacy_numpy_mean_actual_rank": acc["legacy_rank_sum"] / (targets * len(samples) * 5),
            "uniform_reference": {"top5": 0.125, "top10": 0.25, "top20": 0.5, "mean_actual_rank": 20.5},
        }

    nominal_by_size = []
    for k in range(1, 11):
        nominal = math.comb(27, k)
        canonical = unique_within_size(k)
        nominal_by_size.append({
            "formula_size": k,
            "nominal_raw_count": nominal,
            "unique_canonical_count_within_size": canonical,
            "raw_alias_redundancy": nominal - canonical,
        })
    nominal_total = sum(row["nominal_raw_count"] for row in nominal_by_size)
    per_size_unique_total = sum(row["unique_canonical_count_within_size"] for row in nominal_by_size)
    global_unique = unique_global_count(10)
    registry = build_registry(archive_blob_sha, dates)
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-B1",
        "status": "EXACT_ALIAS_CANONICALIZATION_PASS_WITH_LEGACY_NUMERICAL_TIE_SENSITIVITY",
        "decision": "EXACT_ALIAS_COLLAPSE_CONFIRMED; LEGACY_NUMPY_RANKING_HAS_FLOATING_TIE_SENSITIVITY",
        "hypothesis": "Exact aliases and multiplicity-preserving weighted-mean canonicalization reduce the combined k=1..10 Q80 formula ID universe by 41.0164%; stable raw and canonical scores/ranks are invariant, while legacy NumPy mean ranks are separately audited for floating-point tie sensitivity.",
        "source": {
            "archive_path": "data/storico_daily.csv",
            "archive_git_blob_sha1": archive_blob_sha,
            "eligible_draws": len(draws),
            "cutoff": dates[-1],
            "excluded_rows_after_cutoff": excluded,
            "contest_315_excluded": True,
            "main_commit_at_registration": "70dcf8cc128884d9739959406d5662ef76daa253",
        },
        "formula_universe": {
            "feature_count_raw": 27,
            "feature_count_exact_unique": 25,
            "exact_aliases": ALIASES,
            "formula_sizes": list(range(1, 11)),
            "nominal_raw_formula_count": nominal_total,
            "unique_canonical_formula_count": global_unique,
            "redundant_raw_formula_count": nominal_total - global_unique,
            "reduction_percent": 100.0 * (nominal_total - global_unique) / nominal_total,
            "sum_of_within_size_unique_counts": per_size_unique_total,
            "cross_size_equivalences": per_size_unique_total - global_unique,
            "counts_by_size": nominal_by_size,
            "sample_formula_instances": len(samples),
            "sample_unique_canonical_ids": sample_unique,
        },
        "walkforward": {
            "targets": target_count,
            "minimum_prior_history": base.MIN_HISTORY,
            "split_counts": dict(split_counts),
            "strict_prior": True,
            "update_order": "score target before appending target to occurrence/pair state",
            "alias_pair_checks": total_alias_checks,
            "alias_mismatches": total_alias_mismatches,
            "formula_score_comparisons": total_score_comparisons,
            "score_mismatches": total_score_mismatches,
            "rank_comparisons": total_rank_comparisons,
            "rank_mismatches": total_rank_mismatches,
            "score_abs_tolerance": SCORE_TOLERANCE,
            "max_abs_score_delta": global_max_delta,
            "legacy_numpy_score_mismatches": total_legacy_numpy_score_mismatches,
            "legacy_numpy_rank_mismatches": total_legacy_numpy_rank_mismatches,
            "legacy_numpy_rank_mismatch_rate": total_legacy_numpy_rank_mismatches / total_rank_comparisons,
            "legacy_numpy_max_abs_score_delta": global_legacy_numpy_max_delta,
            "legacy_numpy_max_rank_displacement": global_legacy_numpy_max_rank_displacement,
            "legacy_numpy_max_flipped_pair_score_gap": global_legacy_numpy_max_flipped_pair_score_gap,
            "legacy_numpy_note": "Legacy NumPy mean is compared with stable canonical math.fsum evaluation. Small score differences can change exact lexicographic ranks for near-ties; this is an implementation sensitivity, not evidence of different mathematical functions.",
            "metrics_by_split": split_metrics,
        },
        "statistical_inference": {
            "p_values": "not applicable: exact combinatorial count and deterministic algebraic/property identity",
            "multiple_testing": "not applicable; no stochastic significance tests or candidate selection",
            "predictive_lift_claim": False,
        },
        "acceptance": {
            "archive_blob_verified": True,
            "target_and_split_counts_verified": dict(split_counts) == EXPECTED_SPLITS,
            "exact_alias_columns_verified": total_alias_mismatches == 0,
            "sampled_stable_raw_vs_canonical_scores_verified": total_score_mismatches == 0,
            "sampled_stable_raw_vs_canonical_ranks_verified": total_rank_mismatches == 0,
            "legacy_numpy_tie_sensitivity_measured": True,
            "legacy_numpy_rank_mismatch_count": total_legacy_numpy_rank_mismatches,
            "exact_formula_counts_verified": nominal_total == 16628808 and global_unique == 9808263,
            "future_suffix_invariance": "covered by dedicated synthetic unit test",
            "deterministic_sample_and_stable_sum_replay": "covered by exact source pin, deterministic sample seed and unit tests",
        },
        "limitations": [
            "The exact reduction applies only to equal-weight subset formulas over the 27 Q80 columns and the two source-proven exact aliases.",
            "Multiplicity is preserved; naive deletion of alias columns would change some formula weights.",
            "No exact semantic aliases are asserted for the 32 Q89 extension features.",
            "Q90 interactions/gates, Q7 candidate-quintet formulas and graph/field operator families require separate typed AST definitions.",
            "Historical Blind OOS is exposed research history, not virgin prospective evidence.",
            "Legacy NumPy mean and stable math.fsum can differ by tiny floating-point amounts; the first walk-forward attempt found 2,311 sampled target-formula rank differences despite score differences within tolerance. Stable raw and canonical summation is therefore the mathematical identity reference; no production ranker is changed by this experiment.",
            "The sampled walk-forward validates implementation invariance; it does not exhaustively rescore all 16,628,808 raw formula IDs.",
            "No predictive improvement or formula-selection advantage is claimed.",
        ],
        "recovery_history": [
            {"run_id": 43222532830, "head_sha": "ac1d1e5d06977dc74d68d7e666b66c31c2e6fa08", "failure": "Synthetic test initially generated independent values for the two source-proven alias columns; fixture corrected to enforce alias equality.", "recovery": "Updated synthetic fixture; all seven unit tests passed on the next run."},
            {"run_id": 43222764935, "head_sha": "d13261bfd593b08f4417af377e605c5466fa35c1", "failure": "0 alias mismatches and 0 score mismatches, but 2,311 raw NumPy-versus-canonical rank mismatches.", "root_cause": "Floating-point summation order changed exact ranks for near-tied scores even though absolute score differences remained within 1e-12.", "recovery": "Separate stable raw and canonical math.fsum evaluations from legacy NumPy ranking; preserve and report legacy rank sensitivity rather than treating it as mathematical non-equivalence."}
        ],
        "next_action": "Audit Q80 legacy tie policy before any canonical evaluator could replace it; then import Q90 interaction/gate ASTs and Q7 candidate-quintet AST as separate output types and reconcile source archives before a common-source behaviour atlas.",
        "target_ledger": str(LEDGER.relative_to(ROOT)),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    with REGISTRY.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(registry, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with REPORT.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    fields = list(ledger_rows[0])
    with LEDGER.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger_rows)
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-B1",
        "status": "REPLAYABLE_EXPLORATORY_BUNDLE",
        "source_archive_git_blob_sha1": archive_blob_sha,
        "eligible_draws": len(draws),
        "cutoff": dates[-1],
        "target_rows": len(ledger_rows),
        "split_counts": dict(split_counts),
        "raw_formula_count": nominal_total,
        "canonical_formula_count": global_unique,
        "redundant_formula_count": nominal_total - global_unique,
        "sample_formula_instances": len(samples),
        "score_comparisons": total_score_comparisons,
        "rank_comparisons": total_rank_comparisons,
        "legacy_numpy_score_mismatches": total_legacy_numpy_score_mismatches,
        "legacy_numpy_rank_mismatches": total_legacy_numpy_rank_mismatches,
        "registry_path": str(REGISTRY.relative_to(ROOT)),
        "registry_sha256": sha256_file(REGISTRY),
        "report_path": str(REPORT.relative_to(ROOT)),
        "report_sha256": sha256_file(REPORT),
        "target_ledger_path": str(LEDGER.relative_to(ROOT)),
        "target_ledger_sha256": sha256_file(LEDGER),
        "runner_path": str(Path(__file__).relative_to(ROOT)),
        "runner_sha256": sha256_file(Path(__file__)),
        "preregistration_sha256": sha256_file(PREREG),
        "decision": report["decision"],
    }
    with MANIFEST.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-B1",
        "status": "COMPLETE_PENDING_CI_AND_EXACT_GIT_READBACK",
        "manifest_sha256": sha256_file(MANIFEST),
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "next_action": report["next_action"],
    }
    with CHECKPOINT.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(checkpoint, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps({
        "task_id": "Q141-B1",
        "status": report["status"],
        "raw_formula_count": nominal_total,
        "canonical_formula_count": global_unique,
        "reduction_percent": report["formula_universe"]["reduction_percent"],
        "targets": target_count,
        "sample_formula_instances": len(samples),
        "score_mismatches": total_score_mismatches,
        "rank_mismatches": total_rank_mismatches,
        "legacy_numpy_rank_mismatches": total_legacy_numpy_rank_mismatches,
        "max_abs_score_delta": global_max_delta,
        "manifest_sha256": sha256_file(MANIFEST),
    }, sort_keys=True))

if __name__ == "__main__":
    main()
