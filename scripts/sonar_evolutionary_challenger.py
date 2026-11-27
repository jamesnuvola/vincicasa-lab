#!/usr/bin/env python3
"""SONAR Evolutionary Challenger: prior-only adaptive formula/regime scorer.

This is an experimental challenger, not a promoted predictor. Every target is
scored using strictly earlier draws. Adaptive formula weights are learned only
from already evaluated targets. The canonical Champion is never modified.
"""
from __future__ import annotations
import argparse, csv, json, math, statistics, random
from collections import Counter, deque
from datetime import date, datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
NUMBERS = tuple(range(1, 41))
FEATURES = (
    "freq_5", "freq_20", "freq_100", "freq_500", "freq_all",
    "age_since_hit", "gap_mean", "gap_sd", "overdue_ratio",
    "lag_1", "lag_5", "neighbor_pm1", "neighbor_pm2",
    "pair_with_last", "regime_analog",
    "freq_5_inverse", "freq_20_inverse", "freq_100_inverse", "freq_500_inverse", "freq_all_inverse",
    "age_since_hit_inverse", "gap_mean_inverse", "gap_sd_inverse", "overdue_ratio_inverse",
    "neighbor_pm1_inverse", "neighbor_pm2_inverse", "pair_with_last_inverse", "regime_analog_inverse",
)
WARMUP = 500
LEARNING_WINDOW = 250
EPS = 1e-9

def load_archive():
    if not DATA.exists():
        raise SystemExit("CHALLENGER BLOCKED: canonical archive missing")
    rows = []
    with DATA.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["data", "n1", "n2", "n3", "n4", "n5"]:
            raise SystemExit("CHALLENGER BLOCKED: archive schema mismatch")
        for line, row in enumerate(reader, 2):
            d = date.fromisoformat(row["data"])
            nums = tuple(int(row[f"n{i}"]) for i in range(1, 6))
            if len(set(nums)) != 5 or tuple(sorted(nums)) != nums or any(n not in NUMBERS for n in nums):
                raise SystemExit(f"CHALLENGER BLOCKED: invalid draw at line {line}")
            if rows and d.isoformat() <= rows[-1][0]:
                raise SystemExit(f"CHALLENGER BLOCKED: non-increasing date at line {line}")
            rows.append((d.isoformat(), nums))
    if len(rows) < WARMUP + 100:
        raise SystemExit("CHALLENGER BLOCKED: insufficient history")
    return rows

def zrank(values):
    """Cross-sectional percentile score in [0,1], deterministic ties."""
    ordered = sorted(NUMBERS, key=lambda n: (values[n], n))
    out = {}
    for i, n in enumerate(ordered):
        out[n] = i / 39.0
    return out

def mean_sd(xs):
    if not xs:
        return 0.0, 0.0
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x-m)**2 for x in xs) / len(xs))

def structural_state(history, end=None):
    """Compact state vector from the preceding five draws only."""
    recent = history[-5:] if end is None else history[end-5:end]
    sums = [sum(d) for d in recent]
    spans = [d[-1]-d[0] for d in recent]
    odds = [sum(x % 2 for x in d) for d in recent]
    overlaps = [len(set(recent[i]) & set(recent[i-1])) for i in range(1,len(recent))]
    gaps = [d[i+1]-d[i] for d in recent for i in range(4)]
    sm, ss = mean_sd(sums)
    rm, rs = mean_sd(spans)
    om, os = mean_sd(odds)
    xm, xs = mean_sd(overlaps)
    gm, gs = mean_sd(gaps)
    return (sm, ss, rm, rs, om, os, xm, xs, gm, gs)

def regime_analog_scores(history):
    """Similarity-weighted successor votes from prior contexts; no target leakage."""
    current = structural_state(history)
    # Contexts are only admitted when their successor is already in history.
    candidates = []
    start = max(5, len(history)-700)
    for j in range(start, len(history)):
        prior_state = structural_state(history, j)
        # Robust scale based on the prior context window; floors avoid zero scales.
        scales = (18, 8, 10, 5, 1.5, 1.2, 0.8, 0.8, 1.5, 1.2)
        dist = sum(((a-b)/s)**2 for a,b,s in zip(current, prior_state, scales)) / len(scales)
        candidates.append((dist, history[j]))
    scores = {n: 0.0 for n in NUMBERS}
    if not candidates:
        return scores
    candidates.sort(key=lambda x: x[0])
    nearest = candidates[:min(40, len(candidates))]
    for dist, successor in nearest:
        weight = math.exp(-0.5 * min(dist, 50.0))
        for n in successor:
            scores[n] += weight
    return scores

def raw_features(history):
    draws = history
    last = set(draws[-1])
    counts = {n: [] for n in NUMBERS}
    for i, draw in enumerate(draws):
        for n in draw:
            counts[n].append(i)
    raw = {f: {} for f in FEATURES if not f.endswith("_inverse") and f != "regime_analog"}
    for n in NUMBERS:
        idx = counts[n]
        ages = len(draws)-1-idx[-1] if idx else len(draws)
        intervals = [b-a for a,b in zip(idx,idx[1:])]
        gm, gs = mean_sd(intervals)
        for window, key in ((5,"freq_5"),(20,"freq_20"),(100,"freq_100"),(500,"freq_500")):
            raw[key][n] = sum(n in d for d in draws[-window:]) / min(window,len(draws))
        raw["freq_all"][n] = len(idx)/len(draws)
        raw["age_since_hit"][n] = float(ages)
        raw["gap_mean"][n] = gm if intervals else float(len(draws))
        raw["gap_sd"][n] = gs
        raw["overdue_ratio"][n] = (ages/(gm+EPS)) if intervals else float(ages)
        raw["lag_1"][n] = float(n in draws[-1])
        raw["lag_5"][n] = sum(n in d for d in draws[-5:])
        raw["neighbor_pm1"][n] = sum((n-1 in d or n+1 in d) for d in draws[-100:]) / min(100,len(draws))
        raw["neighbor_pm2"][n] = sum((n-2 in d or n+2 in d) for d in draws[-100:]) / min(100,len(draws))
        raw["pair_with_last"][n] = sum(len(last & set(d)) >= 1 and n in d for d in draws[-500:]) / min(500,len(draws))
    raw["regime_analog"] = regime_analog_scores(draws)
    ranked = {f: zrank(v) for f,v in raw.items()}
    # Explicit opposite-polarity hypotheses let the learner discover whether
    # recency/overdue, short/long gaps, or analog similarity/novelty is active.
    for f in ("freq_5","freq_20","freq_100","freq_500","freq_all",
              "age_since_hit","gap_mean","gap_sd","overdue_ratio",
              "neighbor_pm1","neighbor_pm2","pair_with_last","regime_analog"):
        ranked[f + "_inverse"] = {n: 1.0-ranked[f][n] for n in NUMBERS}
    return ranked

DIRECTION_PAIRS = (
    ("freq_5","freq_5_inverse"), ("freq_20","freq_20_inverse"),
    ("freq_100","freq_100_inverse"), ("freq_500","freq_500_inverse"),
    ("freq_all","freq_all_inverse"), ("age_since_hit","age_since_hit_inverse"),
    ("gap_mean","gap_mean_inverse"), ("gap_sd","gap_sd_inverse"),
    ("overdue_ratio","overdue_ratio_inverse"), ("neighbor_pm1","neighbor_pm1_inverse"),
    ("neighbor_pm2","neighbor_pm2_inverse"), ("pair_with_last","pair_with_last_inverse"),
    ("regime_analog","regime_analog_inverse"),
)
SINGLE_FEATURES = ("lag_1", "lag_5")

def adaptive_weights(performance):
    """Choose one polarity per formula family using prior outcomes only."""
    window = list(performance)[-LEARNING_WINDOW:]
    evidence = {}
    for f in FEATURES:
        if not window:
            evidence[f] = 0.0
            continue
        vals = [row[f] for row in window]
        advantage = 0.5 - sum(vals)/len(vals)
        se = 0.5 / math.sqrt(max(1, len(vals)))
        evidence[f] = min(3.0, max(0.0, (advantage - 0.5*se) / (se + 0.015)))
    selected = {}
    for base, inverse in DIRECTION_PAIRS:
        chosen = inverse if evidence[inverse] > evidence[base] else base
        selected[chosen] = 1.0 + evidence[chosen]
    for f in SINGLE_FEATURES:
        selected[f] = 1.0 + evidence[f]
    total = sum(selected.values())
    return {f: selected.get(f, 0.0)/total for f in FEATURES}

def update_transition(stay, out, previous_draw, next_draw):
    next_set = set(next_draw)
    for n in previous_draw:
        if n in next_set:
            stay[n] += 1
        else:
            out[n] += 1

def champion_rank(history, stay, out):
    """Exact-source SONAR Hybrid Recency Analog ranking, reproduced for paired comparison."""
    current = set(history[-1])
    analog_votes = {n: 0.0 for n in NUMBERS}
    for i in range(len(history)-1):
        overlap = len(current & set(history[i]))
        if overlap >= 3:
            weight = overlap ** 3
            for n in history[i+1]:
                analog_votes[n] += weight
    f20 = Counter(n for d in history[-20:] for n in d)
    f100 = Counter(n for d in history[-100:] for n in d)
    f500 = Counter(n for d in history[-500:] for n in d)
    fall = Counter(n for d in history for n in d)
    recent = Counter(n for d in history[-5:] for n in d)
    raw = []
    for getter in (
        lambda n: f20[n]/min(20,len(history)),
        lambda n: f100[n]/min(100,len(history)),
        lambda n: f500[n]/min(500,len(history)),
        lambda n: fall[n]/len(history),
        lambda n: analog_votes[n],
        lambda n: stay[n]/(stay[n]+out[n]) if stay[n]+out[n] else 0.0,
        lambda n: recent[n]/5.0,
    ):
        values = {n:getter(n) for n in NUMBERS}
        lo, hi = min(values.values()), max(values.values())
        raw.append({n:((values[n]-lo)/(hi-lo) if hi>lo else 0.0) for n in NUMBERS})
    weights = (0.38,0.22,0.14,0.06,0.10,0.06,0.04)
    scores = {n:sum(weights[j]*raw[j][n] for j in range(7)) for n in NUMBERS}
    return sorted(NUMBERS,key=lambda n:(-scores[n],n))

def score_target(history, performance):
    features = raw_features(history)
    weights = adaptive_weights(performance)
    scores = {n: sum(weights[f]*features[f][n] for f in FEATURES) for n in NUMBERS}
    ranked = sorted(NUMBERS, key=lambda n: (-scores[n], n))
    return ranked, scores, weights, features

def evaluate(predictions):
    if not predictions:
        return {"targets": 0}
    hits = [len(set(p["top20"]) & set(p["actual"])) for p in predictions]
    top5 = [len(set(p["top5"]) & set(p["actual"])) for p in predictions]
    return {
        "targets": len(predictions),
        "mean_hits_top5": round(sum(top5)/len(top5), 6),
        "mean_hits_top10": round(sum(len(set(p["top10"]) & set(p["actual"])) for p in predictions)/len(predictions), 6),
        "mean_hits_top20": round(sum(hits)/len(hits), 6),
        "top20_5of5": sum(h == 5 for h in hits),
        "top20_4plus": sum(h >= 4 for h in hits),
        "random_baseline_mean_hits_top5": 0.625,
        "random_baseline_mean_hits_top10": 1.25,
        "random_baseline_mean_hits_top20": 2.5,
    }

def run(rows):
    performance = deque(maxlen=LEARNING_WINDOW)
    ledger = []
    predictions = []
    stay, out = [0]*41, [0]*41
    for j in range(WARMUP-1):
        update_transition(stay,out,rows[j][1],rows[j+1][1])
    for i in range(WARMUP, len(rows)):
        target_date, actual = rows[i]
        history = [d for _,d in rows[:i]]
        ranked, scores, weights, features = score_target(history, performance)
        champion = champion_rank(history,stay,out)
        row = {
            "target_date": target_date, "history_cutoff": rows[i-1][0],
            "history_draws": i, "top20": ranked[:20], "top10": ranked[:10],
            "top5": ranked[:5], "champion_top20": champion[:20],
            "champion_top10": champion[:10], "champion_top5": champion[:5],
            "actual": list(actual), "weights": weights,
            "weight_learned_from_targets": len(performance),
        }
        predictions.append(row)
        performance.append({f:sum(features[f][n] for n in actual)/5.0 for f in FEATURES})
        update_transition(stay,out,history[-1],actual)
        ledger.append(row)
    n = len(predictions)
    d1, d2 = int(n*.60), int(n*.80)
    bounds = {"discovery":(0,d1),"validation":(d1,d2),"oos":(d2,n),"overall":(0,n)}
    splits = {}
    for name,(lo,hi) in bounds.items():
        sample = predictions[lo:hi]
        ch = evaluate([{"top20":p["top20"],"top10":p["top10"],"top5":p["top5"],"actual":p["actual"]} for p in sample])
        cp = evaluate([{"top20":p["champion_top20"],"top10":p["champion_top10"],"top5":p["champion_top5"],"actual":p["actual"]} for p in sample])
        splits[name] = {
            "challenger":ch,"champion":cp,
            "delta_mean_hits_top5":round(ch["mean_hits_top5"]-cp["mean_hits_top5"],6),
            "delta_mean_hits_top10":round(ch["mean_hits_top10"]-cp["mean_hits_top10"],6),
            "delta_mean_hits_top20":round(ch["mean_hits_top20"]-cp["mean_hits_top20"],6),
            "delta_top20_5of5":ch["top20_5of5"]-cp["top20_5of5"],
        }
    current_ranked,current_scores,current_weights,current_features=score_target([d for _,d in rows],performance)
    current_champion=champion_rank([d for _,d in rows],stay,out)
    return {
        "status":"EXPLORATORY_NOT_PROMOTABLE","engine_id":"SONAR::EVOLUTIONARY_FORMULA_REGIME_ADAPTIVE",
        "version":"evolutionary-challenger-v1.1","source":"data/storico_daily.csv",
        "first_date":rows[0][0],"last_date":rows[-1][0],"draws":len(rows),
        "warmup_draws":WARMUP,"evaluated_targets":n,"learning_window_targets":LEARNING_WINDOW,
        "features":list(FEATURES),
        "method":{
            "number_features":"28 prior-only directional hypotheses grouped into 13 paired polarity families plus lag-1/lag-5",
            "regime_feature":"Similarity-weighted successor votes from nearest prior five-draw structural contexts; only observed historical successors are eligible",
            "adaptive_rule":"One direction per family is selected from prior outcomes; inconclusive families retain canonical polarity and unit prior weight",
            "chronology":"At each target, Challenger and Champion forecasts are frozen before the target is revealed; only then are adaptive weights and Champion persistence updated",
            "comparison":"Exact-source Champion scoring is reproduced on identical target dates, cutoffs and warm-up",
            "selection":"Rank all 40 numbers by adaptive weighted formula score; Top5 is the first five ranks",
            "limitations":"Historical walk-forward is exploratory and already inspected; no predictive advantage is claimed; prospective paired evidence is still required"
        },
        "splits":splits,
        "current_forecast":{
            "target_date":"NEXT_DRAW_AFTER_ARCHIVE","history_cutoff":rows[-1][0],
            "top20":current_ranked[:20],"top10":current_ranked[:10],
            "top5_ranked":current_ranked[:5],"ticket_sorted":sorted(current_ranked[:5]),
            "champion_top20":current_champion[:20],"champion_top10":current_champion[:10],
            "champion_top5_ranked":current_champion[:5],"champion_ticket_sorted":sorted(current_champion[:5]),
            "weights":current_weights,
            "score_top20":{str(n):round(current_scores[n],8) for n in current_ranked[:20]},
            "status":"FROZEN_BY_REPORT_GENERATION"
        },
        "ledger":ledger
    }

def persist_shadow(report, rows):
    """Append immutable paired Champion/Challenger freezes; never reconstruct missing targets."""
    path = OUT / "evolutionary_challenger_shadow.csv"
    fields = ["target_date","frozen_at","history_cutoff","model_version",
              "top20","top10","top5","champion_top20","champion_top10","champion_top5",
              "weights_json","status","actual_numbers","hit_numbers","hit_count",
              "champion_hit_numbers","champion_hit_count","evaluated_at"]
    existing = []
    if path.exists():
        with path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != fields:
                raise SystemExit("CHALLENGER BLOCKED: paired shadow ledger schema mismatch")
            existing = list(reader)
    actual_by_date = {d: nums for d, nums in rows}
    now = datetime.now(ZoneInfo("Europe/Rome"))
    changed = False
    for row in existing:
        if row["status"] == "FROZEN_PENDING" and row["target_date"] in actual_by_date:
            actual = actual_by_date[row["target_date"]]
            ch = sorted(set(map(int,row["top20"].split())) & set(actual))
            cp = sorted(set(map(int,row["champion_top20"].split())) & set(actual))
            row["status"] = "EVALUATED"
            row["actual_numbers"] = " ".join(map(str,actual))
            row["hit_numbers"] = " ".join(map(str,ch))
            row["hit_count"] = str(len(ch))
            row["champion_hit_numbers"] = " ".join(map(str,cp))
            row["champion_hit_count"] = str(len(cp))
            row["evaluated_at"] = now.isoformat(timespec="seconds")
            changed = True
    latest = date.fromisoformat(rows[-1][0])
    today = now.date()
    if latest == today:
        target = today + timedelta(days=1)
    elif latest == today - timedelta(days=1):
        target = today if now.time() < time(20,0) else today + timedelta(days=1)
    elif latest < today - timedelta(days=1):
        raise SystemExit("CHALLENGER BLOCKED: archive is stale; no prospective freeze created")
    else:
        target = latest + timedelta(days=1)
    target_text = target.isoformat()
    current = report["current_forecast"]
    prior = next((r for r in existing if r["target_date"] == target_text), None)
    expected = (
        current["history_cutoff"], " ".join(map(str,current["top20"])),
        " ".join(map(str,current["top10"])), " ".join(map(str,current["ticket_sorted"])),
        " ".join(map(str,current["champion_top20"])),
        " ".join(map(str,current["champion_top10"])),
        " ".join(map(str,current["champion_ticket_sorted"]))
    )
    if prior:
        observed = (
            prior["history_cutoff"],prior["top20"],prior["top10"],prior["top5"],
            prior["champion_top20"],prior["champion_top10"],prior["champion_top5"]
        )
        if expected != observed:
            raise SystemExit("CHALLENGER BLOCKED: existing paired freeze conflicts; immutable forecast preserved")
    else:
        existing.append({
            "target_date":target_text,"frozen_at":now.isoformat(timespec="seconds"),
            "history_cutoff":current["history_cutoff"],"model_version":report["version"],
            "top20":" ".join(map(str,current["top20"])),"top10":" ".join(map(str,current["top10"])),
            "top5":" ".join(map(str,current["ticket_sorted"])),
            "champion_top20":" ".join(map(str,current["champion_top20"])),
            "champion_top10":" ".join(map(str,current["champion_top10"])),
            "champion_top5":" ".join(map(str,current["champion_ticket_sorted"])),
            "weights_json":json.dumps(current["weights"],sort_keys=True),
            "status":"FROZEN_PENDING","actual_numbers":"","hit_numbers":"","hit_count":"",
            "champion_hit_numbers":"","champion_hit_count":"","evaluated_at":""
        })
        changed = True
    if changed or not path.exists():
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(existing)
    current["target_date"] = target_text
    current["status"] = "FROZEN_PENDING" if not prior else prior["status"]
    current["frozen_at"] = prior["frozen_at"] if prior else now.isoformat(timespec="seconds")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    rows = load_archive()
    if args.self_test:
        a = raw_features([d for _,d in rows[:WARMUP]])
        b = raw_features([d for _,d in rows[:WARMUP]])
        assert a == b and set(a) == set(FEATURES)
        assert all(abs(sum(adaptive_weights(deque()) .values())-1.0) < 1e-9 for _ in range(1))
        print(json.dumps({"self_test":"PASS","archive_draws":len(rows),"feature_count":len(FEATURES)}))
        return
    report = run(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    persist_shadow(report, rows)
    json_path = OUT / "evolutionary_challenger_walkforward.json"
    csv_path = OUT / "evolutionary_challenger_ledger.csv"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    fields = ["target_date","history_cutoff","history_draws","top20","top10","top5","champion_top20","champion_top10","champion_top5","actual","weight_learned_from_targets"]
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in report["ledger"]:
            w.writerow({k: (" ".join(map(str,r[k])) if isinstance(r[k],list) else r[k]) for k in fields})
    print(json.dumps({
        "status":report["status"],"draws":report["draws"],"targets":report["evaluated_targets"],
        "current_cutoff":report["current_forecast"]["history_cutoff"],
        "top5":report["current_forecast"]["ticket_sorted"],
        "weights":report["current_forecast"]["weights"],"splits":report["splits"]
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
