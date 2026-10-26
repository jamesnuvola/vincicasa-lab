#!/usr/bin/env python3
"""Fast, leakage-safe cascade-loss and fixed-rank-fusion audit from SONAR walk-forward ledger."""
import csv, json, math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "reports/sequence_agent/historical_rule_ledger.csv"
OUT = ROOT / "reports/sequence_agent"
BASELINE = math.comb(20, 5) / math.comb(40, 5)
BASELINE_TOP10 = math.comb(10, 5) / math.comb(40, 5)
BASELINE_TOP5 = math.comb(5, 5) / math.comb(40, 5)
CASCADE_LEDGER = OUT / "cascade_target_hit_ledger.csv"

def read_ledger():
    if not LEDGER.is_file():
        raise SystemExit("PIPELINE BLOCKED: historical_rule_ledger.csv missing")
    by_target = defaultdict(dict)
    with LEDGER.open(newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            target_date = r["target_date"]
            config_id = r["config_id"]
            if not r.get("history_cutoff") or r["history_cutoff"] >= target_date:
                raise SystemExit("PIPELINE BLOCKED: non-prior history cutoff for " + target_date + " / " + config_id)
            if config_id in by_target[target_date]:
                raise SystemExit("PIPELINE BLOCKED: duplicate target/config row " + target_date + " / " + config_id)
            by_target[target_date][config_id] = r
    if not by_target:
        raise SystemExit("PIPELINE BLOCKED: historical ledger empty")
    return sorted(by_target.items())

def parse_nums(s):
    return [int(x) for x in s.split() if x]

def hits(r, field="top20"):
    return len(set(parse_nums(r[field])) & set(parse_nums(r["actual_numbers"])))

def binomial_tail(n, p, k):
    """Exact upper tail for Binomial(n,p), evaluated by stable recurrence."""
    if k <= 0:
        return 1.0
    term = (1.0 - p) ** n
    tail = 0.0
    for i in range(n + 1):
        if i >= k:
            tail += term
        if i < n:
            term *= ((n - i) / (i + 1)) * (p / (1.0 - p))
    return min(1.0, max(0.0, tail))


def holm_adjust(items):
    """Holm step-down adjusted p-values. items is a list of (key, p)."""
    ordered = sorted(items, key=lambda item: item[1])
    adjusted, running = {}, 0.0
    m = len(ordered)
    for i, (key, p_value) in enumerate(ordered):
        running = max(running, min(1.0, (m - i) * p_value))
        adjusted[key] = running
    return adjusted


def summarize_stage_rows(rows):
    n = len(rows)
    if not n:
        raise SystemExit("PIPELINE BLOCKED: empty cascade split")
    d20, d10, d5 = ({k: 0 for k in range(6)} for _ in range(3))
    sum20 = sum10 = sum5 = 0
    for _, r in rows:
        h20 = int(r["hit_count"])
        h10 = int(r["top10_hit_count"])
        h5 = int(r["top5_hit_count"])
        if any(h < 0 or h > 5 for h in (h20, h10, h5)):
            raise SystemExit("PIPELINE BLOCKED: invalid Top20/Top10/Top5 hit count")
        if h10 > h20 or h5 > h10:
            raise SystemExit("PIPELINE BLOCKED: cascade subset invariant violated")
        d20[h20] += 1
        d10[h10] += 1
        d5[h5] += 1
        sum20 += h20
        sum10 += h10
        sum5 += h5
    c20, c10, c5 = d20[5], d10[5], d5[5]
    return {
        "targets": n,
        "top20_hit_distribution": {str(k): d20[k] for k in range(6)},
        "top10_hit_distribution": {str(k): d10[k] for k in range(6)},
        "top5_hit_distribution": {str(k): d5[k] for k in range(6)},
        "top20_all5": c20,
        "top20_rate": c20 / n,
        "top10_all5": c10,
        "top5_all5": c5,
        "top10_given_top20_all5": c10 / c20 if c20 else None,
        "top5_given_top10_all5": c5 / c10 if c10 else None,
        "top20_4plus": sum(v for h, v in d20.items() if h >= 4),
        "mean_top20_hits": sum20 / n,
        "mean_top10_hits": sum10 / n,
        "mean_top5_hits": sum5 / n,
        "random_top20_5of5_expected_count": n * BASELINE,
        "random_top10_5of5_expected_count": n * BASELINE_TOP10,
        "random_top5_5of5_expected_count": n * BASELINE_TOP5
    }


def add_top20_test(summary, family_size):
    p_value = binomial_tail(summary["targets"], BASELINE, summary["top20_all5"])
    summary["top20_5of5_p_unadjusted_one_sided"] = p_value
    summary["top20_5of5_p_bonferroni_family_42"] = min(1.0, p_value * family_size)
    return summary


def main():
    targets = read_ledger()
    n = len(targets)
    cut1, cut2 = int(n*.6), int(n*.8)
    split = {"discovery": set(d for d,_ in targets[:cut1]),
             "validation": set(d for d,_ in targets[cut1:cut2]),
             "oos": set(d for d,_ in targets[cut2:])}
    cfgs = sorted(set(k for _, rows in targets for k in rows))
    stage = {}
    cascade_rows = []
    for target_index, (d, rr) in enumerate(targets):
        expected_cutoff = targets[target_index - 1][0] if target_index else None
        for cfg, r in sorted(rr.items()):
            cutoff = r["history_cutoff"]
            if cutoff >= d or (expected_cutoff and cutoff != expected_cutoff):
                raise SystemExit("PIPELINE BLOCKED: cutoff/target mismatch at " + d + " / " + cfg)
            h20 = int(r["hit_count"])
            h10 = int(r["top10_hit_count"])
            h5 = int(r["top5_hit_count"])
            cascade_rows.append({
                "target_date": d,
                "history_cutoff": cutoff,
                "config_id": cfg,
                "actual_numbers": r["actual_numbers"],
                "top20_hits": h20,
                "top10_hits": h10,
                "top5_hits": h5,
                "top20_5of5": int(h20 == 5),
                "top10_5of5": int(h10 == 5),
                "top5_5of5": int(h5 == 5),
                "evaluation_mode": r.get("evaluation_mode", "")
            })
    with CASCADE_LEDGER.open("w", newline="", encoding="utf-8") as f:
        fields = ["target_date", "history_cutoff", "config_id", "actual_numbers",
                  "top20_hits", "top10_hits", "top5_hits", "top20_5of5",
                  "top10_5of5", "top5_5of5", "evaluation_mode"]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(cascade_rows)

    stage = {}
    for cfg in cfgs:
        rows = [(d, rr[cfg]) for d, rr in targets if cfg in rr]
        if len(rows) != n:
            raise SystemExit("PIPELINE BLOCKED: incomplete target coverage for " + cfg)
        stage[cfg] = add_top20_test(summarize_stage_rows(rows), len(cfgs))
        stage[cfg]["chronological_splits"] = {}
        for splitname, dates in split.items():
            split_rows = [(d, r) for d, r in rows if d in dates]
            stage[cfg]["chronological_splits"][splitname] = add_top20_test(
                summarize_stage_rows(split_rows), len(cfgs)
            )

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
    # Correct the fixed-fusion family separately in every chronological split.
    # Also report a broader 42 individual rules + 4 fixed mixes Bonferroni screen.
    fixed_family_size = len(model_sets)
    broad_family_size = len(cfgs) + fixed_family_size
    for splitname in split:
        raw_p_values = []
        for mix, result in mix_results.items():
            stats = result["splits"][splitname]
            stats["random_top20_5of5_expected_count"] = stats["targets"] * BASELINE
            p_value = binomial_tail(stats["targets"], BASELINE, stats["top20_all5"])
            raw_p_values.append((mix, p_value))
        holm_values = holm_adjust(raw_p_values)
        raw_by_mix = dict(raw_p_values)
        for mix, result in mix_results.items():
            stats = result["splits"][splitname]
            p_value = raw_by_mix[mix]
            stats["top20_5of5_p_unadjusted_one_sided"] = p_value
            stats["top20_5of5_p_holm_within_4_fixed_mixes"] = holm_values[mix]
            stats["top20_5of5_p_bonferroni_family_46"] = min(1.0, p_value * broad_family_size)

    multiple_testing = {
        "fixed_fusion_family_size": fixed_family_size,
        "within_family_adjustment": "Holm step-down separately within discovery, validation and OOS",
        "broader_family_size": broad_family_size,
        "broader_adjustment": "Bonferroni across the 42 individual configurations and 4 fixed fusion candidates",
        "interpretation": "Fixed-mix OOS results are exploratory. A within-four Holm result does not remove prior strategy-selection bias; the broader family correction is the conservative cross-candidate screen."
    }
    # Fixed mixes constrained to the exact legacy Top20 candidate set.
    # The anchor Top20 set is unchanged; only the within-20 order for Top10/Top5 changes.
    anchor = "momentum_20_100"
    constrained_results = {}
    for mix, models in model_sets.items():
        per_split = {}
        for splitname, dates in split.items():
            d20 = {str(k): 0 for k in range(6)}
            d10 = {str(k): 0 for k in range(6)}
            d5 = {str(k): 0 for k in range(6)}
            all20 = all10 = all5 = 0
            sum20 = sum10 = sum5 = 0
            paired = {
                "top10": {"mix_better": 0, "tie": 0, "anchor_better": 0, "hit_delta_sum": 0},
                "top5": {"mix_better": 0, "tie": 0, "anchor_better": 0, "hit_delta_sum": 0}
            }
            used = 0
            for d, rr in targets:
                if d not in dates or anchor not in rr or any(m not in rr for m in models):
                    continue
                anchor_ranked = parse_nums(rr[anchor]["top20"])
                anchor_set = set(anchor_ranked)
                if len(anchor_set) != 20:
                    raise SystemExit("PIPELINE BLOCKED: legacy anchor Top20 is not 20 distinct numbers")
                scores = {x: 0.0 for x in anchor_set}
                for model in models:
                    ranked = parse_nums(rr[model]["top20"])
                    for rank, num in enumerate(ranked, 1):
                        if num in scores:
                            scores[num] += (21 - rank) / 20.0
                fused = sorted(anchor_set, key=lambda x: (-scores[x], x))
                if set(fused) != anchor_set or len(fused) != 20:
                    raise SystemExit("PIPELINE BLOCKED: constrained mix changed the legacy Top20 set")
                actual = set(parse_nums(rr[anchor]["actual_numbers"]))
                h20 = len(set(fused) & actual)
                h10 = len(set(fused[:10]) & actual)
                h5 = len(set(fused[:5]) & actual)
                anchor_h10 = len(set(anchor_ranked[:10]) & actual)
                anchor_h5 = len(set(anchor_ranked[:5]) & actual)
                d20[str(h20)] += 1
                d10[str(h10)] += 1
                d5[str(h5)] += 1
                all20 += int(h20 == 5)
                all10 += int(h10 == 5)
                all5 += int(h5 == 5)
                sum20 += h20
                sum10 += h10
                sum5 += h5
                for endpoint, mixed_hits, anchor_hits in (
                    ("top10", h10, anchor_h10), ("top5", h5, anchor_h5)
                ):
                    item = paired[endpoint]
                    if mixed_hits > anchor_hits:
                        item["mix_better"] += 1
                    elif mixed_hits < anchor_hits:
                        item["anchor_better"] += 1
                    else:
                        item["tie"] += 1
                    item["hit_delta_sum"] += mixed_hits - anchor_hits
                used += 1
            if used == 0:
                raise SystemExit("PIPELINE BLOCKED: no targets for constrained mix " + mix + " / " + splitname)
            for endpoint in paired:
                paired[endpoint]["mean_hit_delta_mix_minus_anchor"] = paired[endpoint]["hit_delta_sum"] / used
                del paired[endpoint]["hit_delta_sum"]
            per_split[splitname] = {
                "targets": used,
                "anchor_top20": anchor,
                "candidate_set_invariant": True,
                "top20_set_preserved_targets": used,
                "top20_hit_distribution": d20,
                "top10_hit_distribution": d10,
                "top5_hit_distribution": d5,
                "top20_all5": all20,
                "top10_all5": all10,
                "top5_all5": all5,
                "top10_given_top20_all5": all10 / all20 if all20 else None,
                "top5_given_top10_all5": all5 / all10 if all10 else None,
                "mean_top20_hits": sum20 / used,
                "mean_top10_hits": sum10 / used,
                "mean_top5_hits": sum5 / used,
                "random_top20_5of5_baseline_rate": BASELINE,
                "random_top10_5of5_baseline_rate": BASELINE_TOP10,
                "random_top5_5of5_baseline_rate": BASELINE_TOP5,
                "random_top20_5of5_expected_count": used * BASELINE,
                "random_top10_5of5_expected_count": used * BASELINE_TOP10,
                "random_top5_5of5_expected_count": used * BASELINE_TOP5,
                "paired_vs_anchor": paired
            }
        constrained_results[mix] = {
            "anchor_top20": anchor,
            "models": models,
            "method": "fixed Borda rank fusion restricted to the same legacy momentum_20_100 Top20; all constituent rankings are prior-only; no per-target model selection",
            "candidate_set_invariant": True,
            "splits": per_split
        }

    constrained_family_size = len(constrained_results) * 2
    constrained_broad_family_size = len(cfgs) + len(model_sets) + constrained_family_size
    for splitname in split:
        raw_tests = []
        for mix, result in constrained_results.items():
            stats = result["splits"][splitname]
            raw_tests.append((mix + ":top10", binomial_tail(stats["targets"], BASELINE_TOP10, stats["top10_all5"])))
            raw_tests.append((mix + ":top5", binomial_tail(stats["targets"], BASELINE_TOP5, stats["top5_all5"])))
        holm_values = holm_adjust(raw_tests)
        raw_by_key = dict(raw_tests)
        for mix, result in constrained_results.items():
            stats = result["splits"][splitname]
            p10 = raw_by_key[mix + ":top10"]
            p5 = raw_by_key[mix + ":top5"]
            stats["top10_5of5_p_unadjusted_one_sided"] = p10
            stats["top10_5of5_p_holm_within_8_constrained_tests"] = holm_values[mix + ":top10"]
            stats["top10_5of5_p_bonferroni_family_54"] = min(1.0, p10 * constrained_broad_family_size)
            stats["top5_5of5_p_unadjusted_one_sided"] = p5
            stats["top5_5of5_p_holm_within_8_constrained_tests"] = holm_values[mix + ":top5"]
            stats["top5_5of5_p_bonferroni_family_54"] = min(1.0, p5 * constrained_broad_family_size)

    constrained_multiple_testing = {
        "constrained_endpoint_family_size": constrained_family_size,
        "within_family_adjustment": "Holm across four fixed constrained mixes x Top10/Top5 5-of-5 endpoints, separately within each chronological split",
        "broader_family_size": constrained_broad_family_size,
        "broader_adjustment": "Bonferroni across 42 individual Top20 configurations, 4 unconstrained fusions and 8 constrained Top10/Top5 endpoints",
        "interpretation": "The legacy Top20 candidate set is held constant. Within-family signals are exploratory and broader correction plus prior strategy selection must be considered."
    }
    output={"status":"COMPLETE_RETROSPECTIVE_DIAGNOSTIC","source":"historical_rule_ledger.csv",
            "targets":n,"first_target":targets[0][0],"last_target":targets[-1][0],
            "split_sizes":{k:len(v) for k,v in split.items()},
            "random_top20_5of5_baseline":BASELINE,
            "multiple_testing":multiple_testing,
            "stage_multiple_testing":{"individual_configuration_family_size":len(cfgs),"adjustment":"Bonferroni across individual configurations for Top20 5-of-5, separately overall and by chronological split"},
            "constrained_multiple_testing":constrained_multiple_testing,
            "per_target_cascade_ledger":"reports/sequence_agent/cascade_target_hit_ledger.csv",
            "stage_loss_by_configuration":stage,"fixed_fusion_walkforward":mix_results,
            "constrained_legacy_top20_mixes":constrained_results,
            "guardrail":"Exploratory only. Historical walk-forward predictions are not prospective Shadow; constrained mixes preserve the legacy Top20 set and only change the Top10/Top5 ordering. Formula selection remains retrospective; no model is promoted by this report."}
    (OUT/"stage_loss_analysis.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    (OUT/"top20_mix_walkforward.json").write_text(json.dumps({"status":output["status"],"targets":n,"splits":output["split_sizes"],"baseline":BASELINE,"baselines":{"top20_5of5_probability":BASELINE,"top10_5of5_probability":BASELINE_TOP10,"top5_5of5_probability":BASELINE_TOP5,"mean_top20_hits":2.5,"mean_top10_hits":1.25,"mean_top5_hits":0.625},"multiple_testing":multiple_testing,"stage_multiple_testing":output["stage_multiple_testing"],"constrained_multiple_testing":constrained_multiple_testing,"individual_strategy_baselines":{model:stage[model]["chronological_splits"] for model in sorted(set([anchor] + [m for models in model_sets.values() for m in models]))},"mixes":mix_results,"constrained_mixes":constrained_results,"guardrail":output["guardrail"]},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":output["status"],"targets":n,"first":targets[0][0],"last":targets[-1][0],"mixes":list(mix_results),"constrained_mixes":list(constrained_results),"cascade_ledger_rows":len(cascade_rows)},ensure_ascii=False))

if __name__=="__main__":
    main()
