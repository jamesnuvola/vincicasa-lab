#!/usr/bin/env python3
"""Q141-B6: prequential adaptation over the immutable Q7 quintet formula grammar."""
from __future__ import annotations
import csv, hashlib, itertools, json, math, os
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
Q7_ROOT=ROOT/"q7-source"
OUT=ROOT/"reports"/"sequence_agent"
TASK="Q141-B6"
WINDOW=100
CANDIDATES=658008
FORMULAS=1023
BOOTSTRAP_REPS=20000
SIGNFLIP_REPS=20000
BLOCK_LENGTH=100
SEED=14120261116
Q7_COMMIT="7a37cab601c5f9386131a00246963f8e4aeabf74"
Q7_ARCHIVE_BLOB="7dab05ba49ace909fe8783eef729605049c65e50"
Q7_WF_MANIFEST_BLOB="aae2c7768c9d37bf633a13939f2b686bcce83a27"
Q7_CATALOG_MANIFEST_BLOB="5cdf9c24431ea23b2176aa6a19133b7f4435980c"
Q7_RUNNER_BLOB="ad1c7fa721f316b3af0018f5da4a0a905bb62dcf"
Q141_ARCHIVE_BLOB="fcb453ed06c8002314f826dbac79d6935f9ac103"
REPORT_PATH=OUT/"q141_q7_formula_adaptation_report_2026-11-12.json"
LEDGER_PATH=OUT/"q141_q7_formula_adaptation_target_ledger_2026-11-12.csv"
MANIFEST_PATH=OUT/"q141_q7_formula_adaptation_manifest_2026-11-12.json"
CHECKPOINT_PATH=OUT/"q141_q7_formula_adaptation_checkpoint_2026-11-12.json"

def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""): h.update(chunk)
    return h.hexdigest()

def git_blob_sha1(path):
    b=path.read_bytes()
    return hashlib.sha1(f"blob {len(b)}\0".encode()+b).hexdigest()

def read_archive(path):
    from datetime import date
    out=[]; seen=set(); previous=""
    with path.open(newline="",encoding="utf-8-sig") as f:
        reader=csv.reader(f); header=next(reader,None)
        if header is None or [x.strip().lower() for x in header[:6]] not in (
            ["data","n1","n2","n3","n4","n5"],["date","n1","n2","n3","n4","n5"]):
            raise RuntimeError(f"unexpected archive header: {header}")
        for line,row in enumerate(reader,2):
            if not row or not any(x.strip() for x in row): continue
            if len(row)<6: raise RuntimeError(f"malformed archive row {line}")
            day=row[0].strip()
            try:
                date.fromisoformat(day); nums=tuple(int(x) for x in row[1:6])
            except Exception as exc: raise RuntimeError(f"invalid archive row {line}: {exc}") from exc
            if day in seen or (previous and day<=previous): raise RuntimeError(f"duplicate/nonchronological date {day}")
            if len(set(nums))!=5 or nums!=tuple(sorted(nums)) or any(x<1 or x>40 for x in nums):
                raise RuntimeError(f"invalid quintet {day}: {nums}")
            seen.add(day); previous=day; out.append((day,nums))
    return out

def load_formula_catalog():
    p=Q7_ROOT/"reports/sequence_agent/exhaustive_formula_catalog_manifest.json"
    if git_blob_sha1(p)!=Q7_CATALOG_MANIFEST_BLOB: raise RuntimeError("Q7 catalog manifest blob mismatch")
    manifest=json.loads(p.read_text(encoding="utf-8"))
    families=[x["name"] for x in manifest.get("feature_families",[])]
    if manifest.get("formula_count")!=FORMULAS or manifest.get("candidate_universe_size")!=CANDIDATES or len(families)!=10:
        raise RuntimeError("Q7 formula catalog dimensions mismatch")
    fmap={}
    for path in sorted((Q7_ROOT/"reports/sequence_agent/exhaustive_formula_catalog").glob("formulas_*.json")):
        part=json.loads(path.read_text(encoding="utf-8"))
        for item in part.get("formulas",[]):
            mask=int(item["formula_mask"])
            expected=[families[b] for b in range(10) if mask&(1<<b)]
            if item.get("formula_id")!=f"F{mask:04d}" or item.get("features")!=expected or mask in fmap:
                raise RuntimeError(f"Q7 formula lineage mismatch at mask {mask}")
            fmap[mask]={"formula_id":item["formula_id"],"features":expected,"feature_count":len(expected)}
    if set(fmap)!=set(range(1,FORMULAS+1)): raise RuntimeError("Q7 formula mask universe incomplete")
    return families,fmap

def load_q7_rank_matrix(draws):
    mp=Q7_ROOT/"reports/sequence_agent/exhaustive_formula_walkforward_manifest.json"
    rp=Q7_ROOT/"scripts/sonar_exhaustive_walkforward.py"
    ap=Q7_ROOT/"data/storico_daily.csv"
    if git_blob_sha1(mp)!=Q7_WF_MANIFEST_BLOB: raise RuntimeError("Q7 walkforward manifest blob mismatch")
    if git_blob_sha1(rp)!=Q7_RUNNER_BLOB: raise RuntimeError("Q7 strict-prior runner blob mismatch")
    if git_blob_sha1(ap)!=Q7_ARCHIVE_BLOB: raise RuntimeError("Q7 archive blob mismatch")
    m=json.loads(mp.read_text(encoding="utf-8"))
    if m.get("status")!="VALIDATED_COMPLETE" or m.get("target_count")!=len(draws) or m.get("scored_target_count")!=len(draws)-1:
        raise RuntimeError("Q7 walkforward manifest not complete or target count mismatch")
    if m.get("formula_count")!=FORMULAS or m.get("candidate_universe_size")!=CANDIDATES:
        raise RuntimeError("Q7 walkforward dimensions mismatch")
    ranks=np.full((len(draws),FORMULAS),-1,dtype=np.int32)
    meta=[None]*len(draws)
    columns=["target_date","cutoff_date","prior_draws","actual_quintet","status"]+[f"rank_mask_{x:04d}" for x in range(1,FORMULAS+1)]
    parts=m.get("parts",[])
    if not parts: raise RuntimeError("Q7 walkforward parts missing")
    for part in parts:
        start=int(part["start_index"]); end=int(part["end_index_exclusive"]); path=Q7_ROOT/part["path"]
        if end<=start or end>len(draws) or sha256_file(path)!=part["sha256"]:
            raise RuntimeError(f"Q7 part range/hash mismatch: {path.name}")
        with path.open(newline="",encoding="utf-8") as f:
            reader=csv.reader(f)
            if next(reader,None)!=columns: raise RuntimeError(f"Q7 rank column order mismatch: {path.name}")
            count=0
            for row in reader:
                i=start+count
                if i>=end or len(row)!=len(columns): raise RuntimeError(f"Q7 row width/range mismatch: {path.name}")
                day,cutoff,prior,actual,status=row[:5]
                expected_day,expected_draw=draws[i]
                expected_cutoff=draws[i-1][0] if i else ""
                if day!=expected_day or cutoff!=expected_cutoff or int(prior)!=i or actual!=" ".join(map(str,expected_draw)):
                    raise RuntimeError(f"Q7 target/cutoff/source mismatch at index {i}")
                if i==0:
                    if status!="INSUFFICIENT_HISTORY" or any(row[5:]): raise RuntimeError("Q7 first target should be unscored")
                else:
                    if status!="SCORED": raise RuntimeError(f"Q7 target not scored: {day}")
                    v=np.asarray(row[5:],dtype=np.int32)
                    if v.shape!=(FORMULAS,) or np.any(v<1) or np.any(v>CANDIDATES):
                        raise RuntimeError(f"invalid one-based Q7 rank at {day}")
                    ranks[i]=v
                meta[i]={"target_date":day,"cutoff_date":cutoff,"prior_draws":i,"actual_quintet":actual,"status":status}
                count+=1
            if count!=end-start: raise RuntimeError(f"Q7 part row count mismatch: {path.name}")
    if any(x is None for x in meta) or np.any(ranks[1:]<0) or np.any(ranks[0]!=-1):
        raise RuntimeError("Q7 rank ledger incomplete")
    return ranks,meta,m

def split_sizes(n):
    d=int(round(n*.60)); v=int(round(n*.20)); b=n-d-v
    if min(d,v,b)<=0: raise ValueError("insufficient targets")
    return d,v,b

def select_formula_mask(ranks,target_index,window=WINDOW):
    if target_index<window+1: raise ValueError("not enough strictly prior scored targets")
    history=ranks[target_index-window:target_index]
    if history.shape!=(window,FORMULAS) or np.any(history<1) or np.any(history>CANDIDATES): raise ValueError("invalid prior rank window")
    return int(np.argmin(history.mean(axis=0))+1)

def holm_adjust(p):
    order=sorted(range(len(p)),key=lambda i:p[i]); out=[1.0]*len(p); running=0.0; m=len(p)
    for rank,i in enumerate(order):
        running=max(running,min(1.0,(m-rank)*float(p[i]))); out[i]=running
    return out

def block_signflip_p(values,block_length=BLOCK_LENGTH,replicates=SIGNFLIP_REPS,seed=SEED):
    x=np.asarray(values,dtype=np.float64)
    if x.ndim!=1 or len(x)<2 or not np.all(np.isfinite(x)): raise ValueError("invalid paired series")
    sums=np.asarray([x[i:i+block_length].sum() for i in range(0,len(x),block_length)])
    observed=float(x.mean()); k=len(sums)
    if k<=16:
        signs=np.asarray(list(itertools.product((-1.0,1.0),repeat=k)))
        null=signs@sums/len(x)
        return float(np.mean(null>=observed-1e-15)),k,f"exact_{2**k}_block_sign_flips"
    rng=np.random.default_rng(seed); signs=rng.choice(np.asarray([-1.0,1.0]),size=(replicates,k))
    null=signs@sums/len(x)
    return float((1+np.count_nonzero(null>=observed-1e-15))/(replicates+1)),k,f"monte_carlo_{replicates}_block_sign_flips"

def moving_block_ci(values,block_length=BLOCK_LENGTH,replicates=BOOTSTRAP_REPS,seed=SEED):
    x=np.asarray(values,dtype=np.float64); n=len(x)
    if x.ndim!=1 or n<2 or not np.all(np.isfinite(x)): raise ValueError("invalid bootstrap series")
    rng=np.random.default_rng(seed); samples=np.empty(replicates)
    sizes=[min(block_length,n-i) for i in range(0,n,block_length)]
    offsets=[np.arange(size) for size in sizes]
    for r in range(replicates):
        total=0.0
        for size,offset in zip(sizes,offsets):
            start=int(rng.integers(0,n)); total+=float(x[(start+offset)%n].sum())
        samples[r]=total/n
    lo,hi=np.quantile(samples,[.025,.975])
    return [float(lo),float(hi)]

def add_test(tests,split,comparison,endpoint,values,offset):
    p,k,method=block_signflip_p(values,seed=SEED+offset)
    ci=moving_block_ci(values,seed=SEED+10000+offset)
    tests.append({"id":f"{split}_{comparison}_{endpoint}","split":split,"comparison":comparison,
        "endpoint":endpoint,"targets":int(len(values)),"mean_effect":float(np.mean(values)),
        "ci95_moving_block":ci,"p_raw_one_sided":p,"block_length":BLOCK_LENGTH,
        "block_count":k,"sign_flip_method":method})

def summarize_split(name,positions,test_indices,ranks,masks,static_mask,fmap,tests,offset):
    idx=test_indices[positions]; selected=masks[positions]
    dyn=ranks[idx,selected-1].astype(np.float64); static=ranks[idx,static_mask-1].astype(np.float64)
    allr=ranks[idx].astype(np.float64); uniform=allr.mean(axis=1)
    u20=(allr<=20).mean(axis=1); u100=(allr<=100).mean(axis=1)
    d20=(dyn<=20).astype(float); d100=(dyn<=100).astype(float)
    dp=(uniform-dyn)/(CANDIDATES-1); d20e=d20-u20; d100e=d100-u100
    ds=(static-dyn)/(CANDIDATES-1)
    add_test(tests,name,"dynamic_vs_uniform_formula","percentile_gain",dp,offset+1)
    add_test(tests,name,"dynamic_vs_uniform_formula","top20_excess",d20e,offset+2)
    add_test(tests,name,"dynamic_vs_uniform_formula","top100_excess",d100e,offset+3)
    if name in ("validation","blind_oos"):
        add_test(tests,name,"dynamic_vs_discovery_static","percentile_gain",ds,offset+4)
    unique,counts=np.unique(selected,return_counts=True)
    chosen=sorted([{"formula_mask":int(m),"formula_id":fmap[int(m)]["formula_id"],
        "features":fmap[int(m)]["features"],"selected_targets":int(c)} for m,c in zip(unique,counts)],
        key=lambda z:(-z["selected_targets"],z["formula_mask"]))
    return {
      "targets":int(len(idx)),
      "dynamic_selector":{"mean_one_based_rank":float(dyn.mean()),
        "mean_percentile_score":float((1-(dyn-1)/(CANDIDATES-1)).mean()),
        "top20_count":int(d20.sum()),"top20_rate":float(d20.mean()),
        "top100_count":int(d100.sum()),"top100_rate":float(d100.mean()),
        "unique_formulas_selected":int(len(unique)),
        "formula_switches":int(np.count_nonzero(selected[1:]!=selected[:-1])),
        "top_selected_formulas":chosen[:10]},
      "uniform_formula_expectation":{"mean_one_based_rank":float(uniform.mean()),
        "mean_percentile_score":float((1-(uniform-1)/(CANDIDATES-1)).mean()),
        "expected_top20_hits":float(u20.sum()),"top20_rate":float(u20.mean()),
        "expected_top100_hits":float(u100.sum()),"top100_rate":float(u100.mean())},
      "discovery_static_formula":{"formula_mask":int(static_mask),"formula_id":fmap[static_mask]["formula_id"],
        "features":fmap[static_mask]["features"],"mean_one_based_rank":float(static.mean()),
        "mean_percentile_score":float((1-(static-1)/(CANDIDATES-1)).mean()),
        "top20_count":int(np.count_nonzero(static<=20)),"top20_rate":float(np.mean(static<=20)),
        "top100_count":int(np.count_nonzero(static<=100)),"top100_rate":float(np.mean(static<=100)),
        "selection_status":"in_sample_on_discovery" if name=="discovery" else "frozen_after_discovery"},
      "random_quintet_null":{"expected_one_based_rank":(CANDIDATES+1)/2,
        "expected_percentile_score":.5,"top20_probability":20/CANDIDATES,"top100_probability":100/CANDIDATES},
      "dynamic_minus_uniform_formula":{"mean_rank_improvement":float((uniform-dyn).mean()),
        "mean_percentile_gain":float(dp.mean()),"top20_excess":float(d20e.mean()),"top100_excess":float(d100e.mean())},
      "dynamic_minus_discovery_static":{"mean_rank_improvement":float((static-dyn).mean()),
        "mean_percentile_gain":float(ds.mean())}}

def run():
    q7_archive=Q7_ROOT/"data/storico_daily.csv"; q141_archive=ROOT/"data/storico_daily.csv"
    if git_blob_sha1(q141_archive)!=Q141_ARCHIVE_BLOB: raise RuntimeError("Q141 source archive blob mismatch")
    if git_blob_sha1(q7_archive)!=Q7_ARCHIVE_BLOB: raise RuntimeError("Q7 source archive blob mismatch")
    q7=read_archive(q7_archive); q141=read_archive(q141_archive)
    if len(q7)!=3387 or q7[-1][0]!="2026-10-24": raise RuntimeError("Q7 source boundary mismatch")
    if q141[:len(q7)]!=q7: raise RuntimeError("Q7 archive is not exact Q141 prefix")
    families,fmap=load_formula_catalog(); ranks,meta,wf=load_q7_rank_matrix(q7)
    targets=np.arange(WINDOW+1,len(q7),dtype=np.int32)
    if len(targets)!=3286: raise RuntimeError("eligible target count mismatch")
    dn,vn,bn=split_sizes(len(targets))
    if (dn,vn,bn)!=(1972,657,657): raise RuntimeError("split counts mismatch")
    splits={"discovery":np.arange(0,dn,dtype=np.int32),
        "validation":np.arange(dn,dn+vn,dtype=np.int32),
        "blind_oos":np.arange(dn+vn,len(targets),dtype=np.int32)}
    masks=np.empty(len(targets),dtype=np.int32); prior_means=np.empty(len(targets))
    for pos,t in enumerate(targets):
        m=select_formula_mask(ranks,int(t),WINDOW); masks[pos]=m
        prior_means[pos]=float(ranks[t-WINDOW:t,m-1].mean())
    static_mask=int(np.argmin(ranks[targets[splits["discovery"]]].mean(axis=0))+1)
    tests=[]; split_reports={}; split_labels=np.empty(len(targets),dtype=object)
    for name,pos in splits.items():
        split_labels[pos]=name
        split_reports[name]=summarize_split(name,pos,targets,ranks,masks,static_mask,fmap,tests,
            {"discovery":0,"validation":100,"blind_oos":200}[name])
    adjusted=holm_adjust([x["p_raw_one_sided"] for x in tests])
    for item,p in zip(tests,adjusted): item["p_holm_all_11_registered_tests"]=p
    ledger=[]
    for pos,t in enumerate(targets):
        m=int(masks[pos]); sr=int(ranks[t,m-1]); ur=float(ranks[t].mean()); st=int(ranks[t,static_mask-1])
        ledger.append({**meta[int(t)],"split":str(split_labels[pos]),"selected_formula_mask":m,
            "selected_formula_id":fmap[m]["formula_id"],"selected_formula_features":"|".join(fmap[m]["features"]),
            "selected_prior_100_mean_rank":float(prior_means[pos]),"selected_actual_quintet_rank_one_based":sr,
            "selected_percentile_score":float(1-(sr-1)/(CANDIDATES-1)),"uniform_formula_mean_rank":ur,
            "uniform_formula_top20_probability":float(np.mean(ranks[t]<=20)),
            "uniform_formula_top100_probability":float(np.mean(ranks[t]<=100)),
            "discovery_static_formula_id":fmap[static_mask]["formula_id"],
            "discovery_static_formula_rank_one_based":st,"dynamic_top20":int(sr<=20),"dynamic_top100":int(sr<=100),
            "static_top20":int(st<=20),"static_top100":int(st<=100),
            "delta_percentile_vs_uniform_formula":float((ur-sr)/(CANDIDATES-1)),
            "delta_top20_vs_uniform_formula":float((sr<=20)-np.mean(ranks[t]<=20)),
            "delta_top100_vs_uniform_formula":float((sr<=100)-np.mean(ranks[t]<=100)),
            "delta_percentile_vs_discovery_static":float((st-sr)/(CANDIDATES-1))})
    OUT.mkdir(parents=True,exist_ok=True)
    with LEDGER_PATH.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0].keys())); w.writeheader(); w.writerows(ledger)
    primary=next(x for x in tests if x["id"]=="blind_oos_dynamic_vs_uniform_formula_percentile_gain")
    decision="PERSISTENCE_SIGNAL_CANDIDATE_NOT_PROMOTED" if primary["p_holm_all_11_registered_tests"]<.05 and primary["mean_effect"]>=.005 else "NO_FORMULA_PERSISTENCE_LIFT_DEMONSTRATED"
    report={
      "schema_version":"1.0","task_id":TASK,"status":"COMPUTED","decision":decision,
      "hypothesis":"Selecting the Q7 quintet-scoring formula with the lowest mean exact quintet rank over the previous 100 scored targets improves the next target's normalized percentile rank versus uniform selection from the 1,023-formula grammar and versus a static Discovery-selected formula.",
      "primary_estimand":"Blind OOS mean normalized percentile gain versus the per-target mean rank of all 1,023 registered formulas.",
      "formula_universe":{"formula_count":FORMULAS,"candidate_quintet_count":CANDIDATES,
        "feature_family_count":len(families),"feature_families":families,
        "formula_selection":"argmin mean one-based exact quintet rank over previous 100 scored targets",
        "tie_break":"smallest integer formula_mask","mask_mapping":"rank_mask_MMMM maps to formula_id FMMMM; masks 1..1023"},
      "source":{"q7_repository_commit":Q7_COMMIT,"q7_archive_git_blob_sha1":Q7_ARCHIVE_BLOB,
        "q7_walkforward_manifest_git_blob_sha1":Q7_WF_MANIFEST_BLOB,
        "q7_catalog_manifest_git_blob_sha1":Q7_CATALOG_MANIFEST_BLOB,
        "q7_runner_git_blob_sha1":Q7_RUNNER_BLOB,"q141_archive_git_blob_sha1":Q141_ARCHIVE_BLOB,
        "q7_archive_draws":len(q7),"q7_archive_cutoff":q7[-1][0],
        "q7_archive_is_exact_prefix_of_q141_archive":True,
        "q141_rows_after_q7_prefix_not_used":len(q141)-len(q7),"contest_315_used":False},
      "walkforward":{"strict_prior":True,"rank_runner_order":"score target before adding target to state; pinned runner hash verified",
        "selector_window_scored_targets":WINDOW,"first_evaluated_target_index":WINDOW+1,
        "eligible_targets":len(targets),"split_counts":{"discovery":dn,"validation":vn,"blind_oos":bn},
        "target_outcome_use":"only to score the precomputed strict-prior rank; current target excluded from selector window",
        "discovery_static_formula":{"formula_mask":static_mask,"formula_id":fmap[static_mask]["formula_id"],
          "features":fmap[static_mask]["features"]},"split_metrics":split_reports},
      "statistical_inference":{"block_length":BLOCK_LENGTH,"block_sign_flip_replicates":SIGNFLIP_REPS,
        "moving_block_bootstrap_replicates":BOOTSTRAP_REPS,"seed":SEED,
        "method":"one-sided paired chronological block sign-flip; circular moving-block bootstrap CI",
        "correction":"Holm-Bonferroni across all 11 registered aggregate tests",
        "registered_test_count":len(tests),"tests":tests,"primary_blind_test":primary,
        "minimum_practical_percentile_gain":.005},
      "acceptance":{"all_1023_formula_masks_present":True,"all_3387_target_rows_reconciled":True,
        "all_34_walkforward_part_hashes_verified":len(wf["parts"]),
        "q7_source_prefix_matches_q141_source":True,"target_cutoffs_match_previous_archive_date":True,
        "strict_prior_runner_hash_verified":True,"selector_excludes_current_and_future_targets":True,
        "contest_315_excluded":True,"no_validation_or_blind_winner_selection":True,
        "all_registered_tests_holm_adjusted":True},
      "limitations":["Q7 is a quintet-scoring grammar, distinct from per-number Q80/Q90 ASTs.",
        "The selector searches 1,023 registered masks with a fixed rolling-100 rule; no current-target formula-specific p-values are computed.",
        "Uniform-formula baseline is the per-target expectation under uniform sampling from Q7 formula IDs, not a uniform random quintet forecast.",
        "Historical Blind OOS is exposed SONAR research history, not virgin prospective evidence.",
        "Holm controls the 11 registered aggregate tests, not the full Q00-Q141 research history.",
        "Q7 ends on 2026-10-24; later Q141 archive rows are not used."],
      "next_action":"Persist Q90's 59-feature matrix and 330,429-formula bundle as hash-pinned repository objects, then construct a separate per-number AST lineage before cross-granularity tests.",
      "governance":{"research_only":True,"no_merge":True,"no_engine_promotion":True,
        "no_shadow_insertion":True,"no_canonical_archive_mutation":True,"protected_prs":[6,7,8]}}
    REPORT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    manifest={"schema_version":"1.0","task_id":TASK,"status":"COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE",
        "source_q7_commit":Q7_COMMIT,"source_q7_archive_blob_sha1":Q7_ARCHIVE_BLOB,
        "source_q7_walkforward_manifest_blob_sha1":Q7_WF_MANIFEST_BLOB,
        "source_q7_runner_blob_sha1":Q7_RUNNER_BLOB,"source_q141_archive_blob_sha1":Q141_ARCHIVE_BLOB,
        "formula_count":FORMULAS,"candidate_quintets":CANDIDATES,"eligible_targets":len(targets),
        "split_counts":{"discovery":dn,"validation":vn,"blind_oos":bn},"files":{},
        "workflow_commit_sha":os.environ.get("GITHUB_SHA","")}
    for label,path in (("report",REPORT_PATH),("target_ledger",LEDGER_PATH)):
        manifest["files"][label]={"path":str(path.relative_to(ROOT)),"bytes":path.stat().st_size,
            "sha256":sha256_file(path),"git_blob_sha1":git_blob_sha1(path)}
    MANIFEST_PATH.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","task_id":TASK,"status":"COMPUTED_BUNDLE_READY_FOR_GIT_PERSISTENCE",
        "report_sha256":sha256_file(REPORT_PATH),"ledger_sha256":sha256_file(LEDGER_PATH),
        "manifest_sha256":sha256_file(MANIFEST_PATH),"decision":decision,
        "next_action":report["next_action"]}
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SONAR_Q141_B6_SUMMARY_BEGIN")
    print(json.dumps({"task_id":TASK,"status":report["status"],"decision":decision,
        "eligible_targets":len(targets),"split_counts":report["walkforward"]["split_counts"],
        "static_formula":report["walkforward"]["discovery_static_formula"],
        "blind_primary":primary,"report":str(REPORT_PATH.relative_to(ROOT)),
        "ledger":str(LEDGER_PATH.relative_to(ROOT)),"manifest":str(MANIFEST_PATH.relative_to(ROOT)),
        "checkpoint":str(CHECKPOINT_PATH.relative_to(ROOT))},ensure_ascii=False,separators=(",",":")))
    print("SONAR_Q141_B6_SUMMARY_END")
    return report

if __name__=="__main__":
    run()
