#!/usr/bin/env python3
"""Validate the SONAR research queue evidence; distinguish valid null results from promotion readiness."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "reports" / "sequence_agent" / "research_backlog.json"
STATUS = ROOT / "reports" / "sequence_agent" / "research_queue_status.json"
DATA = ROOT / "data" / "storico_daily.csv"
METRICS = ROOT / "reports" / "sequence_agent" / "latest_metrics.json"
STAGE = ROOT / "reports" / "sequence_agent" / "stage_loss_analysis.json"
CASCADE = ROOT / "reports" / "sequence_agent" / "cascade_target_hit_ledger.csv"
RESIDUAL = ROOT / "reports" / "sequence_agent" / "residual_error_ledger.csv"
FEATURES = ROOT / "reports" / "sequence_agent" / "residual_number_feature_ledger.csv"
MIX = ROOT / "reports" / "sequence_agent" / "top20_mix_walkforward.json"
GLOBAL = ROOT / "reports" / "sequence_agent" / "global_vs_positional_walkforward.json"
HAZARD = ROOT / "reports" / "sequence_agent" / "structural_hazard_oos.json"
GATE = ROOT / "reports" / "sequence_agent" / "prospective_promotion_gate.json"
Q80_REPORT = ROOT / "reports" / "sequence_agent" / "per_number_condition_grammar.json"
Q80_METRICS = ROOT / "reports" / "sequence_agent" / "per_number_condition_formula_metrics.csv"
Q80_LEDGER = ROOT / "reports" / "sequence_agent" / "per_number_condition_target_ledger.csv"
Q81_REPORT = ROOT / "reports" / "sequence_agent" / "per_number_condition_4plus_grammar.json"
Q81_METRICS = ROOT / "reports" / "sequence_agent" / "per_number_condition_4plus_formula_metrics.csv"
Q81_LEDGER = ROOT / "reports" / "sequence_agent" / "per_number_condition_4plus_target_ledger.csv"

SPLITS = ("discovery", "validation", "oos")
Q80_SPLITS = ("discovery", "validation", "blind_oos")


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read valid JSON " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def load_csv(path):
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError("missing CSV header")
            return reader.fieldnames, list(reader)
    except OSError as exc:
        raise ValueError("cannot read CSV " + str(path.relative_to(ROOT)) + ": " + str(exc)) from exc


def nums(value):
    return [int(x) for x in str(value or "").split() if x]


def add_error(errors, condition, message):
    if not condition:
        errors.append(message)


def validate_q00():
    errors = []
    if not DATA.is_file() or not METRICS.is_file():
        return ["canonical archive or latest metrics missing"]
    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            return ["canonical CSV header invalid"]
        rows = list(reader)
    if not rows:
        return ["canonical archive empty"]
    seen, previous = set(), ""
    for row in rows:
        d = row["data"]
        try:
            date.fromisoformat(d)
            ns = [int(row["n" + str(i)]) for i in range(1, 6)]
        except Exception:
            errors.append("invalid date or number in canonical archive at " + str(d))
            continue
        if d in seen or (previous and d <= previous):
            errors.append("duplicate or non-chronological date " + d)
        if len(set(ns)) != 5 or ns != sorted(ns) or any(n < 1 or n > 40 for n in ns):
            errors.append("invalid quintet at " + d)
        seen.add(d)
        previous = d
    metrics = load_json(METRICS)
    add_error(errors, metrics.get("data_last_date") == previous, "latest metrics cutoff does not match canonical archive")
    add_error(errors, metrics.get("total_draws") == len(rows), "latest metrics draw count does not match canonical archive")
    return errors


def validate_q10():
    errors = []
    stage = load_json(STAGE)
    metrics = load_json(METRICS)
    fields, rows = load_csv(CASCADE)
    required = {"target_date", "history_cutoff", "config_id", "actual_numbers",
                "top20_hits", "top10_hits", "top5_hits", "top20_5of5",
                "top10_5of5", "top5_5of5", "evaluation_mode"}
    add_error(errors, required.issubset(set(fields)), "per-target cascade ledger missing required columns")
    add_error(errors, stage.get("status") == "COMPLETE_RETROSPECTIVE_DIAGNOSTIC", "stage-loss status not complete")
    add_error(errors, stage.get("targets") == metrics.get("walk_forward_targets_evaluated"), "stage target count does not match latest metrics")
    add_error(errors, len(stage.get("stage_loss_by_configuration", {})) == metrics.get("rule_configurations_tested"), "stage configuration count mismatch")
    add_error(errors, len(rows) == metrics.get("historical_ledger_rows"), "per-target cascade ledger row count mismatch")
    add_error(errors, set(stage.get("split_sizes", {})) == set(SPLITS), "stage split keys mismatch")
    add_error(errors, sum(stage.get("split_sizes", {}).values()) == stage.get("targets"), "stage split sizes do not sum to target count")
    seen = set()
    counts_by_date = Counter()
    for row in rows:
        key = (row.get("target_date"), row.get("config_id"))
        if key in seen:
            errors.append("duplicate target/config in cascade ledger: " + str(key))
            break
        seen.add(key)
        counts_by_date[row["target_date"]] += 1
        if not row.get("history_cutoff") or row["history_cutoff"] >= row["target_date"]:
            errors.append("non-prior cutoff in cascade ledger at " + row.get("target_date", "?"))
            break
        try:
            h20, h10, h5 = int(row["top20_hits"]), int(row["top10_hits"]), int(row["top5_hits"])
            flags = int(row["top20_5of5"]), int(row["top10_5of5"]), int(row["top5_5of5"])
        except Exception:
            errors.append("non-integer cascade hit count")
            break
        if any(h < 0 or h > 5 for h in (h20, h10, h5)) or h10 > h20 or h5 > h10:
            errors.append("cascade hit subset invariant failed at " + row.get("target_date", "?"))
            break
        if flags != (int(h20 == 5), int(h10 == 5), int(h5 == 5)):
            errors.append("cascade 5/5 flags inconsistent at " + row.get("target_date", "?"))
            break
    expected_configs = metrics.get("rule_configurations_tested")
    add_error(errors, bool(counts_by_date) and all(v == expected_configs for v in counts_by_date.values()),
              "not every target has the expected number of configurations")
    add_error(errors, len(counts_by_date) == metrics.get("walk_forward_targets_evaluated"), "cascade target coverage mismatch")
    for config_id, summary in stage.get("stage_loss_by_configuration", {}).items():
        split_summaries = summary.get("chronological_splits", {})
        if set(split_summaries) != set(SPLITS):
            errors.append("missing chronological stage splits for " + config_id)
            break
        if sum(split_summaries[s].get("targets", 0) for s in SPLITS) != summary.get("targets"):
            errors.append("chronological stage split target mismatch for " + config_id)
            break
        for split_name in SPLITS:
            ss = split_summaries[split_name]
            if sum(ss.get("top20_hit_distribution", {}).values()) != ss.get("targets"):
                errors.append("Top20 hit distribution mismatch for " + config_id + " / " + split_name)
                break
            if sum(ss.get("top10_hit_distribution", {}).values()) != ss.get("targets") or sum(ss.get("top5_hit_distribution", {}).values()) != ss.get("targets"):
                errors.append("Top10/Top5 hit distribution mismatch for " + config_id + " / " + split_name)
                break
            if "top20_5of5_p_bonferroni_family_42" not in ss:
                errors.append("missing multiple-testing correction for " + config_id + " / " + split_name)
                break
    return errors


def validate_q20():
    errors = []
    rh, residuals = load_csv(RESIDUAL)
    fh, features = load_csv(FEATURES)
    required_residual = {"target_date", "cutoff_date", "actual_numbers", "global_top20",
                         "global_hits", "global_residual_numbers", "global_residual_count",
                         "position_mix_top20", "position_mix_hits", "position_mix_residual_numbers",
                         "position_seed_union", "position_seed_union_size"}
    required_features = {"target_date", "cutoff_date", "actual_number", "missed_global_top20",
                         "missed_position_mix_top20", "missed_by", "global_frequency_rank",
                         "position_score_rank", "draws_since_last_seen", "previous5_draw_frequency",
                         "cooccurrence_with_previous_draw_numbers_last100", "last_seen_position"}
    add_error(errors, required_residual.issubset(set(rh)), "residual ledger missing required columns")
    add_error(errors, required_features.issubset(set(fh)), "residual feature ledger missing required columns")
    add_error(errors, bool(residuals) and bool(features), "residual ledgers are empty")
    by_date = {}
    expected_feature_keys = set()
    for row in residuals:
        d, cutoff = row["target_date"], row["cutoff_date"]
        if cutoff >= d:
            errors.append("residual ledger cutoff is not prior-only at " + d)
            break
        if d in by_date:
            errors.append("duplicate residual target date " + d)
            break
        actual = nums(row["actual_numbers"])
        gtop, ptop = nums(row["global_top20"]), nums(row["position_mix_top20"])
        gset, pset = set(gtop), set(ptop)
        for number in actual:
            if number not in gset or number not in pset:
                expected_feature_keys.add((d, number))
        if len(actual) != 5 or len(set(actual)) != 5 or len(gtop) != 20 or len(set(gtop)) != 20 or len(ptop) != 20 or len(set(ptop)) != 20:
            errors.append("invalid actual/Top20 list in residual ledger at " + d)
            break
        gh = len(set(actual) & set(gtop))
        ph = len(set(actual) & set(ptop))
        gres = sorted(set(actual) - set(gtop))
        pres = sorted(set(actual) - set(ptop))
        if int(row["global_hits"]) != gh or int(row["position_mix_hits"]) != ph:
            errors.append("residual hit counts inconsistent at " + d)
            break
        if nums(row["global_residual_numbers"]) != gres or int(row["global_residual_count"]) != len(gres):
            errors.append("global residual list inconsistent at " + d)
            break
        if nums(row["position_mix_residual_numbers"]) != pres:
            errors.append("positional residual list inconsistent at " + d)
            break
        if int(row["position_seed_union_size"]) != len(set(nums(row["position_seed_union"]))):
            errors.append("position seed union size inconsistent at " + d)
            break
        by_date[d] = row
    allowed = {"GLOBAL_ONLY": (1, 0), "POSITION_MIX_ONLY": (0, 1), "BOTH": (1, 1)}
    feature_keys = set()
    for row in features:
        d, cutoff = row["target_date"], row["cutoff_date"]
        if cutoff >= d or d not in by_date or cutoff != by_date[d]["cutoff_date"]:
            errors.append("feature ledger cutoff/target mismatch at " + d)
            break
        number = int(row["actual_number"])
        key = (d, number)
        if key in feature_keys:
            errors.append("duplicate residual feature row at " + d + " / " + str(number))
            break
        feature_keys.add(key)
        if number not in nums(by_date[d]["actual_numbers"]):
            errors.append("feature row number is not an actual target number at " + d)
            break
        gmiss, pmiss = int(row["missed_global_top20"]), int(row["missed_position_mix_top20"])
        if row["missed_by"] not in allowed or (gmiss, pmiss) != allowed.get(row["missed_by"]):
            errors.append("miss flags inconsistent at " + d + " / " + str(number))
            break
        if gmiss != int(number not in set(nums(by_date[d]["global_top20"]))) or pmiss != int(number not in set(nums(by_date[d]["position_mix_top20"]))):
            errors.append("miss flags do not match frozen Top20 lists at " + d + " / " + str(number))
            break
    if not errors and feature_keys != expected_feature_keys:
        missing = len(expected_feature_keys - feature_keys)
        extra = len(feature_keys - expected_feature_keys)
        errors.append("residual feature ledger coverage mismatch: missing=" + str(missing) + ", extra=" + str(extra))
    return errors


def validate_q30():
    errors = []
    report = load_json(MIX)
    add_error(errors, report.get("status") == "COMPLETE_RETROSPECTIVE_DIAGNOSTIC", "mix report status not complete")
    add_error(errors, set(report.get("splits", {})) == set(SPLITS), "mix split keys mismatch")
    add_error(errors, bool(report.get("individual_strategy_baselines")), "individual strategy baselines missing")
    add_error(errors, report.get("multiple_testing", {}).get("fixed_fusion_family_size") == 4, "fixed-fusion multiple-testing family missing")
    mt = report.get("constrained_multiple_testing", {})
    add_error(errors, mt.get("constrained_endpoint_family_size") == 8, "constrained endpoint family correction missing")
    add_error(errors, mt.get("broader_family_size") == 54, "broader constrained-mix correction missing")
    constrained = report.get("constrained_mixes", {})
    add_error(errors, len(constrained) == 4, "expected four fixed constrained legacy-Top20 mixes")
    for mix_id, mix in constrained.items():
        if mix.get("anchor_top20") != "momentum_20_100" or not mix.get("candidate_set_invariant"):
            errors.append("legacy Top20 anchor/invariant missing for " + mix_id)
            break
        if set(mix.get("splits", {})) != set(SPLITS):
            errors.append("chronological split metrics missing for constrained mix " + mix_id)
            break
        for split_name in SPLITS:
            s = mix["splits"][split_name]
            if s.get("top20_set_preserved_targets") != s.get("targets") or not s.get("candidate_set_invariant"):
                errors.append("constrained mix changed anchor candidate set for " + mix_id + " / " + split_name)
                break
            for field in ("top10_5of5_p_holm_within_8_constrained_tests", "top5_5of5_p_holm_within_8_constrained_tests",
                          "top10_5of5_p_bonferroni_family_54", "top5_5of5_p_bonferroni_family_54"):
                if field not in s:
                    errors.append("missing correction " + field + " for " + mix_id + " / " + split_name)
                    break
    return errors


def validate_q40():
    errors = []
    report = load_json(GLOBAL)
    add_error(errors, report.get("status") == "COMPLETE_RETROSPECTIVE_EXPLORATORY", "global/positional report status not complete")
    add_error(errors, report.get("same_targets_and_splits") is True, "global/positional target/split alignment not confirmed")
    add_error(errors, bool(report.get("raw_positional_union_size")), "raw positional union size missing")
    add_error(errors, bool(report.get("completion_to_20_rule")), "completion-to-20 rule missing")
    add_error(errors, set(report.get("chronological_splits", {})) == set(SPLITS), "global/positional chronological splits missing")
    total = 0
    for split_name in SPLITS:
        s = report["chronological_splits"][split_name]
        n = s.get("targets", 0)
        total += n
        for model in ("global_top20", "position_seed_mix_top20"):
            add_error(errors, s.get(model, {}).get("targets") == n, "unequal targets for " + model + " / " + split_name)
    add_error(errors, total == report.get("evaluated_targets"), "global/positional split target count mismatch")
    return errors


def validate_q50():
    errors = []
    report = load_json(HAZARD)
    add_error(errors, report.get("status") == "COMPLETE_RETROSPECTIVE_EXPLORATORY", "hazard report status not complete")
    null_test = report.get("permutation_null_test", {})
    add_error(errors, "conditional randomization" in null_test.get("method", ""), "conditional randomization null test missing")
    add_error(errors, int(null_test.get("permutations", 0)) >= 199, "conditional randomization count below 199")
    overall = report.get("overall", {})
    for key in ("model_brier", "baseline_brier", "model_log_loss", "baseline_log_loss"):
        add_error(errors, isinstance(overall.get(key), (int, float)), "missing hazard metric " + key)
    tests = report.get("gap_bucket_tests", {})
    add_error(errors, tests.get("family_size") == 4 and tests.get("adjustment") == "Holm", "Holm correction across gap buckets missing")
    buckets = report.get("gap_buckets", {})
    add_error(errors, len(buckets) == 4, "expected four gap-age buckets")
    for bucket, metrics in buckets.items():
        if "p_holm_across_4_gap_buckets" not in metrics:
            errors.append("missing Holm-adjusted p-value for gap bucket " + bucket)
            break
    return errors


def validate_q80():
    errors = []
    report = load_json(Q80_REPORT)
    metrics, metric_rows = load_csv(Q80_METRICS)
    ledger_fields, ledger_rows = load_csv(Q80_LEDGER)
    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        archive_rows = list(csv.DictReader(handle))
    expected_targets = len(archive_rows)
    expected_scored = max(0, expected_targets - int(report.get("minimum_prior_history", 0)))
    expected_formulas = 27 + 27 * 26 // 2 + 27 * 26 * 25 // 6
    add_error(errors, report.get("status") == "VALIDATED_FINITE_GRAMMAR_COMPLETE", "Q80 report status not complete")
    add_error(errors, report.get("task_id") == "Q80", "Q80 task id mismatch")
    add_error(errors, report.get("target_count") == expected_targets, "Q80 target count does not match canonical archive")
    add_error(errors, report.get("scored_targets") == expected_scored, "Q80 scored target count mismatch")
    add_error(errors, report.get("formula_count") == expected_formulas == 3303, "Q80 formula universe count mismatch")
    add_error(errors, len(report.get("features", [])) == 27, "Q80 feature schema size mismatch")
    add_error(errors, report.get("formula_count_check") == expected_formulas, "Q80 formula count check mismatch")
    split_counts = report.get("split_counts", {})
    add_error(errors, set(split_counts) == set(Q80_SPLITS), "Q80 chronological split keys mismatch")
    add_error(errors, sum(split_counts.values()) == expected_scored, "Q80 chronological split sizes do not sum to scored targets")
    add_error(errors, report.get("multiple_testing", {}).get("test_count") == expected_formulas * len(Q80_SPLITS) * 3,
              "Q80 multiple-testing family size mismatch")
    add_error(errors, len(metric_rows) == expected_formulas * len(SPLITS), "Q80 formula/split metrics row count mismatch")
    add_error(errors, {"split", "formula_id", "feature_count", "features", "targets", "mean_number_hits_top5",
                       "mean_number_hits_top10", "mean_number_hits_top20", "mean_rank_of_actual_numbers",
                       "holm_p_max_endpoint_family"}.issubset(set(metrics)), "Q80 metrics schema incomplete")
    if len(metric_rows) == expected_formulas * len(SPLITS):
        seen = set()
        for row in metric_rows:
            key = (row["split"], row["formula_id"])
            if key in seen:
                errors.append("duplicate Q80 formula/split metric " + str(key))
                break
            seen.add(key)
            if row["split"] not in Q80_SPLITS or int(row["feature_count"]) not in (1, 2, 3):
                errors.append("invalid Q80 split or feature count")
                break
            for field in ("mean_number_hits_top5", "mean_number_hits_top10", "mean_number_hits_top20",
                          "mean_rank_of_actual_numbers", "holm_p_max_endpoint_family"):
                try:
                    value = float(row[field])
                except Exception:
                    errors.append("non-numeric Q80 metric " + field)
                    break
                if not math.isfinite(value) or value < 0:
                    errors.append("invalid Q80 metric " + field)
                    break
    for split in Q80_SPLITS:
        split_rows = [row for row in metric_rows if row["split"] == split]
        add_error(errors, len({row["formula_id"] for row in split_rows}) == expected_formulas,
                  "Q80 formula uniqueness/coverage mismatch in " + split)
        add_error(errors, all(int(row["targets"]) == int(split_counts.get(split, -1)) for row in split_rows),
                  "Q80 split target count mismatch in " + split)
    required_ledger = {"target_date", "cutoff_date", "prior_draws", "actual_quintet", "status",
                       "formula_count_tested", "best_formula_id", "best_actual_number_ranks",
                       "single_feature_rank_ledger"}
    add_error(errors, required_ledger.issubset(set(ledger_fields)), "Q80 target ledger schema incomplete")
    add_error(errors, len(ledger_rows) == expected_scored, "Q80 target ledger row count mismatch")
    archive_by_date = {r["data"]: " ".join(str(int(r["n" + str(i)])) for i in range(1, 6)) for r in archive_rows}
    seen_dates = set()
    for row in ledger_rows:
        d = row.get("target_date", "")
        if d in seen_dates:
            errors.append("duplicate Q80 target date " + d)
            break
        seen_dates.add(d)
        if row.get("cutoff_date", "") >= d or row.get("cutoff_date", "") not in archive_by_date:
            errors.append("Q80 target cutoff is not strictly prior at " + d)
            break
        if archive_by_date.get(d) != row.get("actual_quintet"):
            errors.append("Q80 actual quintet does not match canonical archive at " + d)
            break
        if row.get("status") != "SCORED" or int(row.get("formula_count_tested", 0)) != expected_formulas:
            errors.append("Q80 target scoring status/formula count invalid at " + d)
            break
        try:
            ranks = json.loads(row["best_actual_number_ranks"])
            feature_ledger = json.loads(row["single_feature_rank_ledger"])
            if len(ranks) != 5 or any(not isinstance(v, int) or v < 1 or v > 40 for v in ranks):
                raise ValueError("invalid best formula ranks")
            if len(feature_ledger) != 27:
                raise ValueError("single-feature ledger must contain 27 features")
        except Exception as exc:
            errors.append("invalid Q80 per-target condition record at " + d + ": " + str(exc))
            break
    add_error(errors, report.get("first_date") == archive_rows[0]["data"], "Q80 first date mismatch")
    add_error(errors, report.get("last_date") == archive_rows[-1]["data"], "Q80 last date mismatch")
    return errors


def validate_q81():
    errors=[]
    report=load_json(Q81_REPORT)
    metrics,metric_rows=load_csv(Q81_METRICS)
    ledger_fields,ledger_rows=load_csv(Q81_LEDGER)
    with DATA.open(newline="",encoding="utf-8-sig") as handle:
        archive_rows=list(csv.DictReader(handle))
    minimum_history=int(report.get("minimum_prior_history",0))
    expected_targets=len(archive_rows)
    expected_scored=max(0,expected_targets-minimum_history)
    expected_formulas=math.comb(27,4)
    expected_metric_rows=expected_formulas*len(Q80_SPLITS)
    add_error(errors,report.get("status")=="VALIDATED_FINITE_GRAMMAR_COMPLETE","Q81 report status not complete")
    add_error(errors,report.get("review_status")=="PENDING_HUMAN_REVIEW_INTEGRATION","Q81 human-review gate missing")
    add_error(errors,report.get("task_id")=="Q81","Q81 task id mismatch")
    add_error(errors,report.get("target_count")==expected_targets,"Q81 target count does not match canonical archive")
    add_error(errors,report.get("scored_targets")==expected_scored,"Q81 scored target count mismatch")
    add_error(errors,minimum_history>=50,"Q81 minimum prior history is too small")
    add_error(errors,report.get("formula_count")==expected_formulas==17550,"Q81 formula universe count mismatch")
    add_error(errors,report.get("formula_count_check")==expected_formulas,"Q81 formula count check mismatch")
    manifest=report.get("batch_manifest",[])
    add_error(errors,report.get("formula_batch_size")==1024,"Q81 batch size mismatch")
    add_error(errors,report.get("formula_batch_count")==len(manifest),"Q81 batch count mismatch")
    cursor=0
    discovery_rows=[row for row in metric_rows if row.get("split")=="discovery"]
    for batch in manifest:
        start=int(batch.get("formula_start_inclusive",-1)); end=int(batch.get("formula_end_exclusive",-1))
        if start!=cursor or end<=start or end>expected_formulas or int(batch.get("formula_count",-1))!=end-start:
            errors.append("Q81 formula batch manifest has a gap/overlap or invalid range"); break
        if end<=len(discovery_rows) and (batch.get("formula_id_first")!=discovery_rows[start].get("formula_id") or batch.get("formula_id_last")!=discovery_rows[end-1].get("formula_id")):
            errors.append("Q81 formula batch manifest IDs do not reconcile"); break
        cursor=end
    add_error(errors,cursor==expected_formulas,"Q81 formula batch manifest does not cover the full universe")
    add_error(errors,report.get("feature_count")==27 and len(report.get("features",[]))==27,"Q81 feature schema size mismatch")
    add_error(errors,report.get("formula_grammar")=="all 4-feature equal-weight combinations","Q81 grammar label mismatch")
    add_error(errors,report.get("source_archive_sha256")==hashlib.sha256(DATA.read_bytes()).hexdigest(),"Q81 source archive SHA-256 mismatch")
    split_counts=report.get("split_counts",{})
    add_error(errors,set(split_counts)==set(Q80_SPLITS),"Q81 chronological split keys mismatch")
    add_error(errors,sum(split_counts.values())==expected_scored,"Q81 split sizes do not sum to scored targets")
    discovery_end=math.ceil(0.60*expected_scored); validation_end=math.ceil(0.80*expected_scored)
    expected_splits={"discovery":discovery_end,"validation":validation_end-discovery_end,"blind_oos":expected_scored-validation_end}
    add_error(errors,split_counts==expected_splits,"Q81 chronological split sizes mismatch")
    baseline=report.get("uniform_number_rank_baseline",{})
    add_error(errors,baseline.get("mean_number_hits_top5")==0.125 and baseline.get("mean_number_hits_top10")==0.25 and baseline.get("mean_number_hits_top20")==0.5 and baseline.get("mean_rank_of_actual_numbers")==20.5,"Q81 uniform-rank baseline missing or incorrect")
    add_error(errors,report.get("multiple_testing",{}).get("method")=="Holm-Bonferroni","Q81 multiple-testing method mismatch")
    add_error(errors,report.get("multiple_testing",{}).get("test_count")==expected_formulas*len(Q80_SPLITS)*3,"Q81 multiple-testing family size mismatch")
    add_error(errors,report.get("metrics_rows")==expected_metric_rows,"Q81 report metrics row count mismatch")
    add_error(errors,report.get("target_ledger_rows")==expected_scored,"Q81 target ledger count mismatch")
    required_metrics={"split","formula_id","feature_count","features","targets","mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"}
    add_error(errors,required_metrics.issubset(set(metrics)),"Q81 metrics schema incomplete")
    add_error(errors,len(metric_rows)==expected_metric_rows,"Q81 formula/split metrics row count mismatch")
    valid_features=set(report.get("features",[])); formula_ids=set()
    if len(metric_rows)==expected_metric_rows:
        seen={split:set() for split in Q80_SPLITS}
        for row in metric_rows:
            split=row.get("split","")
            try: feature_count=int(row.get("feature_count","0"))
            except Exception: feature_count=0
            if split not in Q80_SPLITS or feature_count!=4:
                errors.append("invalid Q81 split or feature count"); break
            parts=row.get("features","").split("+")
            if len(parts)!=4 or len(set(parts))!=4 or not set(parts).issubset(valid_features):
                errors.append("invalid Q81 formula feature list"); break
            formula_id=row.get("formula_id","")
            if formula_id in seen[split]:
                errors.append("duplicate Q81 formula/split metric "+split+"/"+formula_id); break
            seen[split].add(formula_id); formula_ids.add(formula_id)
            for field in ("mean_number_hits_top5","mean_number_hits_top10","mean_number_hits_top20","all5_top5_rate","all5_top10_rate","all5_top20_rate","mean_rank_of_actual_numbers","p_top5_normal_approx","p_top10_normal_approx","p_top20_normal_approx","holm_p_max_endpoint_family"):
                try: value=float(row[field])
                except Exception: errors.append("non-numeric Q81 metric "+field); break
                if not math.isfinite(value): errors.append("non-finite Q81 metric "+field); break
                if field=="mean_rank_of_actual_numbers":
                    if value<1 or value>40: errors.append("out-of-range Q81 rank metric"); break
                elif value<0 or value>1: errors.append("out-of-range Q81 metric "+field); break
        for split in Q80_SPLITS:
            subset=[row for row in metric_rows if row.get("split")==split]
            add_error(errors,len(subset)==expected_formulas,"Q81 formula coverage mismatch in "+split)
            add_error(errors,len({row.get("formula_id") for row in subset})==expected_formulas,"Q81 formula uniqueness mismatch in "+split)
            add_error(errors,all(int(row["targets"])==int(split_counts.get(split,-1)) for row in subset),"Q81 split target count mismatch in "+split)
    required_ledger={"target_date","cutoff_date","prior_draws","actual_quintet","status","formula_count_tested","best_formula_id","best_formula_features","best_actual_number_ranks","single_feature_rank_ledger"}
    add_error(errors,required_ledger.issubset(set(ledger_fields)),"Q81 target ledger schema incomplete")
    add_error(errors,len(ledger_rows)==expected_scored,"Q81 target ledger row count mismatch")
    expected_dates=[row["data"] for row in archive_rows[minimum_history:]]
    actual_dates=[row.get("target_date","") for row in ledger_rows]
    add_error(errors,actual_dates==expected_dates,"Q81 target ledger coverage/order mismatch")
    archive_by_date={row["data"]:" ".join(str(int(row["n"+str(i)])) for i in range(1,6)) for row in archive_rows}
    archive_index={row["data"]:i for i,row in enumerate(archive_rows)}
    for row in ledger_rows:
        target=row.get("target_date",""); index=archive_index.get(target)
        if index is None or index<minimum_history: errors.append("Q81 target date missing or too early: "+target); break
        if row.get("cutoff_date","")!=archive_rows[index-1]["data"] or int(row.get("prior_draws",-1))!=index:
            errors.append("Q81 target cutoff/prior count mismatch at "+target); break
        if archive_by_date.get(target)!=row.get("actual_quintet",""): errors.append("Q81 actual quintet mismatch at "+target); break
        if row.get("status")!="SCORED" or int(row.get("formula_count_tested",0))!=expected_formulas:
            errors.append("Q81 target scoring status/formula count invalid at "+target); break
        if row.get("best_formula_id","") not in formula_ids: errors.append("Q81 best formula id absent from formula metrics at "+target); break
        parts=row.get("best_formula_features","").split("+")
        if len(parts)!=4 or len(set(parts))!=4 or not set(parts).issubset(valid_features):
            errors.append("Q81 best formula feature schema invalid at "+target); break
        try:
            ranks=json.loads(row["best_actual_number_ranks"]); feature_ledger=json.loads(row["single_feature_rank_ledger"])
            if len(ranks)!=5 or any(not isinstance(v,int) or v<1 or v>40 for v in ranks): raise ValueError("invalid best formula ranks")
            if len(feature_ledger)!=27 or {item.get("feature") for item in feature_ledger}!=valid_features: raise ValueError("single-feature ledger must contain 27 features")
            for item in feature_ledger:
                values=item.get("ranks",[])
                if len(values)!=5 or any(not isinstance(v,int) or v<1 or v>40 for v in values): raise ValueError("invalid single-feature ranks")
        except Exception as exc:
            errors.append("invalid Q81 per-target condition record at "+target+": "+str(exc)); break
    add_error(errors,report.get("first_date")==archive_rows[0]["data"],"Q81 first date mismatch")
    add_error(errors,report.get("last_date")==archive_rows[-1]["data"],"Q81 last date mismatch")
    return errors


def main():
    plan = load_json(BACKLOG)
    tasks = plan.get("tasks", [])
    by_id = {t["id"]: t for t in tasks}
    if len(by_id) != len(tasks):
        raise SystemExit("QUEUE_INVALID: duplicate task id")
    for task in tasks:
        missing = [dep for dep in task.get("depends_on", []) if dep not in by_id]
        if missing:
            raise SystemExit("QUEUE_INVALID: " + task["id"] + " has unknown dependencies " + str(missing))
    visiting, visited = set(), set()
    def visit(task_id):
        if task_id in visiting:
            raise SystemExit("QUEUE_INVALID: dependency cycle at " + task_id)
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in by_id[task_id].get("depends_on", []):
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)
    for task_id in by_id:
        visit(task_id)

    validators = {"Q10": validate_q10, "Q20": validate_q20, "Q30": validate_q30,
                  "Q40": validate_q40, "Q50": validate_q50, "Q80": validate_q80, "Q81": validate_q81}
    states = {}
    for task in sorted(tasks, key=lambda t: (t["priority"], t["id"])):
        missing_evidence = [p for p in task.get("evidence", []) if not (ROOT / p).is_file()]
        dependency_states = [states[d]["status"] for d in task.get("depends_on", [])]
        dependency_complete = all(s == "COMPLETE" for s in dependency_states)
        validation_errors = []
        if task["id"] == "Q00":
            validation_errors = validate_q00()
            status = "COMPLETE" if not validation_errors else "PIPELINE_BLOCKED"
        elif missing_evidence:
            status = "READY" if dependency_complete else "BLOCKED_BY_DEPENDENCY"
            validation_errors = ["missing evidence: " + p for p in missing_evidence]
        elif not dependency_complete:
            status = "BLOCKED_BY_DEPENDENCY"
        elif task["id"] == "Q60":
            gate = load_json(GATE)
            valid = int(gate.get("valid_complete_prospective_targets", 0))
            minimum = int(gate.get("minimum_required", 100))
            if valid < minimum or gate.get("status") == "INSUFFICIENT_PROSPECTIVE_CASES":
                status = "INSUFFICIENT_PROSPECTIVE_CASES"
                validation_errors = [
                    str(valid) + " complete prospective paired targets; minimum " + str(minimum) +
                    " (preferred " + str(gate.get("preferred_required", 200)) + "). No missing historical freezes may be reconstructed."
                ]
            elif gate.get("promotion_allowed") is True and gate.get("status") == "VALIDATED":
                status = "COMPLETE"
            else:
                status = "EVIDENCE_PRESENT_REQUIRES_VALIDATION"
                validation_errors = ["prospective minimum reached but registered promotion criteria are not validated"]
        else:
            try:
                validation_errors = validators[task["id"]]()
            except Exception as exc:
                validation_errors = [str(exc)]
            status = "COMPLETE" if not validation_errors else "EVIDENCE_PRESENT_REQUIRES_VALIDATION"
            if task["id"] in ("Q80", "Q81") and not validation_errors:
                status = "VALIDATED_PENDING_HUMAN_REVIEW"
        states[task["id"]] = {
            "id": task["id"], "priority": task["priority"], "title": task["title"],
            "status": status, "depends_on": task.get("depends_on", []),
            "missing_evidence": missing_evidence,
            "validation_errors": validation_errors,
            "acceptance_criteria": task.get("acceptance", [])
        }

    ready = [s["id"] for s in states.values() if s["status"] == "READY"]
    complete_count = sum(s["status"] == "COMPLETE" for s in states.values())
    blocked = states.get("Q00", {}).get("status") == "PIPELINE_BLOCKED"
    insufficient = [s["id"] for s in states.values() if s["status"] == "INSUFFICIENT_PROSPECTIVE_CASES"]
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "project": plan["project"],
        "queue_status": "QUEUE_VALID" if len(visited) == len(tasks) else "QUEUE_INVALID",
        "overall_cycle_status": "PIPELINE BLOCKED" if blocked else ("COMPLETE" if complete_count == len(tasks) else "INCOMPLETE"),
        "task_count": len(tasks),
        "complete_count": complete_count,
        "ready_count": len(ready),
        "active_next_task": ready[0] if ready else None,
        "active_next_task_title": states[ready[0]]["title"] if ready else None,
        "blocking_tasks": insufficient,
        "next_action": "Continue append-only prospective freezes; do not reconstruct historical freezes." if insufficient else None,
        "tasks": list(states.values()),
        "guardrail": "Evidence presence is not validation. Valid exploratory/null results can complete analytical tasks; the cycle remains incomplete while the prospective gate lacks the registered minimum. No automatic model promotion."
    }
    if STATUS.is_file():
        try:
            previous = load_json(STATUS)
            previous_semantic = dict(previous)
            current_semantic = dict(output)
            previous_semantic.pop("generated_at_utc", None)
            current_semantic.pop("generated_at_utc", None)
            if previous_semantic == current_semantic and previous.get("generated_at_utc"):
                output["generated_at_utc"] = previous["generated_at_utc"]
        except (ValueError, OSError):
            pass
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("SONAR_RESEARCH_QUEUE_REPORT_BEGIN")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("SONAR_RESEARCH_QUEUE_REPORT_END")


if __name__ == "__main__":
    main()
