#!/usr/bin/env python3
"""Independent fail-closed Q93 spectral walk-forward acceptance and replay validator."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path

import numpy as np

import sonar_q87_node_graph_phase_lag as q87
import sonar_q93_spectral_coherence as q93

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = q93.REPORT
MANIFEST_PATH = q93.MANIFEST
LEDGER_PATH = q93.LEDGER
CATALOG_PATH = q93.CATALOG
PROTOCOL_PATH = q93.PROTOCOL
CHECKPOINT_PATH = q93.CHECKPOINT


def close(a, b, tol=1e-10):
    return abs(float(a) - float(b)) <= tol


def compare_nested(a, b, path="root", tol=1e-10):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            raise ValueError(f"Q93 key mismatch at {path}")
        for key in a:
            compare_nested(a[key], b[key], path + "." + str(key), tol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise ValueError(f"Q93 list length mismatch at {path}")
        for index, (left, right) in enumerate(zip(a, b)):
            compare_nested(left, right, f"{path}[{index}]", tol)
    elif isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        if not close(a, b, tol):
            raise ValueError(f"Q93 numeric mismatch at {path}: {a} != {b}")
    elif a != b:
        raise ValueError(f"Q93 value mismatch at {path}: {a!r} != {b!r}")


def verify_manifest(manifest, include_validation):
    required = ("catalog", "target_ledger", "report", "protocol", "checkpoint")
    for key in required:
        meta = manifest.get("files", {}).get(key)
        if not meta:
            raise ValueError("Q93 manifest missing " + key)
        path = ROOT / meta["path"]
        data = path.read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("Q93 manifest byte/hash mismatch: " + key)
    if include_validation:
        meta = manifest.get("files", {}).get("validation")
        if not meta:
            raise ValueError("Q93 manifest missing validation")
        data = q93.VALIDATION.read_bytes()
        if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError("Q93 validation byte/hash mismatch")


def validate(read_only=False):
    errors = []
    required = (REPORT_PATH, MANIFEST_PATH, LEDGER_PATH, CATALOG_PATH, PROTOCOL_PATH, CHECKPOINT_PATH)
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise ValueError("Q93 missing required outputs: " + ", ".join(missing))

    dates, draws = q87.read_draws()
    # q87.read_draws returns a list of draw records; keep the canonical archive pinned by Q93.
    if not isinstance(draws, list):
        raise ValueError("Q93 archive reader returned an unexpected shape")

    archive_sha1 = q93.q90.q84.git_blob_sha1(q93.ARCHIVE)
    archive_sha256 = q93.sha256_file(q93.ARCHIVE)
    date_values = [item["date"].isoformat() for item in draws]
    if archive_sha1 != q93.EXPECTED_SHA1 or archive_sha256 != q93.EXPECTED_SHA256:
        raise ValueError("Q93 archive byte identity mismatch")
    if len(draws) != q93.EXPECTED_DRAWS or date_values[0] != q93.EXPECTED_FIRST or date_values[-1] != q93.EXPECTED_LAST:
        raise ValueError("Q93 archive count/date mismatch")

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    if protocol.get("task_id") != q93.TASK_ID or protocol.get("status") != "PREREGISTERED_PENDING_EXECUTION":
        raise ValueError("Q93 protocol identity/status mismatch")
    if protocol.get("source_archive", {}).get("git_blob_sha1") != archive_sha1:
        raise ValueError("Q93 protocol archive mismatch")
    if manifest.get("task_id") != q93.TASK_ID or manifest.get("source_archive_git_blob_sha1") != archive_sha1:
        raise ValueError("Q93 manifest identity/archive mismatch")

    catalog = [json.loads(line) for line in CATALOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if [row.get("strategy_id") for row in catalog] != list(q93.MODEL_IDS):
        raise ValueError("Q93 catalog model order mismatch")

    result = q93.compute_experiment(draws)
    expected_report = {
        "metrics": result["metrics"],
        "exact_null_holm_tests": result["exact_tests"],
        "paired_block_bootstrap": result["paired"],
        "paired_holm_tests": result["paired_tests"],
        "spectral_randomization": result["randomization"],
        "spectral_randomization_holm_tests": result["randomization_tests"],
        "primary_gate": result["primary_gate"],
        "spectral_diagnostics": result["spectral_summary"],
        "blind_temporal_blocks": result["temporal_blocks"],
    }
    for key, expected in expected_report.items():
        compare_nested(report.get(key), expected, "report." + key)
    if len(report.get("metrics", [])) != 24:
        raise ValueError("Q93 metric row count mismatch")
    if len(report.get("exact_null_holm_tests", [])) != 72:
        raise ValueError("Q93 exact-null Holm family size mismatch")
    if len(report.get("paired_holm_tests", [])) != 48:
        raise ValueError("Q93 paired Holm family size mismatch")
    if len(report.get("spectral_randomization_holm_tests", [])) != 9:
        raise ValueError("Q93 spectral randomization family size mismatch")

    expected_fields = q93.ledger_fields()
    total = len(result["labels"])
    rank_count = signal_count = permutation_count = 0
    with gzip.open(LEDGER_PATH, "rt", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != expected_fields:
            raise ValueError("Q93 ledger schema mismatch")
        rows = list(reader)
    if len(rows) != total or total != 3203:
        raise ValueError("Q93 ledger row count mismatch")

    for target_index, row in enumerate(rows):
        draw_index = q93.MIN_HISTORY + target_index
        actual = sorted(int(x) for x in draws[draw_index]["nums"])
        if row["target_date"] != date_values[draw_index]:
            raise ValueError("Q93 target date mismatch at row " + str(target_index))
        if row["cutoff_date"] != date_values[draw_index - 1] or int(row["prior_draws"]) != draw_index:
            raise ValueError("Q93 strict-prior cutoff mismatch at row " + str(target_index))
        if row["actual_quintet"] != " ".join(map(str, actual)):
            raise ValueError("Q93 actual quintet mismatch at row " + str(target_index))
        if row["split"] != result["labels"][target_index]:
            raise ValueError("Q93 split mismatch at row " + str(target_index))

        for k_index, k in enumerate(q93.K_VALUES):
            if not close(float(row[f"spectral_energy_fraction_k{k}"]), result["spectral_energy"][target_index, k_index]):
                raise ValueError("Q93 spectral energy replay mismatch at row " + str(target_index))
            if int(row[f"spectral_effective_modes_k{k}"]) != int(result["spectral_modes_count"][target_index, k_index]):
                raise ValueError("Q93 effective mode count mismatch at row " + str(target_index))
            for number in range(40):
                raw = float(row[f"spectral_raw_k{k}_{number + 1:02d}"])
                smooth = float(row[f"spectral_ewma_k{k}_{number + 1:02d}"])
                if not close(raw, result["spectral_raw"][target_index, k_index, number]):
                    raise ValueError("Q93 raw spectral signal mismatch at row " + str(target_index))
                if not close(smooth, result["spectral_ewma"][target_index, k_index, number]):
                    raise ValueError("Q93 smoothed spectral signal mismatch at row " + str(target_index))
                signal_count += 2

        for model_index, model in enumerate(q93.MODEL_IDS):
            vector = np.asarray([int(row[f"rank_{q93.slug(model)}_{number:02d}"]) for number in range(1, 41)], dtype=np.int8)
            if sorted(vector.tolist()) != list(range(1, 41)) or not np.array_equal(vector, result["ranks"][target_index, model_index]):
                raise ValueError("Q93 ranking replay mismatch for " + model + " at row " + str(target_index))
            rank_count += 1

        for p in range(q93.PERMUTATION_COUNT):
            observed = (
                int(row[f"perm_{p:02d}_top5_hits"]),
                int(row[f"perm_{p:02d}_top10_hits"]),
                int(row[f"perm_{p:02d}_top20_hits"]),
            )
            expected = tuple(int(x) for x in result["permutation_hits"][target_index, p])
            if observed != expected:
                raise ValueError("Q93 permutation hit replay mismatch at row " + str(target_index) + " permutation " + str(p))
            rank_mean = float(row[f"perm_{p:02d}_mean_actual_rank"])
            if not close(rank_mean, result["permutation_mean_rank"][target_index, p]):
                raise ValueError("Q93 permutation rank replay mismatch at row " + str(target_index) + " permutation " + str(p))
            permutation_count += 4

    if rank_count != total * len(q93.MODEL_IDS):
        raise ValueError("Q93 rank replay count mismatch")
    if signal_count != total * len(q93.K_VALUES) * 2 * 40:
        raise ValueError("Q93 spectral signal replay count mismatch")
    if permutation_count != total * q93.PERMUTATION_COUNT * 4:
        raise ValueError("Q93 permutation replay count mismatch")

    validation = {
        "task_id": q93.TASK_ID,
        "status": "PASS",
        "scope": "HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
        "checks": {
            "archive_git_blob_sha1": archive_sha1,
            "archive_sha256": archive_sha256,
            "canonical_draws": len(draws),
            "targets": total,
            "strict_prior_cutoffs": total,
            "split_counts": result["counts"],
            "models": len(q93.MODEL_IDS),
            "permutations": q93.PERMUTATION_COUNT,
            "rank_vectors_replayed": rank_count,
            "spectral_signal_values_replayed": signal_count,
            "permutation_summary_values_replayed": permutation_count,
            "exact_null_holm_tests": len(result["exact_tests"]),
            "paired_holm_tests": len(result["paired_tests"]),
            "spectral_randomization_holm_tests": len(result["randomization_tests"]),
            "target_ledger_sha256": q93.sha256_file(LEDGER_PATH),
            "report_sha256": q93.sha256_file(REPORT_PATH),
        },
        "primary_gate": result["primary_gate"],
        "engine_promotion_allowed": False,
        "human_review_required": True,
        "immutable_freezes_modified": False,
    }

    if read_only:
        if manifest.get("status") != "ACCEPTANCE_PASS":
            raise ValueError("Q93 persisted manifest is not ACCEPTANCE_PASS")
        if report.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW":
            raise ValueError("Q93 persisted report status mismatch")
        if report.get("acceptance", {}).get("validator") != "Q93_FORMULA_ACCEPTANCE_PASS":
            raise ValueError("Q93 persisted report acceptance missing")
        verify_manifest(manifest, True)
        saved = json.loads(q93.VALIDATION.read_text(encoding="utf-8"))
        compare_nested(saved, validation, "saved_validation")
    else:
        if q93.VALIDATION.exists():
            raise ValueError("Q93 append-only validation already exists")
        report["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        report["acceptance"] = {
            "validator": "Q93_FORMULA_ACCEPTANCE_PASS",
            "workflow_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
            "source_sha": os.environ.get("GITHUB_SHA", ""),
            "human_review": "PENDING_HUMAN_REVIEW_INTEGRATION",
            "current_head_ci": "PENDING",
            "artifact_readback": "PENDING_EXACT_GIT_OBJECT_READBACK",
        }
        q93.dump(REPORT_PATH, report)
        checkpoint = CHECKPOINT_PATH.read_text(encoding="utf-8")
        checkpoint = checkpoint.replace("State: COMPUTED_PENDING_INDEPENDENT_ACCEPTANCE", "State: ACCEPTANCE_PASS")
        checkpoint += (
            "\n## Independent acceptance\n\n"
            "- Validator status: PASS.\n"
            f"- Strict-prior cutoffs: {total}/{total}.\n"
            f"- Ranking vectors replayed: {rank_count}.\n"
            f"- Spectral signal values replayed: {signal_count}.\n"
            f"- Permutation summary values replayed: {permutation_count}.\n"
            f"- Primary historical gate: {result['primary_gate']['status']}.\n"
        )
        CHECKPOINT_PATH.write_text(checkpoint, encoding="utf-8")
        validation["checks"]["report_sha256"] = q93.sha256_file(REPORT_PATH)
        q93.dump(q93.VALIDATION, validation)
        manifest["status"] = "ACCEPTANCE_PASS"
        for key, path in (
            ("report", REPORT_PATH), ("checkpoint", CHECKPOINT_PATH), ("validation", q93.VALIDATION)
        ):
            data = path.read_bytes()
            manifest["files"][key] = {
                "path": str(path.relative_to(ROOT)), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()
            }
        q93.dump(MANIFEST_PATH, manifest)
        verify_manifest(manifest, True)

    print("SONAR_Q93_ACCEPTANCE_BEGIN")
    print(json.dumps(validation, sort_keys=True, separators=(",", ":")))
    print("SONAR_Q93_ACCEPTANCE_END")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    validate(read_only=args.read_only)
