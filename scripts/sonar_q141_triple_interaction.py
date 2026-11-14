#!/usr/bin/env python3
"""Q141-B5: strict-prior walk-forward audit of all Q80 three-way interactions."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry

OUT = ROOT / "reports" / "sequence_agent"
PREREG = OUT / "q141_triple_interaction_preregistration_2026-11-12.json"
CATALOG = OUT / "q141_triple_interaction_formula_catalog_2026-11-12.csv"
LEDGER = OUT / "q141_triple_interaction_target_ledger_2026-11-12.csv"
REPORT = OUT / "q141_triple_interaction_report_2026-11-12.json"
MANIFEST = OUT / "q141_triple_interaction_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_triple_interaction_checkpoint_2026-11-12.json"

SEED, BLOCK_LENGTH, REPLICATES = 14120261115, 20, 20000
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
UNIFORM = {5: 0.125, 10: 0.25, 20: 0.5}
PRACTICAL_TOP5_DELTA = 0.005


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def stable_formula_id(ast):
    payload = json.dumps(ast, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "Q141-B5:" + hashlib.sha256(payload).hexdigest()[:24]


def build_formula_catalog():
    canonical_names = list(registry.CANONICAL_FEATURE_NAMES)
    expected_names = [base.FEATURE_NAMES[i] for i in base.UNIQUE_FEATURE_INDICES]
    if canonical_names != expected_names or len(canonical_names) != 25:
        raise RuntimeError("Q141-B5_BLOCKED: canonical feature order does not match the Q141 feature matrix")
    catalog = []
    for i, j, k in itertools.combinations(range(len(canonical_names)), 3):
        names = (canonical_names[i], canonical_names[j], canonical_names[k])
        families = tuple(registry.q80_family(name) for name in names)
        family_group = "+".join(sorted(families))
        nodes = [{"op": "zscore_feature", "feature": name} for name in names]
        additive_ast = {"type": "per_number_ranking", "op": "add", "children": nodes}
        product_ast = {
            "op": "cross_sectional_zscore",
            "population": "candidate_numbers_1_to_40",
            "child": {"op": "multiply", "children": nodes},
            "constant_sd_rule": "zero_interaction",
        }
        interaction_ast = {
            "type": "per_number_ranking",
            "op": "add",
            "children": nodes + [product_ast],
            "interaction_coefficient": 1.0,
        }
        catalog.append({
            "triple_index": len(catalog),
            "feature_i": i, "feature_j": j, "feature_k": k,
            "feature_i_name": names[0], "feature_j_name": names[1], "feature_k_name": names[2],
            "family_i": families[0], "family_j": families[1], "family_k": families[2],
            "family_group": family_group,
            "additive_formula_id": stable_formula_id(additive_ast),
            "interaction_formula_id": stable_formula_id(interaction_ast),
            "additive_ast": additive_ast, "interaction_ast": interaction_ast,
        })
    if len(catalog) != math.comb(25, 3) or len(catalog) != 2300:
        raise RuntimeError("Q141-B5_BLOCKED: triple catalog cardinality mismatch")
    ids = [item[key] for item in catalog for key in ("additive_formula_id", "interaction_formula_id")]
    if len(ids) != 4600 or len(set(ids)) != 4600:
        raise RuntimeError("Q141-B5_BLOCKED: formula IDs are not unique")
    return catalog


def triple_score_matrices(z_matrix, triples):
    z = np.asarray(z_matrix, dtype=np.float64)
    triples = np.asarray(triples, dtype=np.int16)
    if z.shape != (40, 25) or triples.ndim != 2 or triples.shape[1] != 3:
        raise ValueError("Q141-B5: expected a 40x25 feature matrix and an n-by-3 triple array")
    left = z[:, triples[:, 0]]
    middle = z[:, triples[:, 1]]
    right = z[:, triples[:, 2]]
    additive = left + middle + right
    product = left * middle * right
    means = product.mean(axis=0, keepdims=True)
    sds = product.std(axis=0, ddof=0, keepdims=True)
    standardized = np.zeros_like(product)
    np.divide(product - means, sds, out=standardized, where=sds >= 1e-12)
    interaction = additive + standardized
    if not np.all(np.isfinite(additive)) or not np.all(np.isfinite(interaction)):
        raise RuntimeError("Q141-B5: non-finite formula score")
    return additive, interaction


def rank_score_matrix(scores):
    scores = np.asarray(scores, dtype=np.float64)
    if scores.ndim != 2 or scores.shape[0] != 40 or not np.all(np.isfinite(scores)):
        raise ValueError("Q141-B5: score matrix must be finite with 40 candidate-number rows")
    # Stable descending sort preserves the input order 1..40 for exact ties.
    order = np.argsort(-scores, axis=0, kind="stable")
    ranks = np.empty(order.shape, dtype=np.int16)
    columns = np.arange(order.shape[1])[None, :]
    ranks[order, columns] = np.arange(1, 41, dtype=np.int16)[:, None]
    return ranks


def matrix_rank_metrics(ranks, draw):
    actual = np.asarray(ranks, dtype=np.int16)[np.asarray(draw, dtype=np.int64), :]
    if actual.shape[0] != 5:
        raise ValueError("Q141-B5: each target must contain exactly five winning numbers")
    result = {"targets": int(actual.shape[1])}
    for k in (5, 10, 20):
        result[f"top{k}_hit_share"] = float(np.count_nonzero(actual <= k) / (5 * actual.shape[1]))
    result["mean_actual_number_rank"] = float(actual.mean())
    result["all5_top5_rate"] = float(np.mean(np.all(actual <= 5, axis=0)))
    return result


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: (float(p_values[i]), i))
    adjusted, running, m = [1.0] * len(p_values), 0.0, len(p_values)
    for rank, idx in enumerate(order):
        running = max(running, min(1.0, (m - rank) * float(p_values[idx])))
        adjusted[idx] = running
    return adjusted


def one_sided_block_signflip_p(values, seed):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Q141-B5: invalid block sign-flip input")
    blocks = np.asarray([values[i:i + BLOCK_LENGTH].sum() for i in range(0, len(values), BLOCK_LENGTH)])
    observed = float(blocks.sum())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(REPLICATES, len(blocks)))
    simulated = signs @ blocks
    return float((np.count_nonzero(simulated >= observed - 1e-12) + 1) / (REPLICATES + 1))


def circular_block_bootstrap_ci(values, seed):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Q141-B5: invalid block-bootstrap input")
    n = len(values)
    full_blocks, remainder = divmod(n, BLOCK_LENGTH)
    extended = np.concatenate((values, values[:BLOCK_LENGTH - 1]))
    cumulative = np.concatenate(([0.0], np.cumsum(extended)))
    full_sums = cumulative[BLOCK_LENGTH:] - cumulative[:-BLOCK_LENGTH]
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(REPLICATES, full_blocks))
    totals = full_sums[starts].sum(axis=1) if full_blocks else np.zeros(REPLICATES)
    if remainder:
        partial_sums = cumulative[remainder:] - cumulative[:-remainder]
        totals += partial_sums[rng.integers(0, n, size=REPLICATES)]
    low, high = np.quantile(totals / n, [0.025, 0.975])
    return [float(low), float(high)]


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def file_info(path):
    data = path.read_bytes()
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": sha256_bytes(data),
        "git_blob_sha1": git_blob_sha1(data),
    }


def build_test_family(split_rows):
    tests = []
    index = 0
    for split in ("discovery", "validation", "blind_oos"):
        rows = split_rows[split]
        for k in (5, 10, 20):
            values = [r[f"interaction_top{k}_hit_share"] - r[f"additive_top{k}_hit_share"] for r in rows]
            tests.append({
                "id": f"triple_interaction_minus_additive_top{k}_{split}",
                "family": "three_way_interaction_increment",
                "split": split,
                "endpoint": f"top{k}_hit_share_delta",
                "targets": len(values),
                "mean_delta": float(np.mean(values)),
                "ci95": circular_block_bootstrap_ci(values, SEED + 1000 + index),
                "p_raw": one_sided_block_signflip_p(values, SEED + 2000 + index),
            })
            index += 1
    for split in ("validation", "blind_oos"):
        for model in ("additive", "interaction"):
            values = [r[f"{model}_top5_hit_share"] - UNIFORM[5] for r in split_rows[split]]
            tests.append({
                "id": f"{model}_top5_vs_uniform_{split}",
                "family": "top5_uniform_control",
                "split": split,
                "model": model,
                "endpoint": "top5_hit_share_excess_vs_uniform",
                "targets": len(values),
                "mean_delta": float(np.mean(values)),
                "ci95": circular_block_bootstrap_ci(values, SEED + 3000 + index),
                "p_raw": one_sided_block_signflip_p(values, SEED + 4000 + index),
            })
            index += 1
    if len(tests) != 13:
        raise RuntimeError("Q141-B5: registered test-family size mismatch")
    for row, p_holm in zip(tests, holm_adjust([x["p_raw"] for x in tests])):
        row["p_holm_13_tests"] = float(p_holm)
    return tests


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    prereg_bytes = PREREG.read_bytes()
    prereg = json.loads(prereg_bytes)
    if prereg.get("task_id") != "Q141-B5" or prereg.get("status") != "PREREGISTERED_EXECUTION_PENDING":
        raise RuntimeError("Q141-B5_BLOCKED: preregistration is not frozen in pending state")
    _, archive_blob, dates, draws, excluded = base.load_archive()
    if archive_blob != prereg["source"]["archive_git_blob_sha1"]:
        raise RuntimeError("Q141-B5_BLOCKED: archive blob differs from preregistration")
    if len(draws) != 3404 or dates[-1] != "2026-11-10" or excluded != 1:
        raise RuntimeError("Q141-B5_BLOCKED: eligible archive boundary mismatch")

    catalog = build_formula_catalog()
    triples = np.asarray([(x["feature_i"], x["feature_j"], x["feature_k"]) for x in catalog], dtype=np.int16)
    target_count = len(draws) - base.MIN_HISTORY
    if target_count != 3354:
        raise RuntimeError("Q141-B5_BLOCKED: target count mismatch")
    split_counts = {
        name: sum(base.split_name(offset, target_count) == name for offset in range(target_count))
        for name in EXPECTED_SPLITS
    }
    if split_counts != EXPECTED_SPLITS:
        raise RuntimeError(f"Q141-B5_BLOCKED: chronological split mismatch {split_counts}")

    catalog_rows = []
    for item in catalog:
        for operator, formula_id, ast in (
            ("additive_triple", item["additive_formula_id"], item["additive_ast"]),
            ("additive_plus_standardized_three_way_product", item["interaction_formula_id"], item["interaction_ast"]),
        ):
            catalog_rows.append({
                "formula_id": formula_id,
                "operator": operator,
                "feature_i": item["feature_i_name"],
                "feature_j": item["feature_j_name"],
                "feature_k": item["feature_k_name"],
                "family_i": item["family_i"],
                "family_j": item["family_j"],
                "family_k": item["family_k"],
                "family_group": item["family_group"],
                "ast_json": json.dumps(ast, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            })
    write_csv(CATALOG, list(catalog_rows[0].keys()), catalog_rows)

    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    target_rows = []
    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, target_count)
            feature_raw = base.feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists)
            z_matrix = base.zscore_columns(feature_raw[:, list(base.UNIQUE_FEATURE_INDICES)])
            if z_matrix.shape != (40, 25):
                raise RuntimeError("Q141-B5: malformed standardized feature matrix")
            additive_scores, interaction_scores = triple_score_matrices(z_matrix, triples)
            additive_ranks = rank_score_matrix(additive_scores)
            interaction_ranks = rank_score_matrix(interaction_scores)
            additive_metrics = matrix_rank_metrics(additive_ranks, draw)
            interaction_metrics = matrix_rank_metrics(interaction_ranks, draw)
            row = {
                "target_index": i,
                "target_offset": offset,
                "target_date": dates[i],
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "split": split,
                "actual_quintet": " ".join(str(x + 1) for x in draw),
                "feature_snapshot_sha256": sha256_bytes(z_matrix.tobytes(order="C")),
                "triple_count": len(catalog),
            }
            for k in (5, 10, 20):
                row[f"additive_top{k}_hit_share"] = additive_metrics[f"top{k}_hit_share"]
                row[f"interaction_top{k}_hit_share"] = interaction_metrics[f"top{k}_hit_share"]
                row[f"delta_top{k}_hit_share"] = interaction_metrics[f"top{k}_hit_share"] - additive_metrics[f"top{k}_hit_share"]
            row["additive_mean_actual_rank"] = additive_metrics["mean_actual_number_rank"]
            row["interaction_mean_actual_rank"] = interaction_metrics["mean_actual_number_rank"]
            row["additive_all5_rate"] = additive_metrics["all5_top5_rate"]
            row["interaction_all5_rate"] = interaction_metrics["all5_top5_rate"]
            target_rows.append(row)

        # Strict-prior state update occurs only after all triple formula rankings are frozen.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in itertools.combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    if len(target_rows) != target_count:
        raise RuntimeError("Q141-B5: target ledger incomplete")
    previous = None
    for row in target_rows:
        if row["cutoff_date"] >= row["target_date"] or row["prior_draws"] != row["target_index"]:
            raise RuntimeError("Q141-B5: target cutoff is not strictly prior")
        if previous is not None and row["target_date"] <= previous:
            raise RuntimeError("Q141-B5: target chronology is not increasing")
        previous = row["target_date"]

    split_rows = {s: [r for r in target_rows if r["split"] == s] for s in EXPECTED_SPLITS}
    for split, rows in split_rows.items():
        if len(rows) != EXPECTED_SPLITS[split]:
            raise RuntimeError(f"Q141-B5: {split} row count mismatch")
    summaries = {}
    for split, rows in split_rows.items():
        summaries[split] = {
            "targets": len(rows),
            "additive": {
                "top5_hit_share": float(np.mean([r["additive_top5_hit_share"] for r in rows])),
                "top10_hit_share": float(np.mean([r["additive_top10_hit_share"] for r in rows])),
                "top20_hit_share": float(np.mean([r["additive_top20_hit_share"] for r in rows])),
                "mean_actual_number_rank": float(np.mean([r["additive_mean_actual_rank"] for r in rows])),
                "all5_top5_rate": float(np.mean([r["additive_all5_rate"] for r in rows])),
            },
            "interaction": {
                "top5_hit_share": float(np.mean([r["interaction_top5_hit_share"] for r in rows])),
                "top10_hit_share": float(np.mean([r["interaction_top10_hit_share"] for r in rows])),
                "top20_hit_share": float(np.mean([r["interaction_top20_hit_share"] for r in rows])),
                "mean_actual_number_rank": float(np.mean([r["interaction_mean_actual_rank"] for r in rows])),
                "all5_top5_rate": float(np.mean([r["interaction_all5_rate"] for r in rows])),
            },
            "delta": {
                "top5_hit_share": float(np.mean([r["delta_top5_hit_share"] for r in rows])),
                "top10_hit_share": float(np.mean([r["delta_top10_hit_share"] for r in rows])),
                "top20_hit_share": float(np.mean([r["delta_top20_hit_share"] for r in rows])),
                "mean_actual_number_rank": float(np.mean([r["interaction_mean_actual_rank"] - r["additive_mean_actual_rank"] for r in rows])),
            },
            "uniform": {"top5": UNIFORM[5], "top10": UNIFORM[10], "top20": UNIFORM[20]},
        }

    tests = build_test_family(split_rows)
    primary = next(x for x in tests if x["id"] == "triple_interaction_minus_additive_top5_blind_oos")
    validation = next(x for x in tests if x["id"] == "triple_interaction_minus_additive_top5_validation")
    lift = primary["mean_delta"] > PRACTICAL_TOP5_DELTA and primary["p_holm_13_tests"] < 0.05 and validation["mean_delta"] > 0
    decision = "THREE_WAY_INTERACTION_LIFT_DEMONSTRATED" if lift else "NO_THREE_WAY_INTERACTION_LIFT_DEMONSTRATED"

    write_csv(LEDGER, list(target_rows[0].keys()), target_rows)
    catalog_data = CATALOG.read_bytes()
    ledger_data = LEDGER.read_bytes()
    prereg_sha = sha256_bytes(prereg_bytes)
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-B5",
        "status": "COMPUTED",
        "hypothesis": prereg["hypothesis"],
        "decision": decision,
        "source": {
            "archive_path": prereg["source"]["archive_path"],
            "archive_git_blob_sha1": archive_blob,
            "eligible_draws": len(draws),
            "cutoff": dates[-1],
            "contest_315_used": False,
            "excluded_rows_after_cutoff": excluded,
        },
        "formula_universe": {
            "canonical_feature_count": 25,
            "triple_count": len(catalog),
            "additive_control_formula_count": len(catalog),
            "three_way_interaction_formula_count": len(catalog),
            "formula_variants": 2 * len(catalog),
            "enumeration": "exhaustive C(25,3), no sampling",
            "catalog_path": str(CATALOG.relative_to(ROOT)),
            "catalog_sha256": sha256_bytes(catalog_data),
            "formula_ids_unique": True,
        },
        "walkforward": {
            "targets": len(target_rows),
            "split_counts": {s: len(split_rows[s]) for s in EXPECTED_SPLITS},
            "cutoff_policy": "strictly before target",
            "minimum_prior_history": base.MIN_HISTORY,
            "state_update": "after target scoring",
            "target_outcome_used_only_for_scoring": True,
            "summaries": summaries,
        },
        "statistical_inference": {
            "method": "one-sided chronological block sign-flip",
            "block_length": BLOCK_LENGTH,
            "replicates": REPLICATES,
            "seed": SEED,
            "correction": "Holm-Bonferroni",
            "registered_test_family_size": 13,
            "minimum_practical_top5_delta": PRACTICAL_TOP5_DELTA,
            "confidence_intervals": "circular moving-block bootstrap",
            "primary_blind_oos": primary,
            "tests": tests,
        },
        "acceptance": {
            "archive_blob_matches_preregistration": archive_blob == prereg["source"]["archive_git_blob_sha1"],
            "eligible_draw_count_matches": len(draws) == prereg["source"]["eligible_draws"],
            "contest_315_excluded": dates[-1] == "2026-11-10" and excluded == 1,
            "all_2300_triples_enumerated": len(catalog) == 2300,
            "all_4600_formula_ids_unique": len({item[key] for item in catalog for key in ("additive_formula_id", "interaction_formula_id")}) == 4600,
            "target_count_matches": len(target_rows) == 3354,
            "split_counts_match": {s: len(split_rows[s]) for s in EXPECTED_SPLITS} == EXPECTED_SPLITS,
            "strict_prior_cutoffs_verified": all(r["cutoff_date"] < r["target_date"] and r["prior_draws"] == r["target_index"] for r in target_rows),
            "chronology_verified": all(target_rows[i]["target_date"] < target_rows[i + 1]["target_date"] for i in range(len(target_rows) - 1)),
            "future_suffix_invariance": "covered by Q141-B5 unit test and exact-head CI",
            "no_sampling_or_feature_selection": True,
            "no_parameter_tuning": True,
            "no_pair_or_triple_selection": True,
        },
        "limitations": [
            "Only the 25 canonical Q80 features are included; Q89, Q90, Q7 and Q92 formula types remain separate.",
            "The aggregate is an average over 2,300 formula rankings, not a single deployable number ranking.",
            "No triple-specific p-values or winner selection are performed.",
            "Historical Blind OOS has prior SONAR research exposure and is not virgin prospective evidence.",
            "Holm correction covers the 13 registered Q141-B5 tests, not the full Q00-Q141 research history.",
            "The three-way product grammar is exhaustive only within this declared operator family, not the full mathematical universe.",
        ],
        "next_action": "Import Q90 interaction/gate ASTs and Q7 candidate-quintet ASTs as separate typed output families; reconcile their source archive lineage before pooled behaviour analysis.",
        "preregistration_sha256": prereg_sha,
    }
    write_json(REPORT, report)
    runner_path = Path(__file__)
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-B5",
        "status": "COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE",
        "decision": decision,
        "source_archive_git_blob_sha1": archive_blob,
        "eligible_draws": len(draws),
        "cutoff": dates[-1],
        "canonical_feature_count": 25,
        "triple_count": len(catalog),
        "formula_variants": 2 * len(catalog),
        "target_rows": len(target_rows),
        "split_counts": {s: len(split_rows[s]) for s in EXPECTED_SPLITS},
        "registered_test_family_size": 13,
        "files": {
            "preregistration": file_info(PREREG),
            "runner": file_info(runner_path),
            "formula_catalog": file_info(CATALOG),
            "target_ledger": file_info(LEDGER),
            "report": file_info(REPORT),
        },
    }
    write_json(MANIFEST, manifest)
    manifest_data = MANIFEST.read_bytes()
    checkpoint = {
        "schema_version": "1.0",
        "task_id": "Q141-B5",
        "status": "COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE",
        "catalog_sha256": sha256_bytes(catalog_data),
        "ledger_sha256": sha256_bytes(ledger_data),
        "report_sha256": sha256_bytes(REPORT.read_bytes()),
        "manifest_sha256": sha256_bytes(manifest_data),
        "next_action": report["next_action"],
    }
    write_json(CHECKPOINT, checkpoint)
    print(json.dumps({
        "task_id": "Q141-B5",
        "status": "COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE",
        "decision": decision,
        "targets": len(target_rows),
        "split_counts": {s: len(split_rows[s]) for s in EXPECTED_SPLITS},
        "triple_count": len(catalog),
        "formula_variants": 2 * len(catalog),
        "primary_blind_oos": primary,
        "manifest_sha256": sha256_bytes(manifest_data),
    }, sort_keys=True))
    if not all(report["acceptance"].values()):
        raise RuntimeError("Q141-B5: one or more acceptance gates failed")


if __name__ == "__main__":
    main()
