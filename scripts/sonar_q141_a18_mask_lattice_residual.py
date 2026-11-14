#!/usr/bin/env python3
"""Q141-A18: residual spectral mapping after removing the Q7 mask-lattice design."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from sonar_q141_a17_full_universe_spectral import (
    CANDIDATES, FORMULAS, K, Q7_HEAD, TARGETS, WARMUP,
    apply_independent_circular_shifts, block_bootstrap_ci, csv_write,
    fit_basis, git_blob_sha1, holm_adjust, load_sources, project_capture,
    row_center_and_scale, sha256_bytes, split_slices, write_json,
)

DATE = "2026-11-14"
OUT_PREFIX = "q141_a18_mask_lattice_residual"
MASK_BITS = 10
MAIN_EFFECTS = 10
PAIR_EFFECTS = 45
DESIGN_COLUMNS = 56
RESIDUAL_DF = FORMULAS - DESIGN_COLUMNS
NULL_REPLICATES = 199
BOOTSTRAP_REPLICATES = 20000
BOOTSTRAP_BLOCK = 20
SEED_NULL = 1418001
SEED_BOOTSTRAP = 1418002
PRACTICAL_CAPTURE = 0.50
MIN_SUBSPACE_OVERLAP = 0.75
SPLIT_NAMES = ("discovery", "validation", "blind_oos")


def build_mask_design(formulas):
    masks = np.asarray([int(f["formula_mask"]) for f in formulas], dtype=np.int64)
    if masks.shape != (FORMULAS,) or not np.array_equal(masks, np.arange(1, FORMULAS + 1)):
        raise ValueError("A18_BLOCKED: formula masks must cover 1..1023 in order")
    bit_positions = np.arange(MASK_BITS, dtype=np.int64)
    bits = ((masks[:, None] >> bit_positions[None, :]) & 1).astype(np.float64)
    columns = [np.ones(FORMULAS, dtype=np.float64)]
    columns.extend(bits[:, j] for j in range(MASK_BITS))
    pairs = []
    for i in range(MASK_BITS):
        for j in range(i + 1, MASK_BITS):
            pair = bits[:, i] * bits[:, j]
            columns.append(pair)
            pairs.append((i + 1, j + 1))
    design = np.column_stack(columns)
    rank = int(np.linalg.matrix_rank(design))
    if design.shape != (FORMULAS, DESIGN_COLUMNS) or rank != DESIGN_COLUMNS:
        raise ValueError(f"A18_BLOCKED: mask design rank/shape mismatch {design.shape}/{rank}")
    q, _ = np.linalg.qr(design, mode="reduced")
    orthogonality_error = float(np.max(np.abs(q.T @ q - np.eye(DESIGN_COLUMNS))))
    if orthogonality_error > 1e-11:
        raise ValueError(f"A18_BLOCKED: QR orthogonality error {orthogonality_error}")
    meta = {
        "formula_masks": int(len(masks)),
        "family_bits": MASK_BITS,
        "main_effects": MAIN_EFFECTS,
        "pair_interactions": PAIR_EFFECTS,
        "intercept": 1,
        "design_columns": DESIGN_COLUMNS,
        "design_rank": rank,
        "residual_degrees_of_freedom": RESIDUAL_DF,
        "pair_order": [list(x) for x in pairs],
        "bit_order": "least-significant bit is feature-family 1; formula_mask is the 10-bit non-empty family subset",
        "qr_orthogonality_max_error": orthogonality_error,
    }
    return design, q, meta


def residualize_rows(matrix, q):
    x = np.asarray(matrix, dtype=np.float64)
    basis = np.asarray(q, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != basis.shape[0]:
        raise ValueError("residualize_rows expects rows × formula masks and matching design basis")
    return x - (x @ basis) @ basis.T


def residual_orthogonality_error(matrix, q):
    x = np.asarray(matrix, dtype=np.float64)
    return float(np.max(np.abs(x @ np.asarray(q, dtype=np.float64))))


def subspace_overlap(left, right):
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape or a.ndim != 2:
        raise ValueError("subspace overlap requires equal 2D basis shapes")
    k = a.shape[1]
    value = float(np.sum((a.T @ b) ** 2) / k)
    return min(1.0, max(0.0, value))


def split_training_window(split_slice, window=WARMUP):
    end = int(split_slice.start)
    start = end - int(window)
    if start < 0 or end - start != window:
        raise ValueError("A18_BLOCKED: insufficient strictly prior training window")
    return slice(start, end)


def fit_split_models(residual_matrix, raw_standardized, ranges):
    residual = np.asarray(residual_matrix, dtype=np.float64)
    raw = np.asarray(raw_standardized, dtype=np.float64)
    models = {}
    for name in SPLIT_NAMES:
        target_slice = ranges[name]
        train_slice = split_training_window(target_slice, WARMUP)
        if train_slice.stop > target_slice.start:
            raise ValueError(f"A18_BLOCKED: non-prior training window for {name}")
        train = residual[train_slice]
        basis, eigenvalues = fit_basis(train, K)
        captures = project_capture(residual[target_slice], basis)
        raw_basis, _ = fit_basis(raw[:WARMUP], K)
        raw_captures = project_capture(raw[target_slice], raw_basis)
        total = float(eigenvalues.sum())
        shares = eigenvalues / max(total, 1e-30)
        cumulative = np.cumsum(shares)
        k80 = int(np.searchsorted(cumulative, 0.80) + 1)
        models[name] = {
            "train_slice": train_slice,
            "target_slice": target_slice,
            "basis": basis,
            "eigenvalues": eigenvalues,
            "captures": captures,
            "raw_captures": raw_captures,
            "k80": k80,
            "top6_variance_share": float(cumulative[K - 1]),
            "training_rows": int(train.shape[0]),
        }
    return models


def conditional_shift_surrogates(residual_matrix, q, ranges, replicates=NULL_REPLICATES, seed=SEED_NULL):
    x = np.asarray(residual_matrix, dtype=np.float64)
    n, p = x.shape
    rng = np.random.default_rng(seed)
    null = {name: np.empty(replicates, dtype=np.float64) for name in SPLIT_NAMES}
    for b in range(replicates):
        shifts = rng.integers(1, n, size=p, dtype=np.int64)
        shifted = apply_independent_circular_shifts(x, shifts)
        shifted = residualize_rows(shifted, q)
        for name in SPLIT_NAMES:
            target_slice = ranges[name]
            train_slice = split_training_window(target_slice, WARMUP)
            basis, _ = fit_basis(shifted[train_slice], K)
            null[name][b] = float(project_capture(shifted[target_slice], basis).mean())
        if (b + 1) % 25 == 0:
            print(f"A18_CONDITIONAL_NULL_PROGRESS {b + 1}/{replicates}", flush=True)
    return null


def upper_tail_p(observed, null_values):
    null = np.asarray(null_values, dtype=np.float64)
    return float((1 + np.sum(null >= float(observed))) / (len(null) + 1))


def k80_from_eigenvalues(eigenvalues):
    values = np.asarray(eigenvalues, dtype=np.float64)
    shares = values / max(float(values.sum()), 1e-30)
    return int(np.searchsorted(np.cumsum(shares), 0.80) + 1)


def build_report(ranks, dates, cutoffs, actuals, formulas, lineage, out, seed_offset=0):
    if ranks.shape != (TARGETS, FORMULAS) or not np.isfinite(ranks).all():
        raise SystemExit("A18_BLOCKED: full rank matrix shape/finite check failed")
    design, q, design_meta = build_mask_design(formulas)
    raw_z, train_means, train_scales = row_center_and_scale(ranks, WARMUP)
    residual = residualize_rows(raw_z, q)
    orth_error = residual_orthogonality_error(residual, q)
    if orth_error > 1e-9:
        raise SystemExit(f"A18_BLOCKED: residual projection error {orth_error}")

    # Strict-prior invariance: the scaler and Discovery basis use only the first 400 rows.
    mutated = np.asarray(ranks).copy()
    rng_mut = np.random.default_rng(1418000 + seed_offset)
    mutated[WARMUP:] = rng_mut.integers(1, CANDIDATES + 1, size=mutated[WARMUP:].shape, dtype=np.int32)
    mutated_z, mutated_means, mutated_scales = row_center_and_scale(mutated, WARMUP)
    mutated_residual = residualize_rows(mutated_z, q)
    scaler_invariance = bool(np.array_equal(train_means, mutated_means) and np.array_equal(train_scales, mutated_scales))
    discovery_basis, _ = fit_basis(residual[:WARMUP], K)
    mutated_discovery_basis, _ = fit_basis(mutated_residual[:WARMUP], K)
    future_suffix_invariance = bool(np.array_equal(discovery_basis, mutated_discovery_basis))
    if not scaler_invariance or not future_suffix_invariance:
        raise SystemExit("A18_BLOCKED: future suffix changed training scaler or Discovery basis")

    ranges = split_slices(TARGETS - WARMUP)
    expected_counts = {"discovery": 1792, "validation": 597, "blind_oos": 597}
    counts = {name: int(ranges[name].stop - ranges[name].start) for name in SPLIT_NAMES}
    if counts != expected_counts:
        raise SystemExit(f"A18_BLOCKED: split count mismatch {counts}")

    models = fit_split_models(residual, raw_z, ranges)
    overlaps = {
        "discovery_to_validation": subspace_overlap(models["discovery"]["basis"], models["validation"]["basis"]),
        "validation_to_blind_oos": subspace_overlap(models["validation"]["basis"], models["blind_oos"]["basis"]),
        "discovery_to_blind_oos": subspace_overlap(models["discovery"]["basis"], models["blind_oos"]["basis"]),
    }

    null = conditional_shift_surrogates(residual, q, ranges, NULL_REPLICATES, SEED_NULL + seed_offset)
    primary_names = ["validation", "blind_oos"]
    raw_p = [upper_tail_p(float(models[name]["captures"].mean()), null[name]) for name in primary_names]
    adjusted_p = holm_adjust(raw_p)
    p_map = {name: {"raw": raw_p[i], "holm": float(adjusted_p[i])} for i, name in enumerate(primary_names)}

    split_metrics = {}
    eigen_rows = []
    loading_obj = {"experiment_id": "Q141-A18", "formula_count": FORMULAS, "design_rank": DESIGN_COLUMNS, "residual_dimensions": RESIDUAL_DF, "k": K, "splits": []}
    for split_index, name in enumerate(SPLIT_NAMES):
        model = models[name]
        captures = model["captures"]
        null_values = null[name]
        ci = block_bootstrap_ci(captures, SEED_BOOTSTRAP + seed_offset + split_index, BOOTSTRAP_REPLICATES, BOOTSTRAP_BLOCK)
        null_q99 = float(np.quantile(null_values, 0.99))
        split_metrics[name] = {
            "targets": int(len(captures)),
            "training_window_rows": model["training_rows"],
            "training_window_start_index_zero_based": int(model["train_slice"].start),
            "training_window_end_index_exclusive": int(model["train_slice"].stop),
            "training_window_last_target_date": dates[model["train_slice"].stop - 1],
            "first_evaluated_target_date": dates[model["target_slice"].start],
            "last_evaluated_target_date": dates[model["target_slice"].stop - 1],
            "mean_residual_capture_k6": float(captures.mean()),
            "median_residual_capture_k6": float(np.median(captures)),
            "bootstrap_95_ci_block20": ci,
            "conditional_shift_null_mean": float(null_values.mean()),
            "conditional_shift_null_q95": float(np.quantile(null_values, 0.95)),
            "conditional_shift_null_q99": null_q99,
            "conditional_shift_exceedances": int(np.sum(null_values >= captures.mean())),
            "conditional_shift_p_raw": p_map.get(name, {}).get("raw"),
            "conditional_shift_p_holm": p_map.get(name, {}).get("holm"),
            "raw_a17_fixed_basis_capture": float(model["raw_captures"].mean()),
            "training_k80": int(model["k80"]),
            "training_top6_variance_share": float(model["top6_variance_share"]),
        }
        values = model["eigenvalues"]
        total = float(values.sum())
        cumulative = np.cumsum(values / max(total, 1e-30))
        for idx, value in enumerate(values):
            eigen_rows.append({
                "split": name,
                "component": idx + 1,
                "eigenvalue": float(value),
                "variance_share": float(value / max(total, 1e-30)),
                "cumulative_share": float(cumulative[idx]),
            })
        order = np.argsort(-np.abs(model["basis"]), axis=0)
        components = []
        for c in range(K):
            top = []
            for idx in order[:25, c]:
                formula = formulas[int(idx)]
                loading = float(model["basis"][int(idx), c])
                top.append({
                    "formula_id": formula["formula_id"],
                    "formula_mask": int(formula["formula_mask"]),
                    "feature_count": int(formula["feature_count"]),
                    "features": formula["features"],
                    "loading": loading,
                    "absolute_loading": abs(loading),
                })
            components.append({"component": c + 1, "top_loadings": top})
        loading_obj["splits"].append({"split": name, "components": components})

    holdout_pass = all(
        split_metrics[name]["mean_residual_capture_k6"] >= PRACTICAL_CAPTURE
        and p_map[name]["holm"] < 0.05
        and split_metrics[name]["mean_residual_capture_k6"] > split_metrics[name]["conditional_shift_null_q99"]
        for name in primary_names
    )
    overlap_pass = (
        overlaps["discovery_to_validation"] >= MIN_SUBSPACE_OVERLAP
        and overlaps["validation_to_blind_oos"] >= MIN_SUBSPACE_OVERLAP
    )
    decision = (
        "MASK_LATTICE_RESIDUAL_SIX_DIMENSIONAL_STRUCTURE_SUPPORTED_EXPLORATORY"
        if holdout_pass and overlap_pass
        else "MASK_LATTICE_RESIDUAL_STRUCTURE_NOT_CONFIRMED"
    )

    ledger_rows = []
    captures_by_split = {}
    for name in SPLIT_NAMES:
        sl = models[name]["target_slice"]
        for offset, global_idx in enumerate(range(sl.start, sl.stop)):
            captures_by_split[global_idx] = (name, float(models[name]["captures"][offset]), float(models[name]["raw_captures"][offset]))
    for global_idx in sorted(captures_by_split):
        name, capture, raw_capture = captures_by_split[global_idx]
        ledger_rows.append({
            "target_index": global_idx + 1,
            "target_date": dates[global_idx],
            "cutoff_date": cutoffs[global_idx],
            "prior_draws": global_idx + 1,
            "actual_quintet": actuals[global_idx],
            "split": name,
            "basis_train_start_index_zero_based": models[name]["train_slice"].start,
            "basis_train_end_index_exclusive": models[name]["train_slice"].stop,
            "basis_training_rows": WARMUP,
            "raw_a17_fixed_basis_capture": f"{raw_capture:.12f}",
            "a18_mask_residual_capture": f"{capture:.12f}",
            "strict_prior": "true",
        })
    if len(ledger_rows) != TARGETS - WARMUP:
        raise SystemExit("A18_BLOCKED: target ledger row count mismatch")
    if any(r["cutoff_date"] >= r["target_date"] for r in ledger_rows):
        raise SystemExit("A18_BLOCKED: non-strict cutoff in target ledger")

    null_rows = []
    for b in range(NULL_REPLICATES):
        null_rows.append({"replicate": b + 1, **{name: f"{float(null[name][b]):.12f}" for name in SPLIT_NAMES}})
    eigen_path = out / f"{OUT_PREFIX}_training_eigenvalues_{DATE}.csv"
    csv_write(eigen_path, ["split", "component", "eigenvalue", "variance_share", "cumulative_share"], eigen_rows)
    ledger_path = out / f"{OUT_PREFIX}_target_ledger_{DATE}.csv"
    csv_write(ledger_path, list(ledger_rows[0].keys()), ledger_rows)
    null_path = out / f"{OUT_PREFIX}_conditional_shift_null_{DATE}.csv"
    csv_write(null_path, ["replicate", "discovery", "validation", "blind_oos"], null_rows)
    loadings_path = out / f"{OUT_PREFIX}_component_loadings_{DATE}.json"
    write_json(loadings_path, loading_obj)
    source_path = out / f"{OUT_PREFIX}_source_lineage_{DATE}.json"
    write_json(source_path, lineage)

    report = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A18",
        "status": "COMPLETED_HISTORICAL_PREQUENTIAL_MASK_RESIDUAL_TEST",
        "decision": decision,
        "hypothesis": {
            "primary": "After removing the intercept, 10 mask-family main effects and 45 pair interactions, a six-dimensional residual subspace captures at least 0.50 of residual energy in both Validation and historical Blind OOS, exceeds the conditional shift null after Holm correction, and remains stable across adjacent splits.",
            "practical_capture_threshold": PRACTICAL_CAPTURE,
            "minimum_adjacent_subspace_overlap": MIN_SUBSPACE_OVERLAP,
            "holdout_pass": bool(holdout_pass),
            "overlap_pass": bool(overlap_pass),
        },
        "source": lineage,
        "design": {
            "target_rows": TARGETS,
            "formula_count": FORMULAS,
            "candidate_universe_size": CANDIDATES,
            "warmup_targets": WARMUP,
            "evaluated_targets": TARGETS - WARMUP,
            "split_counts": counts,
            "k": K,
            "split_training_window": WARMUP,
            "mask_lattice": design_meta,
            "null_replicates": NULL_REPLICATES,
            "null_seed": SEED_NULL + seed_offset,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_block_length": BOOTSTRAP_BLOCK,
            "bootstrap_seed_base": SEED_BOOTSTRAP + seed_offset,
            "primary_multiple_testing": "Holm across Validation and historical Blind OOS conditional circular-shift upper-tail tests",
        },
        "preprocessing": {
            "rank_normalization": "(rank-1)/658007",
            "row_centering": "subtract per-target median across all 1,023 masks",
            "column_scaling": "mean and sample standard deviation from the first 400 target rows only; frozen for all splits",
            "mask_design": "intercept + 10 binary family indicators + 45 pairwise products; masks 1..1023 in fixed bit order",
            "residualization": "per target row, project standardized rank profile onto orthogonal complement of the 56-column mask design",
            "basis": "top six right-singular vectors fitted separately for each split on the 400 target rows immediately preceding that split",
            "conditional_null": "independent circular shift of each residual mask trajectory, followed by row-wise projection back into the mask-lattice residual space",
        },
        "split_metrics": split_metrics,
        "subspace_overlaps": overlaps,
        "primary_p_values": p_map,
        "integrity": {
            "source_lineage_verified": True,
            "all_3386_target_rows_reconciled": True,
            "all_1023_formula_masks_reconciled": True,
            "strict_prior_cutoffs": True,
            "split_specific_basis_uses_immediately_prior_400_rows": True,
            "future_suffix_invariance": future_suffix_invariance,
            "training_scaler_uses_first_400_rows_only": scaler_invariance,
            "mask_design_rank_56": design_meta["design_rank"] == DESIGN_COLUMNS,
            "residual_projection_max_error": orth_error,
            "conditional_null_reprojects_to_mask_residual_space": True,
            "deterministic_seeded_null": True,
            "full_replay_byte_identity": "PENDING_WORKFLOW_REPLAY",
        },
        "interpretation": "This is a structural decomposition of historical formula-rank outcome profiles after removing mask-lattice intercept, main effects and pair interactions. It does not forecast candidate numbers or the exact quintet and does not establish predictive skill.",
        "limitations": [
            "The Q7 source archive is pinned through 2026-10-24 and is separate from current main through 2026-11-13.",
            "Historical Blind OOS is not virgin prospective evidence and overlaps prior SONAR exploration.",
            "The 10-family mask grammar is finite and does not enumerate all possible mathematical formulas.",
            "Residualization removes only the registered intercept, 10 main effects and 45 pairwise mask terms; higher-order mask structure remains.",
            "The conditional null preserves each residual column's circular temporal sequence before row-wise re-projection; re-projection changes exact marginal/autocorrelation properties.",
            "The null has 199 replicates, so its minimum attainable raw p-value is 0.005.",
            "Rank profiles describe the realized target after the fact; this is not a candidate-number probability model.",
        ],
    }
    report_path = out / f"{OUT_PREFIX}_report_{DATE}.json"
    write_json(report_path, report)
    md = [
        "# Q141-A18 — Mask-Lattice Residual Spectral Mapping",
        "",
        f"**Status:** {report['status']}",
        f"**Decision:** {decision}",
        "",
        "## Frozen hypothesis",
        "",
        f"After removing the intercept, 10 family main effects and 45 pair interactions, the six-dimensional residual subspace must capture at least {PRACTICAL_CAPTURE:.2f} in both holdouts, beat the conditional null after Holm correction, and retain adjacent subspace overlap >= {MIN_SUBSPACE_OVERLAP:.2f}.",
        "",
        "## Mask-lattice design",
        "",
        f"- Formula masks: {FORMULAS:,}; design columns/rank: {DESIGN_COLUMNS}/{design_meta['design_rank']}; residual dimensions: {RESIDUAL_DF}.",
        "- Design: intercept + 10 family indicators + 45 pairwise products.",
        "- Each split basis is fitted on exactly the 400 targets immediately preceding that split.",
        "",
        "## Results",
        "",
        "| Split | Targets | Residual capture k6 | 95% block CI | Conditional null mean | Null q99 | k80 |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name in SPLIT_NAMES:
        m = split_metrics[name]
        md.append(f"| {name} | {m['targets']} | {m['mean_residual_capture_k6']:.6f} | [{m['bootstrap_95_ci_block20'][0]:.6f}, {m['bootstrap_95_ci_block20'][1]:.6f}] | {m['conditional_shift_null_mean']:.6f} | {m['conditional_shift_null_q99']:.6f} | {m['training_k80']} |")
    md += [
        "",
        "## Primary holdout tests",
        "",
        "| Holdout | Raw p | Holm p |",
        "|---|---:|---:|",
    ]
    for name in primary_names:
        md.append(f"| {name} | {p_map[name]['raw']:.6f} | {p_map[name]['holm']:.6f} |")
    md += [
        "",
        "## Subspace stability",
        "",
        f"- Discovery → Validation: {overlaps['discovery_to_validation']:.6f}",
        f"- Validation → Blind OOS: {overlaps['validation_to_blind_oos']:.6f}",
        f"- Discovery → Blind OOS: {overlaps['discovery_to_blind_oos']:.6f}",
        "",
        "## Limits",
        "",
        "This is a structural decomposition of realized rank profiles, not a forecast. The historical Blind OOS is not virgin prospective evidence. The conditional shift null preserves each residual column's circular sequence before row-wise re-projection, so it is a defined surrogate rather than a universal null.",
        "",
    ]
    report_md_path = out / f"{OUT_PREFIX}_report_{DATE}.md"
    report_md_path.write_text("\n".join(md), encoding="utf-8")

    outputs = [report_path, report_md_path, ledger_path, null_path, eigen_path, loadings_path, source_path]
    output_info = {}
    for path in outputs:
        raw = path.read_bytes()
        output_info[path.name] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    manifest = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A18",
        "status": "COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
        "q7_head": Q7_HEAD,
        "outputs": output_info,
    }
    manifest_path = out / f"{OUT_PREFIX}_manifest_{DATE}.json"
    write_json(manifest_path, manifest)
    checkpoint = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A18",
        "status": "COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
        "decision": decision,
        "q7_head": Q7_HEAD,
        "target_rows": TARGETS,
        "formula_count": FORMULAS,
        "evaluated_targets": TARGETS - WARMUP,
        "split_counts": counts,
        "design_rank": DESIGN_COLUMNS,
        "residual_dimensions": RESIDUAL_DF,
        "null_replicates": NULL_REPLICATES,
        "next_action": "Verify dedicated CI, full replay and remote Git readback; then request human review without merge or promotion.",
    }
    checkpoint_path = out / f"{OUT_PREFIX}_checkpoint_{DATE}.json"
    write_json(checkpoint_path, checkpoint)
    print("A18_COMPUTE_COMPLETE", json.dumps({
        "decision": decision,
        "split_metrics": {name: split_metrics[name]["mean_residual_capture_k6"] for name in SPLIT_NAMES},
        "primary_p": p_map,
        "subspace_overlaps": overlaps,
        "outputs": len(output_info),
    }, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="q7-source")
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ranks, dates, cutoffs, actuals, formulas, lineage = load_sources(Path(args.source_dir))
    build_report(ranks, dates, cutoffs, actuals, formulas, lineage, out, args.seed_offset)


if __name__ == "__main__":
    main()
