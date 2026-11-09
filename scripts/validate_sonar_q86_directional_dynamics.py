#!/usr/bin/env python3
"""Independent Q86-DIR replay validator; PASS validates computation, not predictive efficacy."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

import sonar_q86_directional_dynamics as q86dir
from sonar_sequence_agent import MIN_HISTORY, read_draws

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"


def validate(read_only=False):
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    draws = read_draws()
    dates = [item["date"].isoformat() for item in draws]
    if archive_sha256 != q86dir.EXPECTED_SHA256 or q86dir.q84.git_blob_sha1(ARCHIVE) != q86dir.EXPECTED_SHA1:
        raise ValueError("Q86-DIR validation blocked: canonical archive identity mismatch")

    paths = {
        "catalog": q86dir.CATALOG, "target_ledger": q86dir.LEDGER, "report": q86dir.REPORT,
        "manifest": q86dir.MANIFEST, "checkpoint": q86dir.CHECKPOINT,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Q86-DIR validation blocked: missing " + str(path))
    manifest = json.loads(q86dir.MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(q86dir.REPORT.read_text(encoding="utf-8"))
    if manifest.get("source_archive_sha256") != archive_sha256 or manifest.get("source_archive_git_blob_sha1") != q86dir.EXPECTED_SHA1:
        raise ValueError("Q86-DIR validation blocked: manifest archive identity mismatch")
    for key in ("catalog", "target_ledger", "report"):
        path = paths[key]
        identity = manifest["files"][key]
        if identity.get("sha256") != q86dir.sha256_file(path) or identity.get("bytes") != path.stat().st_size:
            raise ValueError("Q86-DIR validation blocked: byte/hash mismatch for " + key)

    catalog = [json.loads(line) for line in q86dir.CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [item["strategy_id"] for item in catalog] != list(q86dir.MODEL_IDS):
        raise ValueError("Q86-DIR validation blocked: catalog coverage/order mismatch")
    if manifest.get("model_count") != 8 or manifest.get("adaptive_candidate_count") != 4:
        raise ValueError("Q86-DIR validation blocked: model family dimensions mismatch")
    if manifest.get("exact_null_holm_tests") != 72 or manifest.get("paired_holm_tests") != 32:
        raise ValueError("Q86-DIR validation blocked: multiple-testing family dimensions mismatch")

    replay = q86dir.compute_experiment(draws)
    if replay["split_counts"] != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise ValueError("Q86-DIR validation blocked: replay split mismatch")
    if replay["selected_id"] != report.get("selected_on_discovery_only"):
        raise ValueError("Q86-DIR validation blocked: Discovery selection does not replay")
    if len(report.get("metrics", [])) != 24 or len(report.get("paired_block_bootstrap", [])) != 32:
        raise ValueError("Q86-DIR validation blocked: report metric dimensions mismatch")
    if report.get("multiple_testing", {}).get("exact_null_family_size") != 72:
        raise ValueError("Q86-DIR validation blocked: exact-null family mismatch")
    if report.get("multiple_testing", {}).get("paired_family_size") != 32:
        raise ValueError("Q86-DIR validation blocked: paired family mismatch")
    if report.get("primary_gate") != replay["primary_gate"]:
        raise ValueError("Q86-DIR validation blocked: primary gate does not replay")

    expected_rows = len(draws) - MIN_HISTORY
    expected_fields = q86dir.ledger_fields()
    with gzip.open(q86dir.LEDGER, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q86-DIR validation blocked: target ledger schema mismatch")
        ledger_rows = list(reader)
    if len(ledger_rows) != expected_rows or expected_rows != q86dir.EXPECTED_TARGETS:
        raise ValueError("Q86-DIR validation blocked: target ledger row count mismatch")

    for offset, row in enumerate(ledger_rows):
        target_index = MIN_HISTORY + offset
        if row["target_date"] != dates[target_index] or row["cutoff_date"] != dates[target_index - 1]:
            raise ValueError("Q86-DIR validation blocked: target/cutoff mismatch at row " + str(offset))
        if int(row["prior_draws"]) != target_index or row["split"] != replay["split_labels"][offset]:
            raise ValueError("Q86-DIR validation blocked: prior count/split mismatch at row " + str(offset))
        expected_actual = " ".join(map(str, sorted(draws[target_index]["nums"])))
        if row["actual_quintet"] != expected_actual:
            raise ValueError("Q86-DIR validation blocked: actual quintet mismatch at row " + str(offset))
        for model_index, model in enumerate(q86dir.MODEL_IDS):
            vector = [int(row[f"rank_{q86dir.slug(model)}_{number:02d}"]) for number in range(1, 41)]
            if sorted(vector) != list(range(1, 41)):
                raise ValueError("Q86-DIR validation blocked: rank is not a permutation at row " + str(offset))
            if not np.array_equal(np.asarray(vector, dtype=np.int8), replay["ranks"][offset, model_index]):
                raise ValueError("Q86-DIR validation blocked: rank replay mismatch at row " + str(offset))
        if row["field_state_sha256"] != replay["signatures"][offset]:
            raise ValueError("Q86-DIR validation blocked: field-state hash mismatch at row " + str(offset))
        node_values = np.asarray([float(row[f"node_alignment_{number:02d}"]) for number in range(1, 41)])
        graph_values = np.asarray([float(row[f"graph_alignment_{number:02d}"]) for number in range(1, 41)])
        coherence_values = np.asarray([float(row[f"node_graph_coherence_{number:02d}"]) for number in range(1, 41)])
        if not np.isfinite(node_values).all() or not np.isfinite(graph_values).all() or not np.isfinite(coherence_values).all():
            raise ValueError("Q86-DIR validation blocked: non-finite directional vector at row " + str(offset))
        if np.any(np.abs(node_values) > 1.0 + 1e-10) or np.any(np.abs(graph_values) > 1.0 + 1e-10):
            raise ValueError("Q86-DIR validation blocked: cosine outside [-1,1] at row " + str(offset))
        if not np.allclose(coherence_values, node_values * graph_values, rtol=0.0, atol=1e-9):
            raise ValueError("Q86-DIR validation blocked: node-graph coherence product mismatch at row " + str(offset))
        if not np.allclose(node_values, replay["transition"]["node_alignment"][offset], rtol=0.0, atol=1e-9):
            raise ValueError("Q86-DIR validation blocked: node directional replay mismatch at row " + str(offset))
        if not np.allclose(graph_values, replay["transition"]["graph_alignment"][offset], rtol=0.0, atol=1e-9):
            raise ValueError("Q86-DIR validation blocked: graph directional replay mismatch at row " + str(offset))
        if row["directional_state_sha256"] != replay["directional_signatures"][offset]:
            raise ValueError("Q86-DIR validation blocked: directional hash mismatch at row " + str(offset))
        expected_means = {
            "node_alignment_mean": float(node_values.mean()),
            "graph_alignment_mean": float(graph_values.mean()),
            "node_graph_coherence_mean": float(coherence_values.mean()),
        }
        for column, expected_value in expected_means.items():
            if abs(float(row[column]) - expected_value) > 1e-9:
                raise ValueError("Q86-DIR validation blocked: directional mean mismatch at row " + str(offset))

    validation = {
        "task_id": "Q86-DIR-01",
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_sha256": archive_sha256,
            "canonical_draws": len(draws),
            "targets": expected_rows,
            "strict_prior_cutoffs": expected_rows,
            "models": len(q86dir.MODEL_IDS),
            "adaptive_candidates": len(q86dir.DYNAMIC_IDS),
            "rank_vectors_replayed": expected_rows * len(q86dir.MODEL_IDS),
            "exact_null_holm_tests": 72,
            "paired_holm_tests": 32,
            "directional_vectors_replayed": expected_rows * 120,
            "discovery_selection_replayed": replay["selected_id"],
            "persisted_catalog_sha256": q86dir.sha256_file(q86dir.CATALOG),
            "persisted_ledger_sha256": q86dir.sha256_file(q86dir.LEDGER),
            "persisted_report_sha256": q86dir.sha256_file(q86dir.REPORT),
        },
        "primary_gate": replay["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }
    validation_path = q86dir.VALIDATION
    if read_only:
        if not validation_path.is_file():
            raise ValueError("Q86-DIR read-only validation blocked: persisted validation file missing")
        existing = json.loads(validation_path.read_text(encoding="utf-8"))
        if existing != validation:
            raise ValueError("Q86-DIR read-only validation blocked: persisted validation differs from replay")
    else:
        if validation_path.exists():
            raise ValueError("Q86-DIR validation blocked: append-only validation file already exists")
        q86dir.json_dump(validation_path, validation)
    print("SONAR_Q86-DIR_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q86-DIR_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
