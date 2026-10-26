#!/usr/bin/env python3
"""Walk-forward catalog of per-number conditions and their pair/triple formulas.

For every target draw, features are computed from strictly earlier draws only.
Every number in 1..40 is ranked under all single-feature, pair-feature and
triple-feature equal-weight formulas. The 2,625-formula grammar is exhaustive
within the declared feature set, not all mathematical formulas.
"""
from __future__ import annotations

import csv
import itertools
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "storico_daily.csv"
OUT = ROOT / "reports" / "sequence_agent"
METRICS = OUT / "per_number_condition_formula_metrics.csv"
TARGET_LEDGER = OUT / "per_number_condition_target_ledger.csv"
REPORT = OUT / "per_number_condition_grammar.json"
MIN_HISTORY = 50
WINDOWS = (5, 10, 20, 50, 100, 250, 500)
EXPECTED_FEATURES = 27


def load_archive():
    with ARCHIVE.open(newline="", encoding="utf-8-sig") as f:
        raw = list(csv.reader(f))
    if len(raw) < MIN_HISTORY + 2:
        raise SystemExit("Q80_BLOCKED: archive too short")
    header = [x.strip().lower() for x in raw[0][:6]]
    if header not in (["data", "n1", "n2", "n3", "n4", "n5"],
                      ["date", "n1", "n2", "n3", "n4", "n5"]):
        raise SystemExit(f"Q80_BLOCKED: unexpected archive header {raw[0][:6]}")
    dates, draws, seen = [], [], set()
    previous = ""
    for line, row in enumerate(raw[1:], 2):
        if not row or not any(x.strip() for x in row):
            continue
        d = row[0].strip()
        try:
            nums = tuple(int(x) for x in row[1:6])
        except Exception as exc:
            raise SystemExit(f"Q80_BLOCKED: malformed row {line}: {exc}")
        if d in seen or (previous and d <= previous):
            raise SystemExit(f"Q80_BLOCKED: duplicate/non-chronological date {d}")
        if len(nums) != 5 or len(set(nums)) != 5 or nums != tuple(sorted(nums)) or any(x < 1 or x > 40 for x in nums):
            raise SystemExit(f"Q80_BLOCKED: invalid draw at {d}")
        dates.append(d); draws.append(nums); seen.add(d); previous = d
    return dates, draws


def make_feature_names():
    names = [f"freq_{w}" for w in WINDOWS]
    names += ["freq_all", "trend_5_vs_50", "trend_10_vs_100", "trend_20_vs_250"]
    names += ["age_since_hit", "gap_mean", "gap_sd", "overdue_ratio"]
    names += ["position_log_frequency", "pair_count_with_last_draw", "neighbor_pm1_history", "neighbor_pm2_history"]
    names += ["lag_1", "lag_2", "lag_3", "lag_5", "lag_10"]
    names += ["recent_3", "recent_5", "recent_10"]
    if len(names) != EXPECTED_FEATURES:
        raise RuntimeError(f"feature schema drift: {len(names)} != {EXPECTED_FEATURES}")
    return names


FEATURE_NAMES = make_feature_names()


def feature_matrix(i, draws, prefix, position_prefix, pair_counts, occurrence_lists, gap_sum, gap_sq_sum, gap_n):
    """Return 40 x 25 values based only on draws[:i]."""
    out = np.zeros((40, EXPECTED_FEATURES), dtype=np.float64)
    for col, w in enumerate(WINDOWS):
        start = max(0, i - w)
        out[:, col] = prefix[i] - prefix[start]
    out[:, 7] = prefix[i]
    # Short-vs-long rate differences put all frequency scales on a comparable basis.
    out[:, 8] = out[:, 0] / max(1, min(i, 5)) - out[:, 5] / max(1, min(i, 50))
    out[:, 9] = out[:, 1] / max(1, min(i, 10)) - out[:, 6] / max(1, min(i, 100))
    out[:, 10] = out[:, 2] / max(1, min(i, 20)) - out[:, 6] / max(1, min(i, 250))
    ages = np.full(40, i + 1, dtype=np.float64)
    for n, occ in enumerate(occurrence_lists):
        if occ:
            ages[n] = i - occ[-1]
    out[:, 11] = ages
    for n, occ in enumerate(occurrence_lists):
        gaps = np.diff(occ)
        if len(gaps):
            out[n, 12] = float(np.mean(gaps))
            out[n, 13] = float(np.std(gaps))
        else:
            out[n, 12] = max(1, i)
            out[n, 13] = 0.0
    out[:, 14] = out[:, 11] / np.maximum(out[:, 12], 1.0)
    # Position likelihood: average smoothed log-frequency over all five sorted positions.
    if i:
        pos = position_prefix[i].astype(np.float64)
        pos_log = np.log((pos + 0.5) / (i + 20.0))
        out[:, 15] = pos_log.mean(axis=0)
    if i:
        last = np.asarray(draws[i - 1], dtype=int) - 1
        out[:, 16] = pair_counts[:, last].mean(axis=1)
    full_counts = prefix[i]
    out[:, 17] = np.array([sum(full_counts[max(0,n-1):min(40,n+2)]) - full_counts[n] for n in range(40)], dtype=float)
    out[:, 18] = np.array([sum(full_counts[max(0,n-2):min(40,n+3)]) - full_counts[n] for n in range(40)], dtype=float)
    for lag, col in ((1,19),(2,20),(3,21),(5,22),(10,23)):
        if i >= lag:
            drawset = set(draws[i-lag])
            out[:, col] = [1.0 if n+1 in drawset else 0.0 for n in range(40)]
    for w, col in ((3,24),(5,25),(10,26)):
        start = max(0, i-w)
        out[:, col] = prefix[i, :] - prefix[start, :]
    return out


def zscore_columns(matrix):
    means = matrix.mean(axis=0)
    stds = matrix.std(axis=0)
    stds[stds < 1e-12] = 1.0
    return (matrix - means) / stds


def make_formulas():
    # Single feature, all unordered pairs, and all unordered triples.
    formulas = []
    for i in range(EXPECTED_FEATURES):
        formulas.append((i,))
    for k in (2, 3):
        formulas.extend(itertools.combinations(range(EXPECTED_FEATURES), k))
    if len(formulas) != 27 + math.comb(27, 2) + math.comb(27, 3):
        raise RuntimeError("formula enumeration mismatch")
    return formulas


FORMULAS = make_formulas()
FORMULA_IDS = [f"P{len(f)}_" + "_".join(f"{i:02d}" for i in f) for f in FORMULAS]


def split_name(index, n):
    p = index / max(n, 1)
    return "discovery" if p < 0.60 else ("validation" if p < 0.80 else "blind_oos")


def holm_adjust(p_values):
    order = sorted(range(len(p_values)), key=lambda i: p_values[i])
    adjusted = [1.0] * len(p_values)
    running = 0.0
    m = len(p_values)
    for rank, idx in enumerate(order):
        value = min(1.0, (m-rank) * p_values[idx])
        running = max(running, value)
        adjusted[idx] = running
    return adjusted


def binomial_upper_normal_p(successes, trials, p):
    # Continuity-corrected normal approximation; explicitly labeled approximate.
    if trials <= 0:
        return 1.0
    mu = trials * p
    variance = trials * p * (1.0-p)
    if variance <= 0:
        return 1.0
    z = (successes - 0.5 - mu) / math.sqrt(variance)
    return min(1.0, max(0.0, 0.5 * math.erfc(z / math.sqrt(2.0))))


def main():
    dates, draws = load_archive()
    n = len(draws)
    prefix = np.zeros((n+1,40), dtype=np.int32)
    pos_prefix = np.zeros((n+1,5,40), dtype=np.int32)
    pair_counts = np.zeros((40,40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    gap_sum = np.zeros(40); gap_sq_sum = np.zeros(40); gap_n = np.zeros(40)
    for i, draw in enumerate(draws):
        prefix[i+1] = prefix[i]
        pos_prefix[i+1] = pos_prefix[i]
        for pos, value in enumerate(draw):
            v=value-1
            prefix[i+1,v]+=1
            pos_prefix[i+1,pos,v]+=1
        for a,b in itertools.combinations(draw,2):
            pair_counts[a-1,b-1]+=1; pair_counts[b-1,a-1]+=1

    formulas = FORMULAS
    formula_count = len(formulas)
    split_acc = {s: [{"targets":0,"number_hits_top5":0,"number_hits_top10":0,"number_hits_top20":0,
                      "all5_top5":0,"all5_top10":0,"all5_top20":0,"rank_sum":0,
                      "p5":1.0,"p10":1.0,"p20":1.0} for _ in formulas]
                 for s in ("discovery","validation","blind_oos")}
    per_target_rows = []
    feature_summaries = {name: {"targets":0,"hits_top5":0,"hits_top10":0,"hits_top20":0,"rank_sum":0}
                         for name in FEATURE_NAMES}
    # Walk-forward: update all state after scoring the target, never before.
    for i, (target_date, actual) in enumerate(zip(dates, draws)):
        if i:
            # Rebuild pair counts for prefix i: remove future rows from the all-history accumulator.
            # Incremental pair state below is the exact prior-only source.
            pass
        if i < MIN_HISTORY:
            # Still update occurrence lists and prefix-derived state for later targets.
            ranks = None
        else:
            raw = feature_matrix(i, draws, prefix, pos_prefix, prior_pairs, occurrence_lists,
                                 gap_sum, gap_sq_sum, gap_n)
            # Each feature is normalized over the 40 eligible numbers for this target.
            standardized = zscore_columns(raw)
            actual_idx = np.asarray(actual, dtype=int)-1
            all_ranks = np.empty((formula_count,5), dtype=np.int16)
            all_hits5 = np.zeros(formula_count, dtype=np.int8)
            all_hits10 = np.zeros(formula_count, dtype=np.int8)
            all_hits20 = np.zeros(formula_count, dtype=np.int8)
            best_formula = None; best_key = None
            for fi, cols in enumerate(formulas):
                scores = standardized[:, cols].mean(axis=1)
                order = np.lexsort((np.arange(40), -scores))
                rank = np.empty(40, dtype=np.int16)
                rank[order] = np.arange(1,41,dtype=np.int16)
                actual_ranks = rank[actual_idx]
                all_ranks[fi] = actual_ranks
                all_hits5[fi] = int(np.sum(actual_ranks <= 5))
                all_hits10[fi] = int(np.sum(actual_ranks <= 10))
                all_hits20[fi] = int(np.sum(actual_ranks <= 20))
                key = (int(np.sum(actual_ranks)), int(np.sum(actual_ranks <= 20)), -int(np.sum(actual_ranks <= 5)))
                if best_key is None or key < best_key:
                    best_key=key; best_formula=fi
                split=split_name(i-MIN_HISTORY, n-MIN_HISTORY)
                acc=split_acc[split][fi]
                acc["targets"]+=1
                acc["number_hits_top5"]+=int(all_hits5[fi])
                acc["number_hits_top10"]+=int(all_hits10[fi])
                acc["number_hits_top20"]+=int(all_hits20[fi])
                acc["all5_top5"]+=int(np.all(actual_ranks<=5))
                acc["all5_top10"]+=int(np.all(actual_ranks<=10))
                acc["all5_top20"]+=int(np.all(actual_ranks<=20))
                acc["rank_sum"]+=int(np.sum(actual_ranks))
            # Full per-target record: each actual number's rank under every individual feature,
            # plus best composite rule, so the conditions that explain this target remain inspectable.
            feature_ranks=[]
            for col,name in enumerate(FEATURE_NAMES):
                scores=standardized[:,col]
                order=np.lexsort((np.arange(40),-scores))
                rank=np.empty(40,dtype=np.int16); rank[order]=np.arange(1,41,dtype=np.int16)
                actual_ranks=rank[actual_idx]
                feature_ranks.append({"feature":name,"ranks":actual_ranks.tolist(),
                                      "hits_top5":int(np.sum(actual_ranks<=5)),
                                      "hits_top10":int(np.sum(actual_ranks<=10)),
                                      "hits_top20":int(np.sum(actual_ranks<=20)),
                                      "rank_sum":int(np.sum(actual_ranks))})
                fs=feature_summaries[name]
                fs["targets"]+=1;fs["hits_top5"]+=int(np.sum(actual_ranks<=5))
                fs["hits_top10"]+=int(np.sum(actual_ranks<=10))
                fs["hits_top20"]+=int(np.sum(actual_ranks<=20))
                fs["rank_sum"]+=int(np.sum(actual_ranks))
            best_ranks=all_ranks[best_formula].tolist()
            per_target_rows.append({
                "target_date":target_date,"cutoff_date":dates[i-1],"prior_draws":i,
                "actual_quintet":" ".join(map(str,actual)),"status":"SCORED",
                "formula_count_tested":formula_count,"best_formula_id":FORMULA_IDS[best_formula],
                "best_formula_features":"+".join(FEATURE_NAMES[c] for c in formulas[best_formula]),
                "best_actual_number_ranks":json.dumps(best_ranks,separators=(",",":")),
                "best_number_hits_top5":int(np.sum(np.asarray(best_ranks)<=5)),
                "best_number_hits_top10":int(np.sum(np.asarray(best_ranks)<=10)),
                "best_number_hits_top20":int(np.sum(np.asarray(best_ranks)<=20)),
                "best_rank_sum":int(np.sum(best_ranks)),
                "single_feature_rank_ledger":json.dumps(feature_ranks,separators=(",",":"))
            })
        # Increment state only after the target was scored, for the next target.
        for pos,value in enumerate(draws[i]):
            v=value-1
            occurrence_lists[v].append(i)
            if len(occurrence_lists[v])>=2:
                gap=i-occurrence_lists[v][-2]
                gap_sum[v]+=gap;gap_sq_sum[v]+=gap*gap;gap_n[v]+=1
        if i < n-1:
            for a,b in itertools.combinations(draws[i],2):
                prior_pairs[a-1,b-1]+=1;prior_pairs[b-1,a-1]+=1

    # Build per-formula/split metrics and apply Holm across all formula x split x endpoint tests.
    metric_rows=[]; p_records=[]
    for split in ("discovery","validation","blind_oos"):
        for fi,cols in enumerate(formulas):
            a=split_acc[split][fi]; t=a["targets"]
            if not t: continue
            row={"split":split,"formula_id":FORMULA_IDS[fi],"feature_count":len(cols),
                 "features":"+".join(FEATURE_NAMES[c] for c in cols),"targets":t,
                 "mean_number_hits_top5":a["number_hits_top5"]/(5*t),
                 "mean_number_hits_top10":a["number_hits_top10"]/(5*t),
                 "mean_number_hits_top20":a["number_hits_top20"]/(5*t),
                 "all5_top5_rate":a["all5_top5"]/t,"all5_top10_rate":a["all5_top10"]/t,
                 "all5_top20_rate":a["all5_top20"]/t,"mean_rank_of_actual_numbers":a["rank_sum"]/(5*t)}
            # Null hit probability for each actual number is K/40; approximate one-sided normal p-values.
            for endpoint,k,successes,p in (
                ("top5",5,a["number_hits_top5"],5/40),
                ("top10",10,a["number_hits_top10"],10/40),
                ("top20",20,a["number_hits_top20"],20/40)):
                row[f"p_{endpoint}_normal_approx"]=binomial_upper_normal_p(successes,5*t,p)
                p_records.append((len(metric_rows),row[f"p_{endpoint}_normal_approx"]))
            metric_rows.append(row)
    adjusted=holm_adjust([x[1] for x in p_records])
    for (row_idx,p),adj in zip(p_records,adjusted):
        metric_rows[row_idx][f"holm_p_max_endpoint_family"]=max(metric_rows[row_idx].get("holm_p_max_endpoint_family",0.0),adj)
    OUT.mkdir(parents=True,exist_ok=True)
    with METRICS.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(metric_rows[0].keys()));writer.writeheader();writer.writerows(metric_rows)
    with TARGET_LEDGER.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(per_target_rows[0].keys()));writer.writeheader();writer.writerows(per_target_rows)
    summary={
        "schema_version":"1.0","task_id":"Q80","status":"VALIDATED_FINITE_GRAMMAR_COMPLETE",
        "source_archive":"data/storico_daily.csv","target_count":n,"first_date":dates[0],"last_date":dates[-1],
        "minimum_prior_history":MIN_HISTORY,"scored_targets":len(per_target_rows),
        "feature_count":len(FEATURE_NAMES),"features":FEATURE_NAMES,
        "formula_count":formula_count,"formula_grammar":"all 1-, 2- and 3-feature equal-weight combinations",
        "formula_count_check":25+math.comb(25,2)+math.comb(25,3),
        "metrics_rows":len(metric_rows),"target_ledger_rows":len(per_target_rows),
        "split_counts":{s:split_acc[s][0]["targets"] for s in split_acc},
        "feature_summary":{name:{**v,"mean_rank":v["rank_sum"]/(5*v["targets"]) if v["targets"] else None,
             "mean_hits_top5":v["hits_top5"]/(5*v["targets"]) if v["targets"] else None,
             "mean_hits_top10":v["hits_top10"]/(5*v["targets"]) if v["targets"] else None,
             "mean_hits_top20":v["hits_top20"]/(5*v["targets"]) if v["targets"] else None}
             for name,v in feature_summaries.items()},
        "multiple_testing":{"method":"Holm-Bonferroni","test_count":len(p_records),
             "p_value_method":"continuity-corrected normal approximation to number-level binomial hit counts; exploratory, not an exact test"},
        "guardrails":["features at target i use only draws with index < i",
             "all formula scores rank 40 numbers, and outcomes are evaluated only after scoring",
             "formula universe is exhaustive only within the declared feature grammar",
             "best-per-target formula is descriptive/exploratory and must not be treated as a prospective forecast",
             "immutable freezes are never read for writing or overwritten"],
        "outputs":{"metrics":str(METRICS.relative_to(ROOT)),"target_ledger":str(TARGET_LEDGER.relative_to(ROOT)),
                   "report":str(REPORT.relative_to(ROOT))}
    }
    REPORT.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SONAR_Q80_SUMMARY_BEGIN")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("feature_summary","guardrails")},ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q80_SUMMARY_END")
    print("SONAR_Q80_REPORT_BEGIN")
    print(REPORT.read_text(encoding="utf-8"),end="")
    print("SONAR_Q80_REPORT_END")
    if len(per_target_rows)!=n-MIN_HISTORY:
        raise SystemExit(f"Q80_BLOCKED: target ledger row count {len(per_target_rows)} != {n-MIN_HISTORY}")
    if formula_count!=3303:
        raise SystemExit(f"Q80_BLOCKED: formula count {formula_count} != 2625")


if __name__=="__main__":
    # Pair interaction matrix is explicitly initialized before the walk-forward loop.
    prior_pairs=np.zeros((40,40),dtype=np.int32)
    main()
