#!/usr/bin/env python3
"""Fail-closed validator for Q84 K=10/20/50 sensitivity outputs."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math
from datetime import datetime, timezone
from collections import Counter
from pathlib import Path
import numpy as np

import sonar_strategy_atlas as q84
import sonar_strategy_atlas_k_sensitivity as sens
from sonar_sequence_agent import MIN_HISTORY, read_draws

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate(write=True):
    protocol = json.loads(sens.PROTOCOL.read_text(encoding="utf-8"))
    report = json.loads(sens.REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(sens.MANIFEST.read_text(encoding="utf-8"))
    base = json.loads(sens.BASE_REPORT.read_text(encoding="utf-8"))
    draws = read_draws()
    dates = [d["date"].isoformat() for d in draws]
    archive_sha1 = q84.git_blob_sha1(sens.ARCHIVE)
    archive_sha256 = sha256(sens.ARCHIVE)
    if (archive_sha1 != protocol["source_archive"]["git_blob_sha1"]
            or archive_sha256 != protocol["source_archive"]["sha256"]
            or len(draws) != protocol["source_archive"]["draw_count"]
            or dates[-1] != protocol["source_archive"]["last_date"]):
        raise ValueError("Q84-K: canonical archive mismatch")
    if report.get("source_archive", {}).get("sha256") != archive_sha256:
        raise ValueError("Q84-K: report archive hash mismatch")
    total = len(draws) - MIN_HISTORY
    target_dates = dates[MIN_HISTORY:]
    split_all = [q84.split_name(i, total) for i in range(total)]
    split_counts = dict(Counter(split_all))
    if report.get("walk_forward", {}).get("target_count") != total:
        raise ValueError("Q84-K: target count mismatch")
    if report.get("walk_forward", {}).get("split_counts") != split_counts:
        raise ValueError("Q84-K: split counts mismatch")

    with gzip.open(sens.LEDGER, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = reader.fieldnames or []
    if len(rows) != total:
        raise ValueError(f"Q84-K: ledger rows {len(rows)} != {total}")
    model_keys = sens.MODEL_KEYS
    hits = np.zeros((total, 5, 3), dtype=np.int8)
    actual_rank = np.zeros((total, 5, 5), dtype=np.int8)
    model_ids_all = [*sens.MODEL_IDS, sens.FIXED_MODEL_ID]
    for i, row in enumerate(rows):
        draw_index = MIN_HISTORY + i
        if row["target_date"] != dates[draw_index]:
            raise ValueError(f"Q84-K: target date mismatch at {i}")
        if row["prior_cutoff_date"] != dates[draw_index - 1] or int(row["prior_draw_count"]) != draw_index:
            raise ValueError(f"Q84-K: strict prior cutoff mismatch at {i}")
        expected = " ".join(str(x) for x in draws[draw_index]["nums"])
        if row["actual_quintet"] != expected:
            raise ValueError(f"Q84-K: actual quintet mismatch at {i}")
        if row["split"] != split_all[i]:
            raise ValueError(f"Q84-K: split mismatch at {i}")
        state = np.asarray(json.loads(row["flow_state"]), dtype=float)
        if state.shape != (len(q84.FLOW_FEATURES),) or not np.isfinite(state).all():
            raise ValueError(f"Q84-K: invalid prior flow state at {i}")
        for k in sens.K_VALUES:
            dates_near = json.loads(row[f"k{k}_nearest_target_dates"])
            if len(dates_near) != int(row[f"k{k}_analog_count"]) or len(dates_near) > k:
                raise ValueError(f"Q84-K: K={k} analogue count mismatch at {i}")
            if any(d >= row["target_date"] for d in dates_near):
                raise ValueError(f"Q84-K: current/future analogue leakage at {i}, K={k}")
            eff = float(row[f"k{k}_effective_n"])
            if eff < -1e-9 or eff > k + 1e-6:
                raise ValueError(f"Q84-K: effective sample size outside [0,K] at {i}, K={k}")
        for model_index, key in enumerate(model_keys):
            vector = [int(x) for x in row[f"rank_vector_{key}"].split()]
            if len(vector) != 40 or sorted(vector) != list(range(1, 41)):
                raise ValueError(f"Q84-K: invalid 40-number rank vector at {i}/{key}")
            actual_numbers = draws[draw_index]["nums"]
            expected_ranks = [vector[n - 1] for n in actual_numbers]
            actual_values = [int(x) for x in row[f"actual_ranks_{key}"].split()]
            if actual_values != expected_ranks:
                raise ValueError(f"Q84-K: actual rank reconciliation failed at {i}/{key}")
            actual_rank[i, model_index] = actual_values
            for j, endpoint in enumerate(("top5", "top10", "top20")):
                value = int(row[f"hits_{endpoint}_{key}"])
                if value != sum(r <= (5, 10, 20)[j] for r in expected_ranks):
                    raise ValueError(f"Q84-K: hit count mismatch at {i}/{key}/{endpoint}")
                hits[i, model_index, j] = value
        # Fixed Q84 comparator is a descriptive fifth ranking, not a member of the new Holm family.
        vector = [int(x) for x in row["rank_vector_fixed_discovery"].split()]
        if len(vector) != 40 or sorted(vector) != list(range(1, 41)):
            raise ValueError(f"Q84-K: invalid fixed-comparator rank vector at {i}")
        expected_ranks = [vector[n - 1] for n in draws[draw_index]["nums"]]
        actual_values = [int(x) for x in row["actual_ranks_fixed_discovery"].split()]
        if actual_values != expected_ranks:
            raise ValueError(f"Q84-K: fixed comparator rank reconciliation failed at {i}")
        for j, endpoint in enumerate(("top5", "top10", "top20")):
            if int(row[f"hits_{endpoint}_fixed_discovery"]) != sum(r <= (5, 10, 20)[j] for r in expected_ranks):
                raise ValueError(f"Q84-K: fixed comparator hit mismatch at {i}/{endpoint}")
            hits[i, 4, j] = int(row[f"hits_{endpoint}_fixed_discovery"])
        actual_rank[i, 4] = actual_values

    # Recompute the 36-test global Holm family from the complete per-target ledger.
    tests, metrics = [], []
    indices = {s: np.asarray([i for i, name in enumerate(split_all) if name == s], dtype=int) for s in sens.SPLITS}
    for model_index, strategy_id in enumerate(sens.MODEL_IDS):
        for split in sens.SPLITS:
            idx = indices[split]
            item = q84.metric_row(strategy_id, split, idx, hits[:, model_index, :],
                                  actual_rank[:, model_index, :], tests, family_kind="GLOBAL")
            metrics.append(item)
    if len(tests) != 36 or report["registered_test_family"]["tests"] != 36:
        raise ValueError("Q84-K: global Holm family is not exactly 36 tests")
    adjusted = q84.holm_adjust(tests)
    test_lookup = {x["test_id"]: x["p_raw"] for x in tests}
    report_lookup = {(x["strategy_id"], x["split"]): x for x in report["global_metrics"]}
    if len(report_lookup) != 12:
        raise ValueError("Q84-K: expected 12 method/split metric rows")
    for item in metrics:
        stored = report_lookup[(item["strategy_id"], item["split"])]
        for field in ("targets", "mean_hits_top5", "mean_hits_top10", "mean_hits_top20", "mean_rank_actual_numbers"):
            a, b = stored[field], item[field]
            if a is None or b is None:
                if a != b:
                    raise ValueError(f"Q84-K: metric mismatch {item['strategy_id']}/{item['split']}/{field}")
            elif not math.isclose(float(a), float(b), rel_tol=0, abs_tol=1e-12):
                raise ValueError(f"Q84-K: metric mismatch {item['strategy_id']}/{item['split']}/{field}")
        for endpoint, _ in sens.ENDPOINTS:
            test_id = f"GLOBAL|{item['strategy_id']}||{item['split']}|{endpoint}"
            if not math.isclose(float(stored["p_values_raw"][endpoint]), float(test_lookup[test_id]), rel_tol=0, abs_tol=1e-12):
                raise ValueError("Q84-K: raw p-value mismatch")
            if not math.isclose(float(stored["p_values_holm"][endpoint]), float(adjusted[test_id]), rel_tol=0, abs_tol=1e-12):
                raise ValueError("Q84-K: Holm p-value mismatch")

    # Selection must be reproducible from Discovery rows only.
    selected_k, selected_row = sens.select_k([r for r in report["global_metrics"] if r["split"] == "discovery"])
    if selected_k != report["selection"]["selected_k"] or selected_k != report["primary_gate"]["selected_k"]:
        raise ValueError("Q84-K: selected K does not reproduce from Discovery")
    selected_id = sens.FLOW_IDS[selected_k]
    blind_row = report_lookup[(selected_id, "blind_oos")]
    if not math.isclose(float(blind_row["mean_hits_top20"]), float(report["primary_gate"]["blind_mean_hits_top20"]), rel_tol=0, abs_tol=1e-12):
        raise ValueError("Q84-K: blind selection summary mismatch")

    # K=50, equal-weight and fixed-comparator metrics must reproduce the validated parent Q84 run.
    parent_rows = {(x["strategy_id"], x["split"]): x for x in base["global_metrics"]}
    parity_map = {
        sens.EQUAL_ID: "ENSEMBLE::EQUAL_WEIGHT_42",
        sens.FLOW_IDS[50]: "ENSEMBLE::FLOW_STATE_ADAPTIVE",
        sens.FIXED_MODEL_ID: sens.FIXED_ID
    }
    for new_id, old_id in parity_map.items():
        new_rows = ({(x["strategy_id"], x["split"]): x for x in report["global_metrics"]}
                    if new_id != sens.FIXED_MODEL_ID else
                    {(x["strategy_id"], x["split"]): x for x in report["fixed_comparator_metrics_descriptive_only"]})
        for split in sens.SPLITS:
            a = new_rows[(new_id, split)]
            b = parent_rows[(old_id, split)]
            for field in ("mean_hits_top5", "mean_hits_top10", "mean_hits_top20", "mean_rank_actual_numbers"):
                if not math.isclose(float(a[field]), float(b[field]), rel_tol=0, abs_tol=1e-12):
                    raise ValueError(f"Q84-K: parent Q84 parity failed for {new_id}/{split}/{field}")

    if manifest.get("source_archive_sha256") != archive_sha256 or manifest.get("target_count") != total:
        raise ValueError("Q84-K: manifest source/target mismatch")
    checks = {
        "canonical_draws": len(draws, ),
        "walk_forward_targets": total,
        "strict_prior_cutoffs": total,
        "ledger_rows": len(rows),
        "full_rank_vectors_reconciled": total * 5,
        "K_values": list(sens.K_VALUES),
        "K50_parent_parity_models": 3,
        "global_holm_family_tests": 36,
        "discovery_only_selection_reproduced": True,
        "fixed_comparator_excluded_from_inferential_family": True
    }
    validation = {
        "schema_version": "1.0", "task_id": "Q84-K-SENS", "status": "PASS",
        "validated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_archive_git_blob_sha1": archive_sha1, "source_archive_sha256": archive_sha256,
        "checks": checks,
        "guardrails": {"no_target_leakage": True, "blind_oos_not_used_for_selection": True,
                       "no_parent_q84_output_overwritten": True, "no_auto_promotion": True}
    }
    if write:
        json_dump(sens.VALIDATION, validation)
        report["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        report["validation_status"] = "EXPLORATORY_NOT_PROMOTABLE"
        report["acceptance_validation"] = {"status": "PASS", "validation_artifact": str(sens.VALIDATION.relative_to(ROOT))}
        json_dump(sens.REPORT, report)
        checkpoint = json.loads(sens.CHECKPOINT.read_text(encoding="utf-8"))
        checkpoint["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        checkpoint["validation_artifact"] = str(sens.VALIDATION.relative_to(ROOT))
        checkpoint["validation_checks"] = checks
        json_dump(sens.CHECKPOINT, checkpoint)
        manifest["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        file_specs = [
            ("protocol", sens.PROTOCOL, 1), ("catalog", sens.CATALOG, 5),
            ("target_ledger", sens.LEDGER, total), ("report", sens.REPORT, 1),
            ("checkpoint", sens.CHECKPOINT, 1), ("validation", sens.VALIDATION, 1)
        ]
        manifest["files"] = {
            key: {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                  "sha256": sha256(path), "rows": count}
            for key, path, count in file_specs
        }
        json_dump(sens.MANIFEST, manifest)
        # Re-read and verify the exact bytes described by the final manifest.
        final_manifest = json.loads(sens.MANIFEST.read_text(encoding="utf-8"))
        for item in final_manifest["files"].values():
            path = ROOT / item["path"]
            if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                raise ValueError("Q84-K: persisted-byte manifest readback failed: " + item["path"])
    return validation


def json_dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    result = validate(write=not args.no_write)
    print("SONAR_Q84_K_VALIDATION_BEGIN")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q84_K_VALIDATION_END")
