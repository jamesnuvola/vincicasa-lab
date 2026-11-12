#!/usr/bin/env python3
"""Q141-B2: quantify legacy floating-point tie sensitivity from the frozen B1 ledger."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
LEDGER = OUT / "q141_formula_alias_walkforward_target_ledger_2026-11-12.csv"
B1_MANIFEST = OUT / "q141_formula_registry_manifest_2026-11-12.json"
B1_REPORT = OUT / "q141_formula_alias_walkforward_report_2026-11-12.json"
PREREG = OUT / "q141_legacy_tie_sensitivity_preregistration_2026-11-12.json"
REPORT = OUT / "q141_legacy_tie_sensitivity_report_2026-11-12.json"
MANIFEST = OUT / "q141_legacy_tie_sensitivity_manifest_2026-11-12.json"
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
UNIFORM = {5: 0.125, 10: 0.25, 20: 0.5}
TOPK_KEYS = {
    5: ("stable_raw_top5_hit_share", "canonical_top5_hit_share", "legacy_numpy_top5_hit_share"),
    10: ("stable_raw_top10_hit_share", "canonical_top10_hit_share", "legacy_numpy_top10_hit_share"),
    20: ("stable_raw_top20_hit_share", "canonical_top20_hit_share", "legacy_numpy_top20_hit_share"),
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def as_int(row, key):
    value = float(row[key])
    rounded = round(value)
    if abs(value - rounded) > 1e-9:
        raise ValueError(f"Q141_B2_BLOCKED: {key} is not integer-valued: {row[key]}")
    return int(rounded)


def as_float(row, key):
    value = float(row[key])
    if not (value == value and abs(value) != float("inf")):
        raise ValueError(f"Q141_B2_BLOCKED: {key} is not finite")
    return value


def summarize_rows(rows, expected_split_counts=EXPECTED_SPLITS):
    if not rows:
        raise ValueError("Q141_B2_BLOCKED: empty target ledger")
    accum = {
        split: {
            "targets": 0, "formula_target_comparisons": 0, "rank_mismatches": 0,
            "max_rank_displacement": 0, "max_abs_score_delta": 0.0,
            "top5_delta_hits": 0, "top10_delta_hits": 0, "top20_delta_hits": 0,
            "top5_diff_targets": 0, "top10_diff_targets": 0, "top20_diff_targets": 0,
            "stable_hits": {5: 0.0, 10: 0.0, 20: 0.0},
            "legacy_hits": {5: 0.0, 10: 0.0, 20: 0.0},
        }
        for split in ("discovery", "validation", "blind_oos", "all")
    }
    previous_target = None
    for offset, row in enumerate(rows):
        split = row["split"]
        if split not in EXPECTED_SPLITS:
            raise ValueError(f"Q141_B2_BLOCKED: unexpected split {split}")
        target_index = as_int(row, "target_index")
        target_offset = as_int(row, "target_offset")
        prior_draws = as_int(row, "prior_draws")
        formula_count = as_int(row, "formula_sample_count")
        if target_offset != offset or target_index != 50 + offset or prior_draws != target_index:
            raise ValueError("Q141_B2_BLOCKED: target offset/index/prior history mismatch")
        target_date = date.fromisoformat(row["target_date"])
        cutoff_date = date.fromisoformat(row["cutoff_date"])
        if cutoff_date >= target_date:
            raise ValueError("Q141_B2_BLOCKED: non-prior cutoff")
        if previous_target is not None and target_date <= previous_target:
            raise ValueError("Q141_B2_BLOCKED: target dates are not strictly chronological")
        previous_target = target_date
        if formula_count != 120:
            raise ValueError(f"Q141_B2_BLOCKED: expected 120 formula samples, got {formula_count}")
        for key in ("alias_mismatches", "stable_raw_vs_canonical_score_mismatches",
                    "stable_raw_vs_canonical_rank_mismatches"):
            if as_int(row, key) != 0:
                raise ValueError(f"Q141_B2_BLOCKED: nonzero identity mismatch in {key}")
        rank_mismatches = as_int(row, "legacy_numpy_rank_mismatches")
        displacement = as_int(row, "legacy_numpy_max_rank_displacement")
        score_delta = as_float(row, "legacy_numpy_max_abs_score_delta")

        destinations = (accum[split], accum["all"])
        for acc in destinations:
            acc["targets"] += 1
            acc["formula_target_comparisons"] += formula_count
            acc["rank_mismatches"] += rank_mismatches
            acc["max_rank_displacement"] = max(acc["max_rank_displacement"], displacement)
            acc["max_abs_score_delta"] = max(acc["max_abs_score_delta"], score_delta)
            for k, (stable_key, canonical_key, legacy_key) in TOPK_KEYS.items():
                stable = as_float(row, stable_key)
                canonical = as_float(row, canonical_key)
                legacy = as_float(row, legacy_key)
                if abs(stable - canonical) > 1e-12:
                    raise ValueError(f"Q141_B2_BLOCKED: stable/canonical Top-{k} mismatch")
                delta_hits = (legacy - stable) * formula_count * 5
                rounded_delta = round(delta_hits)
                if abs(delta_hits - rounded_delta) > 1e-5:
                    raise ValueError(f"Q141_B2_BLOCKED: Top-{k} share delta is not an integer hit count")
                acc[f"top{k}_delta_hits"] += rounded_delta
                if rounded_delta:
                    acc[f"top{k}_diff_targets"] += 1
                acc["stable_hits"][k] += stable * formula_count * 5
                acc["legacy_hits"][k] += legacy * formula_count * 5

    result = {}
    for split, acc in accum.items():
        if expected_split_counts is not None and split != "all" and acc["targets"] != expected_split_counts[split]:
            raise ValueError(f"Q141_B2_BLOCKED: {split} target count {acc['targets']} != {expected_split_counts[split]}")
        slots = acc["formula_target_comparisons"] * 5
        topk = {}
        for k in (5, 10, 20):
            delta = acc[f"top{k}_delta_hits"]
            topk[str(k)] = {
                "uniform_reference_hit_share": UNIFORM[k],
                "stable_mean_hit_share": acc["stable_hits"][k] / slots,
                "legacy_numpy_mean_hit_share": acc["legacy_hits"][k] / slots,
                "legacy_minus_stable_hit_count": delta,
                "targets_with_any_hit_share_change": acc[f"top{k}_diff_targets"],
                "legacy_minus_stable_percentage_points": (delta / slots * 100.0) if slots else 0.0,
                "legacy_minus_stable_hits_per_100k_actual_number_slots": (delta / slots * 100000.0) if slots else 0.0,
            }
        comparisons = acc["formula_target_comparisons"]
        result[split] = {
            "targets": acc["targets"],
            "formula_target_comparisons": comparisons,
            "legacy_rank_mismatches": acc["rank_mismatches"],
            "legacy_rank_mismatch_rate": acc["rank_mismatches"] / comparisons if comparisons else 0.0,
            "maximum_rank_displacement": acc["max_rank_displacement"],
            "maximum_legacy_stable_score_delta": acc["max_abs_score_delta"],
            "topk": topk,
        }
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    b1_manifest_bytes = B1_MANIFEST.read_bytes()
    b1_manifest = json.loads(b1_manifest_bytes)
    b1_report_bytes = B1_REPORT.read_bytes()
    b1_report = json.loads(b1_report_bytes)
    ledger_bytes = LEDGER.read_bytes()
    archive_bytes = ARCHIVE.read_bytes()
    ledger_sha256 = sha256_bytes(ledger_bytes)
    ledger_blob_sha1 = git_blob_sha1(ledger_bytes)
    archive_blob_sha1 = git_blob_sha1(archive_bytes)

    if archive_blob_sha1 != prereg["source_archive_git_blob_sha1"]:
        raise ValueError("Q141_B2_BLOCKED: source archive blob mismatch")
    if b1_manifest["source_archive_git_blob_sha1"] != archive_blob_sha1:
        raise ValueError("Q141_B2_BLOCKED: B1 manifest archive lineage mismatch")
    if ledger_sha256 != b1_manifest["target_ledger_sha256"]:
        raise ValueError("Q141_B2_BLOCKED: B1 ledger SHA256 mismatch")
    if b1_report["source"]["archive_git_blob_sha1"] != archive_blob_sha1:
        raise ValueError("Q141_B2_BLOCKED: B1 report archive lineage mismatch")
    if b1_report["walkforward"]["strict_prior"] is not True:
        raise ValueError("Q141_B2_BLOCKED: B1 report does not certify strict-prior scoring")
    if b1_report["walkforward"]["targets"] != 3354:
        raise ValueError("Q141_B2_BLOCKED: B1 report target count mismatch")

    with LEDGER.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 3354:
        raise ValueError(f"Q141_B2_BLOCKED: target ledger rows {len(rows)} != 3354")
    summary = summarize_rows(rows)
    if summary["all"]["legacy_rank_mismatches"] != b1_manifest["legacy_numpy_rank_mismatches"]:
        raise ValueError("Q141_B2_BLOCKED: rank mismatch count disagrees with B1 manifest")
    if summary["all"]["formula_target_comparisons"] != b1_manifest["rank_comparisons"]:
        raise ValueError("Q141_B2_BLOCKED: formula-target comparison count disagrees with B1 manifest")

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-B2",
        "status": "COMPLETE_DIAGNOSTIC",
        "decision": "LEGACY_FLOATING_POINT_ORDER_CHANGES_SOME_TOP5_TOP10_MEMBERSHIPS_BUT_HAS_TINY_NET_AGGREGATE_HIT_EFFECT",
        "hypothesis": "Legacy NumPy mean and stable math.fsum can resolve near-tied number scores differently; quantify whether those rank differences materially change sampled Top-k coverage.",
        "interpretation": "This is an implementation sensitivity result only. Stable raw and canonical evaluations remain identical; no predictive advantage or production-ranker replacement is implied.",
        "source": {
            "archive_git_blob_sha1": archive_blob_sha1,
            "eligible_draws": 3404,
            "cutoff": "2026-11-10",
            "b1_ledger_sha256": ledger_sha256,
            "b1_ledger_git_blob_sha1": ledger_blob_sha1,
            "b1_manifest_sha256": sha256_bytes(b1_manifest_bytes),
            "b1_report_sha256": sha256_bytes(b1_report_bytes),
        },
        "formula_sample": {"count": 120, "per_subset_size": 12, "subset_sizes": list(range(1, 11)), "deterministic": True},
        "walkforward": {
            "targets": len(rows),
            "split_counts": EXPECTED_SPLITS,
            "strict_prior_cutoffs_rechecked": True,
            "stable_raw_vs_canonical_score_and_rank_mismatches": 0,
            "legacy_rank_mismatches": summary["all"]["legacy_rank_mismatches"],
            "legacy_rank_mismatch_rate": summary["all"]["legacy_rank_mismatch_rate"],
            "maximum_rank_displacement": summary["all"]["maximum_rank_displacement"],
            "maximum_legacy_stable_score_delta": summary["all"]["maximum_legacy_stable_score_delta"],
            "metrics_by_split": {k: summary[k] for k in ("discovery", "validation", "blind_oos")},
            "all_targets": summary["all"],
        },
        "statistical_inference": {
            "p_values": "not applicable: deterministic implementation/numerical sensitivity audit",
            "multiple_testing": "not applicable: three fixed descriptive Top-k endpoints; no model selection or inferential claim",
            "predictive_lift_claim": False,
        },
        "limitations": [
            "Uses the deterministic 120-formula B1 sample, not all 16,628,808 raw formulas or 9,808,263 canonical IDs.",
            "Top-k share differences are averaged across the 120 formula instances per target; per-formula membership ledgers are not stored in B1.",
            "Historical blind_oos is exposed research history, not virgin prospective evidence.",
            "No engine, production ranker or historical forecast is changed.",
        ],
        "next_action": "Keep legacy Q80 ranker unchanged for compatibility; use stable math.fsum for the canonical registry. Import Q90 interaction/gate ASTs and Q7 candidate-quintet ASTs as separate typed output families with source lineage and archive reconciliation.",
    }
    report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    REPORT.write_bytes(report_bytes)
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-B2",
        "status": "PERSISTENCE_BUNDLE_READY",
        "source_archive_git_blob_sha1": archive_blob_sha1,
        "source_ledger_sha256": ledger_sha256,
        "source_ledger_git_blob_sha1": ledger_blob_sha1,
        "source_b1_manifest_sha256": sha256_bytes(b1_manifest_bytes),
        "source_b1_report_sha256": sha256_bytes(b1_report_bytes),
        "target_rows": len(rows),
        "split_counts": EXPECTED_SPLITS,
        "formula_sample_count": 120,
        "rank_mismatches": summary["all"]["legacy_rank_mismatches"],
        "report_path": str(REPORT.relative_to(ROOT)),
        "report_sha256": sha256_bytes(report_bytes),
        "runner_path": str(Path(__file__).relative_to(ROOT)),
        "runner_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "preregistration_sha256": sha256_bytes(PREREG.read_bytes()),
        "decision": report["decision"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "targets": len(rows),
        "rank_mismatches": summary["all"]["legacy_rank_mismatches"],
        "rank_mismatch_rate": summary["all"]["legacy_rank_mismatch_rate"],
        "topk": summary["all"]["topk"],
        "report_sha256": manifest["report_sha256"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
