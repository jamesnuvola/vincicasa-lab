#!/usr/bin/env python3
"""Nested strict-prior walk-forward formula anticipation on the Q80 3,303-formula grammar.

At each target, six deterministic meta-policies select a formula using only outcomes
from earlier target draws. The policy itself is selected on discovery and frozen
through validation/blind OOS. Per-target oracle formulas are retained as descriptive
upper bounds, never as forecasts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import deque
from pathlib import Path

import numpy as np

import sonar_per_number_condition_grammar as q80

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
MIN_HISTORY = 50
COLD_START_TARGETS = 100
SCORE_CHUNK_TARGETS = 100
POLICY_SPECS = (
    ("EXPANDING_TOP5", "expanding", "top5"),
    ("EXPANDING_RANK", "expanding", "rank"),
    ("ROLLING250_TOP5", "rolling250", "top5"),
    ("ROLLING250_RANK", "rolling250", "rank"),
    ("ROLLING500_TOP5", "rolling500", "top5"),
    ("ROLLING500_RANK", "rolling500", "rank"),
)
POLICY_IDS = [x[0] for x in POLICY_SPECS]
SPLITS = ("discovery", "validation", "blind_oos")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def select_formula(sum_hits5: np.ndarray, sum_rank_sum: np.ndarray, objective: str) -> int:
    """Deterministic tie-break: objective, secondary endpoint, then catalog index."""
    if objective == "top5":
        best_hits = int(np.max(sum_hits5))
        candidates = np.flatnonzero(sum_hits5 == best_hits)
        best_rank = int(np.min(sum_rank_sum[candidates]))
        candidates = candidates[sum_rank_sum[candidates] == best_rank]
    elif objective == "rank":
        best_rank = int(np.min(sum_rank_sum))
        candidates = np.flatnonzero(sum_rank_sum == best_rank)
        best_hits = int(np.max(sum_hits5[candidates]))
        candidates = candidates[sum_hits5[candidates] == best_hits]
    else:
        raise ValueError("Q91_BLOCKED: unknown selection objective " + objective)
    return int(candidates[0])


def compute_target_formula_scores(standardized: np.ndarray, actual_idx: np.ndarray):
    """Rank all 40 numbers under each Q80 formula; return strict-prior target metrics."""
    formulas = q80.FORMULAS
    formula_count = len(formulas)
    scores = np.empty((40, formula_count), dtype=np.float64)
    cursor = 0
    for size in (1, 2, 3):
        group = np.asarray([cols for cols in formulas if len(cols) == size], dtype=np.int16)
        if len(group) == 0:
            continue
        group_scores = standardized[:, group].mean(axis=2)
        end = cursor + len(group)
        scores[:, cursor:end] = group_scores
        cursor = end
    if cursor != formula_count:
        raise ValueError(f"Q91_BLOCKED: formula score coverage {cursor} != {formula_count}")

    # Rows are number IDs in ascending order; stable descending argsort preserves
    # ascending-number tie breaks exactly as Q80.
    order = np.argsort(-scores, axis=0, kind="stable")
    ranks = np.empty(order.shape, dtype=np.int16)
    ranks[order, np.arange(formula_count)] = np.arange(1, 41, dtype=np.int16)[:, None]
    actual_ranks = ranks[actual_idx, :]
    hits5 = np.sum(actual_ranks <= 5, axis=0, dtype=np.int16).astype(np.uint8)
    hits10 = np.sum(actual_ranks <= 10, axis=0, dtype=np.int16).astype(np.uint8)
    hits20 = np.sum(actual_ranks <= 20, axis=0, dtype=np.int16).astype(np.uint8)
    rank_sum = np.sum(actual_ranks, axis=0, dtype=np.int32).astype(np.uint16)
    all5_top5 = np.all(actual_ranks <= 5, axis=0).astype(np.uint8)
    all5_top10 = np.all(actual_ranks <= 10, axis=0).astype(np.uint8)
    all5_top20 = np.all(actual_ranks <= 20, axis=0).astype(np.uint8)
    return actual_ranks, hits5, hits10, hits20, rank_sum, all5_top5, all5_top10, all5_top20


def oracle_formula_index(rank_sum: np.ndarray, hits5: np.ndarray, hits20: np.ndarray) -> int:
    """Q80 descriptive oracle tie-break: rank sum, Top20 hits, inverse Top5 hits, index."""
    best_rank = int(np.min(rank_sum))
    candidates = np.flatnonzero(rank_sum == best_rank)
    best_hits20 = int(np.min(hits20[candidates]))
    candidates = candidates[hits20[candidates] == best_hits20]
    best_hits5 = int(np.max(hits5[candidates]))
    candidates = candidates[hits5[candidates] == best_hits5]
    return int(candidates[0])


def update_window(queue, sum_hits5, sum_rank_sum, hits5, rank_sum, window):
    queue.append((hits5, rank_sum))
    sum_hits5 += hits5.astype(np.int32)
    sum_rank_sum += rank_sum.astype(np.int32)
    if len(queue) > window:
        old_hits5, old_rank_sum = queue.popleft()
        sum_hits5 -= old_hits5.astype(np.int32)
        sum_rank_sum -= old_rank_sum.astype(np.int32)


def upper_top5_hypergeometric_p(successes: int, targets: int) -> float:
    if targets <= 0:
        return 1.0
    mean_per_draw = 5.0 * (5.0 / 40.0)
    variance_per_draw = 5.0 * (5.0 / 40.0) * (1.0 - 5.0 / 40.0) * (40.0 - 5.0) / (40.0 - 1.0)
    z = (successes - 0.5 - targets * mean_per_draw) / math.sqrt(targets * variance_per_draw)
    return min(1.0, max(0.0, 0.5 * math.erfc(z / math.sqrt(2.0))))


def lower_mean_rank_p(rank_sum: int, targets: int) -> float:
    if targets <= 0:
        return 1.0
    mean_per_draw = 5.0 * 20.5
    variance_per_draw = 5.0 * 133.25 * (40.0 - 5.0) / (40.0 - 1.0)
    z = (rank_sum + 0.5 - targets * mean_per_draw) / math.sqrt(targets * variance_per_draw)
    return min(1.0, max(0.0, 0.5 * math.erfc(-z / math.sqrt(2.0))))


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: (p_values[i], i))
    adjusted = [1.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (m - rank) * p_values[index]))
        adjusted[index] = running
    return adjusted


def write_score_part(part_index, target_start, target_dates, hits5_rows, hits20_rows, rank_sum_rows, archive_blob_sha):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"q91_formula_target_scores_part_{part_index:02d}.npz"
    hits5 = np.stack(hits5_rows, axis=0).astype(np.uint8, copy=False)
    hits20 = np.stack(hits20_rows, axis=0).astype(np.uint8, copy=False)
    rank_sum = np.stack(rank_sum_rows, axis=0).astype(np.uint16, copy=False)
    with path.open("wb") as handle:
        np.savez_compressed(
            handle,
            hits5=hits5,
            hits20=hits20,
            rank_sum=rank_sum,
            target_dates=np.asarray(target_dates, dtype="U10"),
            target_start=np.asarray(target_start, dtype=np.int32),
            target_end=np.asarray(target_start + len(target_dates), dtype=np.int32),
            formula_count=np.asarray(len(q80.FORMULAS), dtype=np.int32),
            archive_blob_sha=np.asarray(archive_blob_sha, dtype="U40"),
        )
    return {
        "part_index": part_index,
        "path": str(path.relative_to(ROOT)),
        "target_start_inclusive": target_start,
        "target_end_exclusive": target_start + len(target_dates),
        "targets": len(target_dates),
        "rows": len(target_dates) * len(q80.FORMULAS),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "first_target_date": target_dates[0],
        "last_target_date": target_dates[-1],
    }


def main():
    dates, draws = q80.load_archive()
    n = len(draws)
    scored_targets = n - MIN_HISTORY
    if scored_targets <= COLD_START_TARGETS:
        raise SystemExit("Q91_BLOCKED: archive has insufficient scored targets for nested policy selection")

    archive_blob_sha = __import__("subprocess").check_output(
        ["git", "rev-parse", "HEAD:data/storico_daily.csv"], cwd=ROOT, text=True
    ).strip()
    q80_checkpoint_path = OUT / "per_number_condition_research_checkpoint.json"
    if not q80_checkpoint_path.is_file():
        raise SystemExit("Q91_BLOCKED: current Q80/Q86 research checkpoint is missing")
    q80_checkpoint = json.loads(q80_checkpoint_path.read_text(encoding="utf-8"))
    if q80_checkpoint.get("archive_snapshot", {}).get("source_blob_sha") != archive_blob_sha:
        raise SystemExit("Q91_BLOCKED: Q80 checkpoint archive SHA does not match canonical archive")

    prefix = np.zeros((n + 1, 40), dtype=np.int32)
    position_prefix = np.zeros((n + 1, 5, 40), dtype=np.int32)
    for i, draw in enumerate(draws):
        prefix[i + 1] = prefix[i]
        position_prefix[i + 1] = position_prefix[i]
        for pos, value in enumerate(draw):
            v = value - 1
            prefix[i + 1, v] += 1
            position_prefix[i + 1, pos, v] += 1

    prior_pairs = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    gap_sum = np.zeros(40, dtype=np.float64)
    gap_sq_sum = np.zeros(40, dtype=np.float64)
    gap_n = np.zeros(40, dtype=np.float64)

    formula_count = len(q80.FORMULAS)
    if formula_count != 3303 or len(q80.FORMULA_IDS) != formula_count:
        raise SystemExit("Q91_BLOCKED: Q80 formula catalog dimensions mismatch")

    acc = {
        policy: {
            split: {
                "targets": 0, "number_hits_top5": 0, "number_hits_top10": 0, "number_hits_top20": 0,
                "all5_top5_count": 0, "all5_top10_count": 0, "all5_top20_count": 0, "rank_sum": 0,
            }
            for split in SPLITS
        }
        for policy in POLICY_IDS
    }
    target_rows = []
    score_parts = []
    hits5_chunk, hits20_chunk, rank_sum_chunk, dates_chunk = [], [], [], []
    part_index = 0
    cum_hits5 = np.zeros(formula_count, dtype=np.int32)
    cum_rank_sum = np.zeros(formula_count, dtype=np.int32)
    roll250_hits5 = np.zeros(formula_count, dtype=np.int32)
    roll250_rank_sum = np.zeros(formula_count, dtype=np.int32)
    roll500_hits5 = np.zeros(formula_count, dtype=np.int32)
    roll500_rank_sum = np.zeros(formula_count, dtype=np.int32)
    queue250, queue500 = deque(), deque()
    discovery_targets = math.ceil(0.60 * scored_targets)
    frozen_policy_id = None

    for i, (target_date, actual) in enumerate(zip(dates, draws)):
        if i < MIN_HISTORY:
            # State is still accumulated below for the first scored target.
            pass
        else:
            target_index = i - MIN_HISTORY
            split = q80.split_name(target_index, scored_targets)
            raw = q80.feature_matrix(
                i, draws, prefix, position_prefix, prior_pairs, occurrence_lists,
                gap_sum, gap_sq_sum, gap_n
            )
            standardized = q80.zscore_columns(raw)
            actual_idx = np.asarray(actual, dtype=np.int16) - 1
            (actual_ranks, hits5, hits10, hits20, rank_sum,
             all5_top5, all5_top10, all5_top20) = compute_target_formula_scores(standardized, actual_idx)

            policy_formula_indices = {}
            for policy_id, window_name, objective in POLICY_SPECS:
                if target_index < COLD_START_TARGETS:
                    formula_index = 0  # registered cold-start fallback: Q80 freq_5
                elif window_name == "expanding":
                    formula_index = select_formula(cum_hits5, cum_rank_sum, objective)
                elif window_name == "rolling250":
                    formula_index = select_formula(roll250_hits5, roll250_rank_sum, objective)
                elif window_name == "rolling500":
                    formula_index = select_formula(roll500_hits5, roll500_rank_sum, objective)
                else:
                    raise ValueError("Q91_BLOCKED: unknown policy window " + window_name)
                policy_formula_indices[policy_id] = formula_index

            policy_formula_ids = {p: q80.FORMULA_IDS[idx] for p, idx in policy_formula_indices.items()}
            policy_actual_ranks = {p: actual_ranks[:, idx].astype(int).tolist() for p, idx in policy_formula_indices.items()}
            policy_hits5 = {p: int(hits5[idx]) for p, idx in policy_formula_indices.items()}
            policy_hits10 = {p: int(hits10[idx]) for p, idx in policy_formula_indices.items()}
            policy_hits20 = {p: int(hits20[idx]) for p, idx in policy_formula_indices.items()}
            policy_rank_sum = {p: int(rank_sum[idx]) for p, idx in policy_formula_indices.items()}
            policy_all5_top5 = {p: int(all5_top5[idx]) for p, idx in policy_formula_indices.items()}
            policy_all5_top10 = {p: int(all5_top10[idx]) for p, idx in policy_formula_indices.items()}
            policy_all5_top20 = {p: int(all5_top20[idx]) for p, idx in policy_formula_indices.items()}

            oracle_idx = oracle_formula_index(rank_sum, hits5, hits20)
            oracle_ranks = actual_ranks[:, oracle_idx].astype(int).tolist()
            oracle_rank_sum = int(rank_sum[oracle_idx])
            oracle_hits5 = int(hits5[oracle_idx])
            oracle_hits10 = int(hits10[oracle_idx])
            oracle_hits20 = int(hits20[oracle_idx])

            for policy_id in POLICY_IDS:
                m = acc[policy_id][split]
                m["targets"] += 1
                m["number_hits_top5"] += policy_hits5[policy_id]
                m["number_hits_top10"] += policy_hits10[policy_id]
                m["number_hits_top20"] += policy_hits20[policy_id]
                m["all5_top5_count"] += policy_all5_top5[policy_id]
                m["all5_top10_count"] += policy_all5_top10[policy_id]
                m["all5_top20_count"] += policy_all5_top20[policy_id]
                m["rank_sum"] += policy_rank_sum[policy_id]

            target_rows.append({
                "target_date": target_date,
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "split": split,
                "actual_quintet": " ".join(map(str, actual)),
                "cold_start_history_targets": target_index,
                "policy_formula_ids": json.dumps(policy_formula_ids, sort_keys=True, separators=(",", ":")),
                "policy_actual_number_ranks": json.dumps(policy_actual_ranks, sort_keys=True, separators=(",", ":")),
                "policy_number_hits_top5": json.dumps(policy_hits5, sort_keys=True, separators=(",", ":")),
                "policy_number_hits_top10": json.dumps(policy_hits10, sort_keys=True, separators=(",", ":")),
                "policy_number_hits_top20": json.dumps(policy_hits20, sort_keys=True, separators=(",", ":")),
                "policy_rank_sum": json.dumps(policy_rank_sum, sort_keys=True, separators=(",", ":")),
                "policy_all5_top5_count": json.dumps(policy_all5_top5, sort_keys=True, separators=(",", ":")),
                "policy_all5_top10_count": json.dumps(policy_all5_top10, sort_keys=True, separators=(",", ":")),
                "policy_all5_top20_count": json.dumps(policy_all5_top20, sort_keys=True, separators=(",", ":")),
                "oracle_best_formula_id": q80.FORMULA_IDS[oracle_idx],
                "oracle_best_formula_features": "+".join(q80.FEATURE_NAMES[c] for c in q80.FORMULAS[oracle_idx]),
                "oracle_actual_number_ranks": json.dumps(oracle_ranks, separators=(",", ":")),
                "oracle_number_hits_top5": oracle_hits5,
                "oracle_number_hits_top10": oracle_hits10,
                "oracle_number_hits_top20": oracle_hits20,
                "oracle_rank_sum": oracle_rank_sum,
                "frozen_policy_id": "",
                "frozen_policy_formula_id": "",
                "frozen_policy_actual_number_ranks": "",
                "frozen_policy_number_hits_top5": "",
                "frozen_policy_number_hits_top10": "",
                "frozen_policy_number_hits_top20": "",
                "frozen_policy_rank_sum": "",
                "frozen_policy_regret_rank_sum": "",
                "policy_selection_phase": "DISCOVERY_SELECTION" if split == "discovery" else "FROZEN_POLICY_APPLIED",
                "status": "SCORED",
            })

            hits5_chunk.append(hits5)
            hits20_chunk.append(hits20)
            rank_sum_chunk.append(rank_sum)
            dates_chunk.append(target_date)
            if len(hits5_chunk) == SCORE_CHUNK_TARGETS or target_index == scored_targets - 1:
                score_parts.append(write_score_part(
                    part_index, target_index - len(hits5_chunk) + 1, dates_chunk,
                    hits5_chunk, hits20_chunk, rank_sum_chunk, archive_blob_sha
                ))
                part_index += 1
                hits5_chunk, hits20_chunk, rank_sum_chunk, dates_chunk = [], [], [], []

            # The current target becomes historical only after its prediction/score is recorded.
            cum_hits5 += hits5.astype(np.int32)
            cum_rank_sum += rank_sum.astype(np.int32)
            update_window(queue250, roll250_hits5, roll250_rank_sum, hits5, rank_sum, 250)
            update_window(queue500, roll500_hits5, roll500_rank_sum, hits5, rank_sum, 500)

            if split == "discovery" and target_index == discovery_targets - 1:
                discovery_policy_rows = []
                for policy_id in POLICY_IDS:
                    m = acc[policy_id]["discovery"]
                    mean_top5 = m["number_hits_top5"] / max(1, 5 * m["targets"])
                    mean_rank = m["rank_sum"] / max(1, 5 * m["targets"])
                    discovery_policy_rows.append((policy_id, mean_top5, mean_rank, m["number_hits_top5"]))
                frozen_policy_id = sorted(
                    discovery_policy_rows, key=lambda x: (-x[1], x[2], x[0])
                )[0][0]

        # Update prior-only feature state after target i has been scored.
        for value in draws[i]:
            v = value - 1
            occurrence_lists[v].append(i)
            if len(occurrence_lists[v]) >= 2:
                gap = i - occurrence_lists[v][-2]
                gap_sum[v] += gap
                gap_sq_sum[v] += gap * gap
                gap_n[v] += 1
        if i < n - 1:
            for a, b in __import__("itertools").combinations(draws[i], 2):
                prior_pairs[a - 1, b - 1] += 1

    if frozen_policy_id is None:
        raise SystemExit("Q91_BLOCKED: discovery split did not freeze a policy")

    # The discovery-selected policy is backfilled descriptively for discovery rows;
    # its individual formula choice at each target was still based on earlier targets.
    for row in target_rows:
        ids = json.loads(row["policy_formula_ids"])
        ranks = json.loads(row["policy_actual_number_ranks"])
        h5 = json.loads(row["policy_number_hits_top5"])
        h10 = json.loads(row["policy_number_hits_top10"])
        h20 = json.loads(row["policy_number_hits_top20"])
        rs = json.loads(row["policy_rank_sum"])
        row["frozen_policy_id"] = frozen_policy_id
        row["frozen_policy_formula_id"] = ids[frozen_policy_id]
        row["frozen_policy_actual_number_ranks"] = json.dumps(ranks[frozen_policy_id], separators=(",", ":"))
        row["frozen_policy_number_hits_top5"] = h5[frozen_policy_id]
        row["frozen_policy_number_hits_top10"] = h10[frozen_policy_id]
        row["frozen_policy_number_hits_top20"] = h20[frozen_policy_id]
        row["frozen_policy_rank_sum"] = rs[frozen_policy_id]
        row["frozen_policy_regret_rank_sum"] = int(rs[frozen_policy_id]) - int(row["oracle_rank_sum"])

    policy_metric_rows = []
    p_records = []
    for split in SPLITS:
        for policy_id in POLICY_IDS:
            m = acc[policy_id][split]
            targets = int(m["targets"])
            trials = 5 * targets
            row = {
                "policy_id": policy_id,
                "split": split,
                "targets": targets,
                "number_hits_top5": int(m["number_hits_top5"]),
                "number_hits_top10": int(m["number_hits_top10"]),
                "number_hits_top20": int(m["number_hits_top20"]),
                "all5_top5_count": int(m["all5_top5_count"]),
                "all5_top10_count": int(m["all5_top10_count"]),
                "all5_top20_count": int(m["all5_top20_count"]),
                "rank_sum": int(m["rank_sum"]),
                "mean_number_hits_top5": m["number_hits_top5"] / trials if trials else 0.0,
                "mean_number_hits_top10": m["number_hits_top10"] / trials if trials else 0.0,
                "mean_number_hits_top20": m["number_hits_top20"] / trials if trials else 0.0,
                "all5_top5_rate": m["all5_top5_count"] / targets if targets else 0.0,
                "all5_top10_rate": m["all5_top10_count"] / targets if targets else 0.0,
                "all5_top20_rate": m["all5_top20_count"] / targets if targets else 0.0,
                "mean_rank_of_actual_numbers": m["rank_sum"] / trials if trials else 0.0,
                "p_top5_upper": upper_top5_hypergeometric_p(int(m["number_hits_top5"]), targets),
                "p_rank_lower": lower_mean_rank_p(int(m["rank_sum"]), targets),
                "selected_on_discovery": policy_id == frozen_policy_id,
            }
            policy_metric_rows.append(row)
            p_records.append((len(policy_metric_rows) - 1, row["p_top5_upper"]))
            p_records.append((len(policy_metric_rows) - 1, row["p_rank_lower"]))

    adjusted = holm_adjust([p for _, p in p_records])
    for (row_index, _), adj in zip(p_records, adjusted):
        row = policy_metric_rows[row_index]
        row["holm_p_max_endpoint_family"] = max(row.get("holm_p_max_endpoint_family", 0.0), adj)

    OUT.mkdir(parents=True, exist_ok=True)
    catalog_path = OUT / "q91_formula_catalog.csv"
    with catalog_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["formula_id", "feature_count", "features", "feature_indices"])
        writer.writeheader()
        for formula_id, cols in zip(q80.FORMULA_IDS, q80.FORMULAS):
            writer.writerow({
                "formula_id": formula_id,
                "feature_count": len(cols),
                "features": "+".join(q80.FEATURE_NAMES[c] for c in cols),
                "feature_indices": ";".join(str(c) for c in cols),
            })

    metrics_path = OUT / "q91_policy_metrics.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(policy_metric_rows[0].keys()))
        writer.writeheader()
        writer.writerows(policy_metric_rows)

    ledger_path = OUT / "q91_target_ledger.csv"
    with ledger_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(target_rows[0].keys()))
        writer.writeheader()
        writer.writerows(target_rows)

    score_parts_manifest_sha = hashlib.sha256(
        json.dumps(score_parts, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    score_manifest_path = OUT / "q91_formula_target_scores_manifest.json"
    score_manifest = {
        "schema_version": "1.0",
        "task_id": "Q91",
        "storage_format": "chunked_npz",
        "archive_blob_sha": archive_blob_sha,
        "formula_count": formula_count,
        "scored_targets": scored_targets,
        "rows": scored_targets * formula_count,
        "part_count": len(score_parts),
        "parts_manifest_sha256": score_parts_manifest_sha,
        "parts": score_parts,
        "guardrails": [
            "formula target scores use only strict-prior Q80 features",
            "each target's policy formula is selected only from earlier target outcomes",
            "cold start uses fixed Q80 freq_5 formula for the first 100 scored targets",
            "discovery selects the meta-policy; validation and blind OOS do not retune it",
            "per-target oracle is retrospective and descriptive only",
        ],
    }
    score_manifest_path.write_text(json.dumps(score_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    selection_report_path = OUT / "q91_formula_selection_report.json"
    selection_report = {
        "schema_version": "1.0",
        "task_id": "Q91",
        "selected_policy_on_discovery": frozen_policy_id,
        "policy_selection_rule": "maximize discovery mean number_hits_top5; tie-break by lower discovery mean rank; final tie-break by policy_id ascending",
        "policy_specs": [{"policy_id": p, "window": w, "objective": o} for p, w, o in POLICY_SPECS],
        "cold_start_targets": COLD_START_TARGETS,
        "cold_start_formula_id": q80.FORMULA_IDS[0],
        "discovery_policy_metrics": [
            {k: row[k] for k in ("policy_id", "targets", "mean_number_hits_top5", "mean_rank_of_actual_numbers", "selected_on_discovery")}
            for row in policy_metric_rows if row["split"] == "discovery"
        ],
        "frozen_policy_guardrails": [
            "policy selection is frozen at the discovery boundary",
            "validation and blind_oos update formula performance histories but do not change the selected meta-policy",
            "all formula selection decisions at target t use target outcomes with index < t",
            "no formula or meta-policy is automatically promoted",
        ],
    }
    selection_report_path.write_text(json.dumps(selection_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_path = OUT / "q91_nested_formula_walkforward.json"
    report = {
        "schema_version": "1.0",
        "task_id": "Q91",
        "status": "FORMULA_ENGINE_EXECUTED_PENDING_ACCEPTANCE_VALIDATION",
        "review_status": "PENDING_HUMAN_REVIEW_INTEGRATION",
        "archive": {
            "path": "data/storico_daily.csv",
            "blob_sha": archive_blob_sha,
            "draw_count": n,
            "first_date": dates[0],
            "last_date": dates[-1],
        },
        "minimum_prior_history": MIN_HISTORY,
        "scored_targets": scored_targets,
        "split_target_counts": {
            split: sum(q80.split_name(t, scored_targets) == split for t in range(scored_targets))
            for split in SPLITS
        },
        "formula_count": formula_count,
        "formula_count_check": 27 + math.comb(27, 2) + math.comb(27, 3),
        "formula_grammar": "all 3,303 Q80 single/pair/triple equal-weight formulas",
        "policy_count": len(POLICY_SPECS),
        "policy_ids": POLICY_IDS,
        "selected_policy_on_discovery": frozen_policy_id,
        "policy_selection_rule": selection_report["policy_selection_rule"],
        "cold_start_targets": COLD_START_TARGETS,
        "cold_start_formula_id": q80.FORMULA_IDS[0],
        "metrics_rows": len(policy_metric_rows),
        "target_ledger_rows": len(target_rows),
        "multiple_testing": {
            "method": "Holm-Bonferroni",
            "test_count": len(p_records),
            "adjustment_family": "all 6 meta-policies x 3 chronological splits x 2 endpoints (Top5 number hits and lower mean rank)",
            "p_value_method": "continuity-corrected finite-population normal approximation; exploratory",
        },
        "uniform_number_rank_baseline": {
            "mean_number_hits_top5": 0.125,
            "mean_number_hits_top10": 0.25,
            "mean_number_hits_top20": 0.5,
            "mean_rank_of_actual_numbers": 20.5,
        },
        "formula_target_scores": {
            "manifest_path": str(score_manifest_path.relative_to(ROOT)),
            "manifest_sha256": sha256_file(score_manifest_path),
            "parts_manifest_sha256": score_parts_manifest_sha,
            "part_count": len(score_parts),
            "rows": scored_targets * formula_count,
        },
        "output_sha256": {
            "formula_catalog": sha256_file(catalog_path),
            "policy_metrics": sha256_file(metrics_path),
            "target_ledger": sha256_file(ledger_path),
            "selection_report": sha256_file(selection_report_path),
            "score_manifest": sha256_file(score_manifest_path),
        },
        "outputs": {
            "formula_catalog": str(catalog_path.relative_to(ROOT)),
            "policy_metrics": str(metrics_path.relative_to(ROOT)),
            "target_ledger": str(ledger_path.relative_to(ROOT)),
            "selection_report": str(selection_report_path.relative_to(ROOT)),
            "report": str(report_path.relative_to(ROOT)),
            "checkpoint": str((OUT / f"q91_checkpoint_{dates[-1]}.json").relative_to(ROOT)),
        },
        "guardrails": [
            "Q80 features are strict-prior at every target",
            "meta-policy formula selection uses only outcomes of earlier target draws",
            "discovery selects the meta-policy; validation and blind OOS are held chronologically",
            "all six policy candidates are reported and Holm-corrected across policy x split x endpoint",
            "per-target oracle is retrospective descriptive upper bound, not a forecast",
            "immutable target-2026-10-25 freeze is untouched",
            "no formula or policy is automatically promoted",
        ],
        "pending": [
            "acceptance validator and exact output persistence/readback",
            "current-head CI and human review/integration",
            "interpret selected policy validation/blind results; do not promote if null",
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checkpoint_path = OUT / f"q91_checkpoint_{dates[-1]}.json"
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q91",
        "status": report["status"],
        "checkpoint_date": dates[-1],
        "archive_blob_sha": archive_blob_sha,
        "draw_count": n,
        "scored_targets": scored_targets,
        "formula_count": formula_count,
        "policy_count": len(POLICY_SPECS),
        "selected_policy_on_discovery": frozen_policy_id,
        "metrics_sha256": sha256_file(metrics_path),
        "target_ledger_sha256": sha256_file(ledger_path),
        "score_manifest_sha256": sha256_file(score_manifest_path),
        "score_parts_manifest_sha256": score_parts_manifest_sha,
        "report_sha256": sha256_file(report_path),
        "pending": report["pending"],
    }
    checkpoint_path.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("SONAR_Q91_SUMMARY_BEGIN")
    print(json.dumps({k: report[k] for k in (
        "task_id", "status", "archive", "scored_targets", "split_target_counts",
        "formula_count", "policy_count", "selected_policy_on_discovery", "metrics_rows",
        "target_ledger_rows", "multiple_testing", "formula_target_scores"
    )}, ensure_ascii=False, separators=(",", ":")))
    print("SONAR_Q91_SUMMARY_END")


if __name__ == "__main__":
    main()
