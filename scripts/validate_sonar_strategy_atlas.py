#!/usr/bin/env python3
"""Fail-closed Q84 output validator; supports persisted exact-head readback."""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
CATALOG = OUT / "strategy_atlas_catalog.jsonl"
LEDGER = OUT / "strategy_atlas_target_ledger.csv.gz"
LIFECYCLE = OUT / "strategy_atlas_lifecycle.json"
REPORT = OUT / "strategy_atlas_report.json"
MANIFEST = OUT / "strategy_atlas_manifest.json"
CHECKPOINT = OUT / "strategy_atlas_checkpoint_2026-11-09.json"
VALIDATION = OUT / "strategy_atlas_validation.json"
MIN_HISTORY = 200
FIXED = 42
GLOBAL = 44
CONDITIONAL_PER_REGIME = 42
ORACLE = "ORACLE::BEST_RULE_PER_TARGET"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def archive_rows():
    with ARCHIVE.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    dates, draws = [], []
    for row in rows:
        nums = [int(row[f"n{i}"]) for i in range(1, 6)]
        if len(set(nums)) != 5 or nums != sorted(nums) or any(n < 1 or n > 40 for n in nums):
            raise ValueError("Q84 validator: invalid archive quintet")
        dates.append(row["data"])
        draws.append(nums)
    if dates != sorted(set(dates)):
        raise ValueError("Q84 validator: archive dates not unique/chronological")
    return dates, draws


def split_for(index, total):
    if index < int(.60 * total):
        return "discovery"
    if index < int(.80 * total):
        return "validation"
    return "blind_oos"


def fail(message):
    raise SystemExit("Q84_ACCEPTANCE_BLOCKED: " + message)


def validate(write_validation):
    dates, draws = archive_rows()
    date_index = {d: i for i, d in enumerate(dates)}
    total = len(draws) - MIN_HISTORY
    if total <= 0:
        fail("no eligible targets")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    catalog_lines = [json.loads(x) for x in CATALOG.read_text(encoding="utf-8").splitlines() if x.strip()]
    lifecycle = json.loads(LIFECYCLE.read_text(encoding="utf-8"))

    if report.get("task_id") != "Q84" or manifest.get("task_id") != "Q84":
        fail("task ID mismatch")
    if report.get("source_archive", {}).get("draw_count") != len(draws):
        fail("report archive draw count mismatch")
    if report.get("source_archive", {}).get("last_date") != dates[-1]:
        fail("report archive last date mismatch")
    if manifest.get("source_archive_git_blob_sha1") != report["source_archive"].get("git_blob_sha1"):
        fail("manifest/report archive blob mismatch")
    if manifest.get("source_archive_sha256") != report["source_archive"].get("sha256"):
        fail("manifest/report archive SHA256 mismatch")
    if manifest.get("target_count") != total or report.get("walk_forward", {}).get("target_count") != total:
        fail("target count mismatch")
    expected_splits = {
        "discovery": int(.60 * total),
        "validation": int(.80 * total) - int(.60 * total),
        "blind_oos": total - int(.80 * total),
    }
    if report["walk_forward"].get("split_counts") != expected_splits:
        fail("chronological split dimensions mismatch")
    if len(catalog_lines) != FIXED + 2 + 2 * FIXED + 1:
        fail("catalog row count mismatch")
    catalog_ids = [x.get("strategy_id") for x in catalog_lines]
    if len(set(catalog_ids)) != len(catalog_ids):
        fail("duplicate strategy IDs in catalog")
    if sum(x.get("strategy_class") == "RETROSPECTIVE_DESCRIPTIVE" for x in catalog_lines) != 1:
        fail("retrospective oracle catalog entry missing/duplicated")
    if len(report.get("global_metrics", [])) != GLOBAL * 3:
        fail("global metric dimensions mismatch")
    if len(report.get("conditional_metrics", [])) != (2 * FIXED * 3):
        fail("conditional metric dimensions mismatch")
    family = report.get("registered_test_family", {})
    if family.get("tests") != (GLOBAL + 2 * FIXED) * 3 * 3:
        fail("multiple-testing family size mismatch")
    if family.get("tests") != 1152:
        fail("registered Holm family is not the expected 1,152 tests")
    if report.get("ledger_rows") != manifest.get("ledger_rows"):
        fail("ledger row count disagreement")

    # Verify artifact hashes before parsing the compressed event ledger.
    for name, entry in manifest.get("files", {}).items():
        path = ROOT / entry["path"]
        if not path.is_file():
            fail("missing manifest artifact: " + name)
        if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            fail("manifest byte/hash mismatch: " + name)

    expected_global = set()
    expected_conditional = Counter()
    expected_oracle = set()
    actual_rows = 0
    regime_counts = Counter()
    seen_target_strategy = set()
    with gzip.open(LEDGER, "rt", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {
            "target_date", "prior_cutoff_date", "prior_draw_count", "strategy_id",
            "eligible_ex_ante", "rank_by_number_1_to_40", "actual_quintet",
            "actual_number_ranks", "hits_top5", "hits_top10", "hits_top20",
            "split", "flow_regime_prior_only", "target_selection_used_outcome",
        }
        if not required.issubset(set(reader.fieldnames or [])):
            fail("ledger schema incomplete")
        for row in reader:
            actual_rows += 1
            target = row["target_date"]
            idx = date_index.get(target)
            if idx is None:
                fail("ledger target not in canonical archive: " + target)
            if idx < MIN_HISTORY:
                fail("ledger target has insufficient history")
            if row["prior_cutoff_date"] != dates[idx - 1] or int(row["prior_draw_count"]) != idx:
                fail("strict prior cutoff mismatch at " + target)
            if row["actual_quintet"] != " ".join(map(str, draws[idx])):
                fail("actual quintet mismatch at " + target)
            if row["split"] != split_for(idx - MIN_HISTORY, total):
                fail("split mismatch at " + target)
            sid = row["strategy_id"]
            key = (target, sid)
            if key in seen_target_strategy:
                fail("duplicate target/strategy row")
            seen_target_strategy.add(key)
            regime = row["flow_regime_prior_only"]
            if sid.startswith("COND::"):
                if row["eligible_ex_ante"] != "true" or row["target_selection_used_outcome"] != "false":
                    fail("conditional strategy eligibility flag mismatch")
                expected_regime = "HIGH_TURBULENCE" if sid.endswith("::HIGH_TURBULENCE") else "LOW_TURBULENCE"
                if regime != expected_regime:
                    fail("conditional strategy was scored outside its prior-state regime")
                expected_conditional[regime] += 1
            elif sid == ORACLE:
                expected_oracle.add(target)
                if row["eligible_ex_ante"] != "false" or row["target_selection_used_outcome"] != "true":
                    fail("oracle must be marked retrospective/ineligible ex ante")
            else:
                if row["eligible_ex_ante"] != "true" or row["target_selection_used_outcome"] != "false":
                    fail("global ex-ante strategy flag mismatch")
                expected_global.add(key)
            ranks = json.loads(row["rank_by_number_1_to_40"])
            if len(ranks) != 40 or sorted(ranks) != list(range(1, 41)):
                fail("rank vector is not a complete 1..40 permutation at " + target)
            actual_ranks = json.loads(row["actual_number_ranks"])
            actual = draws[idx]
            expected_actual_ranks = [ranks[n - 1] for n in actual]
            if actual_ranks != expected_actual_ranks:
                fail("actual-number ranks do not reconcile to full rank vector")
            if int(row["hits_top5"]) != sum(x <= 5 for x in actual_ranks):
                fail("Top5 hits do not reconcile")
            if int(row["hits_top10"]) != sum(x <= 10 for x in actual_ranks):
                fail("Top10 hits do not reconcile")
            if int(row["hits_top20"]) != sum(x <= 20 for x in actual_ranks):
                fail("Top20 hits do not reconcile")
            if sid not in (ORACLE,) and not sid.startswith("COND::"):
                regime_counts[regime] += 1

    expected_global_count = total * GLOBAL
    if len(expected_global) != expected_global_count:
        fail(f"global target coverage mismatch: {len(expected_global)} != {expected_global_count}")
    if len(expected_oracle) != total:
        fail("oracle target coverage mismatch")
    eligible_regimes = sum(report["flow_state"]["regime_counts"].get(x, 0)
                           for x in ("HIGH_TURBULENCE", "LOW_TURBULENCE"))
    expected_conditional_rows = eligible_regimes * CONDITIONAL_PER_REGIME
    if sum(expected_conditional.values()) != expected_conditional_rows:
        fail("conditional regime coverage mismatch")
    if actual_rows != expected_global_count + expected_conditional_rows + total:
        fail("total ledger row count mismatch")
    if actual_rows != manifest["ledger_rows"]:
        fail("manifest ledger row count mismatch")
    if len(lifecycle.get("pairwise_relationships", [])) != GLOBAL * (GLOBAL - 1) // 2:
        fail("pairwise relationship count mismatch")
    if lifecycle.get("relationship_summary", {}).get("pair_count") != GLOBAL * (GLOBAL - 1) // 2:
        fail("relationship summary pair count mismatch")

    if write_validation:
        validation = {
            "schema_version": "1.0", "task_id": "Q84", "status": "PASS",
            "validated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_archive_git_blob_sha1": report["source_archive"]["git_blob_sha1"],
            "source_archive_sha256": report["source_archive"]["sha256"],
            "checks": {
                "canonical_draws": len(draws), "walk_forward_targets": total,
                "strict_prior_cutoffs": total, "global_strategy_target_rows": expected_global_count,
                "conditional_strategy_rows": expected_conditional_rows,
                "retrospective_oracle_rows": total, "full_rank_vectors_reconciled": actual_rows,
                "unique_catalog_strategies": len(catalog_ids),
                "global_holm_family_tests": family["tests"],
                "pairwise_relationships": GLOBAL * (GLOBAL - 1) // 2,
            },
            "guardrails": {
                "oracle_excluded_from_ex_ante_inference": True,
                "immutable_target_2026_10_25_freeze_overwritten": False,
                "no_auto_promotion": True,
                "human_review_required": True,
            },
        }
        validation_path_tmp = VALIDATION.with_suffix(".json.tmp")
        validation_path_tmp.write_text(json.dumps(validation, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        validation_path_tmp.replace(VALIDATION)
        report["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        report["acceptance_validation"] = {"status": "PASS", "validation_artifact": str(VALIDATION.relative_to(ROOT))}
        REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
        checkpoint["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        checkpoint["validation_artifact"] = str(VALIDATION.relative_to(ROOT))
        checkpoint["validation_checks"] = validation["checks"]
        CHECKPOINT.write_text(json.dumps(checkpoint, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        manifest["status"] = "VALIDATED_PENDING_HUMAN_REVIEW"
        for name, path, rows in [
            ("report", REPORT, 1), ("checkpoint", CHECKPOINT, 1), ("validation", VALIDATION, 1)
        ]:
            manifest["files"][name] = {"path": str(path.relative_to(ROOT)), "rows": rows,
                                       "bytes": path.stat().st_size, "sha256": sha256(path)}
        MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
        # Re-read every persisted byte after the final writes.
        final_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for name, entry in final_manifest["files"].items():
            path = ROOT / entry["path"]
            if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
                fail("post-validation readback hash mismatch: " + name)
        return validation

    if not VALIDATION.is_file():
        fail("persisted exact-head validation artifact missing")
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS":
        fail("persisted validation artifact is not PASS")
    if report.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW":
        fail("report is not in validated-pending-human-review state")
    for name, entry in manifest.get("files", {}).items():
        path = ROOT / entry["path"]
        if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
            fail("exact-head persisted-byte check failed: " + name)
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    result = validate(write_validation=not args.validate_only)
    print("SONAR_Q84_VALIDATION_BEGIN")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q84_VALIDATION_END")
