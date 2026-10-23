#!/usr/bin/env python3
"""Fast, leakage-safe cascade-loss and fixed-rank-fusion audit from SONAR walk-forward ledger."""
import csv, json, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports/sequence_agent/historical_rule_ledger.csv"
OUT = ROOT / "reports/sequence_agent"
BASELINE = math.comb(20, 5) / math.comb(40, 5)

def read_ledger():
    if not LEDGER.is_file():
        raise SystemExit("PIPELINE BLOCKED: historical_rule_ledger.csv missing")
    by_target = defaultdict(dict)
    with LEDGER.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            by_target[r["target_date"]][r["config_id"]] = r
    if not by_target:
        raise SystemExit("PIPELINE BLOCKED: historical ledger empty")
    return sorted(by_target.items())

def parse_nums(s):
    return [int(x) for x in s.split() if x]

def hits(r, field="top20"):
    return len(set(parse_nums(r[field])) & set(parse_nums(r["actual_numbers"])))

def exact_binomial_upper_tail(n, k, p):
    """Exact one-sided binomial tail P[X >= k], evaluated with a stable recurrence."""
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
    """Holm step-down family-wise adjustment, keyed by test ID."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted = {}
    running = 0.0
    m = len(ordered)
    for i, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p_value))
        adjusted[key] = running
    return adjusted

def mix_multiple_testing(mix_results):
    tests = []
    for mix_name, mix in mix_results.items():
        for split_name in ("discovery", "validation", "oos"):
            metrics = mix["splits"][split_name]
            n = int(metrics["targets"])
            k = int(metrics["top20_all5"])
            test_id = f"{mix_name}:{split_name}"
            tests.append({
                "test_id": test_id,
                "mix": mix_name,
                "split": split_name,
                "targets": n,
                "successes": k,
                "raw_p_one_sided": exact_binomial_upper_tail(n, k, BASELINE),
            })
    adjusted = holm_adjust({row["test_id"]: row["raw_p_one_sided"] for row in tests})
    for row in tests:
        row["holm_adjusted_p"] = adjusted[row["test_id"]]
        row["significant_at_0_05_after_holm"] = row["holm_adjusted_p"] < 0.05
    return {
        "method": "Holm-Bonferroni",
        "test": "One-sided exact binomial test of Top20 5/5 count against the fixed random Top20 baseline",
        "null_probability": BASELINE,
        "alpha": 0.05,
        "family_size": len(tests),
        "family_definition": "All fixed mixes across discovery, validation, and OOS splits; 4 mixes × 3 splits.",
        "tests": tests,
        "interpretation_guardrail": "This correction covers only the reported mix-by-split comparisons; it does not erase selection bias from broader exploratory model search. Discovery is exploratory; prioritize validation and blind OOS.",
    }

def main():
    targets = read_ledger()
    n = len(targets)
    cut1, cut2 = int(n*.6), int(n*.8)
    split = {"discovery": set(d for d,_ in targets[:cut1]),
             "validation": set(d for d,_ in targets[cut1:cut2]),
             "oos": set(d for d,_ in targets[cut2:])}
    cfgs = sorted(set(k for _, rows in targets for k in rows))
    stage = {}
    for cfg in cfgs:
        rows = [(d, rr[cfg]) for d,rr in targets if cfg in rr]
        counts = {k:0 for k in range(6)}
        top10 = top5 = 0
        for d,r in rows:
            h20=hits(r,"top20"); h10=hits(r,"top10"); h5=hits(r,"top5")
            counts[h20]+=1; top10 += int(h10==5); top5 += int(h5==5)
        stage[cfg]={"targets":len(rows),"top20_hit_distribution":{str(k):counts[k] for k in range(6)},
                    "top20_all5":counts[5],"top20_rate":counts[5]/len(rows),
                    "top10_all5":top10,"top5_all5":top5,
                    "top10_given_top20_all5":top10/counts[5] if counts[5] else None,
                    "top5_given_top10_all5":top5/top10 if top10 else None,
                    "mean_top20_hits":sum(int(r["hit_count"]) for _,r in rows)/len(rows)}
    # Fixed candidate models chosen before this audit; rank positions come from prior-only forecasts.
    model_sets = {
      "momentum_freq": ["momentum_20_100","freq_20"],
      "momentum_freq_position": ["momentum_20_100","freq_20","PAIR::freq_20>position_global"],
      "momentum_freq_transition": ["momentum_20_100","freq_20","CHAIN::prev_1>transition_position>gap_age"],
      "four_signal": ["momentum_20_100","freq_20","PAIR::freq_20>momentum_10_50","PAIR::freq_20>position_global"],
    }
    mix_results={}
    for mix, models in model_sets.items():
        per_split={}
        allrows=[]
        for splitname, dates in split.items():
            hitdist={str(k):0 for k in range(6)}; all5=0; top10all=0; top5all=0; hit_sum=0; used=0
            for d, rr in targets:
                if d not in dates or any(m not in rr for m in models): continue
                actual=set(parse_nums(next(iter(rr.values()))["actual_numbers"]))
                # Borda rank fusion: selected numbers receive rank points; numbers outside a model Top20 receive 0.
                scores={x:0.0 for x in range(1,41)}
                for model in models:
                    ranked=parse_nums(rr[model]["top20"])
                    for rank,num in enumerate(ranked,1):
                        scores[num] += (21-rank)/20.0
                fused=sorted(range(1,41),key=lambda x:(-scores[x],x))
                h20=len(set(fused[:20])&actual); h10=len(set(fused[:10])&actual); h5=len(set(fused[:5])&actual)
                hitdist[str(h20)]+=1; all5+=int(h20==5); top10all+=int(h10==5); top5all+=int(h5==5); hit_sum+=h20; used+=1
            per_split[splitname]={"targets":used,"top20_hit_distribution":hitdist,"top20_all5":all5,
                 "top20_rate":all5/used if used else None,"mean_top20_hits":hit_sum/used if used else None,
                 "top10_all5":top10all,"top5_all5":top5all,
                 "random_top20_baseline_rate":BASELINE}
        mix_results[mix]={"models":models,"method":"fixed Borda fusion; within each target uses only prior-only rankings",
                         "splits":per_split}
    output={"status":"COMPLETE_RETROSPECTIVE_DIAGNOSTIC","source":"historical_rule_ledger.csv",
            "targets":n,"first_target":targets[0][0],"last_target":targets[-1][0],
            "split_sizes":{k:len(v) for k,v in split.items()},
            "random_top20_5of5_baseline":BASELINE,
            "stage_loss_by_configuration":stage,"fixed_fusion_walkforward":mix_results,
            "guardrail":"Exploratory only. Historical walk-forward predictions are not prospective Shadow; fusion choices must be frozen and independently validated. No model is promoted by this report."}
    (OUT/"stage_loss_analysis.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    mix_report = {
        "status": output["status"], "targets": n, "splits": output["split_sizes"],
        "baseline": BASELINE, "mixes": mix_results, "guardrail": output["guardrail"],
        "multiple_testing_correction": mix_multiple_testing(mix_results),
    }
    (OUT/"top20_mix_walkforward.json").write_text(json.dumps(mix_report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":output["status"],"targets":n,"first":targets[0][0],"last":targets[-1][0],
                      "mixes":list(mix_results),"multiple_testing_family_size":mix_report["multiple_testing_correction"]["family_size"]},ensure_ascii=False))

if __name__=="__main__":
    main()
