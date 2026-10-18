#!/usr/bin/env python3
"""Leakage-safe VinciCasa positional, regime, residual and gap-hazard research."""
from __future__ import annotations
import csv, json, math, random, statistics
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/storico_daily.csv"
OUT = ROOT / "reports/sequence_agent"
NUMBERS = tuple(range(1, 41))
K = 5
NCOMB = math.comb(40, 5)
BASE_P = 5 / 40
WARMUP = 500
PRIOR_STRENGTH = 30.0
ROME = ZoneInfo("Europe/Rome")
DRAW_TIME = time(20, 0)
GAP_BUCKETS = ((0, 4, "0-4"), (5, 9, "5-9"), (10, 19, "10-19"), (20, 10**9, "20+"))

def comb0(n, r):
    return math.comb(n, r) if 0 <= r <= n else 0

def position_prob(pos, value):
    # Exact order-statistic probability for the pos-th smallest of a uniform 5-of-40 draw.
    return comb0(value - 1, pos - 1) * comb0(40 - value, 5 - pos) / NCOMB

THEORY = {p: {x: position_prob(p, x) for x in range(p, 36 + p)} for p in range(1, 6)}

def load_data():
    if not DATA.is_file():
        raise SystemExit("PIPELINE BLOCKED: data/storico_daily.csv missing")
    rows = []
    with DATA.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            raise SystemExit(f"PIPELINE BLOCKED: unexpected CSV header {reader.fieldnames}")
        for line, row in enumerate(reader, 2):
            try:
                date = row["data"]
                nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            except Exception as exc:
                raise SystemExit(f"PIPELINE BLOCKED: invalid row {line}: {exc}")
            if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n < 1 or n > 40 for n in nums):
                raise SystemExit(f"PIPELINE BLOCKED: invalid five-number draw at CSV line {line}: {nums}")
            rows.append((date, nums))
    dates = [d for d, _ in rows]
    if len(rows) < 1000 or len(dates) != len(set(dates)) or dates != sorted(dates):
        raise SystemExit("PIPELINE BLOCKED: too few draws, duplicate dates, or dates not strictly ordered")
    return rows

def gamma_q(a, x):
    """Regularized upper incomplete gamma Q(a,x), Numerical Recipes approximation."""
    if x <= 0: return 1.0
    gln = math.lgamma(a)
    if x < a + 1:
        ap, term, total = a, 1.0 / a, 1.0 / a
        for _ in range(10000):
            ap += 1
            term *= x / ap
            total += term
            if abs(term) < abs(total) * 1e-14: break
        p = total * math.exp(-x + a * math.log(x) - gln)
        return max(0.0, min(1.0, 1.0 - p))
    b = x + 1.0 - a
    c = 1.0 / 1e-300
    d = 1.0 / b
    h = d
    for i in range(1, 10000):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < 1e-300: d = 1e-300
        c = b + an / c
        if abs(c) < 1e-300: c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14: break
    return max(0.0, min(1.0, math.exp(-x + a * math.log(x) - gln) * h))

def grouped_gof(pos, observed):
    # Merge adjacent support values until each expected cell has >=5 observations.
    support = sorted(THEORY[pos])
    groups, cur, expct, obsct = [], [], 0.0, 0
    total = sum(observed.values())
    for x in support:
        cur.append(x); expct += total * THEORY[pos][x]; obsct += observed.get(x, 0)
        if expct >= 5:
            groups.append((cur, expct, obsct)); cur, expct, obsct = [], 0.0, 0
    if cur:
        if groups:
            old, e, o = groups.pop()
            groups.append((old + cur, e + expct, o + obsct))
        else:
            groups.append((cur, expct, obsct))
    chi2 = sum((o - e) ** 2 / e for _, e, o in groups if e > 0)
    df = max(1, len(groups) - 1)
    return {"chi_square": chi2, "degrees_freedom": df, "p_value": gamma_q(df / 2, chi2 / 2),
            "groups": [{"values": g, "expected": round(e, 4), "observed": o} for g, e, o in groups]}

def holm_adjust(items):
    # items: list of (key,p); returns Holm step-down adjusted p values.
    ordered = sorted(items, key=lambda z: z[1])
    out, running, m = {}, 0.0, len(ordered)
    for i, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p))
        out[key] = running
    return out

def gap_bucket(age):
    for lo, hi, label in GAP_BUCKETS:
        if lo <= age <= hi: return label
    return "20+"

def rank_values(scores, allowed=NUMBERS):
    return sorted(allowed, key=lambda n: (-scores.get(n, 0.0), n))

def position_mix_forecast(history):
    """Create a deterministic Top20 from prior-100 global ranks plus position-conditioned seeds."""
    train = history[-100:]
    global_counts = Counter(n for draw in train for n in draw)
    global_rank = rank_values(global_counts)
    scores = {}
    for pos in range(1, 6):
        counts = Counter(draw[pos - 1] for draw in train)
        for value in THEORY[pos]:
            scores[(pos, value)] = counts[value] + PRIOR_STRENGTH * THEORY[pos][value]
    seeds = set()
    for pos in range(1, 6):
        order = sorted(THEORY[pos], key=lambda x: (-scores[(pos, x)], x))
        seeds.update(order[:3])
    ranked = sorted(seeds, key=lambda x: (-sum(scores.get((pos, x), 0.0) for pos in range(1, 6)), x))
    for value in global_rank:
        if len(ranked) >= 20:
            break
        if value not in ranked:
            ranked.append(value)
    return ranked[:20]

def update_position_shadow(dates, draws):
    """Append a pre-target freeze and evaluate only previously frozen forecasts; never reconstruct gaps."""
    path = OUT / "position_mix_shadow.csv"
    fields = ["target_date", "frozen_at", "history_cutoff", "config_id", "model_version",
              "top20", "top10", "top5", "status", "actual_numbers", "hit_numbers",
              "hit_count", "all5_top20", "evaluated_at", "evaluated_at_data_through", "timeliness_note"]
    rows = []
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != fields:
                raise SystemExit("PIPELINE BLOCKED: position_mix_shadow.csv schema mismatch")
            rows = list(reader)
    now = datetime.now(ROME)
    actual_by_date = {d: nums for d, nums in zip(dates, draws)}
    changed = False
    # Outcomes may be attached only to an existing freeze; frozen numbers/cutoff are never changed.
    for row in rows:
        if row["status"] == "FROZEN_PENDING" and row["target_date"] in actual_by_date:
            actual = actual_by_date[row["target_date"]]
            hits = sorted(set(parse(row["top20"])) & set(actual))
            row["status"] = "EVALUATED"
            row["actual_numbers"] = " ".join(map(str, actual))
            row["hit_numbers"] = " ".join(map(str, hits))
            row["hit_count"] = str(len(hits))
            row["all5_top20"] = "1" if len(hits) == 5 else "0"
            row["evaluated_at"] = now.isoformat(timespec="seconds")
            row["evaluated_at_data_through"] = dates[-1]
            changed = True

    latest = date.fromisoformat(dates[-1])
    today = now.date()
    target = None
    if latest == today:
        target = today + timedelta(days=1)
    elif latest == today - timedelta(days=1) and now.time() < DRAW_TIME:
        target = today
    elif latest < today - timedelta(days=1):
        state = "PIPELINE_BLOCKED_STALE_ARCHIVE"
    elif latest == today - timedelta(days=1) and now.time() >= DRAW_TIME:
        state = "WAITING_FOR_TODAY_RESULT_AFTER_DRAW_CUTOFF"
    else:
        state = "NO_SAFE_TARGET_RESOLVED"

    existing_dates = {row["target_date"] for row in rows}
    if target is not None:
        target_s = target.isoformat()
        earlier_pending = [row for row in rows if row["status"] == "FROZEN_PENDING"
                           and row["target_date"] < target_s and row["target_date"] not in actual_by_date]
        if earlier_pending:
            state = "BLOCKED_EARLIER_PENDING_TARGET"
        elif target_s in existing_dates:
            state = "EXISTING_FREEZE_PRESERVED"
        else:
            top20 = position_mix_forecast(draws)
            rows.append({
                "target_date": target_s, "frozen_at": now.isoformat(timespec="seconds"),
                "history_cutoff": dates[-1], "config_id": "position_seed_mix_top20_v1",
                "model_version": "position-seed-mix-v1",
                "top20": " ".join(map(str, top20)), "top10": " ".join(map(str, top20[:10])),
                "top5": " ".join(map(str, top20[:5])), "status": "FROZEN_PENDING",
                "actual_numbers": "", "hit_numbers": "", "hit_count": "", "all5_top20": "",
                "evaluated_at": "", "evaluated_at_data_through": "",
                "timeliness_note": "Append-only freeze created before nominal draw time; cutoff is canonical latest date."
            })
            state = "FROZEN_PENDING_CREATED"
            changed = True
    if changed or not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    pending = sum(row["status"] == "FROZEN_PENDING" for row in rows)
    evaluated = sum(row["status"] == "EVALUATED" for row in rows)
    latest_row = max(rows, key=lambda row: row["target_date"]) if rows else None
    return {
        "status": state, "file": str(path.relative_to(ROOT)), "rows": len(rows),
        "pending": pending, "evaluated": evaluated,
        "latest_freeze": None if latest_row is None else {
            "target_date": latest_row["target_date"], "frozen_at": latest_row["frozen_at"],
            "history_cutoff": latest_row["history_cutoff"], "status": latest_row["status"],
            "top20": latest_row["top20"]
        },
        "policy": "Append-only; never reconstruct a missing freeze; frozen top20/top10/top5 and cutoff are immutable."
    }

def binom_tail_ge(k, n, p):
    # Exact upper binomial tail; used only for small positional top-1 comparisons.
    if k <= 0: return 1.0
    if p <= 0: return 0.0
    if p >= 1: return 1.0
    logs = []
    for j in range(k, n + 1):
        logs.append(math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1)
                    + j * math.log(p) + (n - j) * math.log1p(-p))
    mx = max(logs)
    return min(1.0, math.exp(mx) * sum(math.exp(v - mx) for v in logs))

def main():
    rows = load_data()
    dates = [d for d, _ in rows]
    draws = [nums for _, nums in rows]
    n_draws = len(draws)
    first, last = dates[0], dates[-1]
    if n_draws <= WARMUP:
        raise SystemExit("PIPELINE BLOCKED: archive too short for the predeclared 500-draw warmup")

    # Descriptive position distributions vs the exact combinatorial order-statistic null.
    position_desc, desc_p = {}, []
    for pos in range(1, 6):
        obs = Counter(d[pos - 1] for d in draws)
        gof = grouped_gof(pos, obs)
        mode = min(THEORY[pos], key=lambda x: (-THEORY[pos][x], x))
        position_desc[str(pos)] = {
            "support": [min(THEORY[pos]), max(THEORY[pos])],
            "observed_mode": min(obs, key=lambda x: (-obs[x], x)),
            "observed_mode_count": obs.most_common(1)[0][1],
            "theoretical_mode": mode, "theoretical_mode_probability": THEORY[pos][mode],
            "gof_vs_exact_order_statistic_null": gof,
            "warning": "descriptive full-history test; not a predictive validation"
        }
        desc_p.append((str(pos), gof["p_value"]))
    desc_adj = holm_adjust(desc_p)
    for pos in position_desc:
        position_desc[pos]["gof_holm_p_value"] = desc_adj[pos]

    # Leakage-safe expanding forecasts for exact position value.
    pos_eval = {str(p): {"n": 0, "adaptive_top1": 0, "theory_mode_top1": 0,
                         "adaptive_top3": 0, "expected_adaptive_top1": 0.0,
                         "adaptive_null_variance": 0.0, "adaptive_wins": 0, "adaptive_losses": 0,
                         "per_draw": []} for p in range(1, 6)}
    pos_counts = {p: Counter() for p in range(1, 6)}
    pos_history = []
    global_hits, mix_hits = [], []
    residual_rows = []
    residual_feature_rows = []
    sum_means_history = []
    global_rolling_counts = Counter()
    # Each target is forecast using only prior draws; first 500 are warmup.
    for t, (date, actual) in enumerate(zip(dates, draws)):
        if t >= WARMUP:
            prior = draws[:t]
            train = prior[-100:]  # predeclared trailing window for number-level models
            global_counts = Counter(n for d in train for n in d)
            global_rank = rank_values(global_counts)
            global20 = global_rank[:20]
            # Position-conditioned top-3 candidates per ordered slot, smoothed toward exact theory.
            p_scores = {}
            position_counts = {}
            for pos in range(1, 6):
                cnt = Counter(d[pos - 1] for d in train)
                position_counts[pos] = cnt
                for x in THEORY[pos]:
                    p_scores[(pos, x)] = cnt[x] + PRIOR_STRENGTH * THEORY[pos][x]
            seeds = set()
            for pos in range(1, 6):
                order = sorted(THEORY[pos], key=lambda x: (-p_scores[(pos, x)], x))
                seeds.update(order[:3])
            mix_rank = list(seeds)
            mix_rank.sort(key=lambda x: (-sum(p_scores.get((p, x), 0.0) for p in range(1, 6)), x))
            for x in global_rank:
                if len(mix_rank) >= 20: break
                if x not in mix_rank: mix_rank.append(x)
            mix20 = mix_rank[:20]
            gh = len(set(global20) & set(actual))
            mh = len(set(mix20) & set(actual))
            global_hits.append(gh); mix_hits.append(mh)

            # Regime labels derive only from the prior 20 sums and prior distribution of prior rolling means.
            prior_sums = [sum(d) for d in prior]
            cur_mean = statistics.mean(prior_sums[-20:])
            historical_means = [statistics.mean(prior_sums[max(0, j-19):j+1]) for j in range(19, len(prior))]
            ordered_means = sorted(historical_means)
            q1 = ordered_means[int(0.33 * (len(ordered_means)-1))]
            q2 = ordered_means[int(0.66 * (len(ordered_means)-1))]
            sum_regime = "LOW" if cur_mean <= q1 else ("HIGH" if cur_mean >= q2 else "MID")
            # Pre-target state only: overlap between the two most recent already-known draws.
            overlap = len(set(prior[-1]) & set(prior[-2]))
            overlap_regime = "0" if overlap == 0 else ("1" if overlap == 1 else "2+")
            residual = sorted(set(actual) - set(global20))
            mix_residual = sorted(set(actual) - set(mix20))
            residual_rows.append({
                "target_date": date, "cutoff_date": dates[t-1], "actual_numbers": " ".join(map(str, actual)),
                "global_top20": " ".join(map(str, global20)), "global_hits": gh,
                "global_residual_numbers": " ".join(map(str, residual)), "global_residual_count": len(residual),
                "position_mix_top20": " ".join(map(str, mix20)), "position_mix_hits": mh,
                "position_mix_residual_numbers": " ".join(map(str, mix_residual)),
                "position_seed_union": " ".join(map(str, sorted(seeds))),
                "position_seed_union_size": len(seeds),
                "prior_20_sum_mean": round(cur_mean, 4), "sum_regime": sum_regime,
                "prior_transition_overlap": overlap, "overlap_regime": overlap_regime
            })
            for pos in range(1, 6):
                counts = Counter(d[pos - 1] for d in prior)
                scores = {x: counts[x] + PRIOR_STRENGTH * THEORY[pos][x] for x in THEORY[pos]}
                ranked = sorted(scores, key=lambda x: (-scores[x], x))
                pred, top3 = ranked[0], set(ranked[:3])
                theory_mode = min(THEORY[pos], key=lambda x: (-THEORY[pos][x], x))
                hit = int(actual[pos - 1] == pred)
                base_hit = int(actual[pos - 1] == theory_mode)
                p_null = THEORY[pos][pred]
                rec = pos_eval[str(pos)]
                rec["n"] += 1
                rec["adaptive_top1"] += hit
                rec["theory_mode_top1"] += base_hit
                rec["adaptive_top3"] += int(actual[pos - 1] in top3)
                rec["expected_adaptive_top1"] += p_null
                rec["adaptive_null_variance"] += p_null * (1-p_null)
                if hit and not base_hit: rec["adaptive_wins"] += 1
                if base_hit and not hit: rec["adaptive_losses"] += 1
                rec["per_draw"].append({"date": date, "actual": actual[pos-1], "prediction": pred,
                                        "theory_mode": theory_mode, "hit": hit, "theory_mode_hit": base_hit,
                                        "top3_hit": int(actual[pos-1] in top3), "null_probability": p_null})
        # positional counts kept for auditability; no current target is used until after its forecast.
        for pos in range(1, 6):
            pos_counts[pos][actual[pos - 1]] += 1

    # Chronological 60/20/20 splits over the scored targets; no target is used to create its own forecast.
    eval_n = n_draws - WARMUP
    split_bounds = {"discovery": (0, int(eval_n * 0.60)),
                    "validation": (int(eval_n * 0.60), int(eval_n * 0.80)),
                    "oos": (int(eval_n * 0.80), eval_n)}
    position_split_metrics = {}
    for pos in range(1, 6):
        rows_for_pos = pos_eval[str(pos)]["per_draw"]
        position_split_metrics[str(pos)] = {}
        for split_name, (lo, hi) in split_bounds.items():
            part = rows_for_pos[lo:hi]
            n_part = len(part)
            position_split_metrics[str(pos)][split_name] = {
                "targets": n_part,
                "adaptive_top1_hits": sum(r["hit"] for r in part),
                "adaptive_top1_rate": sum(r["hit"] for r in part) / n_part if n_part else None,
                "theory_mode_top1_hits": sum(r["theory_mode_hit"] for r in part),
                "theory_mode_top1_rate": sum(r["theory_mode_hit"] for r in part) / n_part if n_part else None,
                "adaptive_top3_hits": sum(r["top3_hit"] for r in part),
                "adaptive_top3_rate": sum(r["top3_hit"] for r in part) / n_part if n_part else None
            }

    # Finalize per-position tests and Holm correction for the 5 adaptive top-1 tests.
    pred_p = []
    paired_p = []
    for pos in range(1, 6):
        rec = pos_eval[str(pos)]
        n = rec["n"]
        expected = rec["expected_adaptive_top1"]
        var = rec["adaptive_null_variance"]
        z = (rec["adaptive_top1"] - expected) / math.sqrt(var) if var else 0.0
        # one-sided normal tail
        pval = 0.5 * math.erfc(z / math.sqrt(2))
        rec["adaptive_top1_rate"] = rec["adaptive_top1"] / n
        rec["theory_mode_top1_rate"] = rec["theory_mode_top1"] / n
        rec["adaptive_top3_rate"] = rec["adaptive_top3"] / n
        rec["expected_top1_hits_under_theory"] = expected
        rec["observed_minus_expected"] = rec["adaptive_top1"] - expected
        rec["z_vs_position_specific_theory_null"] = z
        rec["p_one_sided_approx"] = pval
        rec["adaptive_vs_theory_mode_discordant_wins_losses"] = {
            "wins": rec["adaptive_wins"], "losses": rec["adaptive_losses"]
        }
        discordant = rec["adaptive_wins"] + rec["adaptive_losses"]
        paired_pval = min(1.0, 2.0 * binom_tail_ge(max(rec["adaptive_wins"], rec["adaptive_losses"]),
                                                   discordant, 0.5)) if discordant else 1.0
        rec["p_adaptive_vs_theory_mode_exact_mcnemar"] = paired_pval
        paired_p.append((str(pos), paired_pval))
        rec.pop("adaptive_null_variance", None)
        rec.pop("per_draw", None)
        pred_p.append((str(pos), pval))
    pred_adj = holm_adjust(pred_p)
    paired_adj = holm_adjust(paired_p)
    for pos in pos_eval:
        pos_eval[pos]["p_holm_5_positions_vs_theory_null"] = pred_adj[pos]
        pos_eval[pos]["p_holm_5_positions_vs_theory_mode"] = paired_adj[pos]
        pos_eval[pos]["interpretation"] = "exploratory; temporal dependence and adaptive estimation mean these are screening tests, not proof of predictability"

    # Regime summaries for global vs positional mix.
    regimes = {}
    for row in residual_rows:
        for key, val in (("sum_regime", row["sum_regime"]), ("overlap_regime", row["overlap_regime"])):
            slot = regimes.setdefault(key, {})
            cell = slot.setdefault(val, {"n": 0, "global_hits": 0, "mix_hits": 0, "global_5of5": 0, "mix_5of5": 0})
            cell["n"] += 1; cell["global_hits"] += row["global_hits"]; cell["mix_hits"] += row["position_mix_hits"]
            cell["global_5of5"] += int(row["global_hits"] == 5); cell["mix_5of5"] += int(row["position_mix_hits"] == 5)
    for group in regimes.values():
        for cell in group.values():
            cell["global_mean_hits"] = cell["global_hits"] / cell["n"]
            cell["position_mix_mean_hits"] = cell["mix_hits"] / cell["n"]
            cell["warning"] = "descriptive regime slices; not independently selected or prospectively validated"

    # Structural gap hazard, evaluated prequentially on all number-draw opportunities after warmup.
    last_seen = {n: None for n in NUMBERS}
    bucket_total = Counter(); bucket_hits = Counter()
    hazard_brier = hazard_log = base_brier = base_log = 0.0
    hazard_n = 0
    hazard_split = {name: {"targets": hi-lo, "opportunities": 0, "model_brier_sum": 0.0,
                           "baseline_brier_sum": 0.0, "model_log_loss_sum": 0.0,
                           "baseline_log_loss_sum": 0.0}
                    for name, (lo, hi) in split_bounds.items()}
    hazard_bucket_eval = {label: {"n": 0, "hits": 0, "brier_model": 0.0, "brier_base": 0.0} for _, _, label in GAP_BUCKETS}
    for t, actual in enumerate(draws):
        actual_set = set(actual)
        if t >= WARMUP:
            target_brier_model = target_brier_base = target_log_model = target_log_base = 0.0
            for n in NUMBERS:
                age = t if last_seen[n] is None else t - last_seen[n] - 1
                b = gap_bucket(age)
                p = (bucket_hits[b] + PRIOR_STRENGTH * BASE_P) / (bucket_total[b] + PRIOR_STRENGTH)
                y = int(n in actual_set)
                pclip = min(1 - 1e-12, max(1e-12, p))
                brier = (p-y)**2
                brier0 = (BASE_P-y)**2
                log_model = -(y*math.log(pclip)+(1-y)*math.log1p(-pclip))
                log_base = -(y*math.log(BASE_P)+(1-y)*math.log1p(-BASE_P))
                hazard_brier += brier; base_brier += brier0
                hazard_log += log_model; base_log += log_base
                target_brier_model += brier; target_brier_base += brier0
                target_log_model += log_model; target_log_base += log_base
                hazard_n += 1
                cell = hazard_bucket_eval[b]; cell["n"] += 1; cell["hits"] += y
                cell["brier_model"] += brier; cell["brier_base"] += brier0
            eidx = t - WARMUP
            split_name = "discovery" if eidx < split_bounds["discovery"][1] else (
                "validation" if eidx < split_bounds["validation"][1] else "oos")
            hs = hazard_split[split_name]
            hs["opportunities"] += len(NUMBERS)
            hs["model_brier_sum"] += target_brier_model
            hs["baseline_brier_sum"] += target_brier_base
            hs["model_log_loss_sum"] += target_log_model
            hs["baseline_log_loss_sum"] += target_log_base
        # Update hazard training only after scoring this draw.
        for n in NUMBERS:
            age = t if last_seen[n] is None else t - last_seen[n] - 1
            b = gap_bucket(age)
            bucket_total[b] += 1
            if n in actual_set: bucket_hits[b] += 1
        for n in actual_set: last_seen[n] = t
    for cell in hazard_bucket_eval.values():
        cell["hit_rate"] = cell["hits"] / cell["n"] if cell["n"] else None
        cell["mean_brier_model"] = cell["brier_model"] / cell["n"] if cell["n"] else None
        cell["mean_brier_baseline"] = cell["brier_base"] / cell["n"] if cell["n"] else None
    for hs in hazard_split.values():
        m = hs["opportunities"]
        hs["model_brier"] = hs["model_brier_sum"] / m if m else None
        hs["baseline_brier"] = hs["baseline_brier_sum"] / m if m else None
        hs["brier_improvement"] = (hs["baseline_brier_sum"] - hs["model_brier_sum"]) / m if m else None
        hs["model_log_loss"] = hs["model_log_loss_sum"] / m if m else None
        hs["baseline_log_loss"] = hs["baseline_log_loss_sum"] / m if m else None
        hs["log_loss_improvement"] = (hs["baseline_log_loss_sum"] - hs["model_log_loss_sum"]) / m if m else None
        for key in ("model_brier_sum", "baseline_brier_sum", "model_log_loss_sum", "baseline_log_loss_sum"):
            hs.pop(key, None)
    hazard_report = {
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY",
        "source": "data/storico_daily.csv", "first_date": first, "last_date": last,
        "draws": n_draws, "warmup_draws": WARMUP, "evaluated_draws": n_draws-WARMUP,
        "number_draw_opportunities": hazard_n, "baseline_probability": BASE_P,
        "gap_buckets": hazard_bucket_eval,
        "overall": {"model_brier": hazard_brier/hazard_n, "baseline_brier": base_brier/hazard_n,
                    "brier_improvement": (base_brier-hazard_brier)/hazard_n,
                    "model_log_loss": hazard_log/hazard_n, "baseline_log_loss": base_log/hazard_n,
                    "log_loss_improvement": (base_log-hazard_log)/hazard_n},
        "chronological_splits": hazard_split,
        "guardrail": "All gap ages and hazard estimates use prior draws only. Historical score improvement is exploratory; no prospective promotion."
    }
    (OUT / "structural_hazard_oos.json").write_text(json.dumps(hazard_report, indent=2) + "\n", encoding="utf-8")

    # Residual ledger persists every scored target, including missed numbers and exact cutoff.
    with (OUT / "residual_error_ledger.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(residual_rows[0].keys()))
        writer.writeheader(); writer.writerows(residual_rows)

    # Global vs position-mix paired metrics; descriptive regime and overall comparison.
    def summary_hits(vals):
        n = len(vals)
        return {"targets": n, "mean_hits": sum(vals)/n if n else None,
                "hit_distribution": {str(k): sum(v==k for v in vals) for k in range(6)},
                "top20_5of5": sum(v==5 for v in vals),
                "top20_4plus": sum(v>=4 for v in vals)}
    global_summary, mix_summary = summary_hits(global_hits), summary_hits(mix_hits)
    position_report = {
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY",
        "source": "data/storico_daily.csv", "first_date": first, "last_date": last,
        "draws": n_draws, "warmup_draws": WARMUP, "evaluated_targets": n_draws-WARMUP,
        "theoretical_position_distributions": position_desc,
        "prequential_exact_position_prediction": pos_eval,
        "position_prediction_by_chronological_split": position_split_metrics,
        "walkforward_split_bounds": {k: {"start_index_in_scored_targets": lo, "end_index_exclusive": hi,
                                         "targets": hi-lo} for k, (lo, hi) in split_bounds.items()},
        "global_top20_vs_position_seed_mix": {
            "definition": "Global Top20 = frequency ranking on prior 100 draws. Position-seed mix = union of top-3 smoothed values for each ordered position, completed to 20 using the same global frequency ranking.",
            "global_top20": global_summary, "position_seed_mix_top20": mix_summary,
            "random_top20_5of5_baseline_rate": math.comb(20, 5) / math.comb(40, 5),
            "random_top20_5of5_expected_count": len(global_hits) * math.comb(20, 5) / math.comb(40, 5),
            "mean_hit_delta_mix_minus_global": mix_summary["mean_hits"]-global_summary["mean_hits"],
            "chronological_splits": {
                split_name: {
                    "targets": hi-lo,
                    "global_top20": summary_hits(global_hits[lo:hi]),
                    "position_seed_mix_top20": summary_hits(mix_hits[lo:hi]),
                    "random_top20_5of5_expected_count": (hi-lo) * math.comb(20, 5) / math.comb(40, 5)
                } for split_name, (lo, hi) in split_bounds.items()
            },
            "per_target_paired": {"mix_better": sum(m>g for m,g in zip(mix_hits,global_hits)),
                                  "tie": sum(m==g for m,g in zip(mix_hits,global_hits)),
                                  "global_better": sum(g>m for m,g in zip(mix_hits,global_hits))},
            "warning": "retrospective chronological evaluation; no prospective freeze; exploratory only"
        },
        "regime_slices": regimes,
        "guardrail": "All predictions use only data available before target. Full-history position frequency tests are descriptive only. Holm correction is applied across five position tests."
    }
    shadow_status = update_position_shadow(dates, draws)
    position_report["prospective_shadow"] = shadow_status
    (OUT / "position_regime_residual_lab.json").write_text(json.dumps(position_report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "COMPLETE_RETROSPECTIVE_EXPLORATORY", "source": str(DATA.relative_to(ROOT)),
                      "draws": n_draws, "first_date": first, "last_date": last,
                      "evaluated_targets": n_draws-WARMUP,
                      "position_top1_rates": {p: round(v["adaptive_top1_rate"], 5) for p,v in pos_eval.items()},
                      "position_top1_holm_p_vs_theory": {p: round(v["p_holm_5_positions_vs_theory_null"], 5) for p,v in pos_eval.items()},
                      "position_top1_holm_p_vs_mode": {p: round(v["p_holm_5_positions_vs_theory_mode"], 5) for p,v in pos_eval.items()},
                      "global_mean_hits": round(global_summary["mean_hits"], 5),
                      "position_mix_mean_hits": round(mix_summary["mean_hits"], 5),
                      "position_mix_split_5of5": {k: {"global": v["global_top20"]["top20_5of5"],
                                                       "mix": v["position_seed_mix_top20"]["top20_5of5"],
                                                       "targets": v["targets"]}
                                                  for k, v in position_report["global_top20_vs_position_seed_mix"]["chronological_splits"].items()},
                      "hazard_brier_improvement": round(hazard_report["overall"]["brier_improvement"], 7),
                      "hazard_brier_improvement_by_split": {k: round(v["brier_improvement"], 7) for k, v in hazard_split.items()},
                      "position_shadow": shadow_status,
                      "outputs": ["reports/sequence_agent/position_regime_residual_lab.json",
                                  "reports/sequence_agent/residual_error_ledger.csv",
                                  "reports/sequence_agent/structural_hazard_oos.json",
                                  "reports/sequence_agent/position_mix_shadow.csv"],
                      "guardrail": "No auto-promotion; historical OOS is exploratory; prospective shadow required"}, indent=2))

if __name__ == "__main__":
    main()
