#!/usr/bin/env python3
"""Q141-A17: prequential six-component spectral test on all 1,023 Q7 formulas."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np

Q7_BRANCH = "research/exhaustive-formula-catalog-20261025"
Q7_HEAD = "7a37cab601c5f9386131a00246963f8e4aeabf74"
WALK_MANIFEST_BLOB = "aae2c7768c9d37bf633a13939f2b686bcce83a27"
CATALOG_MANIFEST_BLOB = "5cdf9c24431ea23b2176aa6a19133b7f4435980c"
ARCHIVE_BLOB = "7dab05ba49ace909fe8783eef729605049c65e50"
FORMULAS = 1023
DRAWS = 3387
TARGETS = 3386
CANDIDATES = 658008
WARMUP = 400
K = 6
NULL_REPLICATES = 199
BOOTSTRAP_REPLICATES = 20000
BLOCK = 20
SEED_NULL = 1417001
SEED_BOOTSTRAP = 1417002
PRACTICAL_CAPTURE = 0.75
DATE = "2026-11-14"
OUT_PREFIX = "q141_a17_full_universe_spectral"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()

def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def read_archive(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows or [x.strip().lower() for x in rows[0][:6]] not in (
        ["data", "n1", "n2", "n3", "n4", "n5"],
        ["date", "n1", "n2", "n3", "n4", "n5"],
    ):
        raise ValueError("A17_BLOCKED: unexpected pinned archive header")
    dates, draws = [], []
    previous = ""
    seen = set()
    for line, row in enumerate(rows[1:], 2):
        if not row or not any(x.strip() for x in row):
            continue
        date = row[0].strip()
        numbers = tuple(int(x) for x in row[1:6])
        if date in seen or (previous and date <= previous):
            raise ValueError(f"A17_BLOCKED: duplicate/nonchronological archive date at line {line}")
        if len(numbers) != 5 or len(set(numbers)) != 5 or numbers != tuple(sorted(numbers)):
            raise ValueError(f"A17_BLOCKED: invalid quintet at archive line {line}")
        if any(x < 1 or x > 40 for x in numbers):
            raise ValueError(f"A17_BLOCKED: out-of-range number at archive line {line}")
        dates.append(date)
        draws.append(numbers)
        seen.add(date)
        previous = date
    return dates, draws

def validate_alignment(row_index, target_date, cutoff_date, prior_draws, actual_quintet, dates, draws):
    expected_actual = " ".join(str(x) for x in draws[row_index + 1])
    actual = " ".join(str(x) for x in sorted(int(x) for x in actual_quintet.split()))
    return (
        int(prior_draws) == row_index + 1
        and cutoff_date == dates[row_index]
        and target_date == dates[row_index + 1]
        and actual == expected_actual
        and cutoff_date < target_date
    )

def load_sources(source_dir: Path):
    archive_path = source_dir / "data/storico_daily.csv"
    walk_path = source_dir / "reports/sequence_agent/exhaustive_formula_walkforward_manifest.json"
    catalog_path = source_dir / "reports/sequence_agent/exhaustive_formula_catalog_manifest.json"
    for p in (archive_path, walk_path, catalog_path):
        if not p.is_file():
            raise ValueError(f"A17_BLOCKED: missing pinned source {p}")
    archive_bytes = archive_path.read_bytes()
    walk_bytes = walk_path.read_bytes()
    catalog_bytes = catalog_path.read_bytes()
    if git_blob_sha1(archive_bytes) != ARCHIVE_BLOB:
        raise ValueError("A17_BLOCKED: pinned Q7 archive Git blob mismatch")
    if git_blob_sha1(walk_bytes) != WALK_MANIFEST_BLOB:
        raise ValueError("A17_BLOCKED: Q7 walk-forward manifest Git blob mismatch")
    if git_blob_sha1(catalog_bytes) != CATALOG_MANIFEST_BLOB:
        raise ValueError("A17_BLOCKED: Q7 formula catalog manifest Git blob mismatch")

    dates, draws = read_archive(archive_path)
    if len(draws) != DRAWS or dates[0] != "2017-07-17" or dates[-1] != "2026-10-24":
        raise ValueError("A17_BLOCKED: pinned Q7 archive count/date mismatch")

    walk = json.loads(walk_bytes)
    catalog = json.loads(catalog_bytes)
    if walk.get("status") != "VALIDATED_COMPLETE":
        raise ValueError("A17_BLOCKED: Q7 walk-forward source is not VALIDATED_COMPLETE")
    if (walk.get("target_count"), walk.get("scored_target_count"), walk.get("formula_count"), walk.get("candidate_universe_size")) != (DRAWS, TARGETS, FORMULAS, CANDIDATES):
        raise ValueError("A17_BLOCKED: Q7 walk-forward manifest dimensions mismatch")
    if catalog.get("status") != "EXHAUSTIVE_FINITE_GRAMMAR_COMPLETE" or catalog.get("formula_count") != FORMULAS:
        raise ValueError("A17_BLOCKED: Q7 catalog manifest identity mismatch")

    rank_names = [f"rank_mask_{i:04d}" for i in range(1, FORMULAS + 1)]
    matrix = np.empty((TARGETS, FORMULAS), dtype=np.int32)
    target_dates, cutoff_dates, actuals = [], [], []
    part_lineage = []
    row_index = 0
    for part in walk["parts"]:
        p = source_dir / part["path"]
        if not p.is_file():
            raise ValueError(f"A17_BLOCKED: missing ledger part {part['path']}")
        raw = p.read_bytes()
        if sha256_bytes(raw) != part["sha256"]:
            raise ValueError(f"A17_BLOCKED: Q7 part SHA-256 mismatch {part['path']}")
        with p.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected_header = ["target_date", "cutoff_date", "prior_draws", "actual_quintet", "status"] + rank_names
            if reader.fieldnames != expected_header:
                raise ValueError(f"A17_BLOCKED: rank column order/header mismatch in {part['path']}")
            part_rows = 0
            for row in reader:
                if row_index >= TARGETS:
                    raise ValueError("A17_BLOCKED: excess Q7 ledger rows")
                if not validate_alignment(
                    row_index, row["target_date"], row["cutoff_date"], row["prior_draws"],
                    row["actual_quintet"], dates, draws
                ):
                    raise ValueError(f"A17_BLOCKED: strict-prior/date/outcome reconciliation failed at row {row_index}")
                values = np.fromiter((int(row[name]) for name in rank_names), dtype=np.int32, count=FORMULAS)
                if values.shape != (FORMULAS,) or np.any(values < 1) or np.any(values > CANDIDATES):
                    raise ValueError(f"A17_BLOCKED: invalid formula rank at target row {row_index}")
                matrix[row_index] = values
                target_dates.append(row["target_date"])
                cutoff_dates.append(row["cutoff_date"])
                actuals.append(row["actual_quintet"])
                row_index += 1
                part_rows += 1
            if part_rows != part["data_rows"]:
                raise ValueError(f"A17_BLOCKED: row count mismatch in {part['path']}")
        part_lineage.append({
            "path": part["path"],
            "data_rows": part_rows,
            "sha256": sha256_bytes(raw),
            "git_blob_sha1": git_blob_sha1(raw),
        })
    if row_index != TARGETS:
        raise ValueError(f"A17_BLOCKED: expected {TARGETS} target rows, got {row_index}")

    formulas_by_mask = {}
    catalog_lineage = []
    for item in catalog["storage_layout"]["formulas_stored_in_parts"]:
        p = source_dir / item["path"]
        if not p.is_file():
            raise ValueError(f"A17_BLOCKED: missing formula catalog chunk {item['path']}")
        raw = p.read_bytes()
        chunk = json.loads(raw)
        formulas = chunk.get("formulas", [])
        if len(formulas) != item["formula_count"]:
            raise ValueError(f"A17_BLOCKED: formula chunk count mismatch {item['path']}")
        for formula in formulas:
            mask = int(formula["formula_mask"])
            features = formula.get("features", [])
            if mask in formulas_by_mask or int(formula["feature_count"]) != len(features):
                raise ValueError(f"A17_BLOCKED: duplicate or inconsistent formula mask {mask}")
            formulas_by_mask[mask] = {
                "formula_id": formula["formula_id"],
                "formula_mask": mask,
                "feature_count": int(formula["feature_count"]),
                "features": features,
            }
        catalog_lineage.append({
            "path": item["path"],
            "formula_count": len(formulas),
            "git_blob_sha1": git_blob_sha1(raw),
            "sha256": sha256_bytes(raw),
        })
    if set(formulas_by_mask) != set(range(1, FORMULAS + 1)):
        raise ValueError("A17_BLOCKED: formula catalog does not cover masks 1..1023 exactly")

    formulas = [formulas_by_mask[i] for i in range(1, FORMULAS + 1)]
    lineage = {
        "q7_branch": Q7_BRANCH,
        "q7_commit": Q7_HEAD,
        "archive": {
            "path": "data/storico_daily.csv",
            "git_blob_sha1": git_blob_sha1(archive_bytes),
            "sha256": sha256_bytes(archive_bytes),
            "draws": len(draws),
            "first_date": dates[0],
            "last_date": dates[-1],
        },
        "walkforward_manifest": {
            "path": "reports/sequence_agent/exhaustive_formula_walkforward_manifest.json",
            "git_blob_sha1": git_blob_sha1(walk_bytes),
            "sha256": sha256_bytes(walk_bytes),
        },
        "catalog_manifest": {
            "path": "reports/sequence_agent/exhaustive_formula_catalog_manifest.json",
            "git_blob_sha1": git_blob_sha1(catalog_bytes),
            "sha256": sha256_bytes(catalog_bytes),
        },
        "ledger_parts": part_lineage,
        "formula_catalog_chunks": catalog_lineage,
        "target_rows": row_index,
        "formula_count": len(formulas),
        "candidate_universe_size": CANDIDATES,
    }
    return matrix, target_dates, cutoff_dates, actuals, formulas, lineage

def row_center_and_scale(ranks: np.ndarray, train_rows: int = WARMUP):
    normalized = (np.asarray(ranks, dtype=np.float64) - 1.0) / float(CANDIDATES - 1)
    centered = normalized - np.median(normalized, axis=1, keepdims=True)
    train = centered[:train_rows]
    means = train.mean(axis=0)
    scales = train.std(axis=0, ddof=1)
    scales[scales < 1e-12] = 1.0
    standardized = (centered - means) / scales
    return standardized, means, scales

def fit_basis(train_matrix: np.ndarray, k: int = K):
    x = np.asarray(train_matrix, dtype=np.float64)
    if x.ndim != 2 or x.shape[0] < k or x.shape[1] < k:
        raise ValueError("fit_basis requires a 2D matrix with both dimensions >= k")
    _, singular, vt = np.linalg.svd(x, full_matrices=False)
    basis = vt[:k].T.copy()
    for component in range(k):
        pivot = int(np.argmax(np.abs(basis[:, component])))
        if basis[pivot, component] < 0:
            basis[:, component] *= -1.0
    eigenvalues = (singular ** 2) / max(1, x.shape[0] - 1)
    return basis, eigenvalues

def project_capture(matrix: np.ndarray, basis: np.ndarray):
    x = np.asarray(matrix, dtype=np.float64)
    u = np.asarray(basis, dtype=np.float64)
    denominator = np.sum(x * x, axis=1)
    numerator = np.sum((x @ u) ** 2, axis=1)
    out = np.zeros(x.shape[0], dtype=np.float64)
    valid = denominator > 1e-20
    out[valid] = numerator[valid] / denominator[valid]
    return np.clip(out, 0.0, 1.0)

def split_slices(n_eval: int):
    discovery = int(round(n_eval * 0.60))
    validation = int(round(n_eval * 0.20))
    blind = n_eval - discovery - validation
    start = WARMUP
    return {
        "discovery": slice(start, start + discovery),
        "validation": slice(start + discovery, start + discovery + validation),
        "blind_oos": slice(start + discovery + validation, start + n_eval),
    }

def holm_adjust(p_values):
    p = np.asarray(p_values, dtype=np.float64)
    order = np.argsort(p, kind="mergesort")
    adjusted = np.empty_like(p)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (len(p) - rank) * p[idx]))
        adjusted[idx] = running
    return adjusted.tolist()

def block_bootstrap_ci(values, seed, replicates=BOOTSTRAP_REPLICATES, block=BLOCK):
    x = np.asarray(values, dtype=np.float64)
    n = len(x)
    if n == 0:
        raise ValueError("bootstrap requires non-empty values")
    rng = np.random.default_rng(seed)
    blocks = int(math.ceil(n / block))
    offsets = np.arange(block, dtype=np.int64)
    samples = np.empty(replicates, dtype=np.float64)
    for start in range(0, replicates, 250):
        batch = min(250, replicates - start)
        starts = rng.integers(0, n, size=(batch, blocks))
        indices = (starts[:, :, None] + offsets[None, None, :]) % n
        flat = indices.reshape(batch, -1)[:, :n]
        samples[start:start + batch] = x[flat].mean(axis=1)
    return [float(v) for v in np.quantile(samples, [0.025, 0.975])]

def apply_independent_circular_shifts(matrix, shifts):
    x = np.asarray(matrix, dtype=np.float64)
    shifts = np.asarray(shifts, dtype=np.int64)
    if x.ndim != 2 or shifts.shape != (x.shape[1],):
        raise ValueError("circular shifts require one offset per matrix column")
    indices = (np.arange(x.shape[0], dtype=np.int64)[:, None] - shifts[None, :]) % x.shape[0]
    return np.take_along_axis(x, indices, axis=0)

def circular_shift_surrogates(centered, split_ranges, replicates=NULL_REPLICATES, seed=SEED_NULL):
    x = np.asarray(centered, dtype=np.float64)
    n, p = x.shape
    rng = np.random.default_rng(seed)
    null = {name: np.empty(replicates, dtype=np.float64) for name in split_ranges}
    for b in range(replicates):
        shifts = rng.integers(1, n, size=p, dtype=np.int64)
        shifted = apply_independent_circular_shifts(x, shifts)
        shifted = shifted - np.median(shifted, axis=1, keepdims=True)
        train = shifted[:WARMUP]
        means = train.mean(axis=0)
        scales = train.std(axis=0, ddof=1)
        scales[scales < 1e-12] = 1.0
        z = (shifted - means) / scales
        basis, _ = fit_basis(z[:WARMUP], K)
        captures = project_capture(z[WARMUP:], basis)
        for name, sl in split_ranges.items():
            lo = sl.start - WARMUP
            hi = sl.stop - WARMUP
            null[name][b] = float(captures[lo:hi].mean())
        if (b + 1) % 25 == 0:
            print(f"A17_NULL_PROGRESS {b + 1}/{replicates}", flush=True)
    return null

def csv_write(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", default="q7-source")
    parser.add_argument("--out-dir", default="reports/sequence_agent")
    args = parser.parse_args()
    source_dir = Path(args.source_dir)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    ranks, dates, cutoffs, actuals, formulas, lineage = load_sources(source_dir)
    if ranks.shape != (TARGETS, FORMULAS) or not np.isfinite(ranks).all():
        raise SystemExit("A17_BLOCKED: full rank matrix shape/finite check failed")

    z, train_means, train_scales = row_center_and_scale(ranks, WARMUP)
    basis, eigenvalues = fit_basis(z[:WARMUP], K)
    if basis.shape != (FORMULAS, K):
        raise SystemExit("A17_BLOCKED: PCA basis shape mismatch")
    orthogonality_error = float(np.max(np.abs(basis.T @ basis - np.eye(K))))
    if orthogonality_error > 1e-10:
        raise SystemExit(f"A17_BLOCKED: basis orthogonality error {orthogonality_error}")

    # Future-suffix invariance: only the first 400 rows are passed to the fitter.
    mutated = z.copy()
    mutated[WARMUP:] = mutated[WARMUP:] * -3.0 + 17.0
    basis_mutated, _ = fit_basis(mutated[:WARMUP], K)
    future_suffix_invariance = bool(np.array_equal(basis, basis_mutated))
    if not future_suffix_invariance:
        raise SystemExit("A17_BLOCKED: future suffix changed the fitted training basis")

    n_eval = TARGETS - WARMUP
    ranges = split_slices(n_eval)
    counts = {name: sl.stop - sl.start for name, sl in ranges.items()}
    if counts != {"discovery": 1792, "validation": 597, "blind_oos": 597}:
        raise SystemExit(f"A17_BLOCKED: unexpected split counts {counts}")

    all_captures = project_capture(z[WARMUP:], basis)
    split_captures = {}
    for name, sl in ranges.items():
        split_captures[name] = all_captures[sl.start - WARMUP:sl.stop - WARMUP]
    null = circular_shift_surrogates(
        z,
        ranges,
        NULL_REPLICATES,
        SEED_NULL,
    )
    primary_names = ["validation", "blind_oos"]
    raw_p = []
    for name in primary_names:
        observed = float(split_captures[name].mean())
        raw_p.append(float((1 + np.sum(null[name] >= observed)) / (NULL_REPLICATES + 1)))
    adjusted_p = holm_adjust(raw_p)
    p_map = {name: {"raw": raw_p[i], "holm": adjusted_p[i]} for i, name in enumerate(primary_names)}

    split_metrics = {}
    for i, name in enumerate(("discovery", "validation", "blind_oos")):
        values = split_captures[name]
        null_values = null[name]
        split_metrics[name] = {
            "targets": int(len(values)),
            "mean_capture_k6": float(values.mean()),
            "median_capture_k6": float(np.median(values)),
            "sd_capture_k6": float(values.std(ddof=1)),
            "bootstrap_95_ci": block_bootstrap_ci(values, SEED_BOOTSTRAP + i),
            "haar_random_subspace_expected_capture": float(K / FORMULAS),
            "circular_shift_null_mean": float(null_values.mean()),
            "circular_shift_null_q95": float(np.quantile(null_values, 0.95)),
            "circular_shift_null_q99": float(np.quantile(null_values, 0.99)),
            "circular_shift_exceedances": int(np.sum(null_values >= values.mean())),
            "circular_shift_p_raw": p_map.get(name, {}).get("raw"),
            "circular_shift_p_holm": p_map.get(name, {}).get("holm"),
        }

    positive = all(
        split_metrics[name]["mean_capture_k6"] >= PRACTICAL_CAPTURE
        and p_map[name]["holm"] < 0.05
        and split_metrics[name]["mean_capture_k6"] > split_metrics[name]["circular_shift_null_q99"]
        for name in primary_names
    )
    decision = (
        "FULL_UNIVERSE_SIX_DIMENSIONAL_PREQUENTIAL_STRUCTURE_SUPPORTED_EXPLORATORY"
        if positive else
        "FULL_UNIVERSE_SIX_DIMENSIONAL_PREQUENTIAL_STRUCTURE_NOT_CONFIRMED"
    )

    total_variance = float(eigenvalues.sum())
    shares = eigenvalues / max(total_variance, 1e-30)
    cumulative = np.cumsum(shares)
    k80 = int(np.searchsorted(cumulative, 0.80) + 1)
    k90 = int(np.searchsorted(cumulative, 0.90) + 1)
    positive_shares = shares[shares > 0]
    entropy_rank = float(np.exp(-np.sum(positive_shares * np.log(positive_shares))))
    participation = float((eigenvalues.sum() ** 2) / max(np.sum(eigenvalues ** 2), 1e-30))

    eigen_rows = [
        {"component": i + 1, "eigenvalue": float(eigenvalues[i]), "variance_share": float(shares[i]), "cumulative_share": float(cumulative[i])}
        for i in range(len(eigenvalues))
    ]
    eigen_path = out / f"{OUT_PREFIX}_training_eigenvalues_{DATE}.csv"
    csv_write(eigen_path, ["component", "eigenvalue", "variance_share", "cumulative_share"], eigen_rows)

    loading_obj = {"k": K, "formula_count": FORMULAS, "components": []}
    for c in range(K):
        order = np.argsort(-np.abs(basis[:, c]))[:20]
        loading_obj["components"].append({
            "component": c + 1,
            "top_loadings": [
                {
                    **formulas[int(idx)],
                    "loading": float(basis[int(idx), c]),
                    "absolute_loading": float(abs(basis[int(idx), c])),
                }
                for idx in order
            ],
        })
    loadings_path = out / f"{OUT_PREFIX}_component_loadings_{DATE}.json"
    write_json(loadings_path, loading_obj)

    ledger_rows = []
    for local_idx, capture in enumerate(all_captures):
        global_idx = WARMUP + local_idx
        if local_idx < counts["discovery"]:
            split = "discovery"
        elif local_idx < counts["discovery"] + counts["validation"]:
            split = "validation"
        else:
            split = "blind_oos"
        ledger_rows.append({
            "target_index": global_idx + 1,
            "target_date": dates[global_idx],
            "cutoff_date": cutoffs[global_idx],
            "prior_draws": global_idx + 1,
            "actual_quintet": actuals[global_idx],
            "split": split,
            "captured_energy_k6": f"{float(capture):.12f}",
            "haar_random_expected_capture": f"{K / FORMULAS:.12f}",
        })
    ledger_path = out / f"{OUT_PREFIX}_target_ledger_{DATE}.csv"
    csv_write(ledger_path, list(ledger_rows[0].keys()), ledger_rows)

    null_rows = []
    for b in range(NULL_REPLICATES):
        null_rows.append({
            "replicate": b + 1,
            **{name: f"{float(null[name][b]):.12f}" for name in ("discovery", "validation", "blind_oos")},
        })
    null_path = out / f"{OUT_PREFIX}_circular_shift_null_{DATE}.csv"
    csv_write(null_path, ["replicate", "discovery", "validation", "blind_oos"], null_rows)

    source_path = out / f"{OUT_PREFIX}_source_lineage_{DATE}.json"
    write_json(source_path, lineage)

    report = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A17",
        "status": "COMPLETED_HISTORICAL_PREQUENTIAL_STRUCTURAL_TEST",
        "source": lineage,
        "design": {
            "target_rows": TARGETS,
            "formula_count": FORMULAS,
            "candidate_universe_size": CANDIDATES,
            "warmup_targets": WARMUP,
            "evaluated_targets": n_eval,
            "split_counts": counts,
            "k_frozen_from_a16": K,
            "practical_capture_threshold": PRACTICAL_CAPTURE,
            "null_replicates": NULL_REPLICATES,
            "null_seed": SEED_NULL,
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
            "bootstrap_block_length": BLOCK,
            "bootstrap_seed_base": SEED_BOOTSTRAP,
            "primary_multiple_testing": "Holm across Validation and historical Blind OOS circular-shift upper-tail tests",
        },
        "preprocessing": {
            "rank_normalization": "(rank-1)/658007",
            "row_centering": "subtract the median across all 1,023 formula ranks within each target",
            "column_scaling": "mean and sample standard deviation from the first 400 target rows only; frozen thereafter",
            "basis": "top six right-singular vectors of the standardized first 400 target rows; sign-canonicalized",
            "target_statistic": "||U_6^T z_t||^2 / ||z_t||^2, evaluated before any basis update (basis is fixed)",
        },
        "training_spectrum": {
            "training_rows": WARMUP,
            "participation_ratio": participation,
            "entropy_effective_rank": entropy_rank,
            "k80": k80,
            "k90": k90,
            "top6_variance_share": float(cumulative[K - 1]),
            "orthogonality_max_error": orthogonality_error,
        },
        "split_metrics": split_metrics,
        "primary_p_values": p_map,
        "decision": decision,
        "integrity": {
            "source_lineage_verified": True,
            "all_3386_target_rows_reconciled": True,
            "all_1023_formula_masks_reconciled": True,
            "strict_prior_cutoffs": True,
            "rank_bounds_1_to_658008": True,
            "future_suffix_invariance": future_suffix_invariance,
            "training_basis_uses_first_400_rows_only": True,
            "null_is_independent_column_circular_shift": True,
            "deterministic_seeded_null": True,
            "full_replay_byte_identity": "PENDING_WORKFLOW_REPLAY",
        },
        "interpretation": (
            "This is a prequential structural test of the realized 1,023-formula rank-profile vector. "
            "It does not forecast the five numbers or the exact quintet and does not establish causal or predictive skill."
        ),
        "limitations": [
            "The pinned Q7 archive ends on 2026-10-24 and is separate from current main through 2026-11-12.",
            "The historical Blind OOS overlaps earlier SONAR research and is not virgin prospective confirmation.",
            "The rank-profile vector is an outcome descriptor for the realized quintet, not a vector of candidate-number probabilities.",
            "The independent circular-shift null preserves each column's circular sequence but is only one surrogate dependence model.",
            "The fixed six-component basis is not updated after the first 400 targets.",
            "The Q7 universe is exhaustive only within its registered ten-family finite grammar, not all possible mathematical formulas.",
        ],
    }
    report_path = out / f"{OUT_PREFIX}_report_{DATE}.json"
    write_json(report_path, report)

    md = [
        "# Q141-A17 — Full-Universe Prequential Spectral Mapping",
        "",
        f"**Status:** {report['status']}",
        f"**Decision:** {decision}",
        "",
        "## Design",
        "",
        f"- Full Q7 panel: {TARGETS:,} target rows × {FORMULAS:,} formula masks.",
        f"- Initial training prefix: {WARMUP}; fixed basis dimension: {K}.",
        f"- Evaluated targets: {n_eval:,}; Discovery / Validation / historical Blind OOS: {counts['discovery']} / {counts['validation']} / {counts['blind_oos']}.",
        "- The basis and scaler are fitted only on the first 400 target rows and then frozen.",
        "",
        "## Results",
        "",
        "| Split | Mean captured energy | 95% block-bootstrap CI | Circular-shift null mean | Null q99 |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in ("discovery", "validation", "blind_oos"):
        m = split_metrics[name]
        md.append(f"| {name} | {m['mean_capture_k6']:.6f} | [{m['bootstrap_95_ci'][0]:.6f}, {m['bootstrap_95_ci'][1]:.6f}] | {m['circular_shift_null_mean']:.6f} | {m['circular_shift_null_q99']:.6f} |")
    md += [
        "",
        "## Primary holdout tests",
        "",
        "| Holdout | Raw p | Holm p | Practical threshold |",
        "|---|---:|---:|---:|",
    ]
    for name in primary_names:
        md.append(f"| {name} | {p_map[name]['raw']:.6f} | {p_map[name]['holm']:.6f} | mean capture >= {PRACTICAL_CAPTURE:.2f} |")
    md += [
        "",
        f"Training spectrum: participation ratio {participation:.4f}; entropy effective rank {entropy_rank:.4f}; k80={k80}; k90={k90}; top-six variance share {cumulative[K-1]:.6f}.",
        "",
        "## Limits",
        "",
        "This tests whether the realized formula-rank profile lies in a subspace learned before each evaluated target. It does not predict the actual numbers or a ticket. The historical Blind OOS is exposed to previous SONAR research, and the circular-shift null is only one temporal dependence control.",
        "",
    ]
    report_md_path = out / f"{OUT_PREFIX}_report_{DATE}.md"
    report_md_path.write_text("\n".join(md), encoding="utf-8")

    outputs = [report_path, report_md_path, ledger_path, null_path, eigen_path, loadings_path, source_path]
    output_info = {}
    for p in outputs:
        raw = p.read_bytes()
        output_info[p.name] = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
    manifest = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A17",
        "status": "COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
        "q7_head": Q7_HEAD,
        "outputs": output_info,
    }
    manifest_path = out / f"{OUT_PREFIX}_manifest_{DATE}.json"
    write_json(manifest_path, manifest)

    checkpoint = {
        "schema_version": "1.0",
        "experiment_id": "Q141-A17",
        "status": "COMPLETED_LOCAL_PENDING_REMOTE_READBACK",
        "q7_head": Q7_HEAD,
        "target_rows": TARGETS,
        "formula_count": FORMULAS,
        "warmup": WARMUP,
        "evaluated_targets": n_eval,
        "split_counts": counts,
        "decision": decision,
        "next_action": "Verify dedicated CI, byte-identical replay and remote Git readback; then request human review without merge.",
    }
    checkpoint_path = out / f"{OUT_PREFIX}_checkpoint_{DATE}.json"
    write_json(checkpoint_path, checkpoint)
    print("A17_COMPUTE_COMPLETE", json.dumps({
        "decision": decision,
        "split_metrics": {k: v["mean_capture_k6"] for k, v in split_metrics.items()},
        "primary_p": p_map,
        "k80": k80,
        "top6_variance_share": float(cumulative[K - 1]),
        "outputs": len(output_info),
    }, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()
