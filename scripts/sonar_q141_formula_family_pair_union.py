#!/usr/bin/env python3
"""Q141-C1: size-adjusted pair-union complementarity with predictable e-process."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
import numpy as np
import sonar_q141_formula_family_anticipation as base

ROOT = base.ROOT
OUT = base.OUT
EXPECTED_TARGETS = 3354
EXPECTED_SPLITS = {"discovery": 2013, "validation": 671, "blind_oos": 670}
LAMBDA_GRID = (0.05, 0.10, 0.20, 0.40)
FAMILY_PAIRS = tuple(combinations(base.FAMILY_NAMES, 2))
PREREG_PATH = OUT / "q141_formula_family_pair_union_preregistration_2026-11-12.json"
REPORT_PATH = OUT / "q141_formula_family_pair_union_report_2026-11-12.json"
LEDGER_PATH = OUT / "q141_formula_family_pair_union_target_ledger_2026-11-12.csv"
MANIFEST_PATH = OUT / "q141_formula_family_pair_union_manifest_2026-11-12.json"
LEDGER_FIELDS = ("target_index","target_offset","target_date","cutoff_date","prior_draws","split","actual_quintet","family_a","family_b","union_mask","union_size","union_hits","expected_hits","excess_hits")


def logsumexp(values):
    values = list(values)
    maximum = max(values)
    return maximum + math.log(sum(math.exp(value - maximum) for value in values))


def centered_log_mgf(union_size, lam):
    """Exact log E[exp(lambda*(H-mu))] for H~Hypergeom(40, union_size, 5)."""
    pmf = base.hypergeom_pmf(int(union_size))
    mean = 5.0 * int(union_size) / 40.0
    terms = [math.log(probability) + lam * hits for hits, probability in pmf.items() if probability > 0.0]
    return logsumexp(terms) - lam * mean


def family_top5_masks(raw_features):
    standardized = base.zscore_columns(raw_features)
    masks = {}
    for family, indices in base.FAMILIES.items():
        ranks = base.rank_scores(standardized[:, indices].mean(axis=1))
        selected = np.flatnonzero(ranks <= 5)
        if len(selected) != 5:
            raise RuntimeError("Q141_C1_BLOCKED: family Top-5 cardinality is not five")
        masks[family] = sum(1 << int(number) for number in selected)
    return masks


def pair_union_size_hits(mask_a, mask_b, actual):
    union_mask = int(mask_a) | int(mask_b)
    union_size = union_mask.bit_count()
    hits = sum(1 for number in actual if union_mask & (1 << int(number)))
    return union_mask, union_size, hits


def build_pair_ledger():
    raw, archive_blob_sha, dates, draws, excluded = base.load_archive()
    n = len(draws)
    scored_targets = n - base.MIN_HISTORY
    if scored_targets != EXPECTED_TARGETS:
        raise RuntimeError(f"Q141_C1_BLOCKED: targets {scored_targets} != {EXPECTED_TARGETS}")
    split_counts = Counter(base.split_name(offset, scored_targets) for offset in range(scored_targets))
    if dict(split_counts) != EXPECTED_SPLITS or len(FAMILY_PAIRS) != 15:
        raise RuntimeError(f"Q141_C1_BLOCKED: split/pair mismatch {dict(split_counts)}")
    prefix, pos_prefix = base.build_prefix_arrays(draws)
    pair_counts = np.zeros((40, 40), dtype=np.int32)
    occurrence_lists = [[] for _ in range(40)]
    ledger = []
    for i, draw in enumerate(draws):
        if i >= base.MIN_HISTORY:
            offset = i - base.MIN_HISTORY
            split = base.split_name(offset, scored_targets)
            features = base.feature_matrix(i, draws, prefix, pos_prefix, pair_counts, occurrence_lists)
            if not np.array_equal(features[:, 0], features[:, 25]) or not np.array_equal(features[:, 1], features[:, 26]):
                raise RuntimeError("Q141_C1_BLOCKED: duplicate alias mismatch")
            masks = family_top5_masks(features)
            for family_a, family_b in FAMILY_PAIRS:
                union_mask, union_size, union_hits = pair_union_size_hits(masks[family_a], masks[family_b], draw)
                if not 5 <= union_size <= 10 or not 0 <= union_hits <= 5:
                    raise RuntimeError("Q141_C1_BLOCKED: invalid union size/hits")
                expected = 5.0 * union_size / 40.0
                ledger.append({
                    "target_index":i,"target_offset":offset,"target_date":dates[i],"cutoff_date":dates[i-1],
                    "prior_draws":i,"split":split,"actual_quintet":" ".join(str(x+1) for x in draw),
                    "family_a":family_a,"family_b":family_b,"union_mask":union_mask,"union_size":union_size,
                    "union_hits":union_hits,"expected_hits":expected,"excess_hits":union_hits-expected
                })
        # Add the target draw only after every candidate union for that target has been scored.
        for value in draw:
            occurrence_lists[value].append(i)
        for a, b in combinations(draw, 2):
            pair_counts[a, b] += 1
            pair_counts[b, a] += 1
    if len(ledger) != scored_targets * len(FAMILY_PAIRS):
        raise RuntimeError("Q141_C1_BLOCKED: incomplete target x pair ledger")
    if not all(row["cutoff_date"] < row["target_date"] and row["prior_draws"] == row["target_index"] for row in ledger):
        raise RuntimeError("Q141_C1_BLOCKED: chronology failure")
    return raw, archive_blob_sha, dates, draws, excluded, dict(split_counts), ledger


def e_process_result(rows):
    """Mixture e-process; Ville p-value uses the maximum over all within-split looks."""
    log_e_by_lambda = [0.0 for _ in LAMBDA_GRID]
    max_log_e_mixture = 0.0
    for row in rows:
        u, hits = int(row["union_size"]), int(row["union_hits"])
        mean = 5.0 * u / 40.0
        for j, lam in enumerate(LAMBDA_GRID):
            log_e_by_lambda[j] += lam * (hits - mean) - centered_log_mgf(u, lam)
        log_mix = logsumexp(log_e_by_lambda) - math.log(len(LAMBDA_GRID))
        max_log_e_mixture = max(max_log_e_mixture, log_mix)
    final_log_e = logsumexp(log_e_by_lambda) - math.log(len(LAMBDA_GRID))
    p_value = math.exp(-max_log_e_mixture) if max_log_e_mixture < 745.0 else 0.0
    return {"log_e_mixture_final":final_log_e,"max_log_e_mixture":max_log_e_mixture,"p_anytime_raw":min(1.0,max(0.0,p_value)),"log_e_by_lambda_final":{str(lam):log_e_by_lambda[j] for j,lam in enumerate(LAMBDA_GRID)}}


def summarize_pairs(ledger):
    grouped = defaultdict(list)
    for row in ledger:
        grouped[(row["split"],row["family_a"],row["family_b"])].append(row)
    results=[]
    for split in ("discovery","validation","blind_oos"):
        for family_a,family_b in FAMILY_PAIRS:
            rows=grouped[(split,family_a,family_b)]
            n=len(rows)
            observed=sum(int(r["union_hits"]) for r in rows)
            expected=sum(float(r["expected_hits"]) for r in rows)
            union_total=sum(int(r["union_size"]) for r in rows)
            results.append({
                "split":split,"family_a":family_a,"family_b":family_b,"targets":n,
                "mean_union_size":union_total/n,"observed_hits":observed,"expected_hits":expected,
                "excess_hits":observed-expected,"excess_hits_per_target":(observed-expected)/n,
                "observed_to_expected_ratio":observed/expected if expected else None,
                "hits_per_union_candidate":observed/union_total if union_total else None,
                **e_process_result(rows)
            })
    if len(results)!=45:
        raise RuntimeError("Q141_C1_BLOCKED: expected 45 pair x split tests")
    adjusted=base.holm_adjust([r["p_anytime_raw"] for r in results])
    for row,p_adj in zip(results,adjusted):
        row["p_holm_45"]=float(p_adj)
    return results


def write_ledger(rows):
    OUT.mkdir(parents=True,exist_ok=True)
    with LEDGER_PATH.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=LEDGER_FIELDS,lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return LEDGER_PATH.read_bytes()


def run():
    if not PREREG_PATH.exists():
        raise RuntimeError("Q141_C1_BLOCKED: preregistration file missing")
    prereg_bytes=PREREG_PATH.read_bytes()
    prereg=json.loads(prereg_bytes.decode("utf-8"))
    if prereg.get("task_id")!="Q141-C1" or tuple(prereg.get("inference",{}).get("lambda_grid",[]))!=LAMBDA_GRID:
        raise RuntimeError("Q141_C1_BLOCKED: preregistration/method mismatch")
    raw,archive_blob_sha,dates,draws,excluded,split_counts,ledger=build_pair_ledger()
    ledger_bytes=write_ledger(ledger)
    results=summarize_pairs(ledger)
    blind=[r for r in results if r["split"]=="blind_oos"]
    signals=[r for r in blind if r["excess_hits"]>0 and r["p_holm_45"]<0.05]
    best_blind=sorted(blind,key=lambda r:(r["p_holm_45"],-r["excess_hits_per_target"]))[0]
    decision="SIZE_ADJUSTED_PAIR_COMPLEMENTARITY_SIGNAL" if signals else "NO_SIZE_ADJUSTED_PAIR_COMPLEMENTARITY_LIFT_DEMONSTRATED"
    code_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    ledger_sha=hashlib.sha256(ledger_bytes).hexdigest()
    report={
        "schema_version":"1.0","task_id":"Q141-C1","status":"EXECUTED_EXPLORATORY","decision":decision,
        "hypothesis":prereg["hypothesis"],
        "source":{"archive_path":"data/storico_daily.csv","archive_git_blob_sha1":archive_blob_sha,"archive_sha256":hashlib.sha256(raw).hexdigest(),"eligible_draw_count":len(draws),"first_date":dates[0],"last_date":dates[-1],"excluded_rows_after_cutoff":excluded,"contest_315_used":False},
        "walkforward":{"minimum_prior_history":base.MIN_HISTORY,"scored_targets":len(ledger)//len(FAMILY_PAIRS),"split_counts":split_counts,"strict_prior":True,"state_update":"target added only after prior-only unions frozen/scored","family_count":len(base.FAMILY_NAMES),"pair_count":len(FAMILY_PAIRS),"target_pair_ledger_rows":len(ledger)},
        "null_model":{"assumption":"independent uniform 5-of-40 draws","conditional_distribution":"H_t | F_(t-1) ~ Hypergeometric(N=40,K=U_t,n=5)","conditional_mean":"5*U_t/40","adaptive_union_size_handled":True,"method_note":"predictable conditional MGF; no unconditional fixed-parameter convolution"},
        "inference":{"method":"equal mixture of predictable hypergeometric e-processes","lambda_grid":list(LAMBDA_GRID),"p_value":"min(1,1/max_t E_mix,t), Ville inequality","alternative":"one-sided positive excess coverage","test_count":len(results),"holm_method":"Holm-Bonferroni","holm_family_size":45,"holm_scope":"15 unordered family pairs x 3 chronological splits"},
        "results":results,
        "primary_blind":{"tested_pairs":len(blind),"significant_pairs_after_holm":len(signals),"best_pair_by_adjusted_p_then_excess":best_blind,"signals":signals},
        "acceptance":{"archive_git_blob_sha_verified":archive_blob_sha==base.EXPECTED_ARCHIVE_BLOB_SHA1,"eligible_draw_count_verified":len(draws)==base.EXPECTED_ELIGIBLE_DRAWS,"target_count_verified":len(ledger)==EXPECTED_TARGETS*len(FAMILY_PAIRS),"split_counts_verified":split_counts==EXPECTED_SPLITS,"family_pair_count_verified":len(FAMILY_PAIRS)==15,"test_count_verified":len(results)==45,"union_size_bounds_verified":all(5<=int(r["union_size"])<=10 for r in ledger),"union_hit_bounds_verified":all(0<=int(r["union_hits"])<=5 for r in ledger),"strict_prior_cutoffs_verified":all(r["cutoff_date"]<r["target_date"] and r["prior_draws"]==r["target_index"] for r in ledger),"holm_family_size_verified":all("p_holm_45" in r for r in results)},
        "limitations":["Six coarse Q80-derived families only; not the full Q141 formula universe.","Historical archive is exposed to extensive prior SONAR experimentation; not virgin prospective confirmation.","Conditional null assumes independent uniform draws of five distinct numbers from 1..40.","Holm controls the 45 Q141-C1 tests only, not the full Q00-Q141 research family.","A pair union is not an ex-ante selector; no pair is selected or promoted from Blind OOS."],
        "next_action":"Complete Q141-A formula lineage reconciliation and Q141-B canonical typed registry; use C1 only as a bounded complementarity diagnostic.",
        "code_sha256":code_sha,"target_ledger_sha256":ledger_sha,"preregistration_sha256":hashlib.sha256(prereg_bytes).hexdigest()
    }
    if not all(report["acceptance"].values()):
        raise RuntimeError("Q141_C1_BLOCKED: acceptance checks failed")
    report_bytes=(json.dumps(report,indent=2,sort_keys=True)+"\n").encode("utf-8")
    REPORT_PATH.write_bytes(report_bytes)
    manifest={"schema_version":"1.0","task_id":"Q141-C1","status":"REPLAYABLE_EXPLORATORY_BUNDLE","source_archive_git_blob_sha1":archive_blob_sha,"code_sha256":code_sha,"preregistration_sha256":hashlib.sha256(prereg_bytes).hexdigest(),"report_path":str(REPORT_PATH.relative_to(ROOT)),"report_sha256":hashlib.sha256(report_bytes).hexdigest(),"target_ledger_path":str(LEDGER_PATH.relative_to(ROOT)),"target_ledger_sha256":ledger_sha,"target_ledger_rows":len(ledger),"split_counts":split_counts,"family_pair_count":len(FAMILY_PAIRS),"test_count":len(results),"holm_family_size":45,"lambda_grid":list(LAMBDA_GRID)}
    manifest_bytes=(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode("utf-8")
    MANIFEST_PATH.write_bytes(manifest_bytes)
    print("SONAR_Q141_C1_RESULT "+json.dumps({"status":report["status"],"decision":decision,"targets":EXPECTED_TARGETS,"pair_ledger_rows":len(ledger),"tests":len(results),"blind_significant_pairs":len(signals),"best_blind_pair":[best_blind["family_a"],best_blind["family_b"]],"best_blind_excess_per_target":best_blind["excess_hits_per_target"],"best_blind_p_holm_45":best_blind["p_holm_45"],"report_sha256":manifest["report_sha256"],"target_ledger_sha256":ledger_sha},separators=(",",":")))
    print("SONAR_Q141_C1_ACCEPTANCE_PASS: source, strict-prior pair ledger, conditional e-process and Holm family verified")
    return report


if __name__=="__main__":
    run()
