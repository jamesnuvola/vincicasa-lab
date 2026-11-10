#!/usr/bin/env python3
"""Q94: prior-only weighting by persistence of the leading Q93 spectral subspace."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import sonar_q87_node_graph_phase_lag as q87
import sonar_q90_edge_field_decomposition as q90
import sonar_q93_spectral_coherence as q93

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "q94_spectral_subspace_persistence_protocol_2026-11-10.json"
CATALOG = OUT / "q94_spectral_subspace_persistence_catalog.jsonl"
LEDGER = OUT / "q94_spectral_subspace_persistence_target_ledger.csv.gz"
REPORT = OUT / "q94_spectral_subspace_persistence_report.json"
MANIFEST = OUT / "q94_spectral_subspace_persistence_manifest.json"
CHECKPOINT = OUT / "q94_spectral_subspace_persistence_checkpoint_2026-11-10.md"
VALIDATION = OUT / "q94_spectral_subspace_persistence_validation.json"
Q93_LEDGER = q93.LEDGER
Q93_MANIFEST = q93.MANIFEST
Q93_VALIDATION = q93.VALIDATION

TASK_ID = "Q94-SPECTRAL-SUBSPACE-PERSISTENCE-01"
EXPECTED_SHA1 = "8d3e19f0b417024ba32e576697eac0648d12ab86"
EXPECTED_SHA256 = "ba0c8f4e78805e72d04a1b731e1882a9edd3ac71a2bc35c92409540d9ebdec61"
EXPECTED_DRAWS = 3403
EXPECTED_FIRST = "2017-07-17"
EXPECTED_LAST = "2026-11-09"
MIN_HISTORY = 200
REQUESTED_MODES = 2
MODELS = (
    "BASE::EQUAL42",
    "Q90::PAIR_INTERACTION_TRANSFER",
    "Q93::SPECTRAL_K2",
    "Q94::STABILITY_WEIGHTED",
    "Q94::INSTABILITY_WEIGHTED",
)
FOCAL = "Q94::STABILITY_WEIGHTED"
COMPARATORS = (
    "Q90::PAIR_INTERACTION_TRANSFER",
    "BASE::EQUAL42",
    "Q93::SPECTRAL_K2",
    "Q94::INSTABILITY_WEIGHTED",
)
SPLITS = ("discovery", "validation", "blind_oos")
ENDPOINTS = (("top5", 5), ("top10", 10), ("top20", 20))
SHIFT_COUNT = 99
SHIFT_SEED = 9401
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_REPLICATES = 2000


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def dump(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def slug(model: str) -> str:
    return model.replace("::", "_").lower()


def ledger_fields():
    fields = [
        "target_date", "cutoff_date", "prior_draws", "actual_quintet", "split",
        "current_effective_modes", "previous_effective_modes", "subspace_stability",
        "observed_top5_hits_stability", "observed_top10_hits_stability", "observed_top20_hits_stability",
        "observed_top5_hits_instability", "observed_top10_hits_instability", "observed_top20_hits_instability",
    ]
    for model in MODELS:
        fields.extend(f"rank_{slug(model)}_{number:02d}" for number in range(1, 41))
    return fields


def read_q93_ledger():
    manifest = json.loads(Q93_MANIFEST.read_text(encoding="utf-8"))
    validation = json.loads(Q93_VALIDATION.read_text(encoding="utf-8"))
    if manifest.get("status") != "ACCEPTANCE_PASS" or validation.get("status") != "PASS":
        raise ValueError("Q94 blocked: Q93 source artifacts are not accepted")
    meta = manifest.get("files", {}).get("target_ledger", {})
    if not meta or meta.get("bytes") != Q93_LEDGER.stat().st_size or meta.get("sha256") != sha256_file(Q93_LEDGER):
        raise ValueError("Q94 blocked: Q93 source ledger does not match its accepted manifest")
    with gzip.open(Q93_LEDGER, "rt", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 3203:
        raise ValueError("Q94 expected exactly 3,203 accepted Q93 target rows")
    return rows, sha256_file(Q93_LEDGER)


def subspace_overlap(current: np.ndarray, previous: np.ndarray) -> float:
    current = np.asarray(current, dtype=np.float64)
    previous = np.asarray(previous, dtype=np.float64)
    if current.ndim != 2 or previous.ndim != 2 or current.shape[0] != 40 or previous.shape[0] != 40:
        raise ValueError("Q94 subspace bases must have 40 rows")
    r_current, r_previous = current.shape[1], previous.shape[1]
    if not r_current or not r_previous:
        return 0.0
    if not np.isfinite(current).all() or not np.isfinite(previous).all():
        raise ValueError("Q94 non-finite subspace basis")
    overlap = float(np.sum((current.T @ previous) ** 2)) / float(min(r_current, r_previous))
    if overlap < -1e-10 or overlap > 1.0 + 1e-8:
        raise ValueError(f"Q94 subspace overlap outside [0,1]: {overlap}")
    return float(np.clip(overlap, 0.0, 1.0))


def compute_stability(draws):
    """Compute each target's current-vs-previous leading subspace from strict prefixes only."""
    stability = np.zeros(len(draws) - MIN_HISTORY, dtype=np.float64)
    current_modes = np.zeros_like(stability, dtype=np.int16)
    previous_modes = np.zeros_like(stability, dtype=np.int16)
    previous_edge = None
    previous_vectors = np.zeros((40, 0), dtype=np.float64)

    for offset, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        edge = q87.field.pair_residual_graph(history)
        if previous_edge is None:
            vectors = np.zeros((40, 0), dtype=np.float64)
        else:
            edge_delta = edge - previous_edge
            _, pair_residual, _ = q90.decompose_edge_change(edge_delta)
            _, vectors, _ = q93.spectral_modes(pair_residual, REQUESTED_MODES)

        current_modes[offset] = vectors.shape[1]
        previous_modes[offset] = previous_vectors.shape[1]
        stability[offset] = subspace_overlap(vectors, previous_vectors)
        previous_edge = edge
        previous_vectors = vectors.copy()

    if not np.isfinite(stability).all() or np.any(stability < 0) or np.any(stability > 1):
        raise ValueError("Q94 stability sequence is invalid")
    return stability, current_modes, previous_modes


def parse_rank(row, model):
    values = np.asarray([int(row[f"rank_{slug(model)}_{number:02d}"]) for number in range(1, 41)], dtype=np.int8)
    if sorted(values.tolist()) != list(range(1, 41)):
        raise ValueError(f"Q94 invalid source ranking for {model}")
    return values


def rank_hits(rank, actual):
    actual_ranks = rank[np.asarray(actual, dtype=np.int64) - 1]
    return (
        int(np.sum(actual_ranks <= 5)),
        int(np.sum(actual_ranks <= 10)),
        int(np.sum(actual_ranks <= 20)),
    ), actual_ranks


def holm(tests):
    return q90.q84.holm_adjust(tests)


def compute_experiment(draws=None):
    draws = q87.read_draws() if draws is None else draws
    dates = [item["date"].isoformat() for item in draws]
    archive_sha1 = q90.q84.git_blob_sha1(ARCHIVE)
    archive_sha256 = sha256_file(ARCHIVE)
    if archive_sha1 != EXPECTED_SHA1 or archive_sha256 != EXPECTED_SHA256:
        raise ValueError("Q94 canonical archive byte identity mismatch")
    if len(draws) != EXPECTED_DRAWS or dates[0] != EXPECTED_FIRST or dates[-1] != EXPECTED_LAST:
        raise ValueError("Q94 canonical archive count/date mismatch")

    q93_rows, q93_ledger_sha256 = read_q93_ledger()
    total = len(draws) - MIN_HISTORY
    labels = q93.split_labels(total)
    counts = dict(Counter(labels))
    expected_counts = {"discovery": 1921, "validation": 641, "blind_oos": 641}
    if total != 3203 or counts != expected_counts or len(q93_rows) != total:
        raise ValueError(f"Q94 target/split mismatch: total={total}, counts={counts}")

    stability, current_modes, previous_modes = compute_stability(draws)
    ranks = np.empty((total, len(MODELS), 40), dtype=np.int8)
    hits = np.empty((total, len(MODELS), 3), dtype=np.int8)
    actual_ranks = np.empty((total, len(MODELS), 5), dtype=np.int8)
    ledger_rows = []

    for offset, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        source = q93_rows[offset]
        target_date = dates[draw_index]
        cutoff_date = dates[draw_index - 1]
        if source.get("target_date") != target_date or source.get("cutoff_date") != cutoff_date:
            raise ValueError(f"Q94 Q93 source cutoff/date mismatch at target {target_date}")
        if int(source.get("prior_draws", "-1")) != draw_index:
            raise ValueError(f"Q94 Q93 source prior count mismatch at target {target_date}")
        if source.get("split") != labels[offset]:
            raise ValueError(f"Q94 Q93 source split mismatch at target {target_date}")

        equal_rank = parse_rank(source, "BASE::EQUAL42")
        pair_rank = parse_rank(source, "Q90::PAIR_INTERACTION_TRANSFER")
        spectral_rank = parse_rank(source, "Q93::SPECTRAL_K2")
        equal_strength = 41.0 - equal_rank.astype(np.float64)
        spectral_strength = 41.0 - spectral_rank.astype(np.float64)
        weight = float(stability[offset])

        # These are fixed convex blends of already-frozen prior-only rankings.
        stable_score = (1.0 - weight) * equal_strength + weight * spectral_strength
        unstable_score = weight * equal_strength + (1.0 - weight) * spectral_strength
        stable_rank = q87.field.rank_from_scores(stable_score)
        unstable_rank = q87.field.rank_from_scores(unstable_score)

        current = np.vstack([equal_rank, pair_rank, spectral_rank, stable_rank, unstable_rank])
        if any(sorted(row.tolist()) != list(range(1, 41)) for row in current):
            raise ValueError(f"Q94 generated invalid ranking at target {target_date}")
        ranks[offset] = current

        # Only after every ranking is frozen do we inspect the target outcome.
        actual = sorted(int(x) for x in draws[draw_index]["nums"])
        if len(actual) != 5 or len(set(actual)) != 5 or any(x < 1 or x > 40 for x in actual):
            raise ValueError(f"Q94 invalid target quintet at {target_date}")
        if source.get("actual_quintet") != " ".join(map(str, actual)):
            raise ValueError(f"Q94 Q93 source actual outcome mismatch at target {target_date}")

        row = {
            "target_date": target_date,
            "cutoff_date": cutoff_date,
            "prior_draws": str(draw_index),
            "actual_quintet": " ".join(map(str, actual)),
            "split": labels[offset],
            "current_effective_modes": str(int(current_modes[offset])),
            "previous_effective_modes": str(int(previous_modes[offset])),
            "subspace_stability": format(weight, ".17g"),
        }
        for model_index, model in enumerate(MODELS):
            current_hits, current_actual_ranks = rank_hits(current[model_index], actual)
            hits[offset, model_index] = current_hits
            actual_ranks[offset, model_index] = current_actual_ranks
            for number, rank_value in enumerate(current[model_index], start=1):
                row[f"rank_{slug(model)}_{number:02d}"] = str(int(rank_value))
            if model == FOCAL:
                row.update({
                    "observed_top5_hits_stability": str(current_hits[0]),
                    "observed_top10_hits_stability": str(current_hits[1]),
                    "observed_top20_hits_stability": str(current_hits[2]),
                })
            elif model == "Q94::INSTABILITY_WEIGHTED":
                row.update({
                    "observed_top5_hits_instability": str(current_hits[0]),
                    "observed_top10_hits_instability": str(current_hits[1]),
                    "observed_top20_hits_instability": str(current_hits[2]),
                })
        ledger_rows.append(row)

    split_indices = {
        split: np.asarray([i for i, label in enumerate(labels) if label == split], dtype=np.int64)
        for split in SPLITS
    }
    metrics = []
    exact_tests = []
    for model_index, model in enumerate(MODELS):
        for split in SPLITS:
            idx = split_indices[split]
            selected = hits[idx, model_index, :]
            selected_ranks = actual_ranks[idx, model_index, :]
            metric = {
                "strategy_id": model,
                "split": split,
                "targets": int(len(idx)),
                "mean_hits_top5": float(selected[:, 0].mean()),
                "mean_hits_top10": float(selected[:, 1].mean()),
                "mean_hits_top20": float(selected[:, 2].mean()),
                "mean_rank_actual_numbers": float(selected_ranks.mean()),
                "top20_4plus": int(np.sum(selected[:, 2] >= 4)),
                "top20_5of5": int(np.sum(selected[:, 2] == 5)),
                "top20_hit_distribution": {str(k): int(np.sum(selected[:, 2] == k)) for k in range(6)},
                "p_values_raw": {},
            }
            for endpoint_index, (endpoint, k) in enumerate(ENDPOINTS):
                p_value = q87.field.exact_upper_tail(int(selected[:, endpoint_index].sum()), len(idx), k)
                test_id = f"Q94EXACT|{model}|{split}|{endpoint}"
                exact_tests.append({"test_id": test_id, "p_raw": float(p_value)})
                metric["p_values_raw"][endpoint] = float(p_value)
            metrics.append(metric)
    if len(exact_tests) != 45:
        raise ValueError("Q94 exact-null family must contain 45 tests")
    exact_adjusted = holm(exact_tests)
    for test in exact_tests:
        test["p_holm"] = exact_adjusted[test["test_id"]]
    for metric in metrics:
        metric["p_values_holm"] = {
            endpoint: exact_adjusted[f"Q94EXACT|{metric['strategy_id']}|{metric['split']}|{endpoint}"]
            for endpoint, _ in ENDPOINTS
        }

    focal_index = MODELS.index(FOCAL)
    paired = []
    paired_tests = []
    for split_index, split in enumerate(("validation", "blind_oos")):
        idx = split_indices[split]
        for comparator_index, comparator in enumerate(COMPARATORS):
            comparator_model_index = MODELS.index(comparator)
            for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
                result = q90.q84.bootstrap_paired(
                    hits[idx, focal_index, endpoint_index],
                    hits[idx, comparator_model_index, endpoint_index],
                    94000 + split_index * 1000 + comparator_index * 100 + endpoint_index,
                )
                test_id = f"Q94PAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id": test_id, "p_raw": float(result["p_two_sided"])})
                paired.append({
                    "test_id": test_id, "split": split, "comparator": comparator, "endpoint": endpoint,
                    **result, "positive_difference_favors_stability_weighted": True,
                })
    if len(paired_tests) != 24:
        raise ValueError("Q94 paired bootstrap family must contain 24 tests")
    paired_adjusted = holm(paired_tests)
    for test in paired_tests:
        test["p_holm"] = paired_adjusted[test["test_id"]]
    for row in paired:
        row["p_holm"] = paired_adjusted[row["test_id"]]

    # Circular shifts are a post-hoc alignment null, never a forecast input.
    rng = np.random.default_rng(SHIFT_SEED)
    shift_tests = []
    shift_rows = []
    for split in SPLITS:
        idx = split_indices[split]
        n = len(idx)
        shifts = np.sort(rng.choice(np.arange(1, n, dtype=np.int64), size=SHIFT_COUNT, replace=False))
        base_strength = 41.0 - ranks[idx, MODELS.index("BASE::EQUAL42")].astype(np.float64)
        spectral_strength = 41.0 - ranks[idx, MODELS.index("Q93::SPECTRAL_K2")].astype(np.float64)
        actuals = [sorted(int(x) for x in draws[MIN_HISTORY + int(i)]["nums"]) for i in idx]
        null_hits = np.zeros((SHIFT_COUNT, 3), dtype=np.float64)
        for shift_index, shift in enumerate(shifts):
            shifted_weights = np.roll(stability[idx], int(shift))
            sums = np.zeros(3, dtype=np.float64)
            for local_index in range(n):
                score = (1.0 - shifted_weights[local_index]) * base_strength[local_index] + shifted_weights[local_index] * spectral_strength[local_index]
                rank = q87.field.rank_from_scores(score)
                current_hits, _ = rank_hits(rank, actuals[local_index])
                sums += np.asarray(current_hits, dtype=np.float64)
            null_hits[shift_index] = sums / n
        observed = hits[idx, focal_index, :].mean(axis=0)
        for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
            p_value = (1.0 + float(np.sum(null_hits[:, endpoint_index] >= observed[endpoint_index]))) / (1.0 + SHIFT_COUNT)
            test_id = f"Q94SHIFT|{split}|{endpoint}"
            shift_tests.append({"test_id": test_id, "p_raw": p_value})
            shift_rows.append({
                "test_id": test_id, "split": split, "endpoint": endpoint,
                "observed_mean_hits": float(observed[endpoint_index]),
                "shift_null_mean": float(null_hits[:, endpoint_index].mean()),
                "shift_null_sd": float(null_hits[:, endpoint_index].std(ddof=1)),
                "shift_null_q95": float(np.quantile(null_hits[:, endpoint_index], 0.95)),
                "shift_count": SHIFT_COUNT, "p_raw": p_value,
            })
    if len(shift_tests) != 9:
        raise ValueError("Q94 circular-shift family must contain 9 tests")
    shift_adjusted = holm(shift_tests)
    for test in shift_tests:
        test["p_holm"] = shift_adjusted[test["test_id"]]
    for row in shift_rows:
        row["p_holm"] = shift_adjusted[row["test_id"]]

    def metric(model, split):
        return next(row for row in metrics if row["strategy_id"] == model and row["split"] == split)

    def paired_row(split, comparator, endpoint):
        return next(row for row in paired if row["split"] == split and row["comparator"] == comparator and row["endpoint"] == endpoint)

    focal_blind = metric(FOCAL, "blind_oos")
    primary_comparisons = []
    gate = True
    for comparator in ("Q90::PAIR_INTERACTION_TRANSFER", "BASE::EQUAL42", "Q93::SPECTRAL_K2"):
        reference_top20 = metric(comparator, "blind_oos")["mean_hits_top20"]
        result = paired_row("blind_oos", comparator, "top20")
        lift = focal_blind["mean_hits_top20"] - reference_top20
        passed = (
            lift >= 0.10 and result["ci95"][0] is not None and result["ci95"][0] > 0
            and result["p_holm"] < 0.05
        )
        primary_comparisons.append({
            "comparator": comparator, "reference_top20": float(reference_top20),
            "focal_top20": focal_blind["mean_hits_top20"], "lift": float(lift),
            "ci95": result["ci95"], "paired_p_holm": result["p_holm"],
            "gate_component": "PASS" if passed else "NOT_MET",
        })
        gate = gate and passed
    exact_focal = focal_blind["p_values_holm"]["top20"]
    shift_focal = next(row for row in shift_rows if row["split"] == "blind_oos" and row["endpoint"] == "top20")
    gate = gate and exact_focal < 0.05 and shift_focal["p_holm"] < 0.05
    primary_gate = {
        "focal_model": FOCAL,
        "blind_top20": focal_blind["mean_hits_top20"],
        "exact_null_p_holm": exact_focal,
        "circular_shift_p_holm": shift_focal["p_holm"],
        "comparisons": primary_comparisons,
        "status": "PASS" if gate else "NOT_MET",
    }

    stability_summary = []
    for split in SPLITS:
        idx = split_indices[split]
        values = stability[idx]
        stability_summary.append({
            "split": split,
            "targets": int(len(idx)),
            "mean_stability": float(values.mean()),
            "median_stability": float(np.median(values)),
            "q25_stability": float(np.quantile(values, 0.25)),
            "q75_stability": float(np.quantile(values, 0.75)),
            "fraction_stability_ge_0_5": float(np.mean(values >= 0.5)),
            "mean_current_effective_modes": float(current_modes[idx].mean()),
            "mean_previous_effective_modes": float(previous_modes[idx].mean()),
            "empty_current_subspace_targets": int(np.sum(current_modes[idx] == 0)),
        })

    temporal_blocks = []
    blind_idx = split_indices["blind_oos"]
    stable_index = MODELS.index(FOCAL)
    equal_index = MODELS.index("BASE::EQUAL42")
    spectral_index = MODELS.index("Q93::SPECTRAL_K2")
    for start in range(0, len(blind_idx), 100):
        block = blind_idx[start:start + 100]
        if len(block) < 40:
            continue
        temporal_blocks.append({
            "first_target": dates[MIN_HISTORY + int(block[0])],
            "last_target": dates[MIN_HISTORY + int(block[-1])],
            "targets": int(len(block)),
            "stability_weighted_delta_vs_equal42": float((hits[block, stable_index, 2] - hits[block, equal_index, 2]).mean()),
            "stability_weighted_delta_vs_q93_k2": float((hits[block, stable_index, 2] - hits[block, spectral_index, 2]).mean()),
        })

    return {
        "dates": dates, "labels": labels, "counts": counts,
        "stability": stability, "current_modes": current_modes, "previous_modes": previous_modes,
        "ranks": ranks, "hits": hits, "actual_ranks": actual_ranks, "ledger_rows": ledger_rows,
        "metrics": metrics, "exact_tests": exact_tests,
        "paired": paired, "paired_tests": paired_tests,
        "circular_shift": shift_rows, "circular_shift_tests": shift_tests,
        "primary_gate": primary_gate, "stability_summary": stability_summary,
        "temporal_blocks": temporal_blocks, "q93_ledger_sha256": q93_ledger_sha256,
        "archive_sha1": archive_sha1, "archive_sha256": archive_sha256,
    }


def catalog_entries():
    return [
        {"strategy_id": "BASE::EQUAL42", "role": "frozen equal-weight 42-rule baseline"},
        {"strategy_id": "Q90::PAIR_INTERACTION_TRANSFER", "role": "frozen Q90 pair-residual comparator"},
        {"strategy_id": "Q93::SPECTRAL_K2", "role": "frozen Q93 unweighted k=2 comparator"},
        {"strategy_id": "Q94::STABILITY_WEIGHTED", "role": "focal; convex rank blend weighted by prior-only leading-subspace persistence"},
        {"strategy_id": "Q94::INSTABILITY_WEIGHTED", "role": "opposite-weight diagnostic control"},
    ]


def write_outputs(result):
    for path in (CATALOG, LEDGER, REPORT, MANIFEST, CHECKPOINT, VALIDATION):
        if path.exists():
            raise SystemExit("Q94 append-only output already exists: " + str(path.relative_to(ROOT)))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("task_id") != TASK_ID or protocol.get("status") != "PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q94 protocol identity/status mismatch")

    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
        for item in catalog_entries():
            handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")

    fields = ledger_fields()
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
            with io.TextIOWrapper(gz, encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(result["ledger_rows"])

    report = {
        "task_id": TASK_ID,
        "status": "COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "source_archive": {
            "draws": EXPECTED_DRAWS, "first_date": EXPECTED_FIRST, "last_date": EXPECTED_LAST,
            "git_blob_sha1": result["archive_sha1"], "sha256": result["archive_sha256"],
        },
        "source_q93_ledger_sha256": result["q93_ledger_sha256"],
        "target_counts": result["counts"],
        "focal_model": FOCAL,
        "models": list(MODELS),
        "frozen_parameters": {
            "requested_modes": REQUESTED_MODES,
            "rank_blend": "convex ordinal-rank blend",
            "circular_shift_count": SHIFT_COUNT,
            "circular_shift_seed": SHIFT_SEED,
            "bootstrap_block_length": BOOTSTRAP_BLOCK,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        },
        "metrics": result["metrics"],
        "exact_null_holm_tests": result["exact_tests"],
        "paired_block_bootstrap": result["paired"],
        "paired_holm_tests": result["paired_tests"],
        "circular_shift_randomization": result["circular_shift"],
        "circular_shift_holm_tests": result["circular_shift_tests"],
        "primary_gate": result["primary_gate"],
        "spectral_persistence_diagnostics": result["stability_summary"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "guardrails": [
            "Q93 source ledger was acceptance-verified before use.",
            "Current and previous pair-residual subspaces use strict prefixes only.",
            "All rankings are frozen before reading each target quintet.",
            "No Validation or historical Blind OOS tuning.",
            "Circular shifts are inferential only, not forecast inputs.",
            "Global Holm correction is applied separately to exact-null, paired and shift families.",
            "Historical Blind OOS is exploratory, not virgin prospective confirmation.",
            "No immutable freeze changes or engine promotion.",
        ],
        "limitations": [
            "Subspace overlap measures persistence, not causality.",
            "Ordinal-rank blending discards score magnitudes.",
            "Circular-shift null preserves the within-split stability sequence up to rotation but is not a universal graph null.",
            "The co-occurrence graph is statistical, not physical coupling.",
            "Q60 prospective promotion still requires 200 complete paired targets.",
        ],
    }
    dump(REPORT, report)

    checkpoint = (
        "# SONAR Q94 Spectral Subspace Persistence — execution checkpoint\n\n"
        "- Task: Q94-SPECTRAL-SUBSPACE-PERSISTENCE-01\n"
        "- State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE\n"
        f"- Archive: {EXPECTED_DRAWS} draws, {EXPECTED_FIRST} through {EXPECTED_LAST}\n"
        f"- Strict-prior targets: {len(result['labels'])}; splits: {result['counts']}\n"
        f"- Focal model: {FOCAL}\n"
        f"- Primary historical gate: {result['primary_gate']['status']}\n"
        f"- Q93 source ledger SHA-256: {result['q93_ledger_sha256']}\n\n"
        "## Next action\n\n"
        "Run the independent replay validator, append-only persist the accepted outputs, verify exact Git-object bytes, "
        "and replay the persisted head read-only. Historical Blind OOS remains exploratory. No promotion, merge or freeze changes.\n"
    )
    CHECKPOINT.write_text(checkpoint, encoding="utf-8")

    files = {
        "catalog": CATALOG,
        "target_ledger": LEDGER,
        "report": REPORT,
        "protocol": PROTOCOL,
        "checkpoint": CHECKPOINT,
    }
    manifest = {
        "task_id": TASK_ID,
        "status": "COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive_git_blob_sha1": result["archive_sha1"],
        "source_archive_sha256": result["archive_sha256"],
        "source_q93_ledger_sha256": result["q93_ledger_sha256"],
        "draws": EXPECTED_DRAWS,
        "targets": len(result["labels"]),
        "split_counts": result["counts"],
        "models": len(MODELS),
        "ledger_fields": len(fields),
        "files": {
            key: {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for key, path in files.items()
        },
    }
    dump(MANIFEST, manifest)
    print(json.dumps({
        "task_id": TASK_ID,
        "status": "COMPUTED",
        "targets": len(result["labels"]),
        "splits": result["counts"],
        "focal_top20_blind": next(x["mean_hits_top20"] for x in result["metrics"] if x["strategy_id"] == FOCAL and x["split"] == "blind_oos"),
        "primary_gate": result["primary_gate"]["status"],
        "ledger_bytes": LEDGER.stat().st_size,
    }, sort_keys=True))


def main():
    result = compute_experiment()
    write_outputs(result)


if __name__ == "__main__":
    main()
