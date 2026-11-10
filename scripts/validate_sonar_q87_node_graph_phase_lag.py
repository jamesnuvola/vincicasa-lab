#!/usr/bin/env python3
"""Independent fail-closed Q87 replay validator; PASS certifies computation, not efficacy."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import sonar_q87_node_graph_phase_lag as q87
from sonar_sequence_agent import MIN_HISTORY, read_draws

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"


def _close(a, b, tolerance=1e-12):
    return abs(float(a) - float(b)) <= tolerance


def _compare_metrics(actual, expected):
    if len(actual) != len(expected):
        raise ValueError("Q87 metric row count mismatch")
    numeric = (
        "mean_hits_top5", "mean_hits_top10", "mean_hits_top20",
        "mean_rank_actual_numbers", "top20_5of5_rate",
    )
    for left, right in zip(actual, expected):
        for key in ("strategy_id", "split", "targets", "top20_4plus", "top20_5of5", "top20_hit_distribution"):
            if left.get(key) != right.get(key):
                raise ValueError("Q87 metric mismatch: " + key)
        for key in numeric:
            if not _close(left[key], right[key], 1e-12):
                raise ValueError("Q87 metric mismatch: " + key)
        for endpoint in ("top5", "top10", "top20"):
            if not _close(left["p_values_raw"][endpoint], right["p_values_raw"][endpoint], 1e-12):
                raise ValueError("Q87 raw p-value mismatch")
            if not _close(left["p_values_holm"][endpoint], right["p_values_holm"][endpoint], 1e-12):
                raise ValueError("Q87 Holm p-value mismatch")


def validate(read_only=False):
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    archive_sha1 = q87.q86.q84.git_blob_sha1(ARCHIVE)
    draws = read_draws()
    dates = [item["date"].isoformat() for item in draws]
    if archive_sha256 != q87.EXPECTED_SHA256 or archive_sha1 != q87.EXPECTED_SHA1:
        raise ValueError("Q87 archive identity mismatch")
    if len(draws) != q87.EXPECTED_DRAWS or dates[-1] != q87.EXPECTED_LAST:
        raise ValueError("Q87 archive dimensions mismatch")

    paths = {
        "catalog": q87.CATALOG,
        "target_ledger": q87.LEDGER,
        "report": q87.REPORT,
        "manifest": q87.MANIFEST,
        "checkpoint": q87.CHECKPOINT,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Q87 missing artifact: " + str(path))

    protocol = json.loads(q87.PROTOCOL.read_text(encoding="utf-8"))
    manifest = json.loads(q87.MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(q87.REPORT.read_text(encoding="utf-8"))
    if protocol["source_archive"]["sha256"] != archive_sha256 or protocol["source_archive"]["git_blob_sha1"] != archive_sha1:
        raise ValueError("Q87 protocol/archive identity mismatch")
    if manifest.get("source_archive_sha256") != archive_sha256 or manifest.get("source_archive_git_blob_sha1") != archive_sha1:
        raise ValueError("Q87 manifest/archive identity mismatch")
    for key, path in paths.items():
        if key == "manifest":
            continue
        identity = manifest["files"][key]
        if identity.get("sha256") != q87.sha256_file(path) or identity.get("bytes") != path.stat().st_size:
            raise ValueError("Q87 persisted byte/hash mismatch: " + key)

    catalog = [json.loads(line) for line in q87.CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [row["strategy_id"] for row in catalog] != list(q87.MODEL_IDS):
        raise ValueError("Q87 catalog coverage/order mismatch")
    if manifest.get("model_count") != 12 or manifest.get("phase_candidate_count") != 4:
        raise ValueError("Q87 model-family dimensions mismatch")
    if manifest.get("exact_null_holm_tests") != 108 or manifest.get("paired_holm_tests") != 32:
        raise ValueError("Q87 multiple-testing family dimensions mismatch")

    replay = q87.compute_experiment(draws)
    if replay["split_counts"] != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise ValueError("Q87 replay split mismatch")
    if replay["selected_id"] != report.get("selected_on_discovery_only"):
        raise ValueError("Q87 Discovery-only selection mismatch")
    if len(report.get("metrics", [])) != 36 or len(report.get("paired_block_bootstrap", [])) != 32:
        raise ValueError("Q87 report dimensions mismatch")
    if len(replay["exact_tests"]) != 108 or len(replay["paired_tests"]) != 32:
        raise ValueError("Q87 replay test-family dimensions mismatch")
    if report.get("multiple_testing", {}).get("exact_null_family_size") != 108:
        raise ValueError("Q87 exact-null Holm family mismatch")
    if report.get("multiple_testing", {}).get("paired_family_size") != 32:
        raise ValueError("Q87 paired Holm family mismatch")
    _compare_metrics(report["metrics"], replay["metrics"])
    if report.get("primary_gate") != replay["primary_gate"]:
        # JSON numeric values should be deterministic; provide a targeted fallback for float serialization.
        left, right = report.get("primary_gate", {}), replay["primary_gate"]
        for key in ("selected_strategy", "status"):
            if left.get(key) != right.get(key):
                raise ValueError("Q87 primary gate mismatch: " + key)
        for key in ("blind_top20", "blind_top20_equal42", "blind_lift_vs_equal42",
                    "blind_paired_p_raw", "blind_paired_p_holm", "blind_exact_null_p_holm",
                    "validation_lift_vs_equal42"):
            if not _close(left.get(key), right.get(key), 1e-12):
                raise ValueError("Q87 primary gate mismatch: " + key)
        if not np.allclose(left.get("blind_paired_ci95"), right["blind_paired_ci95"], atol=1e-12, rtol=0):
            raise ValueError("Q87 primary gate confidence interval mismatch")

    expected_fields = q87.ledger_fields()
    expected_rows = len(draws) - MIN_HISTORY
    with gzip.open(q87.LEDGER, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q87 target-ledger schema mismatch")
        ledger_rows = list(reader)
    if len(ledger_rows) != expected_rows or expected_rows != q87.EXPECTED_TARGETS:
        raise ValueError("Q87 target-ledger row count mismatch")

    phase_columns = {
        "node_leads_graph": "node_leads_graph",
        "graph_leads_node": "graph_leads_node",
        "phase_asymmetry": "phase_asymmetry",
        "bidirectional_phase_coherence": "bidirectional_phase_coherence",
    }
    rank_vectors = 0
    phase_values = 0
    for offset, row in enumerate(ledger_rows):
        target_index = MIN_HISTORY + offset
        if row["target_date"] != dates[target_index] or row["cutoff_date"] != dates[target_index - 1]:
            raise ValueError("Q87 target/cutoff mismatch at row " + str(offset))
        if int(row["prior_draws"]) != target_index or row["split"] != replay["split_labels"][offset]:
            raise ValueError("Q87 prior count/split mismatch at row " + str(offset))
        actual = " ".join(map(str, sorted(draws[target_index]["nums"])))
        if row["actual_quintet"] != actual:
            raise ValueError("Q87 target quintet mismatch at row " + str(offset))

        for model_index, model in enumerate(q87.MODEL_IDS):
            vector = np.asarray([int(row[f"rank_{q87.slug(model)}_{number:02d}"]) for number in range(1, 41)], dtype=np.int8)
            if sorted(vector.tolist()) != list(range(1, 41)):
                raise ValueError("Q87 rank vector is not a permutation at row " + str(offset))
            if not np.array_equal(vector, replay["ranks"][offset, model_index]):
                raise ValueError("Q87 rank replay mismatch at row " + str(offset) + " model " + model)
            rank_vectors += 1

        for phase_name, column_prefix in phase_columns.items():
            vector = np.asarray([float(row[f"{column_prefix}_{number:02d}"]) for number in range(1, 41)], dtype=np.float64)
            expected = replay["phase"][phase_name][offset]
            if not np.allclose(vector, expected, atol=1e-9, rtol=0):
                raise ValueError("Q87 phase-vector replay mismatch at row " + str(offset) + " signal " + phase_name)
            if not np.isfinite(vector).all():
                raise ValueError("Q87 non-finite phase vector")
            phase_values += len(vector)

        forward = np.asarray([float(row[f"node_leads_graph_{number:02d}"]) for number in range(1, 41)])
        backward = np.asarray([float(row[f"graph_leads_node_{number:02d}"]) for number in range(1, 41)])
        asymmetry = np.asarray([float(row[f"phase_asymmetry_{number:02d}"]) for number in range(1, 41)])
        coherence = np.asarray([float(row[f"bidirectional_phase_coherence_{number:02d}"]) for number in range(1, 41)])
        if np.any(np.abs(forward) > 1.0 + 1e-9) or np.any(np.abs(backward) > 1.0 + 1e-9):
            raise ValueError("Q87 forward/backward correlation outside [-1,1]")
        if np.any(np.abs(asymmetry) > 2.0 + 1e-9) or np.any(np.abs(coherence) > 1.0 + 1e-9):
            raise ValueError("Q87 derived phase signal outside theoretical bounds")
        if not np.allclose(asymmetry, forward - backward, atol=1e-9, rtol=0):
            raise ValueError("Q87 phase asymmetry identity mismatch")
        if not np.allclose(coherence, 0.5 * (forward + backward), atol=1e-9, rtol=0):
            raise ValueError("Q87 phase coherence identity mismatch")
        if offset == 0 and any(np.any(np.abs(replay["phase"][name][offset]) > 1e-12) for name in phase_columns):
            raise ValueError("Q87 first transition must be neutral")

    expected_rank_vectors = expected_rows * len(q87.MODEL_IDS)
    expected_phase_values = expected_rows * 40 * 4
    if rank_vectors != expected_rank_vectors or phase_values != expected_phase_values:
        raise ValueError("Q87 replayed vector dimensions mismatch")
    validation = {
        "task_id": "Q87-NODE-GRAPH-PHASE-LAG-01",
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_sha256": archive_sha256,
            "canonical_draws": len(draws),
            "targets": expected_rows,
            "strict_prior_cutoffs": expected_rows,
            "models": len(q87.MODEL_IDS),
            "phase_candidates": len(q87.DYNAMIC_IDS),
            "rank_vectors_replayed": rank_vectors,
            "phase_values_replayed": phase_values,
            "exact_null_holm_tests": 108,
            "paired_holm_tests": 32,
            "discovery_selection_replayed": replay["selected_id"],
            "persisted_catalog_sha256": q87.sha256_file(q87.CATALOG),
            "persisted_ledger_sha256": q87.sha256_file(q87.LEDGER),
            "persisted_report_sha256": q87.sha256_file(q87.REPORT),
        },
        "primary_gate": replay["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }
    if read_only:
        if not q87.VALIDATION.is_file():
            raise ValueError("Q87 read-only validation file missing")
        existing = json.loads(q87.VALIDATION.read_text(encoding="utf-8"))
        if existing != validation:
            raise ValueError("Q87 read-only validation differs from full replay")
    else:
        if q87.VALIDATION.exists():
            raise ValueError("Q87 append-only validation already exists")
        q87.json_dump(q87.VALIDATION, validation)

    print("SONAR_Q87_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q87_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
