#!/usr/bin/env python3
"""SONAR evolutionary strategy lab: systematic pair search, split-safe screening, and audit trail."""
from __future__ import annotations
import csv, json, math
from collections import defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports/sequence_agent/historical_rule_ledger.csv"
OUT = ROOT / "reports/sequence_agent"
NUMBERS = tuple(range(1, 41))
BASELINE = math.comb(20, 5) / math.comb(40, 5)

def parse(s):
    return [int(x) for x in s.split() if x]

def read():
    if not LEDGER.is_file():
        raise SystemExit("PIPELINE BLOCKED: historical_rule_ledger.csv missing")
    by_date = defaultdict(dict)
    with LEDGER.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            by_date[row["target_date"]][row["config_id"]] = row
    targets = sorted(by_date.items())
    if len(targets) < 500:
        raise SystemExit(f"PIPELINE BLOCKED: insufficient target rows ({len(targets)})")
    return targets

def score_row(row):
    ranks = {n: 41 for n in NUMBERS}
    for i, n in enumerate(parse(row["top20"]), 1):
        ranks[n] = i
    borda = {n: ((21-ranks[n])/20 if ranks[n] <= 20 else 0.0) for n in NUMBERS}
    rrf = {n: (1.0/(60+ranks[n]) if ranks[n] <= 20 else 0.0) for n in NUMBERS}
    return ranks, borda, rrf, set(parse(row["actual_numbers"]))

def binomial_upper_tail(k, n, p):
    """Exact upper-tail binomial probability, evaluated in log space."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    terms = [math.lgamma(n + 1) - math.lgamma(j + 1) - math.lgamma(n - j + 1)
             + j * math.log(p) + (n - j) * math.log1p(-p) for j in range(k, n + 1)]
    peak = max(terms)
    return min(1.0, math.exp(peak) * sum(math.exp(v - peak) for v in terms))

def holm_adjust(items):
    """Holm step-down adjusted p-values for a list of (key, p) pairs."""
    ordered = sorted(items, key=lambda item: item[1])
    adjusted, running, total = {}, 0.0, len(ordered)
    for i, (key, p) in enumerate(ordered):
        running = max(running, min(1.0, (total - i) * p))
        adjusted[key] = running
    return adjusted

def metrics(predictions):
    n = len(predictions)
    dist = {str(k): 0 for k in range(6)}
    top10 = top5 = ge4 = hit_sum = 0
    for top20, actual in predictions:
        h20 = len(set(top20[:20]) & actual)
        h10 = len(set(top20[:10]) & actual)
        h5 = len(set(top20[:5]) & actual)
        dist[str(h20)] += 1
        top10 += int(h10 == 5)
        top5 += int(h5 == 5)
        ge4 += int(h20 >= 4)
        hit_sum += h20
    return {"targets": n, "top20_hit_distribution": dist, "top20_5of5": dist["5"],
            "top20_4plus": ge4, "top20_rate_5of5": dist["5"]/n if n else None,
            "mean_top20_hits": hit_sum/n if n else None,
            "top10_5of5": top10, "top5_5of5": top5,
            "random_top20_5of5_rate": BASELINE}

def main():
    targets = read()
    n = len(targets)
    d1, d2 = int(n*0.60), int(n*0.80)
    splits = {"discovery": targets[:d1], "validation": targets[d1:d2], "oos": targets[d2:]}
    configs = sorted(set(k for _, rr in targets for k in rr))
    # Precompute prior-only ranks, Borda/RRF scores, actuals and a consensus tie-break for each target.
    prepared = []
    for dt, rr in targets:
        available = {k: score_row(rr[k]) for k in configs if k in rr}
        global_score = {x: sum(v[1][x] for v in available.values()) for x in NUMBERS}
        prepared.append((dt, available, global_score, next(iter(available.values()))[3]))
    # Candidate-pool screening is performed on discovery only. Validation selects
    # among these pairs; OOS is never used for either screening or ranking.
    discovery_rows = splits["discovery"]
    discovery_scores = []
    for cfg in configs:
        vals = [(parse(rr[cfg]["top20"]), set(parse(rr[cfg]["actual_numbers"])))
                for _, rr in discovery_rows if cfg in rr]
        m = metrics(vals)
        discovery_scores.append((cfg, m["top20_5of5"], m["top20_4plus"], m["mean_top20_hits"] or 0.0))
    search_configs = [r[0] for r in sorted(discovery_scores, key=lambda r: (-r[1], -r[2], -r[3], r[0]))[:24]]
    candidates = []
    methods = ("borda", "rrf", "agreement_bonus")
    pairs = [(a,b) for a,b in combinations(search_configs,2)]
    for a,b in pairs:
        for method in methods:
            per_split = {}
            for split_name, split_targets in splits.items():
                start, end = (0, d1) if split_name == "discovery" else ((d1,d2) if split_name == "validation" else (d2,n))
                preds = []
                for _, available, global_score, actual in prepared[start:end]:
                    if a not in available or b not in available:
                        continue
                    ra, ba, rra, _ = available[a]
                    rb, bb, rrb, _ = available[b]
                    if method == "rrf":
                        scores = {x: rra[x] + rrb[x] for x in NUMBERS}
                    else:
                        scores = {x: ba[x] + bb[x] for x in NUMBERS}
                        if method == "agreement_bonus":
                            scores = {x: scores[x] + (0.20 if ra[x] <= 20 and rb[x] <= 20 else 0.0) for x in NUMBERS}
                    ranked = sorted(NUMBERS, key=lambda x: (-scores[x], -global_score[x], x))
                    preds.append((ranked, actual))
                per_split[split_name] = metrics(preds)
            candidates.append({"id": f"{method}::{a} + {b}", "method": method,
                              "models": [a,b], "splits": per_split})
    # Selection uses validation only; OOS is reported for the predeclared validation shortlist.
    ranked = sorted(candidates, key=lambda c: (
        -c["splits"]["validation"]["top20_5of5"],
        -c["splits"]["validation"]["top20_4plus"],
        -(c["splits"]["validation"]["mean_top20_hits"] or 0),
        c["id"]))
    shortlist = ranked[:30]
    # Correct the OOS-vs-random screens across the entire validation-selected shortlist.
    # This remains exploratory because historical OOS has already been inspected in project work.
    oos_p_values = []
    for candidate in shortlist:
        oos = candidate["splits"]["oos"]
        p_value = binomial_upper_tail(oos["top20_5of5"], oos["targets"], BASELINE)
        candidate["oos_top20_5of5_p_value_vs_random"] = p_value
        oos_p_values.append((candidate["id"], p_value))
    oos_p_holm = holm_adjust(oos_p_values)
    for candidate in shortlist:
        candidate["oos_top20_5of5_p_holm_30"] = oos_p_holm[candidate["id"]]
    base_rows = {}
    for cfg in configs:
        vals = {}
        for split_name, split_targets in splits.items():
            selected = []
            for _, rr in split_targets:
                if cfg in rr:
                    r = rr[cfg]
                    selected.append((parse(r["top20"]), set(parse(r["actual_numbers"]))))
            vals[split_name] = metrics(selected)
        base_rows[cfg] = vals
    base_oos_p = []
    for cfg, vals in base_rows.items():
        oos = vals["oos"]
        p_value = binomial_upper_tail(oos["top20_5of5"], oos["targets"], BASELINE)
        oos["top20_5of5_p_value_vs_random"] = p_value
        base_oos_p.append((cfg, p_value))
    base_oos_holm = holm_adjust(base_oos_p)
    for cfg, vals in base_rows.items():
        vals["oos"]["top20_5of5_p_holm_42"] = base_oos_holm[cfg]
    report = {
        "status": "COMPLETE_RETROSPECTIVE_EXPLORATORY_SEARCH",
        "source": "historical_rule_ledger.csv",
        "targets": n, "first_target": targets[0][0], "last_target": targets[-1][0],
        "split_sizes": {k: len(v) for k,v in splits.items()},
        "configurations": len(configs), "discovery_screened_pair_pool_size": len(search_configs),
        "discovery_screened_pair_pool": search_configs, "pairs_tested": len(pairs),
        "fusion_candidates_tested": len(candidates), "methods": list(methods),
        "candidate_pool_rule": "Top 24 individual configurations ranked on discovery only by 5/5, then 4+, then mean hits; pairs are evaluated on validation and OOS, with OOS excluded from selection.",
        "random_top20_5of5_baseline": BASELINE,
        "selection_rule": "Validation shortlist ordered by Top20 5/5 count, then Top20 4+ count, then mean hits; OOS is not used for ranking.",
        "individual_baselines": base_rows,
        "validation_shortlist_with_oos": shortlist,
        "overall_best_validation": shortlist[0] if shortlist else None,
        "guardrails": [
            "All model rankings are prior-only forecasts recorded in the ledger.",
            "The historical OOS has been inspected in prior project analyses; treat this as exploratory, not a pristine holdout.",
            "No strategy is promoted automatically. Freeze candidates in prospective Shadow and compare on at least 100 complete future cases, preferably 200+.",
            "Results describe historical lottery draws and do not imply a guaranteed predictive advantage."
        ]
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "evolutionary_strategy_lab.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    compact = {"status": report["status"], "targets": n, "configurations": len(configs),
               "discovery_screened_pair_pool_size": len(search_configs),
               "pairs_tested": len(pairs), "fusion_candidates_tested": len(candidates),
               "validation_shortlist": [{"id": c["id"], "models": c["models"],
                   "validation": c["splits"]["validation"], "oos": c["splits"]["oos"],
                   "oos_top20_5of5_p_value_vs_random": c["oos_top20_5of5_p_value_vs_random"],
                   "oos_top20_5of5_p_holm_30": c["oos_top20_5of5_p_holm_30"]} for c in shortlist],
               "guardrails": report["guardrails"]}
    (OUT / "evolutionary_strategy_shortlist.json").write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "targets": n, "discovery_pool": len(search_configs),
                      "pairs": len(pairs), "candidates": len(candidates), "shortlist": len(shortlist)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
