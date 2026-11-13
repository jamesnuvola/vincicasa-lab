#!/usr/bin/env python3
"""Q141-D4: pre-target family-consensus state under inter-family disagreement."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

Q90_ZIP_SHA256 = "12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077"
A6_ZIP_SHA256 = "e139ed4587f04ae584c12bff76bcbf49d7cd397d41d7fde5a159cc487570ea3fc"
MATRIX_SHA256 = "681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49"
FEATURE_CATALOG_SHA256 = "0761324a35faade5e7dc9a053d19146f21d349ba9e8237b334691c6b1e5517a5"
A6_LEDGER_SHA256 = "3db21ad7a0d94f3d07f437865282ed306d0a022d9f313095fa4bedbb66d5b32b"
WINDOW = 100
BLOCK = 20
BOOTSTRAPS = 20000
RANDOMIZATIONS = 20000
SEED = 14120261113
UNIFORM_EXPECTED_HITS = 0.625
PRACTICAL_THRESHOLD = 0.025
SPLIT_COUNTS = {"discovery": 2011, "validation": 670, "blind_oos": 670}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def build_family_groups(feature_names: list[str], family_map: dict[str, str]) -> dict[str, list[int]]:
    names = list(feature_names)
    if len(names) != 59 or len(set(names)) != 59:
        raise ValueError("expected 59 unique feature names")
    unknown = set(family_map) - set(names)
    if unknown:
        raise ValueError(f"family map contains unknown features: {sorted(unknown)}")
    groups: dict[str, list[int]] = {}
    baseline = [i for i, name in enumerate(names) if name not in family_map]
    groups["baseline_legacy"] = baseline
    for family in [
        "ewma_hit_dynamics", "gap_dynamics", "cooccurrence_novelty",
        "rank_trajectory", "residual_surprise", "regime_transition_affinity"
    ]:
        groups[family] = [i for i, name in enumerate(names) if family_map.get(name) == family]
    flattened = [i for indices in groups.values() for i in indices]
    if sorted(flattened) != list(range(59)) or len(flattened) != len(set(flattened)):
        raise ValueError("feature groups must partition all 59 columns exactly once")
    if any(not indices for indices in groups.values()):
        raise ValueError("empty feature family")
    return groups


def top5_from_scores(scores: np.ndarray) -> np.ndarray:
    x = np.asarray(scores, dtype=np.float64)
    if x.shape != (40,) or not np.isfinite(x).all():
        raise ValueError("expected 40 finite candidate scores")
    numbers = np.arange(1, 41)
    return np.lexsort((numbers, -np.round(x, 12)))[:5] + 1


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    sa, sb = set(map(int, a)), set(map(int, b))
    if not sa or not sb:
        raise ValueError("Jaccard sets must be non-empty")
    return len(sa & sb) / len(sa | sb)


def target_family_state(row: np.ndarray, groups: dict[str, list[int]]):
    x = np.asarray(row, dtype=np.float64)
    if x.shape != (40, 59) or not np.isfinite(x).all():
        raise ValueError("expected finite 40x59 feature row")
    family_names = list(groups)
    family_scores = np.stack([x[:, groups[name]].mean(axis=1) for name in family_names], axis=0)
    family_top5 = [top5_from_scores(family_scores[i]) for i in range(len(family_names))]
    pairwise = [
        jaccard(family_top5[i], family_top5[j])
        for i in range(len(family_top5)) for j in range(i + 1, len(family_top5))
    ]
    agreement = float(np.mean(pairwise))
    equal_family_score = family_scores.mean(axis=0)
    equal_family_top5 = top5_from_scores(equal_family_score)
    votes = np.zeros(40, dtype=np.int64)
    for selected in family_top5:
        votes[np.asarray(selected, dtype=int) - 1] += 1
    numbers = np.arange(1, 41)
    consensus_top5 = np.lexsort((
        numbers,
        -np.round(equal_family_score, 12),
        -votes
    ))[:5] + 1
    equal59_top5 = top5_from_scores(x.mean(axis=1))
    return {
        "family_scores": family_scores,
        "family_top5": family_top5,
        "agreement": agreement,
        "equal_family_top5": equal_family_top5,
        "consensus_top5": consensus_top5,
        "equal59_top5": equal59_top5,
        "votes": votes,
    }


def build_disagreement_state(agreement: np.ndarray, window: int = WINDOW):
    a = np.asarray(agreement, dtype=np.float64)
    thresholds = np.full(len(a), np.nan, dtype=np.float64)
    state = np.full(len(a), -1, dtype=np.int8)
    for t in range(window, len(a)):
        thresholds[t] = float(np.median(a[t-window:t]))
        state[t] = int(a[t] < thresholds[t])
    return thresholds, state


def count_hits(top5: np.ndarray, actual: np.ndarray) -> int:
    return int(len(set(map(int, top5)) & set(map(int, actual))))


def hypergeom_5of40_pmf() -> np.ndarray:
    from math import comb
    den = comb(40, 5)
    p = np.array([comb(5, k) * comb(35, 5-k) / den for k in range(6)], dtype=np.float64)
    if abs(float(p.sum()) - 1.0) > 1e-14:
        raise AssertionError("hypergeometric PMF does not sum to one")
    return p


def exact_uniform_upper_tail(total_hits: int, targets: int) -> float:
    pmf = hypergeom_5of40_pmf()
    dist = np.array([1.0], dtype=np.float64)
    for _ in range(targets):
        dist = np.convolve(dist, pmf)
    if total_hits < 0 or total_hits >= len(dist):
        raise ValueError("observed hit total outside exact support")
    return float(dist[total_hits:].sum())


def circular_block_bootstrap(values: np.ndarray, state: np.ndarray | None,
                             replicates: int = BOOTSTRAPS, block: int = BLOCK,
                             seed: int = SEED, estimand: str = "mean") -> list[float]:
    y = np.asarray(values, dtype=np.float64)
    h = None if state is None else np.asarray(state, dtype=np.int8)
    n = len(y)
    if n == 0 or (h is not None and len(h) != n):
        raise ValueError("invalid bootstrap inputs")
    rng = np.random.default_rng(seed)
    nblocks = int(math.ceil(n / block))
    starts_all = rng.integers(0, n, size=(replicates, nblocks))
    offsets = np.arange(block, dtype=np.int64)
    effects = np.empty(replicates, dtype=np.float64)
    for b in range(replicates):
        idx = ((starts_all[b, :, None] + offsets[None, :]) % n).reshape(-1)[:n]
        yb = y[idx]
        if estimand == "mean":
            effects[b] = float(yb.mean())
        elif estimand == "high_minus_low":
            hb = h[idx]
            if int(hb.sum()) == 0 or int(hb.sum()) == len(hb):
                effects[b] = np.nan
            else:
                effects[b] = float(yb[hb == 1].mean() - yb[hb == 0].mean())
        else:
            raise ValueError("unknown estimand")
    effects = effects[np.isfinite(effects)]
    if len(effects) < int(replicates * 0.99):
        raise RuntimeError("too many degenerate bootstrap replicates")
    return [float(v) for v in np.quantile(effects, [0.025, 0.975])]


def circular_shift_p(values: np.ndarray, state: np.ndarray,
                     replicates: int = RANDOMIZATIONS, seed: int = SEED + 1) -> float:
    y = np.asarray(values, dtype=np.float64)
    h = np.asarray(state, dtype=np.int8)
    observed = abs(float(y[h == 1].mean() - y[h == 0].mean()))
    rng = np.random.default_rng(seed)
    shifts = rng.integers(1, len(y), size=replicates)
    extreme = 0
    for shift in shifts:
        shifted = np.roll(h, int(shift))
        if shifted.min() == shifted.max():
            continue
        effect = abs(float(y[shifted == 1].mean() - y[shifted == 0].mean()))
        if effect >= observed - 1e-15:
            extreme += 1
    return float((extreme + 1) / (replicates + 1))


def block_signflip_p(values: np.ndarray, replicates: int = RANDOMIZATIONS,
                     block: int = BLOCK, seed: int = SEED + 2) -> float:
    y = np.asarray(values, dtype=np.float64)
    blocks = np.array_split(np.arange(len(y)), int(math.ceil(len(y) / block)))
    sums = np.array([float(y[idx].sum()) for idx in blocks], dtype=np.float64)
    observed = abs(float(y.mean()))
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(replicates, len(sums)))
    simulated = np.abs(signs @ sums / len(y))
    extreme = int(np.count_nonzero(simulated >= observed - 1e-15))
    return float((extreme + 1) / (replicates + 1))


def holm_adjust(p_values: list[float]) -> list[float]:
    p = np.asarray(p_values, dtype=np.float64)
    order = np.argsort(p)
    adjusted = np.empty(len(p), dtype=np.float64)
    running = 0.0
    m = len(p)
    for rank, idx in enumerate(order):
        running = max(running, (m-rank) * float(p[idx]))
        adjusted[idx] = min(1.0, running)
    return [float(v) for v in adjusted]


def load_inputs(q90_zip: Path, a6_zip: Path):
    q90_bytes = q90_zip.read_bytes()
    a6_bytes = a6_zip.read_bytes()
    if sha256_bytes(q90_bytes) != Q90_ZIP_SHA256:
        raise ValueError("Q90 artifact ZIP SHA-256 mismatch")
    if sha256_bytes(a6_bytes) != A6_ZIP_SHA256:
        raise ValueError("A6 artifact ZIP SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(q90_bytes)) as zq, zipfile.ZipFile(io.BytesIO(a6_bytes)) as za:
        matrix_bytes = zq.read("adaptive_novelty_feature_matrix.npz")
        catalog_bytes = zq.read("adaptive_novelty_feature_catalog.json")
        ledger_bytes = za.read("q141_a6_target_ledger_2026-11-13.csv")
        a6_manifest = json.loads(za.read("q141_a6_full59_covering_manifest_2026-11-13.json"))
        a6_report = json.loads(za.read("q141_a6_full59_covering_report_2026-11-13.json"))
        if sha256_bytes(matrix_bytes) != MATRIX_SHA256:
            raise ValueError("Q90 matrix member SHA-256 mismatch")
        if sha256_bytes(catalog_bytes) != FEATURE_CATALOG_SHA256:
            raise ValueError("Q89 feature catalog SHA-256 mismatch")
        if sha256_bytes(ledger_bytes) != A6_LEDGER_SHA256:
            raise ValueError("A6 target ledger SHA-256 mismatch")
        if a6_manifest["source_artifact_sha256"] != Q90_ZIP_SHA256:
            raise ValueError("A6 manifest does not pin the Q90 artifact")
        if a6_report["source"]["q90_archive_blob_sha1"] != "5d2efd70684e918b27d8f06386d545647898336d":
            raise ValueError("Q90 archive lineage mismatch")
        npz = np.load(io.BytesIO(matrix_bytes), allow_pickle=False)
        matrix = npz["feature_matrix"]
        dates = npz["target_dates"].astype(str)
        cutoffs = npz["cutoff_dates"].astype(str)
        actual = npz["actual_quintets"].astype(np.int64)
        feature_names = npz["feature_names"].astype(str).tolist()
        archive_blob = str(npz["archive_blob_sha"].item())
        feature_catalog = json.loads(catalog_bytes)
        ledger = pd.read_csv(io.BytesIO(ledger_bytes))
    if matrix.shape != (3351, 40, 59) or matrix.dtype != np.float32:
        raise ValueError("unexpected Q90 matrix shape/dtype")
    if not np.isfinite(matrix).all():
        raise ValueError("non-finite feature matrix")
    if archive_blob != "5d2efd70684e918b27d8f06386d545647898336d":
        raise ValueError("matrix archive blob mismatch")
    if len(ledger) != len(matrix):
        raise ValueError("Q90/A6 target count mismatch")
    ledger_dates = ledger["target_date"].astype(str).to_numpy()
    ledger_cutoffs = ledger["cutoff_date"].astype(str).to_numpy()
    ledger_actual = np.array([[int(v) for v in str(s).split()] for s in ledger["actual_quintet"]], dtype=np.int64)
    if not np.array_equal(dates, ledger_dates):
        raise ValueError("target dates do not align")
    if not np.array_equal(cutoffs, ledger_cutoffs):
        raise ValueError("cutoff dates do not align")
    if not np.array_equal(actual, ledger_actual):
        raise ValueError("actual quintets do not align")
    if not np.all(cutoffs < dates):
        raise ValueError("cutoff must strictly precede target")
    if not np.array_equal(ledger["prior_draws"].to_numpy(dtype=int), np.arange(len(ledger)) + 50):
        raise ValueError("prior draw counts do not reconcile")
    if ledger["split"].value_counts().to_dict() != SPLIT_COUNTS:
        raise ValueError("unexpected chronological split counts")
    if feature_catalog["formula_search_matrix"]["normalization"] != "per-target feature z-score across the 40 candidate numbers; strictly prior-only":
        raise ValueError("feature matrix normalization/lineage mismatch")
    groups = build_family_groups(feature_names, feature_catalog["new_feature_family_map"])
    return matrix, dates, cutoffs, actual, ledger, feature_names, groups, {
        "q90_zip_sha256": Q90_ZIP_SHA256,
        "a6_zip_sha256": A6_ZIP_SHA256,
        "matrix_sha256": MATRIX_SHA256,
        "feature_catalog_sha256": FEATURE_CATALOG_SHA256,
        "a6_ledger_sha256": A6_LEDGER_SHA256,
        "q90_archive_blob_sha1": archive_blob,
        "matrix_shape": list(matrix.shape),
        "matrix_dtype": str(matrix.dtype),
        "feature_count": len(feature_names),
        "family_counts": {name: len(indices) for name, indices in groups.items()},
        "q90_archive_cutoff": "2026-11-07",
        "q90_archive_draws": 3401,
        "main_archive_suffix_excluded": 5,
    }


def analyse(q90_zip: Path, a6_zip: Path, output_dir: Path, preregistration: Path):
    matrix, dates, cutoffs, actual, ledger, feature_names, groups, source = load_inputs(q90_zip, a6_zip)
    n = len(matrix)
    family_agreement = np.empty(n, dtype=np.float64)
    consensus_top5 = np.empty((n, 5), dtype=np.int64)
    equal_family_top5 = np.empty((n, 5), dtype=np.int64)
    equal59_top5 = np.empty((n, 5), dtype=np.int64)
    for t in range(n):
        result = target_family_state(matrix[t], groups)
        family_agreement[t] = result["agreement"]
        consensus_top5[t] = result["consensus_top5"]
        equal_family_top5[t] = result["equal_family_top5"]
        equal59_top5[t] = result["equal59_top5"]
    thresholds, state = build_disagreement_state(family_agreement)
    hits_consensus = np.array([count_hits(consensus_top5[t], actual[t]) for t in range(n)], dtype=np.int8)
    hits_equal_family = np.array([count_hits(equal_family_top5[t], actual[t]) for t in range(n)], dtype=np.int8)
    hits_equal59 = np.array([count_hits(equal59_top5[t], actual[t]) for t in range(n)], dtype=np.int8)
    delta = hits_consensus.astype(np.float64) - hits_equal_family.astype(np.float64)
    delta_equal59 = hits_consensus.astype(np.float64) - hits_equal59.astype(np.float64)
    valid = np.arange(n) >= WINDOW
    split = ledger["split"].astype(str).to_numpy()
    evaluated = {}
    for name in ["discovery", "validation", "blind_oos"]:
        mask = valid & (split == name)
        h = state[mask]
        d = delta[mask]
        evaluated[name] = {
            "targets": int(mask.sum()),
            "high_disagreement_targets": int((h == 1).sum()),
            "low_disagreement_targets": int((h == 0).sum()),
            "mean_family_jaccard": float(family_agreement[mask].mean()),
            "consensus_mean_hits": float(hits_consensus[mask].mean()),
            "equal_family_mean_hits": float(hits_equal_family[mask].mean()),
            "equal59_mean_hits": float(hits_equal59[mask].mean()),
            "uniform_expected_hits": UNIFORM_EXPECTED_HITS,
            "consensus_minus_equal_family_mean_hits": float(d.mean()),
            "consensus_minus_equal59_mean_hits": float(delta_equal59[mask].mean()),
            "consensus_vs_uniform_mean_hits": float(hits_consensus[mask].mean() - UNIFORM_EXPECTED_HITS),
            "paired_delta_high_mean": float(d[h == 1].mean()),
            "paired_delta_low_mean": float(d[h == 0].mean()),
            "high_minus_low_paired_delta": float(d[h == 1].mean() - d[h == 0].mean()),
        }
    blind = valid & (split == "blind_oos")
    y = delta[blind]
    h = state[blind]
    hc = hits_consensus[blind]
    primary_effect = float(y[h == 1].mean() - y[h == 0].mean())
    secondary_effect = float(y.mean())
    tertiary_effect = float(hc.mean() - UNIFORM_EXPECTED_HITS)
    primary_ci = circular_block_bootstrap(y, h, estimand="high_minus_low", seed=SEED + 10)
    secondary_ci = circular_block_bootstrap(y, None, estimand="mean", seed=SEED + 11)
    tertiary_ci = circular_block_bootstrap(hc.astype(np.float64) - UNIFORM_EXPECTED_HITS, None,
                                           estimand="mean", seed=SEED + 12)
    p_primary = circular_shift_p(y, h, seed=SEED + 20)
    p_secondary = block_signflip_p(y, seed=SEED + 21)
    p_tertiary = exact_uniform_upper_tail(int(hc.sum()), len(hc))
    raw_p = [p_primary, p_secondary, p_tertiary]
    adjusted = holm_adjust(raw_p)
    accepted = (
        primary_effect >= PRACTICAL_THRESHOLD
        and primary_ci[0] > 0
        and adjusted[0] < 0.05
    )
    split_summary = evaluated
    family_hit_means = {}
    blind_mask = blind
    for name, indices in groups.items():
        group_scores = matrix[:, :, indices].mean(axis=2)
        group_top = np.stack([top5_from_scores(group_scores[t]) for t in range(n)])
        group_hits = np.array([count_hits(group_top[t], actual[t]) for t in range(n)])
        family_hit_means[name] = {
            split: float(group_hits[valid & (ledger["split"].astype(str).to_numpy() == split)].mean())
            for split in ["discovery", "validation", "blind_oos"]
        }

    mutation_checks = []
    check_targets = [100, 250, 1000, 2000, 3000, 3350]
    for t in check_targets:
        original = target_family_state(matrix[t], groups)
        prev_agreement = np.array([
            target_family_state(matrix[j], groups)["agreement"] for j in range(t-WINDOW, t)
        ])
        original_threshold = float(np.median(prev_agreement))
        altered = matrix.copy()
        altered[t+1:] = 0.0
        changed = target_family_state(altered[t], groups)
        changed_prev = np.array([
            target_family_state(altered[j], groups)["agreement"] for j in range(t-WINDOW, t)
        ])
        changed_threshold = float(np.median(changed_prev))
        mutation_checks.append({
            "target_index": t,
            "agreement_unchanged": abs(changed["agreement"] - original["agreement"]) < 1e-15,
            "threshold_unchanged": abs(changed_threshold - original_threshold) < 1e-15,
            "consensus_top5_unchanged": bool(np.array_equal(changed["consensus_top5"], original["consensus_top5"])),
            "equal_family_top5_unchanged": bool(np.array_equal(changed["equal_family_top5"], original["equal_family_top5"])),
        })
    if not all(all(v for k, v in row.items() if k != "target_index") for row in mutation_checks):
        raise RuntimeError("future-suffix mutation invariance failed")

    target_ledger = pd.DataFrame({
        "target_index": np.arange(n),
        "target_date": dates,
        "cutoff_date": cutoffs,
        "prior_draws": ledger["prior_draws"].to_numpy(dtype=int),
        "split": split,
        "actual_quintet": [" ".join(map(str, row)) for row in actual],
        "family_agreement_mean_jaccard": family_agreement,
        "prior100_agreement_median": thresholds,
        "high_disagreement_state": [None if v < 0 else int(v) for v in state],
        "consensus_top5": [" ".join(map(str, row)) for row in consensus_top5],
        "equal_family_top5": [" ".join(map(str, row)) for row in equal_family_top5],
        "equal59_top5": [" ".join(map(str, row)) for row in equal59_top5],
        "consensus_hits": hits_consensus,
        "equal_family_hits": hits_equal_family,
        "equal59_hits": hits_equal59,
        "consensus_minus_equal_family_hits": delta,
        "consensus_minus_equal59_hits": delta_equal59,
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "q141_d4_family_consensus_state_target_ledger_2026-11-13.csv"
    target_ledger.to_csv(ledger_path, index=False, float_format="%.12g", lineterminator="\n")

    endpoints = [
        {"id": "D4_T1", "endpoint": "high_disagreement_minus_low_disagreement_paired_hit_delta",
         "effect": primary_effect, "ci95_circular_block_bootstrap": primary_ci,
         "p_raw": p_primary, "practical_threshold_hits_per_target": PRACTICAL_THRESHOLD},
        {"id": "D4_T2", "endpoint": "unconditional_consensus_minus_equal_family_mean_hits",
         "effect": secondary_effect, "ci95_circular_block_bootstrap": secondary_ci,
         "p_raw": p_secondary, "practical_threshold_hits_per_target": PRACTICAL_THRESHOLD},
        {"id": "D4_T3", "endpoint": "consensus_mean_hits_minus_exact_uniform_expectation",
         "effect": tertiary_effect, "ci95_circular_block_bootstrap": tertiary_ci,
         "p_raw": p_tertiary, "exact_null": "sum of 670 Hypergeometric(40,5,5) outcomes",
         "uniform_expected_hits": UNIFORM_EXPECTED_HITS},
    ]
    for row, adj in zip(endpoints, adjusted):
        row["p_holm"] = float(adj)
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-D4",
        "status": "COMPLETED_HISTORICAL_WALK_FORWARD",
        "decision": "FAMILY_CONSENSUS_LIFT_DEMONSTRATED" if accepted else "NO_FAMILY_CONSENSUS_CONDITIONAL_LIFT_DEMONSTRATED",
        "hypothesis": {
            "signal": "mean pairwise Jaccard of seven family-specific Top-5 sets",
            "state": "high disagreement when current agreement < median of previous 100 target agreements",
            "primary_outcome": "consensus Top-5 hits minus equal-family-mean Top-5 hits",
            "primary_minimum_effect": PRACTICAL_THRESHOLD,
            "family_count": len(groups),
            "window": WINDOW,
            "top_k": 5,
            "tie_rule": "scores rounded to 12 decimals; ascending number; consensus vote count then mean family score then number",
        },
        "source": source,
        "walkforward": {
            "target_rows": n,
            "warmup_targets": WINDOW,
            "evaluated_split_counts": {k: v["targets"] for k, v in split_summary.items()},
            "original_split_counts": SPLIT_COUNTS,
            "first_target": str(dates[0]),
            "last_target": str(dates[-1]),
            "strict_prior_alignment": True,
            "historical_blind_oos_not_virgin": True,
        },
        "split_results": split_summary,
        "family_top5_hit_means": family_hit_means,
        "blind_oos_inference": {
            "method": "20,000 circular moving-block bootstrap (block=20); 20,000 circular state shifts; 20,000 non-overlapping block sign-flips; exact hypergeometric convolution; Holm across 3 registered endpoints",
            "endpoints": endpoints,
            "holm_family_size": 3,
            "acceptance_rule": "primary effect >= +0.025 hits/target AND 95% CI lower > 0 AND Holm p < 0.05",
            "accepted": bool(accepted),
        },
        "integrity": {
            "all_cutoffs_strictly_before_targets": True,
            "matrix_ledger_dates_cutoffs_actuals_exactly_aligned": True,
            "prior_draws_equal_target_index_plus_50": True,
            "all_feature_values_finite": True,
            "family_groups_partition_59_features": True,
            "family_counts": source["family_counts"],
            "future_suffix_mutation_checks": mutation_checks,
            "inference_target_level": True,
        },
        "limitations": [
            "Historical Blind OOS has been exposed to prior SONAR research and is not virgin prospective evidence.",
            "Q89 features are per-target cross-sectional z-scores; known rank duplicates remain within the baseline legacy family.",
            "Equal-family averaging reduces family-size weighting but does not remove within-family feature redundancy.",
            "The endpoint is per-number Top-5 hit count, not exact five-number ticket probability.",
            "Q90 matrix ends 2026-11-07; five later main-archive rows are excluded.",
            "Holm correction covers the three D4 endpoints only, not the full Q00-Q141 research family.",
        ],
        "next_action": "Keep D4 research-only. Continue common-source AST semantic reconciliation and obtain prospective frozen evidence; do not retune the disagreement state on this historical Blind OOS.",
    }
    report_path = output_dir / "q141_d4_family_consensus_state_report_2026-11-13.json"
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    prereg_bytes = preregistration.read_bytes()
    script_bytes = Path(__file__).read_bytes()
    files = {}
    for path in [preregistration, Path(__file__), report_path, ledger_path]:
        data = path.read_bytes()
        files[path.name] = {
            "path": str(path.name),
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "git_blob_sha1": git_blob_sha1(data),
        }
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-D4",
        "source_q90_zip_sha256": Q90_ZIP_SHA256,
        "source_a6_zip_sha256": A6_ZIP_SHA256,
        "preregistration_sha256": sha256_bytes(prereg_bytes),
        "runner_sha256": sha256_bytes(script_bytes),
        "target_rows": n,
        "evaluated_targets": int(valid.sum()),
        "files": files,
    }
    manifest_path = output_dir / "q141_d4_family_consensus_state_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-D4",
        "status": "LOCAL_REPLAY_COMPLETE_PENDING_REMOTE_READBACK",
        "decision": report["decision"],
        "report_path": report_path.name,
        "ledger_path": ledger_path.name,
        "manifest_path": manifest_path.name,
        "report_sha256": sha256_bytes(report_path.read_bytes()),
        "ledger_sha256": sha256_bytes(ledger_path.read_bytes()),
        "manifest_sha256": sha256_bytes(manifest_path.read_bytes()),
        "source_q90_zip_sha256": Q90_ZIP_SHA256,
        "source_a6_zip_sha256": A6_ZIP_SHA256,
        "next_action": report["next_action"],
        "governance": {
            "research_only": True,
            "canonical_archive_mutated": False,
            "b11_or_q60_freeze_mutated": False,
            "engine_promoted": False,
            "merge": False,
            "protected_prs_6_7_8_untouched": True,
        },
    }
    checkpoint_path = output_dir / "q141_d4_family_consensus_state_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report, target_ledger, manifest, checkpoint


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q90-zip", type=Path, required=True)
    parser.add_argument("--a6-zip", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, ledger, manifest, checkpoint = analyse(
        args.q90_zip, args.a6_zip, args.output_dir, args.preregistration
    )
    print(json.dumps({
        "decision": report["decision"],
        "split_counts": report["walkforward"]["evaluated_split_counts"],
        "blind_oos": report["blind_oos_inference"]["endpoints"],
        "ledger_rows": len(ledger),
        "manifest_files": len(manifest["files"]),
        "checkpoint_status": checkpoint["status"],
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
