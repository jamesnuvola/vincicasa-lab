#!/usr/bin/env python3
"""Independent fail-closed Q88 replay validator; PASS certifies computation, not efficacy."""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import json

import numpy as np
import sonar_q88_signed_node_graph_transfer as q88
from sonar_sequence_agent import MIN_HISTORY, read_draws


def close(a, b, tolerance=1e-12):
    return abs(float(a) - float(b)) <= tolerance


def compare_metrics(actual, expected):
    if len(actual) != len(expected):
        raise ValueError("Q88 metric row count mismatch")
    exact = ("strategy_id", "split", "targets", "top20_4plus", "top20_5of5", "top20_hit_distribution")
    numeric = ("mean_hits_top5", "mean_hits_top10", "mean_hits_top20", "mean_rank_actual_numbers", "top20_5of5_rate")
    for left, right in zip(actual, expected):
        for key in exact:
            if left.get(key) != right.get(key):
                raise ValueError("Q88 metric mismatch: " + key)
        for key in numeric:
            if not close(left[key], right[key], 1e-12):
                raise ValueError("Q88 metric mismatch: " + key)
        for endpoint in ("top5", "top10", "top20"):
            if not close(left["p_values_raw"][endpoint], right["p_values_raw"][endpoint], 1e-12):
                raise ValueError("Q88 raw p-value mismatch")
            if not close(left["p_values_holm"][endpoint], right["p_values_holm"][endpoint], 1e-12):
                raise ValueError("Q88 Holm p-value mismatch")


def compare_paired(actual, expected):
    if len(actual) != len(expected):
        raise ValueError("Q88 paired row count mismatch")
    for left, right in zip(actual, expected):
        for key in ("test_id", "split", "comparator", "endpoint", "n", "p_holm"):
            if left.get(key) != right.get(key):
                raise ValueError("Q88 paired result mismatch: " + key)
        for key in ("mean_difference", "p_two_sided"):
            if not close(left[key], right[key], 1e-12):
                raise ValueError("Q88 paired numeric mismatch: " + key)
        if not np.allclose(left["ci95"], right["ci95"], atol=1e-12, rtol=0):
            raise ValueError("Q88 paired confidence interval mismatch")


def validate(read_only=False):
    raw = q88.ARCHIVE.read_bytes()
    archive_sha256 = hashlib.sha256(raw).hexdigest()
    archive_sha1 = q88.q87.q86.q84.git_blob_sha1(q88.ARCHIVE)
    draws = read_draws()
    dates = [item["date"].isoformat() for item in draws]
    if archive_sha256 != q88.EXPECTED_SHA256 or archive_sha1 != q88.EXPECTED_SHA1:
        raise ValueError("Q88 archive identity mismatch")
    if len(draws) != q88.EXPECTED_DRAWS or dates[-1] != q88.EXPECTED_LAST:
        raise ValueError("Q88 archive dimensions mismatch")

    paths = {
        "catalog": q88.CATALOG,
        "target_ledger": q88.LEDGER,
        "report": q88.REPORT,
        "manifest": q88.MANIFEST,
        "checkpoint": q88.CHECKPOINT,
    }
    for name, path in paths.items():
        if not path.is_file():
            raise ValueError("Q88 missing artifact: " + str(path))

    protocol = json.loads(q88.PROTOCOL.read_text(encoding="utf-8"))
    manifest = json.loads(q88.MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(q88.REPORT.read_text(encoding="utf-8"))
    if protocol["source_archive"]["sha256"] != archive_sha256 or protocol["source_archive"]["git_blob_sha1"] != archive_sha1:
        raise ValueError("Q88 protocol/archive identity mismatch")
    if manifest.get("source_archive_sha256") != archive_sha256 or manifest.get("source_archive_git_blob_sha1") != archive_sha1:
        raise ValueError("Q88 manifest/archive identity mismatch")
    for key in ("catalog", "target_ledger", "report"):
        identity = manifest["files"][key]
        path = paths[key]
        if identity.get("sha256") != q88.sha256_file(path) or identity.get("bytes") != path.stat().st_size:
            raise ValueError("Q88 persisted byte/hash mismatch: " + key)

    catalog = [json.loads(line) for line in q88.CATALOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [row["strategy_id"] for row in catalog] != list(q88.MODEL_IDS):
        raise ValueError("Q88 catalog coverage/order mismatch")
    if manifest.get("model_count") != 15 or manifest.get("candidate_count") != 3:
        raise ValueError("Q88 model-family dimensions mismatch")
    if manifest.get("exact_null_holm_tests") != 135 or manifest.get("paired_holm_tests") != 96:
        raise ValueError("Q88 multiple-testing dimensions mismatch")

    replay = q88.compute_experiment(draws)
    if replay["split_counts"] != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise ValueError("Q88 replay split mismatch")
    if replay["selected_id"] != report.get("selected_on_discovery_only"):
        raise ValueError("Q88 Discovery-only selection mismatch")
    if len(report.get("metrics", [])) != 45 or len(report.get("paired_block_bootstrap", [])) != 96:
        raise ValueError("Q88 report dimensions mismatch")
    if len(replay["exact_tests"]) != 135 or len(replay["paired_tests"]) != 96:
        raise ValueError("Q88 replay test-family dimensions mismatch")
    if report.get("multiple_testing", {}).get("exact_null_family_size") != 135:
        raise ValueError("Q88 exact-null Holm family mismatch")
    if report.get("multiple_testing", {}).get("paired_family_size") != 96:
        raise ValueError("Q88 paired Holm family mismatch")
    compare_metrics(report["metrics"], replay["metrics"])
    compare_paired(report["paired_block_bootstrap"], replay["paired_rows"])
    if json.loads(json.dumps(report.get("primary_gate"))) != json.loads(json.dumps(replay["primary_gate"])):
        raise ValueError("Q88 primary gate mismatch")

    expected_fields = q88.ledger_fields()
    expected_rows = len(draws) - MIN_HISTORY
    with gzip.open(q88.LEDGER, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q88 target-ledger schema mismatch")
        ledger_rows = list(reader)
    if len(ledger_rows) != expected_rows or expected_rows != q88.EXPECTED_TARGETS:
        raise ValueError("Q88 target-ledger row count mismatch")

    rank_vectors = 0
    transfer_values = 0
    for offset, row in enumerate(ledger_rows):
        target_index = MIN_HISTORY + offset
        if row["target_date"] != dates[target_index] or row["cutoff_date"] != dates[target_index - 1]:
            raise ValueError("Q88 target/cutoff mismatch at row " + str(offset))
        if int(row["prior_draws"]) != target_index or row["split"] != replay["split_labels"][offset]:
            raise ValueError("Q88 prior count/split mismatch at row " + str(offset))
        actual = " ".join(map(str, sorted(draws[target_index]["nums"])))
        if row["actual_quintet"] != actual:
            raise ValueError("Q88 target quintet mismatch at row " + str(offset))

        for name, expected in (("transfer_cosine", replay["transfer_raw"][offset]),
                               ("transfer_ewma", replay["transfer_ewma"][offset])):
            vector = np.asarray([float(row[f"{name}_{number:02d}"]) for number in range(1, 41)], dtype=np.float64)
            if not np.isfinite(vector).all() or not np.allclose(vector, expected, atol=1e-9, rtol=0):
                raise ValueError("Q88 transfer-vector replay mismatch at row " + str(offset) + " signal " + name)
            transfer_values += len(vector)

        for model_index, model in enumerate(q88.MODEL_IDS):
            vector = np.asarray([int(row[f"rank_{q88.slug(model)}_{number:02d}"]) for number in range(1, 41)], dtype=np.int8)
            if sorted(vector.tolist()) != list(range(1, 41)):
                raise ValueError("Q88 rank vector is not a permutation at row " + str(offset))
            if not np.array_equal(vector, replay["ranks"][offset, model_index]):
                raise ValueError("Q88 rank replay mismatch at row " + str(offset) + " model " + model)
            rank_vectors += 1

    if rank_vectors != expected_rows * len(q88.MODEL_IDS):
        raise ValueError("Q88 rank-vector count mismatch")
    if transfer_values != expected_rows * 80:
        raise ValueError("Q88 transfer-value count mismatch")

    validation = {
        "task_id": "Q88-SIGNED-NODE-GRAPH-TRANSFER-01",
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_sha256": archive_sha256,
            "canonical_draws": len(draws),
            "targets": expected_rows,
            "strict_prior_cutoffs": expected_rows,
            "models": len(q88.MODEL_IDS),
            "candidates": len(q88.DYNAMIC_IDS),
            "rank_vectors_replayed": rank_vectors,
            "transfer_values_replayed": transfer_values,
            "exact_null_holm_tests": 135,
            "paired_holm_tests": 96,
            "discovery_selection_replayed": replay["selected_id"],
            "catalog_sha256": q88.sha256_file(q88.CATALOG),
            "target_ledger_sha256": q88.sha256_file(q88.LEDGER),
            "report_sha256": q88.sha256_file(q88.REPORT),
        },
        "primary_gate": replay["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }
    if read_only:
        if not q88.VALIDATION.is_file():
            raise ValueError("Q88 read-only validation file missing")
        existing = json.loads(q88.VALIDATION.read_text(encoding="utf-8"))
        if existing != validation:
            raise ValueError("Q88 read-only validation differs from full replay")
    else:
        if q88.VALIDATION.exists():
            raise ValueError("Q88 append-only validation already exists")
        q88.json_dump(q88.VALIDATION, validation)

    print("SONAR_Q88_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q88_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
