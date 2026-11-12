#!/usr/bin/env python3
"""Q141-C3: strict-prior consensus ranking across a frozen canonical formula sample."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
PREREG_JSON = OUT / "q141_formula_rank_consensus_preregistration_2026-11-12.json"
PREREG_MD = OUT / "q141_formula_rank_consensus_preregistration_2026-11-12.md"
CATALOG = OUT / "q141_formula_rank_consensus_formula_catalog_2026-11-12.csv"
LEDGER = OUT / "q141_formula_rank_consensus_target_ledger_2026-11-12.csv"
REPORT = OUT / "q141_formula_rank_consensus_report_2026-11-12.json"
MANIFEST = OUT / "q141_formula_rank_consensus_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_formula_rank_consensus_checkpoint_2026-11-12.json"
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry

EXPECTED_FORMULA_RAW = 120
EXPECTED_FORMULA_UNIQUE = 113
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
POLICIES = ("borda_mean_rank", "median_rank", "top5_vote")
CONTROLS = ("equal_family", "equal_feature")
ENDPOINTS = ("top5_hit_share", "top10_hit_share", "top20_hit_share", "mean_actual_number_rank")
BLOCK_LENGTH = 20
REPLICATES = 20000
SEED = 14120261112
PRACTICAL_THRESHOLD = 0.005


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def build_formula_sample():
    raw_sample = registry.sample_formulas()
    if len(raw_sample) != EXPECTED_FORMULA_RAW:
        raise RuntimeError(f"Q141-C3_BLOCKED: raw formula sample count {len(raw_sample)}")
    unique = {}
    for columns in raw_sample:
        signature, _scale = registry.canonicalize_formula(columns)
        formula_id = registry.canonical_formula_id(signature)
        if formula_id not in unique:
            unique[formula_id] = {
                "formula_id": formula_id,
                "signature": tuple((int(index), int(weight)) for index, weight in signature),
                "raw_representations": [],
            }
        unique[formula_id]["raw_representations"].append(tuple(int(x) for x in columns))
    formulas = [unique[key] for key in sorted(unique)]
    if len(formulas) != EXPECTED_FORMULA_UNIQUE:
        raise RuntimeError(f"Q141-C3_BLOCKED: canonical sample count {len(formulas)}")
    return formulas, len(raw_sample)


FORMULAS, RAW_FORMULA_COUNT = build_formula_sample()


def canonical_feature_matrix(raw_features):
    matrix = np.empty((40, len(registry.CANONICAL_FEATURE_NAMES)), dtype=np.float64)
    assigned = set()
    for raw_index, canonical_index in enumerate(registry.RAW_TO_CANONICAL):
        if canonical_index not in assigned:
            matrix[:, canonical_index] = raw_features[:, raw_index]
            assigned.add(canonical_index)
    if len(assigned) != 25 or not np.isfinite(matrix).all():
        raise RuntimeError("Q141-C3_BLOCKED: canonical feature matrix is incomplete or non-finite")
    if not np.array_equal(matrix[:, 0], raw_features[:, 0]) or not np.array_equal(matrix[:, 1], raw_features[:, 1]):
        raise RuntimeError("Q141-C3_BLOCKED: canonical feature projection mismatch")
    return matrix


def rank_ascending(values):
    values = np.asarray(values, dtype=np.float64)
    if values.shape != (40,) or not np.isfinite(values).all():
        raise ValueError("Q141-C3: expected 40 finite ranking values")
    order = np.lexsort((np.arange(40), values))
    ranks = np.empty(40, dtype=np.int16)
    ranks[order] = np.arange(1, 41, dtype=np.int16)
    return ranks


def consensus_rankings(raw_features):
    canonical = canonical_feature_matrix(raw_features)
    formula_rank_rows = []
    for formula in FORMULAS:
        scores = registry.canonical_scores(canonical, formula["signature"], 1)
        formula_rank_rows.append(registry.base.rank_scores(scores))
    rank_matrix = np.vstack(formula_rank_rows).astype(np.int16)
    if rank_matrix.shape != (EXPECTED_FORMULA_UNIQUE, 40):
        raise RuntimeError(f"Q141-C3_BLOCKED: formula rank matrix shape {rank_matrix.shape}")

    mean_rank = rank_matrix.mean(axis=0)
    median_rank = np.median(rank_matrix, axis=0)
    top5_votes = np.sum(rank_matrix <= 5, axis=0).astype(np.int16)
    models = {
        "borda_mean_rank": rank_ascending(mean_rank),
        "median_rank": rank_ascending(median_rank),
    }
    order = np.lexsort((np.arange(40), mean_rank, -top5_votes))
    vote_ranks = np.empty(40, dtype=np.int16)
    vote_ranks[order] = np.arange(1, 41, dtype=np.int16)
    models["top5_vote"] = vote_ranks

    standardized = base.zscore_columns(raw_features)
    family_scores = {
        family: standardized[:, indices].mean(axis=1)
        for family, indices in base.FAMILIES.items()
    }
    equal_family_scores = np.mean(np.vstack([family_scores[name] for name in base.FAMILY_NAMES]), axis=0)
    equal_feature_scores = standardized[:, base.UNIQUE_FEATURE_INDICES].mean(axis=1)
    controls = {
        "equal_family": base.rank_scores(equal_family_scores),
        "equal_feature": base.rank_scores(equal_feature_scores),
    }

    vote_mass = top5_votes.astype(np.float64)
    if vote_mass.sum() > 0:
        probabilities = vote_mass / vote_mass.sum()
        positive = probabilities[probabilities > 0]
        vote_entropy = float(-np.sum(positive * np.log(positive)) / math.log(40.0))
    else:
        vote_entropy = 0.0
    borda_top5 = np.flatnonzero(models["borda_mean_rank"] <= 5)
    family_top5_masks = []
    for family in base.FAMILY_NAMES:
        family_scores_vector = family_scores[family]
        family_ranks = base.rank_scores(family_scores_vector)
        family_top5_masks.append(set(np.flatnonzero(family_ranks <= 5).tolist()))
    jaccards = []
    for a, b in combinations(family_top5_masks, 2):
        union = a | b
        jaccards.append(len(a & b) / len(union) if union else 0.0)
    diagnostics = {
        "mean_top5_vote_count_among_borda_top5": float(np.mean(top5_votes[borda_top5])),
        "max_top5_vote_count": int(np.max(top5_votes)),
        "normalized_vote_entropy": vote_entropy,
        "mean_pairwise_q80_family_top5_jaccard": float(np.mean(jaccards)),
    }
    return models, controls, diagnostics


def split_summary(rows, model_names):
    output = {}
    for split in ("discovery", "validation", "blind_oos"):
        subset = [row for row in rows if row["split"] == split]
        metrics = {}
        for name in model_names:
            n = len(subset)
            metrics[name] = {
                "targets": n,
                "mean_number_hits_top5": float(sum(row[name]["top5_hits"] for row in subset) / (5 * n)),
                "mean_number_hits_top10": float(sum(row[name]["top10_hits"] for row in subset) / (5 * n)),
                "mean_number_hits_top20": float(sum(row[name]["top20_hits"] for row in subset) / (5 * n)),
                "mean_actual_number_rank": float(sum(row[name]["mean_rank"] for row in subset) / n),
                "all5_top5_rate": float(sum(row[name]["top5_hits"] == 5 for row in subset) / n),
            }
        output[split] = {"targets": len(subset), "models": metrics}
    return output


def endpoint_delta(model_metrics, control_metrics, endpoint):
    if endpoint == "top5_hit_share":
        return (model_metrics["top5_hits"] - control_metrics["top5_hits"]) / 5.0
    if endpoint == "top10_hit_share":
        return (model_metrics["top10_hits"] - control_metrics["top10_hits"]) / 5.0
    if endpoint == "top20_hit_share":
        return (model_metrics["top20_hits"] - control_metrics["top20_hits"]) / 5.0
    return control_metrics["mean_rank"] - model_metrics["mean_rank"]


def formula_catalog_rows():
    rows = []
    for formula in FORMULAS:
        signature = formula["signature"]
        rows.append({
            "formula_id": formula["formula_id"],
            "canonical_signature": ";".join(
                f"{registry.CANONICAL_FEATURE_NAMES[index]}={weight}"
                for index, weight in signature
            ),
            "canonical_feature_count": len(signature),
            "raw_representation_count": len(formula["raw_representations"]),
            "raw_representations": json.dumps(formula["raw_representations"], separators=(",", ":")),
        })
    return rows


def run():
    prereg = json.loads(PREREG_JSON.read_text(encoding="utf-8"))
    if prereg.get("status") != "PREREGISTERED_NOT_YET_EXECUTED":
        raise RuntimeError("Q141-C3_BLOCKED: preregistration status is not pristine")
    if prereg.get("formula_sample", {}).get("unique_canonical_formula_count") != len(FORMULAS):
        raise RuntimeError("Q141-C3_BLOCKED: preregistered formula sample mismatch")

    raw, archive_blob_sha, dates, draws, excluded = base.load_archive()
    if archive_blob_sha != "fcb453ed06c8002314f826dbac79d6935f9ac103":
        raise RuntimeError("Q141-C3_BLOCKED: source archive hash mismatch")
    n = len(draws)
    scored_targets = n - base.MIN_HISTORY
    actual_split_counts = Counter(
        base.split_name(offset, scored_targets) for offset in range(scored_targets)
    )
    if scored_targets != 3354 or dict(actual_split_counts) != EXPECTED_SPLITS:
        raise RuntimeError(f"Q141-C3_BLOCKED: target/split mismatch {scored_targets} {dict(actual_split_counts)}")

    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    rows = []
    diagnostic_rows = []

    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, scored_targets)
            raw_features = base.feature_matrix(
                i, draws, prefix, pos_prefix, pair_counts, occurrence_lists
            )
            if not np.array_equal(raw_features[:, 0], raw_features[:, 25]):
                raise RuntimeError("Q141-C3_BLOCKED: recent_5 exact alias invariant failed")
            if not np.array_equal(raw_features[:, 1], raw_features[:, 26]):
                raise RuntimeError("Q141-C3_BLOCKED: recent_10 exact alias invariant failed")

            models, controls, diagnostics = consensus_rankings(raw_features)
            metrics = {
                name: base.rank_metrics(ranks, draw)
                for name, ranks in {**models, **controls}.items()
            }
            row = {
                "target_index": i,
                "target_offset": offset,
                "target_date": dates[i],
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "split": split,
                "actual": tuple(draw),
                **metrics,
            }
            rows.append(row)
            diagnostic_rows.append({"split": split, **diagnostics})

        # Strict prequential update: target i is appended only after all target-i features/ranks are fixed.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    if len(rows) != scored_targets:
        raise RuntimeError("Q141-C3_BLOCKED: target ledger row count mismatch")
    for row in rows:
        if not row["cutoff_date"] < row["target_date"]:
            raise RuntimeError("Q141-C3_BLOCKED: non-strict chronological cutoff")

    model_names = list(POLICIES + CONTROLS)
    metrics_by_split = split_summary(rows, model_names)
    paired_tests = []
    test_index = 0
    for split in ("validation", "blind_oos"):
        subset = [row for row in rows if row["split"] == split]
        for policy in POLICIES:
            for control in CONTROLS:
                deltas_by_endpoint = {}
                for endpoint in ENDPOINTS:
                    deltas = [
                        endpoint_delta(row[policy], row[control], endpoint)
                        for row in subset
                    ]
                    seed = SEED + 30000 + test_index
                    p_raw = base.block_signflip_p(deltas, seed)
                    ci = base.circular_block_bootstrap_ci(deltas, seed + 50000)
                    item = {
                        "split": split,
                        "policy": policy,
                        "control": control,
                        "endpoint": endpoint,
                        "targets": len(subset),
                        "mean_benefit_delta": float(np.mean(deltas)),
                        "bootstrap_ci_95": ci,
                        "block_signflip_p_raw": p_raw,
                    }
                    paired_tests.append(item)
                    deltas_by_endpoint[endpoint] = deltas
                    test_index += 1
    if len(paired_tests) != 48:
        raise RuntimeError(f"Q141-C3_BLOCKED: expected 48 paired tests, got {len(paired_tests)}")
    adjusted = base.holm_adjust([item["block_signflip_p_raw"] for item in paired_tests])
    for item, p_adj in zip(paired_tests, adjusted):
        item["block_signflip_p_holm_48_tests"] = float(p_adj)

    uniform_tests = []
    for split in ("validation", "blind_oos"):
        subset = [row for row in rows if row["split"] == split]
        for policy in POLICIES:
            for endpoint, top_k, field in (
                ("top5_hit_share", 5, "top5_hits"),
                ("top10_hit_share", 10, "top10_hits"),
                ("top20_hit_share", 20, "top20_hits"),
            ):
                observed = sum(row[policy][field] for row in subset)
                uniform_tests.append({
                    "split": split,
                    "policy": policy,
                    "endpoint": endpoint,
                    "targets": len(subset),
                    "observed_number_hits": int(observed),
                    "uniform_expected_number_hits": len(subset) * 5 * top_k / 40.0,
                    "exact_hypergeom_upper_tail_p_raw": base.exact_hypergeom_upper_tail(
                        observed, len(subset), top_k
                    ),
                })
    if len(uniform_tests) != 18:
        raise RuntimeError("Q141-C3_BLOCKED: uniform-null test family size mismatch")
    uniform_adjusted = base.holm_adjust([
        item["exact_hypergeom_upper_tail_p_raw"] for item in uniform_tests
    ])
    for item, p_adj in zip(uniform_tests, uniform_adjusted):
        item["exact_hypergeom_p_holm_18_tests"] = float(p_adj)

    primary = next(
        item for item in paired_tests
        if item["split"] == "blind_oos"
        and item["policy"] == "borda_mean_rank"
        and item["control"] == "equal_family"
        and item["endpoint"] == "top5_hit_share"
    )
    primary_pass = (
        primary["mean_benefit_delta"] >= PRACTICAL_THRESHOLD
        and primary["bootstrap_ci_95"][0] > 0.0
        and primary["block_signflip_p_holm_48_tests"] < 0.05
    )
    decision = (
        "PRIMARY_BORDA_CONSENSUS_GATE_PASS_EXPLORATORY"
        if primary_pass else "NO_ROBUST_FORMULA_CONSENSUS_LIFT_DEMONSTRATED"
    )

    catalog_rows = formula_catalog_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    with CATALOG.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(catalog_rows[0]))
        writer.writeheader()
        writer.writerows(catalog_rows)

    ledger_fields = [
        "target_index", "target_offset", "target_date", "cutoff_date", "prior_draws",
        "split", "actual_quintet",
    ]
    for model in model_names:
        ledger_fields.extend([
            f"{model}_top5_hits", f"{model}_top10_hits",
            f"{model}_top20_hits", f"{model}_mean_actual_rank",
        ])
    ledger_fields.extend([
        "borda_mean_vote_count_in_top5", "borda_max_vote_count",
        "normalized_vote_entropy", "mean_family_top5_jaccard",
    ])
    with LEDGER.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger_fields)
        writer.writeheader()
        for row, diagnostic in zip(rows, diagnostic_rows):
            output = {
                "target_index": row["target_index"],
                "target_offset": row["target_offset"],
                "target_date": row["target_date"],
                "cutoff_date": row["cutoff_date"],
                "prior_draws": row["prior_draws"],
                "split": row["split"],
                "actual_quintet": " ".join(str(value + 1) for value in row["actual"]),
                "borda_mean_vote_count_in_top5": diagnostic["mean_top5_vote_count_among_borda_top5"],
                "borda_max_vote_count": diagnostic["max_top5_vote_count"],
                "normalized_vote_entropy": diagnostic["normalized_vote_entropy"],
                "mean_family_top5_jaccard": diagnostic["mean_pairwise_q80_family_top5_jaccard"],
            }
            for model in model_names:
                output[f"{model}_top5_hits"] = row[model]["top5_hits"]
                output[f"{model}_top10_hits"] = row[model]["top10_hits"]
                output[f"{model}_top20_hits"] = row[model]["top20_hits"]
                output[f"{model}_mean_actual_rank"] = row[model]["mean_rank"]
            writer.writerow(output)

    report = {
        "schema_version": "1.0",
        "task_id": "Q141-C3",
        "status": "EXECUTED_EXPLORATORY",
        "decision": decision,
        "hypothesis": prereg["hypothesis"],
        "source": {
            "archive_path": "data/storico_daily.csv",
            "git_blob_sha1": archive_blob_sha,
            "archive_sha256": sha256_bytes(raw),
            "eligible_draws": n,
            "first_date": dates[0],
            "last_date": dates[-1],
            "cutoff": "2026-11-10",
            "excluded_rows_after_cutoff": excluded,
            "contest_315_used": False,
        },
        "formula_sample": {
            "raw_sample_count": RAW_FORMULA_COUNT,
            "unique_canonical_formula_count": len(FORMULAS),
            "selection_seed": SEED,
            "one_vote_per_canonical_formula": True,
            "exhaustive_universe": False,
            "formula_ids": [formula["formula_id"] for formula in FORMULAS],
        },
        "walkforward": {
            "minimum_prior_history": base.MIN_HISTORY,
            "scored_targets": scored_targets,
            "split_counts": dict(actual_split_counts),
            "strict_prior": True,
            "update_order": "compute features and ranks for target i using draws[:i], score target, then append draw i to historical state",
            "blind_used_for_policy_selection": False,
        },
        "policies": {
            "borda_mean_rank": "rank ascending by mean candidate rank across 113 unique canonical formula IDs",
            "median_rank": "rank ascending by median candidate rank across 113 unique canonical formula IDs",
            "top5_vote": "rank descending by formula Top-5 vote count, ties by mean rank then ascending number",
            "controls": {
                "equal_family": "equal average of six Q80 family score vectors",
                "equal_feature": "equal average of 25 exact canonical Q80 feature columns",
            },
            "tie_policy": "ascending number for exact ties",
        },
        "metrics_by_split": metrics_by_split,
        "diagnostics": {
            split: {
                "mean_top5_vote_count_among_borda_top5": float(np.mean([
                    row["mean_top5_vote_count_among_borda_top5"]
                    for row in diagnostic_rows if row["split"] == split
                ])),
                "mean_normalized_vote_entropy": float(np.mean([
                    row["normalized_vote_entropy"]
                    for row in diagnostic_rows if row["split"] == split
                ])),
                "mean_pairwise_family_top5_jaccard": float(np.mean([
                    row["mean_pairwise_q80_family_top5_jaccard"]
                    for row in diagnostic_rows if row["split"] == split
                ])),
            }
            for split in ("discovery", "validation", "blind_oos")
        },
        "paired_inference": {
            "method": "non-overlapping chronological 20-target block sign-flip and circular moving-block bootstrap",
            "replicates": REPLICATES,
            "block_length": BLOCK_LENGTH,
            "holm_family_size": 48,
            "tests": paired_tests,
            "primary_test": primary,
            "primary_practical_threshold": PRACTICAL_THRESHOLD,
        },
        "uniform_exact_null": {
            "method": "exact convolution of Hypergeometric(40,k,5) per-target hit counts",
            "holm_family_size": 18,
            "tests": uniform_tests,
        },
        "acceptance": {
            "archive_blob_verified": True,
            "contest_315_excluded": True,
            "target_count_verified": True,
            "split_counts_verified": True,
            "formula_sample_deterministic": True,
            "formula_sample_raw_count": RAW_FORMULA_COUNT,
            "formula_sample_unique_count": len(FORMULAS),
            "target_cutoffs_strictly_prior": True,
            "feature_state_updated_after_scoring": True,
            "target_and_future_suffix_invariance": "covered by synthetic unit tests",
            "paired_test_count": len(paired_tests),
            "uniform_test_count": len(uniform_tests),
        },
        "limitations": [
            "The 113-formula sample is not exhaustive over the 9,808,263 canonical Q80 formulas.",
            "Formula ranks are dependent because the formulas share input features; they are not independent voters.",
            "The historical Blind OOS has prior SONAR research exposure and is not virgin prospective evidence.",
            "Holm correction covers only this preregistered 48-test paired family and 18-test uniform family, not all Q00-Q141 experimentation.",
            "No formula-level discovery winner is selected; all consensus policies are frozen before outcomes.",
            "A null result does not establish that every formula or family is useless.",
        ],
        "recovery_history": [
            {
                "run_id": 43272932529,
                "failed_stage": "exact_remote_git_readback",
                "computation_and_unit_tests": "passed",
                "artifact_upload_and_output_commit": "completed",
                "root_cause": "The first serialization wrote a literal backslash-n suffix after JSON documents, so the remote verifier rejected the manifest as extra trailing data.",
                "recovery": "Serialize actual newline characters, rerun the same frozen preregistered experiment, then verify remote JSON parsing and all manifest file SHA-256 values.",
            },
            {
                "run_id": 43273210888,
                "failed_stage": "independent_git_blob_identity_audit",
                "computation_unit_tests_and_sha256_remote_readback": "passed",
                "root_cause": "The Git blob helper escaped the header terminator as the two literal characters backslash-zero instead of a NUL byte; the SHA-256 checks were correct, but the manifest Git blob SHA-1 fields did not match GitHub blob IDs.",
                "recovery": "Use the actual NUL byte in the Git blob header, add a unit test against the canonical Git blob SHA-1 for b'abc', and verify each manifest Git blob SHA-1 with git rev-parse during remote readback.",
            },
            {
                "run_id": 43273673008,
                "failed_stage": "git_blob_helper_unit_test",
                "root_cause": "The first recovery patch did not insert the hashlib import because it matched an escaped newline rather than the source line; the test fixture already contained the correct NUL escape.",
                "recovery": "Insert the missing hashlib import by matching the literal import token and rerun the full deterministic workflow.",
            }
        ],
        "next_action": prereg["next_action"],
    }
    report_bytes = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode("utf-8")
    REPORT.write_bytes(report_bytes)

    files = {}
    for path in (CATALOG, LEDGER, REPORT, PREREG_JSON, PREREG_MD):
        data = path.read_bytes()
        files[str(path.relative_to(ROOT))] = {
            "bytes": len(data),
            "sha256": sha256_bytes(data),
            "git_blob_sha1": git_blob_sha1(data),
        }
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-C3",
        "status": "COMPUTED_LOCAL_PENDING_REMOTE_READBACK",
        "source_archive_git_blob_sha1": archive_blob_sha,
        "target_rows": len(rows),
        "split_counts": dict(actual_split_counts),
        "raw_formula_sample_count": RAW_FORMULA_COUNT,
        "unique_canonical_formula_count": len(FORMULAS),
        "paired_test_count": len(paired_tests),
        "paired_holm_family_size": 48,
        "uniform_test_count": len(uniform_tests),
        "uniform_holm_family_size": 18,
        "bootstrap_replicates": REPLICATES,
        "block_length": BLOCK_LENGTH,
        "deterministic_seed": SEED,
        "script_sha256": sha256_bytes(Path(__file__).read_bytes()),
        "test_sha256": sha256_bytes((ROOT / "tests" / "test_sonar_q141_formula_consensus.py").read_bytes()),
        "preregistration_json_sha256": sha256_bytes(PREREG_JSON.read_bytes()),
        "files": files,
        "decision": decision,
    }
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest_sha = sha256_bytes(MANIFEST.read_bytes())
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-C3",
        "status": "COMPUTED_PENDING_WORKFLOW_AND_REMOTE_GIT_READBACK",
        "manifest_path": str(MANIFEST.relative_to(ROOT)),
        "manifest_sha256": manifest_sha,
        "report_path": str(REPORT.relative_to(ROOT)),
        "report_sha256": files[str(REPORT.relative_to(ROOT))]["sha256"],
        "target_ledger_path": str(LEDGER.relative_to(ROOT)),
        "target_ledger_sha256": files[str(LEDGER.relative_to(ROOT))]["sha256"],
        "next_action": prereg["next_action"],
    }
    CHECKPOINT.write_text(json.dumps(checkpoint, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    for relative, expected in files.items():
        data = (ROOT / relative).read_bytes()
        if sha256_bytes(data) != expected["sha256"] or git_blob_sha1(data) != expected["git_blob_sha1"]:
            raise RuntimeError(f"Q141-C3_BLOCKED: local readback mismatch for {relative}")
    if sha256_bytes(MANIFEST.read_bytes()) != manifest_sha:
        raise RuntimeError("Q141-C3_BLOCKED: local manifest readback mismatch")

    print(json.dumps({
        "task_id": "Q141-C3",
        "decision": decision,
        "targets": len(rows),
        "splits": dict(actual_split_counts),
        "raw_formula_count": RAW_FORMULA_COUNT,
        "unique_formula_count": len(FORMULAS),
        "primary_test": primary,
        "report_sha256": files[str(REPORT.relative_to(ROOT))]["sha256"],
        "ledger_sha256": files[str(LEDGER.relative_to(ROOT))]["sha256"],
        "manifest_sha256": manifest_sha,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    run()
