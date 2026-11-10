#!/usr/bin/env python3
"""Q93: low-rank spectral coherence of the Q90 pair-interaction residual."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import sonar_q87_node_graph_phase_lag as q87
import sonar_q88_signed_node_graph_transfer as q88
import sonar_q90_edge_field_decomposition as q90

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "q93_spectral_coherence_protocol_2026-11-10.json"
CATALOG = OUT / "q93_spectral_coherence_catalog.jsonl"
LEDGER = OUT / "q93_spectral_coherence_target_ledger.csv.gz"
REPORT = OUT / "q93_spectral_coherence_report.json"
MANIFEST = OUT / "q93_spectral_coherence_manifest.json"
CHECKPOINT = OUT / "q93_spectral_coherence_checkpoint_2026-11-10.md"
VALIDATION = OUT / "q93_spectral_coherence_validation.json"

TASK_ID = "Q93-SPECTRAL-COHERENCE-01"
EXPECTED_SHA1 = "8d3e19f0b417024ba32e576697eac0648d12ab86"
EXPECTED_SHA256 = "ba0c8f4e78805e72d04a1b731e1882a9edd3ac71a2bc35c92409540d9ebdec61"
EXPECTED_DRAWS = 3403
EXPECTED_FIRST = "2017-07-17"
EXPECTED_LAST = "2026-11-09"
MIN_HISTORY = 200
ALPHA = 0.20
WINDOW = 20
DECAY = 0.80
K_VALUES = (1, 2, 4)
FOCAL = "Q93::SPECTRAL_K2"
SPECTRAL_IDS = tuple(f"Q93::SPECTRAL_K{k}" for k in K_VALUES)
MODEL_IDS = tuple(q90.MODEL_IDS) + SPECTRAL_IDS
SPLITS = ("discovery", "validation", "blind_oos")
ENDPOINTS = (("top5", 5), ("top10", 10), ("top20", 20))
PERMUTATION_COUNT = 99
PERMUTATION_SEED = 9301
BOOTSTRAP_BLOCK = 20
BOOTSTRAP_REPLICATES = 2000
PERMUTATION_COMPARATOR = "Q93::SPECTRAL_K2_PERM_MEAN"
COMPARATORS = (
    "Q90::FULL_EDGE_TRANSFER",
    "Q90::DEGREE_MAIN_TRANSFER",
    "Q90::PAIR_INTERACTION_TRANSFER",
    "Q90::NODE_ONLY_INERTIA",
    "BASE::EQUAL42",
    PERMUTATION_COMPARATOR,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump(path: Path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def slug(model: str) -> str:
    return model.replace("::", "_").lower()


def fixed_permutations():
    rng = np.random.default_rng(PERMUTATION_SEED)
    found = []
    seen = set()
    identity = tuple(range(40))
    while len(found) < PERMUTATION_COUNT:
        item = tuple(int(x) for x in rng.permutation(40))
        if item != identity and item not in seen:
            found.append(np.asarray(item, dtype=np.int64))
            seen.add(item)
    return found


def spectral_modes(pair_residual: np.ndarray, k: int):
    """Return a deterministic signed low-rank spectral operator, retaining cutoff ties."""
    matrix = np.asarray(pair_residual, dtype=np.float64)
    if matrix.shape != (40, 40) or not np.isfinite(matrix).all():
        raise ValueError("Q93 spectral input must be finite 40x40")
    if not np.allclose(matrix, matrix.T, atol=1e-10, rtol=0):
        raise ValueError("Q93 spectral input must be symmetric")
    if np.max(np.abs(np.diag(matrix))) > 1e-10:
        raise ValueError("Q93 pair residual must have zero diagonal")
    if np.max(np.abs(matrix.sum(axis=1))) > 1e-8:
        raise ValueError("Q93 pair residual must have zero row sums")

    values, vectors = np.linalg.eigh(matrix)
    order = np.argsort(-np.abs(values), kind="stable")
    scale = max(1.0, float(np.max(np.abs(values))))
    nonzero = [int(i) for i in order if abs(float(values[i])) > 1e-12 * scale]
    if not nonzero:
        return np.zeros(0, dtype=np.float64), np.zeros((40, 0), dtype=np.float64), 0.0

    requested = min(int(k), len(nonzero))
    cutoff = abs(float(values[nonzero[requested - 1]]))
    tie_tol = 1e-10 * max(1.0, cutoff)
    selected = [i for i in nonzero if abs(abs(float(values[i])) - cutoff) <= tie_tol or abs(float(values[i])) > cutoff]
    selected = sorted(selected, key=lambda i: (-abs(float(values[i])), -float(values[i]), i))
    selected_values = values[selected].astype(np.float64, copy=True)
    selected_vectors = vectors[:, selected].astype(np.float64, copy=True)

    # Canonicalize eigenvector signs; the operator is sign-invariant, but this aids replay diagnostics.
    for column in range(selected_vectors.shape[1]):
        pivot = int(np.argmax(np.abs(selected_vectors[:, column])))
        if selected_vectors[pivot, column] < 0:
            selected_vectors[:, column] *= -1.0

    total_energy = float(np.sum(values * values))
    retained_energy = float(np.sum(selected_values * selected_values))
    fraction = retained_energy / total_energy if total_energy > 0 else 0.0
    if np.max(np.abs(selected_vectors.T @ np.ones(40))) > 1e-8:
        raise ValueError("Q93 nonzero spectral modes are not orthogonal to the all-ones vector")
    return selected_values, selected_vectors, float(fraction)


def spectral_projection(values: np.ndarray, vectors: np.ndarray, features: np.ndarray) -> np.ndarray:
    """Apply V diag(lambda) V.T to prior features without materializing a dense operator."""
    x = np.asarray(features, dtype=np.float64)
    if x.shape != (40, 6) or not np.isfinite(x).all():
        raise ValueError("Q93 spectral projection requires finite prior features (40,6)")
    if vectors.shape[1] == 0:
        return np.zeros((40, 6), dtype=np.float64)
    return vectors @ (values[:, None] * (vectors.T @ x))


def permuted_spectral_projection(values, vectors, features, permutation):
    """Apply P V diag(lambda) V.T P.T to features; preserves the spectral eigenvalues."""
    permutation = np.asarray(permutation, dtype=np.int64)
    permuted_vectors = vectors[permutation, :]
    original_features = np.asarray(features, dtype=np.float64)
    if original_features.shape != (40, 6) or not np.isfinite(original_features).all():
        raise ValueError("Q93 permuted spectral projection requires finite prior features (40,6)")
    if vectors.shape[1] == 0:
        return np.zeros((40, 6), dtype=np.float64)
    # (P V) Lambda (P V).T X is exactly (P S P.T) X; do not permute X a second time.
    return permuted_vectors @ (values[:, None] * (permuted_vectors.T @ original_features))


def split_labels(total: int):
    return q90.split_labels(total)


def ledger_fields():
    fields = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "split"]
    for k in K_VALUES:
        fields.extend([f"spectral_energy_fraction_k{k}", f"spectral_effective_modes_k{k}"])
        for number in range(1, 41):
            fields.extend([f"spectral_raw_k{k}_{number:02d}", f"spectral_ewma_k{k}_{number:02d}"])
    for model in MODEL_IDS:
        fields.extend(f"rank_{slug(model)}_{number:02d}" for number in range(1, 41))
    for p in range(PERMUTATION_COUNT):
        fields.extend([
            f"perm_{p:02d}_top5_hits", f"perm_{p:02d}_top10_hits",
            f"perm_{p:02d}_top20_hits", f"perm_{p:02d}_mean_actual_rank"
        ])
    return fields


def compute_experiment(draws=None):
    draws = q87.read_draws() if draws is None else draws
    dates = [item["date"].isoformat() for item in draws]
    archive_sha1 = q90.q84.git_blob_sha1(ARCHIVE)
    archive_sha256 = sha256_file(ARCHIVE)
    if archive_sha1 != EXPECTED_SHA1 or archive_sha256 != EXPECTED_SHA256:
        raise ValueError("Q93 canonical archive byte identity mismatch")
    if len(draws) != EXPECTED_DRAWS or dates[0] != EXPECTED_FIRST or dates[-1] != EXPECTED_LAST:
        raise ValueError("Q93 canonical archive count/date mismatch")

    total = len(draws) - MIN_HISTORY
    if total != 3203:
        raise ValueError("Q93 strict-prior target count mismatch")
    labels = split_labels(total)
    counts = dict(Counter(labels))
    expected_counts = {"discovery": 1921, "validation": 641, "blind_oos": 641}
    if counts != expected_counts:
        raise ValueError(f"Q93 chronological split mismatch: {counts}")

    ranks = np.empty((total, len(MODEL_IDS), 40), dtype=np.int8)
    hits = np.empty((total, len(MODEL_IDS), 3), dtype=np.int8)
    actual_ranks = np.empty((total, len(MODEL_IDS), 5), dtype=np.int8)
    spectral_raw = np.zeros((total, len(K_VALUES), 40), dtype=np.float64)
    spectral_ewma = np.zeros_like(spectral_raw)
    spectral_energy = np.zeros((total, len(K_VALUES)), dtype=np.float64)
    spectral_modes_count = np.zeros((total, len(K_VALUES)), dtype=np.int16)
    permutation_hits = np.zeros((total, PERMUTATION_COUNT, 3), dtype=np.int8)
    permutation_mean_rank = np.zeros((total, PERMUTATION_COUNT), dtype=np.float64)

    spectral_histories = [deque(maxlen=WINDOW) for _ in K_VALUES]
    permutation_histories = [deque(maxlen=WINDOW) for _ in range(PERMUTATION_COUNT)]
    permutations = fixed_permutations()
    previous_features = None
    previous_edge = None
    previous_node_delta = None
    base_signal_histories = {name: deque(maxlen=WINDOW) for name in ("full", "degree", "pair", "node")}

    for offset, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        # Strict-prior state: target draw is never passed to a feature, graph or spectral function.
        history = draws[:draw_index]
        state = q87.field.field_state(history)
        edge = q87.field.pair_residual_graph(history)
        equal = q90.equal42_rank(history)
        base_z = q87.field.zscore(41.0 - equal.astype(np.float64))
        if previous_features is None or previous_edge is None:
            node_delta = np.zeros((40, 6), dtype=np.float64)
            edge_delta = np.zeros((40, 40), dtype=np.float64)
            main = np.zeros((40, 40), dtype=np.float64)
            pair = np.zeros((40, 40), dtype=np.float64)
            full_signal = degree_signal = pair_signal = node_signal = np.zeros(40, dtype=np.float64)
        else:
            node_delta = state["features"] - previous_features
            edge_delta = edge - previous_edge
            main, pair, _ = q90.decompose_edge_change(edge_delta)
            full_signal = q88.signed_transfer_alignment(node_delta, edge_delta, previous_features)
            degree_signal = q88.signed_transfer_alignment(node_delta, main, previous_features)
            pair_signal = q88.signed_transfer_alignment(node_delta, pair, previous_features)
            node_signal = q88.rowwise_signed_cosine(node_delta, previous_node_delta)

        # Reproduce Q90's fixed EWMA operators with independent per-component histories.
        raw_base = {"full": full_signal, "degree": degree_signal, "pair": pair_signal, "node": node_signal}
        smooth_base = {}
        for name, vector in raw_base.items():
            base_signal_histories[name].append(vector)
            smooth_base[name] = q88.rolling_signed_transfer(
                np.asarray(base_signal_histories[name]), len(base_signal_histories[name]) - 1, WINDOW, DECAY
            )

        blend = 0.5 * (state["signals"]["REVERSION"] + state["graph_signal"])
        current = np.empty((len(MODEL_IDS), 40), dtype=np.int8)
        base_model_scores = (
            q90.transfer_score(base_z, blend, smooth_base["full"]),
            q90.transfer_score(base_z, blend, smooth_base["degree"]),
            q90.transfer_score(base_z, blend, smooth_base["pair"]),
            q90.transfer_score(base_z, state["signals"]["REVERSION"], smooth_base["node"]),
        )
        for model_index, score in enumerate(base_model_scores):
            current[model_index] = q87.field.rank_from_scores(score)
        current[4] = equal

        spectral_operators = []
        for k_index, k in enumerate(K_VALUES):
            if previous_features is None:
                values = np.zeros(0, dtype=np.float64)
                vectors = np.zeros((40, 0), dtype=np.float64)
                energy_fraction = 0.0
                signal = np.zeros(40, dtype=np.float64)
            else:
                values, vectors, energy_fraction = spectral_modes(pair, k)
                projected = spectral_projection(values, vectors, state["features"])
                signal = q88.rowwise_signed_cosine(node_delta, projected)
            spectral_operators.append((values, vectors))
            spectral_raw[offset, k_index] = signal
            spectral_histories[k_index].append(signal)
            smooth = q88.rolling_signed_transfer(
                np.asarray(spectral_histories[k_index]), len(spectral_histories[k_index]) - 1, WINDOW, DECAY
            )
            spectral_ewma[offset, k_index] = smooth
            spectral_energy[offset, k_index] = energy_fraction
            spectral_modes_count[offset, k_index] = len(values)
            score = base_z + ALPHA * blend * q87.field.zscore(smooth)
            current[5 + k_index] = q87.field.rank_from_scores(score)

        if any(sorted(row.tolist()) != list(range(1, 41)) for row in current):
            raise ValueError("Q93 model ranking is not a permutation of 1..40")

        # All named model rankings are frozen before the target quintet is read.
        actual = np.sort(np.asarray(draws[draw_index]["nums"], dtype=np.int64))
        if actual.shape != (5,) or len(set(actual.tolist())) != 5 or np.any(actual < 1) or np.any(actual > 40):
            raise ValueError("Q93 invalid target quintet")
        actual_rank_matrix = current[:, actual - 1]
        current_hits = np.column_stack([
            np.sum(actual_rank_matrix <= 5, axis=1),
            np.sum(actual_rank_matrix <= 10, axis=1),
            np.sum(actual_rank_matrix <= 20, axis=1),
        ]).astype(np.int8)
        ranks[offset] = current
        actual_ranks[offset] = actual_rank_matrix
        hits[offset] = current_hits

        # Fixed node-label permutation null for the focal k=2 spectral operator.
        values2, vectors2 = spectral_operators[1]
        for p_index, permutation in enumerate(permutations):
            if previous_features is None or vectors2.shape[1] == 0:
                perm_signal = np.zeros(40, dtype=np.float64)
            else:
                projected_perm = permuted_spectral_projection(values2, vectors2, state["features"], permutation)
                perm_signal = q88.rowwise_signed_cosine(node_delta, projected_perm)
            permutation_histories[p_index].append(perm_signal)
            perm_smooth = q88.rolling_signed_transfer(
                np.asarray(permutation_histories[p_index]), len(permutation_histories[p_index]) - 1, WINDOW, DECAY
            )
            perm_score = base_z + ALPHA * blend * q87.field.zscore(perm_smooth)
            perm_rank = q87.field.rank_from_scores(perm_score)
            perm_actual_ranks = perm_rank[actual - 1]
            permutation_hits[offset, p_index] = (
                np.sum(perm_actual_ranks <= 5),
                np.sum(perm_actual_ranks <= 10),
                np.sum(perm_actual_ranks <= 20),
            )
            permutation_mean_rank[offset, p_index] = float(np.mean(perm_actual_ranks))

        previous_features = state["features"]
        previous_edge = edge
        previous_node_delta = node_delta

    split_indices = {split: np.asarray([i for i, label in enumerate(labels) if label == split], dtype=np.int64)
                     for split in SPLITS}
    metrics = []
    exact_tests = []
    for model_index, model in enumerate(MODEL_IDS):
        for split in SPLITS:
            idx = split_indices[split]
            selected = hits[idx, model_index, :]
            rank_values = actual_ranks[idx, model_index, :]
            row = {
                "strategy_id": model,
                "split": split,
                "targets": int(len(idx)),
                "mean_hits_top5": float(selected[:, 0].mean()),
                "mean_hits_top10": float(selected[:, 1].mean()),
                "mean_hits_top20": float(selected[:, 2].mean()),
                "mean_rank_actual_numbers": float(rank_values.mean()),
                "top20_4plus": int(np.sum(selected[:, 2] >= 4)),
                "top20_5of5": int(np.sum(selected[:, 2] == 5)),
                "top20_5of5_rate": float(np.mean(selected[:, 2] == 5)),
                "top20_hit_distribution": {str(k): int(np.sum(selected[:, 2] == k)) for k in range(6)},
                "p_values_raw": {},
            }
            for endpoint_index, (endpoint, k) in enumerate(ENDPOINTS):
                p_value = q87.field.exact_upper_tail(int(selected[:, endpoint_index].sum()), len(idx), k)
                test_id = f"Q93|{model}|{split}|{endpoint}"
                exact_tests.append({"test_id": test_id, "p_raw": float(p_value)})
                row["p_values_raw"][endpoint] = float(p_value)
            metrics.append(row)
    if len(exact_tests) != 72:
        raise ValueError("Q93 exact-null family must contain 72 tests")
    exact_adjusted = q90.q84.holm_adjust(exact_tests)
    for test in exact_tests:
        test["p_holm"] = exact_adjusted[test["test_id"]]
    for row in metrics:
        row["p_values_holm"] = {
            endpoint: exact_adjusted[f"Q93|{row['strategy_id']}|{row['split']}|{endpoint}"]
            for endpoint, _ in ENDPOINTS
        }

    focal_index = MODEL_IDS.index(FOCAL)
    permutation_mean_hits = permutation_hits.mean(axis=1)
    permutation_mean_rank_average = permutation_mean_rank.mean(axis=1)
    paired = []
    paired_tests = []
    for split_index, split in enumerate(("validation", "blind_oos")):
        idx = split_indices[split]
        for comparator_index, comparator in enumerate(COMPARATORS):
            if comparator == PERMUTATION_COMPARATOR:
                comparator_hits = permutation_mean_hits[idx]
                comparator_rank = permutation_mean_rank_average[idx]
            else:
                model_index = MODEL_IDS.index(comparator)
                comparator_hits = hits[idx, model_index, :].astype(np.float64)
                comparator_rank = actual_ranks[idx, model_index, :].mean(axis=1).astype(np.float64)
            for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
                result = q90.q84.bootstrap_paired(
                    hits[idx, focal_index, endpoint_index], comparator_hits[:, endpoint_index],
                    93000 + split_index * 1000 + comparator_index * 100 + endpoint_index
                )
                test_id = f"Q93PAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id": test_id, "p_raw": float(result["p_two_sided"])})
                paired.append({
                    "test_id": test_id, "split": split, "comparator": comparator, "endpoint": endpoint,
                    **result, "positive_difference_favors_spectral_k2": True
                })
            rank_result = q90.q84.bootstrap_paired(
                comparator_rank, actual_ranks[idx, focal_index, :].mean(axis=1),
                93000 + split_index * 1000 + comparator_index * 100 + 3
            )
            test_id = f"Q93PAIRED|{split}|{comparator}|mean_actual_rank_improvement"
            paired_tests.append({"test_id": test_id, "p_raw": float(rank_result["p_two_sided"])})
            paired.append({
                "test_id": test_id, "split": split, "comparator": comparator,
                "endpoint": "mean_actual_rank_improvement", **rank_result,
                "positive_difference_means_lower_spectral_k2_rank": True
            })
    if len(paired_tests) != 48:
        raise ValueError("Q93 paired bootstrap family must contain 48 tests")
    paired_adjusted = q90.q84.holm_adjust(paired_tests)
    for test in paired_tests:
        test["p_holm"] = paired_adjusted[test["test_id"]]
    for row in paired:
        row["p_holm"] = paired_adjusted[row["test_id"]]

    randomization_tests = []
    randomization = []
    for split in SPLITS:
        idx = split_indices[split]
        null_means = permutation_hits[idx].mean(axis=0)
        observed = hits[idx, focal_index, :].mean(axis=0)
        for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
            p_value = (1.0 + float(np.sum(null_means[:, endpoint_index] >= observed[endpoint_index]))) / (1.0 + PERMUTATION_COUNT)
            test_id = f"Q93RANDOM|{split}|{endpoint}"
            randomization_tests.append({"test_id": test_id, "p_raw": p_value})
            randomization.append({
                "test_id": test_id, "split": split, "endpoint": endpoint,
                "observed_mean_hits": float(observed[endpoint_index]),
                "permutation_mean": float(null_means[:, endpoint_index].mean()),
                "permutation_sd": float(null_means[:, endpoint_index].std(ddof=1)),
                "permutation_count": PERMUTATION_COUNT,
                "p_raw": p_value
            })
    if len(randomization_tests) != 9:
        raise ValueError("Q93 randomization family must contain 9 tests")
    randomization_adjusted = q90.q84.holm_adjust(randomization_tests)
    for test in randomization_tests:
        test["p_holm"] = randomization_adjusted[test["test_id"]]
    for row in randomization:
        row["p_holm"] = randomization_adjusted[row["test_id"]]

    def metric(model, split):
        return next(row for row in metrics if row["strategy_id"] == model and row["split"] == split)

    def paired_row(split, comparator, endpoint):
        return next(row for row in paired if row["split"] == split and row["comparator"] == comparator and row["endpoint"] == endpoint)

    focal_blind = metric(FOCAL, "blind_oos")
    primary_comparisons = []
    gate = True
    for comparator in ("Q90::PAIR_INTERACTION_TRANSFER", "BASE::EQUAL42", PERMUTATION_COMPARATOR):
        reference = metric(comparator, "blind_oos") if comparator in MODEL_IDS else None
        reference_top20 = reference["mean_hits_top20"] if reference else float(permutation_mean_hits[split_indices["blind_oos"]].mean(axis=0)[2])
        result = paired_row("blind_oos", comparator, "top20")
        lift = focal_blind["mean_hits_top20"] - reference_top20
        passed = (
            lift >= 0.10 and result["ci95"][0] is not None and result["ci95"][0] > 0
            and result["p_holm"] < 0.05
        )
        primary_comparisons.append({
            "comparator": comparator, "reference_top20": float(reference_top20),
            "focal_top20": focal_blind["mean_hits_top20"], "lift": float(lift),
            "ci95": result["ci95"], "paired_p_holm": result["p_holm"], "gate_component": "PASS" if passed else "NOT_MET"
        })
        gate = gate and passed
    exact_focal = focal_blind["p_values_holm"]["top20"]
    random_focal = next(row for row in randomization if row["split"] == "blind_oos" and row["endpoint"] == "top20")
    gate = gate and exact_focal < 0.05 and random_focal["p_holm"] < 0.05
    primary_gate = {
        "focal_model": FOCAL,
        "blind_top20": focal_blind["mean_hits_top20"],
        "exact_null_p_holm": exact_focal,
        "spectral_randomization_p_holm": random_focal["p_holm"],
        "comparisons": primary_comparisons,
        "status": "PASS" if gate else "NOT_MET"
    }

    spectral_summary = []
    for split in SPLITS:
        idx = split_indices[split]
        row = {"split": split, "targets": int(len(idx))}
        for k_index, k in enumerate(K_VALUES):
            row[f"mean_energy_fraction_k{k}"] = float(spectral_energy[idx, k_index].mean())
            row[f"mean_effective_modes_k{k}"] = float(spectral_modes_count[idx, k_index].mean())
            row[f"max_effective_modes_k{k}"] = int(spectral_modes_count[idx, k_index].max())
        spectral_summary.append(row)

    temporal_blocks = []
    blind_idx = split_indices["blind_oos"]
    pair_index = MODEL_IDS.index("Q90::PAIR_INTERACTION_TRANSFER")
    equal_index = MODEL_IDS.index("BASE::EQUAL42")
    for start in range(0, len(blind_idx), 100):
        block = blind_idx[start:start + 100]
        if len(block) < 40:
            continue
        temporal_blocks.append({
            "first_target": dates[MIN_HISTORY + int(block[0])],
            "last_target": dates[MIN_HISTORY + int(block[-1])],
            "targets": int(len(block)),
            "k2_delta_vs_pair_residual": float((hits[block, focal_index, 2] - hits[block, pair_index, 2]).mean()),
            "k2_delta_vs_equal42": float((hits[block, focal_index, 2] - hits[block, equal_index, 2]).mean()),
            "k2_delta_vs_permutation_mean": float((hits[block, focal_index, 2] - permutation_mean_hits[block, 2]).mean())
        })

    return {
        "dates": dates, "labels": labels, "counts": counts, "split_indices": split_indices,
        "ranks": ranks, "hits": hits, "actual_ranks": actual_ranks,
        "spectral_raw": spectral_raw, "spectral_ewma": spectral_ewma,
        "spectral_energy": spectral_energy, "spectral_modes_count": spectral_modes_count,
        "permutation_hits": permutation_hits, "permutation_mean_rank": permutation_mean_rank,
        "permutation_mean_hits": permutation_mean_hits, "permutation_mean_rank": permutation_mean_rank,
        "permutation_mean_rank_average": permutation_mean_rank_average,
        "metrics": metrics, "exact_tests": exact_tests, "paired": paired, "paired_tests": paired_tests,
        "randomization": randomization, "randomization_tests": randomization_tests,
        "primary_gate": primary_gate, "spectral_summary": spectral_summary,
        "temporal_blocks": temporal_blocks, "permutations": permutations
    }


def write_outputs(result):
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("task_id") != TASK_ID or protocol.get("status") != "PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q93 protocol identity/status mismatch")
    catalog = []
    for model in q90.MODEL_IDS:
        catalog.append({"strategy_id": model, "role": "frozen Q90 comparator"})
    for k, model in zip(K_VALUES, SPECTRAL_IDS):
        catalog.append({"strategy_id": model, "role": "fixed low-rank spectral operator", "requested_modes": k,
                        "focal": model == FOCAL, "alpha": ALPHA, "window": WINDOW, "decay": DECAY})
    CATALOG.write_text("".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in catalog), encoding="utf-8")

    fields = ledger_fields()
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for t in range(len(result["labels"])):
        draw_index = MIN_HISTORY + t
        row = {
            "target_date": result["dates"][draw_index],
            "cutoff_date": result["dates"][draw_index - 1],
            "prior_draws": draw_index,
            "actual_quintet": "",
            "split": result["labels"][t],
        }
        # The actual quintet is carried separately to avoid reconstructing it from a ranking.
        row["actual_quintet"] = " ".join(map(str, result["actual_numbers"][t]))
        for k_index, k in enumerate(K_VALUES):
            row[f"spectral_energy_fraction_k{k}"] = float(result["spectral_energy"][t, k_index])
            row[f"spectral_effective_modes_k{k}"] = int(result["spectral_modes_count"][t, k_index])
            for number in range(40):
                row[f"spectral_raw_k{k}_{number + 1:02d}"] = float(result["spectral_raw"][t, k_index, number])
                row[f"spectral_ewma_k{k}_{number + 1:02d}"] = float(result["spectral_ewma"][t, k_index, number])
        for model_index, model in enumerate(MODEL_IDS):
            for number in range(40):
                row[f"rank_{slug(model)}_{number + 1:02d}"] = int(result["ranks"][t, model_index, number])
        for p in range(PERMUTATION_COUNT):
            row[f"perm_{p:02d}_top5_hits"] = int(result["permutation_hits"][t, p, 0])
            row[f"perm_{p:02d}_top10_hits"] = int(result["permutation_hits"][t, p, 1])
            row[f"perm_{p:02d}_top20_hits"] = int(result["permutation_hits"][t, p, 2])
            row[f"perm_{p:02d}_mean_actual_rank"] = float(result["permutation_mean_rank"][t, p])
        writer.writerow(row)
    raw = buffer.getvalue().encode("utf-8")
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode="wb", mtime=0) as handle:
        handle.write(raw)
    LEDGER.write_bytes(compressed.getvalue())

    report = {
        "task_id": TASK_ID,
        "status": "COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "source_archive": {
            "draws": EXPECTED_DRAWS, "first_date": EXPECTED_FIRST, "last_date": EXPECTED_LAST,
            "git_blob_sha1": EXPECTED_SHA1, "sha256": EXPECTED_SHA256
        },
        "target_design": {"targets": len(result["labels"]), "minimum_prior_draws": MIN_HISTORY,
                          "split_counts": result["counts"], "cutoff_rule": "draws[:i] only; rankings frozen before target outcome"},
        "models": list(MODEL_IDS), "focal_model": FOCAL,
        "frozen_parameters": {"alpha": ALPHA, "window": WINDOW, "decay": DECAY,
                              "k_values": list(K_VALUES), "permutation_count": PERMUTATION_COUNT,
                              "permutation_seed": PERMUTATION_SEED, "bootstrap_block": BOOTSTRAP_BLOCK,
                              "bootstrap_replicates": BOOTSTRAP_REPLICATES},
        "metrics": result["metrics"], "exact_null_holm_tests": result["exact_tests"],
        "paired_block_bootstrap": result["paired"], "paired_holm_tests": result["paired_tests"],
        "spectral_randomization": result["randomization"], "spectral_randomization_holm_tests": result["randomization_tests"],
        "primary_gate": result["primary_gate"], "spectral_diagnostics": result["spectral_summary"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "limitations": [
            "Historical Blind OOS has been exposed in earlier SONAR work and is exploratory, not virgin prospective confirmation.",
            "The spectral null is fixed node-label permutation conjugation; it preserves eigenvalues but is not an arbitrary Haar eigenvector rotation.",
            "The truncated spectral operator may have a nonzero diagonal; it is used as a feature operator, not interpreted as a zero-self-loop adjacency matrix.",
            "The co-occurrence graph is statistical, not physical or causal.",
            "A valid historical result cannot replace the 200-case prospective promotion gate."
        ],
        "guardrails": ["strict-prior features and edge state", "fixed k/alpha/window/decay", "no Validation/Blind tuning",
                       "all permutation seeds fixed", "no freeze modification", "no automatic promotion"]
    }
    dump(REPORT, report)

    checkpoint = f"""# SONAR Q93 Spectral Coherence — execution checkpoint

- Task: {TASK_ID}
- State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE
- Archive: {EXPECTED_DRAWS} draws, {EXPECTED_FIRST} through {EXPECTED_LAST}
- Archive Git blob SHA-1: {EXPECTED_SHA1}
- Strict-prior targets: {len(result['labels'])}; splits: {result['counts']}
- Models: {len(MODEL_IDS)} named models; focal: {FOCAL}
- Spectral null: {PERMUTATION_COUNT} fixed node-label permutations, seed {PERMUTATION_SEED}
- Exact-null Holm tests: {len(result['exact_tests'])}
- Paired block-bootstrap Holm tests: {len(result['paired_tests'])}
- Spectral randomization Holm tests: {len(result['randomization_tests'])}
- Primary gate: {result['primary_gate']['status']}

## Next action

Run the independent validator, persist all outputs append-only, verify exact Git-object bytes, then replay the persisted head read-only. Historical Blind OOS remains exploratory. No promotion, merge or freeze changes.
"""
    CHECKPOINT.write_text(checkpoint, encoding="utf-8")

    file_paths = {
        "catalog": CATALOG, "target_ledger": LEDGER, "report": REPORT,
        "protocol": PROTOCOL, "checkpoint": CHECKPOINT
    }
    files = {key: {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
             for key, path in file_paths.items()}
    manifest = {
        "task_id": TASK_ID, "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_git_blob_sha1": EXPECTED_SHA1, "source_archive_sha256": EXPECTED_SHA256,
        "draws": EXPECTED_DRAWS, "targets": len(result["labels"]), "split_counts": result["counts"],
        "models": len(MODEL_IDS), "permutations": PERMUTATION_COUNT,
        "ledger_rows": len(result["labels"]), "ledger_fields": len(fields), "files": files,
        "generated_at_utc": datetime.now(timezone.utc).isoformat()
    }
    dump(MANIFEST, manifest)
    print("SONAR_Q93_COMPUTE_BEGIN")
    print(json.dumps({"task_id": TASK_ID, "targets": len(result["labels"]), "split_counts": result["counts"],
                      "models": len(MODEL_IDS), "permutations": PERMUTATION_COUNT,
                      "primary_gate": result["primary_gate"]["status"], "manifest": str(MANIFEST.relative_to(ROOT))},
                     sort_keys=True, separators=(",", ":")))
    print("SONAR_Q93_COMPUTE_END")


def main():
    draws = q87.read_draws()
    result = compute_experiment(draws)
    # Persist actual target quintets only after all model rankings have been frozen.
    result["actual_numbers"] = [np.sort(np.asarray(draws[MIN_HISTORY + i]["nums"], dtype=np.int64)).tolist()
                                for i in range(len(result["labels"]))]
    write_outputs(result)


if __name__ == "__main__":
    main()
