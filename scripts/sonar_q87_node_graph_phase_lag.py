#!/usr/bin/env python3
"""Q87 causal node/graph phase-lag field for the VinciCasa 40-node SONAR model."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sonar_q86_directional_dynamics as q86
import sonar_per_number_field_dynamics as field
from sonar_sequence_agent import MIN_HISTORY, read_draws

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "q87_node_graph_phase_lag_protocol_2026-11-10.json"
CATALOG = OUT / "q87_node_graph_phase_lag_catalog.jsonl"
LEDGER = OUT / "q87_node_graph_phase_lag_target_ledger.csv.gz"
REPORT = OUT / "q87_node_graph_phase_lag_report.json"
MANIFEST = OUT / "q87_node_graph_phase_lag_manifest.json"
CHECKPOINT = OUT / "q87_node_graph_phase_lag_checkpoint_2026-11-10.json"
VALIDATION = OUT / "q87_node_graph_phase_lag_validation.json"

DYNAMIC_IDS = (
    "DYN::NODE_LEADS_GRAPH",
    "DYN::GRAPH_LEADS_NODE",
    "DYN::PHASE_ASYMMETRY",
    "DYN::BIDIRECTIONAL_PHASE_COHERENCE",
)
MODEL_IDS = tuple(q86.MODEL_IDS) + DYNAMIC_IDS
COMPARATORS = tuple(q86.COMPARATORS)
SPLITS = ("discovery", "validation", "blind_oos")
ENDPOINTS = (("top5", 5), ("top10", 10), ("top20", 20))
WINDOW = 80
LAGS = (1, 2, 3)
MIN_PAIRED = 30
ALPHA = 0.20
EXPECTED_SHA1 = q86.EXPECTED_SHA1
EXPECTED_SHA256 = q86.EXPECTED_SHA256
EXPECTED_DRAWS = q86.EXPECTED_DRAWS
EXPECTED_LAST = q86.EXPECTED_LAST
EXPECTED_TARGETS = q86.EXPECTED_TARGETS


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
        "node_speed_mean", "graph_row_speed_mean",
    ]
    for number in range(1, 41):
        fields.extend([
            f"node_leads_graph_{number:02d}",
            f"graph_leads_node_{number:02d}",
            f"phase_asymmetry_{number:02d}",
            f"bidirectional_phase_coherence_{number:02d}",
        ])
    for model in MODEL_IDS:
        fields.extend(f"rank_{slug(model)}_{number:02d}" for number in range(1, 41))
    return fields


def lagged_correlation(node_series, graph_series, lag, direction="node_leads_graph", minimum_pairs=MIN_PAIRED):
    """Per-number Pearson correlation. Positive lag means the named source leads the other series."""
    node = np.asarray(node_series, dtype=np.float64)
    graph = np.asarray(graph_series, dtype=np.float64)
    if node.shape != graph.shape or node.ndim != 2 or node.shape[1] != 40:
        raise ValueError("lag correlation requires matching (time,40) arrays")
    if not np.isfinite(node).all() or not np.isfinite(graph).all():
        raise ValueError("non-finite lag-correlation input")
    lag = int(lag)
    if lag < 1 or direction not in ("node_leads_graph", "graph_leads_node"):
        raise ValueError("invalid lag or direction")
    if direction == "node_leads_graph":
        left, right = node[:-lag], graph[lag:]
    else:
        left, right = node[lag:], graph[:-lag]
    if len(left) < int(minimum_pairs):
        return np.zeros(40, dtype=np.float64)
    left = left - left.mean(axis=0, keepdims=True)
    right = right - right.mean(axis=0, keepdims=True)
    numerator = np.sum(left * right, axis=0)
    denominator = np.linalg.norm(left, axis=0) * np.linalg.norm(right, axis=0)
    result = np.divide(numerator, denominator, out=np.zeros(40, dtype=np.float64), where=denominator > 1e-12)
    return np.clip(result, -1.0, 1.0)


def phase_lag_features(node_speed_history, graph_speed_history, target_offset,
                       window=WINDOW, lags=LAGS, minimum_pairs=MIN_PAIRED):
    """Use no transition later than target_offset; future rows are deliberately sliced away."""
    node = np.asarray(node_speed_history, dtype=np.float64)
    graph = np.asarray(graph_speed_history, dtype=np.float64)
    if node.shape != graph.shape or node.ndim != 2 or node.shape[1] != 40:
        raise ValueError("phase history must be matching (time,40) arrays")
    if not np.isfinite(node).all() or not np.isfinite(graph).all():
        raise ValueError("non-finite phase history")
    end = int(target_offset) + 1
    if end < 1 or end > len(node):
        raise ValueError("target offset outside phase history")
    start = max(0, end - int(window))
    node_prefix = node[start:end]
    graph_prefix = graph[start:end]
    forward = np.mean(
        np.vstack([lagged_correlation(node_prefix, graph_prefix, lag, "node_leads_graph", minimum_pairs) for lag in lags]),
        axis=0,
    )
    backward = np.mean(
        np.vstack([lagged_correlation(node_prefix, graph_prefix, lag, "graph_leads_node", minimum_pairs) for lag in lags]),
        axis=0,
    )
    asymmetry = forward - backward
    coherence = 0.5 * (forward + backward)
    if not all(np.isfinite(x).all() for x in (forward, backward, asymmetry, coherence)):
        raise ValueError("non-finite phase feature")
    if np.any(np.abs(forward) > 1.0 + 1e-10) or np.any(np.abs(backward) > 1.0 + 1e-10):
        raise ValueError("phase correlation outside [-1,1]")
    return forward, backward, asymmetry, coherence


def phase_operator_scores(base_z, reversion, graph_signal, forward, backward, asymmetry, coherence):
    arrays = [np.asarray(x, dtype=np.float64) for x in
              (base_z, reversion, graph_signal, forward, backward, asymmetry, coherence)]
    if any(x.shape != (40,) for x in arrays) or not all(np.isfinite(x).all() for x in arrays):
        raise ValueError("phase operator inputs must be finite length-40 vectors")
    base_z, reversion, graph_signal, forward, backward, asymmetry, coherence = arrays
    blend = 0.5 * (reversion + graph_signal)
    return {
        DYNAMIC_IDS[0]: base_z + ALPHA * reversion * field.zscore(forward),
        DYNAMIC_IDS[1]: base_z + ALPHA * graph_signal * field.zscore(backward),
        DYNAMIC_IDS[2]: base_z + ALPHA * blend * field.zscore(asymmetry),
        DYNAMIC_IDS[3]: base_z + ALPHA * blend * field.zscore(coherence),
    }


def _metric_row(model, split, indices, hits, actual_ranks, tests):
    model_index = MODEL_IDS.index(model)
    selected = hits[indices, model_index, :]
    ranks = actual_ranks[indices, model_index, :]
    n = len(indices)
    row = {
        "strategy_id": model,
        "split": split,
        "targets": int(n),
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
        test_id = f"Q87|{model}|{split}|{endpoint}"
        tests.append({"test_id": test_id, "p_raw": p_value})
        row["p_values_raw"][endpoint] = p_value
    return row


def compute_experiment(draws=None):
    draws = read_draws() if draws is None else draws
    dates = [item["date"].isoformat() for item in draws]
    if len(draws) != EXPECTED_DRAWS or dates[-1] != EXPECTED_LAST:
        raise ValueError("Q87 archive count/date mismatch")
    if len(draws) - MIN_HISTORY != EXPECTED_TARGETS:
        raise ValueError("Q87 target count mismatch")

    # Q86 supplies the eight frozen comparator rankings; no Q87 outcome enters this call.
    prior = q86.compute_experiment(draws)
    split_labels = list(prior["split_labels"])
    split_counts = dict(Counter(split_labels))
    if split_counts != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise ValueError("Q87 chronological split mismatch")

    total = len(split_labels)
    candidate_ranks = np.empty((total, len(DYNAMIC_IDS), 40), dtype=np.int8)
    candidate_hits = np.empty((total, len(DYNAMIC_IDS), 3), dtype=np.int8)
    candidate_actual_ranks = np.empty((total, len(DYNAMIC_IDS), 5), dtype=np.int8)
    phase = {
        "node_speed": np.zeros((total, 40), dtype=np.float64),
        "graph_row_speed": np.zeros((total, 40), dtype=np.float64),
        "node_leads_graph": np.zeros((total, 40), dtype=np.float64),
        "graph_leads_node": np.zeros((total, 40), dtype=np.float64),
        "phase_asymmetry": np.zeros((total, 40), dtype=np.float64),
        "bidirectional_phase_coherence": np.zeros((total, 40), dtype=np.float64),
    }
    node_speed_history = np.zeros((total, 40), dtype=np.float64)
    graph_speed_history = np.zeros((total, 40), dtype=np.float64)
    previous_features = previous_edge = previous_node_delta = previous_edge_delta = None

    equal_index = q86.MODEL_IDS.index(q86.BASE_EQUAL)
    for target_offset, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        current_field = field.field_state(history)
        current_edge = field.pair_residual_graph(history)
        node_speed, node_accel, graph_speed, graph_accel, node_alignment, graph_alignment, node_delta, edge_delta = q86.transition_metrics(
            current_field["features"], current_edge,
            previous_features, previous_edge, previous_node_delta, previous_edge_delta,
        )
        if node_delta is None or edge_delta is None:
            node_velocity_magnitude = np.zeros(40, dtype=np.float64)
            graph_velocity_magnitude = np.zeros(40, dtype=np.float64)
        else:
            node_velocity_magnitude = np.linalg.norm(node_delta, axis=1)
            graph_velocity_magnitude = np.linalg.norm(edge_delta, axis=1)
        node_speed_history[target_offset] = node_velocity_magnitude
        graph_speed_history[target_offset] = graph_velocity_magnitude

        forward, backward, asymmetry, coherence = phase_lag_features(
            node_speed_history, graph_speed_history, target_offset
        )
        equal_rank = prior["ranks"][target_offset, equal_index]
        base_z = field.zscore(41.0 - equal_rank.astype(np.float64))
        reversion = current_field["signals"]["REVERSION"]
        graph_signal = current_field["graph_signal"]
        scores = phase_operator_scores(base_z, reversion, graph_signal, forward, backward, asymmetry, coherence)
        for candidate_index, model in enumerate(DYNAMIC_IDS):
            rank = field.rank_from_scores(scores[model])
            candidate_ranks[target_offset, candidate_index] = rank
            actual = np.asarray(draws[draw_index]["nums"], dtype=np.int64)
            actual_rank = rank[actual - 1]
            candidate_actual_ranks[target_offset, candidate_index] = actual_rank
            candidate_hits[target_offset, candidate_index] = (
                np.sum(actual_rank <= 5), np.sum(actual_rank <= 10), np.sum(actual_rank <= 20)
            )

        phase["node_speed"][target_offset] = node_velocity_magnitude
        phase["graph_row_speed"][target_offset] = graph_velocity_magnitude
        phase["node_leads_graph"][target_offset] = forward
        phase["graph_leads_node"][target_offset] = backward
        phase["phase_asymmetry"][target_offset] = asymmetry
        phase["bidirectional_phase_coherence"][target_offset] = coherence

        # Advance the state only after the current pre-target ranking has been frozen.
        previous_features = current_field["features"]
        previous_edge = current_edge
        previous_node_delta = node_delta
        previous_edge_delta = edge_delta

    ranks = np.concatenate([prior["ranks"], candidate_ranks], axis=1)
    hits = np.concatenate([prior["hits"], candidate_hits], axis=1)
    actual_ranks = np.concatenate([prior["actual_ranks"], candidate_actual_ranks], axis=1)
    split_indices = prior["split_indices"]

    exact_tests, metrics = [], []
    for model in MODEL_IDS:
        for split in SPLITS:
            metrics.append(_metric_row(model, split, split_indices[split], hits, actual_ranks, exact_tests))
    exact_adjusted = q86.q84.holm_adjust(exact_tests)
    for row in metrics:
        row["p_values_holm"] = {
            endpoint: exact_adjusted[f"Q87|{row['strategy_id']}|{row['split']}|{endpoint}"]
            for endpoint, _ in ENDPOINTS
        }

    discovery_rows = [
        row for row in metrics
        if row["split"] == "discovery" and row["strategy_id"] in DYNAMIC_IDS
    ]
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
            comparator_index_model = MODEL_IDS.index(comparator)
            for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
                result = q86.q84.bootstrap_paired(
                    hits[idx, selected_index, endpoint_index],
                    hits[idx, comparator_index_model, endpoint_index],
                    87000 + split_index * 1000 + comparator_index * 100 + endpoint_index,
                )
                test_id = f"Q87PAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id": test_id, "p_raw": float(result["p_two_sided"])})
                paired_rows.append({
                    "test_id": test_id, "split": split, "comparator": comparator,
                    "endpoint": endpoint, **result, "positive_difference_favors_selected": True,
                })
            rank_result = q86.q84.bootstrap_paired(
                actual_ranks[idx, comparator_index_model, :].mean(axis=1),
                actual_ranks[idx, selected_index, :].mean(axis=1),
                87000 + split_index * 1000 + comparator_index * 100 + 3,
            )
            test_id = f"Q87PAIRED|{split}|{comparator}|mean_actual_rank_improvement"
            paired_tests.append({"test_id": test_id, "p_raw": float(rank_result["p_two_sided"])})
            paired_rows.append({
                "test_id": test_id, "split": split, "comparator": comparator,
                "endpoint": "mean_actual_rank_improvement", **rank_result,
                "positive_difference_means_lower_selected_rank": True,
            })
    paired_adjusted = q86.q84.holm_adjust(paired_tests)
    for row in paired_rows:
        row["p_holm"] = paired_adjusted[row["test_id"]]

    def metric_for(model, split):
        return next(row for row in metrics if row["strategy_id"] == model and row["split"] == split)

    def paired_for(split, comparator, endpoint):
        return next(row for row in paired_rows if row["split"] == split and row["comparator"] == comparator and row["endpoint"] == endpoint)

    blind_selected = metric_for(selected_id, "blind_oos")
    blind_equal = metric_for(q86.BASE_EQUAL, "blind_oos")
    blind_primary = paired_for("blind_oos", q86.BASE_EQUAL, "top20")
    validation_selected = metric_for(selected_id, "validation")
    validation_equal = metric_for(q86.BASE_EQUAL, "validation")
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

    phase_diagnostics = []
    for split in SPLITS:
        idx = split_indices[split]
        for name in ("node_leads_graph", "graph_leads_node", "phase_asymmetry", "bidirectional_phase_coherence"):
            values = phase[name][idx]
            phase_diagnostics.append({
                "split": split, "signal": name,
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "positive_fraction": float(np.mean(values > 0.0)),
                "near_zero_fraction": float(np.mean(np.abs(values) < 0.05)),
            })

    temporal_blocks = []
    blind_idx = split_indices["blind_oos"]
    equal_model_index = MODEL_IDS.index(q86.BASE_EQUAL)
    for start in range(0, len(blind_idx), 100):
        block = blind_idx[start:start + 100]
        if len(block) < 40:
            continue
        delta = float((hits[block, selected_index, 2] - hits[block, equal_model_index, 2]).mean())
        temporal_blocks.append({
            "first_target": dates[MIN_HISTORY + int(block[0])],
            "last_target": dates[MIN_HISTORY + int(block[-1])],
            "targets": int(len(block)),
            "top20_delta_vs_equal42": delta,
        })

    return {
        "draws": draws, "dates": dates, "split_labels": split_labels, "split_counts": split_counts,
        "split_indices": split_indices, "ranks": ranks, "hits": hits, "actual_ranks": actual_ranks,
        "phase": phase, "metrics": metrics, "exact_tests": exact_tests,
        "paired_rows": paired_rows, "paired_tests": paired_tests,
        "selected_id": selected_id, "primary_gate": primary_gate,
        "phase_diagnostics": phase_diagnostics, "temporal_blocks": temporal_blocks,
    }


def catalog_entries():
    entries = q86.catalog_entries()
    entries.extend([
        {"strategy_id": DYNAMIC_IDS[0], "kind": "PHASE_LAG_CANDIDATE",
         "definition": "Per-number reversion signal times prior-80-transition mean cross-correlation at lags +1,+2,+3; node activity leads graph activity; alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[1], "kind": "PHASE_LAG_CANDIDATE",
         "definition": "Per-number graph signal times prior-80-transition mean cross-correlation at lags -1,-2,-3; graph activity leads node activity; alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[2], "kind": "PHASE_LAG_CANDIDATE",
         "definition": "Mean node/graph signal times z-scored forward-minus-backward lag correlation; alpha 0.20."},
        {"strategy_id": DYNAMIC_IDS[3], "kind": "PHASE_LAG_CANDIDATE",
         "definition": "Mean node/graph signal times z-scored symmetric forward/backward lag correlation; alpha 0.20."},
    ])
    return entries


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
                        "node_speed_mean": format(float(result["phase"]["node_speed"][offset].mean()), ".12g"),
                        "graph_row_speed_mean": format(float(result["phase"]["graph_row_speed"][offset].mean()), ".12g"),
                    }
                    for number in range(1, 41):
                        j = number - 1
                        row[f"node_leads_graph_{number:02d}"] = format(float(result["phase"]["node_leads_graph"][offset, j]), ".12g")
                        row[f"graph_leads_node_{number:02d}"] = format(float(result["phase"]["graph_leads_node"][offset, j]), ".12g")
                        row[f"phase_asymmetry_{number:02d}"] = format(float(result["phase"]["phase_asymmetry"][offset, j]), ".12g")
                        row[f"bidirectional_phase_coherence_{number:02d}"] = format(float(result["phase"]["bidirectional_phase_coherence"][offset, j]), ".12g")
                    for model_index, model in enumerate(MODEL_IDS):
                        for number, rank in enumerate(result["ranks"][offset, model_index], 1):
                            row[f"rank_{slug(model)}_{number:02d}"] = int(rank)
                    writer.writerow(row)

    report = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "task_id": "Q87-NODE-GRAPH-PHASE-LAG-01",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive": {
            "draw_count": len(result["draws"]),
            "first_date": result["dates"][0],
            "last_date": result["dates"][-1],
            "git_blob_sha1": archive_sha1,
            "sha256": archive_sha256,
        },
        "source_code_commit": os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "models": list(MODEL_IDS),
        "phase_lag_candidates": list(DYNAMIC_IDS),
        "phase_definition": {
            "window_transitions": WINDOW, "lags": list(LAGS),
            "minimum_paired_observations": MIN_PAIRED,
            "positive_lag": "node leads graph",
            "negative_lag": "graph leads node",
            "alpha": ALPHA,
        },
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
        "phase_diagnostics": result["phase_diagnostics"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "phase_summary": {
            name: {
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "p10": float(np.quantile(values, 0.10)),
                "p90": float(np.quantile(values, 0.90)),
            } for name, values in result["phase"].items()
        },
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "limitations": [
            "Historical Blind OOS has prior exposure to SONAR research and is not a virgin holdout.",
            "Lagged correlations use transition magnitudes, not signed physical velocities; they are statistical descriptors, not fluid-mechanical phase.",
            "The 80-transition window and lags 1-3 are preregistered finite choices, not an exhaustive lag grammar.",
            "Pearson correlations can be unstable when per-number transition magnitudes have low variance; zero-variance cases are mapped to neutral zero.",
            "The exact hypergeometric null assumes independent uniform 5-of-40 draws; paired block bootstrap addresses temporal dependence in comparator deltas separately.",
            "Acceptance certifies causal cutoffs and computational replay, not predictive efficacy."
        ],
        "next_action": "If the phase-lag gate is not met, retain the result and inspect whether lag direction is stable across time without tuning on historical Blind OOS; any next operator family must be preregistered and confirmed prospectively."
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
        "phase_candidate_count": len(DYNAMIC_IDS),
        "rank_vectors": len(result["split_labels"]) * len(MODEL_IDS),
        "phase_values": len(result["split_labels"]) * 40 * 4,
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "ledger_fields": ledger_fields(),
        "files": files,
    }
    json_dump(MANIFEST, manifest)
    json_dump(CHECKPOINT, {
        "checkpoint_id": "SONAR-Q87-NODE-GRAPH-PHASE-LAG-2026-11-10",
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_git_blob_sha1": archive_sha1,
        "source_archive_sha256": archive_sha256,
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"],
        "next_action": "Independent full replay, strict-prefix/correlation validation, append-only persistence and exact-byte readback; human review required."
    })


def main():
    for path in (CATALOG, LEDGER, REPORT, MANIFEST, CHECKPOINT, VALIDATION):
        if path.exists():
            raise SystemExit("Q87_BLOCKED: append-only output already exists: " + str(path))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    archive_sha1 = q86.q84.git_blob_sha1(ARCHIVE)
    if archive_sha1 != EXPECTED_SHA1 or archive_sha256 != EXPECTED_SHA256:
        raise SystemExit("Q87_BLOCKED: canonical archive identity mismatch")
    if protocol["source_archive"]["sha256"] != archive_sha256 or protocol["source_archive"]["git_blob_sha1"] != archive_sha1:
        raise SystemExit("Q87_BLOCKED: preregistration/archive identity mismatch")
    result = compute_experiment()
    write_outputs(result, archive_sha1, archive_sha256)
    summary = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "targets": len(result["split_labels"]),
        "splits": result["split_counts"],
        "models": len(MODEL_IDS),
        "phase_candidates": len(DYNAMIC_IDS),
        "rank_vectors": len(result["split_labels"]) * len(MODEL_IDS),
        "phase_values": len(result["split_labels"]) * 40 * 4,
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"]["status"],
        "archive_sha256": archive_sha256,
    }
    print("SONAR_Q87_SUMMARY_BEGIN")
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q87_SUMMARY_END")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    main()
