#!/usr/bin/env python3
"""Q141-B9: balanced factorial attribution for the fixed Q7 quintet formula grammar."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sonar_q141_q7_ast_import_complexity as q7lib  # noqa: E402

TASK = "Q141-B9"
Q7_COMMIT = "7a37cab601c5f9386131a00246963f8e4aeabf74"
Q7_ARCHIVE_BLOB = "7dab05ba49ace909fe8783eef729605049c65e50"
Q7_WF_MANIFEST_BLOB = "aae2c7768c9d37bf633a13939f2b686bcce83a27"
Q7_CATALOG_MANIFEST_BLOB = "5cdf9c24431ea23b2176aa6a19133b7f4435980c"
Q7_RUNNER_BLOB = "ad1c7fa721f316b3af0018f5da4a0a905bb62dcf"
Q141_ARCHIVE_BLOB = "fcb453ed06c8002314f826dbac79d6935f9ac103"
PREREG_JSON_BLOB = "2d915678e9cc8912b8127df79e30eb08ee0e8c68"
PREREG_MD_BLOB = "e92bea378e97345fd3799de495ba59b7e8967b23"
DRAW_COUNT = 3387
FORMULAS = 1023
CANDIDATES = 658008
FIRST_TARGET = 101
ELIGIBLE = 3286
SPLITS = {"discovery": 1972, "validation": 657, "blind_oos": 657}
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261121
PRACTICAL_THRESHOLD = 0.005

PREREG_JSON = "q141_q7_factorial_attribution_preregistration_2026-11-12.json"
PREREG_MD = "q141_q7_factorial_attribution_preregistration_2026-11-12.md"
REPORT_NAME = "q141_q7_factorial_attribution_report_2026-11-12.json"
LEDGER_NAME = "q141_q7_factorial_attribution_target_ledger_2026-11-12.csv"
MANIFEST_NAME = "q141_q7_factorial_attribution_manifest_2026-11-12.json"
CHECKPOINT_NAME = "q141_q7_factorial_attribution_checkpoint_2026-11-12.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_info(path: Path, root: Path, rows: int | None = None) -> dict:
    data = path.read_bytes()
    item = {
        "path": str(path.resolve().relative_to(root.resolve())),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "git_blob_sha1": hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest(),
    }
    if rows is not None:
        item["rows"] = int(rows)
    return item


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def build_contrast_contexts(family_names: list[str]) -> list[dict]:
    if len(family_names) != 10 or len(set(family_names)) != 10:
        raise ValueError("exactly ten unique Q7 feature-family names are required")
    masks = np.arange(1, FORMULAS + 1, dtype=np.int32)
    contexts: list[dict] = []
    for i, name in enumerate(family_names):
        bit = 1 << i
        base = masks[(masks & bit) == 0]
        if len(base) != 511 or np.any(base <= 0):
            raise AssertionError(f"main-effect context count/empty-subset error for {name}")
        contexts.append({
            "id": f"MAIN_{i:02d}",
            "kind": "main_effect",
            "family_indices": [i],
            "family_names": [name],
            "base": base,
            "plus": base | bit,
        })
    for i in range(10):
        for j in range(i + 1, 10):
            bits = (1 << i) | (1 << j)
            base = masks[(masks & bits) == 0]
            if len(base) != 255 or np.any(base <= 0):
                raise AssertionError(f"pairwise context count/empty-subset error for {i},{j}")
            contexts.append({
                "id": f"PAIR_{i:02d}_{j:02d}",
                "kind": "pairwise_interaction",
                "family_indices": [i, j],
                "family_names": [family_names[i], family_names[j]],
                "base": base,
                "plus_i": base | (1 << i),
                "plus_j": base | (1 << j),
                "plus_ij": base | bits,
            })
    if len(contexts) != 55:
        raise AssertionError("Q7 factorial design must contain exactly 55 endpoints")
    return contexts


def factorial_effects_from_percentiles(percentiles: np.ndarray, contexts: list[dict]) -> np.ndarray:
    p = np.asarray(percentiles, dtype=np.float64)
    if p.shape != (FORMULAS,) or not np.all(np.isfinite(p)):
        raise ValueError("percentile vector must contain 1,023 finite values")
    out = np.empty(len(contexts), dtype=np.float64)
    for k, context in enumerate(contexts):
        base = context["base"] - 1
        if context["kind"] == "main_effect":
            plus = context["plus"] - 1
            out[k] = float(np.mean(p[plus] - p[base]))
        else:
            plus_i = context["plus_i"] - 1
            plus_j = context["plus_j"] - 1
            plus_ij = context["plus_ij"] - 1
            out[k] = float(np.mean(p[plus_ij] - p[plus_i] - p[plus_j] + p[base]))
    return out


def target_factorial_effects(rank_matrix: np.ndarray, target_index: int, contexts: list[dict]) -> tuple[np.ndarray, float]:
    """Use only the already-frozen rank vector for this target; never inspect later rows."""
    if rank_matrix.ndim != 2 or rank_matrix.shape[1] != FORMULAS:
        raise ValueError("rank matrix shape mismatch")
    ranks = np.asarray(rank_matrix[target_index], dtype=np.int64)
    if ranks.shape != (FORMULAS,) or np.any(ranks < 1) or np.any(ranks > CANDIDATES):
        raise ValueError(f"invalid strict-prior rank row at target index {target_index}")
    p = 1.0 - (ranks.astype(np.float64) - 1.0) / (CANDIDATES - 1.0)
    return factorial_effects_from_percentiles(p, contexts), float(p.mean())


def split_sizes(n: int) -> tuple[int, int, int]:
    d = int(round(n * 0.60))
    v = int(round(n * 0.20))
    b = n - d - v
    if min(d, v, b) <= 0:
        raise ValueError("insufficient targets for chronological splits")
    return d, v, b


def holm_adjust(p_values: list[float]) -> list[float]:
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    out = [1.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * float(p_values[i])))
        out[i] = running
    return out


def block_signflip_two_sided(values: np.ndarray, block_length: int, replicates: int, seed: int) -> tuple[float, int]:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x)):
        raise ValueError("invalid target-level effect series")
    blocks = np.asarray([x[i:i + block_length].sum() for i in range(0, len(x), block_length)], dtype=np.float64)
    observed = float(x.mean())
    k = len(blocks)
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.asarray([-1.0, 1.0]), size=(replicates, k))
    null = signs @ blocks / len(x)
    p = (1.0 + np.count_nonzero(np.abs(null) >= abs(observed) - 1e-15)) / (replicates + 1.0)
    return float(p), k


def split_summary(values: np.ndarray, all_formula_percentiles: np.ndarray, ranks_top20: np.ndarray, contexts: list[dict]) -> dict:
    x = np.asarray(values, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != len(contexts):
        raise ValueError("split effect matrix shape mismatch")
    effects = {}
    for j, context in enumerate(contexts):
        col = x[:, j]
        effects[context["id"]] = {
            "mean": float(col.mean()),
            "median": float(np.median(col)),
            "standard_deviation": float(col.std(ddof=1)),
            "minimum": float(col.min()),
            "maximum": float(col.max()),
        }
    return {
        "targets": int(len(x)),
        "mean_all_formula_percentile": float(np.mean(all_formula_percentiles)),
        "uniform_quintet_percentile_reference": 0.5,
        "mean_formula_top20_share_for_realized_quintet": float(np.mean(ranks_top20)),
        "effects": effects,
    }


def run(q7_root: Path, q141_archive: Path, output_dir: Path) -> dict:
    prereg_path = output_dir / PREREG_JSON
    prereg_md_path = output_dir / PREREG_MD
    if q7lib.git_blob_sha1(prereg_path) != PREREG_JSON_BLOB:
        raise RuntimeError("Q141-B9 JSON preregistration Git blob mismatch")
    if q7lib.git_blob_sha1(prereg_md_path) != PREREG_MD_BLOB:
        raise RuntimeError("Q141-B9 Markdown preregistration Git blob mismatch")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("task_id") != TASK or prereg.get("status") != "PREREGISTERED_EXECUTION_PENDING":
        raise RuntimeError("Q141-B9 preregistration is missing or already altered")
    source = prereg["source"]
    if (source.get("q7_commit"), source.get("q7_archive_blob_sha1"),
        source.get("q7_walkforward_manifest_blob_sha1"), source.get("q7_runner_blob_sha1"),
        source.get("q141_archive_blob_sha1"), source.get("q7_draws"),
        source.get("q7_cutoff"), source.get("formula_count"),
        source.get("candidate_quintets"), source.get("feature_family_count")) != (
            Q7_COMMIT, Q7_ARCHIVE_BLOB, Q7_WF_MANIFEST_BLOB, Q7_RUNNER_BLOB,
            Q141_ARCHIVE_BLOB, DRAW_COUNT, "2026-10-24", FORMULAS, CANDIDATES, 10):
        raise RuntimeError("Q141-B9 pinned source lineage mismatch")
    target_protocol = prereg["target_protocol"]
    if (target_protocol.get("eligible_target_indices"), target_protocol.get("eligible_targets"),
        target_protocol.get("split_counts"), target_protocol.get("strict_prior"),
        target_protocol.get("target_update_order")) != (
            "101..3386 inclusive", ELIGIBLE, SPLITS,
            "Use only the pinned Q7 rank row generated from draws strictly before the target; target outcome only evaluates that frozen rank.",
            "score/write rank row before adding target draw to state"):
        raise RuntimeError("Q141-B9 target protocol differs from preregistration")
    inference = prereg["inference"]
    if (inference.get("blind_oos_tests"), inference.get("block_length"),
        inference.get("sign_flip_replicates"), inference.get("moving_block_bootstrap_replicates"),
        inference.get("seed"), inference.get("correction")) != (
            55, BLOCK_LENGTH, REPLICATES, REPLICATES, SEED,
            "Holm-Bonferroni across all 55 registered Blind OOS main and pairwise interaction endpoints"):
        raise RuntimeError("Q141-B9 inference settings differ from preregistration")
    if prereg["estimands"].get("practical_effect_threshold_absolute") != PRACTICAL_THRESHOLD:
        raise RuntimeError("Q141-B9 practical threshold mismatch")

    q7_archive_path = q7_root / "data/storico_daily.csv"
    if q7lib.git_blob_sha1(q141_archive) != Q141_ARCHIVE_BLOB:
        raise RuntimeError("Q141 source archive Git blob mismatch")
    q7_draws = q7lib.read_archive(q7_archive_path)
    q141_draws = q7lib.read_archive(q141_archive)
    if len(q7_draws) != DRAW_COUNT or q7_draws[-1][0] != "2026-10-24":
        raise RuntimeError("Q7 archive row count or cutoff mismatch")
    if q141_draws[:DRAW_COUNT] != q7_draws:
        raise RuntimeError("Q7 source archive is not the exact Q141 archive prefix")

    catalog_manifest, ast_records, snapshots = q7lib.load_formula_catalog(q7_root)
    family_names = [x["name"] for x in catalog_manifest["feature_families"]]
    if len(ast_records) != FORMULAS or len(snapshots) != FORMULAS:
        raise RuntimeError("Q7 formula catalog failed full 1,023-formula lineage audit")
    if family_names != [x["name"] for x in catalog_manifest["feature_families"]]:
        raise RuntimeError("Q7 family ordering mismatch")
    ranks, meta, wf_manifest, runner_order = q7lib.load_q7_rank_matrix(q7_root, q7_draws)
    if len(wf_manifest.get("parts", [])) != 34:
        raise RuntimeError("Q7 rank matrix does not contain all 34 registered parts")

    targets = np.arange(FIRST_TARGET, DRAW_COUNT, dtype=np.int32)
    if len(targets) != ELIGIBLE or (int(targets[0]), int(targets[-1])) != (101, 3386):
        raise RuntimeError("Q141-B9 eligible target indices mismatch")
    split_n = split_sizes(len(targets))
    if split_n != (1972, 657, 657):
        raise RuntimeError(f"Q141-B9 chronological split mismatch: {split_n}")
    split_positions = {
        "discovery": np.arange(0, split_n[0], dtype=np.int32),
        "validation": np.arange(split_n[0], split_n[0] + split_n[1], dtype=np.int32),
        "blind_oos": np.arange(split_n[0] + split_n[1], len(targets), dtype=np.int32),
    }
    split_labels = np.empty(len(targets), dtype=object)
    for label, positions in split_positions.items():
        split_labels[positions] = label

    contexts = build_contrast_contexts(family_names)
    effects = np.empty((len(targets), len(contexts)), dtype=np.float64)
    all_formula_percentiles = np.empty(len(targets), dtype=np.float64)
    top20_shares = np.empty(len(targets), dtype=np.float64)
    ledger_rows = []
    for position, target_index in enumerate(targets):
        target_index = int(target_index)
        row_meta = meta[target_index]
        if int(row_meta["prior_draws"]) != target_index:
            raise RuntimeError(f"prior draw count mismatch at target index {target_index}")
        if not row_meta["cutoff_date"] or row_meta["cutoff_date"] >= row_meta["target_date"]:
            raise RuntimeError(f"non-prior cutoff at target {row_meta['target_date']}")
        if row_meta["target_date"] != q7_draws[target_index][0] or row_meta["actual_quintet"] != " ".join(map(str, q7_draws[target_index][1])):
            raise RuntimeError(f"target outcome/source mismatch at index {target_index}")
        effects[position], all_formula_percentiles[position] = target_factorial_effects(ranks, target_index, contexts)
        top20_shares[position] = float(np.mean(ranks[target_index] <= 20))
        record = {
            "target_date": row_meta["target_date"],
            "cutoff_date": row_meta["cutoff_date"],
            "prior_draws": int(row_meta["prior_draws"]),
            "actual_quintet": row_meta["actual_quintet"],
            "split": str(split_labels[position]),
            "eligible_position": int(position),
            "all_formula_mean_percentile": float(all_formula_percentiles[position]),
            "all_formula_top20_share": float(top20_shares[position]),
        }
        for j, context in enumerate(contexts):
            record[context["id"]] = float(effects[position, j])
        ledger_rows.append(record)

    split_reports = {}
    for label, positions in split_positions.items():
        split_reports[label] = split_summary(
            effects[positions],
            all_formula_percentiles[positions],
            top20_shares[positions],
            contexts,
        )

    blind_positions = split_positions["blind_oos"]
    blind_effects = effects[blind_positions]
    tests = []
    for j, context in enumerate(contexts):
        values = blind_effects[:, j]
        p_raw, block_count = block_signflip_two_sided(
            values, BLOCK_LENGTH, REPLICATES, SEED + j
        )
        ci = q7lib.moving_block_ci(
            values, block_length=BLOCK_LENGTH, replicates=REPLICATES, seed=SEED + 1000 + j
        )
        tests.append({
            "id": context["id"],
            "kind": context["kind"],
            "family_indices": context["family_indices"],
            "family_names": context["family_names"],
            "targets": int(len(values)),
            "mean_effect": float(values.mean()),
            "median_effect": float(np.median(values)),
            "ci95_circular_moving_block": ci,
            "null_effect": 0.0,
            "p_raw_two_sided": float(p_raw),
            "block_count": int(block_count),
            "block_length": BLOCK_LENGTH,
            "holm_adjusted_p_55": None,
            "absolute_practical_threshold": PRACTICAL_THRESHOLD,
            "flagged_for_replication_only": False,
        })
    adjusted = holm_adjust([x["p_raw_two_sided"] for x in tests])
    for item, p_holm in zip(tests, adjusted):
        item["holm_adjusted_p_55"] = float(p_holm)
        item["flagged_for_replication_only"] = bool(
            p_holm < 0.05 and abs(item["mean_effect"]) >= PRACTICAL_THRESHOLD
        )
    flagged = [x["id"] for x in tests if x["flagged_for_replication_only"]]
    decision = (
        "MAIN_OR_INTERACTION_EFFECTS_FLAGGED_FOR_INDEPENDENT_REPLICATION_ONLY"
        if flagged else "NO_REGISTERED_MAIN_OR_PAIRWISE_EFFECT_DEMONSTRATED"
    )

    report = {
        "schema_version": "1.0",
        "task_id": TASK,
        "status": "WALKFORWARD_COMPLETE",
        "decision": decision,
        "hypothesis": prereg["hypothesis"],
        "estimands": prereg["estimands"],
        "formula_universe": {
            "formula_count": FORMULAS,
            "candidate_quintets": CANDIDATES,
            "feature_family_count": len(family_names),
            "feature_families": family_names,
            "main_effect_endpoint_count": 10,
            "pairwise_interaction_endpoint_count": 45,
            "total_endpoint_count": len(contexts),
            "main_contexts_per_endpoint": 511,
            "pair_contexts_per_endpoint": 255,
            "empty_background_excluded": True,
        },
        "source": {
            "q7_commit": Q7_COMMIT,
            "q7_archive_blob_sha1": Q7_ARCHIVE_BLOB,
            "q7_walkforward_manifest_blob_sha1": Q7_WF_MANIFEST_BLOB,
            "q7_catalog_manifest_blob_sha1": Q7_CATALOG_MANIFEST_BLOB,
            "q7_runner_blob_sha1": Q7_RUNNER_BLOB,
            "q141_archive_blob_sha1": Q141_ARCHIVE_BLOB,
            "q7_draws": len(q7_draws),
            "q7_cutoff": q7_draws[-1][0],
            "q7_exact_prefix_of_q141": True,
            "q141_rows_after_q7_prefix_excluded": len(q141_draws) - len(q7_draws),
            "contest_315_used": False,
            "rank_parts_verified": len(wf_manifest["parts"]),
            "runner_strict_prior_order_offsets": runner_order,
        },
        "walkforward": {
            "strict_prior": True,
            "target_indices": [int(targets[0]), int(targets[-1])],
            "eligible_targets": len(targets),
            "split_rule": "chronological 60% / 20% / 20%",
            "split_counts": {"discovery": split_n[0], "validation": split_n[1], "blind_oos": split_n[2]},
            "target_cutoff_rule": "Each rank row's cutoff is exactly the immediately preceding Q7 archive date; score/write precedes add_draw(state) in the pinned runner.",
            "target_outcome_role": "The realized quintet is only the evaluation label for the already-frozen strict-prior rank vector.",
            "no_target_or_future_used_in_formula_construction": True,
            "split_summaries": split_reports,
        },
        "blind_oos_tests": tests,
        "inference": {
            "null": "zero main or pairwise interaction effect",
            "method": "two-sided block sign-flip over consecutive non-overlapping blocks; circular moving-block bootstrap confidence interval",
            "block_length": BLOCK_LENGTH,
            "sign_flip_replicates": REPLICATES,
            "bootstrap_replicates": REPLICATES,
            "seed": SEED,
            "correction": "Holm-Bonferroni across all 55 registered Blind OOS endpoints",
            "global_research_family_correction": "Not covered; prior Q00-Q141 exploration remains an exposure and multiplicity limitation.",
            "practical_gate": "Flag only if Holm-adjusted p<0.05 and absolute mean effect>=0.005 percentile units.",
            "flagged_endpoints": flagged,
        },
        "baseline_and_controls": {
            "factorial_zero_effect_reference": 0.0,
            "uniform_random_quintet_expected_percentile": 0.5,
            "per_target_mean_over_1023_formulas_reported": True,
            "all_1023_formula_rank_vector_used_for_each_target": True,
            "no_family_or_pair_selected_for_a_forecast": True,
        },
        "limitations": [
            "Q7 is a quintet_score grammar; effects are not comparable to per-number Q80/Q90 scores.",
            "Main and pairwise effects are descriptive factorial rank contrasts, not causal effects and not a deployable predictor.",
            "The fixed Q7 grammar contains 1,023 masks over ten feature families; conclusions do not cover all possible formulas.",
            "Historical Blind OOS is exposed prior SONAR research history, not virgin prospective evidence.",
            "Holm correction covers the 55 registered B9 endpoints only, not the full Q00-Q141 research family.",
            "The source archive ends on 2026-10-24; later Q141 suffix rows and contest 315 are excluded.",
            "The Blind OOS segment contains 657 targets and 33 non-overlapping blocks of length 20; block inference remains dependent on the registered sign-flip assumptions.",
        ],
        "next_action": "If no effects are flagged, stop adding Q7-only interaction variants and proceed to the cross-granularity behaviour atlas while preserving Q7 quintet_score separately from Q80/Q90 per-number_score. If any endpoint is flagged, preregister an independent replication before any selector or engine use.",
        "governance": {
            "research_only": True,
            "no_merge": True,
            "no_engine_promotion": True,
            "no_shadow_insertion": True,
            "no_canonical_archive_mutation": True,
            "protected_prs": [6, 7, 8],
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / REPORT_NAME
    ledger_path = output_dir / LEDGER_NAME
    manifest_path = output_dir / MANIFEST_NAME
    checkpoint_path = output_dir / CHECKPOINT_NAME

    with ledger_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(ledger_rows[0].keys()))
        writer.writeheader()
        writer.writerows(ledger_rows)
    write_json(report_path, report)

    script_path = Path(__file__).resolve()
    test_path = ROOT / "tests" / "test_sonar_q141_q7_factorial_attribution.py"
    workflow_path = ROOT / ".github" / "workflows" / "q141-b9-q7-factorial-attribution.yml"
    prereg_files = {
        "json": {"path": str(prereg_path.resolve().relative_to(ROOT.resolve())), "git_blob_sha1": q7lib.git_blob_sha1(prereg_path)},
        "markdown": {"path": str(prereg_md_path.resolve().relative_to(ROOT.resolve())), "git_blob_sha1": q7lib.git_blob_sha1(prereg_md_path)},
    }
    if prereg_files["json"]["git_blob_sha1"] != PREREG_JSON_BLOB or prereg_files["markdown"]["git_blob_sha1"] != PREREG_MD_BLOB:
        raise RuntimeError("Q141-B9 preregistration changed during execution")
    code_lineage = {}
    for label, path in (("runner", script_path), ("tests", test_path), ("workflow", workflow_path)):
        if not path.is_file():
            raise RuntimeError(f"missing code lineage file: {path}")
        code_lineage[label] = {
            "path": str(path.resolve().relative_to(ROOT.resolve())),
            "git_blob_sha1": q7lib.git_blob_sha1(path),
        }

    manifest = {
        "schema_version": "1.0",
        "task_id": TASK,
        "status": "LOCAL_OUTPUTS_READY_REMOTE_GIT_READBACK_PENDING",
        "source": report["source"],
        "formula_universe": report["formula_universe"],
        "eligible_targets": ELIGIBLE,
        "split_counts": report["walkforward"]["split_counts"],
        "registered_endpoints": 55,
        "rank_parts_verified": len(wf_manifest["parts"]),
        "rank_part_sha256": [{"path": x["path"], "sha256": x["sha256"], "start": x["start_index"], "end_exclusive": x["end_index_exclusive"]} for x in wf_manifest["parts"]],
        "preregistration": prereg_files,
        "code_lineage": code_lineage,
        "workflow_commit_sha": os.environ.get("GITHUB_SHA", ""),
        "files": {
            "report": file_info(report_path, ROOT),
            "target_ledger": file_info(ledger_path, ROOT, len(ledger_rows)),
        },
    }
    write_json(manifest_path, manifest)
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141_B9_CHECKPOINT",
        "status": "LOCAL_OUTPUTS_READY_REMOTE_GIT_READBACK_PENDING",
        "decision": decision,
        "eligible_targets": ELIGIBLE,
        "split_counts": report["walkforward"]["split_counts"],
        "report_sha256": q7lib.sha256_file(report_path),
        "ledger_sha256": q7lib.sha256_file(ledger_path),
        "manifest_sha256": q7lib.sha256_file(manifest_path),
        "flagged_endpoints": flagged,
        "next_action": report["next_action"],
    }
    write_json(checkpoint_path, checkpoint)
    print("SONAR_Q141_B9_SUMMARY_BEGIN")
    print(json.dumps({
        "task_id": TASK,
        "status": report["status"],
        "decision": decision,
        "eligible_targets": ELIGIBLE,
        "split_counts": report["walkforward"]["split_counts"],
        "flagged_endpoints": flagged,
        "blind_tests": tests,
        "report": str(report_path.relative_to(ROOT)),
        "ledger": str(ledger_path.relative_to(ROOT)),
        "manifest": str(manifest_path.relative_to(ROOT)),
        "checkpoint": str(checkpoint_path.relative_to(ROOT)),
    }, sort_keys=True, separators=(",", ":"), allow_nan=False))
    print("SONAR_Q141_B9_SUMMARY_END")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--q7-root", type=Path, required=True)
    parser.add_argument("--q141-archive", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.q7_root, args.q141_archive, args.output_dir)


if __name__ == "__main__":
    main()
