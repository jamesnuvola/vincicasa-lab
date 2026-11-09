#!/usr/bin/env python3
"""Q84 flow-state neighborhood sensitivity: K=10/20/50, prior-only walk-forward."""
from __future__ import annotations
import csv, gzip, hashlib, json, math, os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import sonar_strategy_atlas as q84
from sonar_sequence_agent import CONFIGS, MIN_HISTORY, read_draws, feature_scores

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "sequence_agent"
ARCHIVE = ROOT / "data" / "storico_daily.csv"
PROTOCOL = OUT / "strategy_atlas_k_sensitivity_protocol_2026-11-09.json"
BASE_REPORT = OUT / "strategy_atlas_report.json"
BASE_VALIDATION = OUT / "strategy_atlas_validation.json"
CATALOG = OUT / "strategy_atlas_k_sensitivity_catalog.jsonl"
LEDGER = OUT / "strategy_atlas_k_sensitivity_target_ledger.csv.gz"
REPORT = OUT / "strategy_atlas_k_sensitivity_report.json"
MANIFEST = OUT / "strategy_atlas_k_sensitivity_manifest.json"
CHECKPOINT = OUT / "strategy_atlas_k_sensitivity_checkpoint_2026-11-09.json"
VALIDATION = OUT / "strategy_atlas_k_sensitivity_validation.json"

K_VALUES = (10, 20, 50)
FLOW_IDS = {k: f"ENSEMBLE::FLOW_STATE_K{k}" for k in K_VALUES}
EQUAL_ID = "ENSEMBLE::EQUAL_WEIGHT_42"
FIXED_ID = "PAIR::freq_20>momentum_10_50"
MODEL_IDS = [EQUAL_ID, FLOW_IDS[10], FLOW_IDS[20], FLOW_IDS[50]]
MODEL_KEYS = ["equal42", "flow_k10", "flow_k20", "flow_k50", "fixed_discovery"]
FIXED_MODEL_ID = "FIXED::" + FIXED_ID
SPLITS = ("discovery", "validation", "blind_oos")
ENDPOINTS = q84.ENDPOINTS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def flow_context_for_k(current_state, prior_states, prior_hits, prior_turbulence, neighbors):
    """Exact Q84 causal kernel with only the neighborhood size parameterized."""
    if not (len(prior_states) == len(prior_hits) == len(prior_turbulence)):
        raise ValueError("prior flow memories are misaligned")
    if len(prior_states) < q84.MIN_ANALOGS:
        return (np.ones(len(CONFIGS)), np.full(len(CONFIGS), q84.BASELINE_TOP20),
                0, 0.0, None, "UNCLASSIFIED", np.asarray([], dtype=int),
                np.asarray([], dtype=float), np.asarray([], dtype=float))
    states = np.asarray(prior_states[-q84.LOOKBACK:], dtype=float)
    hit_memory = np.asarray(prior_hits[-q84.LOOKBACK:], dtype=float)
    center, scale = q84.robust_center_scale(states)
    z_current = (current_state - center) / scale
    distances = np.sqrt(np.mean(np.square((states - current_state) / scale), axis=1))
    k_used = min(int(neighbors), len(states))
    nearest_local = np.argsort(distances, kind="stable")[:k_used]
    bandwidth = max(float(np.median(distances[nearest_local])), 1e-6)
    kernel = np.exp(-0.5 * np.square(distances[nearest_local] / bandwidth))
    if float(kernel.sum()) <= 1e-12:
        kernel = np.ones(k_used, dtype=float)
    local = np.average(hit_memory[nearest_local], axis=0, weights=kernel)
    effective_n = float(kernel.sum() ** 2 / np.square(kernel).sum())
    shrunk = (effective_n * local + q84.SHRINKAGE * q84.BASELINE_TOP20) / (effective_n + q84.SHRINKAGE)
    weights = np.clip(np.exp((shrunk - q84.BASELINE_TOP20) / q84.TEMPERATURE),
                      q84.WEIGHT_CLIP[0], q84.WEIGHT_CLIP[1])
    turbulence = float(np.sqrt(np.mean(np.square(z_current))))
    recent_turbulence = np.asarray([x for x in prior_turbulence[-q84.LOOKBACK:] if x is not None], dtype=float)
    if len(recent_turbulence) < q84.MIN_ANALOGS:
        regime = "UNCLASSIFIED"
    else:
        q20, q80 = np.quantile(recent_turbulence, [0.2, 0.8])
        if turbulence <= q20:
            regime = "LOW_TURBULENCE"
        elif turbulence >= q80:
            regime = "HIGH_TURBULENCE"
        else:
            regime = "MID_TURBULENCE"
    offset = len(prior_states) - len(states)
    nearest_global = offset + nearest_local
    return weights, local, k_used, effective_n, turbulence, regime, nearest_global, distances[nearest_local], kernel


def select_k(discovery_rows):
    candidates = [r for r in discovery_rows if r["strategy_id"] in FLOW_IDS.values()]
    if len(candidates) != len(K_VALUES):
        raise ValueError("Discovery must contain exactly one metric row for each registered K")
    chosen = sorted(candidates, key=lambda r: (
        -float(r["mean_hits_top20"]),
        float(r["mean_rank_actual_numbers"]),
        int(r["strategy_id"].rsplit("K", 1)[1])
    ))[0]
    return int(chosen["strategy_id"].rsplit("K", 1)[1]), chosen


def metric_rows(hits_all, actual_rank_all, split_all):
    rows, tests = [], []
    indices = {s: np.asarray([i for i, name in enumerate(split_all) if name == s], dtype=int) for s in SPLITS}
    for model_index, strategy_id in enumerate(MODEL_IDS):
        for split in SPLITS:
            row = q84.metric_row(strategy_id, split, indices[split],
                                 hits_all[:, model_index, :], actual_rank_all[:, model_index, :],
                                 tests, family_kind="GLOBAL")
            rows.append(row)
    if len(tests) != len(MODEL_IDS) * len(SPLITS) * len(ENDPOINTS):
        raise ValueError(f"unexpected Holm family size: {len(tests)}")
    adjusted = q84.holm_adjust(tests)
    lookup = {x["test_id"]: x["p_raw"] for x in tests}
    for row in rows:
        row["p_values_raw"] = {}
        row["p_values_holm"] = {}
        for endpoint, _ in ENDPOINTS:
            test_id = f"GLOBAL|{row['strategy_id']}||{row['split']}|{endpoint}"
            row["p_values_raw"][endpoint] = lookup[test_id]
            row["p_values_holm"][endpoint] = adjusted[test_id]
    return rows, tests


def paired_summary(hits_all, actual_rank_all, split_all, selected_model_index):
    indices = {s: np.asarray([i for i, name in enumerate(split_all) if name == s], dtype=int) for s in SPLITS}
    comparisons = {}
    for split in ("validation", "blind_oos"):
        comparisons[split] = {}
        for label, comparator_index, seed_base in (("selected_vs_equal", 0, 8400), ("selected_vs_fixed", 4, 8500)):
            result = {}
            for j, (endpoint, _) in enumerate(ENDPOINTS):
                item = q84.bootstrap_paired(
                    hits_all[indices[split], selected_model_index, j],
                    hits_all[indices[split], comparator_index, j],
                    seed_base + j + (0 if split == "validation" else 100)
                )
                item["mean_difference_hit_share_per_actual_number"] = (
                    None if item["mean_difference"] is None else item["mean_difference"] / 5.0
                )
                result[endpoint] = item
            comparator_rank = actual_rank_all[indices[split], comparator_index, :].mean(axis=1)
            selected_rank = actual_rank_all[indices[split], selected_model_index, :].mean(axis=1)
            rank_item = q84.bootstrap_paired(
                comparator_rank, selected_rank,
                seed_base + 3 + (0 if split == "validation" else 100)
            )
            rank_item["interpretation"] = "positive mean_difference means the selected model has a lower (better) mean actual-number rank"
            result["mean_actual_rank_improvement"] = rank_item
            comparisons[split][label] = result
    return comparisons


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for path in (CATALOG, LEDGER, REPORT, MANIFEST, CHECKPOINT, VALIDATION):
        if path.exists():
            raise SystemExit(f"Q84_K_BLOCKED: append-only output already exists: {path.relative_to(ROOT)}")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    draws = read_draws()
    dates = [d["date"].isoformat() for d in draws]
    archive_sha1 = q84.git_blob_sha1(ARCHIVE)
    archive_sha256 = sha256_file(ARCHIVE)
    expected = protocol["source_archive"]
    if (len(draws) != expected["draw_count"] or dates[-1] != expected["last_date"]
            or archive_sha1 != expected["git_blob_sha1"] or archive_sha256 != expected["sha256"]):
        raise SystemExit("Q84_K_BLOCKED: canonical archive differs from the preregistered source")
    base_report = json.loads(BASE_REPORT.read_text(encoding="utf-8"))
    base_validation = json.loads(BASE_VALIDATION.read_text(encoding="utf-8"))
    if (base_report.get("status") != "VALIDATED_PENDING_HUMAN_REVIEW"
            or base_report.get("source_archive", {}).get("sha256") != archive_sha256
            or base_validation.get("status") != "PASS"):
        raise SystemExit("Q84_K_BLOCKED: validated parent Q84 evidence is missing or archive-misaligned")
    if len(CONFIGS) != 42:
        raise SystemExit("Q84_K_BLOCKED: fixed-rule catalog differs from parent Q84")
    fixed_matches = [i for i, config in enumerate(CONFIGS) if config[0] == FIXED_ID]
    if len(fixed_matches) != 1:
        raise SystemExit("Q84_K_BLOCKED: frozen fixed comparator is not unique")
    fixed_index = fixed_matches[0]

    target_dates = dates[MIN_HISTORY:]
    total = len(target_dates)
    if total != 3202:
        raise SystemExit(f"Q84_K_BLOCKED: unexpected target count {total}")
    actuals = np.asarray([d["nums"] for d in draws[MIN_HISTORY:]], dtype=np.int16)
    split_all = [q84.split_name(i, total) for i in range(total)]
    split_counts = dict(Counter(split_all))
    if split_counts != {"discovery": 1921, "validation": 640, "blind_oos": 641}:
        raise SystemExit(f"Q84_K_BLOCKED: unexpected chronological splits {split_counts}")

    n_models = 5
    rank_all = np.empty((total, n_models, 40), dtype=np.int8)
    hits_all = np.empty((total, n_models, 3), dtype=np.int8)
    actual_rank_all = np.empty((total, n_models, 5), dtype=np.int8)
    states, prior_hits, prior_turbulence = [], [], []
    flow_diagnostics = {k: {"effective_n": [], "analog_count": [], "weight_cv": [],
                            "max_weight": [], "min_weight": [], "neighbor_age_targets": [],
                            "neighbor_gap_days": []} for k in K_VALUES}
    ledger_rows = []
    parity_checked = False

    for t, draw_index in enumerate(range(MIN_HISTORY, len(draws))):
        history = draws[:draw_index]
        target = draws[draw_index]
        state = q84.flow_state(history)
        base = feature_scores(history)
        fixed_ranks = np.empty((len(CONFIGS), 40), dtype=np.int8)
        for s, config in enumerate(CONFIGS):
            fixed_ranks[s] = q84.rank_vector_from_order(q84.strategy_order(base, config))
        equal_rank = q84.weighted_borda_rank(fixed_ranks, np.ones(len(CONFIGS), dtype=float))
        fixed_rank = fixed_ranks[fixed_index]
        flow_ranks, contexts = {}, {}
        for k in K_VALUES:
            context = flow_context_for_k(state, states, prior_hits, prior_turbulence, k)
            weights, local, analog_count, effective_n, turbulence, regime, nearest, distances, kernel = context
            flow_ranks[k] = q84.weighted_borda_rank(fixed_ranks, weights)
            contexts[k] = context
            diag = flow_diagnostics[k]
            diag["effective_n"].append(effective_n)
            diag["analog_count"].append(analog_count)
            diag["weight_cv"].append(float(np.std(weights) / np.mean(weights)))
            diag["max_weight"].append(float(np.max(weights)))
            diag["min_weight"].append(float(np.min(weights)))
            if len(nearest):
                ages = [t - int(j) for j in nearest]
                diag["neighbor_age_targets"].extend(ages)
                diag["neighbor_gap_days"].extend([
                    (datetime.fromisoformat(target_dates[t]).date() -
                     datetime.fromisoformat(target_dates[int(j)]).date()).days for j in nearest
                ])
            else:
                ages = []

        if not parity_checked and len(states) >= q84.MIN_ANALOGS:
            original = q84.prior_flow_context(state, states, prior_hits, prior_turbulence)
            candidate = contexts[50]
            for a, b in ((original[0], candidate[0]), (original[1], candidate[1])):
                np.testing.assert_allclose(a, b, rtol=0.0, atol=1e-12)
            if (original[2] != candidate[2] or original[3] != candidate[3]
                    or original[5] != candidate[5]):
                raise SystemExit("Q84_K_BLOCKED: K=50 flow-context parity failed")
            parity_checked = True

        current_ranks = np.vstack([equal_rank, flow_ranks[10], flow_ranks[20], flow_ranks[50], fixed_rank])
        actual = actuals[t]
        actual_ranks = current_ranks[:, actual - 1]
        current_hits = np.column_stack([
            np.sum(actual_ranks <= 5, axis=1),
            np.sum(actual_ranks <= 10, axis=1),
            np.sum(actual_ranks <= 20, axis=1),
        ]).astype(np.int8)
        rank_all[t] = current_ranks
        actual_rank_all[t] = actual_ranks
        hits_all[t] = current_hits

        row = {
            "target_date": target_dates[t],
            "prior_cutoff_date": dates[draw_index - 1],
            "prior_draw_count": draw_index,
            "actual_quintet": " ".join(str(int(x)) for x in actual),
            "split": split_all[t],
            "flow_state": json.dumps([float(x) for x in state], separators=(",", ":")),
            "flow_regime": contexts[50][5],
            "flow_turbulence": "" if contexts[50][4] is None else f"{contexts[50][4]:.12g}",
        }
        for k in K_VALUES:
            context = contexts[k]
            nearest = context[6]
            dates_near = [target_dates[int(j)] for j in nearest]
            ages = [t - int(j) for j in nearest]
            gaps = [(datetime.fromisoformat(target_dates[t]).date() -
                     datetime.fromisoformat(target_dates[int(j)]).date()).days for j in nearest]
            row[f"k{k}_analog_count"] = context[2]
            row[f"k{k}_effective_n"] = f"{context[3]:.12g}"
            row[f"k{k}_mean_neighbor_age_targets"] = "" if not ages else f"{float(np.mean(ages)):.12g}"
            row[f"k{k}_median_neighbor_age_targets"] = "" if not ages else f"{float(np.median(ages)):.12g}"
            row[f"k{k}_mean_neighbor_gap_days"] = "" if not gaps else f"{float(np.mean(gaps)):.12g}"
            row[f"k{k}_nearest_target_dates"] = json.dumps(dates_near, separators=(",", ":"))
            row[f"k{k}_local_top20_mean"] = f"{float(np.mean(context[1])):.12g}"
        for model_index, key in enumerate(MODEL_KEYS):
            row[f"rank_vector_{key}"] = " ".join(str(int(x)) for x in rank_all[t, model_index])
            row[f"actual_ranks_{key}"] = " ".join(str(int(x)) for x in actual_rank_all[t, model_index])
            row[f"hits_top5_{key}"] = int(hits_all[t, model_index, 0])
            row[f"hits_top10_{key}"] = int(hits_all[t, model_index, 1])
            row[f"hits_top20_{key}"] = int(hits_all[t, model_index, 2])
        ledger_rows.append(row)

        # The current target enters analogue memory only after its ranking and outcome are recorded.
        fixed_actual_ranks = fixed_ranks[:, actual - 1]
        fixed_top20_hits = np.sum(fixed_actual_ranks <= 20, axis=1).astype(float)
        states.append(state)
        prior_hits.append(fixed_top20_hits)
        prior_turbulence.append(contexts[50][4])

    if not parity_checked:
        raise SystemExit("Q84_K_BLOCKED: K=50 parity was never exercised")

    global_metrics, tests = metric_rows(hits_all[:, :4, :], actual_rank_all[:, :4, :], split_all)
    fixed_metrics = []
    fixed_test_sink = []
    indices_by_split = {s: np.asarray([i for i, name in enumerate(split_all) if name == s], dtype=int) for s in SPLITS}
    for split in SPLITS:
        fixed_metrics.append(q84.metric_row(FIXED_MODEL_ID, split, indices_by_split[split],
                                            hits_all[:, 4, :], actual_rank_all[:, 4, :],
                                            fixed_test_sink, family_kind="DESCRIPTIVE"))
    selected_k, selected_discovery = select_k([r for r in global_metrics if r["split"] == "discovery"])
    selected_id = FLOW_IDS[selected_k]
    selected_model_index = MODEL_IDS.index(selected_id)
    paired = paired_summary(hits_all, actual_rank_all, split_all, selected_model_index)
    blind_row = next(r for r in global_metrics if r["strategy_id"] == selected_id and r["split"] == "blind_oos")
    blind_top20_pair = paired["blind_oos"]["selected_vs_equal"]["top20"]
    primary = {
        "selected_k": selected_k,
        "selected_strategy_id": selected_id,
        "selection_split": "discovery",
        "selected_discovery_mean_hits_top20": selected_discovery["mean_hits_top20"],
        "blind_mean_hits_top20": blind_row["mean_hits_top20"],
        "equal_blind_mean_hits_top20": next(r for r in global_metrics if r["strategy_id"] == EQUAL_ID and r["split"] == "blind_oos")["mean_hits_top20"],
        "paired_blind_top20_delta_vs_equal": blind_top20_pair["mean_difference"],
        "paired_blind_top20_ci95_vs_equal": blind_top20_pair["ci95"],
        "blind_global_holm_p_top20": blind_row["p_values_holm"]["top20"],
    }
    primary["demonstrated_gain"] = bool(
        primary["blind_mean_hits_top20"] >= 2.5
        and primary["paired_blind_top20_delta_vs_equal"] >= 0.10
        and primary["paired_blind_top20_ci95_vs_equal"][0] is not None
        and primary["paired_blind_top20_ci95_vs_equal"][0] > 0.0
        and primary["blind_global_holm_p_top20"] < 0.05
    )

    neighbor_summary = {}
    for k, diag in flow_diagnostics.items():
        ages = np.asarray(diag["neighbor_age_targets"], dtype=float)
        gaps = np.asarray(diag["neighbor_gap_days"], dtype=float)
        eff = np.asarray(diag["effective_n"], dtype=float)
        neighbor_summary[str(k)] = {
            "mean_effective_n": float(np.mean(eff)),
            "mean_analog_count": float(np.mean(diag["analog_count"])),
            "mean_weight_cv": float(np.mean(diag["weight_cv"])),
            "mean_max_weight": float(np.mean(diag["max_weight"])),
            "mean_min_weight": float(np.mean(diag["min_weight"])),
            "neighbor_age_targets": {
                "mean": float(np.mean(ages)) if len(ages) else None,
                "median": float(np.median(ages)) if len(ages) else None,
                "p90": float(np.quantile(ages, 0.9)) if len(ages) else None
            },
            "neighbor_gap_days": {
                "mean": float(np.mean(gaps)) if len(gaps) else None,
                "median": float(np.median(gaps)) if len(gaps) else None,
                "p90": float(np.quantile(gaps, 0.9)) if len(gaps) else None
            }
        }

    catalog_entries = []
    catalog_entries.append({
        "strategy_id": EQUAL_ID, "strategy_class": "EX_ANTE_GENERAL",
        "canonical_formula": "weighted_borda_rank(all_42_fixed_rules, equal_weights)",
        "parameters": {"fixed_rule_count": 42}, "target_selection_used_outcome": False
    })
    for k in K_VALUES:
        catalog_entries.append({
            "strategy_id": FLOW_IDS[k], "strategy_class": "EX_ANTE_CONDITIONAL",
            "canonical_formula": f"weighted_borda_rank(all_42_fixed_rules, causal_flow_kernel_K{k})",
            "parameters": {"K": k, "lookback": q84.LOOKBACK, "minimum_analogs": q84.MIN_ANALOGS,
                          "shrinkage": q84.SHRINKAGE, "temperature": q84.TEMPERATURE,
                          "weight_clip": list(q84.WEIGHT_CLIP), "flow_features": list(q84.FLOW_FEATURES)},
            "target_selection_used_outcome": False
        })
    catalog_entries.append({
        "strategy_id": FIXED_MODEL_ID, "strategy_class": "EX_ANTE_GENERAL",
        "canonical_formula": FIXED_ID, "parameters": {"selection_source": "parent_Q84_discovery"},
        "target_selection_used_outcome": False
    })
    for item in catalog_entries:
        item["grammar_version"] = "Q84_FLOW_K_SENSITIVITY_V1"
        item["hash"] = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    source_paths = [
        "scripts/sonar_strategy_atlas.py",
        "scripts/sonar_sequence_agent.py",
        "scripts/sonar_strategy_atlas_k_sensitivity.py",
        "scripts/validate_sonar_strategy_atlas_k_sensitivity.py",
        "tests/test_sonar_strategy_atlas_k_sensitivity.py",
        "reports/sequence_agent/strategy_atlas_k_sensitivity_protocol_2026-11-09.json",
    ]
    source_hashes = {p: sha256_file(ROOT / p) for p in source_paths}
    report = {
        "schema_version": "1.0", "task_id": "Q84-K-SENS",
        "status": "OUTPUTS_WRITTEN_PENDING_VALIDATOR",
        "validation_status": "EXPLORATORY_NOT_PROMOTABLE",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_code_commit_sha": os.environ.get("GITHUB_SHA", "LOCAL_UNPINNED"),
        "source_code_sha256": source_hashes,
        "source_archive": {
            "path": "data/storico_daily.csv", "draw_count": len(draws),
            "first_date": dates[0], "last_date": dates[-1],
            "git_blob_sha1": archive_sha1, "sha256": archive_sha256,
            "latest_quintet": list(draws[-1]["nums"])
        },
        "parent_q84_report_sha256": sha256_file(BASE_REPORT),
        "hypothesis": protocol["hypothesis"],
        "baseline": {"mean_hits_top5": 0.625, "mean_hits_top10": 1.25,
                     "mean_hits_top20": 2.5, "mean_actual_number_rank": 20.5},
        "flow_state": {"features": list(q84.FLOW_FEATURES), "K_values": list(K_VALUES),
                       "lookback_targets": q84.LOOKBACK, "minimum_prior_analogs": q84.MIN_ANALOGS,
                       "shrinkage_pseudocount": q84.SHRINKAGE, "temperature": q84.TEMPERATURE,
                       "weight_clip": list(q84.WEIGHT_CLIP), "regime_quantiles": [0.2, 0.8]},
        "walk_forward": {"target_count": total, "minimum_prior_draws": MIN_HISTORY,
                         "first_target": target_dates[0], "last_target": target_dates[-1],
                         "split_counts": split_counts, "strict_prefix_verified_by_runner": True,
                         "adaptive_memory_rule": "target state and outcome enter analogue memory only after its own ranking is recorded"},
        "selection": {"selected_k": selected_k, "selected_strategy_id": selected_id,
                      "rule": "highest Discovery mean Top-20 hits; ties lower mean actual rank, then smaller K",
                      "discovery_metric": selected_discovery},
        "global_metrics": global_metrics,
        "fixed_comparator_metrics_descriptive_only": fixed_metrics,
        "paired_block_bootstrap": paired,
        "paired_bootstrap_inference_note": "Paired block-bootstrap intervals are descriptive and are not part of the global 36-test Holm family.",
        "neighbor_gap_summary": neighbor_summary,
        "registered_test_family": {
            "methods": 4, "splits": 3, "endpoints": 3, "tests": len(tests),
            "holm_adjusted_tests_below_0_05": sum(
                1 for r in global_metrics for p in r["p_values_holm"].values() if p < 0.05
            ),
            "null": "Per-target Hypergeometric(40,5,k) number-hit count with continuity-corrected normal screen; one global Holm family."
        },
        "primary_gate": primary,
        "holdout_guardrail": "The historical Blind OOS dates were already inspected by earlier SONAR research; this sensitivity is exploratory, not a virgin holdout.",
        "next_action": "If no gain, retain K=10/20/50 as diagnostic evidence and test a preregistered alternative flow-state representation; if gain, human review and prospective shadow are still required.",
        "promotion_guardrail": "No automatic promotion; require at least 200 future prospective paired targets and human review."
    }

    fieldnames = ["target_date", "prior_cutoff_date", "prior_draw_count", "actual_quintet", "split",
                  "flow_state", "flow_regime", "flow_turbulence"]
    for k in K_VALUES:
        fieldnames += [f"k{k}_analog_count", f"k{k}_effective_n", f"k{k}_mean_neighbor_age_targets",
                       f"k{k}_median_neighbor_age_targets", f"k{k}_mean_neighbor_gap_days",
                       f"k{k}_nearest_target_dates", f"k{k}_local_top20_mean"]
    for key in MODEL_KEYS:
        fieldnames += [f"rank_vector_{key}", f"actual_ranks_{key}",
                       f"hits_top5_{key}", f"hits_top10_{key}", f"hits_top20_{key}"]
    with gzip.open(LEDGER, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ledger_rows)
    with CATALOG.open("w", encoding="utf-8", newline="") as handle:
        for item in catalog_entries:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    json_dump(REPORT, report)
    checkpoint = {
        "checkpoint_id": "SONAR-Q84-K-SENS-2026-11-09",
        "task_id": "Q84-K-SENS", "status": "OUTPUTS_WRITTEN_PENDING_VALIDATOR",
        "source_archive_sha256": archive_sha256, "source_archive_git_blob_sha1": archive_sha1,
        "source_code_commit_sha": report["source_code_commit_sha"],
        "target_count": total, "split_counts": split_counts, "K_values": list(K_VALUES),
        "selected_k_discovery_only": selected_k, "ledger_rows": len(ledger_rows),
        "next_action": "Run fail-closed validator, persist exact bytes and verify exact-head CI."
    }
    json_dump(CHECKPOINT, checkpoint)
    file_map = {}
    for key, path, rows in (
        ("protocol", PROTOCOL, 1), ("catalog", CATALOG, len(catalog_entries)),
        ("target_ledger", LEDGER, len(ledger_rows)), ("report", REPORT, 1),
        ("checkpoint", CHECKPOINT, 1)
    ):
        file_map[key] = {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size,
                         "sha256": sha256_file(path), "rows": rows}
    manifest = {
        "schema_version": "1.0", "task_id": "Q84-K-SENS",
        "status": "OUTPUTS_WRITTEN_PENDING_VALIDATOR",
        "source_archive_git_blob_sha1": archive_sha1, "source_archive_sha256": archive_sha256,
        "source_code_commit_sha": report["source_code_commit_sha"],
        "target_count": total, "split_counts": split_counts,
        "registered_test_family_size": len(tests), "selected_k": selected_k,
        "source_code_sha256": source_hashes, "files": file_map
    }
    json_dump(MANIFEST, manifest)
    print("SONAR_Q84_K_SENSITIVITY_SUMMARY_BEGIN")
    print(json.dumps({"status": report["status"], "target_count": total, "split_counts": split_counts,
                      "selected_k_discovery_only": selected_k, "primary_gate": primary,
                      "holm_family_size": len(tests), "neighbor_gap_summary": neighbor_summary},
                     separators=(",", ":"), ensure_ascii=False))
    print("SONAR_Q84_K_SENSITIVITY_SUMMARY_END")


if __name__ == "__main__":
    main()
