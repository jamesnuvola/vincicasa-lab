#!/usr/bin/env python3
"""SONAR Sequence Discovery Agent.

Reconstructs fixed, leakage-safe candidate-generation rules for VinciCasa,
logs each rule/draw outcome, searches for repeated success sequences, and
freezes prospective shadow forecasts. Historical reconstruction is explicitly
labelled as retrospective; it is not a record of forecasts made at the time.
Only Python's standard library is required.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from itertools import combinations
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
LEDGER = OUT / "historical_rule_ledger.csv"
METRICS = OUT / "latest_metrics.json"
SIGNATURES = OUT / "draw_signatures.csv"
WAVES = OUT / "wave_events.csv"
SHADOW = OUT / "shadow_forecasts.csv"
MIN_HISTORY = 200
NUMBERS = tuple(range(1, 41))
RNG_TOP20_P = math.comb(20, 5) / math.comb(40, 5)
RNG_TOP10_P = math.comb(10, 5) / math.comb(40, 5)
RNG_TOP5_P = math.comb(5, 5) / math.comb(40, 5)
ROME = ZoneInfo("Europe/Rome")

# Fixed rule grammar. Changes to this list create a new experiment version.
WINDOWS = (5, 10, 20, 50, 100, 200)
HALF_LIVES = (10, 30, 60, 120)
BASE_RULES = (
    [f"freq_{w}" for w in WINDOWS]
    + [f"decay_{h}" for h in HALF_LIVES]
    + ["gap_age", "return_fit", "momentum_10_50", "momentum_20_100",
       "position_global", "prev_1", "prev_3", "prev_5",
       "arith_1", "arith_3", "arith_5", "complement_1",
       "transition_position", "pair_affinity_50"]
)
PAIR_RULES = (
    ("freq_20", "momentum_10_50"),
    ("freq_20", "return_fit"),
    ("freq_20", "position_global"),
    ("freq_20", "arith_3"),
    ("freq_50", "momentum_20_100"),
    ("freq_50", "gap_age"),
    ("decay_30", "return_fit"),
    ("decay_60", "position_global"),
    ("prev_3", "arith_3"),
    ("prev_3", "complement_1"),
    ("arith_3", "gap_age"),
    ("transition_position", "momentum_10_50"),
)
CHAIN_RULES = (
    ("freq_20", "momentum_10_50", "arith_3"),
    ("freq_50", "return_fit", "position_global"),
    ("decay_30", "prev_3", "arith_3"),
    ("prev_1", "transition_position", "gap_age"),
    ("freq_20", "pair_affinity_50", "complement_1"),
    ("freq_100", "momentum_20_100", "return_fit"),
)
CONFIGS = [(name, "family", (name,)) for name in BASE_RULES]
CONFIGS += [
    ("PAIR::" + ">".join(pair), "pair", pair) for pair in PAIR_RULES
]
CONFIGS += [
    ("CHAIN::" + ">".join(chain), "chain", chain) for chain in CHAIN_RULES
]
CONFIG_BY_ID = {config[0]: config for config in CONFIGS}


def read_draws():
    if not DATA.exists():
        raise RuntimeError(f"PIPELINE BLOCKED: archivio mancante: {DATA.relative_to(ROOT)}")
    with DATA.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        expected = ["data", "n1", "n2", "n3", "n4", "n5"]
        if reader.fieldnames != expected:
            raise RuntimeError(f"PIPELINE BLOCKED: intestazione CSV inattesa: {reader.fieldnames}")
        draws = []
        seen_dates = set()
        for line, row in enumerate(reader, start=2):
            try:
                d = date.fromisoformat(row["data"])
                nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            except Exception as exc:
                raise RuntimeError(f"PIPELINE BLOCKED: riga {line} non leggibile: {exc}") from exc
            if d in seen_dates:
                raise RuntimeError(f"PIPELINE BLOCKED: data duplicata {d}")
            if tuple(sorted(set(nums))) != nums or any(n < 1 or n > 40 for n in nums):
                raise RuntimeError(f"PIPELINE BLOCKED: cinquina non valida alla riga {line}: {nums}")
            if draws and d <= draws[-1]["date"]:
                raise RuntimeError(f"PIPELINE BLOCKED: date non crescenti alla riga {line}")
            seen_dates.add(d)
            draws.append({"date": d, "nums": nums})
    if len(draws) <= MIN_HISTORY:
        raise RuntimeError(f"PIPELINE BLOCKED: servono più di {MIN_HISTORY} estrazioni, trovate {len(draws)}")
    return draws


def csv_write(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rank_numbers(scores):
    # Stable deterministic tie break; scores are calculated from the prefix only.
    order = sorted(NUMBERS, key=lambda n: (-float(scores.get(n, 0.0)), n))
    return order, {n: i + 1 for i, n in enumerate(order)}


def last_seen_age(history, n):
    for age, draw in enumerate(reversed(history), start=0):
        if n in draw["nums"]:
            return age
    return len(history) + 1


def arithmetic_support(history, k):
    support = Counter()
    recent = history[-k:]
    for draw in recent:
        values = set(draw["nums"])
        for n in values:
            support[n] += 1.0
            support[41 - n] += 0.5
        for a, b in combinations(draw["nums"], 2):
            diff = abs(a - b)
            total = a + b
            if 1 <= diff <= 40:
                support[diff] += 1.0
            if 1 <= total <= 40:
                support[total] += 1.0
            folded = ((total - 1) % 40) + 1
            support[folded] += 0.5
            folded_diff = ((diff - 1) % 40) + 1
            support[folded_diff] += 0.5
    return {n: float(support[n]) for n in NUMBERS}


def feature_scores(history):
    """Return deterministic number scores derived strictly from prior draws."""
    hlen = len(history)
    scores = {name: {} for name in BASE_RULES}
    counts = {n: sum(n in d["nums"] for d in history) for n in NUMBERS}
    positions_by_number = {n: [] for n in NUMBERS}
    for draw_index, draw in enumerate(history):
        for number in draw["nums"]:
            positions_by_number[number].append(draw_index)
    for w in WINDOWS:
        window = history[-min(w, hlen):]
        for n in NUMBERS:
            scores[f"freq_{w}"][n] = sum(n in d["nums"] for d in window)
    for half in HALF_LIVES:
        for n in NUMBERS:
            scores[f"decay_{half}"][n] = sum(
                math.exp(-age / half)
                for age, draw in enumerate(reversed(history[-200:]))
                if n in draw["nums"]
            )
    ages = {n: last_seen_age(history, n) for n in NUMBERS}
    for n in NUMBERS:
        scores["gap_age"][n] = ages[n]
        positions = positions_by_number[n]
        gaps = [b - a for a, b in zip(positions, positions[1:])]
        typical = statistics.median(gaps) if gaps else max(1.0, hlen / (counts[n] + 1))
        scores["return_fit"][n] = -abs(ages[n] - typical)
        recent10 = history[-10:]
        prev50 = history[-60:-10]
        recent20 = history[-20:]
        prev100 = history[-120:-20]
        r10 = sum(n in d["nums"] for d in recent10) / max(1, len(recent10))
        p50 = sum(n in d["nums"] for d in prev50) / max(1, len(prev50))
        r20 = sum(n in d["nums"] for d in recent20) / max(1, len(recent20))
        p100 = sum(n in d["nums"] for d in prev100) / max(1, len(prev100))
        scores["momentum_10_50"][n] = r10 - p50
        scores["momentum_20_100"][n] = r20 - p100
        # Expected rank-position from the number's location in the 1..40 range.
        # Score frequency in that rank, not the number's global count.
        expected_pos = min(4, max(0, round((n - 1) * 4 / 39)))
        recent200 = history[-200:]
        scores["position_global"][n] = sum(
            d["nums"][expected_pos] == n for d in recent200
        ) / max(1, len(recent200))
        scores["prev_1"][n] = float(n in history[-1]["nums"])
        scores["prev_3"][n] = sum((1.0 / (lag + 1)) for lag, d in enumerate(reversed(history[-3:])) if n in d["nums"])
        scores["prev_5"][n] = sum((1.0 / (lag + 1)) for lag, d in enumerate(reversed(history[-5:])) if n in d["nums"])
        scores["complement_1"][n] = float(41 - n in history[-1]["nums"])
        # Position transition: support in the same position in the latest 5 draws,
        # discounted by lag. This remains a global number score for Top20 evaluation.
        expected_pos = min(4, max(0, round((n - 1) * 4 / 39)))
        scores["transition_position"][n] = sum(
            (1.0 / (lag + 1)) * math.exp(-abs(pos - expected_pos) / 1.5)
            for lag, d in enumerate(reversed(history[-5:]))
            for pos, value in enumerate(d["nums"]) if value == n
        )
    for k in (1, 3, 5):
        support = arithmetic_support(history, k)
        for n in NUMBERS:
            scores[f"arith_{k}"][n] = support[n]
    recent = history[-50:]
    pair_counts = Counter()
    for d in recent:
        pair_counts.update(combinations(d["nums"], 2))
    recent_numbers = set(n for d in history[-3:] for n in d["nums"])
    for n in NUMBERS:
        scores["pair_affinity_50"][n] = sum(
            pair_counts[tuple(sorted((n, other)))]
            for other in recent_numbers if other != n
        )
    return scores


def combine_scores(base_scores, family_sequence):
    # Convert each stage to ordinal rank points before combining, preventing
    # arbitrary units (counts vs decay vs gaps) from dominating a chain.
    ranks = {name: rank_numbers(base_scores[name])[1] for name in set(family_sequence)}
    weights = list(range(len(family_sequence), 0, -1))
    result = {}
    for n in NUMBERS:
        total = 0.0
        for name, weight in zip(family_sequence, weights):
            total += weight * (41 - ranks[name][n]) / 40.0
        result[n] = total / sum(weights)
    return result


def cascade_rank(base_scores, family_sequence):
    """A literal ordered cascade: each stage narrows the surviving candidate set."""
    candidates = list(NUMBERS)
    keep_sizes = {3: (30, 25, 20), 2: (30, 20)}
    sizes = keep_sizes.get(len(family_sequence), tuple(
        max(20, 40 - round(20 * (i + 1) / len(family_sequence)))
        for i in range(len(family_sequence))
    ))
    for stage_index, family in enumerate(family_sequence):
        ordered = sorted(candidates, key=lambda n: (-float(base_scores[family][n]), n))
        keep = sizes[min(stage_index, len(sizes) - 1)]
        candidates = ordered[:keep]
    # Return the survivors first, followed by the excluded numbers in a stable
    # order. This gives Top20 the cascade semantics while preserving Top10/Top5.
    survivor_order = list(candidates)
    excluded = [n for n in NUMBERS if n not in set(survivor_order)]
    return survivor_order + excluded


def describe_draw(draw, previous_draws):
    nums = draw["nums"]
    gaps = tuple(b - a for a, b in zip(nums, nums[1:]))
    return {
        "date": draw["date"].isoformat(),
        "numbers": " ".join(map(str, nums)),
        "sum": sum(nums),
        "product": math.prod(nums),
        "range": nums[-1] - nums[0],
        "gaps": "-".join(map(str, gaps)),
        "odd_count": sum(n % 2 for n in nums),
        "even_count": sum(n % 2 == 0 for n in nums),
        "mod5": "-".join(str(n % 5) for n in nums),
        "decades": "-".join(str((n - 1) // 10) for n in nums),
        "overlap_prev1": len(set(nums) & set(previous_draws[-1]["nums"])) if previous_draws else 0,
        "overlap_prev2": len(set(nums) & set(n for d in previous_draws[-2:] for n in d["nums"])),
        "overlap_prev3": len(set(nums) & set(n for d in previous_draws[-3:] for n in d["nums"])),
    }


def evaluate(draws):
    ledger = []
    signature_rows = []
    aggregate = {
        name: {"tested": 0, "hits": Counter(), "all5": 0, "top10_all5": 0, "top5_all5": 0,
               "hit_sum": 0, "success_dates": []}
        for name, _, _ in CONFIGS
    }
    for i in range(MIN_HISTORY, len(draws)):
        history = draws[:i]
        target = draws[i]
        base = feature_scores(history)
        predictions = {}
        for config_id, config_type, sequence in CONFIGS:
            if config_type == "chain":
                ranked = cascade_rank(base, sequence)
            else:
                rule_scores = base[sequence[0]] if len(sequence) == 1 else combine_scores(base, sequence)
                ranked, _ = rank_numbers(rule_scores)
            top20 = ranked[:20]
            hits = sorted(set(top20) & set(target["nums"]))
            top10_hits = len(set(ranked[:10]) & set(target["nums"]))
            top5_hits = len(set(ranked[:5]) & set(target["nums"]))
            all5 = len(hits) == 5
            predictions[config_id] = ranked
            stats = aggregate[config_id]
            stats["tested"] += 1
            stats["hits"][len(hits)] += 1
            stats["hit_sum"] += len(hits)
            stats["all5"] += int(all5)
            stats["top10_all5"] += int(top10_hits == 5)
            stats["top5_all5"] += int(top5_hits == 5)
            if all5:
                stats["success_dates"].append(target["date"].isoformat())
            ledger.append({
                "target_date": target["date"].isoformat(),
                "history_cutoff": history[-1]["date"].isoformat(),
                "config_id": config_id,
                "config_type": config_type,
                "rule_sequence": ">".join(sequence),
                "top20": " ".join(map(str, top20)),
                "top10": " ".join(map(str, ranked[:10])),
                "top5": " ".join(map(str, ranked[:5])),
                "hit_numbers": " ".join(map(str, hits)),
                "hit_count": len(hits),
                "top10_hit_count": top10_hits,
                "top5_hit_count": top5_hits,
                "all5_top20": int(all5),
                "actual_numbers": " ".join(map(str, target["nums"])),
                "evaluation_mode": "RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW",
            })
        sig = describe_draw(target, history)
        row_for_target = [r for r in ledger[-len(CONFIGS):]]
        sig["configs_tested"] = len(CONFIGS)
        sig["configs_top20_5of5"] = sum(int(r["all5_top20"]) for r in row_for_target)
        sig["best_top20_hits"] = max(int(r["hit_count"]) for r in row_for_target)
        sig["any_config_5of5"] = int(sig["configs_top20_5of5"] > 0)
        signature_rows.append(sig)
    return ledger, signature_rows, aggregate


def binomial_z(observed, n, p):
    expected = n * p
    sd = math.sqrt(max(1e-12, n * p * (1.0 - p)))
    return (observed - expected) / sd


def build_metrics(draws, aggregate, signature_rows):
    n = len(signature_rows)
    configs = []
    for config_id, config_type, sequence in CONFIGS:
        s = aggregate[config_id]
        tested = s["tested"]
        observed = s["all5"]
        configs.append({
            "config_id": config_id,
            "config_type": config_type,
            "rule_sequence": list(sequence),
            "draws_tested": tested,
            "mean_top20_hits": round(s["hit_sum"] / tested, 6) if tested else None,
            "top20_hit_distribution": {str(k): int(s["hits"].get(k, 0)) for k in range(6)},
            "top20_5of5_count": observed,
            "top20_5of5_rate": round(observed / tested, 8) if tested else None,
            "top20_5of5_random_baseline_rate": round(RNG_TOP20_P, 8),
            "top20_5of5_random_expected_count": round(tested * RNG_TOP20_P, 4),
            "top20_5of5_baseline_z_approx": round(binomial_z(observed, tested, RNG_TOP20_P), 4) if tested else None,
            "top10_5of5_count": int(s["top10_all5"]),
            "top10_5of5_random_baseline_rate": round(RNG_TOP10_P, 8),
            "top5_5of5_count": int(s["top5_all5"]),
            "top5_5of5_random_baseline_rate": round(RNG_TOP5_P, 8),
            "retrospective_success_dates": s["success_dates"],
        })
    configs.sort(key=lambda x: (-x["top20_5of5_count"], -x["mean_top20_hits"], x["config_id"]))
    return {
        "agent": "SONAR Sequence Discovery Agent",
        "version": "1.0.0",
        "status": "COMPLETE_RETROSPECTIVE_RUN" if n else "INCOMPLETE",
        "scope": "VinciCasa 5/40; this agent is separate from WFL and SuperEnalotto",
        "source": "data/storico_daily.csv",
        "data_first_date": draws[0]["date"].isoformat(),
        "data_last_date": draws[-1]["date"].isoformat(),
        "total_draws": len(draws),
        "min_history_before_target": MIN_HISTORY,
        "walk_forward_targets_evaluated": n,
        "rule_configurations_tested": len(CONFIGS),
        "historical_ledger_rows": n * len(CONFIGS),
        "top20_5of5_random_baseline": {
            "probability": RNG_TOP20_P,
            "expected_count_per_1000_targets": round(1000 * RNG_TOP20_P, 3),
            "note": "Exact combinatorial baseline for a fixed 20-number set; z scores are approximate and do not correct for dependence or multiple testing."
        },
        "top10_5of5_random_baseline": RNG_TOP10_P,
        "top5_5of5_random_baseline": RNG_TOP5_P,
        "draws_with_any_config_top20_5of5": sum(int(r["any_config_5of5"]) for r in signature_rows),
        "draws_with_any_config_top20_5of5_rate": round(sum(int(r["any_config_5of5"]) for r in signature_rows) / n, 8) if n else None,
        "interpretation_guardrail": "Retrospective results generate hypotheses only. A success discovered after examining the target is not an ex-ante forecast. Compare fixed rules against baseline and validate prospective shadow forecasts.",
        "configurations": configs,
    }


def load_shadow():
    if not SHADOW.exists():
        return []
    with SHADOW.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def shadow_update(draws):
    """Evaluate frozen forecasts when a target enters the archive, then freeze next."""
    rows = load_shadow()
    by_target = defaultdict(list)
    for row in rows:
        by_target[row["target_date"]].append(row)
    actual_by_date = {d["date"].isoformat(): d["nums"] for d in draws}
    changed = False
    for target_date, entries in by_target.items():
        if target_date in actual_by_date:
            actual = set(actual_by_date[target_date])
            for row in entries:
                if row.get("status") != "EVALUATED":
                    top20 = set(int(v) for v in row["top20"].split())
                    row["actual_numbers"] = " ".join(map(str, sorted(actual)))
                    row["hit_numbers"] = " ".join(map(str, sorted(actual & top20)))
                    row["hit_count"] = str(len(actual & top20))
                    row["all5_top20"] = str(int(len(actual & top20) == 5))
                    row["status"] = "EVALUATED"
                    row["evaluated_at_data_through"] = target_date
                    changed = True
    now = datetime.now(ROME)
    today = now.date()
    latest = draws[-1]["date"]
    # Forecast today's draw only if the latest archive ends yesterday and it is
    # still before the nominal draw time; otherwise freeze the next calendar day.
    before_cutoff = (now.hour, now.minute) < (20, 30)
    if latest >= today:
        target = latest + timedelta(days=1)
    elif latest == today - timedelta(days=1) and before_cutoff:
        target = today
    else:
        target = max(today + timedelta(days=1), latest + timedelta(days=1))
    # Never create a forecast for a later draw while an earlier frozen
    # forecast is still awaiting its official result in the canonical archive.
    pending_dates = sorted(
        target_date for target_date, entries in by_target.items()
        if target_date not in actual_by_date
        and any(entry.get("status") == "FROZEN_PENDING" for entry in entries)
    )
    target_s = pending_dates[0] if pending_dates else target.isoformat()
    if target_s not in by_target:
        history = draws
        base = feature_scores(history)
        created_at = now.isoformat(timespec="seconds")
        for config_id, config_type, sequence in CONFIGS:
            if config_type == "chain":
                ranked = cascade_rank(base, sequence)
            else:
                rule_scores = base[sequence[0]] if len(sequence) == 1 else combine_scores(base, sequence)
                ranked, _ = rank_numbers(rule_scores)
            rows.append({
                "target_date": target_s,
                "frozen_at": created_at,
                "history_cutoff": latest.isoformat(),
                "config_id": config_id,
                "config_type": config_type,
                "rule_sequence": ">".join(sequence),
                "top20": " ".join(map(str, ranked[:20])),
                "top10": " ".join(map(str, ranked[:10])),
                "top5": " ".join(map(str, ranked[:5])),
                "status": "FROZEN_PENDING",
                "actual_numbers": "",
                "hit_numbers": "",
                "hit_count": "",
                "all5_top20": "",
                "evaluated_at_data_through": "",
                "timeliness_note": "Frozen before nominal draw time" if target == today and before_cutoff else "Frozen for next target date; verify timing against official draw schedule",
            })
        changed = True
    # Keep every frozen forecast, including misses; never replace a forecast for
    # a target date that already has a row.
    if changed or not SHADOW.exists():
        fields = ["target_date", "frozen_at", "history_cutoff", "config_id", "config_type",
                  "rule_sequence", "top20", "top10", "top5", "status", "actual_numbers",
                  "hit_numbers", "hit_count", "all5_top20", "evaluated_at_data_through",
                  "timeliness_note"]
        csv_write(SHADOW, fields, rows)
    return rows


def build_wave_events(ledger):
    successes = defaultdict(list)
    for row in ledger:
        if row["all5_top20"] == "1":
            successes[row["config_id"]].append(row)
    events = []
    for config_id, rows in successes.items():
        rows.sort(key=lambda r: r["target_date"])
        run = []
        prev_date = None
        for row in rows:
            d = date.fromisoformat(row["target_date"])
            if run and (d - prev_date).days != 1:
                events.append(wave_row(config_id, run))
                run = []
            run.append(row)
            prev_date = d
        if run:
            events.append(wave_row(config_id, run))
    events.sort(key=lambda r: (-int(r["consecutive_successes"]), r["config_id"], r["start_date"]))
    return events


def wave_row(config_id, run):
    return {
        "config_id": config_id,
        "rule_sequence": run[0]["rule_sequence"],
        "start_date": run[0]["target_date"],
        "end_date": run[-1]["target_date"],
        "consecutive_successes": len(run),
        "success_dates": " ".join(r["target_date"] for r in run),
        "event_type": "REPEATED_WAVE_CANDIDATE" if len(run) >= 2 else "ISOLATED_SUCCESS",
        "evaluation_mode": "RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW",
    }


def main():
    draws = read_draws()
    ledger, signatures, aggregate = evaluate(draws)
    metrics = build_metrics(draws, aggregate, signatures)
    OUT.mkdir(parents=True, exist_ok=True)
    csv_write(LEDGER, ["target_date", "history_cutoff", "config_id", "config_type",
                       "rule_sequence", "top20", "top10", "top5", "hit_numbers",
                       "hit_count", "top10_hit_count", "top5_hit_count", "all5_top20",
                       "actual_numbers", "evaluation_mode"], ledger)
    csv_write(SIGNATURES, ["date", "numbers", "sum", "product", "range", "gaps",
                           "odd_count", "even_count", "mod5", "decades", "overlap_prev1",
                           "overlap_prev2", "overlap_prev3", "configs_tested",
                           "configs_top20_5of5", "best_top20_hits", "any_config_5of5"], signatures)
    csv_write(WAVES, ["config_id", "rule_sequence", "start_date", "end_date",
                      "consecutive_successes", "success_dates", "event_type", "evaluation_mode"],
              build_wave_events(ledger))
    shadow_rows = shadow_update(draws)
    metrics["shadow_forecasts_total"] = len(shadow_rows)
    metrics["shadow_forecasts_pending"] = sum(r.get("status") == "FROZEN_PENDING" for r in shadow_rows)
    metrics["shadow_forecasts_evaluated"] = sum(r.get("status") == "EVALUATED" for r in shadow_rows)
    metrics["shadow_forecast_policy"] = "Append-only per target date; no retrospective reconstruction; outcomes filled only after target appears in canonical archive."
    METRICS.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": metrics["status"],
        "data_last_date": metrics["data_last_date"],
        "total_draws": metrics["total_draws"],
        "targets_evaluated": metrics["walk_forward_targets_evaluated"],
        "configurations": metrics["rule_configurations_tested"],
        "ledger_rows": metrics["historical_ledger_rows"],
        "shadow_pending": metrics["shadow_forecasts_pending"],
        "metrics_path": str(METRICS.relative_to(ROOT)),
        "ledger_path": str(LEDGER.relative_to(ROOT)),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
