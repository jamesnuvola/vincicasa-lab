#!/usr/bin/env python3
"""Q141-A4/B8: import Q7 quintet formulas as typed ASTs and test complexity association."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path

import numpy as np

TASK_IMPORT = "Q141-A4"
TASK_TEST = "Q141-B8"
Q7_COMMIT = "7a37cab601c5f9386131a00246963f8e4aeabf74"
Q7_ARCHIVE_BLOB = "7dab05ba49ace909fe8783eef729605049c65e50"
Q7_CATALOG_MANIFEST_BLOB = "5cdf9c24431ea23b2176aa6a19133b7f4435980c"
Q7_WF_MANIFEST_BLOB = "aae2c7768c9d37bf633a13939f2b686bcce83a27"
Q7_RUNNER_BLOB = "ad1c7fa721f316b3af0018f5da4a0a905bb62dcf"
Q141_ARCHIVE_BLOB = "fcb453ed06c8002314f826dbac79d6935f9ac103"
DRAW_COUNT = 3387
CANDIDATES = 658008
FORMULAS = 1023
WINDOW = 100
ELIGIBLE = 3286
SPLITS = {"discovery": 1972, "validation": 657, "blind_oos": 657}
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261120
PRIMARY_MARGIN = 0.02
OUT_NAMES = {
    "ast": "q7_typed_ast_catalog_part_00.jsonl.gz",
    "snapshot": "q7_typed_ast_snapshot_2026-10-25.jsonl.gz",
    "import_report": "q7_typed_ast_import_report_2026-11-12.json",
    "complexity_report": "q7_formula_complexity_walkforward_report_2026-11-12.json",
    "ledger": "q7_formula_complexity_walkforward_target_ledger_2026-11-12.csv",
    "manifest": "q141_q7_ast_complexity_manifest_2026-11-12.json",
    "checkpoint": "q141_q7_ast_complexity_checkpoint_2026-11-12.json",
}

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return git_blob_sha1_bytes(data)

def read_archive(path: Path):
    from datetime import date
    rows, seen, previous = [], set(), ""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None or [x.strip().lower() for x in header[:6]] not in (
            ["data", "n1", "n2", "n3", "n4", "n5"],
            ["date", "n1", "n2", "n3", "n4", "n5"],
        ):
            raise RuntimeError(f"unexpected archive header: {header}")
        for line, row in enumerate(reader, 2):
            if not row or not any(x.strip() for x in row):
                continue
            if len(row) < 6:
                raise RuntimeError(f"malformed archive row {line}")
            day = row[0].strip()
            try:
                date.fromisoformat(day)
                nums = tuple(int(x) for x in row[1:6])
            except Exception as exc:
                raise RuntimeError(f"invalid archive row {line}: {exc}") from exc
            if day in seen or (previous and day <= previous):
                raise RuntimeError(f"duplicate/nonchronological date {day}")
            validate_quintet(nums)
            seen.add(day)
            previous = day
            rows.append((day, nums))
    return rows

def validate_quintet(nums):
    if len(nums) != 5 or len(set(nums)) != 5 or tuple(sorted(nums)) != tuple(nums):
        raise ValueError(f"invalid sorted distinct quintet: {nums}")
    if any(int(x) < 1 or int(x) > 40 for x in nums):
        raise ValueError(f"quintet outside 1..40: {nums}")

def formula_ast(mask: int, families: list[dict], manifest: dict) -> dict:
    if mask < 1 or mask > FORMULAS:
        raise ValueError("formula mask outside Q7 grammar")
    terms = []
    for bit, family in enumerate(families):
        if mask & (1 << bit):
            terms.append({
                "op": "z_normalized_feature_score",
                "feature_ref": {"namespace": "Q7", "feature_id": family["name"]},
                "definition": family["definition"],
                "smoothing": {
                    "method": manifest["smoothing"]["method"],
                    "alpha_numerator": 1,
                    "alpha_denominator": 2,
                },
                "normalization": "zscore_across_all_658008_candidate_quintets_for_this_target",
            })
    return {
        "schema_version": "1.0",
        "output_type": "quintet_score",
        "candidate_universe": {
            "n": 40,
            "k": 5,
            "size": CANDIDATES,
            "definition": "all sorted distinct 5-number subsets of 1..40",
            "ordering": "lexicographic",
        },
        "aggregation": {
            "op": "sum",
            "weight_per_term": 1,
            "weighting": "equal_weight_sum_of_selected_standardized_family_scores",
        },
        "terms": terms,
    }

def canonical_ast_id(ast: dict) -> str:
    raw = json.dumps(ast, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "Q7AST1-" + sha256_bytes(raw)

def load_formula_catalog(q7_root: Path):
    base = q7_root / "reports/sequence_agent"
    manifest_path = base / "exhaustive_formula_catalog_manifest.json"
    if git_blob_sha1(manifest_path) != Q7_CATALOG_MANIFEST_BLOB:
        raise RuntimeError("Q7 formula catalog manifest Git blob mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("formula_count") != FORMULAS or manifest.get("candidate_universe_size") != CANDIDATES:
        raise RuntimeError("Q7 catalog dimensions mismatch")
    if manifest.get("history_draws") != DRAW_COUNT or manifest.get("history_last_date") != "2026-10-24":
        raise RuntimeError("Q7 catalog source window mismatch")
    families = manifest.get("feature_families", [])
    if len(families) != 10 or len({x.get("name") for x in families}) != 10:
        raise RuntimeError("Q7 feature-family definitions are incomplete or duplicated")
    if manifest.get("smoothing", {}).get("alpha") != 0.5:
        raise RuntimeError("unexpected Q7 smoothing alpha")
    paths = sorted((base / "exhaustive_formula_catalog").glob("formulas_*.json"))
    if len(paths) != 11:
        raise RuntimeError(f"expected 11 Q7 formula catalog parts, found {len(paths)}")
    records, snapshots, seen_masks, seen_ids = [], [], set(), set()
    for path in paths:
        part = json.loads(path.read_text(encoding="utf-8"))
        if part.get("formula_count") != FORMULAS or part.get("part_count") != 11:
            raise RuntimeError(f"catalog part metadata mismatch: {path.name}")
        for item in part.get("formulas", []):
            mask = int(item["formula_mask"])
            expected_features = [families[b]["name"] for b in range(10) if mask & (1 << b)]
            if item.get("formula_id") != f"F{mask:04d}" or item.get("features") != expected_features:
                raise RuntimeError(f"formula mask/feature lineage mismatch: {mask}")
            if mask in seen_masks or item["formula_id"] in seen_ids:
                raise RuntimeError(f"duplicate Q7 source formula: {mask}")
            if int(item.get("feature_count", -1)) != len(expected_features):
                raise RuntimeError(f"feature count mismatch for mask {mask}")
            top20 = item.get("top20", [])
            if len(top20) != 20:
                raise RuntimeError(f"Q7 source top20 missing for formula {mask}")
            for candidate in top20:
                validate_quintet(tuple(int(x) for x in candidate["numbers"]))
                if not math.isfinite(float(candidate["score"])):
                    raise RuntimeError(f"non-finite Q7 top20 score for formula {mask}")
            ast = formula_ast(mask, families, manifest)
            ast_id = canonical_ast_id(ast)
            records.append({
                "schema_version": "1.0",
                "ast_id": ast_id,
                "source_formula_id": item["formula_id"],
                "source_formula_mask": mask,
                "feature_count": len(expected_features),
                "output_type": "quintet_score",
                "canonical_ast": ast,
                "source_lineage": {
                    "repository": "jamesnuvola/vincicasa-lab",
                    "source_commit": Q7_COMMIT,
                    "source_catalog_manifest_blob_sha1": Q7_CATALOG_MANIFEST_BLOB,
                    "source_archive_blob_sha1": Q7_ARCHIVE_BLOB,
                    "source_history_draws": DRAW_COUNT,
                    "source_cutoff": "2026-10-24",
                },
            })
            snapshots.append({
                "source_formula_id": item["formula_id"],
                "source_formula_mask": mask,
                "target_date": manifest["target_date"],
                "target_cutoff_date": manifest["target_cutoff_date"],
                "top20": item["top20"],
            })
            seen_masks.add(mask)
            seen_ids.add(item["formula_id"])
    if seen_masks != set(range(1, FORMULAS + 1)) or len(records) != FORMULAS:
        raise RuntimeError("Q7 formula universe is incomplete")
    ast_ids = [x["ast_id"] for x in records]
    if len(set(ast_ids)) != FORMULAS:
        raise RuntimeError("Q7 canonical AST IDs are not unique")
    return manifest, records, snapshots

def assert_runner_strict_prior_order(source: str):
    loop = source.find("for i in range(start_index, end_index):")
    if loop < 0:
        raise RuntimeError("pinned Q7 runner loop not found")
    score = source.find("ranks = ranks_for_actual(standardized, actual_index)", loop)
    write = source.find("writer.writerow(row)", loop)
    update = source.find("add_draw(state, draw)", write)
    if not (loop < score < write < update):
        raise RuntimeError("Q7 runner does not score/write the target before adding it to state")
    return {"loop_offset": loop, "score_offset": score, "write_offset": write, "state_update_offset": update}

def average_ranks(values):
    x = np.asarray(values)
    order = np.argsort(x, kind="mergesort")
    ranks = np.empty(len(x), dtype=np.float64)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and x[order[j]] == x[order[i]]:
            j += 1
        ranks[order[i:j]] = ((i + 1) + j) / 2.0
        i = j
    return ranks

def spearman_from_values(x, y):
    rx, ry = average_ranks(x), average_ranks(y)
    dx, dy = rx - rx.mean(), ry - ry.mean()
    denom = math.sqrt(float(np.dot(dx, dx) * np.dot(dy, dy)))
    return float(np.dot(dx, dy) / denom) if denom else 0.0

def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    out = [1.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * float(p_values[i])))
        out[i] = running
    return out

def block_signflip_p(values, threshold=0.0, block_length=BLOCK_LENGTH, replicates=REPLICATES, seed=SEED):
    x = np.asarray(values, dtype=np.float64) - float(threshold)
    if x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x)):
        raise ValueError("invalid paired series for block sign-flip")
    blocks = np.asarray([x[i:i + block_length].sum() for i in range(0, len(x), block_length)])
    observed = float(x.mean())
    k = len(blocks)
    if k <= 16:
        signs = np.asarray(list(itertools.product((-1.0, 1.0), repeat=k)))
        null = signs @ blocks / len(x)
        return float(np.mean(null >= observed - 1e-15)), k, f"exact_{2**k}_block_sign_flips"
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.asarray([-1.0, 1.0]), size=(replicates, k))
    null = signs @ blocks / len(x)
    return float((1 + np.count_nonzero(null >= observed - 1e-15)) / (replicates + 1)), k, f"monte_carlo_{replicates}_block_sign_flips"

def moving_block_ci(values, block_length=BLOCK_LENGTH, replicates=REPLICATES, seed=SEED):
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    if x.ndim != 1 or n < 2 or not np.all(np.isfinite(x)):
        raise ValueError("invalid paired series for moving-block bootstrap")
    rng = np.random.default_rng(seed)
    samples = np.empty(replicates, dtype=np.float64)
    block_count = int(math.ceil(n / block_length))
    offsets = np.arange(block_length, dtype=np.int32)
    for first in range(0, replicates, 500):
        last = min(replicates, first + 500)
        starts = rng.integers(0, n, size=(last - first, block_count), dtype=np.int32)
        indices = (starts[:, :, None] + offsets[None, None, :]) % n
        indices = indices.reshape(last - first, -1)[:, :n]
        samples[first:last] = x[indices].mean(axis=1)
    lo, hi = np.quantile(samples, [0.025, 0.975])
    return [float(lo), float(hi)]

def split_sizes(n):
    d = int(round(n * 0.60))
    v = int(round(n * 0.20))
    b = n - d - v
    if min(d, v, b) <= 0:
        raise ValueError("insufficient targets for chronological splits")
    return d, v, b

def load_q7_rank_matrix(q7_root: Path, draws):
    base = q7_root / "reports/sequence_agent"
    manifest_path = base / "exhaustive_formula_walkforward_manifest.json"
    runner_path = q7_root / "scripts/sonar_exhaustive_walkforward.py"
    archive_path = q7_root / "data/storico_daily.csv"
    if git_blob_sha1(manifest_path) != Q7_WF_MANIFEST_BLOB:
        raise RuntimeError("Q7 walk-forward manifest Git blob mismatch")
    if git_blob_sha1(runner_path) != Q7_RUNNER_BLOB:
        raise RuntimeError("Q7 runner Git blob mismatch")
    if git_blob_sha1(archive_path) != Q7_ARCHIVE_BLOB:
        raise RuntimeError("Q7 archive Git blob mismatch")
    runner_order = assert_runner_strict_prior_order(runner_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "VALIDATED_COMPLETE":
        raise RuntimeError("Q7 walk-forward source is not VALIDATED_COMPLETE")
    if (manifest.get("target_count"), manifest.get("scored_target_count"),
        manifest.get("formula_count"), manifest.get("candidate_universe_size")) != (DRAW_COUNT, DRAW_COUNT - 1, FORMULAS, CANDIDATES):
        raise RuntimeError("Q7 walk-forward dimensions mismatch")
    ranks = np.full((DRAW_COUNT, FORMULAS), -1, dtype=np.int32)
    meta = [None] * DRAW_COUNT
    columns = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + [
        f"rank_mask_{x:04d}" for x in range(1, FORMULAS + 1)
    ]
    parts = manifest.get("parts", [])
    if len(parts) != 34:
        raise RuntimeError(f"expected 34 Q7 rank parts, found {len(parts)}")
    for part in parts:
        start = int(part["start_index"])
        end = int(part["end_index_exclusive"])
        path = q7_root / part["path"]
        if end <= start or end > DRAW_COUNT or sha256_file(path) != part["sha256"]:
            raise RuntimeError(f"Q7 rank part range/hash mismatch: {path.name}")
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            if next(reader, None) != columns:
                raise RuntimeError(f"Q7 rank column order mismatch: {path.name}")
            count = 0
            for row in reader:
                i = start + count
                if i >= end or len(row) != len(columns):
                    raise RuntimeError(f"Q7 rank row width/range mismatch: {path.name}")
                day, cutoff, prior, actual, status = row[:5]
                expected_day, expected_draw = draws[i]
                expected_cutoff = draws[i - 1][0] if i else ""
                if day != expected_day or cutoff != expected_cutoff or int(prior) != i or actual != " ".join(map(str, expected_draw)):
                    raise RuntimeError(f"Q7 target/cutoff/source mismatch at index {i}")
                if i == 0:
                    if status != "INSUFFICIENT_HISTORY" or any(row[5:]):
                        raise RuntimeError("Q7 first target should be unscored")
                else:
                    if status != "SCORED":
                        raise RuntimeError(f"Q7 target not scored: {day}")
                    values = np.asarray(row[5:], dtype=np.int32)
                    if values.shape != (FORMULAS,) or np.any(values < 1) or np.any(values > CANDIDATES):
                        raise RuntimeError(f"invalid one-based rank vector at {day}")
                    ranks[i] = values
                meta[i] = {
                    "target_date": day, "cutoff_date": cutoff, "prior_draws": i,
                    "actual_quintet": actual, "status": status,
                }
                count += 1
            if count != end - start:
                raise RuntimeError(f"Q7 rank part row count mismatch: {path.name}")
    if any(x is None for x in meta) or np.any(ranks[1:] < 1) or np.any(ranks[0] != -1):
        raise RuntimeError("Q7 rank matrix incomplete")
    return ranks, meta, manifest, runner_order

def write_gzip_jsonl(path: Path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
            for record in records:
                gz.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def file_info(path: Path, relative_to: Path, rows: int | None = None):
    data = path.read_bytes()
    info = {
        "path": str(path.relative_to(relative_to)),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "git_blob_sha1": git_blob_sha1_bytes(data),
    }
    if rows is not None:
        info["rows"] = int(rows)
    return info

def target_metrics(rank_vector, complexity, complexity_rank):
    percentile = 1.0 - (rank_vector.astype(np.float64) - 1.0) / (CANDIDATES - 1.0)
    rho = spearman_from_values(complexity, percentile)
    low = complexity <= 2
    high = complexity >= 6
    return {
        "spearman_rho": rho,
        "mean_percentile_all": float(percentile.mean()),
        "mean_percentile_low_1_2": float(percentile[low].mean()),
        "mean_percentile_high_6_10": float(percentile[high].mean()),
        "high_low_percentile_delta": float(percentile[high].mean() - percentile[low].mean()),
        "top20_rate_all": float(np.mean(rank_vector <= 20)),
        "top100_rate_all": float(np.mean(rank_vector <= 100)),
        "top20_rate_low_1_2": float(np.mean(rank_vector[low] <= 20)),
        "top20_rate_high_6_10": float(np.mean(rank_vector[high] <= 20)),
        "high_low_top20_delta": float(np.mean(rank_vector[high] <= 20) - np.mean(rank_vector[low] <= 20)),
        "top100_rate_low_1_2": float(np.mean(rank_vector[low] <= 100)),
        "top100_rate_high_6_10": float(np.mean(rank_vector[high] <= 100)),
        "high_low_top100_delta": float(np.mean(rank_vector[high] <= 100) - np.mean(rank_vector[low] <= 100)),
        "mean_one_based_rank_all": float(rank_vector.mean()),
    }

def summarize_split(name, rows):
    keys = [
        "spearman_rho", "mean_percentile_all", "mean_percentile_low_1_2",
        "mean_percentile_high_6_10", "high_low_percentile_delta",
        "top20_rate_all", "top100_rate_all", "top20_rate_low_1_2",
        "top20_rate_high_6_10", "high_low_top20_delta",
        "top100_rate_low_1_2", "top100_rate_high_6_10",
        "high_low_top100_delta", "mean_one_based_rank_all",
    ]
    out = {"targets": len(rows), "metrics": {}}
    for j, key in enumerate(keys):
        values = np.asarray([x[key] for x in rows], dtype=np.float64)
        out["metrics"][key] = {
            "mean": float(values.mean()),
            "ci95_moving_block": moving_block_ci(values, seed=SEED + 1000 + j + len(name)),
        }
    out["random_quintet_reference"] = {
        "expected_mean_percentile": 0.5,
        "expected_mean_one_based_rank": (CANDIDATES + 1) / 2.0,
        "top20_probability": 20 / CANDIDATES,
        "top100_probability": 100 / CANDIDATES,
    }
    strata = {}
    for k in range(1, 11):
        values = [x for x in rows if x["feature_count"] == k]
        strata[str(k)] = {
            "formula_count": math.comb(10, k),
            "mean_percentile": float(np.mean([x["stratum_percentiles"][str(k)] for x in rows])),
        }
    out["complexity_strata"] = strata
    return out

def run(q7_root: Path, q141_archive: Path, output_dir: Path):
    prereg_path = output_dir / "q141_q7_complexity_preregistration_2026-11-12.json"
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("task_id") != TASK_TEST or prereg.get("status") != "PREREGISTERED_BEFORE_EXECUTION":
        raise RuntimeError("Q7 complexity preregistration missing or invalid")
    if prereg["source"]["q7_commit"] != Q7_COMMIT:
        raise RuntimeError("preregistration Q7 commit mismatch")
    q7_archive = q7_root / "data/storico_daily.csv"
    if git_blob_sha1(q7_archive) != Q7_ARCHIVE_BLOB or git_blob_sha1(q141_archive) != Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q7/Q141 archive Git blob mismatch")
    q7_draws = read_archive(q7_archive)
    q141_draws = read_archive(q141_archive)
    if len(q7_draws) != DRAW_COUNT or q7_draws[-1][0] != "2026-10-24":
        raise RuntimeError("Q7 archive row count/cutoff mismatch")
    if q141_draws[:DRAW_COUNT] != q7_draws:
        raise RuntimeError("Q7 archive is not an exact prefix of Q141 archive")
    catalog_manifest, ast_records, snapshots = load_formula_catalog(q7_root)
    ranks, meta, wf_manifest, runner_order = load_q7_rank_matrix(q7_root, q7_draws)
    masks = np.arange(1, FORMULAS + 1, dtype=np.int32)
    complexity = np.asarray([int(x).bit_count() for x in masks], dtype=np.int32)
    targets = np.arange(WINDOW + 1, DRAW_COUNT, dtype=np.int32)
    if len(targets) != ELIGIBLE:
        raise RuntimeError(f"eligible target count mismatch: {len(targets)}")
    split_n = split_sizes(len(targets))
    if split_n != (1972, 657, 657):
        raise RuntimeError(f"split counts mismatch: {split_n}")
    split_labels = np.empty(len(targets), dtype=object)
    split_positions = {
        "discovery": np.arange(0, split_n[0], dtype=np.int32),
        "validation": np.arange(split_n[0], split_n[0] + split_n[1], dtype=np.int32),
        "blind_oos": np.arange(split_n[0] + split_n[1], len(targets), dtype=np.int32),
    }
    for name, positions in split_positions.items():
        split_labels[positions] = name
    ledger_rows = []
    per_target = []
    complexity_counts = {str(k): int(np.count_nonzero(complexity == k)) for k in range(1, 11)}
    for pos, target_index in enumerate(targets):
        if int(meta[int(target_index)]["prior_draws"]) != int(target_index):
            raise RuntimeError("prior draw count mismatch")
        if meta[int(target_index)]["cutoff_date"] >= meta[int(target_index)]["target_date"]:
            raise RuntimeError("non-prior cutoff detected")
        vector = ranks[int(target_index)]
        metric = target_metrics(vector, complexity, None)
        metric["feature_count"] = None
        metric["stratum_percentiles"] = {}
        for k in range(1, 11):
            metric["stratum_percentiles"][str(k)] = float(
                (1.0 - (vector[complexity == k].astype(np.float64) - 1.0) / (CANDIDATES - 1.0)).mean()
            )
        metric["feature_count"] = -1
        per_target.append(metric)
        ledger_rows.append({
            **meta[int(target_index)],
            "split": str(split_labels[pos]),
            "eligible_position": int(pos),
            "formula_count": FORMULAS,
            "candidate_quintet_count": CANDIDATES,
            "spearman_complexity_vs_percentile": metric["spearman_rho"],
            "mean_percentile_all_formulas": metric["mean_percentile_all"],
            "mean_percentile_low_complexity_1_2": metric["mean_percentile_low_1_2"],
            "mean_percentile_high_complexity_6_10": metric["mean_percentile_high_6_10"],
            "high_minus_low_percentile": metric["high_low_percentile_delta"],
            "top20_rate_all_formulas": metric["top20_rate_all"],
            "top100_rate_all_formulas": metric["top100_rate_all"],
            "high_minus_low_top20_rate": metric["high_low_top20_delta"],
            "high_minus_low_top100_rate": metric["high_low_top100_delta"],
            "mean_one_based_rank_all_formulas": metric["mean_one_based_rank_all"],
        })
    split_reports = {}
    for name, positions in split_positions.items():
        split_reports[name] = summarize_split(name, [per_target[int(i)] for i in positions])
    blind = [per_target[int(i)] for i in split_positions["blind_oos"]]
    test_series = {
        "B8_T1": ([x["spearman_rho"] for x in blind], PRIMARY_MARGIN),
        "B8_T2": ([x["mean_percentile_all"] for x in blind], 0.5),
        "B8_T3": ([x["high_low_percentile_delta"] for x in blind], 0.005),
        "B8_T4": ([x["high_low_top20_delta"] for x in blind], 0.0),
    }
    tests = []
    for i, (test_id, (values, threshold)) in enumerate(test_series.items()):
        p, block_count, method = block_signflip_p(values, threshold=threshold, seed=SEED + i)
        tests.append({
            "id": test_id,
            "endpoint": prereg["registered_tests"][i]["endpoint"],
            "targets": len(values),
            "mean_effect": float(np.mean(values)),
            "null_threshold": float(threshold),
            "ci95_moving_block": moving_block_ci(values, seed=SEED + 500 + i),
            "p_raw_one_sided": p,
            "block_length": BLOCK_LENGTH,
            "block_count": block_count,
            "method": method,
        })
    adjusted = holm_adjust([x["p_raw_one_sided"] for x in tests])
    for item, p in zip(tests, adjusted):
        item["p_holm_four_registered_blind_tests"] = p
    primary = tests[0]
    primary_pass = primary["mean_effect"] >= PRIMARY_MARGIN and primary["p_holm_four_registered_blind_tests"] < 0.05
    complexity_strata = {}
    for k in range(1, 11):
        mask = complexity == k
        idx = split_positions["blind_oos"]
        vals = []
        for pos in idx:
            target_index = int(targets[int(pos)])
            vals.append(float((1.0 - (ranks[target_index, mask].astype(np.float64) - 1.0) / (CANDIDATES - 1.0)).mean()))
        complexity_strata[str(k)] = {
            "formula_count": int(mask.sum()),
            "mean_percentile": float(np.mean(vals)),
            "mean_top20_rate": float(np.mean([
                np.mean(ranks[int(targets[int(pos)]), mask] <= 20) for pos in idx
            ])),
            "mean_top100_rate": float(np.mean([
                np.mean(ranks[int(targets[int(pos)]), mask] <= 100) for pos in idx
            ])),
        }
    report = {
        "schema_version": "1.0",
        "task_id": TASK_TEST,
        "status": "WALKFORWARD_COMPLETE",
        "decision": "COMPLEXITY_ASSOCIATION_NOT_DEMONSTRATED" if not primary_pass else "PRIMARY_ASSOCIATION_PASSES_REGISTERED_GATE_PENDING_REPLICATION",
        "hypothesis": prereg["hypothesis"],
        "primary_estimand": prereg["primary_estimand"],
        "source": {
            "q7_commit": Q7_COMMIT,
            "q7_archive_blob_sha1": Q7_ARCHIVE_BLOB,
            "q7_catalog_manifest_blob_sha1": Q7_CATALOG_MANIFEST_BLOB,
            "q7_walkforward_manifest_blob_sha1": Q7_WF_MANIFEST_BLOB,
            "q7_runner_blob_sha1": Q7_RUNNER_BLOB,
            "q141_archive_blob_sha1": Q141_ARCHIVE_BLOB,
            "q7_draws": DRAW_COUNT,
            "q7_cutoff": "2026-10-24",
            "q7_is_exact_q141_prefix": True,
            "contest_315_used": False,
        },
        "universe": {
            "formula_count": FORMULAS,
            "candidate_quintets": CANDIDATES,
            "feature_family_count": 10,
            "formula_counts_by_complexity": complexity_counts,
            "low_complexity_formula_count_1_2": int(np.count_nonzero(complexity <= 2)),
            "high_complexity_formula_count_6_10": int(np.count_nonzero(complexity >= 6)),
        },
        "walkforward": {
            "strict_prior": True,
            "target_update_order": "score and write target rank row before add_draw(state, draw), verified against pinned runner source",
            "burn_in_scored_targets": WINDOW,
            "eligible_targets": ELIGIBLE,
            "split_counts": SPLITS,
            "split_metrics": split_reports,
        },
        "blind_oos_complexity_strata": complexity_strata,
        "registered_blind_tests": tests,
        "inference": {
            "block_length": BLOCK_LENGTH,
            "sign_flip_replicates": REPLICATES,
            "moving_block_bootstrap_replicates": REPLICATES,
            "seed": SEED,
            "correction": "Holm-Bonferroni across four preregistered Blind OOS endpoints",
            "global_research_family_correction": "not covered; historical Q00-Q141 experimentation remains an additional multiplicity/exposure limitation",
        },
        "limitations": [
            "Q7 is a quintet_score grammar and is not directly comparable to per-number Q80/Q90 scores.",
            "The experiment tests a structural association across a fixed grammar, not a deployable ex-ante selector.",
            "Historical Blind OOS is exposed prior research history, not virgin prospective evidence.",
            "Holm correction covers only the four preregistered B8 Blind OOS endpoints, not all prior Q00-Q141 experimentation.",
            "Q7 ends on 2026-10-24; later archive rows are excluded.",
        ],
    }
    out = output_dir
    out.mkdir(parents=True, exist_ok=True)
    ast_path = out / OUT_NAMES["ast"]
    snapshot_path = out / OUT_NAMES["snapshot"]
    import_report_path = out / OUT_NAMES["import_report"]
    complexity_report_path = out / OUT_NAMES["complexity_report"]
    ledger_path = out / OUT_NAMES["ledger"]
    manifest_path = out / OUT_NAMES["manifest"]
    checkpoint_path = out / OUT_NAMES["checkpoint"]
    write_gzip_jsonl(ast_path, ast_records)
    write_gzip_jsonl(snapshot_path, snapshots)
    import_report = {
        "schema_version": "1.0",
        "task_id": TASK_IMPORT,
        "status": "LOCAL_TYPED_AST_IMPORT_COMPLETE",
        "formula_count": len(ast_records),
        "unique_source_formula_ids": len({x["source_formula_id"] for x in ast_records}),
        "unique_canonical_ast_ids": len({x["ast_id"] for x in ast_records}),
        "output_type": "quintet_score",
        "candidate_universe_size": CANDIDATES,
        "source_catalog_target_date": catalog_manifest["target_date"],
        "source_catalog_target_cutoff": catalog_manifest["target_cutoff_date"],
        "feature_families": catalog_manifest["feature_families"],
        "source_commit": Q7_COMMIT,
        "source_archive_blob_sha1": Q7_ARCHIVE_BLOB,
        "note": "Structural import only; top20 snapshot is a historical source artifact, not a prospective claim.",
    }
    write_json(import_report_path, import_report)
    write_json(complexity_report_path, report)
    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        fields = list(ledger_rows[0].keys())
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ledger_rows)
    repo_root = Path.cwd()
    outputs = [
        file_info(ast_path, repo_root, len(ast_records)),
        file_info(snapshot_path, repo_root, len(snapshots)),
        file_info(import_report_path, repo_root),
        file_info(complexity_report_path, repo_root),
        file_info(ledger_path, repo_root, len(ledger_rows)),
    ]
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-A4_B8",
        "status": "LOCAL_OUTPUTS_READY",
        "source_commit": Q7_COMMIT,
        "source_archive_blob_sha1": Q7_ARCHIVE_BLOB,
        "source_catalog_manifest_blob_sha1": Q7_CATALOG_MANIFEST_BLOB,
        "source_walkforward_manifest_blob_sha1": Q7_WF_MANIFEST_BLOB,
        "source_runner_blob_sha1": Q7_RUNNER_BLOB,
        "q141_archive_blob_sha1": Q141_ARCHIVE_BLOB,
        "formula_count": FORMULAS,
        "unique_ast_count": len({x["ast_id"] for x in ast_records}),
        "snapshot_rows": len(snapshots),
        "candidate_quintets": CANDIDATES,
        "eligible_targets": ELIGIBLE,
        "split_counts": SPLITS,
        "rank_parts_verified": len(wf_manifest["parts"]),
        "runner_order_offsets": runner_order,
        "files": {Path(x["path"]).name: x for x in outputs},
    }
    write_json(manifest_path, manifest)
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141_A4_B8_CHECKPOINT",
        "status": "LOCAL_OUTPUTS_READY_REMOTE_READBACK_PENDING",
        "source_commit": Q7_COMMIT,
        "eligible_targets": ELIGIBLE,
        "split_counts": SPLITS,
        "completed": ["source hash verification", "Q7 AST generation", "strict-prior rank matrix audit", "complexity walk-forward", "local manifest and output hashes"],
        "next_action": "Persist outputs to Q141 branch and verify exact remote Git readback.",
        "decision": report["decision"],
    }
    write_json(checkpoint_path, checkpoint)
    print(json.dumps({
        "status": "LOCAL_OUTPUTS_READY",
        "formula_count": FORMULAS,
        "ast_count": len(ast_records),
        "eligible_targets": ELIGIBLE,
        "split_counts": SPLITS,
        "decision": report["decision"],
        "primary_mean_rho": tests[0]["mean_effect"],
        "primary_p_holm": tests[0]["p_holm_four_registered_blind_tests"],
        "manifest": str(manifest_path),
    }, sort_keys=True))
    return report, manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--q7-root", type=Path, required=True)
    parser.add_argument("--q141-archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.q7_root, args.q141_archive, args.output_dir)

if __name__ == "__main__":
    main()
