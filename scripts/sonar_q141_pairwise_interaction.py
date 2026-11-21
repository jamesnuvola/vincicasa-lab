#!/usr/bin/env python3
"""Q141-B4: strict-prior walk-forward audit of all Q80 pairwise interactions."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry

OUT = ROOT / "reports" / "sequence_agent"
PREREG = OUT / "q141_pairwise_interaction_preregistration_2026-11-12.json"
CATALOG = OUT / "q141_pairwise_interaction_formula_catalog_2026-11-12.csv"
LEDGER = OUT / "q141_pairwise_interaction_target_ledger_2026-11-12.csv"
REPORT = OUT / "q141_pairwise_interaction_report_2026-11-12.json"
MANIFEST = OUT / "q141_pairwise_interaction_manifest_2026-11-12.json"
CHECKPOINT = OUT / "q141_pairwise_interaction_checkpoint_2026-11-12.json"

SEED, BLOCK_LENGTH, REPLICATES = 14120261114, 20, 20000
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
UNIFORM = {5: 0.125, 10: 0.25, 20: 0.5}
PRACTICAL_TOP5_DELTA = 0.005


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def git_blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def stable_formula_id(ast):
    payload = json.dumps(ast, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "Q141-B4:" + hashlib.sha256(payload).hexdigest()[:24]


def build_formula_catalog():
    canonical_names = list(registry.CANONICAL_FEATURE_NAMES)
    expected_names = [base.FEATURE_NAMES[i] for i in base.UNIQUE_FEATURE_INDICES]
    if canonical_names != expected_names or len(canonical_names) != 25:
        raise RuntimeError("Q141-B4_BLOCKED: canonical feature order does not match the Q141 feature matrix")
    catalog = []
    for i, j in itertools.combinations(range(len(canonical_names)), 2):
        left, right = canonical_names[i], canonical_names[j]
        left_family, right_family = registry.q80_family(left), registry.q80_family(right)
        family_group = "+".join(sorted((left_family, right_family)))
        left_node = {"op": "zscore_feature", "feature": left}
        right_node = {"op": "zscore_feature", "feature": right}
        additive_ast = {"type": "per_number_ranking", "op": "add", "children": [left_node, right_node]}
        product_ast = {
            "op": "cross_sectional_zscore", "population": "candidate_numbers_1_to_40",
            "child": {"op": "multiply", "children": [left_node, right_node]},
            "constant_sd_rule": "zero_interaction",
        }
        interaction_ast = {
            "type": "per_number_ranking", "op": "add",
            "children": [left_node, right_node, product_ast], "interaction_coefficient": 1.0,
        }
        catalog.append({
            "pair_index": len(catalog), "feature_i": i, "feature_j": j,
            "family_left": left_family, "family_right": right_family, "family_group": family_group,
            "feature_left": left, "feature_right": right,
            "additive_formula_id": stable_formula_id(additive_ast),
            "interaction_formula_id": stable_formula_id(interaction_ast),
            "additive_ast": additive_ast, "interaction_ast": interaction_ast,
        })
    if len(catalog) != math.comb(25, 2):
        raise RuntimeError("Q141-B4_BLOCKED: pair catalog cardinality mismatch")
    ids = [item[key] for item in catalog for key in ("additive_formula_id", "interaction_formula_id")]
    if len(ids) != 600 or len(set(ids)) != 600:
        raise RuntimeError("Q141-B4_BLOCKED: formula IDs are not unique")
    return catalog


def interaction_scores(z_matrix, i, j):
    z = np.asarray(z_matrix, dtype=np.float64)
    if z.shape != (40, 25):
        raise ValueError("Q141-B4: expected a 40x25 standardized feature matrix")
    left, right = z[:, i], z[:, j]
    additive = left + right
    product = left * right
    product_sd = float(np.std(product))
    standardized_product = (
        np.zeros(40, dtype=np.float64)
        if product_sd < 1e-12
        else (product - float(np.mean(product))) / product_sd
    )
    enhanced = additive + standardized_product
    if not np.all(np.isfinite(additive)) or not np.all(np.isfinite(enhanced)):
        raise RuntimeError("Q141-B4: non-finite formula score")
    return additive, enhanced


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
        raise ValueError("Q141-B4: invalid block sign-flip input")
    blocks = np.asarray([values[i:i + BLOCK_LENGTH].sum() for i in range(0, len(values), BLOCK_LENGTH)])
    observed = float(blocks.sum())
    rng = np.random.default_rng(seed)
    signs = rng.choice(np.array([-1.0, 1.0]), size=(REPLICATES, len(blocks)))
    simulated = signs @ blocks
    return float((np.count_nonzero(simulated >= observed - 1e-12) + 1) / (REPLICATES + 1))


def circular_block_bootstrap_ci(values, seed):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Q141-B4: invalid block-bootstrap input")
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


def metric_summary(rows, model):
    return {
        "targets": len(rows),
        "top5_hit_share": float(np.mean([r[f"{model}_top5_hit_share"] for r in rows])),
        "top10_hit_share": float(np.mean([r[f"{model}_top10_hit_share"] for r in rows])),
        "top20_hit_share": float(np.mean([r[f"{model}_top20_hit_share"] for r in rows])),
        "mean_actual_number_rank": float(np.mean([r[f"{model}_mean_actual_rank"] for r in rows])),
        "all5_top5_rate": float(np.mean([r[f"{model}_all5_rate"] for r in rows])),
    }


def build_test_family(split_rows):
    tests, index = [], 0
    for split in ("discovery", "validation", "blind_oos"):
        rows = split_rows[split]
        for k in (5, 10, 20):
            values = [r[f"interaction_top{k}_hit_share"] - r[f"additive_top{k}_hit_share"] for r in rows]
            tests.append({
                "id": f"interaction_minus_additive_top{k}_{split}",
                "family": "pairwise_interaction_increment", "split": split,
                "endpoint": f"top{k}_hit_share_delta", "targets": len(values),
                "mean_delta": float(np.mean(values)),
                "ci95": circular_block_bootstrap_ci(values, SEED + 1000 + index),
                "p_raw": one_sided_block_signflip_p(values, SEED + 2000 + index),
            })
            index += 1
    for split in ("validation", "blind_oos"):
        for model in ("additive", "interaction"):
            values = [r[f"{model}_top5_hit_share"] - UNIFORM[5] for r in split_rows[split]]
            tests.append({
                "id": f"{model}_top5_vs_uniform_{split}", "family": "top5_uniform_control",
                "split": split, "model": model, "endpoint": "top5_hit_share_excess_vs_uniform",
                "targets": len(values), "mean_delta": float(np.mean(values)),
                "ci95": circular_block_bootstrap_ci(values, SEED + 3000 + index),
                "p_raw": one_sided_block_signflip_p(values, SEED + 4000 + index),
            })
            index += 1
    if len(tests) != 13:
        raise RuntimeError("Q141-B4: registered test-family size mismatch")
    for row, p_holm in zip(tests, holm_adjust([x["p_raw"] for x in tests])):
        row["p_holm_13_tests"] = float(p_holm)
    return tests


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    prereg_bytes = PREREG.read_bytes()
    prereg = json.loads(prereg_bytes)
    if prereg.get("task_id") != "Q141-B4" or prereg.get("status") != "PREREGISTERED_EXECUTION_PENDING":
        raise RuntimeError("Q141-B4_BLOCKED: preregistration is not frozen in pending state")
    _, archive_blob, dates, draws, excluded = base.load_archive()
    if archive_blob != prereg["source"]["archive_git_blob_sha1"]:
        raise RuntimeError("Q141-B4_BLOCKED: archive blob differs from preregistration")
    if len(draws) != 3404 or dates[-1] != "2026-11-10" or excluded != 1:
        raise RuntimeError("Q141-B4_BLOCKED: eligible archive boundary mismatch")

    catalog = build_formula_catalog()
    target_count = len(draws) - base.MIN_HISTORY
    if target_count != 3354:
        raise RuntimeError("Q141-B4_BLOCKED: target count mismatch")
    split_counts = {
        name: sum(base.split_name(offset, target_count) == name for offset in range(target_count))
        for name in EXPECTED_SPLITS
    }
    if split_counts != EXPECTED_SPLITS:
        raise RuntimeError(f"Q141-B4_BLOCKED: chronological split mismatch {split_counts}")

    catalog_rows = []
    for item in catalog:
        for operator, formula_id, ast in (
            ("additive_pair", item["additive_formula_id"], item["additive_ast"]),
            ("additive_plus_standardized_product", item["interaction_formula_id"], item["interaction_ast"]),
        ):
            catalog_rows.append({
                "formula_id": formula_id, "operator": operator,
                "feature_left": item["feature_left"], "feature_right": item["feature_right"],
                "family_left": item["family_left"], "family_right": item["family_right"],
                "family_group": item["family_group"],
                "ast_json": json.dumps(ast, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
            })
    write_csv(CATALOG, list(catalog_rows[0].keys()), catalog_rows)

    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    target_rows = []
    group_totals = {
        split: defaultdict(lambda: {
            "pair_count": 0, "add5": 0, "int5": 0, "add10": 0, "int10": 0,
            "add20": 0, "int20": 0, "add_all5": 0, "int_all5": 0,
        }) for split in EXPECTED_SPLITS
    }
    group_pair_counts = defaultdict(int)
    for item in catalog:
        group_pair_counts[item["family_group"]] += 1

    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, target_count)
            feature_raw = base.feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists)
            z_matrix = base.zscore_columns(feature_raw[:, list(base.UNIQUE_FEATURE_INDICES)])
            if z_matrix.shape != (40, 25):
                raise RuntimeError("Q141-B4: malformed standardized feature matrix")
            add_hits, int_hits = {5: 0, 10: 0, 20: 0}, {5: 0, 10: 0, 20: 0}
            add_rank_sum = int_rank_sum = 0.0
            add_all5 = int_all5 = 0
            local_groups = defaultdict(lambda: {
                "add5": 0, "int5": 0, "add10": 0, "int10": 0,
                "add20": 0, "int20": 0, "add_all5": 0, "int_all5": 0,
            })
            for item in catalog:
                additive_scores, interaction_score = interaction_scores(z_matrix, item["feature_i"], item["feature_j"])
                additive_metrics = base.rank_metrics(base.rank_scores(additive_scores), draw)
                interaction_metrics = base.rank_metrics(base.rank_scores(interaction_score), draw)
                for k in (5, 10, 20):
                    add_hits[k] += additive_metrics[f"top{k}_hits"]
                    int_hits[k] += interaction_metrics[f"top{k}_hits"]
                add_rank_sum += additive_metrics["mean_rank"]
                int_rank_sum += interaction_metrics["mean_rank"]
                add_all5 += int(additive_metrics["top5_hits"] == 5)
                int_all5 += int(interaction_metrics["top5_hits"] == 5)
                group = item["family_group"]
                local_groups[group]["add5"] += additive_metrics["top5_hits"]
                local_groups[group]["int5"] += interaction_metrics["top5_hits"]
                local_groups[group]["add10"] += additive_metrics["top10_hits"]
                local_groups[group]["int10"] += interaction_metrics["top10_hits"]
                local_groups[group]["add20"] += additive_metrics["top20_hits"]
                local_groups[group]["int20"] += interaction_metrics["top20_hits"]
                local_groups[group]["add_all5"] += int(additive_metrics["top5_hits"] == 5)
                local_groups[group]["int_all5"] += int(interaction_metrics["top5_hits"] == 5)

            n_pairs = len(catalog)
            row = {
                "target_index": i, "target_offset": offset, "target_date": dates[i],
                "cutoff_date": dates[i - 1], "prior_draws": i, "split": split,
                "actual_quintet": " ".join(str(x + 1) for x in draw),
                "feature_snapshot_sha256": sha256_bytes(z_matrix.tobytes()), "pair_count": n_pairs,
                "additive_top5_hit_share": add_hits[5] / (5 * n_pairs),
                "interaction_top5_hit_share": int_hits[5] / (5 * n_pairs),
                "delta_top5_hit_share": (int_hits[5] - add_hits[5]) / (5 * n_pairs),
                "additive_top10_hit_share": add_hits[10] / (5 * n_pairs),
                "interaction_top10_hit_share": int_hits[10] / (5 * n_pairs),
                "delta_top10_hit_share": (int_hits[10] - add_hits[10]) / (5 * n_pairs),
                "additive_top20_hit_share": add_hits[20] / (5 * n_pairs),
                "interaction_top20_hit_share": int_hits[20] / (5 * n_pairs),
                "delta_top20_hit_share": (int_hits[20] - add_hits[20]) / (5 * n_pairs),
                "additive_mean_actual_rank": add_rank_sum / n_pairs,
                "interaction_mean_actual_rank": int_rank_sum / n_pairs,
                "additive_all5_rate": add_all5 / n_pairs,
                "interaction_all5_rate": int_all5 / n_pairs,
            }
            target_rows.append(row)
            for group, values in local_groups.items():
                total = group_totals[split][group]
                total["pair_count"] = group_pair_counts[group]
                for key, value in values.items():
                    total[key] += value

        # Strict-prior state update occurs only after every formula has been scored.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in itertools.combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    if len(target_rows) != target_count:
        raise RuntimeError("Q141-B4: target ledger incomplete")
    previous = None
    for row in target_rows:
        if row["cutoff_date"] >= row["target_date"] or row["prior_draws"] != row["target_index"]:
            raise RuntimeError("Q141-B4: target cutoff is not strictly prior")
        if previous is not None and row["target_date"] <= previous:
            raise RuntimeError("Q141-B4: target chronology is not increasing")
        previous = row["target_date"]

    split_rows = {s: [r for r in target_rows if r["split"] == s] for s in EXPECTED_SPLITS}
    for split, rows in split_rows.items():
        if len(rows) != EXPECTED_SPLITS[split]:
            raise RuntimeError(f"Q141-B4: {split} row count mismatch")
    summaries = {}
    for split, rows in split_rows.items():
        additive, interaction = metric_summary(rows, "additive"), metric_summary(rows, "interaction")
        summaries[split] = {
            "targets": len(rows), "additive": additive, "interaction": interaction,
            "delta": {
                "top5_hit_share": interaction["top5_hit_share"] - additive["top5_hit_share"],
                "top10_hit_share": interaction["top10_hit_share"] - additive["top10_hit_share"],
                "top20_hit_share": interaction["top20_hit_share"] - additive["top20_hit_share"],
                "mean_actual_number_rank": interaction["mean_actual_number_rank"] - additive["mean_actual_number_rank"],
            },
            "uniform": {"top5": UNIFORM[5], "top10": UNIFORM[10], "top20": UNIFORM[20]},
        }

    group_summary = {}
    for split, rows in split_rows.items():
        n_targets = len(rows)
        group_summary[split] = {}
        for group, values in sorted(group_totals[split].items()):
            pair_count = group_pair_counts[group]
            denominator = 5 * n_targets * pair_count
            group_summary[split][group] = {
                "pair_count": pair_count,
                "additive_top5_hit_share": values["add5"] / denominator,
                "interaction_top5_hit_share": values["int5"] / denominator,
                "delta_top5_hit_share": (values["int5"] - values["add5"]) / denominator,
                "additive_top10_hit_share": values["add10"] / denominator,
                "interaction_top10_hit_share": values["int10"] / denominator,
                "delta_top10_hit_share": (values["int10"] - values["add10"]) / denominator,
                "additive_top20_hit_share": values["add20"] / denominator,
                "interaction_top20_hit_share": values["int20"] / denominator,
                "delta_top20_hit_share": (values["int20"] - values["add20"]) / denominator,
                "additive_all5_rate": values["add_all5"] / (n_targets * pair_count),
                "interaction_all5_rate": values["int_all5"] / (n_targets * pair_count),
                "inference": "descriptive_only_no_pair_or_group_selection",
            }

    tests = build_test_family(split_rows)
    primary = next(x for x in tests if x["id"] == "interaction_minus_additive_top5_blind_oos")
    validation_primary = next(x for x in tests if x["id"] == "interaction_minus_additive_top5_validation")
    interaction_uniform_blind = next(x for x in tests if x["id"] == "interaction_top5_vs_uniform_blind_oos")
    if (primary["mean_delta"] > 0 and primary["mean_delta"] >= PRACTICAL_TOP5_DELTA
        and primary["p_holm_13_tests"] < 0.05 and validation_primary["mean_delta"] > 0
        and interaction_uniform_blind["mean_delta"] > 0 and interaction_uniform_blind["p_holm_13_tests"] < 0.05):
        decision = "HISTORICAL_INTERACTION_LIFT_SIGNAL_REQUIRES_PROSPECTIVE_REPLICATION"
    else:
        decision = "NO_PAIRWISE_INTERACTION_LIFT_DEMONSTRATED"

    ledger_fields = list(target_rows[0].keys())
    write_csv(LEDGER, ledger_fields, target_rows)
    catalog_bytes, ledger_bytes = CATALOG.read_bytes(), LEDGER.read_bytes()
    prereg_sha, runner_sha = sha256_bytes(prereg_bytes), sha256_bytes(Path(__file__).read_bytes())
    report = {
        "schema_version": "1.0", "task_id": "Q141-B4", "status": "COMPUTED", "decision": decision,
        "hypothesis": prereg["hypothesis"],
        "source": {"archive_path": "data/storico_daily.csv", "archive_git_blob_sha1": archive_blob,
                   "eligible_draws": len(draws), "cutoff": dates[-1], "excluded_rows_after_cutoff": excluded,
                   "contest_315_used": False},
        "formula_universe": {"canonical_feature_count": 25, "pair_count": len(catalog),
            "additive_control_formula_count": len(catalog), "interaction_formula_count": len(catalog),
            "total_formula_variants": 2 * len(catalog), "pair_enumeration": "exhaustive unordered pairs from all canonical Q80 features",
            "catalog_path": str(CATALOG.relative_to(ROOT)), "catalog_sha256": sha256_bytes(catalog_bytes),
            "family_group_summaries": group_summary},
        "walkforward": {"targets": len(target_rows), "split_counts": {k: len(v) for k, v in split_rows.items()},
            "minimum_prior_history": base.MIN_HISTORY, "cutoff_policy": "strictly before target",
            "state_update": "after target scoring", "target_outcome_used_only_for_scoring": True, "summaries": summaries},
        "statistical_inference": {"registered_test_family_size": 13, "holm_method": "Holm-Bonferroni across all 13 registered tests",
            "test_direction": "one-sided positive", "method": "chronological block sign-flip", "block_length": BLOCK_LENGTH,
            "replicates": REPLICATES, "confidence_intervals": "circular moving-block bootstrap", "tests": tests,
            "primary_blind_oos": primary, "minimum_practical_top5_delta": PRACTICAL_TOP5_DELTA},
        "acceptance": {"archive_blob_matches_preregistration": archive_blob == prereg["source"]["archive_git_blob_sha1"],
            "eligible_draw_count_matches": len(draws) == prereg["source"]["eligible_draws"],
            "contest_315_excluded": excluded == 1 and dates[-1] == "2026-11-10",
            "canonical_feature_order_matches": list(registry.CANONICAL_FEATURE_NAMES) == [base.FEATURE_NAMES[i] for i in base.UNIQUE_FEATURE_INDICES],
            "all_300_pairs_enumerated": len(catalog) == 300,
            "all_600_formula_ids_unique": len({x[k] for x in catalog for k in ("additive_formula_id", "interaction_formula_id")}) == 600,
            "target_count_matches": len(target_rows) == 3354,
            "split_counts_match": {k: len(v) for k, v in split_rows.items()} == EXPECTED_SPLITS,
            "strict_prior_cutoffs_verified": all(r["cutoff_date"] < r["target_date"] and r["prior_draws"] == r["target_index"] for r in target_rows),
            "chronology_verified": all(target_rows[i-1]["target_date"] < target_rows[i]["target_date"] for i in range(1, len(target_rows))),
            "future_suffix_invariance": "covered by Q141-B4 unit test; see exact-head CI",
            "deterministic_replay": "fixed formula order, no random sampling, fixed bootstrap/sign-flip seeds",
            "no_pair_selection_or_parameter_tuning": True},
        "limitations": ["Only the 25 canonical Q80 features are included; Q89, Q90, Q7 and Q92 formula types remain separate.",
            "The aggregate is an average over 300 formula rankings, not a single deployable number ranking.",
            "Family-group summaries are descriptive only; no pair-specific significance or winner selection is reported.",
            "Historical Blind OOS has prior SONAR research exposure and is not virgin prospective evidence.",
            "Holm correction covers the 13 registered Q141-B4 tests, not the full Q00-Q141 research history.",
            "The 300-pair grammar is exhaustive only within this declared operator family, not the full mathematical universe."],
        "next_action": "Import Q90 interaction/gate ASTs and Q7 candidate-quintet ASTs as separate typed output families; reconcile their source archive lineage before any pooled behaviour atlas or prospective test.",
        "preregistration_sha256": prereg_sha, "runner_sha256": runner_sha,
    }
    report_bytes = (json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    REPORT.write_bytes(report_bytes)
    manifest = {"schema_version": "1.0", "task_id": "Q141-B4",
        "status": "COMPUTED_AWAITING_CI_AND_EXACT_REPOSITORY_READBACK",
        "source_archive_git_blob_sha1": archive_blob, "eligible_draws": len(draws), "cutoff": dates[-1],
        "target_rows": len(target_rows), "split_counts": {k: len(v) for k, v in split_rows.items()},
        "canonical_feature_count": 25, "pair_count": len(catalog), "formula_variants": 2 * len(catalog),
        "registered_test_family_size": 13, "decision": decision, "files": {}}
    for name, path in (("formula_catalog", CATALOG), ("target_ledger", LEDGER), ("report", REPORT),
                       ("preregistration", PREREG), ("runner", Path(__file__))):
        data = path.read_bytes()
        manifest["files"][name] = {"path": str(path.relative_to(ROOT)), "bytes": len(data),
            "sha256": sha256_bytes(data), "git_blob_sha1": git_blob_sha1(data)}
    write_json(MANIFEST, manifest)
    checkpoint = {"schema_version": "1.0", "task_id": "Q141-B4",
        "status": "COMPUTED_AWAITING_CI_AND_EXACT_REPOSITORY_READBACK",
        "manifest_path": str(MANIFEST.relative_to(ROOT)), "manifest_sha256": sha256_bytes(MANIFEST.read_bytes()),
        "report_sha256": sha256_bytes(REPORT.read_bytes()), "ledger_sha256": sha256_bytes(LEDGER.read_bytes()),
        "catalog_sha256": sha256_bytes(CATALOG.read_bytes()), "next_action": report["next_action"]}
    write_json(CHECKPOINT, checkpoint)
    print(json.dumps({"task_id": "Q141-B4", "status": "COMPUTED", "decision": decision,
        "targets": len(target_rows), "split_counts": {k: len(v) for k, v in split_rows.items()},
        "pair_count": len(catalog), "formula_variants": 2 * len(catalog),
        "primary_blind_oos_delta": primary["mean_delta"], "primary_blind_oos_ci95": primary["ci95"],
        "primary_blind_oos_p_raw": primary["p_raw"], "primary_blind_oos_p_holm": primary["p_holm_13_tests"],
        "report": str(REPORT.relative_to(ROOT)), "manifest": str(MANIFEST.relative_to(ROOT))}, sort_keys=True))


if __name__ == "__main__":
    main()
