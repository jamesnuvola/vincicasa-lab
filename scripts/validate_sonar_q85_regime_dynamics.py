#!/usr/bin/env python3
"""Independent Q85 replay validator; PASS validates computation, not predictive efficacy."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np

import sonar_q85_regime_dynamics as q85
from sonar_sequence_agent import MIN_HISTORY, read_draws

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"


def validate(read_only=False):
    raw = ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    draws = read_draws()
    dates = [item["date"].isoformat() for item in draws]
    if archive_sha256 != q85.EXPECTED_SHA256 or q85.q84.git_blob_sha1(ARCHIVE) != q85.EXPECTED_SHA1:
        raise ValueError("Q85 validation blocked: canonical archive identity mismatch")

    paths = {
        "catalog": q85.CATALOG, "target_ledger": q85.LEDGER, "report": q85.REPORT,
        "manifest": q85.MANIFEST, "checkpoint": q85.CHECKPOINT,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Q85 validation blocked: missing " + str(path))
    manifest = json.loads(q85.MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(q85.REPORT.read_text(encoding="utf-8"))
    if manifest.get("source_archive_sha256") != archive_sha256 or manifest.get("source_archive_git_blob_sha1") != q85.EXPECTED_SHA1:
        raise ValueError("Q85 validation blocked: manifest archive identity mismatch")
    for key in ("catalog", "target_ledger", "report"):
        path = paths[key]
        identity = manifest["files"][key]
        if identity.get("sha256") != q85.sha256_file(path) or identity.get("bytes") != path.stat().st_size:
            raise ValueError("Q85 validation blocked: byte/hash mismatch for " + key)

    catalog = [json.loads(line) for line in q85.CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [item["strategy_id"] for item in catalog] != list(q85.MODEL_IDS):
        raise ValueError("Q85 validation blocked: catalog coverage/order mismatch")
    if manifest.get("model_count") != 8 or manifest.get("adaptive_candidate_count") != 4:
        raise ValueError("Q85 validation blocked: model family dimensions mismatch")
    if manifest.get("exact_null_holm_tests") != 72 or manifest.get("paired_holm_tests") != 32:
        raise ValueError("Q85 validation blocked: multiple-testing family dimensions mismatch")

    replay = q85.compute_experiment(draws)
    if replay["split_counts"] != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise ValueError("Q85 validation blocked: replay split mismatch")
    if replay["selected_id"] != report.get("selected_on_discovery_only"):
        raise ValueError("Q85 validation blocked: Discovery selection does not replay")
    if len(report.get("metrics", [])) != 24 or len(report.get("paired_block_bootstrap", [])) != 32:
        raise ValueError("Q85 validation blocked: report metric dimensions mismatch")
    if report.get("multiple_testing", {}).get("exact_null_family_size") != 72:
        raise ValueError("Q85 validation blocked: exact-null family mismatch")
    if report.get("multiple_testing", {}).get("paired_family_size") != 32:
        raise ValueError("Q85 validation blocked: paired family mismatch")
    if report.get("primary_gate") != replay["primary_gate"]:
        raise ValueError("Q85 validation blocked: primary gate does not replay")

    expected_rows = len(draws) - MIN_HISTORY
    expected_fields = q85.ledger_fields()
    with gzip.open(q85.LEDGER, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q85 validation blocked: target ledger schema mismatch")
        ledger_rows = list(reader)
    if len(ledger_rows) != expected_rows or expected_rows != q85.EXPECTED_TARGETS:
        raise ValueError("Q85 validation blocked: target ledger row count mismatch")

    for offset, row in enumerate(ledger_rows):
        target_index = MIN_HISTORY + offset
        if row["target_date"] != dates[target_index] or row["cutoff_date"] != dates[target_index - 1]:
            raise ValueError("Q85 validation blocked: target/cutoff mismatch at row " + str(offset))
        if int(row["prior_draws"]) != target_index or row["split"] != replay["split_labels"][offset]:
            raise ValueError("Q85 validation blocked: prior count/split mismatch at row " + str(offset))
        expected_actual = " ".join(map(str, sorted(draws[target_index]["nums"])))
        if row["actual_quintet"] != expected_actual:
            raise ValueError("Q85 validation blocked: actual quintet mismatch at row " + str(offset))
        for model_index, model in enumerate(q85.MODEL_IDS):
            vector = [int(row[f"rank_{q85.slug(model)}_{number:02d}"]) for number in range(1, 41)]
            if sorted(vector) != list(range(1, 41)):
                raise ValueError("Q85 validation blocked: rank is not a permutation at row " + str(offset))
            if not np.array_equal(np.asarray(vector, dtype=np.int8), replay["ranks"][offset, model_index]):
                raise ValueError("Q85 validation blocked: rank replay mismatch at row " + str(offset))
        for name in ("node_acceleration_percentile", "graph_acceleration_percentile"):
            value = float(row[name])
            if not 0.0 <= value <= 1.0:
                raise ValueError("Q85 validation blocked: invalid causal percentile at row " + str(offset))
        for name in ("alpha_rev_node_up", "alpha_rev_node_down", "alpha_graph_up", "alpha_graph_down"):
            value = float(row[name])
            if not 0.10 - 1e-12 <= value <= 0.30 + 1e-12:
                raise ValueError("Q85 validation blocked: adaptive alpha out of bounds at row " + str(offset))

    validation = {
        "task_id": "Q85-REGIME-TRANSITION-01",
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_sha256": archive_sha256,
            "canonical_draws": len(draws),
            "targets": expected_rows,
            "strict_prior_cutoffs": expected_rows,
            "models": len(q85.MODEL_IDS),
            "adaptive_candidates": len(q85.DYNAMIC_IDS),
            "rank_vectors_replayed": expected_rows * len(q85.MODEL_IDS),
            "exact_null_holm_tests": 72,
            "paired_holm_tests": 32,
            "discovery_selection_replayed": replay["selected_id"],
            "persisted_catalog_sha256": q85.sha256_file(q85.CATALOG),
            "persisted_ledger_sha256": q85.sha256_file(q85.LEDGER),
            "persisted_report_sha256": q85.sha256_file(q85.REPORT),
        },
        "primary_gate": replay["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }
    validation_path = q85.VALIDATION
    if read_only:
        if not validation_path.is_file():
            raise ValueError("Q85 read-only validation blocked: persisted validation file missing")
        existing = json.loads(validation_path.read_text(encoding="utf-8"))
        if existing != validation:
            raise ValueError("Q85 read-only validation blocked: persisted validation differs from replay")
    else:
        if validation_path.exists():
            raise ValueError("Q85 validation blocked: append-only validation file already exists")
        q85.json_dump(validation_path, validation)
    print("SONAR_Q85_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q85_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
