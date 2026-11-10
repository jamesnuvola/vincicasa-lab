#!/usr/bin/env python3
"""Q88 signed node-to-graph transfer by prior neighbor-state projection."""
from __future__ import annotations
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
import sonar_q87_node_graph_phase_lag as q87

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "q88_signed_node_graph_transfer_protocol_2026-11-10.json"
CATALOG = OUT / "q88_signed_node_graph_transfer_catalog.jsonl"
LEDGER = OUT / "q88_signed_node_graph_transfer_target_ledger.csv.gz"
REPORT = OUT / "q88_signed_node_graph_transfer_report.json"
MANIFEST = OUT / "q88_signed_node_graph_transfer_manifest.json"
CHECKPOINT = OUT / "q88_signed_node_graph_transfer_checkpoint_2026-11-10.json"
VALIDATION = OUT / "q88_signed_node_graph_transfer_validation.json"

DYNAMIC_IDS = (
    "DYN::TRANSFER_REVERSION",
    "DYN::TRANSFER_GRAPH",
    "DYN::TRANSFER_BLEND",
)
MODEL_IDS = tuple(q87.MODEL_IDS) + DYNAMIC_IDS
COMPARATORS = tuple(q87.MODEL_IDS)
SPLITS = tuple(q87.SPLITS)
ENDPOINTS = tuple(q87.ENDPOINTS)
WINDOW = 20
DECAY = 0.80
ALPHA = 0.20
EXPECTED_SHA1 = q87.EXPECTED_SHA1
EXPECTED_SHA256 = q87.EXPECTED_SHA256
EXPECTED_DRAWS = q87.EXPECTED_DRAWS
EXPECTED_LAST = q87.EXPECTED_LAST
EXPECTED_TARGETS = q87.EXPECTED_TARGETS


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
    fields = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "split"]
    for number in range(1, 41):
        fields.extend([f"transfer_cosine_{number:02d}", f"transfer_ewma_{number:02d}"])
    for model in MODEL_IDS:
        fields.extend(f"rank_{slug(model)}_{number:02d}" for number in range(1, 41))
    return fields


def projected_graph_change(edge_delta, prior_features):
    """Project each node's 40-edge change row into the 6 prior neighbor-feature channels."""
    edge = np.asarray(edge_delta, dtype=np.float64)
    features = np.asarray(prior_features, dtype=np.float64)
    if edge.shape != (40, 40) or features.shape != (40, 6):
        raise ValueError("projection requires edge_delta (40,40) and prior_features (40,6)")
    if not np.isfinite(edge).all() or not np.isfinite(features).all():
        raise ValueError("non-finite graph projection input")
    if not np.allclose(edge, edge.T, atol=1e-10, rtol=0):
        raise ValueError("pair-graph transition must be symmetric")
    if np.any(np.abs(np.diag(edge)) > 1e-10):
        raise ValueError("pair-graph transition diagonal must be zero")
    projected = (edge @ features) / np.sqrt(39.0)
    if not np.isfinite(projected).all():
        raise ValueError("non-finite projected graph change")
    return projected


def rowwise_signed_cosine(left, right):
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2 or a.shape[0] != 40:
        raise ValueError("signed cosine requires matching 40-row matrices")
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("non-finite signed cosine input")
    numerator = np.sum(a * b, axis=1)
    denominator = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    result = np.divide(numerator, denominator, out=np.zeros(40, dtype=np.float64), where=denominator > 1e-12)
    return np.clip(result, -1.0, 1.0)


def signed_transfer_alignment(node_delta, edge_delta, prior_features):
    node = np.asarray(node_delta, dtype=np.float64)
    if node.shape != (40, 6) or not np.isfinite(node).all():
        raise ValueError("node transition must be a finite 40x6 matrix")
    projected = projected_graph_change(edge_delta, prior_features)
    return rowwise_signed_cosine(node, projected)


def rolling_signed_transfer(history, target_offset, window=WINDOW, decay=DECAY):
    """Weighted mean through target_offset only; later rows are deliberately excluded."""
    values = np.asarray(history, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 40 or not np.isfinite(values).all():
        raise ValueError("transfer history must be finite (time,40)")
    end = int(target_offset) + 1
    if end < 1 or end > len(values):
        raise ValueError("target offset outside transfer history")
    if int(window) < 1 or not 0.0 < float(decay) <= 1.0:
        raise ValueError("invalid transfer smoothing parameters")
    prefix = values[max(0, end - int(window)):end]
    weights = float(decay) ** np.arange(len(prefix) - 1, -1, -1, dtype=np.float64)
    return np.average(prefix, axis=0, weights=weights)


def transfer_operator_scores(base_z, reversion, graph_signal, transfer):
    arrays = [np.asarray(x, dtype=np.float64) for x in (base_z, reversion, graph_signal, transfer)]
    if any(x.shape != (40,) for x in arrays) or not all(np.isfinite(x).all() for x in arrays):
        raise ValueError("transfer operators require finite length-40 vectors")
    base_z, reversion, graph_signal, transfer = arrays
    signal = q87.field.zscore(transfer)
    blend = 0.5 * (reversion + graph_signal)
    return {
        DYNAMIC_IDS[0]: base_z + ALPHA * reversion * signal,
        DYNAMIC_IDS[1]: base_z + ALPHA * graph_signal * signal,
        DYNAMIC_IDS[2]: base_z + ALPHA * blend * signal,
    }


def metric_row(model, split, indices, hits, actual_ranks, tests):
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
        p_value = q87.field.exact_upper_tail(int(selected[:, endpoint_index].sum()), n, k)
        test_id = f"Q88|{model}|{split}|{endpoint}"
        tests.append({"test_id": test_id, "p_raw": p_value})
        row["p_values_raw"][endpoint] = p_value
    return row


def compute_experiment(draws=None):
    draws = q87.read_draws() if draws is None else draws
    dates = [item["date"].isoformat() for item in draws]
    if len(draws) != EXPECTED_DRAWS or dates[-1] != EXPECTED_LAST:
        raise ValueError("Q88 archive count/date mismatch")
    if len(draws) - q87.q86.q84.MIN_HISTORY != EXPECTED_TARGETS:
        raise ValueError("Q88 target count mismatch")

    # All 12 Q87 rankings are frozen comparators; Q88 candidates use the same strict prefixes.
    prior = q87.compute_experiment(draws)
    split_labels = list(prior["split_labels"])
    split_counts = dict(Counter(split_labels))
    expected_splits = {"discovery": 1921, "validation": 640, "blind_oos": 641}
    if split_counts != expected_splits:
        raise ValueError("Q88 chronological split mismatch")

    total = len(split_labels)
    candidate_ranks = np.empty((total, len(DYNAMIC_IDS), 40), dtype=np.int8)
    candidate_hits = np.empty((total, len(DYNAMIC_IDS), 3), dtype=np.int8)
    candidate_actual_ranks = np.empty((total, len(DYNAMIC_IDS), 5), dtype=np.int8)
    transfer_raw = np.zeros((total, 40), dtype=np.float64)
    transfer_ewma = np.zeros((total, 40), dtype=np.float64)
    transition_history = []
    previous_features = None
    previous_edge = None
    equal_index = q87.MODEL_IDS.index(q87.q86.BASE_EQUAL)

    for target_offset, draw_index in enumerate(range(q87.q86.q84.MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        current_field = q87.field.field_state(history)
        current_edge = q87.field.pair_residual_graph(history)
        if previous_features is None or previous_edge is None:
            current_transfer = np.zeros(40, dtype=np.float64)
        else:
            node_delta = current_field["features"] - previous_features
            edge_delta = current_edge - previous_edge
            current_transfer = signed_transfer_alignment(node_delta, edge_delta, previous_features)
        transition_history.append(current_transfer)
        transfer_raw[target_offset] = current_transfer
        smooth = rolling_signed_transfer(np.asarray(transition_history), target_offset)
        transfer_ewma[target_offset] = smooth

        equal_rank = prior["ranks"][target_offset, equal_index]
        base_z = q87.field.zscore(41.0 - equal_rank.astype(np.float64))
        reversion = current_field["signals"]["REVERSION"]
        graph_signal = current_field["graph_signal"]
        scores = transfer_operator_scores(base_z, reversion, graph_signal, smooth)
        actual = np.asarray(draws[draw_index]["nums"], dtype=np.int64)

        # Freeze all rankings before reading the target outcome.
        for candidate_index, model in enumerate(DYNAMIC_IDS):
            rank = q87.field.rank_from_scores(scores[model])
            candidate_ranks[target_offset, candidate_index] = rank
            actual_rank = rank[actual - 1]
            candidate_actual_ranks[target_offset, candidate_index] = actual_rank
            candidate_hits[target_offset, candidate_index] = (
                np.sum(actual_rank <= 5), np.sum(actual_rank <= 10), np.sum(actual_rank <= 20)
            )

        previous_features = current_field["features"]
        previous_edge = current_edge

    ranks = np.concatenate([prior["ranks"], candidate_ranks], axis=1)
    hits = np.concatenate([prior["hits"], candidate_hits], axis=1)
    actual_ranks = np.concatenate([prior["actual_ranks"], candidate_actual_ranks], axis=1)
    split_indices = prior["split_indices"]

    exact_tests, metrics = [], []
    for model in MODEL_IDS:
        for split in SPLITS:
            metrics.append(metric_row(model, split, split_indices[split], hits, actual_ranks, exact_tests))
    if len(exact_tests) != 135:
        raise ValueError("Q88 exact-null family must contain 135 tests")
    exact_adjusted = q87.q86.q84.holm_adjust(exact_tests)
    for row in metrics:
        row["p_values_holm"] = {
            endpoint: exact_adjusted[f"Q88|{row['strategy_id']}|{row['split']}|{endpoint}"]
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
            comparator_model_index = MODEL_IDS.index(comparator)
            for endpoint_index, (endpoint, _) in enumerate(ENDPOINTS):
                result = q87.q86.q84.bootstrap_paired(
                    hits[idx, selected_index, endpoint_index],
                    hits[idx, comparator_model_index, endpoint_index],
                    88000 + split_index * 10000 + comparator_index * 100 + endpoint_index,
                )
                test_id = f"Q88PAIRED|{split}|{comparator}|{endpoint}"
                paired_tests.append({"test_id": test_id, "p_raw": float(result["p_two_sided"])})
                paired_rows.append({
                    "test_id": test_id, "split": split, "comparator": comparator,
                    "endpoint": endpoint, **result, "positive_difference_favors_selected": True,
                })
            rank_result = q87.q86.q84.bootstrap_paired(
                actual_ranks[idx, comparator_model_index, :].mean(axis=1),
                actual_ranks[idx, selected_index, :].mean(axis=1),
                88000 + split_index * 10000 + comparator_index * 100 + 3,
            )
            test_id = f"Q88PAIRED|{split}|{comparator}|mean_actual_rank_improvement"
            paired_tests.append({"test_id": test_id, "p_raw": float(rank_result["p_two_sided"])})
            paired_rows.append({
                "test_id": test_id, "split": split, "comparator": comparator,
                "endpoint": "mean_actual_rank_improvement", **rank_result,
                "positive_difference_means_lower_selected_rank": True,
            })
    if len(paired_tests) != 96:
        raise ValueError("Q88 paired family must contain 96 tests")
    paired_adjusted = q87.q86.q84.holm_adjust(paired_tests)
    for row in paired_rows:
        row["p_holm"] = paired_adjusted[row["test_id"]]

    def metric_for(model, split):
        return next(row for row in metrics if row["strategy_id"] == model and row["split"] == split)

    def paired_for(split, comparator, endpoint):
        return next(row for row in paired_rows if row["split"] == split and row["comparator"] == comparator and row["endpoint"] == endpoint)

    blind_selected = metric_for(selected_id, "blind_oos")
    blind_equal = metric_for(q87.q86.BASE_EQUAL, "blind_oos")
    blind_primary = paired_for("blind_oos", q87.q86.BASE_EQUAL, "top20")
    validation_selected = metric_for(selected_id, "validation")
    validation_equal = metric_for(q87.q86.BASE_EQUAL, "validation")
    lift = blind_selected["mean_hits_top20"] - blind_equal["mean_hits_top20"]
    gate_pass = (
        blind_selected["mean_hits_top20"] >= 2.5
        and lift >= 0.10
        and blind_primary["ci95"][0] is not None
        and blind_primary["ci95"][0] > 0.0
        and blind_primary["p_holm"] < 0.05
        and blind_selected["p_values_holm"]["top20"] < 0.05
    )
    primary_gate = {
        "selected_strategy": selected_id,
        "blind_top20": blind_selected["mean_hits_top20"],
        "blind_top20_equal42": blind_equal["mean_hits_top20"],
        "blind_lift_vs_equal42": lift,
        "blind_paired_ci95": blind_primary["ci95"],
        "blind_paired_p_raw": blind_primary["p_two_sided"],
        "blind_paired_p_holm": blind_primary["p_holm"],
        "blind_exact_null_p_holm": blind_selected["p_values_holm"]["top20"],
        "validation_lift_vs_equal42": validation_selected["mean_hits_top20"] - validation_equal["mean_hits_top20"],
        "status": "PASS" if gate_pass else "NOT_MET",
    }

    transfer_diagnostics = []
    for split in SPLITS:
        idx = split_indices[split]
        for name, values in (("instantaneous_signed_projection", transfer_raw[idx]),
                             ("rolling_signed_projection", transfer_ewma[idx])):
            transfer_diagnostics.append({
                "split": split, "signal": name,
                "mean": float(values.mean()),
                "median": float(np.median(values)),
                "positive_fraction": float(np.mean(values > 0.0)),
                "near_zero_fraction": float(np.mean(np.abs(values) < 0.05)),
                "mean_absolute": float(np.mean(np.abs(values))),
            })

    temporal_blocks = []
    blind_idx = split_indices["blind_oos"]
    equal_model_index = MODEL_IDS.index(q87.q86.BASE_EQUAL)
    for start in range(0, len(blind_idx), 100):
        block = blind_idx[start:start + 100]
        if len(block) < 40:
            continue
        delta = float((hits[block, selected_index, 2] - hits[block, equal_model_index, 2]).mean())
        temporal_blocks.append({
            "first_target": dates[q87.q86.q84.MIN_HISTORY + int(block[0])],
            "last_target": dates[q87.q86.q84.MIN_HISTORY + int(block[-1])],
            "targets": int(len(block)),
            "top20_delta_vs_equal42": delta,
        })

    return {
        "draws": draws, "dates": dates, "split_labels": split_labels, "split_counts": split_counts,
        "split_indices": split_indices, "ranks": ranks, "hits": hits, "actual_ranks": actual_ranks,
        "transfer_raw": transfer_raw, "transfer_ewma": transfer_ewma,
        "metrics": metrics, "exact_tests": exact_tests,
        "paired_rows": paired_rows, "paired_tests": paired_tests,
        "selected_id": selected_id, "primary_gate": primary_gate,
        "transfer_diagnostics": transfer_diagnostics, "temporal_blocks": temporal_blocks,
    }


def catalog_entries():
    entries = q87.catalog_entries()
    entries.extend([
        {"strategy_id": DYNAMIC_IDS[0], "kind": "SIGNED_TRANSFER_CANDIDATE",
         "definition": "base_z + 0.20 * reversion_i * z(20-transition exponentially weighted signed cosine between node delta and graph-row delta projected onto prior neighbor features)."},
        {"strategy_id": DYNAMIC_IDS[1], "kind": "SIGNED_TRANSFER_CANDIDATE",
         "definition": "base_z + 0.20 * graph_signal_i * z(20-transition exponentially weighted signed cosine between node delta and graph-row delta projected onto prior neighbor features)."},
        {"strategy_id": DYNAMIC_IDS[2], "kind": "SIGNED_TRANSFER_CANDIDATE",
         "definition": "base_z + 0.20 * 0.5*(reversion_i+graph_signal_i) * z(20-transition exponentially weighted signed cosine between node delta and graph-row delta projected onto prior neighbor features)."},
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
                for offset, target_date in enumerate(result["dates"][q87.q86.q84.MIN_HISTORY:]):
                    target_index = q87.q86.q84.MIN_HISTORY + offset
                    row = {
                        "target_date": target_date,
                        "cutoff_date": result["dates"][target_index - 1],
                        "prior_draws": target_index,
                        "actual_quintet": " ".join(map(str, sorted(result["draws"][target_index]["nums"]))),
                        "split": result["split_labels"][offset],
                    }
                    for number in range(1, 41):
                        j = number - 1
                        row[f"transfer_cosine_{number:02d}"] = format(float(result["transfer_raw"][offset, j]), ".12g")
                        row[f"transfer_ewma_{number:02d}"] = format(float(result["transfer_ewma"][offset, j]), ".12g")
                    for model_index, model in enumerate(MODEL_IDS):
                        for number, rank in enumerate(result["ranks"][offset, model_index], 1):
                            row[f"rank_{slug(model)}_{number:02d}"] = int(rank)
                    writer.writerow(row)

    report = {
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "task_id": "Q88-SIGNED-NODE-GRAPH-TRANSFER-01",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive": {
            "draw_count": len(result["draws"]),
            "first_date": result["dates"][0],
            "last_date": result["dates"][-1],
            "git_blob_sha1": archive_sha1,
            "sha256": archive_sha256,
        },
        "source_code_commit": os.environ.get("SONAR_SOURCE_SHA", "LOCAL_UNPINNED"),
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "models": list(MODEL_IDS),
        "signed_transfer_candidates": list(DYNAMIC_IDS),
        "projection_definition": {
            "node_delta_shape": [40, 6],
            "edge_delta_shape": [40, 40],
            "prior_neighbor_features_shape": [40, 6],
            "projected_graph_change": "(edge_delta @ prior_neighbor_features) / sqrt(39)",
            "signed_cosine": "rowwise dot(node_delta, projected_graph_change)/(norm(node_delta)*norm(projected_graph_change)); zero for zero norm",
            "smoothing_window": WINDOW,
            "smoothing_decay": DECAY,
            "alpha": ALPHA,
        },
        "selected_on_discovery_only": result["selected_id"],
        "selection_rule": "Discovery mean Top20 hits; tie lower mean actual rank then stable ID.",
        "metrics": result["metrics"],
        "multiple_testing": {
            "exact_null_method": "global Holm-Bonferroni; discrete upper-tail convolution of iid Hypergeometric(40,k,5)",
            "exact_null_family_size": len(result["exact_tests"]),
            "paired_method": "global Holm-Bonferroni across moving-block bootstrap comparisons",
            "paired_family_size": len(result["paired_tests"]),
            "bootstrap_block_length": 20,
            "bootstrap_replicates": 2000,
        },
        "paired_block_bootstrap": result["paired_rows"],
        "primary_gate": result["primary_gate"],
        "transfer_diagnostics": result["transfer_diagnostics"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "limitations": [
            "The historical Blind OOS has prior exposure across SONAR research and is exploratory, not a virgin holdout.",
            "The graph is a smoothed co-occurrence descriptor; signed projection does not establish physical or causal coupling.",
            "The exact-null convolution assumes independent target draws; paired moving-block bootstrap is reported separately for serial dependence.",
            "Only three preregistered operators were tested; this is not an exhaustive formula universe.",
            "A positive historical result would still require a new prospective confirmation and human review."
        ],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }
    json_dump(REPORT, report)

    files = {}
    for name, path in (("catalog", CATALOG), ("target_ledger", LEDGER), ("report", REPORT)):
        files[name] = {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    manifest = {
        "task_id": "Q88-SIGNED-NODE-GRAPH-TRANSFER-01",
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_sha256": archive_sha256,
        "source_archive_git_blob_sha1": archive_sha1,
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "model_count": len(MODEL_IDS),
        "candidate_count": len(DYNAMIC_IDS),
        "rank_vectors": len(result["split_labels"]) * len(MODEL_IDS),
        "transfer_values": len(result["split_labels"]) * 40 * 2,
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "ledger_fields": fields,
        "files": files,
    }
    json_dump(MANIFEST, manifest)
    json_dump(CHECKPOINT, {
        "checkpoint_id": "SONAR-Q88-SIGNED-NODE-GRAPH-TRANSFER-2026-11-10",
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "source_archive_git_blob_sha1": archive_sha1,
        "source_archive_sha256": archive_sha256,
        "target_count": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"],
        "next_action": "Independent replay of all prior cutoffs, signed projection vectors, rank permutations, metric families and Holm adjustments; append-only persistence and exact-byte readback; human review required."
    })


def main():
    for path in (CATALOG, LEDGER, REPORT, MANIFEST, CHECKPOINT, VALIDATION):
        if path.exists():
            raise SystemExit("Q88_BLOCKED: append-only output already exists: " + str(path))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    archive_sha1 = q87.q86.q84.git_blob_sha1(ARCHIVE)
    if archive_sha1 != EXPECTED_SHA1 or archive_sha256 != EXPECTED_SHA256:
        raise SystemExit("Q88_BLOCKED: canonical archive identity mismatch")
    if protocol["source_archive"]["sha256"] != archive_sha256 or protocol["source_archive"]["git_blob_sha1"] != archive_sha1:
        raise SystemExit("Q88_BLOCKED: preregistration/archive identity mismatch")
    result = compute_experiment()
    write_outputs(result, archive_sha1, archive_sha256)
    print("SONAR_Q88_SUMMARY_BEGIN")
    print(json.dumps({
        "status": "COMPUTED_PENDING_ACCEPTANCE",
        "targets": len(result["split_labels"]),
        "split_counts": result["split_counts"],
        "models": len(MODEL_IDS),
        "rank_vectors": len(result["split_labels"]) * len(MODEL_IDS),
        "exact_null_holm_tests": len(result["exact_tests"]),
        "paired_holm_tests": len(result["paired_tests"]),
        "selected_on_discovery_only": result["selected_id"],
        "primary_gate": result["primary_gate"],
    }, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q88_SUMMARY_END")


if __name__ == "__main__":
    main()
