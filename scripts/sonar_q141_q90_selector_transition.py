#!/usr/bin/env python3
"""Q141-C6: prior-only selector transition state added to Q7 meta-quality."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import sonar_q141_q90_to_q7_transfer as c5  # noqa: E402

OUT = ROOT / "reports" / "sequence_agent"
WINDOW = 50
FEATURE_START = 100
DISCOVERY_START = 150
DISCOVERY_END = 1972
VALIDATION_END = 2629
TRAIN_START = 100
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261126
PRACTICAL_THRESHOLD = 0.005

REPORT = OUT / "q141_q90_selector_transition_report_2026-11-12.json"
LEDGER = OUT / "q141_q90_selector_transition_target_ledger_2026-11-12.csv"
MANIFEST = OUT / "q141_q90_selector_transition_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_q90_selector_transition_checkpoint_2026-11-12.json"
PREREG = OUT / "q141_q90_selector_transition_preregistration_2026-11-12.json"
PREREG_MD = OUT / "q141_q90_selector_transition_preregistration_2026-11-12.md"

C5_REPORT = OUT / "q141_q90_to_q7_transfer_report_2026-11-12.json"
C5_MANIFEST = OUT / "q141_q90_to_q7_transfer_manifest_2026-11-12.json"
C5_CHECKPOINT = OUT / "q141_q90_to_q7_transfer_checkpoint_2026-11-12.json"
C5_RECEIPT = OUT / "q141_q90_to_q7_transfer_remote_readback_2026-11-12.json"

Q80_FAMILIES = (
    "frequency_change", "frequency_level", "lag_memory",
    "neighbour_field", "position_dependence", "recency_gap",
)
Q90_FAMILIES = (
    "linear_mean_L4", "linear_mean_L5", "linear_mean_L6",
    "linear_mean_L7", "linear_mean_L8", "pairwise_interaction_I4",
    "conditional_gate_G4",
)
WARMUP_LABELS = {"", "EQUAL_WARMUP", "warmup_equal_family"}

def transition_state(rows: list[dict[str, str]], family_names: tuple[str, ...]) -> tuple[float, float, int, int]:
    labels = [str(row.get("selected_family", "")) for row in rows]
    if any(label in WARMUP_LABELS for label in labels):
        raise RuntimeError("transition window contains warm-up selector labels")
    allowed = set(family_names)
    if any(label not in allowed for label in labels):
        raise RuntimeError("transition window contains an unknown or oracle family label")
    if len(labels) != WINDOW:
        raise RuntimeError(f"transition window must contain exactly {WINDOW} labels")
    switches = sum(a != b for a, b in zip(labels[:-1], labels[1:]))
    switch_rate = float(switches / (WINDOW - 1))
    counts = Counter(labels)
    probabilities = np.asarray([counts.get(name, 0) / WINDOW for name in family_names], dtype=np.float64)
    positive = probabilities > 0
    entropy = float(-np.sum(probabilities[positive] * np.log(probabilities[positive])) / math.log(len(family_names)))
    return switch_rate, entropy, len(labels), int(switches)

def transition_features_for_target(
    q7_row: dict[str, str],
    q80_rows: list[dict[str, str]],
    q90_rows: list[dict[str, str]],
) -> dict:
    q80_keys = [int(row["target_index"]) for row in q80_rows]
    q90_keys = [int(row["prior_draws"]) for row in q90_rows]
    target_index = int(q7_row["prior_draws"])
    q80_prior = c5.prior_window(q80_rows, q80_keys, target_index, WINDOW, "target_index")
    q90_prior = c5.prior_window(q90_rows, q90_keys, target_index, WINDOW, "prior_draws")
    for source_name, rows in (("Q80", q80_prior), ("Q90", q90_prior)):
        if any(row["target_date"] > q7_row["cutoff_date"] for row in rows):
            raise RuntimeError(f"{source_name} transition feature contains a row after target cutoff")
    q80_switch, q80_entropy, q80_n, q80_switches = transition_state(q80_prior, Q80_FAMILIES)
    q90_switch, q90_entropy, q90_n, q90_switches = transition_state(q90_prior, Q90_FAMILIES)
    if q80_n != WINDOW or q90_n != WINDOW:
        raise RuntimeError("incomplete active selector transition window")
    return {
        "q80_prior50_selector_switch_rate": q80_switch,
        "q80_prior50_selector_family_entropy": q80_entropy,
        "q90_prior50_selector_switch_rate": q90_switch,
        "q90_prior50_selector_family_entropy": q90_entropy,
        "q80_prior50_selector_switches": q80_switches,
        "q90_prior50_selector_switches": q90_switches,
        "q80_prior50_active_labels": q80_n,
        "q90_prior50_active_labels": q90_n,
        "q80_last_prior_target_index": int(q80_prior[-1]["target_index"]),
        "q90_last_prior_draws": int(q90_prior[-1]["prior_draws"]),
        "q80_last_prior_target_date": q80_prior[-1]["target_date"],
        "q90_last_prior_target_date": q90_prior[-1]["target_date"],
    }

def build_transition_matrix(q7_rows, q80_rows, q90_rows):
    matrix = np.full((len(q7_rows), 4), np.nan, dtype=np.float64)
    details = []
    for i, q7_row in enumerate(q7_rows):
        if i < FEATURE_START:
            details.append({"available": False, "reason": "selector warm-up / transition window not fully active"})
            continue
        state = transition_features_for_target(q7_row, q80_rows, q90_rows)
        values = [
            state["q80_prior50_selector_switch_rate"],
            state["q80_prior50_selector_family_entropy"],
            state["q90_prior50_selector_switch_rate"],
            state["q90_prior50_selector_family_entropy"],
        ]
        if not np.isfinite(values).all():
            raise RuntimeError("non-finite transition feature")
        matrix[i] = values
        details.append({"available": True, **state})
    if not np.isfinite(matrix[FEATURE_START:]).all():
        raise RuntimeError("transition matrix incomplete after feature start")
    return matrix, details

def verify_c5_readback():
    report = c5.read_json(C5_REPORT)
    manifest = c5.read_json(C5_MANIFEST)
    checkpoint = c5.read_json(C5_CHECKPOINT)
    receipt = c5.read_json(C5_RECEIPT)
    if report.get("task_id") != "Q141-C5" or report.get("status") != "WALKFORWARD_COMPLETE":
        raise RuntimeError("Q141-C5 report is not complete")
    if report.get("decision") != "NO_Q90_INCREMENTAL_TRANSFER_LIFT_DEMONSTRATED":
        raise RuntimeError("Q141-C5 decision differs from the pinned negative result")
    if checkpoint.get("status") != "REMOTE_GIT_READBACK_VERIFIED":
        raise RuntimeError("Q141-C5 checkpoint lacks remote readback")
    if receipt.get("status") != "REMOTE_GIT_READBACK_VERIFIED" or receipt.get("files_verified") != 2:
        raise RuntimeError("Q141-C5 remote readback receipt invalid")
    if receipt.get("code_lineage_verified") != len(manifest.get("code_lineage", {})):
        raise RuntimeError("Q141-C5 historical code-lineage receipt count mismatch")
    manifest_bytes = C5_MANIFEST.read_bytes()
    if receipt.get("manifest_git_blob_sha1") != c5.git_blob_sha1(manifest_bytes):
        raise RuntimeError("Q141-C5 manifest blob identity mismatch")
    verified_files = []
    for label, expected in manifest["files"].items():
        raw = (ROOT / expected["path"]).read_bytes()
        if len(raw) != expected["bytes"] or c5.sha256_bytes(raw) != expected["sha256"] or c5.git_blob_sha1(raw) != expected["git_blob_sha1"]:
            raise RuntimeError(f"Q141-C5 persisted output mismatch: {label}")
        verified_files.append(label)
    lineage_drift = []
    allowed_drift = {"q80_report", "q80_manifest"}
    for label, expected in manifest["code_lineage"].items():
        raw = (ROOT / expected["path"]).read_bytes()
        matches = (
            len(raw) == expected["bytes"]
            and c5.sha256_bytes(raw) == expected["sha256"]
            and c5.git_blob_sha1(raw) == expected["git_blob_sha1"]
        )
        if not matches:
            if label not in allowed_drift:
                raise RuntimeError(f"Q141-C5 unexpected source lineage drift: {label}")
            lineage_drift.append(label)

    # Q80's report and manifest were replayed after C5; allow only that
    # documented metadata drift if the underlying ledger and archive remain exact.
    q80_report = c5.read_json(c5.Q80_REPORT)
    q80_manifest = c5.read_json(c5.Q80_MANIFEST)
    q80_ledger_sha = c5.sha256_bytes(c5.Q80_LEDGER.read_bytes())
    if q80_report.get("task_id") != "Q141-C0" or q80_report.get("source", {}).get("git_blob_sha1") != c5.Q141_ARCHIVE_BLOB:
        raise RuntimeError("current Q80 report archive lineage invalid")
    if q80_manifest.get("source_archive_git_blob_sha1") != c5.Q141_ARCHIVE_BLOB:
        raise RuntimeError("current Q80 manifest archive lineage invalid")
    if q80_manifest.get("target_rows") != c5.EXPECTED_Q80_ROWS or q80_manifest.get("target_ledger_sha256") != q80_ledger_sha:
        raise RuntimeError("current Q80 manifest/ledger identity invalid")
    if q80_report.get("status") != "EXECUTED_EXPLORATORY":
        raise RuntimeError("current Q80 report status invalid")
    if any(label not in allowed_drift for label in lineage_drift):
        raise RuntimeError("Q141-C5 lineage drift exceeds the documented Q80 replay")
    return {
        "report_git_blob_sha1": c5.git_blob_sha1(C5_REPORT.read_bytes()),
        "manifest_git_blob_sha1": c5.git_blob_sha1(manifest_bytes),
        "checkpoint_git_blob_sha1": c5.git_blob_sha1(C5_CHECKPOINT.read_bytes()),
        "receipt_git_blob_sha1": c5.git_blob_sha1(C5_RECEIPT.read_bytes()),
        "output_files_verified": len(verified_files),
        "historical_code_lineage_receipt_count": receipt["code_lineage_verified"],
        "current_source_lineage_drift": lineage_drift,
        "drift_resolution": "Q80 report/manifest metadata replay allowed; Q80 ledger SHA-256 and archive lineage revalidated exactly.",
        "blind_oos_effect": report["primary"]["mae_improvement"],
        "blind_oos_p": report["primary"]["one_sided_block_signflip_p"],
    }

def descriptive_transition_atlas(q7_rows, y, transition):
    ranges = {
        "discovery": (DISCOVERY_START, DISCOVERY_END),
        "validation": (DISCOVERY_END, VALIDATION_END),
        "blind_oos": (VALIDATION_END, len(q7_rows)),
    }
    out = {}
    for split, (start, end) in ranges.items():
        idx = np.arange(start, end, dtype=np.int64)
        q80_switch, q80_entropy, q90_switch, q90_entropy = (transition[idx, j] for j in range(4))
        out[split] = {
            "targets": int(len(idx)),
            "q80_switch_rate_mean": float(q80_switch.mean()),
            "q80_family_entropy_mean": float(q80_entropy.mean()),
            "q90_switch_rate_mean": float(q90_switch.mean()),
            "q90_family_entropy_mean": float(q90_entropy.mean()),
            "pearson_q80_switch_rate_vs_q7_meta_quality": c5.safe_corr(q80_switch.tolist(), y[idx].tolist()),
            "pearson_q80_entropy_vs_q7_meta_quality": c5.safe_corr(q80_entropy.tolist(), y[idx].tolist()),
            "pearson_q90_switch_rate_vs_q7_meta_quality": c5.safe_corr(q90_switch.tolist(), y[idx].tolist()),
            "pearson_q90_entropy_vs_q7_meta_quality": c5.safe_corr(q90_entropy.tolist(), y[idx].tolist()),
            "interpretation": "descriptive association only; no causal or predictive claim",
        }
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source = c5.verify_sources()
    c5_readback = verify_c5_readback()
    q7, q80, q90 = c5.read_csv(c5.Q7_LEDGER), c5.read_csv(c5.Q80_LEDGER), c5.read_csv(c5.Q90_LEDGER)
    joined = c5.validate_and_join(q7, q80, q90)
    x0, x1, x2, base_feature_rows = c5.build_features(q7, q80, q90)
    transition, transition_rows = build_transition_matrix(q7, q80, q90)
    y = np.asarray([float(row["mean_percentile_all_formulas"]) for row in q7], dtype=np.float64)
    if not np.isfinite(y).all() or np.any(y < 0) or np.any(y > 1):
        raise RuntimeError("Q7 target meta-quality outside [0,1]")
    if not np.isfinite(x2[FEATURE_START:]).all():
        raise RuntimeError("Q7+Q80+Q90 baseline features missing after feature start")
    x3 = np.column_stack([x2, transition])
    if not np.isfinite(x3[FEATURE_START:]).all():
        raise RuntimeError("M3 feature matrix missing after feature start")

    matrices = {"m0_q7_only": x0, "m1_q7_q80": x1, "m2_q7_q80_q90": x2, "m3_with_transitions": x3}
    predictions = {name: np.full(len(q7), np.nan, dtype=np.float64) for name in matrices}
    training_rows = np.zeros(len(q7), dtype=np.int32)
    modes = ["warmup"] * len(q7)

    for i in range(DISCOVERY_START, DISCOVERY_END):
        train = np.arange(TRAIN_START, i, dtype=np.int64)
        if len(train) < 50:
            raise RuntimeError("Q141-C6 Discovery model has fewer than 50 prior training rows")
        for name, matrix in matrices.items():
            model = c5.fit_ridge(matrix[train], y[train], alpha=1.0)
            predictions[name][i] = float(c5.predict_ridge(model, matrix[i:i+1])[0])
        training_rows[i] = len(train)
        modes[i] = "expanding_prequential_discovery"

    discovery_train = np.arange(TRAIN_START, DISCOVERY_END, dtype=np.int64)
    frozen = {name: c5.fit_ridge(matrix[discovery_train], y[discovery_train], alpha=1.0) for name, matrix in matrices.items()}
    for i in range(DISCOVERY_END, len(q7)):
        for name, matrix in matrices.items():
            predictions[name][i] = float(c5.predict_ridge(frozen[name], matrix[i:i+1])[0])
        training_rows[i] = len(discovery_train)
        modes[i] = "frozen_discovery_coefficients_prequential_features"

    if any(not np.isfinite(values[DISCOVERY_START:]).all() for values in predictions.values()):
        raise RuntimeError("Q141-C6 prediction ledger contains non-finite values")

    split_ranges = {
        "discovery": (DISCOVERY_START, DISCOVERY_END),
        "validation": (DISCOVERY_END, VALIDATION_END),
        "blind_oos": (VALIDATION_END, len(q7)),
    }
    metrics, ledger_rows = {}, []
    for split, (start, end) in split_ranges.items():
        idx = np.arange(start, end, dtype=np.int64)
        metrics[split] = {
            "targets": int(len(idx)),
            "m0_q7_only": c5.metric_summary(y[idx], predictions["m0_q7_only"][idx]),
            "m1_q7_q80": c5.metric_summary(y[idx], predictions["m1_q7_q80"][idx]),
            "m2_q7_q80_q90": c5.metric_summary(y[idx], predictions["m2_q7_q80_q90"][idx]),
            "m3_with_transitions": c5.metric_summary(y[idx], predictions["m3_with_transitions"][idx]),
            "primary_mae_improvement_m2_minus_m3": float(
                np.mean(np.abs(y[idx] - predictions["m2_q7_q80_q90"][idx]))
                - np.mean(np.abs(y[idx] - predictions["m3_with_transitions"][idx]))
            ),
        }
        for i in idx:
            q7_row, base, tr = q7[i], base_feature_rows[i], transition_rows[i]
            ledger_rows.append({
                "target_index": int(q7_row["prior_draws"]),
                "target_date": q7_row["target_date"], "cutoff_date": q7_row["cutoff_date"],
                "prior_draws": int(q7_row["prior_draws"]), "split": split,
                "actual_quintet": q7_row["actual_quintet"],
                "q7_mean_percentile_all_formulas": float(y[i]),
                **{k: base[k] for k in c5.Q7_X_NAMES + c5.Q80_X_NAMES + c5.Q90_X_NAMES},
                "q80_prior50_selector_switch_rate": tr["q80_prior50_selector_switch_rate"],
                "q80_prior50_selector_family_entropy": tr["q80_prior50_selector_family_entropy"],
                "q90_prior50_selector_switch_rate": tr["q90_prior50_selector_switch_rate"],
                "q90_prior50_selector_family_entropy": tr["q90_prior50_selector_family_entropy"],
                "q80_prior50_selector_switches": tr["q80_prior50_selector_switches"],
                "q90_prior50_selector_switches": tr["q90_prior50_selector_switches"],
                "q80_prior50_active_labels": tr["q80_prior50_active_labels"],
                "q90_prior50_active_labels": tr["q90_prior50_active_labels"],
                "q80_last_prior_target_index": tr["q80_last_prior_target_index"],
                "q90_last_prior_draws": tr["q90_last_prior_draws"],
                "pred_m2": float(predictions["m2_q7_q80_q90"][i]),
                "pred_m3": float(predictions["m3_with_transitions"][i]),
                "abs_error_m2": float(abs(predictions["m2_q7_q80_q90"][i] - y[i])),
                "abs_error_m3": float(abs(predictions["m3_with_transitions"][i] - y[i])),
                "primary_improvement_m2_minus_m3": float(
                    abs(predictions["m2_q7_q80_q90"][i] - y[i])
                    - abs(predictions["m3_with_transitions"][i] - y[i])
                ),
                "model_mode": modes[i], "training_rows": int(training_rows[i]),
            })

    blind = np.asarray([r["primary_improvement_m2_minus_m3"] for r in ledger_rows if r["split"] == "blind_oos"], dtype=np.float64)
    effect = float(blind.mean())
    ci = c5.moving_block_ci(blind, BLOCK_LENGTH, REPLICATES, SEED + 1)
    p = c5.block_signflip_p(blind, BLOCK_LENGTH, REPLICATES, SEED)
    supported = effect >= PRACTICAL_THRESHOLD and p < 0.05 and ci[0] > 0.0
    atlas = descriptive_transition_atlas(q7, y, transition)

    report = {
        "schema_version": "1.0", "task_id": "Q141-C6", "status": "WALKFORWARD_COMPLETE",
        "decision": "Q80_Q90_TRANSITION_STATE_LIFT_DEMONSTRATED" if supported else "NO_Q80_Q90_TRANSITION_STATE_LIFT_DEMONSTRATED",
        "hypothesis": c5.read_json(PREREG)["hypothesis"],
        "estimand": c5.read_json(PREREG)["estimand"],
        "source": {
            "q141_archive_git_blob_sha1": c5.Q141_ARCHIVE_BLOB,
            "q7_archive_git_blob_sha1": c5.Q7_ARCHIVE_BLOB,
            "q90_archive_git_blob_sha1": c5.Q90_ARCHIVE_BLOB,
            "q90_artifact_sha256": c5.Q90_ARTIFACT_SHA256,
            "q7_rows": len(q7), "q80_rows": len(q80), "q90_rows": len(q90),
            "q7_cutoff": "2026-10-24", "q80_cutoff": "2026-11-10", "q90_cutoff": "2026-11-07",
            "q90_full_catalog_count": 330429, "q90_fixed_sample_count": 700,
            "q7_ledger_sha256": source["source_hashes"]["q7_ledger_sha256"],
            "q80_ledger_sha256": source["source_hashes"]["q80_ledger_sha256"],
            "q90_ledger_sha256": source["source_hashes"]["q90_ledger_sha256"],
        },
        "prior_c5_readback": c5_readback,
        "alignment": {"matched_rows": len(joined), "mismatches": 0, "q7_split_authoritative": True},
        "walkforward": {
            "strict_prior": True, "transition_window": WINDOW,
            "first_transition_feature_offset": FEATURE_START,
            "first_scored_discovery_offset": DISCOVERY_START,
            "training_start_offset": TRAIN_START,
            "discovery_end_offset": DISCOVERY_END, "validation_end_offset": VALIDATION_END,
            "evaluated_targets": {"discovery": 1822, "validation": 657, "blind_oos": 657, "total": 3136},
            "coefficients_frozen_after_discovery": True, "ridge_alpha_fixed": 1.0,
            "standardization": "training rows only",
            "update_order": "score current target; only then allow its outcome into future rolling state",
            "warmup_policy": "Exclude first 100 Q7 target offsets from transition features; first scored Discovery target is offset 150 after 50 fully active training rows.",
        },
        "metrics_by_split": metrics,
        "primary_blind_oos": {
            "comparison": "M2 Q7+Q80+Q90 versus M3 M2 plus prior-50 Q80/Q90 selector transition state",
            "mae_improvement": effect, "practical_threshold": PRACTICAL_THRESHOLD,
            "ci95_circular_moving_block": ci, "one_sided_block_signflip_p": p,
            "block_length": BLOCK_LENGTH, "replicates": REPLICATES,
            "confirmatory_endpoint_count": 1,
            "multiplicity_correction": "One confirmatory endpoint; other model comparisons and atlas associations are descriptive only.",
            "criteria_met": supported,
        },
        "transition_atlas_descriptive": atlas,
        "limitations": [
            "Target is Q7 formula-universe meta-quality, not winning quintet or number-hit count.",
            "Q90 uses a fixed 700-formula sample from 330,429 and a 20-feature Discovery-selected subset from 59 source features.",
            "Q80/Q90 selected_family labels are generated by source prior-only selectors; only the previous 50 labels are used, never oracle_best_family_descriptive_only.",
            "Q7/Q80/Q90 source cutoffs differ; exact target/cutoff/quintet/index alignment was verified.",
            "Historical Blind OOS has prior SONAR exposure and is not virgin prospective evidence.",
            "A null result does not establish that all transition information is absent; this tests only four fixed rolling transition summaries.",
        ],
        "governance": {"no_engine_promotion": True, "no_shadow_insertion": True, "no_canonical_archive_mutation": True, "no_merge": True, "protected_prs": [6, 7, 8]},
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path, ledger_path = output_dir / REPORT.name, output_dir / LEDGER.name
    c5.write_json(report_path, report)
    c5.write_csv(ledger_path, ledger_rows, list(ledger_rows[0].keys()))

    lineage_paths = {
        "q7_report": c5.Q7_REPORT, "q7_manifest": c5.Q7_MANIFEST, "q7_ledger": c5.Q7_LEDGER,
        "q80_report": c5.Q80_REPORT, "q80_manifest": c5.Q80_MANIFEST, "q80_ledger": c5.Q80_LEDGER,
        "q90_report": c5.Q90_REPORT, "q90_manifest": c5.Q90_MANIFEST, "q90_ledger": c5.Q90_LEDGER,
        "c5_report": C5_REPORT, "c5_manifest": C5_MANIFEST, "c5_checkpoint": C5_CHECKPOINT, "c5_receipt": C5_RECEIPT,
        "c5_preregistration": c5.PREREG, "c5_runner": ROOT / "scripts" / "sonar_q141_q90_to_q7_transfer.py",
        "c5_tests": ROOT / "tests" / "test_sonar_q141_q90_to_q7_transfer.py",
        "c5_workflow": ROOT / ".github" / "workflows" / "q141-c5-q90-to-q7-transfer.yml",
        "preregistration_json": PREREG, "preregistration_markdown": PREREG_MD,
        "runner": ROOT / "scripts" / "sonar_q141_q90_selector_transition.py",
        "tests": ROOT / "tests" / "test_sonar_q141_q90_selector_transition.py",
        "workflow": ROOT / ".github" / "workflows" / "q141-c6-q90-selector-transition.yml",
    }
    code_lineage = {}
    for label, path in lineage_paths.items():
        raw = path.read_bytes()
        code_lineage[label] = {"path": str(path.relative_to(ROOT)), "bytes": len(raw), "sha256": c5.sha256_bytes(raw), "git_blob_sha1": c5.git_blob_sha1(raw)}
    files = {}
    for label, path in (("report", report_path), ("target_ledger", ledger_path)):
        raw = path.read_bytes()
        files[label] = {
            "path": f"reports/sequence_agent/{path.name}", "bytes": len(raw),
            "sha256": c5.sha256_bytes(raw), "git_blob_sha1": c5.git_blob_sha1(raw),
            "rows": len(ledger_rows) if label == "target_ledger" else None,
        }
    manifest = {
        "schema_version": "1.0", "task_id": "Q141-C6",
        "status": "OUTPUTS_COMPUTED_PENDING_REMOTE_READBACK",
        "source_archive_git_blob_sha1": c5.Q141_ARCHIVE_BLOB,
        "q7_archive_git_blob_sha1": c5.Q7_ARCHIVE_BLOB,
        "q90_archive_git_blob_sha1": c5.Q90_ARCHIVE_BLOB,
        "q90_artifact_sha256": c5.Q90_ARTIFACT_SHA256,
        "target_count": len(ledger_rows),
        "split_counts": {"discovery": 1822, "validation": 657, "blind_oos": 657},
        "files": files, "code_lineage": code_lineage,
    }
    c5.write_json(output_dir / MANIFEST.name, manifest)
    checkpoint = {
        "schema_version": "1.0", "task_id": "Q141-C6_CHECKPOINT",
        "status": "OUTPUTS_COMPUTED_PENDING_REMOTE_READBACK",
        "decision": report["decision"],
        "branch": os.environ.get("GITHUB_REF_NAME", "research/q141-formula-universe-behaviour-mapping-20261112"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "source_archive_git_blob_sha1": c5.Q141_ARCHIVE_BLOB,
        "target_count": len(ledger_rows), "blind_oos_effect": effect,
        "blind_oos_ci95": ci, "blind_oos_p": p,
        "report_path": f"reports/sequence_agent/{REPORT.name}",
        "ledger_path": f"reports/sequence_agent/{LEDGER.name}",
        "manifest_path": f"reports/sequence_agent/{MANIFEST.name}",
        "next_action": "Review transition-state incremental evidence; if null, prioritize full Q90 AST feature-lineage reconciliation and a prospective-only state monitor rather than another historical selector.",
    }
    c5.write_json(output_dir / CHECKPOINT.name, checkpoint)
    print(json.dumps({"task_id": "Q141-C6", "decision": report["decision"], "targets": len(ledger_rows), "blind_oos_effect": effect, "blind_oos_ci95": ci, "blind_oos_p": p, "report_sha256": c5.sha256_bytes(report_path.read_bytes()), "ledger_sha256": c5.sha256_bytes(ledger_path.read_bytes())}, sort_keys=True))

if __name__ == "__main__":
    main()
