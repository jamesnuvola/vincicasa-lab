#!/usr/bin/env python3
"""Q141-C2: current-state formula-family selection by standardized Top-5/Top-6 margin."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np
import sonar_q141_formula_family_anticipation as base

ROOT = base.ROOT
OUT = base.OUT
EXPECTED_TARGETS = 3354
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
COMPARATORS = ("equal_family", "equal_feature", "fixed_discovery_family")
ENDPOINTS = ("top5_hit_share", "top10_hit_share", "top20_hit_share", "mean_actual_number_rank")
PREREG_PATH = OUT / "q141_formula_family_margin_selector_preregistration_2026-11-12.json"
REPORT_PATH = OUT / "q141_formula_family_margin_selector_report_2026-11-12.json"
LEDGER_PATH = OUT / "q141_formula_family_margin_selector_target_ledger_2026-11-12.csv"
MANIFEST_PATH = OUT / "q141_formula_family_margin_selector_manifest_2026-11-12.json"
LEDGER_FIELDS = (
    "target_index", "target_offset", "target_date", "cutoff_date", "prior_draws",
    "split", "actual_quintet", "selected_family", "selected_margin",
    "family_margins_json", "family_top5_hits_json",
    "margin_selected_top5_hits", "margin_selected_top10_hits",
    "margin_selected_top20_hits", "margin_selected_mean_rank",
    "equal_family_top5_hits", "equal_family_top10_hits",
    "equal_family_top20_hits", "equal_family_mean_rank",
    "equal_feature_top5_hits", "equal_feature_top10_hits",
    "equal_feature_top20_hits", "equal_feature_mean_rank",
    "family_metrics_json"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def standardized_top5_margin(scores) -> float:
    """Scale-invariant (5th minus 6th score) divided by population SD."""
    values = np.asarray(scores, dtype=np.float64)
    if values.shape != (40,) or not np.all(np.isfinite(values)):
        raise ValueError("Q141_C2: family score must be 40 finite values")
    sd = float(np.std(values, ddof=0))
    if sd < 1e-12:
        return 0.0
    ordered = np.sort(values)[::-1]
    return float((ordered[4] - ordered[5]) / sd)


def choose_margin_family(family_scores):
    """Largest standardized margin; exact ties resolve by ascending family ID."""
    margins = {name: standardized_top5_margin(scores) for name, scores in family_scores.items()}
    if set(margins) != set(base.FAMILY_NAMES):
        raise ValueError("Q141_C2: family set differs from registered Q141-C0 families")
    selected = min(base.FAMILY_NAMES, key=lambda name: (-margins[name], name))
    return selected, margins


def rankdata_average(values):
    """One-based average ranks for ties; deterministic and dependency-free."""
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(len(values), dtype=np.float64)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average_rank = ((start + 1) + end) / 2.0
        ranks[order[start:end]] = average_rank
        start = end
    return ranks


def spearman_rho(x, y, seed):
    rx, ry = rankdata_average(x), rankdata_average(y)
    if len(rx) < 3 or float(np.std(rx)) < 1e-12 or float(np.std(ry)) < 1e-12:
        return None, None
    rho = float(np.corrcoef(rx, ry)[0, 1])
    # Centered rank-product sequence; block sign-flip preserves local dependence.
    products = (rx - rx.mean()) * (ry - ry.mean())
    p_value = base.block_signflip_p(products, seed)
    return rho, p_value


def summarize(rows, model, fixed_family=None):
    metrics = []
    for row in rows:
        if model == "families":
            metrics.append(row["family_metrics"][fixed_family])
        else:
            metrics.append(row[model])
    n = len(metrics)
    if not n:
        return {"targets": 0}
    return {
        "targets": n,
        "mean_number_hits_top5": float(sum(m["top5_hits"] for m in metrics) / (5 * n)),
        "mean_number_hits_top10": float(sum(m["top10_hits"] for m in metrics) / (5 * n)),
        "mean_number_hits_top20": float(sum(m["top20_hits"] for m in metrics) / (5 * n)),
        "mean_actual_number_rank": float(sum(m["mean_rank"] for m in metrics) / n),
        "all5_top5_rate": float(sum(m["top5_hits"] == 5 for m in metrics) / n),
    }


def benefit_deltas(rows, model, comparator, endpoint):
    values = []
    for row in rows:
        candidate = row[model]
        control = row[comparator] if comparator != "fixed_discovery_family" else row["family_metrics"][row["fixed_family"]]
        if endpoint == "top5_hit_share":
            values.append((candidate["top5_hits"] - control["top5_hits"]) / 5.0)
        elif endpoint == "top10_hit_share":
            values.append((candidate["top10_hits"] - control["top10_hits"]) / 5.0)
        elif endpoint == "top20_hit_share":
            values.append((candidate["top20_hits"] - control["top20_hits"]) / 5.0)
        elif endpoint == "mean_actual_number_rank":
            values.append(control["mean_rank"] - candidate["mean_rank"])
        else:
            raise ValueError(f"Unknown endpoint: {endpoint}")
    return np.asarray(values, dtype=np.float64)


def validate_preregistration():
    raw = PREREG_PATH.read_bytes()
    prereg = json.loads(raw.decode("utf-8"))
    expected = {
        "task_id": "Q141-C2",
        "status": "PREREGISTERED_EXECUTION_PENDING",
        "expected_targets": EXPECTED_TARGETS,
        "expected_splits": EXPECTED_SPLITS,
        "source": {
            "git_blob_sha1": base.EXPECTED_ARCHIVE_BLOB_SHA1,
            "eligible_draw_count": base.EXPECTED_ELIGIBLE_DRAWS,
            "cutoff": base.CUTOFF,
        },
    }
    for key in ("task_id", "status", "expected_targets", "expected_splits"):
        if prereg.get(key) != expected[key]:
            raise RuntimeError(f"Q141_C2_BLOCKED: preregistration mismatch at {key}")
    for key, value in expected["source"].items():
        if prereg.get("source", {}).get(key) != value:
            raise RuntimeError(f"Q141_C2_BLOCKED: source preregistration mismatch at {key}")
    if prereg.get("formula_policy", {}).get("no_tuning") is not True:
        raise RuntimeError("Q141_C2_BLOCKED: frozen no-tuning policy missing")
    return raw, prereg


def build_walkforward():
    raw, archive_blob_sha, dates, draws, excluded = base.load_archive()
    if len(draws) - base.MIN_HISTORY != EXPECTED_TARGETS:
        raise RuntimeError("Q141_C2_BLOCKED: target count mismatch")
    split_counts = Counter(
        base.split_name(offset, EXPECTED_TARGETS) for offset in range(EXPECTED_TARGETS)
    )
    if dict(split_counts) != EXPECTED_SPLITS:
        raise RuntimeError(f"Q141_C2_BLOCKED: split counts {dict(split_counts)}")
    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    rows = []

    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, EXPECTED_TARGETS)
            features = base.feature_matrix(
                i, draws, prefix, pos_prefix, pair_counts, occurrence_lists
            )
            if not np.array_equal(features[:, 0], features[:, 25]) or not np.array_equal(
                features[:, 1], features[:, 26]
            ):
                raise RuntimeError("Q141_C2_BLOCKED: duplicate feature aliases differ")
            standardized = base.zscore_columns(features)
            family_scores = {
                family: standardized[:, indices].mean(axis=1)
                for family, indices in base.FAMILIES.items()
            }
            selected_family, margins = choose_margin_family(family_scores)
            family_ranks = {
                family: base.rank_scores(scores)
                for family, scores in family_scores.items()
            }
            family_metrics = {
                family: base.rank_metrics(ranks, draw)
                for family, ranks in family_ranks.items()
            }
            equal_family_scores = np.mean(
                np.stack([family_scores[name] for name in base.FAMILY_NAMES]), axis=0
            )
            equal_feature_scores = standardized[:, base.UNIQUE_FEATURE_INDICES].mean(axis=1)
            models = {
                "margin_selected": base.rank_metrics(family_ranks[selected_family], draw),
                "equal_family": base.rank_metrics(base.rank_scores(equal_family_scores), draw),
                "equal_feature": base.rank_metrics(base.rank_scores(equal_feature_scores), draw),
            }
            rows.append({
                "target_index": i,
                "target_offset": offset,
                "target_date": dates[i],
                "cutoff_date": dates[i - 1],
                "prior_draws": i,
                "split": split,
                "actual_quintet": tuple(draw),
                "selected_family": selected_family,
                "selected_margin": margins[selected_family],
                "family_margins": margins,
                "family_metrics": family_metrics,
                **models,
            })
        # Strict-prior update: add the target only after its family choice/rankings are frozen and scored.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in base.combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1

    if len(rows) != EXPECTED_TARGETS:
        raise RuntimeError("Q141_C2_BLOCKED: incomplete target ledger")
    if not all(r["cutoff_date"] < r["target_date"] and r["prior_draws"] == r["target_index"] for r in rows):
        raise RuntimeError("Q141_C2_BLOCKED: strict chronology failed")

    discovery = [r for r in rows if r["split"] == "discovery"]
    discovery_family_scores = {
        family: sum(r["family_metrics"][family]["top5_hits"] for r in discovery)
        for family in base.FAMILY_NAMES
    }
    discovery_family_ranks = {
        family: sum(r["family_metrics"][family]["mean_rank"] for r in discovery) / len(discovery)
        for family in base.FAMILY_NAMES
    }
    fixed_family = min(
        base.FAMILY_NAMES,
        key=lambda family: (-discovery_family_scores[family], discovery_family_ranks[family], family),
    )
    for row in rows:
        row["fixed_family"] = fixed_family
    return raw, archive_blob_sha, dates, draws, excluded, dict(split_counts), rows, fixed_family


def paired_inference(rows):
    results = []
    seed_index = 0
    for split in ("validation", "blind_oos"):
        subset = [r for r in rows if r["split"] == split]
        for comparator in COMPARATORS:
            for endpoint in ENDPOINTS:
                deltas = benefit_deltas(subset, "margin_selected", comparator, endpoint)
                seed = 14120261114 + seed_index * 17
                results.append({
                    "split": split,
                    "comparison": f"margin_selected_vs_{comparator}",
                    "endpoint": endpoint,
                    "targets": len(deltas),
                    "mean_benefit_delta": float(deltas.mean()),
                    "bootstrap_ci_95": base.circular_block_bootstrap_ci(deltas, seed),
                    "block_signflip_p_raw": base.block_signflip_p(deltas, seed + 1),
                })
                seed_index += 1
    if len(results) != 24:
        raise RuntimeError("Q141_C2_BLOCKED: paired test denominator != 24")
    adjusted = base.holm_adjust([r["block_signflip_p_raw"] for r in results])
    for row, p_adj in zip(results, adjusted):
        row["block_signflip_p_holm_24_tests"] = float(p_adj)
    primary = next(
        r for r in results
        if r["split"] == "blind_oos"
        and r["comparison"] == "margin_selected_vs_equal_family"
        and r["endpoint"] == "top5_hit_share"
    )
    return {"method": "non-overlapping 20-target block sign-flip and circular moving-block bootstrap",
            "replicates": base.REPLICATES, "block_length": base.BLOCK_LENGTH,
            "holm_method": "Holm-Bonferroni over 24 Validation/Blind x 3 controls x 4 endpoints",
            "tests": results, "primary_test": primary, "primary_practical_threshold": 0.005}


def uniform_null(rows):
    tests = []
    for split in ("validation", "blind_oos"):
        subset = [r for r in rows if r["split"] == split]
        for top_k, field in ((5, "top5_hits"), (10, "top10_hits"), (20, "top20_hits")):
            observed = sum(r["margin_selected"][field] for r in subset)
            tests.append({
                "split": split,
                "model": "margin_selected",
                "endpoint": f"top{top_k}_hit_share",
                "targets": len(subset),
                "observed_number_hits": int(observed),
                "uniform_expected_number_hits": len(subset) * 5.0 * top_k / 40.0,
                "exact_hypergeom_upper_tail_p_raw": base.exact_hypergeom_upper_tail(
                    int(observed), len(subset), top_k
                ),
            })
    if len(tests) != 6:
        raise RuntimeError("Q141_C2_BLOCKED: uniform test denominator != 6")
    adjusted = base.holm_adjust([r["exact_hypergeom_upper_tail_p_raw"] for r in tests])
    for row, p_adj in zip(tests, adjusted):
        row["exact_hypergeom_p_holm_6_tests"] = float(p_adj)
    return {"method": "exact convolution of Hypergeometric(40,k,5) per-target hit counts",
            "holm_method": "Holm-Bonferroni over six margin-selected Validation/Blind x Top-5/10/20 tests",
            "tests": tests}


def margin_calibration(rows):
    results = []
    seed_index = 0
    for split in ("discovery", "validation", "blind_oos"):
        subset = [r for r in rows if r["split"] == split]
        for family in base.FAMILY_NAMES:
            margins = [r["family_margins"][family] for r in subset]
            hits = [r["family_metrics"][family]["top5_hits"] for r in subset]
            rho, p_raw = spearman_rho(margins, hits, 14120261113 + seed_index * 19)
            if p_raw is None:
                p_raw = 1.0
            results.append({
                "split": split, "family": family, "targets": len(subset),
                "spearman_margin_vs_top5_hits": rho,
                "block_signflip_p_raw": float(p_raw),
            })
            seed_index += 1
    if len(results) != 18:
        raise RuntimeError("Q141_C2_BLOCKED: margin calibration denominator != 18")
    adjusted = base.holm_adjust([r["block_signflip_p_raw"] for r in results])
    for row, p_adj in zip(results, adjusted):
        row["block_signflip_p_holm_18_tests"] = float(p_adj)
    return results


def write_target_ledger(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        for row in rows:
            actual = row["actual_quintet"]
            margin = row["margin_selected"]
            equal_family = row["equal_family"]
            equal_feature = row["equal_feature"]
            writer.writerow({
                "target_index": row["target_index"],
                "target_offset": row["target_offset"],
                "target_date": row["target_date"],
                "cutoff_date": row["cutoff_date"],
                "prior_draws": row["prior_draws"],
                "split": row["split"],
                "actual_quintet": " ".join(str(x + 1) for x in actual),
                "selected_family": row["selected_family"],
                "selected_margin": format(row["selected_margin"], ".17g"),
                "family_margins_json": json.dumps(row["family_margins"], sort_keys=True, separators=(",", ":")),
                "family_top5_hits_json": json.dumps(
                    {name: row["family_metrics"][name]["top5_hits"] for name in base.FAMILY_NAMES},
                    sort_keys=True, separators=(",", ":")
                ),
                "margin_selected_top5_hits": margin["top5_hits"],
                "margin_selected_top10_hits": margin["top10_hits"],
                "margin_selected_top20_hits": margin["top20_hits"],
                "margin_selected_mean_rank": format(margin["mean_rank"], ".17g"),
                "equal_family_top5_hits": equal_family["top5_hits"],
                "equal_family_top10_hits": equal_family["top10_hits"],
                "equal_family_top20_hits": equal_family["top20_hits"],
                "equal_family_mean_rank": format(equal_family["mean_rank"], ".17g"),
                "equal_feature_top5_hits": equal_feature["top5_hits"],
                "equal_feature_top10_hits": equal_feature["top10_hits"],
                "equal_feature_top20_hits": equal_feature["top20_hits"],
                "equal_feature_mean_rank": format(equal_feature["mean_rank"], ".17g"),
                "family_metrics_json": json.dumps(row["family_metrics"], sort_keys=True, separators=(",", ":")),
            })


def run():
    prereg_raw, prereg = validate_preregistration()
    raw, archive_blob_sha, dates, draws, excluded, split_counts, rows, fixed_family = build_walkforward()
    split_reports = {}
    for split in ("discovery", "validation", "blind_oos"):
        subset = [r for r in rows if r["split"] == split]
        split_reports[split] = {
            "targets": len(subset),
            "models": {
                "margin_selected": summarize(subset, "margin_selected"),
                "equal_family": summarize(subset, "equal_family"),
                "equal_feature": summarize(subset, "equal_feature"),
                "fixed_discovery_family": summarize(subset, "families", fixed_family),
                "families": {family: summarize(subset, "families", family) for family in base.FAMILY_NAMES},
            },
            "selected_family_counts": dict(Counter(r["selected_family"] for r in subset)),
            "mean_selected_margin": float(np.mean([r["selected_margin"] for r in subset])),
        }
    selector_sequence = [r["selected_family"] for r in rows]
    switches = sum(a != b for a, b in zip(selector_sequence[1:], selector_sequence[:-1]))
    paired = paired_inference(rows)
    null = uniform_null(rows)
    calibration = margin_calibration(rows)
    acceptance = {
        "archive_git_blob_sha_verified": archive_blob_sha == base.EXPECTED_ARCHIVE_BLOB_SHA1,
        "eligible_draw_count_verified": len(draws) == base.EXPECTED_ELIGIBLE_DRAWS,
        "target_count_verified": len(rows) == EXPECTED_TARGETS,
        "split_counts_verified": split_counts == EXPECTED_SPLITS,
        "strict_prior_cutoffs_verified": all(r["cutoff_date"] < r["target_date"] and r["prior_draws"] == r["target_index"] for r in rows),
        "family_count_verified": all(len(r["family_margins"]) == 6 for r in rows),
        "family_margin_finite_and_nonnegative": all(math.isfinite(r["selected_margin"]) and r["selected_margin"] >= -1e-12 for r in rows),
        "fixed_family_selected_from_discovery_only": fixed_family in base.FAMILY_NAMES,
        "paired_holm_family_size_verified": len(paired["tests"]) == 24,
        "uniform_holm_family_size_verified": len(null["tests"]) == 6,
        "calibration_holm_family_size_verified": len(calibration) == 18,
        "disputed_contest_315_excluded": not any(d > base.CUTOFF for d in dates),
    }
    if not all(acceptance.values()):
        raise RuntimeError(f"Q141_C2_BLOCKED: acceptance failure {acceptance}")
    primary = paired["primary_test"]
    decision = "NO_CURRENT_STATE_MARGIN_LIFT_DEMONSTRATED"
    if (primary["mean_benefit_delta"] >= 0.005
            and primary["block_signflip_p_holm_24_tests"] < 0.05
            and primary["bootstrap_ci_95"][0] > 0.0):
        decision = "CURRENT_STATE_MARGIN_LIFT_DEMONSTRATED_HISTORICAL_EXPLORATORY"
    report = {
        "schema_version": "1.0",
        "task_id": "Q141-C2",
        "status": "EXECUTED_EXPLORATORY",
        "decision": decision,
        "hypothesis": prereg["hypothesis"],
        "source": {
            "archive_path": "data/storico_daily.csv",
            "git_blob_sha1": archive_blob_sha,
            "archive_sha256": sha256(raw),
            "eligible_draw_count": len(draws),
            "first_date": dates[0],
            "last_date": dates[-1],
            "cutoff": base.CUTOFF,
            "excluded_rows_after_cutoff": excluded,
            "disputed_contest_315_used": False,
        },
        "walkforward": {
            "minimum_prior_history": base.MIN_HISTORY,
            "scored_targets": len(rows),
            "split_rule": "offset/scored_targets <0.60 discovery; <0.80 validation; otherwise blind_oos",
            "split_counts": split_counts,
            "strict_prior": "feature state and all six family rankings are frozen before target scoring; state update follows scoring",
            "selection_policy": "max standardized (5th minus 6th family score)/population SD; exact ties by ascending family ID",
            "blind_used_for_policy_selection": False,
            "fixed_control_family_selected_on_discovery": fixed_family,
            "selector_switches": switches,
        },
        "formula_registry": {
            "source_feature_count": len(base.FEATURE_NAMES),
            "unique_feature_count": len(base.UNIQUE_FEATURE_INDICES),
            "aliases_verified": {"recent_5": "freq_5", "recent_10": "freq_10"},
            "families": {name: [base.FEATURE_NAMES[i] for i in base.FAMILIES[name]] for name in base.FAMILY_NAMES},
        },
        "metrics_by_split": split_reports,
        "paired_inference": paired,
        "uniform_exact_null": null,
        "margin_calibration": {
            "method": "Spearman rank correlation between each family’s prior-only standardized score margin and realized Top-5 hits; block sign-flip p-values",
            "holm_method": "Holm-Bonferroni across 6 families x 3 splits",
            "tests": calibration,
        },
        "acceptance": acceptance,
        "limitations": prereg["limitations"],
        "next_action": "Do not tune the margin rule. Continue Q141-B typed formula registry and source-lineage reconciliation; if C2 is null, require a new independently preregistered state signal or focus on formula grammar coverage.",
    }
    write_target_ledger(rows)
    report_bytes = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    REPORT_PATH.write_bytes(report_bytes)
    ledger_bytes = LEDGER_PATH.read_bytes()
    code_bytes = Path(__file__).read_bytes()
    manifest = {
        "schema_version": "1.0",
        "task_id": "Q141-C2",
        "status": "REPLAYABLE_EXPLORATORY_BUNDLE",
        "source_archive_git_blob_sha1": archive_blob_sha,
        "preregistration_sha256": sha256(prereg_raw),
        "code_sha256": sha256(code_bytes),
        "report_path": str(REPORT_PATH.relative_to(ROOT)),
        "report_sha256": sha256(report_bytes),
        "target_ledger_path": str(LEDGER_PATH.relative_to(ROOT)),
        "target_ledger_sha256": sha256(ledger_bytes),
        "target_rows": len(rows),
        "split_counts": split_counts,
        "paired_test_count": len(paired["tests"]),
        "paired_holm_family_size": 24,
        "uniform_test_count": len(null["tests"]),
        "uniform_holm_family_size": 6,
        "margin_calibration_test_count": len(calibration),
        "margin_calibration_holm_family_size": 18,
        "bootstrap_replicates": base.REPLICATES,
        "block_length": base.BLOCK_LENGTH,
        "decision": decision,
        "primary_test": primary,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "task_id": "Q141-C2", "decision": decision, "split_counts": split_counts,
        "primary_test": primary, "acceptance": acceptance,
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
