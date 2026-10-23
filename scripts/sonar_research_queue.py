#!/usr/bin/env python3
"""Validate the SONAR research queue against task-specific acceptance evidence."""
from __future__ import annotations

import csv
import json
import math
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKLOG = ROOT / "reports" / "sequence_agent" / "research_backlog.json"
STATUS = ROOT / "reports" / "sequence_agent" / "research_queue_status.json"
ROME = ZoneInfo("Europe/Rome")
PROTOCOL_START = date(2026, 10, 19)
BASELINE_TOP20 = math.comb(20, 5) / math.comb(40, 5)
BASELINE_NUMBER = 5 / 40
SPLITS = ("discovery", "validation", "oos")


def read_json(relative_path):
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def parse_numbers(value):
    if not str(value or "").strip():
        return []
    return [int(token) for token in str(value).split()]


def exact_binomial_upper_tail(n, k, p):
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    log_mass = (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                + k * math.log(p) + (n - k) * math.log1p(-p))
    term = math.exp(log_mass)
    total = term
    for i in range(k, n):
        term *= ((n - i) / (i + 1)) * (p / (1 - p))
        total += term
    return min(1.0, total)


def holm_adjust(p_values):
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted, running, m = {}, 0.0, len(ordered)
    for i, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p_value))
        adjusted[key] = running
    return adjusted


def validate_q00():
    checks, errors = [], []
    data_path = ROOT / "data" / "storico_daily.csv"
    dates, draws = [], {}
    try:
        with data_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
                errors.append("canonical CSV header is not the required six-column schema")
                return checks, errors, None
            for line, row in enumerate(reader, 2):
                d = date.fromisoformat(row["data"])
                nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
                if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n < 1 or n > 40 for n in nums):
                    errors.append(f"invalid quintet at canonical CSV line {line}")
                    continue
                if dates and d <= dates[-1]:
                    errors.append(f"duplicate or non-chronological date at {d.isoformat()}")
                dates.append(d)
                draws[d.isoformat()] = nums
        if len(dates) < 1000:
            errors.append("canonical archive has fewer than 1,000 valid draws")
        if not errors:
            checks.append(f"canonical archive has {len(dates)} unique, ordered, valid draws")
        metrics = read_json("reports/sequence_agent/latest_metrics.json")
        if metrics.get("data_last_date") != dates[-1].isoformat() or metrics.get("total_draws") != len(dates):
            errors.append("latest_metrics.json cutoff/count does not match the canonical archive")
        else:
            checks.append("latest metrics cutoff and draw count match the canonical archive")
        # Structural signatures must be a one-to-one, ordered projection of the canonical archive.
        sig_path = ROOT / "reports" / "daily_lab" / "structural_signatures.csv"
        try:
            with sig_path.open(newline="", encoding="utf-8-sig") as f:
                raw_signatures = list(csv.reader(f))
            if not raw_signatures or len(raw_signatures[0]) != 27:
                errors.append("structural_signatures.csv is empty or does not have exactly 27 columns")
            else:
                signature_header = raw_signatures[0]
                signature_rows = [dict(zip(signature_header, row)) for row in raw_signatures[1:] if len(row) == 27]
                if len(signature_rows) != len(raw_signatures) - 1:
                    errors.append("structural_signatures.csv contains rows with a width other than 27")
                signature_dates = [row.get("date", "") for row in signature_rows]
                if signature_dates != [d.isoformat() for d in dates]:
                    errors.append("structural signature dates do not match the canonical archive one-to-one")
                for row in signature_rows:
                    target = row.get("date", "")
                    if target in draws and row.get("numbers") != "-".join(str(n) for n in draws[target]):
                        errors.append(f"structural signature numbers disagree with canonical draw {target}")
                signature_report = read_json("reports/daily_lab/structural_recurrence_lab.json")
                if (signature_report.get("status") != "COMPLETE_APPEND_ONLY"
                        or int(signature_report.get("archive_rows", -1)) != len(dates)
                        or int(signature_report.get("signature_rows", -1)) != len(signature_rows)
                        or signature_report.get("last_signature_date") != dates[-1].isoformat()
                        or int(signature_report.get("column_count", -1)) != 27):
                    errors.append("structural recurrence report does not certify the current archive/signature cutoff")
                if not any("structural signature" in c.lower() for c in checks):
                    checks.append(f"{len(signature_rows)} structural signature rows align one-to-one with the canonical archive")
        except Exception as exc:
            errors.append(f"structural signature validation raised {type(exc).__name__}: {exc}")
        for shadow_name in ("position_mix_shadow.csv", "shadow_forecasts.csv"):
            shadow_path = ROOT / "reports" / "sequence_agent" / shadow_name
            if not shadow_path.is_file():
                errors.append(f"{shadow_name} is missing; existing freezes cannot be audited")
                continue
            with shadow_path.open(newline="", encoding="utf-8-sig") as f:
                shadow = list(csv.DictReader(f))
            pending_stale = [
                r["target_date"] for r in shadow
                if r.get("status") == "FROZEN_PENDING"
                and r.get("target_date") in draws
                and date.fromisoformat(r["target_date"]) < dates[-1]
            ]
            if pending_stale:
                errors.append(f"{shadow_name} has pending freezes with canonical outcomes: " + ", ".join(sorted(set(pending_stale))))
            else:
                checks.append(f"{shadow_name}: no older pending freeze is left unevaluated when its outcome is in the archive")
        info = {"dates": [d.isoformat() for d in dates], "draws": draws, "last_date": dates[-1].isoformat()}
    except Exception as exc:
        errors.append(f"canonical archive validation raised {type(exc).__name__}: {exc}")
        info = None
    return checks, errors, info


def validate_q10():
    checks, errors = [], []
    try:
        report = read_json("reports/sequence_agent/stage_loss_analysis.json")
        n = int(report.get("targets", 0))
        sizes = report.get("split_sizes", {})
        if report.get("status") != "COMPLETE_RETROSPECTIVE_DIAGNOSTIC" or n <= 0:
            errors.append("stage-loss report is not a completed non-empty diagnostic")
        if set(sizes) != set(SPLITS) or sum(int(v) for v in sizes.values()) != n:
            errors.append("stage-loss chronological split sizes do not reconcile to targets")
        configs = report.get("stage_loss_by_configuration", {})
        if not configs or not all(all(k in row for k in ("top20_hit_distribution", "top10_all5", "top5_all5",
                                                         "top10_given_top20_all5", "top5_given_top10_all5"))
                                  for row in configs.values()):
            errors.append("per-configuration Top20/Top10/Top5 and conditional cascade metrics are incomplete")
        mixes = report.get("fixed_fusion_walkforward", {})
        if len(mixes) < 4:
            errors.append("fixed-fusion walk-forward does not contain the four registered mixes")
        for mix_name, mix in mixes.items():
            for split in SPLITS:
                s = mix.get("splits", {}).get(split, {})
                target_count = int(s.get("targets", 0))
                dist = s.get("top20_hit_distribution", {})
                if target_count <= 0 or sum(int(v) for v in dist.values()) != target_count:
                    errors.append(f"{mix_name}/{split}: Top20 hit distribution does not reconcile")
                if int(dist.get("5", -1)) != int(s.get("top20_all5", -2)):
                    errors.append(f"{mix_name}/{split}: Top20 5/5 count disagrees with hit distribution")
        if not errors:
            checks.append("per-configuration cascade counts, conditional rates, and all three chronological fusion splits reconcile")
    except Exception as exc:
        errors.append(f"stage-loss validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q20(archive_info):
    checks, errors = [], []
    try:
        ledger_path = ROOT / "reports" / "sequence_agent" / "residual_error_ledger.csv"
        feature_path = ROOT / "reports" / "sequence_agent" / "residual_number_feature_ledger.csv"
        with ledger_path.open(newline="", encoding="utf-8-sig") as f:
            ledger = list(csv.DictReader(f))
        required = {"target_date", "cutoff_date", "actual_numbers", "global_top20", "global_hits",
                    "global_residual_numbers", "global_residual_count", "position_mix_top20",
                    "position_mix_hits", "position_mix_residual_numbers"}
        if not ledger or not required.issubset(ledger[0]):
            errors.append("residual error ledger is empty or missing required fields")
            return checks, errors, None
        by_target = {}
        previous = ""
        for row in ledger:
            target, cutoff = row["target_date"], row["cutoff_date"]
            if not cutoff < target:
                errors.append(f"residual ledger cutoff is not before target {target}")
                continue
            if previous and target < previous:
                errors.append(f"residual ledger targets are not chronological at {target}")
            previous = target
            actual = parse_numbers(row["actual_numbers"])
            global20 = parse_numbers(row["global_top20"])
            pos20 = parse_numbers(row["position_mix_top20"])
            if len(actual) != 5 or len(set(actual)) != 5 or actual != sorted(actual):
                errors.append(f"invalid actual quintet in residual ledger at {target}")
            if len(global20) != 20 or len(set(global20)) != 20 or any(n < 1 or n > 40 for n in global20):
                errors.append(f"invalid global Top20 at {target}")
            if len(pos20) != 20 or len(set(pos20)) != 20 or any(n < 1 or n > 40 for n in pos20):
                errors.append(f"invalid positional Top20 at {target}")
            global_hits = len(set(actual) & set(global20))
            pos_hits = len(set(actual) & set(pos20))
            global_residual = [n for n in actual if n not in set(global20)]
            pos_residual = [n for n in actual if n not in set(pos20)]
            if int(row["global_hits"]) != global_hits or int(row["position_mix_hits"]) != pos_hits:
                errors.append(f"hit counts disagree with frozen Top20 at {target}")
            if int(row["global_residual_count"]) != len(global_residual) or parse_numbers(row["global_residual_numbers"]) != global_residual:
                errors.append(f"global residual list/count mismatch at {target}")
            if parse_numbers(row["position_mix_residual_numbers"]) != pos_residual:
                errors.append(f"positional residual list mismatch at {target}")
            by_target[target] = {"cutoff": cutoff, "actual": set(actual), "global20": set(global20), "pos20": set(pos20)}
        if ledger and ledger[-1]["target_date"] != archive_info["last_date"]:
            errors.append("residual error ledger does not reach the canonical archive cutoff")
        with feature_path.open(newline="", encoding="utf-8-sig") as f:
            features = list(csv.DictReader(f))
        required_features = {"target_date", "cutoff_date", "actual_number", "missed_global_top20",
                             "missed_position_mix_top20", "missed_by"}
        if not features or not required_features.issubset(features[0]):
            errors.append("residual number feature ledger is empty or missing required fields")
        for row in features:
            target = row["target_date"]
            if target not in by_target:
                errors.append(f"feature row has no matching target in residual ledger: {target}")
                continue
            info = by_target[target]
            number = int(row["actual_number"])
            gflag, pflag = int(row["missed_global_top20"]), int(row["missed_position_mix_top20"])
            if row["cutoff_date"] != info["cutoff"] or not row["cutoff_date"] < target:
                errors.append(f"feature cutoff mismatch/leakage at {target}/{number}")
            if number not in info["actual"]:
                errors.append(f"feature number is not in the actual target quintet at {target}/{number}")
            if gflag not in (0, 1) or pflag not in (0, 1):
                errors.append(f"feature miss flags are not binary at {target}/{number}")
                continue
            if gflag != int(number not in info["global20"]) or pflag != int(number not in info["pos20"]):
                errors.append(f"feature miss flags disagree with the frozen Top20 at {target}/{number}")
            expected = "BOTH" if gflag and pflag else "GLOBAL_ONLY" if gflag else "POSITION_MIX_ONLY" if pflag else "NEITHER"
            if row["missed_by"] != expected:
                errors.append(f"feature missed_by label mismatch at {target}/{number}")
        if not errors:
            checks.append(f"{len(ledger)} target rows and {len(features)} number-feature rows pass cutoff, hit, residual, and flag reconciliation")
    except Exception as exc:
        errors.append(f"residual-ledger validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q30():
    checks, errors = [], []
    try:
        report = read_json("reports/sequence_agent/top20_mix_walkforward.json")
        correction = report.get("multiple_testing_correction", {})
        mixes = report.get("mixes", {})
        if len(mixes) != 4:
            errors.append("Q30 report must contain exactly four registered fixed mixes")
        split_sizes = report.get("splits", {})
        if set(split_sizes) != set(SPLITS) or sum(int(v) for v in split_sizes.values()) != int(report.get("targets", 0)):
            errors.append("Q30 chronological split sizes do not reconcile")
        tests, p_values = [], {}
        for mix_name, mix in mixes.items():
            for split in SPLITS:
                s = mix.get("splits", {}).get(split, {})
                n, k = int(s.get("targets", 0)), int(s.get("top20_all5", -1))
                if n != int(split_sizes.get(split, -1)) or k < 0 or k > n:
                    errors.append(f"Q30 {mix_name}/{split}: invalid target count or 5/5 count")
                test_id = f"{mix_name}:{split}"
                p_values[test_id] = exact_binomial_upper_tail(n, k, float(report.get("baseline", BASELINE_TOP20))) if n else 1.0
                tests.append((test_id, mix_name, split, n, k))
        recorded = correction.get("tests", [])
        if correction.get("method") != "Holm-Bonferroni" or correction.get("family_size") != len(tests) or len(recorded) != len(tests):
            errors.append("Q30 Holm correction missing or family size does not match the 4×3 comparison family")
        else:
            expected_adjusted = holm_adjust(p_values)
            by_id = {r.get("test_id", f"{r.get('mix')}:{r.get('split')}"): r for r in recorded}
            if set(by_id) != set(p_values):
                errors.append("Q30 corrected test IDs do not match all mix-by-split comparisons")
            for test_id, mix_name, split, n, k in tests:
                row = by_id.get(test_id, {})
                if int(row.get("targets", -1)) != n or int(row.get("successes", -1)) != k:
                    errors.append(f"Q30 correction count mismatch for {test_id}")
                if abs(float(row.get("raw_p_one_sided", -1)) - p_values[test_id]) > 1e-8:
                    errors.append(f"Q30 exact binomial p-value mismatch for {test_id}")
                if abs(float(row.get("holm_adjusted_p", -1)) - expected_adjusted[test_id]) > 1e-8:
                    errors.append(f"Q30 Holm adjusted p-value mismatch for {test_id}")
        if not errors:
            checks.append("four fixed mixes, identical chronological splits, exact binomial p-values, and Holm correction across 12 comparisons validate")
    except Exception as exc:
        errors.append(f"Q30 validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q40():
    checks, errors = [], []
    try:
        report = read_json("reports/sequence_agent/global_vs_positional_walkforward.json")
        splits = report.get("chronological_splits", {})
        if report.get("status") != "COMPLETE_RETROSPECTIVE_EXPLORATORY" or report.get("same_targets_and_splits") is not True:
            errors.append("global-vs-positional report does not certify paired identical targets/splits")
        if set(splits) != set(SPLITS):
            errors.append("global-vs-positional report lacks discovery/validation/OOS")
        for name, row in splits.items():
            g = row.get("global_top20", {})
            p = row.get("position_seed_mix_top20", {})
            if int(g.get("targets", 0)) <= 0 or int(g.get("targets", 0)) != int(p.get("targets", -1)):
                errors.append(f"global-vs-positional target mismatch in {name}")
            if int(row.get("raw_positional_union_size", {}).get("targets", -1)) != int(g.get("targets", 0)):
                errors.append(f"raw positional union target mismatch in {name}")
        union = report.get("raw_positional_union_size", {})
        if int(union.get("targets", 0)) != int(report.get("evaluated_targets", -1)) or "mean_raw_union_size" not in union:
            errors.append("overall raw positional union size is missing or inconsistent")
        if not errors:
            checks.append("global and positional Top20 use identical targets in all chronological splits; raw union is reported before completion")
    except Exception as exc:
        errors.append(f"Q40 validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q50():
    checks, errors = [], []
    try:
        report = read_json("reports/sequence_agent/structural_hazard_oos.json")
        overall = report.get("overall", {})
        required = {"model_brier", "baseline_brier", "brier_improvement", "model_log_loss",
                    "baseline_log_loss", "log_loss_improvement"}
        if not required.issubset(overall):
            errors.append("hazard report is missing Brier/log-loss baseline comparisons")
        perm = report.get("permutation_null_test", {})
        p_value = perm.get("p_one_sided_improvement")
        if int(perm.get("permutations", 0)) < 99 or p_value is None or not 0 <= float(p_value) <= 1:
            errors.append("hazard report lacks a reproducible permutation null and valid p-value")
        buckets = report.get("gap_bucket_tests", {})
        if int(buckets.get("family_size", 0)) != 4 or str(buckets.get("adjustment", "")).lower() != "holm":
            errors.append("gap-bucket tests do not declare Holm correction across four buckets")
        splits = report.get("chronological_splits", {})
        if set(splits) != set(SPLITS):
            errors.append("hazard report lacks discovery/validation/OOS splits")
        for name, row in splits.items():
            if not {"brier_improvement", "log_loss_improvement"}.issubset(row):
                errors.append(f"hazard Brier/log-loss improvements missing in {name}")
        if not errors:
            checks.append("frequency baseline, Brier/log-loss, permutation null, and Holm-corrected four-bucket family are present across chronological splits")
    except Exception as exc:
        errors.append(f"Q50 validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q55():
    checks, errors = [], []
    try:
        report = read_json("reports/sequence_agent/structural_category_oos.json")
        if report.get("status") != "COMPLETE_RETROSPECTIVE_EXPLORATORY" or int(report.get("draws", 0)) < 1000:
            errors.append("structural category report is not a completed archive-scale analysis")
        splits = report.get("chronological_splits", {})
        if set(splits) != set(SPLITS) or sum(int(v.get("targets", 0)) for v in splits.values()) != int(report.get("scored_targets", 0)):
            errors.append("structural category chronological splits do not reconcile")
        models = report.get("models", {})
        if set(models) != {"frequency_100", "age_bucket_hazard", "frequency_plus_age_equal_weight"}:
            errors.append("structural category report lacks the three predeclared models")
        for model_name, model in models.items():
            if set(model) != set(SPLITS):
                errors.append(f"{model_name} lacks all three chronological splits")
                continue
            for split in SPLITS:
                row = model[split]
                required = {"brier_score", "log_loss", "top1_hit_rate", "top2_any_hit_rate", "top2_mean_hits"}
                if not required.issubset(row) or int(row.get("targets", 0)) != int(splits[split]["targets"]):
                    errors.append(f"{model_name}/{split}: metrics or target counts are incomplete")
        perm = report.get("permutation_null_test", {})
        results = perm.get("results", {})
        if int(perm.get("permutations", 0)) < 199 or int(perm.get("family_size", 0)) != 3 or set(results) != set(models):
            errors.append("structural category null lacks 199+ replicates or the fixed three-model family")
        else:
            raw = {name: float(results[name]["p_one_sided_improvement"]) for name in models}
            adjusted = holm_adjust(raw)
            for name in models:
                row = results[name]
                if abs(float(row.get("p_holm_across_three_oos_models", -1)) - adjusted[name]) > 1e-8:
                    errors.append(f"{name}: Holm-adjusted OOS permutation p-value does not reconcile")
        if not errors:
            checks.append("fixed frequency/age/fusion models, Brier/log-loss/Top1/Top2, chronological splits, and recomputed Holm-corrected conditional randomization null validate")
    except Exception as exc:
        errors.append(f"Q55 validation raised {type(exc).__name__}: {exc}")
    return checks, errors, None


def validate_q60(archive_info):
    checks, errors = [], []
    override = None
    try:
        from scripts.sonar_position_regime_residual_lab import prospective_row_is_eligible
        position_path = ROOT / "reports" / "sequence_agent" / "position_mix_shadow.csv"
        global_path = ROOT / "reports" / "sequence_agent" / "shadow_forecasts.csv"
        with position_path.open(newline="", encoding="utf-8-sig") as f:
            position_rows_all = list(csv.DictReader(f))
        with global_path.open(newline="", encoding="utf-8-sig") as f:
            global_rows_all = list(csv.DictReader(f))
        position_rows = [r for r in position_rows_all if r.get("config_id") == "position_seed_mix_top20_v1"]
        global_rows = [r for r in global_rows_all if r.get("config_id") == "freq_100"]
        required = {"target_date", "frozen_at", "history_cutoff", "top20", "status", "actual_numbers", "hit_count", "all5_top20"}
        if not position_rows or not required.issubset(position_rows[0]):
            errors.append("positional shadow is empty or missing required freeze/outcome fields")
            return checks, errors, override
        if not global_rows or not required.issubset(global_rows[0]):
            errors.append("freq_100 comparator shadow is empty or missing required freeze/outcome fields")
            return checks, errors, override

        actual_by_date = archive_info["draws"]
        protocol_start = date(2026, 10, 19)
        def audit_evaluated(rows, label):
            evaluated_rows = [r for r in rows if r.get("status") == "EVALUATED"]
            for row in evaluated_rows:
                target_s = row["target_date"]
                if target_s not in actual_by_date:
                    errors.append(f"{label} evaluated target is absent from canonical archive: {target_s}")
                    continue
                actual = list(actual_by_date[target_s])
                if parse_numbers(row.get("actual_numbers", "")) != actual:
                    errors.append(f"{label} frozen outcome mismatch for {target_s}")
                top20 = parse_numbers(row.get("top20", ""))
                if len(top20) != 20 or len(set(top20)) != 20:
                    errors.append(f"{label} invalid Top20 at {target_s}")
                hits = sorted(set(top20) & set(actual))
                if int(row.get("hit_count", -1)) != len(hits):
                    errors.append(f"{label} hit count mismatch at {target_s}")
                if sorted(parse_numbers(row.get("hit_numbers", ""))) != hits:
                    errors.append(f"{label} hit list mismatch at {target_s}")
                if row.get("all5_top20") != ("1" if len(hits) == 5 else "0"):
                    errors.append(f"{label} Top20 5/5 flag mismatch at {target_s}")
            return evaluated_rows

        evaluated_position = audit_evaluated(position_rows, "position")
        evaluated_global = audit_evaluated(global_rows, "freq_100")
        def eligible(rows, config_id):
            return [
                row for row in rows
                if prospective_row_is_eligible(
                    row, actual_by_date, protocol_start, time(20, 0), ZoneInfo("Europe/Rome"), config_id
                )
            ]
        valid_position = eligible(position_rows, "position_seed_mix_top20_v1")
        valid_global = eligible(global_rows, "freq_100")
        position_by_date = {r["target_date"]: r for r in valid_position}
        global_by_date = {r["target_date"]: r for r in valid_global}
        if len(position_by_date) != len(valid_position) or len(global_by_date) != len(valid_global):
            errors.append("duplicate eligible target dates exist in a shadow comparator")
        paired_dates = sorted(set(position_by_date) & set(global_by_date))
        paired_position = [position_by_date[d] for d in paired_dates]
        paired_global = [global_by_date[d] for d in paired_dates]
        gate = read_json("reports/sequence_agent/prospective_promotion_gate.json")
        if int(gate.get("valid_complete_prospective_targets", -1)) != len(paired_dates):
            errors.append("gate paired target count does not match the eligible position/global shadow intersection")
        if gate.get("paired_target_dates") != paired_dates:
            errors.append("gate paired target dates do not match the eligible shadow intersection")
        if int(gate.get("evaluated_position_shadow_rows_total", -1)) != len(evaluated_position):
            errors.append("gate evaluated positional row count does not match shadow CSV")
        if int(gate.get("excluded_position_rows", -1)) != len(evaluated_position) - len(valid_position):
            errors.append("gate excluded positional row count does not match eligibility audit")
        if int(gate.get("eligible_position_rows_without_global_pair", -1)) != len(set(position_by_date) - set(global_by_date)):
            errors.append("gate position-only eligible count does not reconcile")
        if int(gate.get("eligible_global_rows_without_position_pair", -1)) != len(set(global_by_date) - set(position_by_date)):
            errors.append("gate global-only eligible count does not reconcile")
        position_five = sum(r.get("all5_top20") == "1" for r in paired_position)
        global_five = sum(r.get("all5_top20") == "1" for r in paired_global)
        position_hits = [int(r["hit_count"]) for r in paired_position]
        if int(gate.get("position_top20_5of5", -1)) != position_five:
            errors.append("gate positional 5/5 count does not reconcile to paired freezes")
        if int(gate.get("global_top20_5of5", -1)) != global_five:
            errors.append("gate global 5/5 count does not reconcile to paired freezes")
        if int(gate.get("top20_4plus", -1)) != sum(h >= 4 for h in position_hits):
            errors.append("gate positional 4+ count does not reconcile to paired freezes")
        mean_hits = sum(position_hits) / len(position_hits) if position_hits else None
        if mean_hits is None:
            if gate.get("mean_position_top20_hits") is not None:
                errors.append("gate mean positional hits should be null for an empty paired sample")
        elif abs(float(gate.get("mean_position_top20_hits", -999)) - mean_hits) > 1e-9:
            errors.append("gate mean positional hits does not reconcile to paired freezes")
        for rows in (position_rows_all, global_rows_all):
            for row in rows:
                if row.get("status") == "FROZEN_PENDING" and row.get("target_date") in actual_by_date:
                    if date.fromisoformat(row["target_date"]) < date.fromisoformat(archive_info["last_date"]):
                        errors.append(f"stale pending freeze should have been evaluated: {row['target_date']}")
        if gate.get("promotion_allowed") is not False or int(gate.get("missing_freezes_reconstructed", -1)) != 0:
            errors.append("promotion gate must keep auto-promotion disabled and never reconstruct missing freezes")
        minimum = int(gate.get("minimum_required", 200))
        if len(paired_dates) < minimum:
            if gate.get("status") != "INSUFFICIENT_PROSPECTIVE_CASES":
                errors.append("gate status must be INSUFFICIENT_PROSPECTIVE_CASES below its paired minimum")
            else:
                override = "VALIDATED_INSUFFICIENT_DATA"
        elif gate.get("status") == "REVIEW_REQUIRED_NO_AUTO_PROMOTION" and gate.get("promotion_allowed") is False:
            override = "VALIDATED_REQUIRES_MANUAL_REVIEW"
        else:
            errors.append("gate cannot promote without explicit manual review while auto-promotion remains disabled")
        if not errors:
            checks.append(f"{len(paired_dates)} paired complete prospective cases reconcile across immutable position/global freezes; auto-promotion remains disabled")
    except Exception as exc:
        errors.append(f"Q60 validation raised {type(exc).__name__}: {exc}")
    return checks, errors, override

VALIDATORS = {
    "Q10": lambda info: validate_q10(),
    "Q20": lambda info: validate_q20(info),
    "Q30": lambda info: validate_q30(),
    "Q40": lambda info: validate_q40(),
    "Q50": lambda info: validate_q50(),
    "Q55": lambda info: validate_q55(),
    "Q60": lambda info: validate_q60(info),
}

NEXT_ACTIONS = {
    "Q00": "Keep archive and metrics synchronized; evaluate every pending freeze once its canonical outcome exists.",
    "Q10": "Inspect cascade-loss counts and conditional Top10/Top5 transitions on the same chronological targets.",
    "Q20": "Repair any residual cutoff, Top20 hit-count, residual-list, or feature-flag mismatch.",
    "Q30": "Re-run fixed mixes and recompute the Holm family whenever a mix or split changes.",
    "Q40": "Recompute paired global-vs-positional metrics on identical targets and chronological splits.",
    "Q50": "Retain age/hazard only if Brier/log-loss improvements survive the conditional randomization and Holm checks.",
    "Q55": "Compare frequency, age-hazard, and equal-weight fusion; prioritize only blind-OOS improvements that survive Holm.",
    "Q60": "Collect at least the registered paired minimum (currently 200 complete cases; 100 is only an early monitoring milestone), obtain manual review, and keep promotion disabled.",
}


def main():
    plan = read_json("reports/sequence_agent/research_backlog.json")
    tasks = plan.get("tasks", [])
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise SystemExit("QUEUE_INVALID: duplicate task id")
    for task in tasks:
        missing = [dep for dep in task.get("depends_on", []) if dep not in by_id]
        if missing:
            raise SystemExit(f"QUEUE_INVALID: {task['id']} has unknown dependencies {missing}")
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            raise SystemExit(f"QUEUE_INVALID: dependency cycle at {task_id}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dep in by_id[task_id].get("depends_on", []):
            visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id)

    q00_checks, q00_errors, archive_info = validate_q00()
    states = {}
    for task in sorted(tasks, key=lambda item: (item["priority"], item["id"])):
        task_id = task["id"]
        missing_evidence = [p for p in task.get("evidence", []) if not (ROOT / p).is_file()]
        dependencies = [states[d]["status"] for d in task.get("depends_on", [])]
        if task_id == "Q00":
            checks, errors, override = q00_checks, q00_errors, None
        elif task_id in VALIDATORS:
            if archive_info is None:
                checks, errors, override = [], ["canonical archive validation failed; dependent acceptance checks cannot run"], None
            else:
                checks, errors, override = VALIDATORS[task_id](archive_info)
        else:
            checks, errors, override = [], ["no task-specific acceptance validator is registered"], None

        if missing_evidence:
            status = "READY" if all(s == "COMPLETE" for s in dependencies) else "BLOCKED_BY_DEPENDENCY"
        elif errors:
            status = "VALIDATION_FAILED"
        elif any(s != "COMPLETE" for s in dependencies):
            status = "BLOCKED_BY_DEPENDENCY"
        elif override:
            status = override
        else:
            status = "COMPLETE"
        next_action = "No action; declared acceptance checks passed." if status == "COMPLETE" else NEXT_ACTIONS.get(task_id, "Resolve the reported validation blockers.")
        states[task_id] = {
            "id": task_id,
            "priority": task["priority"],
            "title": task["title"],
            "status": status,
            "depends_on": task.get("depends_on", []),
            "missing_evidence": missing_evidence,
            "validation_passed": not errors and not missing_evidence,
            "validation_checks": checks,
            "validation_errors": errors,
            "acceptance_criteria": task.get("acceptance", []),
            "next_action": next_action,
        }

    ordered_states = list(states.values())
    failed = sum(s["status"] == "VALIDATION_FAILED" for s in ordered_states)
    missing = sum(bool(s["missing_evidence"]) for s in ordered_states)
    active_candidates = [
        s for s in ordered_states
        if s["status"] in {"READY", "VALIDATION_FAILED", "EVIDENCE_PRESENT_REQUIRES_VALIDATION",
                           "VALIDATED_INSUFFICIENT_DATA", "VALIDATED_REQUIRES_MANUAL_REVIEW"}
    ]
    active = active_candidates[0] if active_candidates else None
    output = {
        "generated_at_utc": datetime.now().astimezone().astimezone(ZoneInfo("UTC")).isoformat(),
        "project": plan["project"],
        "queue_status": "QUEUE_VALID" if failed == 0 and missing == 0 else "QUEUE_VALID_WITH_BLOCKERS",
        "completion_gate_status": "OPEN" if any(s["status"] != "COMPLETE" for s in ordered_states) else "ALL_ACCEPTANCE_GATES_PASSED",
        "task_count": len(tasks),
        "complete_count": sum(s["status"] == "COMPLETE" for s in ordered_states),
        "validated_count": sum(s["validation_passed"] for s in ordered_states),
        "failed_count": failed,
        "missing_evidence_count": missing,
        "ready_count": sum(s["status"] == "READY" for s in ordered_states),
        "active_next_task": active["id"] if active else None,
        "active_next_task_title": active["title"] if active else None,
        "active_next_task_action": active["next_action"] if active else None,
        "tasks": ordered_states,
        "guardrail": "File presence is not completion. Each task is complete only when its acceptance validator passes and dependencies are complete. Prospective promotion remains disabled until the minimum prospective sample and manual review.",
    }
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in (
        "queue_status", "completion_gate_status", "task_count", "complete_count",
        "validated_count", "failed_count", "missing_evidence_count", "ready_count",
        "active_next_task", "active_next_task_title", "active_next_task_action"
    )}, ensure_ascii=False))
    if os.environ.get("SONAR_EMIT_REPORT") == "1":
        print("SONAR_RESEARCH_QUEUE_REPORT_BEGIN")
        print(json.dumps(output, indent=2, ensure_ascii=False))
        print("SONAR_RESEARCH_QUEUE_REPORT_END")
    if failed or missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
