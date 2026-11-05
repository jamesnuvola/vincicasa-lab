#!/usr/bin/env python3
"""Fail-closed acceptance validator for Q91 nested formula anticipation outputs."""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
import subprocess
from collections import deque
from pathlib import Path

import numpy as np

import sonar_per_number_condition_grammar as q80
import sonar_q91_nested_walkforward as q91

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
REPORT_PATH = OUT / "q91_nested_formula_walkforward.json"
METRICS_PATH = OUT / "q91_policy_metrics.csv"
LEDGER_PATH = OUT / "q91_target_ledger.csv"
CATALOG_PATH = OUT / "q91_formula_catalog.csv"
SELECTION_PATH = OUT / "q91_formula_selection_report.json"
SCORE_MANIFEST_PATH = OUT / "q91_formula_target_scores_manifest.json"
Q80_CHECKPOINT_PATH = OUT / "per_number_condition_research_checkpoint.json"
FORMULA_COUNT = 3303
MIN_HISTORY = 50
POLICY_IDS = tuple(q91.POLICY_IDS)
SPLITS = tuple(q91.SPLITS)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_error(errors, condition, message):
    if not condition:
        errors.append(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def parse_json_field(row, field, errors, target_date):
    try:
        value = json.loads(row[field])
        if not isinstance(value, dict):
            raise ValueError("expected JSON object")
        return value
    except Exception as exc:
        errors.append(f"Q91 invalid JSON field {field} at {target_date}: {exc}")
        return {}


def validate_outputs():
    errors = []
    required_paths = (
        REPORT_PATH, METRICS_PATH, LEDGER_PATH, CATALOG_PATH, SELECTION_PATH,
        SCORE_MANIFEST_PATH, Q80_CHECKPOINT_PATH,
    )
    missing = [str(p.relative_to(ROOT)) for p in required_paths if not p.is_file()]
    if missing:
        return ["Q91 missing required evidence: " + ", ".join(missing)]

    try:
        dates, draws = q80.load_archive()
        n = len(draws)
        scored_targets = n - MIN_HISTORY
        archive_blob_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD:data/storico_daily.csv"], cwd=ROOT, text=True
        ).strip()
        report = read_json(REPORT_PATH)
        checkpoint = read_json(Q80_CHECKPOINT_PATH)
        q80_archive_sha = checkpoint.get("archive_snapshot", {}).get("source_blob_sha")
        add_error(errors, q80_archive_sha == archive_blob_sha,
                  "Q91 Q80 checkpoint archive SHA differs from canonical archive")
        add_error(errors, report.get("task_id") == "Q91", "Q91 task ID mismatch")
        add_error(errors, report.get("status") in (
            "FORMULA_ENGINE_EXECUTED_PENDING_ACCEPTANCE_VALIDATION",
            "FORMULA_ACCEPTANCE_PASS_PENDING_ARTIFACT_READBACK_MAIN_CI_HUMAN_REVIEW",
            "VALIDATED_PENDING_HUMAN_REVIEW",
        ), "Q91 report status is not an allowed acceptance state")
        add_error(errors, report.get("review_status") == "PENDING_HUMAN_REVIEW_INTEGRATION",
                  "Q91 human-review gate missing")
        add_error(errors, report.get("archive", {}).get("blob_sha") == archive_blob_sha,
                  "Q91 archive blob SHA mismatch")
        add_error(errors, report.get("archive", {}).get("draw_count") == n,
                  "Q91 archive draw count mismatch")
        add_error(errors, report.get("archive", {}).get("first_date") == dates[0]
                  and report.get("archive", {}).get("last_date") == dates[-1],
                  "Q91 archive dates mismatch")
        add_error(errors, report.get("minimum_prior_history") == MIN_HISTORY,
                  "Q91 minimum prior history mismatch")
        add_error(errors, report.get("scored_targets") == scored_targets,
                  "Q91 scored target count mismatch")
        add_error(errors, report.get("formula_count") == FORMULA_COUNT
                  and report.get("formula_count_check") == FORMULA_COUNT,
                  "Q91 formula count mismatch")
        add_error(errors, report.get("formula_grammar") == "all 3,303 Q80 single/pair/triple equal-weight formulas",
                  "Q91 formula grammar label mismatch")
        add_error(errors, report.get("policy_count") == len(POLICY_IDS)
                  and report.get("policy_ids") == list(POLICY_IDS),
                  "Q91 policy schema mismatch")
        add_error(errors, report.get("cold_start_targets") == q91.COLD_START_TARGETS
                  and report.get("cold_start_formula_id") == q80.FORMULA_IDS[0],
                  "Q91 cold-start rule mismatch")
        expected_split_counts = {
            split: sum(q80.split_name(t, scored_targets) == split for t in range(scored_targets))
            for split in SPLITS
        }
        add_error(errors, report.get("split_target_counts") == expected_split_counts,
                  "Q91 chronological split counts mismatch")
        add_error(errors, report.get("metrics_rows") == len(POLICY_IDS) * len(SPLITS),
                  "Q91 policy metrics row count mismatch")
        add_error(errors, report.get("target_ledger_rows") == scored_targets,
                  "Q91 target ledger row count mismatch")
        add_error(errors, report.get("multiple_testing", {}).get("method") == "Holm-Bonferroni"
                  and report.get("multiple_testing", {}).get("test_count") == len(POLICY_IDS) * len(SPLITS) * 2,
                  "Q91 multiple-testing family size mismatch")

        expected_hashes = {
            "formula_catalog": CATALOG_PATH,
            "policy_metrics": METRICS_PATH,
            "target_ledger": LEDGER_PATH,
            "selection_report": SELECTION_PATH,
            "score_manifest": SCORE_MANIFEST_PATH,
        }
        hashes = report.get("output_sha256", {})
        for key, path in expected_hashes.items():
            add_error(errors, hashes.get(key) == sha256_file(path),
                      "Q91 output SHA mismatch: " + key)

        score_manifest = read_json(SCORE_MANIFEST_PATH)
        add_error(errors, report.get("formula_target_scores", {}).get("manifest_path")
                  == str(SCORE_MANIFEST_PATH.relative_to(ROOT)),
                  "Q91 score manifest path mismatch")
        add_error(errors, report.get("formula_target_scores", {}).get("manifest_sha256")
                  == sha256_file(SCORE_MANIFEST_PATH),
                  "Q91 score manifest SHA mismatch")
        add_error(errors, score_manifest.get("task_id") == "Q91"
                  and score_manifest.get("storage_format") == "chunked_npz",
                  "Q91 score manifest identity/storage mismatch")
        add_error(errors, score_manifest.get("archive_blob_sha") == archive_blob_sha,
                  "Q91 score manifest archive SHA mismatch")
        add_error(errors, score_manifest.get("formula_count") == FORMULA_COUNT
                  and score_manifest.get("scored_targets") == scored_targets
                  and score_manifest.get("rows") == scored_targets * FORMULA_COUNT,
                  "Q91 score manifest dimensions mismatch")
        parts = score_manifest.get("parts", [])
        parts_sha = hashlib.sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        add_error(errors, score_manifest.get("parts_manifest_sha256") == parts_sha
                  and report.get("formula_target_scores", {}).get("parts_manifest_sha256") == parts_sha,
                  "Q91 score parts manifest hash mismatch")
        add_error(errors, score_manifest.get("part_count") == len(parts)
                  and report.get("formula_target_scores", {}).get("part_count") == len(parts),
                  "Q91 score parts count mismatch")

        hits5_parts, rank_sum_parts, score_dates = [], [], []
        target_cursor = 0
        for part_index, part in enumerate(parts):
            rel = str(part.get("path", ""))
            path = ROOT / rel
            add_error(errors, part.get("part_index") == part_index,
                      "Q91 score part index/order mismatch")
            add_error(errors, int(part.get("target_start_inclusive", -1)) == target_cursor,
                      "Q91 score part target gap/overlap")
            if not path.is_file():
                errors.append("Q91 score part missing: " + rel)
                target_cursor += max(0, int(part.get("targets", 0)))
                continue
            raw_bytes = path.read_bytes()
            add_error(errors, len(raw_bytes) == int(part.get("bytes", -1)),
                      "Q91 score part byte count mismatch: " + rel)
            add_error(errors, hashlib.sha256(raw_bytes).hexdigest() == part.get("sha256"),
                      "Q91 score part SHA mismatch: " + rel)
            try:
                with np.load(path, allow_pickle=False) as z:
                    local_hits5 = z["hits5"]
                    local_rank_sum = z["rank_sum"]
                    local_dates = z["target_dates"].tolist()
                    local_start = int(z["target_start"].item())
                    local_end = int(z["target_end"].item())
                    local_formula_count = int(z["formula_count"].item())
                    local_archive_sha = str(z["archive_blob_sha"].item())
                expected_targets = int(part.get("targets", -1))
                add_error(errors, local_hits5.shape == (expected_targets, FORMULA_COUNT)
                          and local_rank_sum.shape == (expected_targets, FORMULA_COUNT),
                          "Q91 score part array shape mismatch: " + rel)
                add_error(errors, local_start == target_cursor
                          and local_end == target_cursor + expected_targets,
                          "Q91 score part embedded range mismatch: " + rel)
                add_error(errors, local_formula_count == FORMULA_COUNT
                          and local_archive_sha == archive_blob_sha,
                          "Q91 score part embedded provenance mismatch: " + rel)
                expected_dates = dates[MIN_HISTORY + target_cursor:MIN_HISTORY + target_cursor + expected_targets]
                add_error(errors, local_dates == expected_dates,
                          "Q91 score part target dates mismatch: " + rel)
                add_error(errors, int(part.get("target_end_exclusive", -1)) == local_end
                          and part.get("first_target_date") == expected_dates[0]
                          and part.get("last_target_date") == expected_dates[-1],
                          "Q91 score part manifest range/date mismatch: " + rel)
                if local_hits5.shape == (expected_targets, FORMULA_COUNT):
                    add_error(errors, np.all((local_hits5 >= 0) & (local_hits5 <= 5)),
                              "Q91 score part Top5 hit values out of range: " + rel)
                    add_error(errors, np.all((local_rank_sum >= 5) & (local_rank_sum <= 200)),
                              "Q91 score part rank sums out of range: " + rel)
                    hits5_parts.append(local_hits5.astype(np.uint8, copy=False))
                    rank_sum_parts.append(local_rank_sum.astype(np.uint16, copy=False))
                    score_dates.extend(local_dates)
            except Exception as exc:
                errors.append("Q91 cannot read score part " + rel + ": " + str(exc))
            target_cursor += int(part.get("targets", 0))
        add_error(errors, target_cursor == scored_targets,
                  "Q91 score parts do not cover all targets")
        add_error(errors, int(score_manifest.get("rows", -1)) == scored_targets * FORMULA_COUNT,
                  "Q91 score manifest row coverage mismatch")

        if len(hits5_parts) != len(parts) or len(rank_sum_parts) != len(parts):
            errors.append("Q91 score parts could not be fully materialized for validation")
            return errors
        all_hits5 = np.concatenate(hits5_parts, axis=0)
        all_rank_sum = np.concatenate(rank_sum_parts, axis=0)
        add_error(errors, all_hits5.shape == (scored_targets, FORMULA_COUNT)
                  and all_rank_sum.shape == (scored_targets, FORMULA_COUNT),
                  "Q91 combined score arrays shape mismatch")
        add_error(errors, score_dates == dates[MIN_HISTORY:],
                  "Q91 combined score date coverage mismatch")

        # Catalog is exact and ordered, not just count-reconciled.
        catalog_fields, catalog_rows = read_csv(CATALOG_PATH)
        required_catalog = {"formula_id", "feature_count", "features", "feature_indices"}
        add_error(errors, required_catalog.issubset(set(catalog_fields)),
                  "Q91 formula catalog schema incomplete")
        add_error(errors, len(catalog_rows) == FORMULA_COUNT,
                  "Q91 formula catalog row count mismatch")
        if len(catalog_rows) == FORMULA_COUNT:
            for index, row in enumerate(catalog_rows):
                cols = q80.FORMULAS[index]
                expected = {
                    "formula_id": q80.FORMULA_IDS[index],
                    "feature_count": str(len(cols)),
                    "features": "+".join(q80.FEATURE_NAMES[c] for c in cols),
                    "feature_indices": ";".join(str(c) for c in cols),
                }
                if any(row.get(key) != value for key, value in expected.items()):
                    errors.append("Q91 formula catalog mismatch at index " + str(index))
                    break

        # Chronology, prior-only formula choices, per-policy ranks and oracle consistency.
        ledger_fields, ledger_rows = read_csv(LEDGER_PATH)
        required_ledger = {
            "target_date", "cutoff_date", "prior_draws", "split", "actual_quintet",
            "cold_start_history_targets", "policy_formula_ids", "policy_actual_number_ranks",
            "policy_number_hits_top5", "policy_number_hits_top10", "policy_number_hits_top20",
            "policy_rank_sum", "policy_all5_top5_count", "policy_all5_top10_count",
            "policy_all5_top20_count", "oracle_best_formula_id", "oracle_actual_number_ranks",
            "oracle_number_hits_top5", "oracle_number_hits_top10", "oracle_number_hits_top20",
            "oracle_rank_sum", "frozen_policy_id", "frozen_policy_formula_id",
            "frozen_policy_actual_number_ranks", "frozen_policy_number_hits_top5",
            "frozen_policy_number_hits_top10", "frozen_policy_number_hits_top20",
            "frozen_policy_rank_sum", "frozen_policy_regret_rank_sum", "policy_selection_phase", "status",
        }
        add_error(errors, required_ledger.issubset(set(ledger_fields)),
                  "Q91 target ledger schema incomplete")
        add_error(errors, len(ledger_rows) == scored_targets,
                  "Q91 target ledger row count mismatch")
        expected_dates = dates[MIN_HISTORY:]
        add_error(errors, [row.get("target_date", "") for row in ledger_rows] == expected_dates,
                  "Q91 target ledger date coverage/order mismatch")

        formula_index = {formula_id: index for index, formula_id in enumerate(q80.FORMULA_IDS)}
        aggregate = {
            policy: {
                split: {
                    "targets": 0, "number_hits_top5": 0, "number_hits_top10": 0, "number_hits_top20": 0,
                    "all5_top5_count": 0, "all5_top10_count": 0, "all5_top20_count": 0, "rank_sum": 0,
                }
                for split in SPLITS
            }
            for policy in POLICY_IDS
        }
        cum_hits5 = np.zeros(FORMULA_COUNT, dtype=np.int32)
        cum_rank_sum = np.zeros(FORMULA_COUNT, dtype=np.int32)
        roll250_hits5 = np.zeros(FORMULA_COUNT, dtype=np.int32)
        roll250_rank_sum = np.zeros(FORMULA_COUNT, dtype=np.int32)
        roll500_hits5 = np.zeros(FORMULA_COUNT, dtype=np.int32)
        roll500_rank_sum = np.zeros(FORMULA_COUNT, dtype=np.int32)
        queue250, queue500 = deque(), deque()
        selected_policy = report.get("selected_policy_on_discovery")
        add_error(errors, selected_policy in POLICY_IDS,
                  "Q91 selected discovery policy is unknown")

        for target_index, row in enumerate(ledger_rows):
            target_date = expected_dates[target_index]
            archive_index = target_index + MIN_HISTORY
            expected_split = q80.split_name(target_index, scored_targets)
            expected_actual = " ".join(map(str, draws[archive_index]))
            add_error(errors, row.get("cutoff_date") == dates[archive_index - 1]
                      and int(row.get("prior_draws", -1)) == archive_index,
                      "Q91 strict-prior cutoff mismatch at " + target_date)
            add_error(errors, row.get("split") == expected_split
                      and row.get("actual_quintet") == expected_actual,
                      "Q91 target split/actual quintet mismatch at " + target_date)
            add_error(errors, int(row.get("cold_start_history_targets", -1)) == target_index,
                      "Q91 cold-start history count mismatch at " + target_date)
            add_error(errors, row.get("status") == "SCORED",
                      "Q91 target status invalid at " + target_date)
            add_error(errors, row.get("policy_selection_phase") == (
                "DISCOVERY_SELECTION" if expected_split == "discovery" else "FROZEN_POLICY_APPLIED"
            ), "Q91 policy selection phase mismatch at " + target_date)

            policy_formula_ids = parse_json_field(row, "policy_formula_ids", errors, target_date)
            policy_ranks = parse_json_field(row, "policy_actual_number_ranks", errors, target_date)
            policy_h5 = parse_json_field(row, "policy_number_hits_top5", errors, target_date)
            policy_h10 = parse_json_field(row, "policy_number_hits_top10", errors, target_date)
            policy_h20 = parse_json_field(row, "policy_number_hits_top20", errors, target_date)
            policy_rs = parse_json_field(row, "policy_rank_sum", errors, target_date)
            policy_a5 = parse_json_field(row, "policy_all5_top5_count", errors, target_date)
            policy_a10 = parse_json_field(row, "policy_all5_top10_count", errors, target_date)
            policy_a20 = parse_json_field(row, "policy_all5_top20_count", errors, target_date)
            for mapping, name in (
                (policy_formula_ids, "formula IDs"), (policy_ranks, "rank vectors"),
                (policy_h5, "Top5 hits"), (policy_h10, "Top10 hits"), (policy_h20, "Top20 hits"),
                (policy_rs, "rank sums"), (policy_a5, "all-five Top5"),
                (policy_a10, "all-five Top10"), (policy_a20, "all-five Top20"),
            ):
                add_error(errors, set(mapping) == set(POLICY_IDS),
                          "Q91 policy " + name + " keys mismatch at " + target_date)

            expected_policy_indices = {}
            for policy_id, window_name, objective in q91.POLICY_SPECS:
                if target_index < q91.COLD_START_TARGETS:
                    expected_index = 0
                elif window_name == "expanding":
                    expected_index = q91.select_formula(cum_hits5, cum_rank_sum, objective)
                elif window_name == "rolling250":
                    expected_index = q91.select_formula(roll250_hits5, roll250_rank_sum, objective)
                elif window_name == "rolling500":
                    expected_index = q91.select_formula(roll500_hits5, roll500_rank_sum, objective)
                else:
                    errors.append("Q91 unknown policy window " + window_name)
                    expected_index = 0
                expected_policy_indices[policy_id] = expected_index
                expected_formula_id = q80.FORMULA_IDS[expected_index]
                add_error(errors, policy_formula_ids.get(policy_id) == expected_formula_id,
                          "Q91 strict-prior formula selection mismatch for " + policy_id + " at " + target_date)

                ranks = policy_ranks.get(policy_id, [])
                if not isinstance(ranks, list) or len(ranks) != 5:
                    errors.append("Q91 invalid policy rank vector for " + policy_id + " at " + target_date)
                    continue
                try:
                    ranks = [int(value) for value in ranks]
                    if any(value < 1 or value > 40 for value in ranks):
                        raise ValueError("rank outside 1..40")
                    h5 = sum(value <= 5 for value in ranks)
                    h10 = sum(value <= 10 for value in ranks)
                    h20 = sum(value <= 20 for value in ranks)
                    rs = sum(ranks)
                    a5 = int(all(value <= 5 for value in ranks))
                    a10 = int(all(value <= 10 for value in ranks))
                    a20 = int(all(value <= 20 for value in ranks))
                    add_error(errors, int(policy_h5.get(policy_id, -1)) == h5
                              and int(policy_h10.get(policy_id, -1)) == h10
                              and int(policy_h20.get(policy_id, -1)) == h20
                              and int(policy_rs.get(policy_id, -1)) == rs
                              and int(policy_a5.get(policy_id, -1)) == a5
                              and int(policy_a10.get(policy_id, -1)) == a10
                              and int(policy_a20.get(policy_id, -1)) == a20,
                              "Q91 policy rank/hit ledger mismatch for " + policy_id + " at " + target_date)
                    formula_idx = expected_policy_indices[policy_id]
                    add_error(errors, int(all_hits5[target_index, formula_idx]) == h5
                              and int(all_rank_sum[target_index, formula_idx]) == rs,
                              "Q91 policy score-array mismatch for " + policy_id + " at " + target_date)
                    m = aggregate[policy_id][expected_split]
                    m["targets"] += 1
                    m["number_hits_top5"] += h5
                    m["number_hits_top10"] += h10
                    m["number_hits_top20"] += h20
                    m["all5_top5_count"] += a5
                    m["all5_top10_count"] += a10
                    m["all5_top20_count"] += a20
                    m["rank_sum"] += rs
                except Exception as exc:
                    errors.append("Q91 invalid policy rank vector for " + policy_id + " at " + target_date + ": " + str(exc))

            oracle_id = row.get("oracle_best_formula_id", "")
            oracle_idx = formula_index.get(oracle_id)
            if oracle_idx is None:
                errors.append("Q91 unknown oracle formula at " + target_date)
                oracle_idx = 0
            try:
                oracle_ranks = [int(value) for value in json.loads(row["oracle_actual_number_ranks"])]
                if len(oracle_ranks) != 5 or any(value < 1 or value > 40 for value in oracle_ranks):
                    raise ValueError("invalid oracle ranks")
                oracle_h5 = sum(value <= 5 for value in oracle_ranks)
                oracle_h10 = sum(value <= 10 for value in oracle_ranks)
                oracle_h20 = sum(value <= 20 for value in oracle_ranks)
                oracle_rs = sum(oracle_ranks)
                add_error(errors, int(row.get("oracle_number_hits_top5", -1)) == oracle_h5
                          and int(row.get("oracle_number_hits_top10", -1)) == oracle_h10
                          and int(row.get("oracle_number_hits_top20", -1)) == oracle_h20
                          and int(row.get("oracle_rank_sum", -1)) == oracle_rs,
                          "Q91 oracle rank/hit ledger mismatch at " + target_date)
                add_error(errors, int(all_hits5[target_index, oracle_idx]) == oracle_h5
                          and int(all_rank_sum[target_index, oracle_idx]) == oracle_rs,
                          "Q91 oracle score-array mismatch at " + target_date)
                add_error(errors, oracle_rs == int(np.min(all_rank_sum[target_index])),
                          "Q91 oracle does not attain minimum rank sum at " + target_date)
            except Exception as exc:
                errors.append("Q91 invalid oracle rank record at " + target_date + ": " + str(exc))

            if selected_policy in POLICY_IDS:
                frozen_id = policy_formula_ids.get(selected_policy, "")
                frozen_ranks = policy_ranks.get(selected_policy, [])
                try:
                    frozen_ranks = [int(value) for value in frozen_ranks]
                    frozen_rs = sum(frozen_ranks)
                    frozen_h5 = sum(value <= 5 for value in frozen_ranks)
                    frozen_h10 = sum(value <= 10 for value in frozen_ranks)
                    frozen_h20 = sum(value <= 20 for value in frozen_ranks)
                    regret = frozen_rs - int(row.get("oracle_rank_sum", -1))
                    add_error(errors, row.get("frozen_policy_id") == selected_policy
                              and row.get("frozen_policy_formula_id") == frozen_id
                              and json.loads(row.get("frozen_policy_actual_number_ranks", "[]")) == frozen_ranks
                              and int(row.get("frozen_policy_number_hits_top5", -1)) == frozen_h5
                              and int(row.get("frozen_policy_number_hits_top10", -1)) == frozen_h10
                              and int(row.get("frozen_policy_number_hits_top20", -1)) == frozen_h20
                              and int(row.get("frozen_policy_rank_sum", -1)) == frozen_rs
                              and int(row.get("frozen_policy_regret_rank_sum", -1)) == regret
                              and regret >= 0,
                              "Q91 frozen policy/oracle regret mismatch at " + target_date)
                except Exception as exc:
                    errors.append("Q91 invalid frozen policy record at " + target_date + ": " + str(exc))

            # Add current target outcomes only after all formula choices are checked.
            current_hits5 = all_hits5[target_index].astype(np.int32)
            current_rank_sum = all_rank_sum[target_index].astype(np.int32)
            cum_hits5 += current_hits5
            cum_rank_sum += current_rank_sum
            q91.update_window(queue250, roll250_hits5, roll250_rank_sum,
                              current_hits5.astype(np.uint8), current_rank_sum.astype(np.uint16), 250)
            q91.update_window(queue500, roll500_hits5, roll500_rank_sum,
                              current_hits5.astype(np.uint8), current_rank_sum.astype(np.uint16), 500)

        # Discovery-only meta-policy selection is recomputed from the target ledger.
        discovery_aggregates = {
            policy: {"hits5": 0, "rank_sum": 0, "targets": 0}
            for policy in POLICY_IDS
        }
        for row in ledger_rows:
            if row.get("split") != "discovery":
                continue
            h5 = json.loads(row["policy_number_hits_top5"])
            rs = json.loads(row["policy_rank_sum"])
            for policy in POLICY_IDS:
                discovery_aggregates[policy]["hits5"] += int(h5[policy])
                discovery_aggregates[policy]["rank_sum"] += int(rs[policy])
                discovery_aggregates[policy]["targets"] += 1
        discovery_policy_rank = sorted(
            POLICY_IDS,
            key=lambda policy: (
                -discovery_aggregates[policy]["hits5"] / max(1, 5 * discovery_aggregates[policy]["targets"]),
                discovery_aggregates[policy]["rank_sum"] / max(1, 5 * discovery_aggregates[policy]["targets"]),
                policy,
            ),
        )
        expected_selected_policy = discovery_policy_rank[0]
        add_error(errors, report.get("selected_policy_on_discovery") == expected_selected_policy,
                  "Q91 selected meta-policy is not the discovery-only optimum")

        # Reconcile policy metrics to the target ledger and recompute raw/Holm p-values.
        metric_fields, metric_rows = read_csv(METRICS_PATH)
        required_metrics = {
            "policy_id", "split", "targets", "number_hits_top5", "number_hits_top10", "number_hits_top20",
            "all5_top5_count", "all5_top10_count", "all5_top20_count", "rank_sum",
            "mean_number_hits_top5", "mean_number_hits_top10", "mean_number_hits_top20",
            "all5_top5_rate", "all5_top10_rate", "all5_top20_rate", "mean_rank_of_actual_numbers",
            "p_top5_upper", "p_rank_lower", "selected_on_discovery", "holm_p_max_endpoint_family",
        }
        add_error(errors, required_metrics.issubset(set(metric_fields)),
                  "Q91 policy metrics schema incomplete")
        add_error(errors, len(metric_rows) == len(POLICY_IDS) * len(SPLITS),
                  "Q91 policy metrics row count mismatch")
        metrics_by_key = {(row.get("policy_id"), row.get("split")): row for row in metric_rows}
        p_records = []
        for split in SPLITS:
            for policy in POLICY_IDS:
                key = (policy, split)
                row = metrics_by_key.get(key)
                if row is None:
                    errors.append("Q91 missing policy metrics row " + str(key))
                    continue
                m = aggregate[policy][split]
                targets = int(m["targets"])
                trials = 5 * targets
                expected_values = {
                    "targets": targets,
                    "number_hits_top5": m["number_hits_top5"],
                    "number_hits_top10": m["number_hits_top10"],
                    "number_hits_top20": m["number_hits_top20"],
                    "all5_top5_count": m["all5_top5_count"],
                    "all5_top10_count": m["all5_top10_count"],
                    "all5_top20_count": m["all5_top20_count"],
                    "rank_sum": m["rank_sum"],
                }
                for field, expected in expected_values.items():
                    add_error(errors, int(row.get(field, -1)) == int(expected),
                              "Q91 metrics count mismatch " + str(key) + "/" + field)
                rates = {
                    "mean_number_hits_top5": m["number_hits_top5"] / trials if trials else 0.0,
                    "mean_number_hits_top10": m["number_hits_top10"] / trials if trials else 0.0,
                    "mean_number_hits_top20": m["number_hits_top20"] / trials if trials else 0.0,
                    "all5_top5_rate": m["all5_top5_count"] / targets if targets else 0.0,
                    "all5_top10_rate": m["all5_top10_count"] / targets if targets else 0.0,
                    "all5_top20_rate": m["all5_top20_count"] / targets if targets else 0.0,
                    "mean_rank_of_actual_numbers": m["rank_sum"] / trials if trials else 0.0,
                }
                for field, expected in rates.items():
                    try:
                        value = float(row[field])
                    except Exception:
                        errors.append("Q91 nonnumeric metric " + str(key) + "/" + field)
                        continue
                    add_error(errors, math.isfinite(value) and abs(value - expected) <= 1e-12,
                              "Q91 metrics rate mismatch " + str(key) + "/" + field)
                expected_p5 = q91.upper_top5_hypergeometric_p(int(m["number_hits_top5"]), targets)
                expected_prank = q91.lower_mean_rank_p(int(m["rank_sum"]), targets)
                add_error(errors, abs(float(row.get("p_top5_upper", -1)) - expected_p5) <= 1e-12,
                          "Q91 Top5 raw p-value mismatch " + str(key))
                add_error(errors, abs(float(row.get("p_rank_lower", -1)) - expected_prank) <= 1e-12,
                          "Q91 rank raw p-value mismatch " + str(key))
                add_error(errors, (row.get("selected_on_discovery", "").lower() == "true")
                          == (policy == expected_selected_policy),
                          "Q91 selected-on-discovery flag mismatch " + str(key))
                p_records.append((key, "top5", expected_p5))
                p_records.append((key, "rank", expected_prank))

        adjusted = q91.holm_adjust([p for _, _, p in p_records])
        holm_by_key = {}
        for (key, endpoint, _), adj in zip(p_records, adjusted):
            holm_by_key[key] = max(holm_by_key.get(key, 0.0), adj)
        for key, expected in holm_by_key.items():
            row = metrics_by_key.get(key)
            if row is not None:
                add_error(errors, abs(float(row.get("holm_p_max_endpoint_family", -1)) - expected) <= 1e-12,
                          "Q91 Holm-adjusted p-value mismatch " + str(key))

        selection_report = read_json(SELECTION_PATH)
        add_error(errors, selection_report.get("task_id") == "Q91"
                  and selection_report.get("selected_policy_on_discovery") == expected_selected_policy,
                  "Q91 selection report identity/policy mismatch")
        add_error(errors, selection_report.get("cold_start_targets") == q91.COLD_START_TARGETS
                  and selection_report.get("cold_start_formula_id") == q80.FORMULA_IDS[0],
                  "Q91 selection report cold-start mismatch")
        add_error(errors, selection_report.get("policy_selection_rule") == report.get("policy_selection_rule"),
                  "Q91 selection rule mismatch")
        expected_specs = [{"policy_id": p, "window": w, "objective": o} for p, w, o in q91.POLICY_SPECS]
        add_error(errors, selection_report.get("policy_specs") == expected_specs,
                  "Q91 selection policy specifications mismatch")

        # Independent direct-loop recomputation at deterministic boundary samples.
        discovery_count = expected_split_counts["discovery"]
        validation_count = expected_split_counts["validation"]
        sample_targets = sorted(set(x for x in (
            0, q91.COLD_START_TARGETS, discovery_count - 1, discovery_count,
            discovery_count + validation_count - 1, discovery_count + validation_count,
            scored_targets - 1,
        ) if 0 <= x < scored_targets))
        prefix = np.zeros((n + 1, 40), dtype=np.int32)
        position_prefix = np.zeros((n + 1, 5, 40), dtype=np.int32)
        for i, draw in enumerate(draws):
            prefix[i + 1] = prefix[i]
            position_prefix[i + 1] = position_prefix[i]
            for pos, value in enumerate(draw):
                v = value - 1
                prefix[i + 1, v] += 1
                position_prefix[i + 1, pos, v] += 1
        for target_index in sample_targets:
            i = target_index + MIN_HISTORY
            occurrence_lists = [[] for _ in range(40)]
            gap_sum = np.zeros(40, dtype=np.float64)
            gap_sq_sum = np.zeros(40, dtype=np.float64)
            gap_n = np.zeros(40, dtype=np.float64)
            prior_pairs = np.zeros((40, 40), dtype=np.int32)
            for prior_index, prior_draw in enumerate(draws[:i]):
                for value in prior_draw:
                    v = value - 1
                    occurrence_lists[v].append(prior_index)
                    if len(occurrence_lists[v]) >= 2:
                        gap = prior_index - occurrence_lists[v][-2]
                        gap_sum[v] += gap
                        gap_sq_sum[v] += gap * gap
                        gap_n[v] += 1
                for a, b in itertools.combinations(prior_draw, 2):
                    prior_pairs[a - 1, b - 1] += 1
            raw = q80.feature_matrix(
                i, draws, prefix, position_prefix, prior_pairs, occurrence_lists,
                gap_sum, gap_sq_sum, gap_n
            )
            standardized = q80.zscore_columns(raw)
            actual_idx = np.asarray(draws[i], dtype=np.int16) - 1
            sample_hits5 = np.empty(FORMULA_COUNT, dtype=np.uint8)
            sample_rank_sum = np.empty(FORMULA_COUNT, dtype=np.uint16)
            for formula_index, cols in enumerate(q80.FORMULAS):
                scores = standardized[:, cols].mean(axis=1)
                order = np.lexsort((np.arange(40), -scores))
                rank = np.empty(40, dtype=np.int16)
                rank[order] = np.arange(1, 41, dtype=np.int16)
                actual_ranks = rank[actual_idx]
                sample_hits5[formula_index] = np.sum(actual_ranks <= 5)
                sample_rank_sum[formula_index] = np.sum(actual_ranks)
            add_error(errors, np.array_equal(sample_hits5, all_hits5[target_index]),
                      "Q91 direct score recomputation Top5 mismatch at target index " + str(target_index))
            add_error(errors, np.array_equal(sample_rank_sum, all_rank_sum[target_index]),
                      "Q91 direct score recomputation rank sum mismatch at target index " + str(target_index))

        if report.get("status") == "VALIDATED_PENDING_HUMAN_REVIEW":
            acceptance = report.get("acceptance", {})
            add_error(errors, acceptance.get("validator") == "Q91_FORMULA_ACCEPTANCE_PASS",
                      "Q91 acceptance checkpoint validator marker missing")
            add_error(errors, acceptance.get("human_review") == "PENDING_HUMAN_REVIEW_INTEGRATION",
                      "Q91 acceptance human-review gate missing")
        add_error(errors, checkpoint.get("task_id") == "Q91"
                  and checkpoint.get("archive_blob_sha") == archive_blob_sha
                  and checkpoint.get("draw_count") == n
                  and checkpoint.get("scored_targets") == scored_targets
                  and checkpoint.get("formula_count") == FORMULA_COUNT
                  and checkpoint.get("selected_policy_on_discovery") == expected_selected_policy,
                  "Q91 checkpoint dimensions/provenance mismatch")
        add_error(errors, checkpoint.get("metrics_sha256") == sha256_file(METRICS_PATH)
                  and checkpoint.get("target_ledger_sha256") == sha256_file(LEDGER_PATH)
                  and checkpoint.get("score_manifest_sha256") == sha256_file(SCORE_MANIFEST_PATH)
                  and checkpoint.get("score_parts_manifest_sha256") == parts_sha
                  and checkpoint.get("report_sha256") == sha256_file(REPORT_PATH),
                  "Q91 checkpoint artifact SHA mismatch")
        return errors
    except Exception as exc:
        errors.append("Q91 validator exception: " + str(exc))
        return errors


def main():
    errors = validate_outputs()
    if errors:
        print("Q91_FORMULA_ACCEPTANCE_BLOCKED")
        for error in errors:
            print("Q91_VALIDATOR_ERROR:", error)
        raise SystemExit(1)
    report = read_json(REPORT_PATH)
    score_manifest = read_json(SCORE_MANIFEST_PATH)
    checkpoint_path = OUT / f"q91_checkpoint_{report['archive']['last_date']}.json"
    checkpoint = read_json(checkpoint_path)
    print("Q91_FORMULA_ACCEPTANCE_PASS",
          FORMULA_COUNT, report["metrics_rows"], report["target_ledger_rows"],
          report["archive"]["blob_sha"], report["archive"]["last_date"],
          report["selected_policy_on_discovery"], score_manifest["parts_manifest_sha256"],
          checkpoint["report_sha256"])


if __name__ == "__main__":
    main()
