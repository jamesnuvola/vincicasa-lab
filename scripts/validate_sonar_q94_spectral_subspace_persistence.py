#!/usr/bin/env python3
"""Independent fail-closed Q94 spectral-subspace persistence validator."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path

import numpy as np

import sonar_q94_spectral_subspace_persistence as q94

ROOT = Path(__file__).resolve().parents[1]


def close(a, b, tol=1e-10):
    return abs(float(a) - float(b)) <= tol


def compare_nested(left, right, path="root", tol=1e-10):
    if isinstance(left, dict) and isinstance(right, dict):
        if set(left) != set(right):
            raise ValueError(f"Q94 key mismatch at {path}")
        for key in left:
            compare_nested(left[key], right[key], path + "." + str(key), tol)
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            raise ValueError(f"Q94 list length mismatch at {path}")
        for index, (a, b) in enumerate(zip(left, right)):
            compare_nested(a, b, f"{path}[{index}]", tol)
    elif isinstance(left, (int, float)) and not isinstance(left, bool) and isinstance(right, (int, float)) and not isinstance(right, bool):
        if not close(left, right, tol):
            raise ValueError(f"Q94 numeric mismatch at {path}: {left} != {right}")
    elif left != right:
        raise ValueError(f"Q94 value mismatch at {path}: {left!r} != {right!r}")


def verify_manifest(manifest, include_validation):
    required = ("catalog", "target_ledger", "report", "protocol", "checkpoint")
    for key in required:
        meta = manifest.get("files", {}).get(key)
        if not meta:
            raise ValueError("Q94 manifest missing " + key)
        path = ROOT / meta["path"]
        data = path.read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("Q94 manifest byte/hash mismatch: " + key)
    if include_validation:
        meta = manifest.get("files", {}).get("validation")
        if not meta:
            raise ValueError("Q94 manifest missing validation")
        data = q94.VALIDATION.read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("Q94 validation byte/hash mismatch")


def validate(read_only=False):
    required = (q94.CATALOG, q94.LEDGER, q94.REPORT, q94.MANIFEST, q94.CHECKPOINT, q94.PROTOCOL)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise ValueError("Q94 missing required outputs: " + ", ".join(missing))

    protocol = json.loads(q94.PROTOCOL.read_text(encoding="utf-8"))
    manifest = json.loads(q94.MANIFEST.read_text(encoding="utf-8"))
    report = json.loads(q94.REPORT.read_text(encoding="utf-8"))
    if protocol.get("task_id") != q94.TASK_ID or protocol.get("status") != "PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q94 protocol identity/status mismatch")
    if manifest.get("task_id") != q94.TASK_ID:
        raise ValueError("Q94 manifest task identity mismatch")

    result = q94.compute_experiment()
    if manifest.get("source_archive_git_blob_sha1") != result["archive_sha1"]:
        raise ValueError("Q94 manifest archive SHA-1 mismatch")
    if manifest.get("source_q93_ledger_sha256") != result["q93_ledger_sha256"]:
        raise ValueError("Q94 manifest Q93 ledger SHA-256 mismatch")

    expected_report = {
        "metrics": result["metrics"],
        "exact_null_holm_tests": result["exact_tests"],
        "paired_block_bootstrap": result["paired"],
        "paired_holm_tests": result["paired_tests"],
        "circular_shift_randomization": result["circular_shift"],
        "circular_shift_holm_tests": result["circular_shift_tests"],
        "primary_gate": result["primary_gate"],
        "spectral_persistence_diagnostics": result["stability_summary"],
        "blind_temporal_blocks": result["temporal_blocks"],
        "target_counts": result["counts"],
        "source_q93_ledger_sha256": result["q93_ledger_sha256"],
    }
    for key, expected in expected_report.items():
        compare_nested(report.get(key), expected, "report." + key)

    if len(report.get("metrics", [])) != 15:
        raise ValueError("Q94 metric row count mismatch")
    if len(report.get("exact_null_holm_tests", [])) != 45:
        raise ValueError("Q94 exact-null Holm family size mismatch")
    if len(report.get("paired_holm_tests", [])) != 24:
        raise ValueError("Q94 paired Holm family size mismatch")
    if len(report.get("circular_shift_holm_tests", [])) != 9:
        raise ValueError("Q94 circular-shift Holm family size mismatch")

    expected_fields = q94.ledger_fields()
    with gzip.open(q94.LEDGER, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q94 ledger schema mismatch")
        rows = list(reader)
    if len(rows) != 3203 or len(result["ledger_rows"]) != 3203:
        raise ValueError("Q94 ledger target count mismatch")

    for index, (actual, expected) in enumerate(zip(rows, result["ledger_rows"])):
        if actual != expected:
            differing = [key for key in expected if actual.get(key) != expected[key]]
            raise ValueError(f"Q94 ledger replay mismatch at target {index}: {differing[:5]}")
        draw_index = q94.MIN_HISTORY + index
        if actual["cutoff_date"] >= actual["target_date"] or int(actual["prior_draws"]) != draw_index:
            raise ValueError("Q94 target leakage/cutoff violation at target " + str(index))
        if not 0.0 <= float(actual["subspace_stability"]) <= 1.0:
            raise ValueError("Q94 stability outside [0,1] at target " + str(index))

    validation = {
        "task_id": q94.TASK_ID,
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_git_blob_sha1": result["archive_sha1"],
            "archive_sha256": result["archive_sha256"],
            "q93_source_ledger_sha256": result["q93_ledger_sha256"],
            "targets": len(rows),
            "strict_prior_cutoffs": len(rows),
            "split_counts": result["counts"],
            "models": len(q94.MODELS),
            "subspace_stability_values_replayed": len(result["stability"]),
            "ranking_vectors_replayed": len(rows) * len(q94.MODELS),
            "exact_null_holm_tests": len(result["exact_tests"]),
            "paired_holm_tests": len(result["paired_tests"]),
            "circular_shift_holm_tests": len(result["circular_shift_tests"]),
            "target_ledger_sha256": q94.sha256_file(q94.LEDGER),
            "report_sha256": q94.sha256_file(q94.REPORT),
        },
        "primary_gate": result["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }

    if read_only:
        if manifest.get("status") != "ACCEPTANCE_PASS":
            raise ValueError("Q94 persisted manifest is not ACCEPTANCE_PASS")
        if report.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW":
            raise ValueError("Q94 persisted report status mismatch")
        if report.get("acceptance", {}).get("validator") != "Q94_FORMULA_ACCEPTANCE_PASS":
            raise ValueError("Q94 persisted report acceptance missing")
        verify_manifest(manifest, True)
        saved = json.loads(q94.VALIDATION.read_text(encoding="utf-8"))
        compare_nested(saved, validation, "saved_validation")
    else:
        if q94.VALIDATION.exists():
            raise ValueError("Q94 append-only validation already exists")
        report["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        report["acceptance"] = {
            "validator": "Q94_FORMULA_ACCEPTANCE_PASS",
            "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
            "source_sha": os.environ.get("GITHUB_SHA", ""),
            "human_review": "PENDING_HUMAN_REVIEW_INTEGRATION",
            "persisted_head_replay": "PENDING",
        }
        q94.dump(q94.REPORT, report)

        checkpoint = q94.CHECKPOINT.read_text(encoding="utf-8")
        checkpoint = checkpoint.replace(
            "State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE", "State: ACCEPTANCE_PASS"
        )
        checkpoint += (
            "\n## Independent acceptance\n\n"
            "- Validator status: PASS.\n"
            f"- Strict-prior cutoffs: {len(rows)}/{len(rows)}.\n"
            f"- Subspace stability values replayed: {len(result['stability'])}.\n"
            f"- Ranking vectors replayed: {len(rows) * len(q94.MODELS)}.\n"
            f"- Primary historical gate: {result['primary_gate']['status']}.\n"
        )
        q94.CHECKPOINT.write_text(checkpoint, encoding="utf-8")
        validation["checks"]["report_sha256"] = q94.sha256_file(q94.REPORT)
        q94.dump(q94.VALIDATION, validation)

        manifest["status"] = "ACCEPTANCE_PASS"
        for key, path in (
            ("report", q94.REPORT), ("checkpoint", q94.CHECKPOINT), ("validation", q94.VALIDATION)
        ):
            data = path.read_bytes()
            manifest["files"][key] = {
                "path": str(path.relative_to(ROOT)),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        q94.dump(q94.MANIFEST, manifest)
        verify_manifest(manifest, True)

    print("SONAR_Q94_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q94_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
