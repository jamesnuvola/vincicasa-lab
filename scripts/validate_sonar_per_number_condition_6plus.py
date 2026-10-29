#!/usr/bin/env python3
"""Fail-closed acceptance validation for Q86's distributed six-feature formula outputs."""
from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import os
import subprocess
from pathlib import Path

import sonar_per_number_condition_grammar as q80

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
REPORT = OUT / "per_number_condition_6plus_grammar.json"
CHECKPOINT = OUT / "per_number_condition_6plus_checkpoint.json"
LEDGER = OUT / "per_number_condition_6plus_target_ledger.csv"
FEATURE_NAMES = q80.FEATURE_NAMES
FEATURE_COUNT = len(FEATURE_NAMES)
FORMULA_SIZE = 6
FORMULA_COUNT = math.comb(FEATURE_COUNT, FORMULA_SIZE)
SPLITS = ("discovery", "validation", "blind_oos")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def formula_id(index: int, columns) -> str:
    return "P6_" + "_".join(f"{column:02d}" for column in columns)


def formula_features(columns) -> str:
    return "+".join(FEATURE_NAMES[column] for column in columns)


def rank_vector(raw: str):
    try:
        values = json.loads(raw)
    except Exception as exc:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: invalid rank-vector JSON: " + str(exc))
    if not isinstance(values, list) or len(values) != 5:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: expected five ranks")
    if any(not isinstance(value, int) or not 1 <= value <= 40 for value in values):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: rank outside 1..40")
    return values


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-persisted", action="store_true")
    args = parser.parse_args()

    if not REPORT.is_file() or not CHECKPOINT.is_file() or not LEDGER.is_file():
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: report/checkpoint/target ledger missing")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    dates, draws = q80.load_archive()
    target_count = len(draws)
    scored_targets = target_count - q80.MIN_HISTORY
    archive_sha = sha256(ARCHIVE)
    expected_splits = {
        split: sum(q80.split_name(offset, scored_targets) == split for offset in range(scored_targets))
        for split in SPLITS
    }

    expected = {
        "task_id": "Q86",
        "status": "VALIDATED_PENDING_HUMAN_REVIEW",
        "review_status": "PENDING_HUMAN_REVIEW_INTEGRATION",
        "source_archive_sha256": archive_sha,
        "target_count": target_count,
        "first_date": dates[0],
        "last_date": dates[-1],
        "latest_quintet": list(draws[-1]),
        "minimum_prior_history": q80.MIN_HISTORY,
        "scored_targets": scored_targets,
        "feature_count": FEATURE_COUNT,
        "formula_count": FORMULA_COUNT,
        "formula_count_check": math.comb(FEATURE_COUNT, FORMULA_SIZE),
        "metrics_rows": FORMULA_COUNT * len(SPLITS),
        "target_ledger_rows": scored_targets,
        "split_counts": expected_splits,
        "shard_count": 16,
    }
    for key, value in expected.items():
        if report.get(key) != value:
            raise SystemExit(f"Q86_ACCEPTANCE_BLOCKED: report {key}={report.get(key)!r}, expected {value!r}")
    if report.get("multiple_testing", {}).get("method") != "Holm-Bonferroni":
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: global Holm correction missing")
    if report.get("multiple_testing", {}).get("test_count") != FORMULA_COUNT * len(SPLITS) * 3:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: global formula×split×endpoint test count mismatch")
    if report.get("immutable_target_2026_10_25_freeze_overwritten", False):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: immutable freeze overwrite flag is true")
    if report.get("review_status") == "COMPLETE" or report.get("automatic_promotion", False):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: automatic completion/promotion is prohibited")

    formulas = list(itertools.combinations(range(FEATURE_COUNT), FORMULA_SIZE))
    if len(formulas) != FORMULA_COUNT or len(set(formulas)) != FORMULA_COUNT:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: formula enumeration is not complete/unique")
    manifest = report.get("outputs", {}).get("metrics_parts", [])
    if len(manifest) != 16:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: expected 16 persisted metrics parts")
    seen = {split: bytearray(FORMULA_COUNT) for split in SPLITS}
    row_count = 0
    manifest_ranges = []
    for part in manifest:
        path = ROOT / part.get("path", "")
        if not path.is_file():
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics part missing " + str(path))
        if sha256(path) != part.get("sha256") or path.stat().st_size != part.get("bytes"):
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics part checksum/byte count mismatch " + path.name)
        start = int(part.get("formula_start_inclusive", -1))
        end = int(part.get("formula_end_exclusive", -1))
        if start < 0 or end <= start or end > FORMULA_COUNT:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: invalid metrics part formula range")
        manifest_ranges.append((start, end))
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics part header missing")
            part_rows = 0
            for row in reader:
                try:
                    formula_index = int(row["formula_index"])
                    split = row["split"]
                    feature_count = int(row["feature_count"])
                    targets = int(row["targets"])
                    raw_ps = [float(row[key]) for key in ("p_top5_normal_approx", "p_top10_normal_approx", "p_top20_normal_approx")]
                    adj_ps = [float(row[key]) for key in ("holm_p_top5", "holm_p_top10", "holm_p_top20")]
                    holm_max = float(row["holm_p_max_endpoint_family"])
                    means = [float(row[key]) for key in ("mean_number_hits_top5", "mean_number_hits_top10", "mean_number_hits_top20")]
                    mean_rank = float(row["mean_rank_of_actual_numbers"])
                except Exception as exc:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: malformed final metrics row: " + str(exc))
                if split not in SPLITS or not start <= formula_index < end:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics row outside its split/part range")
                if feature_count != FORMULA_SIZE or targets != expected_splits[split]:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics feature/target count mismatch")
                columns = formulas[formula_index]
                if row["formula_id"] != formula_id(formula_index, columns) or row["features"] != formula_features(columns):
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: formula index/ID/features do not reconcile")
                if seen[split][formula_index]:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: duplicate formula×split metrics row")
                seen[split][formula_index] = 1
                if any(not math.isfinite(value) or not 0 <= value <= 1 for value in raw_ps + adj_ps + [holm_max]):
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: invalid raw/adjusted p-value")
                if any(adj < raw for adj, raw in zip(adj_ps, raw_ps)):
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: Holm-adjusted p-value below raw p-value")
                if abs(holm_max - max(adj_ps)) > 1e-12:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: endpoint-family maximum mismatch")
                if any(not math.isfinite(value) or not 0 <= value <= 1 for value in means):
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: mean hit rate outside [0,1]")
                if not math.isfinite(mean_rank) or not 1 <= mean_rank <= 40:
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: mean rank outside [1,40]")
                row_count += 1
                part_rows += 1
            if part_rows != int(part.get("rows", -1)):
                raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics part row count differs from manifest")
    if sorted(manifest_ranges) != sorted([
        (FORMULA_COUNT * i // 16, FORMULA_COUNT * (i + 1) // 16) for i in range(16)
    ]):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: metrics part ranges do not partition formula universe")
    if row_count != FORMULA_COUNT * len(SPLITS) or any(sum(values) != FORMULA_COUNT for values in seen.values()):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: global metrics row coverage mismatch")

    ledger_meta = report.get("outputs", {}).get("target_ledger", {})
    if sha256(LEDGER) != ledger_meta.get("sha256") or LEDGER.stat().st_size != ledger_meta.get("bytes"):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target ledger checksum/bytes mismatch")
    with LEDGER.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target ledger header missing")
        rows = list(reader)
    if len(rows) != scored_targets or len(rows) != int(ledger_meta.get("rows", -1)):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target ledger row count mismatch")
    archive_index = {date: index for index, date in enumerate(dates)}
    if [row.get("target_date") for row in rows] != dates[q80.MIN_HISTORY:]:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target ledger date coverage/order mismatch")
    for row in rows:
        target_index = archive_index[row["target_date"]]
        if row.get("cutoff_date") != dates[target_index - 1] or int(row.get("prior_draws", "-1")) != target_index:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target cutoff/prior draw count mismatch")
        if row.get("actual_quintet") != " ".join(map(str, draws[target_index])):
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: actual quintet does not reconcile to archive")
        if row.get("status") != "SCORED" or int(row.get("formula_count_tested", "-1")) != FORMULA_COUNT:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: target status/formula count mismatch")
        formula_index = int(row["best_formula_index"])
        if not 0 <= formula_index < FORMULA_COUNT:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: best formula index outside universe")
        columns = formulas[formula_index]
        if row.get("best_formula_id") != formula_id(formula_index, columns) or row.get("best_formula_features") != formula_features(columns):
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: best formula ID/features mismatch")
        ranks = rank_vector(row["best_actual_number_ranks"])
        if int(row["best_rank_sum"]) != sum(ranks):
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: best rank sum mismatch")
        for key, threshold in (("best_number_hits_top5", 5), ("best_number_hits_top10", 10), ("best_number_hits_top20", 20)):
            if int(row[key]) != sum(value <= threshold for value in ranks):
                raise SystemExit("Q86_ACCEPTANCE_BLOCKED: best rank hit count mismatch")
        try:
            single = json.loads(row["single_feature_rank_ledger"])
        except Exception as exc:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: single-feature rank ledger JSON invalid: " + str(exc))
        if len(single) != FEATURE_COUNT:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: single-feature rank ledger width mismatch")
        for column, item in enumerate(single):
            if item.get("feature") != FEATURE_NAMES[column]:
                raise SystemExit("Q86_ACCEPTANCE_BLOCKED: single-feature order mismatch")
            values = rank_vector(json.dumps(item.get("ranks", [])))
            if int(item.get("rank_sum", -1)) != sum(values):
                raise SystemExit("Q86_ACCEPTANCE_BLOCKED: single-feature rank sum mismatch")
            for key, threshold in (("hits_top5", 5), ("hits_top10", 10), ("hits_top20", 20)):
                if int(item.get(key, -1)) != sum(value <= threshold for value in values):
                    raise SystemExit("Q86_ACCEPTANCE_BLOCKED: single-feature hit count mismatch")

    if checkpoint.get("task_id") != "Q86" or checkpoint.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW":
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint status/task mismatch")
    if checkpoint.get("archive_snapshot", {}).get("source_sha256") != archive_sha:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint archive hash mismatch")
    if checkpoint.get("archive_snapshot", {}).get("immutable_target_2026_10_25_freeze_overwritten") is not False:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint freeze guardrail missing")
    if checkpoint.get("validation", {}).get("human_review_required") is not True or checkpoint.get("validation", {}).get("automatic_promotion") is not False:
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint human-review/promotion guardrail missing")
    if checkpoint.get("outputs", {}).get("report_sha256") != sha256(REPORT):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint report checksum mismatch")
    if checkpoint.get("outputs", {}).get("target_ledger_sha256") != sha256(LEDGER):
        raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkpoint target-ledger checksum mismatch")
    if args.require_persisted:
        if checkpoint.get("validation", {}).get("persisted_bytes_verified") is not True:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: persisted byte verification not recorded")
        expected_head = os.environ.get("GITHUB_SHA")
        actual_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
        if expected_head and expected_head != actual_head:
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: checkout SHA differs from workflow head SHA")
        if checkpoint.get("validation", {}).get("exact_head_ci_status") not in ("PENDING", "PASS"):
            raise SystemExit("Q86_ACCEPTANCE_BLOCKED: exact-head CI status field invalid")

    print("Q86_ACCEPTANCE_VALIDATED " + json.dumps({
        "task_id": "Q86",
        "archive_cutoff": dates[-1],
        "target_count": target_count,
        "scored_targets": scored_targets,
        "formula_count": FORMULA_COUNT,
        "metrics_rows": row_count,
        "target_ledger_rows": len(rows),
        "split_counts": expected_splits,
        "holm_test_count": FORMULA_COUNT * len(SPLITS) * 3,
        "persisted_bytes_required": args.require_persisted,
        "human_review_required": True,
        "automatic_promotion": False,
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
