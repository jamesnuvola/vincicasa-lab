#!/usr/bin/env python3
"""Q86-DIR causal state-transition gates for the VinciCasa 40-node SONAR field."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import numpy as np
import sonar_strategy_atlas as q84
import sonar_strategy_atlas_k_sensitivity as ksens
import sonar_per_number_field_dynamics as field
from sonar_sequence_agent import CONFIGS, MIN_HISTORY, read_draws, feature_scores

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "q86_directional_dynamics_protocol_2026-11-10.json"
CATALOG = OUT / "q86_directional_dynamics_catalog.jsonl"
LEDGER = OUT / "q86_directional_dynamics_target_ledger.csv.gz"
REPORT = OUT / "q86_directional_dynamics_report.json"
MANIFEST = OUT / "q86_directional_dynamics_manifest.json"
CHECKPOINT = OUT / "q86_directional_dynamics_checkpoint_2026-11-10.json"
VALIDATION = OUT / "q86_directional_dynamics_validation.json"

BASE_EQUAL = "BASE::EQUAL42"
BASE_FLOW = "BASE::FLOW_K50"
FIXED_REV = "FIXED::REVERSION_A20"
FIXED_GRAPH = "FIXED::GRAPH_MIX_A20"
DYNAMIC_IDS = (
    "DYN::NODE_DIRECTIONAL_ALIGNMENT",
    "DYN::NODE_DIRECTIONAL_CURVATURE",
    "DYN::GRAPH_DIRECTIONAL_ALIGNMENT",
    "DYN::NODE_GRAPH_DIRECTIONAL_COHERENCE",
)
MODEL_IDS = (BASE_EQUAL, BASE_FLOW, FIXED_REV, FIXED_GRAPH) + DYNAMIC_IDS
SPLITS = ("discovery", "validation", "blind_oos")
ENDPOINTS = (("top5", 5), ("top10", 10), ("top20", 20))
COMPARATORS = (BASE_EQUAL, BASE_FLOW, FIXED_REV, FIXED_GRAPH)
ROLLING_WINDOW = 300
MIN_GATE_HISTORY = 100
EXPECTED_SHA1 = "77ca692a6082809fcc6c471501617433ec7c36cf"
EXPECTED_SHA256 = "5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b"
EXPECTED_DRAWS = 3402
EXPECTED_LAST = "2026-11-08"
EXPECTED_TARGETS = 3202


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def slug(model_id):
    return model_id.replace("::", "_").lower()


def ledger_fields():
    fields = [
        "target_date", "cutoff_date", "prior_draws", "actual_quintet", "split",
        "node_speed", "node_acceleration", "graph_speed", "graph_acceleration",
        "node_alignment_mean", "graph_alignment_mean", "node_graph_coherence_mean",
        "field_state_sha256", "directional_state_sha256",
    ]
    for number in range(1, 41):
        fields.extend([f"node_alignment_{number:02d}", f"graph_alignment_{number:02d}", f"node_graph_coherence_{number:02d}"])
    for model in MODEL_IDS:
        fields.extend(f"rank_{slug(model)}_{number:02d}" for number in range(1, 41))
    return fields


def empirical_midrank_percentile(value, prior_values, minimum_history=MIN_GATE_HISTORY, window=ROLLING_WINDOW):
    """Causal mid-rank percentile. The current value is never inserted into prior_values."""
    if not math.isfinite(float(value)):
        raise ValueError("non-finite transition metric")
    prior = np.asarray(list(prior_values)[-window:], dtype=np.float64)
    if len(prior) < minimum_history:
        return 0.5
    if not np.isfinite(prior).all():
        raise ValueError("non-finite prior transition history")
    less = int(np.sum(prior < float(value)))
    equal = int(np.sum(prior == float(value)))
    return float((less + 0.5 * equal) / len(prior))


def alpha_up(percentile):
    p = float(np.clip(percentile, 0.0, 1.0))
    return float(min(0.30, max(0.10, 0.10 + 0.20 * p)))


def alpha_down(percentile):
    p = float(np.clip(percentile, 0.0, 1.0))
    return float(min(0.30, max(0.10, 0.30 - 0.20 * p)))


def field_state_for_target(draws, target_index):
    """Build a field state from the target's strict prior prefix only."""
    if target_index <= 0 or target_index > len(draws):
        raise ValueError("invalid target prefix boundary")
    return field.field_state(draws[:target_index])


def rowwise_cosine(left, right, epsilon=1e-12):
    """Signed cosine by row; zero vectors map to neutral zero."""
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or left.ndim != 2 or left.shape[0] < 1:
        raise ValueError("directional cosine requires matching non-empty matrices")
    if not np.isfinite(left).all() or not np.isfinite(right).all():
        raise ValueError("non-finite directional vector")
    numerator = np.sum(left * right, axis=1)
    denominator = np.linalg.norm(left, axis=1) * np.linalg.norm(right, axis=1)
    return np.divide(numerator, denominator, out=np.zeros(left.shape[0], dtype=np.float64), where=denominator > epsilon)


def directional_state_hash(node_alignment, graph_alignment, coherence):
    values = np.concatenate([np.asarray(node_alignment, dtype="<f8"), np.asarray(graph_alignment, dtype="<f8"), np.asarray(coherence, dtype="<f8")])
    if values.shape != (120,) or not np.isfinite(values).all():
        raise ValueError("invalid directional state for hashing")
    return hashlib.sha256(values.tobytes()).hexdigest()


def transition_metrics(features, edge, previous_features, previous_edge, previous_node_delta, previous_edge_delta):
    """Return causal node/graph speeds, accelerations and signed directional cosines."""
    features = np.asarray(features, dtype=np.float64)
    edge = np.asarray(edge, dtype=np.float64)
    if features.shape != (40, 6) or edge.shape != (40, 40):
        raise ValueError("invalid node or graph state shape")
    if not np.isfinite(features).all() or not np.isfinite(edge).all():
        raise ValueError("non-finite node or graph state")
    if previous_features is None or previous_edge is None:
        zeros = np.zeros(40, dtype=np.float64)
        return 0.0, 0.0, 0.0, 0.0, zeros, zeros.copy(), None, None
    node_delta = features - np.asarray(previous_features, dtype=np.float64)
    edge_delta = edge - np.asarray(previous_edge, dtype=np.float64)
    node_accel = np.zeros_like(node_delta) if previous_node_delta is None else node_delta - np.asarray(previous_node_delta, dtype=np.float64)
    edge_accel = np.zeros_like(edge_delta) if previous_edge_delta is None else edge_delta - np.asarray(previous_edge_delta, dtype=np.float64)
    node_speed = float(np.sqrt(np.mean(node_delta * node_delta)))
    graph_speed = float(np.sqrt(np.mean(edge_delta * edge_delta)))
    node_acceleration = float(np.sqrt(np.mean(node_accel * node_accel)))
    graph_acceleration = float(np.sqrt(np.mean(edge_accel * edge_accel)))
    node_alignment = rowwise_cosine(node_delta, node_accel)
    graph_alignment = rowwise_cosine(edge_delta, edge_accel)
    values = (node_speed, node_acceleration, graph_speed, graph_acceleration)
    if not all(math.isfinite(x) and x >= 0.0 for x in values):
        raise ValueError("invalid transition energy")
    return node_speed, node_acceleration, graph_speed, graph_acceleration, node_alignment, graph_alignment, node_delta, edge_delta


def transition_ledger_values(transition, offset):
    return {
        "node_speed": format(float(transition["node_speed"][offset]), ".12g"),
        "node_acceleration": format(float(transition["node_acceleration"][offset]), ".12g"),
        "graph_speed": format(float(transition["graph_speed"][offset]), ".12g"),
        "graph_acceleration": format(float(transition["graph_acceleration"][offset]), ".12g"),
        "node_alignment_mean": format(float(transition["node_alignment"][offset].mean()), ".12g"),
        "graph_alignment_mean": format(float(transition["graph_alignment"][offset].mean()), ".12g"),
        "node_graph_coherence_mean": format(float(transition["node_graph_coherence"][offset].mean()), ".12g"),
    }


def directional_operator_scores(base_z, reversion, graph_signal, node_alignment, graph_alignment):
    """Four preregistered fixed-alpha operators; no parameter is tuned on Validation/OOS."""
    arrays = [np.asarray(x, dtype=np.float64) for x in (base_z, reversion, graph_signal, node_alignment, graph_alignment)]
    if any(x.shape != (40,) for x in arrays) or not all(np.isfinite(x).all() for x in arrays):
        raise ValueError("directional operator inputs must be finite length-40 vectors")
    base_z, reversion, graph_signal, node_alignment, graph_alignment = arrays
    coherence = node_alignment * graph_alignment
    blend = 0.5 * (reversion + graph_signal)
    return {
        DYNAMIC_IDS[0]: base_z + 0.20 * reversion * node_alignment,
        DYNAMIC_IDS[1]: base_z - 0.20 * reversion * node_alignment,
        DYNAMIC_IDS[2]: base_z + 0.20 * graph_signal * graph_alignment,
        DYNAMIC_IDS[3]: base_z + 0.20 * blend * coherence,
    }


def _metric_row(model, split, indices, hits, actual_ranks, tests):
    selected = hits[indices, MODEL_IDS.index(model), :]
    ranks = actual_ranks[indices, MODEL_IDS.index(model), :]
    n = len(indices)
    row = {
        "strategy_id": model,
        "split": split,
        "targets": n,
        "mean_hits_top5": float(selected[:, 0].mean()),
        "mean_hits_top10": float(selected[:, 1].mean()),
        "mean_hits_top20": float(selected[:, 2].mean()),
        "mean_rank_actual_numbers": float(ranks.mean()),
        "top20_4plus": int(np.sum(selected[:, 2] >= 4)),
        "top20_5of5": int(np.sum(selected[:, 2] == 5)),
        "top20_5of5_rate": float(np.mean(selected[:, 2] == 5)),
        "top20_hit_distribution": {str(k): int(np.sum(selected[:, 2] == k)) for k in range(6)},
        "p_values_raw": {},
    }
    for endpoint_index, (endpoint, k) in enumerate(ENDPOINTS):
        p_value = field.exact_upper_tail(int(selected[:, endpoint_index].sum()), n, k)
        test_id = f"Q86-DIR|{model}|{split}|{endpoint}"
        tests.append({"test_id": test_id, "p_raw": p_value})
        row["p_values_raw"][endpoint] = p_value
    return row


def compute_experiment(draws=None):
    draws = read_draws() if draws is None else draws
    dates = [item["date"].isoformat() for item in draws]
    if len(draws) != EXPECTED_DRAWS or dates[-1] != EXPECTED_LAST:
        raise ValueError("Q86-DIR archive count/date mismatch")
    total = len(draws) - MIN_HISTORY
    if total != EXPECTED_TARGETS or len(CONFIGS) != 42:
        raise ValueError("Q86-DIR target or fixed-rule family mismatch")
    split_labels = [q84.split_name(index, total) for index in range(total)]
    split_counts = dict(Counter(split_labels))
    expected_splits = {"discovery": 1921, "validation": 640, "blind_oos": 641}
    if split_counts != expected_splits:
        raise ValueError("Q86-DIR chronological split mismatch")

    ranks = np.empty((total, len(MODEL_IDS), 40), dtype=np.int8)
    hits = np.empty((total, len(MODEL_IDS), 3), dtype=np.int8)
    actual_ranks = np.empty((total, len(MODEL_IDS), 5), dtype=np.int8)
    transition = {name: np.zeros(total, dtype=np.float64) for name in ("node_speed", "node_acceleration", "graph_speed", "graph_acceleration")}
    transition["node_alignment"] = np.zeros((total, 40), dtype=np.float64)
    transition["graph_alignment"] = np.zeros((total, 40), dtype=np.float64)
    transition["node_graph_coherence"] = np.zeros((total, 40), dtype=np.float64)
    signatures, directional_signatures = [], []

    flow_states, prior_fixed_hits, prior_turbulence = [], [], []
    previous_features = previous_edge = previous_node_delta = previous_edge_delta = None

    for target_offset, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        target = draws[draw_index]
        flow_state = q84.flow_state(history)
        context = ksens.flow_context_for_k(flow_state, flow_states, prior_fixed_hits, prior_turbulence, 50)
        flow_weights, _, _, effective_n, turbulence, _, _, _, _ = context

        base = feature_scores(history)
        fixed = np.empty((len(CONFIGS), 40), dtype=np.int8)
        for strategy_index, config in enumerate(CONFIGS):
            fixed[strategy_index] = q84.rank_vector_from_order(q84.strategy_order(base, config))
        equal_rank = q84.weighted_borda_rank(fixed, np.ones(len(CONFIGS), dtype=np.float64))
        flow_rank = q84.weighted_borda_rank(fixed, flow_weights)
        base_z = field.zscore(41.0 - equal_rank.astype(np.float64))

        current_field = field.field_state(history)
        current_edge = field.pair_residual_graph(history)
        node_speed, node_accel, graph_speed, graph_accel, node_alignment, graph_alignment, node_delta, edge_delta = transition_metrics(
            current_field["features"], current_edge, previous_features, previous_edge,
            previous_node_delta, previous_edge_delta,
        )
        coherence = node_alignment * graph_alignment

        reversion = current_field["signals"]["REVERSION"]
        graph_only = current_field["graph_signal"]
        operator_scores = directional_operator_scores(base_z, reversion, graph_only, node_alignment, graph_alignment)
        current_ranks = np.vstack([
            equal_rank,
            flow_rank,
            field.rank_from_scores(base_z + 0.20 * reversion),
            field.rank_from_scores(base_z + 0.20 * current_field["signals"]["GRAPH"]),
            *[field.rank_from_scores(operator_scores[model]) for model in DYNAMIC_IDS],
        ])

        actual = np.asarray(target["nums"], dtype=np.int64)
        actual_rank = current_ranks[:, actual - 1]
        current_hits = np.column_stack([
            np.sum(actual_rank <= 5, axis=1),
            np.sum(actual_rank <= 10, axis=1),
            np.sum(actual_rank <= 20, axis=1),
        ]).astype(np.int8)
        ranks[target_offset] = current_ranks
        hits[target_offset] = current_hits
        actual_ranks[target_offset] = actual_rank
        signatures.append(current_field["signature"])

        transition["node_speed"][target_offset] = node_speed
        transition["node_acceleration"][target_offset] = node_accel
        transition["graph_speed"][target_offset] = graph_speed
        transition["graph_acceleration"][target_offset] = graph_accel
        transition["node_alignment"][target_offset] = node_alignment
        transition["graph_alignment"][target_offset] = graph_alignment
        transition["node_graph_coherence"][target_offset] = coherence
        directional_signatures.append(directional_state_hash(node_alignment, graph_alignment, coherence))

        fixed_hits = np.sum(fixed[:, actual - 1] <= 20, axis=1)
        if fixed_hits.shape != (42,):
            raise ValueError("Q86-DIR flow memory requires all 42 fixed-rule outcomes")
        flow_states.append(flow_state)
        prior_fixed_hits.append(fixed_hits.astype(np.float64))
        prior_turbulence.append(turbulence)
        previous_features = current_field["features"]
        previous_edge = current_edge
        previous_node_delta = node_delta
        previous_edge_delta = edge_delta

    split_indices = {split: np.asarray([i for i, label in enumerate(split_labels) if label == split], dtype=np.int64) for split in SPLITS}
    exact_tests, metrics = [], []
    for model in MODEL_IDS:
        for split in SPLITS:
            metrics.append(_metric_row(model, split, split_indices[split], hits, actual_ranks, exact_tests))
    exact_adjusted = q84.holm_adjust(exact_tests)
    for row in metrics:
        row["p_values_holm"] = {
            endpoint: exact_adjusted[f"Q86-DIR|{row['strategy_id']}|{row['split']}|{endpoint}"]
            for endpoint, _ in ENDPOINTS
        }

    discovery_rows = [row for row in metrics if row["split"] == "discovery" and row["strategy_id"] in DYNAMIC_IDS]
    selected_row = sorted(
        discovery_rows,
        key=lambda row: (-row["mean_hits_top20"], row["mean_rank_actual_numbers"], row["strategy_id"]),
    )[0]
    selected_id = selected_row["strategy_id"]
    selected_index = MODEL_IDS.index(selected_id)

    paired_rows, paired_tests = [], []
    for split_index, split in enumerate(("validation", "blind_oos")):
        idx = split_indices[split]
        for comparator_index, comparator in enumerate(COMPARATORS):
            comparator_model_index = MODEL_IDS.index(comparator)
            for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
                result = q84.bootstrap_paired(
                    hits[idx, selected_index, endpoint_index],
                    hits[idx, comparator_model_index, endpoint_index],
                    85000 + split_index * 1000 + comparator_index * 100 + endpoint_index,
                )
                test_id = f"Q86-DIRPAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id": test_id, "p_raw": float(result["p_two_sided"])})
                paired_rows.append({
                    "test_id": test_id, "split": split, "comparator": comparator, "endpoint": endpoint,
                    **result, "positive_difference_favors_selected": True,
                })
            rank_result = q84.bootstrap_paired(
                actual_ranks[idx, comparator_model_index, :].mean(axis=1),
                actual_ranks[idx, selected_index, :].mean(axis=1),
                85000 + split_index * 1000 + comparator_index * 100 + 3,
            )
            test_id = f"Q86-DIRPAIRED|{split}|{comparator}|mean_actual_rank_improvement"
            paired_tests.append({"test_id": test_id, "p_raw": float(rank_result["p_two_sided"])})
            paired_rows.append({
                "test_id": test_id, "split": split, "comparator": comparator,
                "endpoint": "mean_actual_rank_improvement", **rank_result,
                "positive_difference_means_lower_selected_rank": True,
            })
    paired_adjusted = q84.holm_adjust(paired_tests)
    for row in paired_rows:
        row["p_holm"] = paired_adjusted[row["test_id"]]

    def metric_for(model, split):
        return next(row for row in metrics if row["strategy_id"] == model and row["split"] == split)

    def paired_for(split, comparator, endpoint):
        return next(row for row in paired_rows if row["split"] == split and row["comparator"] == comparator and row["endpoint"] == endpoint)

    blind_selected = metric_for(selected_id, "blind_oos")
    blind_equal = metric_for(BASE_EQUAL, "blind_oos")
    blind_primary = paired_for("blind_oos", BASE_EQUAL, "top20")
    validation_selected = metric_for(selected_id, "validation")
    validation_equal = metric_for(BASE_EQUAL, "validation")
    exact_holm = blind_selected["p_values_holm"]["top20"]
    ci_lower = blind_primary["ci95"][0]
    lift = blind_selected["mean_hits_top20"] - blind_equal["mean_hits_top20"]
    gate_pass = (
        blind_selected["mean_hits_top20"] >= 2.5
        and lift >= 0.10
        and ci_lower is not None and ci_lower > 0.0
        and blind_primary["p_holm"] < 0.05
        and exact_holm < 0.05
    )
    primary_gate = {
        "selected_strategy": selected_id,
        "blind_top20": blind_selected["mean_hits_top20"],
        "blind_top20_equal42": blind_equal["mean_hits_top20"],
        "blind_lift_vs_equal42": lift,
        "blind_paired_ci95": blind_primary["ci95"],
        "blind_paired_p_raw": blind_primary["p_two_sided"],
        "blind_paired_p_holm": blind_primary["p_holm"],
        "blind_exact_null_p_holm": exact_holm,
        "validation_lift_vs_equal42": validation_selected["mean_hits_top20"] - validation_equal["mean_hits_top20"],
        "status": "PASS" if gate_pass else "NOT_MET",
    }

    regime_diagnostics = []
    for axis, values in (("node_directional_alignment", transition["node_alignment"].mean(axis=1)), ("graph_directional_alignment", transition["graph_alignment"].mean(axis=1))):
        labels = np.where(values < (-1.0 / 3.0), "negative", np.where(values < (1.0 / 3.0), "neutral", "positive"))
        for split in ("validation", "blind_oos"):
            for regime in ("low", "middle", "high"):
                idx = split_indices[split]
                selected = idx[labels[idx] == regime]
                if len(selected) == 0:
                    continue
                si = MODEL_IDS.index(selected_id)
                bi = MODEL_IDS.index(BASE_EQUAL)
                regime_diagnostics.append({
                    "axis": axis, "split": split, "regime": regime, "targets": int(len(selected)),
                    "selected_strategy": selected_id,
                    "selected_top5": float(hits[selected, si, 0].mean()),
                    "selected_top20": float(hits[selected, si, 2].mean()),
                    "equal42_top5": float(hits[selected, bi, 0].mean()),
                    "equal42_top20": float(hits[selected, bi, 2].mean()),
                    "top5_delta": float((hits[selected, si, 0] - hits[selected, bi, 0]).mean()),
                    "top20_delta": float((hits[selected, si, 2] - hits[selected, bi, 2]).mean()),
                })

    temporal_blocks = []
    idx = split_indices["blind_oos"]
    si, bi = MODEL_IDS.index(selected_id), MODEL_IDS.index(BASE_EQUAL)
    for start in range(0, len(idx), 100):
        block = idx[start:start + 100]
        if len(block) < 40:
            continue
        delta = float((hits[block, si, 2] - hits[block, bi, 2]).mean())
        temporal_blocks.append({"first_target": dates[MIN_HISTORY + int(block[0])],
                                "last_target": dates[MIN_HISTORY + int(block[-1])],
                                "targets": int(len(block)), "top20_delta_vs_equal42": delta})

    return {
        "draws": draws, "dates": dates, "split_labels": split_labels, "split_counts": split_counts,
        "split_indices": split_indices, "ranks": ranks, "hits": hits, "actual_ranks": actual_ranks,
        "transition": transition, "signatures": signatures, "directional_signatures": directional_signatures, "metrics": metrics,
        "exact_tests": exact_tests, "paired_rows": paired_rows, "paired_tests": paired_tests,
        "selected_id": selected_id, "primary_gate": primary_gate,
        "regime_diagnostics": regime_diagnostics, "temporal_blocks": temporal_blocks,
    }


def catalog_entries():
    return [
        {"strategy_id": BASE_EQUAL, "kind": "BASELINE", "definition": "Equal-weight Borda of 42 fixed Q84 rules."},
        {"strategy_id": BASE_FLOW, "kind": "BASELINE", "definition": "Causal Q84 flow-state analogue ensemble, K=50."},
        {"strategy_id": FIXED_REV, "kind": "FIXED_CONTROL", "definition": "Q84 field reversion signal with fixed alpha 0.20."},
        {"strategy_id": FIXED_GRAPH, "kind": "FIXED_CONTROL", "definition": "Q84 graph signal with fixed alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[0], "kind": "DIRECTIONAL_CANDIDATE", "definition": "Per-number reversion signal multiplied by signed node-wise cosine(velocity, acceleration); fixed alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[1], "kind": "DIRECTIONAL_CANDIDATE", "definition": "Per-number reversion signal multiplied by the negative signed node-wise cosine; fixed alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[2], "kind": "DIRECTIONAL_CANDIDATE", "definition": "Per-number graph signal multiplied by signed row-wise cosine(edge velocity, edge acceleration); fixed alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[3], "kind": "DIRECTIONAL_CANDIDATE", "definition": "Blended node/graph signal multiplied by the product of node and graph directional cosines; fixed alpha 0.20."},
    ]


def write_outputs(result, archive_sha1, archive_sha256):
    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
        for item in catalog_entries():
            handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
    fields = ledger_fields()
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for offset, target_date in enumerate(result["dates"][MIN_HISTORY:]):
                    target_index = MIN_HISTORY + offset
                    row = {
                        "target_date": target_date,
                        "cutoff_date": result["dates"][target_index - 1],
                        "prior_draws": target_index,
                        "actual_quintet": " ".join(map(str, sorted(result["draws"][target_index]["nums"]))),
                        "split": result["split_labels"][offset],
                        "field_state_sha256": result["signatures"][offset],
                        "directional_state_sha256": result["directional_signatures"][offset],
                    }
                    row.update(transition_ledger_values(result["transition"], offset))
                    for number in range(1, 41):
                        row[f"node_alignment_{number:02d}"] = format(float(result["transition"]["node_alignment"][offset, number - 1]), ".12g")
                        row[f"graph_alignment_{number:02d}"] = format(float(result["transition"]["graph_alignment"][offset, number - 1]), ".12g")
                        row[f"node_graph_coherence_{number:02d}"] = format(float(result["transition"]["node_graph_coherence"][offset, number - 1]), ".12g")
                    for model_index, model in enumerate(MODEL_IDS):
                        for number, rank in enumerate(result["ranks"][offset, model_index], 1):
                            row[f"rank_{slug(model)}_{number:02d}"] = int(rank)
                    writer.writerow(row)

    blind_exact = [row for row in result["metrics"] if row["split"] == "blind_oos"]
    report = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "task_id": "Q86-DIR-01",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive": {
            "draw_count": len(result["draws"]), "first_date": result["dates"][0],
            "last_date": result["dates"][-1], "git_blob_sha1": archive_sha1,
            "sha256": archive_sha256,
        },
        "source_code_commit": os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "models": list(MODEL_IDS),
        "adaptive_candidates": list(DYNAMIC_IDS),
        "selected_on_discovery_only": result["selected_id"],
        "selection_rule": "Discovery mean Top20 hits; tie lower mean actual rank then stable ID.",
        "metrics": result["metrics"],
        "multiple_testing": {
            "exact_null_method": "global Holm-Bonferroni",
            "exact_null_family_size": len(result["exact_tests"]),
            "exact_null_p_method": "discrete upper-tail convolution of iid Hypergeometric(40,k,5) hit counts",
            "paired_method": "global Holm-Bonferroni across paired moving-block bootstrap tests",
            "paired_family_size": len(result["paired_tests"]),
        },
        "paired_block_bootstrap": result["paired_rows"],
        "primary_gate": result["primary_gate"],
        "regime_diagnostics": result["regime_diagnostics"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "transition_metric_summary": {
            name: {
                "median": float(np.median(values)),
                "p90": float(np.quantile(values, 0.90)),
                "maximum": float(np.max(values)),
            } for name, values in result["transition"].items()
            if name in ("node_speed", "node_acceleration", "graph_speed", "graph_acceleration")
        },
        "directional_metric_summary": {
            name: {"mean": float(np.mean(values)), "p10": float(np.quantile(values, 0.10)), "p90": float(np.quantile(values, 0.90))}
            for name, values in result["transition"].items()
            if name in ("node_alignment", "graph_alignment", "node_graph_coherence")
        },
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "limitations": [
            "Historical Blind OOS is already exposed to prior SONAR research.",
            "Four preregistered directional operators are a finite grammar, not every possible function of the field.",
            "The pair graph is a historical association descriptor, not physical coupling; row-wise graph cosine is not a physical force.",
            "The exact hypergeometric null assumes independent uniform 5-of-40 draws; paired block bootstrap is reported separately.",
            "Regime-conditioned rows and 100-target temporal blocks are descriptive diagnostics, not additional confirmatory claims.",
        ],
        "next_action": "If the directional gate is not met, retain the negative result; inspect signed alignment distributions and local-versus-graph coherence without tuning on the historical Blind OOS, then reserve new prospective targets for confirmation.",
    }
    json_dump(REPORT, report)
    files = {
        "catalog": {"path": str(CATALOG.relative_to(ROOT)), "sha256": sha256_file(CATALOG), "bytes": CATALOG.stat().st_size},
        "target_ledger": {"path": str(LEDGER.relative_to(ROOT)), "sha256": sha256_file(LEDGER), "bytes": LEDGER.stat().st_size, "rows": len(result["split_labels"])},
        "report": {"path": str(REPORT.relative_to(ROOT)), "sha256": sha256_file(REPORT), "bytes": REPORT.stat().st_size},
    }
    manifest = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_git_blob_sha1": archive_sha1,
        "source_archive_sha256": archive_sha256,
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "model_count": len(MODEL_IDS),
        "adaptive_candidate_count": len(DYNAMIC_IDS),
        "rank_vectors": len(result["split_labels"]) * len(MODEL_IDS),
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "ledger_fields": ledger_fields(),
        "files": files,
    }
    json_dump(MANIFEST, manifest)
    json_dump(CHECKPOINT, {
        "checkpoint_id": "SONAR-Q86-DIR-REGIME-TRANSITION-2026-11-09",
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_sha256": archive_sha256,
        "target_count": len(result["split_labels"]),
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"],
        "next_action": "Replay all target states/ranks and verify exact persisted bytes; human review and prospective confirmation required.",
    })


def main():
    for path in (CATALOG, LEDGER, REPORT, MANIFEST, CHECKPOINT, VALIDATION):
        if path.exists():
            raise SystemExit("Q86-DIR_BLOCKED: append-only output already exists: " + str(path))
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    archive_sha1 = q84.git_blob_sha1(ARCHIVE)
    if archive_sha256 != EXPECTED_SHA256 or archive_sha1 != EXPECTED_SHA1:
        raise SystemExit("Q86-DIR_BLOCKED: canonical archive identity mismatch")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol["source_archive"]["sha256"] != archive_sha256 or protocol["source_archive"]["git_blob_sha1"] != archive_sha1:
        raise SystemExit("Q86-DIR_BLOCKED: protocol/archive identity mismatch")
    result = compute_experiment()
    write_outputs(result, archive_sha1, archive_sha256)
    summary = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "targets": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "models": len(MODEL_IDS),
        "adaptive_candidates": len(DYNAMIC_IDS),
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"],
        "archive_sha256": archive_sha256,
    }
    print("SONAR_Q86-DIR_REGIME_SUMMARY_BEGIN")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q86-DIR_REGIME_SUMMARY_END")


if __name__ == "__main__":
    main()
