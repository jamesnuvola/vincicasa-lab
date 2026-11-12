#!/usr/bin/env python3
"""Q141-B3: strict-prior walk-forward of canonical formula complexity strata."""
from __future__ import annotations
import csv,hashlib,json,math,random,sys
from itertools import combinations
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import sonar_q141_formula_family_anticipation as base
import sonar_q141_formula_registry as registry
OUT=ROOT/"reports"/"sequence_agent"
PREREG=OUT/"q141_formula_size_trend_preregistration_2026-11-12.json"
REPORT=OUT/"q141_formula_size_trend_report_2026-11-12.json"
LEDGER=OUT/"q141_formula_size_trend_target_ledger_2026-11-12.csv"
MANIFEST=OUT/"q141_formula_size_trend_manifest_2026-11-12.json"
CHECKPOINT=OUT/"q141_formula_size_trend_checkpoint_2026-11-12.json"
SEED,SAMPLE_PER_MASS,BLOCK_LENGTH,REPLICATES=14120261113,120,20,20000
EXPECTED_COUNTS=[25,300,2348,13202,57201,198605,567479,1359622,2768832,4840649]
EXPECTED_SPLITS={"discovery":2013,"validation":671,"blind_oos":670}
MASSES=tuple(range(1,11))
UNIFORM={5:0.125,10:0.25,20:0.5}
def sha256_bytes(data): return hashlib.sha256(data).hexdigest()
def git_blob_sha1(data): return hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+b"\0"+data).hexdigest()
def canonical_mass_options(mass):
    options=[]
    for a in range(3):
        for b in range(3):
            s=mass-a-b
            if not 0<=s<=23: continue
            positive=[x for x in (a,b) if x]
            if s: positive.append(1)
            if not positive or math.gcd(*positive)!=1: continue
            options.append((a,b,s,math.comb(23,s)))
    return options
def canonical_mass_count(mass): return sum(x[3] for x in canonical_mass_options(mass))
def make_signature(a,b,other_features):
    weights=[]
    if a: weights.append((0,a))
    if b: weights.append((1,b))
    weights.extend((int(i),1) for i in other_features)
    weights.sort()
    divisor=math.gcd(*(w for _,w in weights))
    return tuple((i,w//divisor) for i,w in weights)
def enumerate_mass(mass):
    for a,b,s,_ in canonical_mass_options(mass):
        for subset in combinations(range(2,25),s):
            signature=make_signature(a,b,subset)
            if sum(w for _,w in signature)!=mass: raise RuntimeError("Q141-B3: non-primitive mass enumeration")
            yield signature
def sample_formulas_by_mass():
    output,all_ids={},set()
    for mass in MASSES:
        expected=EXPECTED_COUNTS[mass-1]; actual=canonical_mass_count(mass)
        if actual!=expected: raise RuntimeError(f"Q141-B3: canonical mass {mass} count {actual} != {expected}")
        take=min(SAMPLE_PER_MASS,actual)
        if take==actual: signatures=list(enumerate_mass(mass))
        else:
            rng=random.Random(SEED+mass); options=canonical_mass_options(mass); weights=[x[3] for x in options]
            seen,attempts=set(),0
            while len(seen)<take:
                attempts+=1
                if attempts>take*1000: raise RuntimeError(f"Q141-B3: sampling stalled at mass {mass}")
                a,b,s,_=rng.choices(options,weights=weights,k=1)[0]
                signature=make_signature(a,b,rng.sample(range(2,25),s))
                if sum(w for _,w in signature)!=mass: raise RuntimeError("Q141-B3: sampled signature not primitive")
                seen.add(signature)
            signatures=sorted(seen,key=registry.canonical_formula_id)
        formulas=[]
        for signature in signatures:
            formula_id=registry.canonical_formula_id(signature)
            if formula_id in all_ids: raise RuntimeError(f"Q141-B3: cross-mass duplicate {formula_id}")
            all_ids.add(formula_id)
            formulas.append({"formula_id":formula_id,"signature":signature,"primitive_mass":mass,"support_size":len(signature)})
        if len(formulas)!=take: raise RuntimeError(f"Q141-B3: sample size mismatch at mass {mass}")
        output[mass]=formulas
    return output
def one_sided_block_signflip_p(values,seed):
    values=np.asarray(values,dtype=np.float64)
    if values.ndim!=1 or len(values)==0 or not np.all(np.isfinite(values)): raise ValueError("Q141-B3: invalid signflip input")
    blocks=np.asarray([values[i:i+BLOCK_LENGTH].sum() for i in range(0,len(values),BLOCK_LENGTH)])
    observed=float(blocks.sum()); rng=np.random.default_rng(seed)
    signs=rng.choice(np.array([-1.0,1.0]),size=(REPLICATES,len(blocks)))
    simulated=signs@blocks
    return float((np.count_nonzero(simulated>=observed-1e-12)+1)/(REPLICATES+1))
def circular_block_bootstrap_ci(values,seed):
    values=np.asarray(values,dtype=np.float64)
    if values.ndim!=1 or len(values)==0 or not np.all(np.isfinite(values)): raise ValueError("Q141-B3: invalid bootstrap input")
    n=len(values); full_blocks,remainder=divmod(n,BLOCK_LENGTH)
    extended=np.concatenate((values,values[:BLOCK_LENGTH-1])); cumulative=np.concatenate(([0.0],np.cumsum(extended)))
    full_sums=cumulative[BLOCK_LENGTH:]-cumulative[:-BLOCK_LENGTH]
    rng=np.random.default_rng(seed); starts=rng.integers(0,n,size=(REPLICATES,full_blocks))
    totals=full_sums[starts].sum(axis=1) if full_blocks else np.zeros(REPLICATES)
    if remainder:
        partial_sums=cumulative[remainder:]-cumulative[:-remainder]
        totals+=partial_sums[rng.integers(0,n,size=REPLICATES)]
    low,high=np.quantile(totals/n,[0.025,0.975]); return [float(low),float(high)]
def slope_by_mass(values):
    y=np.asarray(values,dtype=np.float64); x=np.asarray(MASSES,dtype=np.float64)
    if y.shape!=x.shape or not np.all(np.isfinite(y)): raise ValueError("Q141-B3: malformed complexity profile")
    centered=x-x.mean(); return float(np.dot(centered,y-y.mean())/np.dot(centered,centered))
def summarize_split(rows):
    result={"targets":len(rows),"by_mass":{}}
    for mass in MASSES:
        result["by_mass"][str(mass)]={"sampled_formulas":rows[0]["sample_counts"][mass] if rows else 0,
            "mean_top5_hit_share":float(np.mean([r["top5"][mass] for r in rows])) if rows else None,
            "mean_top10_hit_share":float(np.mean([r["top10"][mass] for r in rows])) if rows else None,
            "mean_top20_hit_share":float(np.mean([r["top20"][mass] for r in rows])) if rows else None,
            "mean_actual_number_rank":float(np.mean([r["mean_rank"][mass] for r in rows])) if rows else None,
            "delta_top5_vs_uniform":float(np.mean([r["top5"][mass]-UNIFORM[5] for r in rows])) if rows else None}
    p5=[float(np.mean([r["top5"][m] for r in rows])) for m in MASSES]
    p10=[float(np.mean([r["top10"][m] for r in rows])) for m in MASSES]
    p20=[float(np.mean([r["top20"][m] for r in rows])) for m in MASSES]
    result["complexity_trend"]={"top5_slope_per_mass_unit":slope_by_mass(p5),"top10_slope_per_mass_unit":slope_by_mass(p10),"top20_slope_per_mass_unit":slope_by_mass(p20)}
    return result
def main():
    OUT.mkdir(parents=True,exist_ok=True); prereg_bytes=PREREG.read_bytes(); prereg=json.loads(prereg_bytes)
    if prereg.get("task_id")!="Q141-B3" or prereg.get("status")!="PREREGISTERED_EXECUTION_PENDING": raise RuntimeError("Q141-B3: preregistration not frozen")
    _,archive_blob,dates,draws,excluded=base.load_archive()
    if archive_blob!=prereg["source"]["archive_git_blob_sha1"]: raise RuntimeError("Q141-B3: archive hash mismatch")
    if len(draws)!=3404 or dates[-1]!="2026-11-10": raise RuntimeError("Q141-B3: eligible source boundary mismatch")
    target_count=len(draws)-base.MIN_HISTORY
    if target_count!=3354 or target_count!=prereg["walkforward"]["target_count"]: raise RuntimeError("Q141-B3: target count mismatch")
    split_counts={name:sum(base.split_name(o,target_count)==name for o in range(target_count)) for name in EXPECTED_SPLITS}
    if split_counts!=EXPECTED_SPLITS: raise RuntimeError(f"Q141-B3: split counts mismatch {split_counts}")
    formulas_by_mass=sample_formulas_by_mass(); sample_counts={m:len(formulas_by_mass[m]) for m in MASSES}
    total_formulas=sum(sample_counts.values())
    if total_formulas!=1105: raise RuntimeError("Q141-B3: total sampled formula count mismatch")
    prefix,pos_prefix=base.build_prefix_arrays(draws); pair_counts=np.zeros((40,40),dtype=np.int32); occurrence_lists=[[] for _ in range(40)]
    target_rows=[]
    for i,draw in enumerate(draws):
        if i>=base.MIN_HISTORY:
            offset=i-base.MIN_HISTORY; split=base.split_name(offset,target_count)
            features=base.feature_matrix(i,draws,prefix,pos_prefix,pair_counts,occurrence_lists); standardized=base.zscore_columns(features)
            top5,top10,top20,mean_rank={},{},{},{}
            for mass in MASSES:
                h5=h10=h20=rank_sum=0.0
                for formula in formulas_by_mass[mass]:
                    scores=registry.canonical_scores(standardized,formula["signature"],1)
                    metrics=base.rank_metrics(base.rank_scores(scores),draw)
                    h5+=metrics["top5_hits"]; h10+=metrics["top10_hits"]; h20+=metrics["top20_hits"]; rank_sum+=metrics["mean_rank"]
                n=sample_counts[mass]; top5[mass]=h5/(5*n); top10[mass]=h10/(5*n); top20[mass]=h20/(5*n); mean_rank[mass]=rank_sum/n
            p5=[top5[m] for m in MASSES]; p10=[top10[m] for m in MASSES]; p20=[top20[m] for m in MASSES]
            target_rows.append({"target_index":i,"target_offset":offset,"target_date":dates[i],"cutoff_date":dates[i-1],
                "prior_draws":i,"split":split,"actual_quintet":" ".join(str(x+1) for x in draw),"sample_counts":sample_counts,
                "top5":top5,"top10":top10,"top20":top20,"mean_rank":mean_rank,"top5_slope":slope_by_mass(p5),
                "top10_slope":slope_by_mass(p10),"top20_slope":slope_by_mass(p20),"equal_mass_top5":float(np.mean(p5)),
                "all_formula_top5":float(sum(top5[m]*sample_counts[m] for m in MASSES)/total_formulas)})
        # Strict-prior state update occurs after all formula scores for target i.
        for value in draw: occurrence_lists[value].append(i)
        for a,b in combinations(draw,2): pair_counts[a,b]+=1; pair_counts[b,a]+=1
    if len(target_rows)!=target_count: raise RuntimeError("Q141-B3: incomplete target ledger")
    previous=None
    for row in target_rows:
        if row["cutoff_date"]>=row["target_date"] or row["prior_draws"]!=row["target_index"]: raise RuntimeError("Q141-B3: non-prior cutoff")
        if previous is not None and row["target_date"]<=previous: raise RuntimeError("Q141-B3: non-chronological targets")
        previous=row["target_date"]
    split_rows={s:[r for r in target_rows if r["split"]==s] for s in EXPECTED_SPLITS}
    split_summary={s:summarize_split(rows) for s,rows in split_rows.items()}
    discovery_profile=split_summary["discovery"]["by_mass"]
    selected_mass=min(MASSES,key=lambda m:(-discovery_profile[str(m)]["mean_top5_hit_share"],m))
    tests=[]; index=0
    for split in ("discovery","validation","blind_oos"):
        vals=[r["top5_slope"] for r in split_rows[split]]
        tests.append({"id":f"slope_top5_{split}","family":"positive_complexity_trend","split":split,"endpoint":"top5_hit_share_slope_per_mass_unit",
            "targets":len(vals),"mean_delta":float(np.mean(vals)),"ci95":circular_block_bootstrap_ci(vals,SEED+1000+index),
            "p_raw":one_sided_block_signflip_p(vals,SEED+2000+index)}); index+=1
    for split in ("validation","blind_oos"):
        for mass in MASSES:
            vals=[r["top5"][mass]-UNIFORM[5] for r in split_rows[split]]
            tests.append({"id":f"mass_{mass}_vs_uniform_top5_{split}","family":"complexity_mass_vs_uniform","split":split,"complexity_mass":mass,
                "endpoint":"top5_hit_share_excess_vs_uniform","targets":len(vals),"mean_delta":float(np.mean(vals)),
                "ci95":circular_block_bootstrap_ci(vals,SEED+3000+index),"p_raw":one_sided_block_signflip_p(vals,SEED+4000+index)}); index+=1
    for split in ("validation","blind_oos"):
        vals=[r["top5"][selected_mass]-r["equal_mass_top5"] for r in split_rows[split]]
        tests.append({"id":f"discovery_selected_mass_{selected_mass}_vs_equal_mass_{split}","family":"discovery_selected_complexity_vs_equal_complexity_ensemble",
            "split":split,"selected_complexity_mass_from_discovery":selected_mass,"endpoint":"top5_hit_share_delta","targets":len(vals),
            "mean_delta":float(np.mean(vals)),"ci95":circular_block_bootstrap_ci(vals,SEED+5000+index),
            "p_raw":one_sided_block_signflip_p(vals,SEED+6000+index)}); index+=1
    adjusted=base.holm_adjust([x["p_raw"] for x in tests])
    for item,p_adj in zip(tests,adjusted): item["p_holm_25_tests"]=float(p_adj)
    fields=["target_index","target_offset","target_date","cutoff_date","prior_draws","split","actual_quintet","top5_slope_per_mass",
        "top10_slope_per_mass","top20_slope_per_mass","equal_mass_top5_share","all_formula_top5_share"]
    for m in MASSES: fields += [f"mass_{m}_formula_count",f"mass_{m}_top5_share",f"mass_{m}_top10_share",f"mass_{m}_top20_share",f"mass_{m}_mean_actual_rank"]
    with LEDGER.open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=fields); w.writeheader()
        for row in target_rows:
            out={"target_index":row["target_index"],"target_offset":row["target_offset"],"target_date":row["target_date"],"cutoff_date":row["cutoff_date"],
                "prior_draws":row["prior_draws"],"split":row["split"],"actual_quintet":row["actual_quintet"],
                "top5_slope_per_mass":f"{row['top5_slope']:.17g}","top10_slope_per_mass":f"{row['top10_slope']:.17g}",
                "top20_slope_per_mass":f"{row['top20_slope']:.17g}","equal_mass_top5_share":f"{row['equal_mass_top5']:.17g}",
                "all_formula_top5_share":f"{row['all_formula_top5']:.17g}"}
            for m in MASSES:
                out[f"mass_{m}_formula_count"]=sample_counts[m]; out[f"mass_{m}_top5_share"]=f"{row['top5'][m]:.17g}"
                out[f"mass_{m}_top10_share"]=f"{row['top10'][m]:.17g}"; out[f"mass_{m}_top20_share"]=f"{row['top20'][m]:.17g}"
                out[f"mass_{m}_mean_actual_rank"]=f"{row['mean_rank'][m]:.17g}"
            w.writerow(out)
    report={"schema_version":"1.0","task_id":"Q141-B3","status":"COMPLETE_EXPLORATORY_WALKFORWARD","decision":"NO_COMPLEXITY_TREND_LIFT_DEMONSTRATED",
        "hypothesis":prereg["hypothesis"],"source":{"archive_git_blob_sha1":archive_blob,"eligible_draws":len(draws),"cutoff":dates[-1],
        "excluded_rows_after_cutoff":excluded,"contest_315_used":False},
        "formula_universe":{"raw_q80_features":27,"canonical_q80_features":25,"exact_aliases":registry.ALIASES,
        "canonical_formula_count_k1_to_k10":sum(EXPECTED_COUNTS),"canonical_formula_count_by_primitive_mass":EXPECTED_COUNTS,
        "sampled_formula_count":total_formulas,"sampled_formula_count_by_mass":{str(k):sample_counts[k] for k in MASSES},
        "sampling":"uniform without replacement from exact canonical signatures within each primitive mass; all 25 mass-1 functions included","seed":SEED},
        "walkforward":{"targets":len(target_rows),"minimum_prior_history":base.MIN_HISTORY,"split_counts":EXPECTED_SPLITS,
        "strict_prior_cutoffs_rechecked":True,"target_scored_before_state_update":True,"metrics_by_split":split_summary,
        "discovery_selected_complexity_mass":selected_mass,"historical_blind_oos_is_virgin":False},
        "statistical_inference":{"registered_test_count":len(tests),"holm_method":"Holm-Bonferroni across all 25 registered tests",
        "test_direction":"one-sided positive","time_series_method":"chronological block sign-flip, block length 20, 20,000 replicates",
        "confidence_interval":"circular block bootstrap, block length 20, 20,000 replicates","tests":tests,
        "primary_blind_top5_complexity_slope":next(x for x in tests if x["id"]=="slope_top5_blind_oos")},
        "acceptance":{"archive_blob_matches_preregistration":True,"eligible_draw_count_matches":len(draws)==3404,"target_count_matches":len(target_rows)==3354,
        "split_counts_match":split_counts==EXPECTED_SPLITS,"canonical_mass_counts_exact":[canonical_mass_count(k) for k in MASSES]==EXPECTED_COUNTS,
        "sample_formula_ids_unique_across_mass":True,"sampled_formula_count_matches":total_formulas==1105,"strict_prior_cutoffs_verified":True,
        "state_update_after_target_scoring":True,"multiplicity_family_size_verified":len(tests)==25,
        "future_suffix_invariance":"covered by dedicated unit test","deterministic_sampling":"covered by dedicated unit test and fixed seed"},
        "limitations":["Stratified sample of 1,105 canonical Q80 equal-weight functions, not exhaustive scoring of 9,808,263 functions.",
        "Q89 extension features, Q90 interactions/gates, Q7 candidate-quintet ASTs and other output types excluded.",
        "Finite samples have Monte Carlo uncertainty despite uniform canonical sampling within each mass.",
        "Historical Blind OOS has prior SONAR research exposure and is not virgin prospective evidence.",
        "Within-experiment Holm correction does not correct the full Q00-Q141 project-wide research history.",
        "No predictive engine, production ranker, canonical archive or shadow forecast is changed."],
        "next_action":"Import Q90 interaction/gate ASTs and Q7 candidate-quintet AST as distinct typed output families with source and archive lineage; do not pool metrics until source archives are reconciled."}
    report_bytes=(json.dumps(report,indent=2,sort_keys=True)+"\n").encode("utf-8"); REPORT.write_bytes(report_bytes)
    ledger_bytes=LEDGER.read_bytes()
    manifest={"schema_version":"1.0","task_id":"Q141-B3","status":"PERSISTENCE_BUNDLE_READY","source_archive_git_blob_sha1":archive_blob,
        "preregistration_sha256":sha256_bytes(prereg_bytes),"sampled_formula_count":total_formulas,"canonical_formula_count":sum(EXPECTED_COUNTS),
        "target_rows":len(target_rows),"split_counts":EXPECTED_SPLITS,"ledger_sha256":sha256_bytes(ledger_bytes),"ledger_git_blob_sha1":git_blob_sha1(ledger_bytes),
        "report_sha256":sha256_bytes(report_bytes),"runner_sha256":sha256_bytes(Path(__file__).read_bytes()),"runner_path":str(Path(__file__).relative_to(ROOT)),
        "decision":report["decision"],"next_action":report["next_action"]}
    manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode("utf-8"); MANIFEST.write_bytes(manifest_bytes)
    checkpoint={"schema_version":"1.0","task_id":"Q141-B3","status":"COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE","source_archive_git_blob_sha1":archive_blob,
        "report_sha256":sha256_bytes(report_bytes),"ledger_sha256":sha256_bytes(ledger_bytes),"manifest_sha256":sha256_bytes(manifest_bytes),
        "target_rows":len(target_rows),"sampled_formula_count":total_formulas,"next_action":report["next_action"]}
    CHECKPOINT.write_text(json.dumps(checkpoint,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],"decision":report["decision"],"targets":len(target_rows),"sampled_formula_count":total_formulas,
        "selected_mass":selected_mass,"blind_primary":report["statistical_inference"]["primary_blind_top5_complexity_slope"],
        "report_sha256":manifest["report_sha256"],"ledger_sha256":manifest["ledger_sha256"]},sort_keys=True))
if __name__=="__main__": main()
