#!/usr/bin/env python3
"""Q141-D2: family-specific volatility-standardized relative advantage."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"
SRC=OUT/"q141_formula_family_behaviour_target_ledger_2026-11-12.csv"
PARENT=OUT/"q141_formula_family_behaviour_report_2026-11-12.json"
D1_REPORT=OUT/"q141_d1_standardized_family_advantage_report_2026-11-13.json"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
SCRIPT=ROOT/"scripts"/"sonar_q141_d2_family_volatility_standardization.py"
TEST=ROOT/"tests"/"test_sonar_q141_d2_family_volatility_standardization.py"
FAMILIES=("frequency_change","frequency_level","lag_memory","neighbour_field","position_dependence","recency_gap")
EXPECTED_LEDGER="4620ac88199256d90bf8e11a852206bfeb817812"
EXPECTED_ARCHIVE="fcb453ed06c8002314f826dbac79d6935f9ac103"
EXPECTED_PARENT="d559f939fc721119590cf84a72afc99fb6c36e0d"
EXPECTED_D1_REPORT="069a4ef826201bdc3e6af58414e7913c44778fa0"
SPLITS={"discovery":2013,"validation":671,"blind_oos":670}
N_TARGETS=3354; WINDOW=100; LAMBDA=0.25; BLOCK=20; REPS=20000; PRACTICAL=0.025; UNIFORM=0.625

def git_blob_sha(path:Path)->str:
    data=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()

def sha256(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mean(xs): return sum(xs)/len(xs) if xs else 0.0

def load_source(skip_archive_check=False):
    if git_blob_sha(SRC)!=EXPECTED_LEDGER: raise ValueError("pinned C0 ledger Git blob mismatch")
    if git_blob_sha(PARENT)!=EXPECTED_PARENT: raise ValueError("pinned C0 parent report Git blob mismatch")
    if git_blob_sha(D1_REPORT)!=EXPECTED_D1_REPORT: raise ValueError("pinned D1 report Git blob mismatch")
    parent=json.loads(PARENT.read_text(encoding="utf-8"))
    if parent["source"]["git_blob_sha1"]!=EXPECTED_ARCHIVE or parent["source"]["eligible_draw_count"]!=3404:
        raise ValueError("C0 archive lineage mismatch")
    if ARCHIVE.exists():
        if git_blob_sha(ARCHIVE)!=EXPECTED_ARCHIVE: raise ValueError("pinned archive Git blob mismatch")
        archive_check="VERIFIED_LOCAL"
    elif skip_archive_check:
        archive_check="NOT_RECHECKED_LOCAL_PARENT_AND_CI_ATTESTED"
    else: raise FileNotFoundError("canonical archive missing; only --skip-archive-check may be used for a local ledger-only replay")
    with SRC.open("r",encoding="utf-8-sig",newline="") as f: source=list(csv.DictReader(f))
    if len(source)!=N_TARGETS: raise ValueError(f"expected {N_TARGETS} targets, got {len(source)}")
    rows=[]; counts=Counter(); prev_index=None; prev_date=""
    for r in source:
        idx=int(r["target_index"]); date=r["target_date"]; cutoff=r["cutoff_date"]
        if cutoff>=date: raise ValueError(f"non-prior cutoff at target {idx}")
        if prev_index is not None and idx!=prev_index+1: raise ValueError("target index gap")
        if prev_date and date<=prev_date: raise ValueError("target dates not strictly chronological")
        prev_index=idx; prev_date=date; counts[r["split"]]+=1
        hits=[]; hits10=[]; hits20=[]; ranks=[]
        for fam in FAMILIES:
            h=float(r[f"{fam}_top5_hits"]); h10=float(r[f"{fam}_top10_hits"]); h20=float(r[f"{fam}_top20_hits"]); rank=float(r[f"{fam}_mean_actual_rank"])
            if not h.is_integer() or not 0<=h<=5: raise ValueError(f"invalid {fam} Top5 at {idx}")
            if not h10.is_integer() or not 0<=h10<=5: raise ValueError(f"invalid {fam} Top10 at {idx}")
            if not h20.is_integer() or not 0<=h20<=5: raise ValueError(f"invalid {fam} Top20 at {idx}")
            if not math.isfinite(rank): raise ValueError(f"invalid rank at {idx}")
            hits.append(int(h)); hits10.append(int(h10)); hits20.append(int(h20)); ranks.append(rank)
        rows.append({"index":idx,"offset":int(r["target_offset"]),"date":date,"cutoff":cutoff,"split":r["split"],
          "hits":hits,"hits10":hits10,"hits20":hits20,"ranks":ranks,"c0_family":r["selected_family"],
          "c0":int(float(r["dynamic_top5_hits"])),"c0_10":int(float(r["dynamic_top10_hits"])),"c0_20":int(float(r["dynamic_top20_hits"])),
          "c0_rank":float(r["dynamic_mean_actual_rank"]),"equal":int(float(r["equal_family_top5_hits"])),
          "equal10":int(float(r["equal_family_top10_hits"])),"equal20":int(float(r["equal_family_top20_hits"])),
          "equal_rank":float(r["equal_family_mean_actual_rank"])})
    if dict(counts)!=SPLITS: raise ValueError(f"split mismatch: {dict(counts)}")
    return rows,parent,archive_check

def d1_select(rows,t):
    if t<WINDOW: return None
    hist=rows[t-WINDOW:t]; sums=[0.0]*6; rank_sums=[0.0]*6
    for row in hist:
        center=mean(row["hits"]); var=mean([(x-center)**2 for x in row["hits"]]); denom=math.sqrt(var+LAMBDA*LAMBDA)
        for j in range(6): sums[j]+=(row["hits"][j]-center)/denom; rank_sums[j]+=row["ranks"][j]
    scores=[x/WINDOW for x in sums]; ranks=[x/WINDOW for x in rank_sums]
    return choose(scores,ranks)

def d2_scores(rows,t):
    if t<WINDOW: return None,None
    hist=rows[t-WINDOW:t]; residual=[[] for _ in FAMILIES]
    for row in hist:
        center=mean(row["hits"])
        for j in range(6): residual[j].append(row["hits"][j]-center)
    scores=[]; ranks=[]
    for j in range(6):
        mu=mean(residual[j]); var=mean([(x-mu)**2 for x in residual[j]])
        scores.append(mu/math.sqrt(var+LAMBDA*LAMBDA)); ranks.append(mean([r["ranks"][j] for r in hist]))
    return scores,ranks

def choose(scores,ranks):
    best=0
    for j in range(1,6):
        if scores[j]>scores[best]+1e-12: best=j
        elif abs(scores[j]-scores[best])<=1e-12:
            if ranks[j]<ranks[best]-1e-12: best=j
            elif abs(ranks[j]-ranks[best])<=1e-12 and FAMILIES[j]<FAMILIES[best]: best=j
    return best

def d2_select(rows,t):
    scores,ranks=d2_scores(rows,t)
    return None if scores is None else choose(scores,ranks)

def build_predictions(rows):
    out=[]
    for i,row in enumerate(rows):
        j1=d1_select(rows,i); j2=d2_select(rows,i)
        out.append({"d1_family":"WARMUP_EQUAL_FAMILY" if j1 is None else FAMILIES[j1],
          "d1_hits":row["equal"] if j1 is None else row["hits"][j1],
          "d2_family":"WARMUP_EQUAL_FAMILY" if j2 is None else FAMILIES[j2],
          "d2_hits":row["equal"] if j2 is None else row["hits"][j2],
          "d2_hits10":row["equal10"] if j2 is None else row["hits10"][j2],
          "d2_hits20":row["equal20"] if j2 is None else row["hits20"][j2],
          "d2_rank":row["equal_rank"] if j2 is None else row["ranks"][j2],
          "d2_scores":[] if j2 is None else d2_scores(rows,i)[0]})
    return out

def xorshift32(seed):
    state=seed&0xffffffff
    def draw():
        nonlocal state
        state^=(state<<13)&0xffffffff; state&=0xffffffff
        state^=state>>17; state&=0xffffffff
        state^=(state<<5)&0xffffffff; state&=0xffffffff
        return state/4294967296.0
    return draw

def quantile(values,p):
    ordered=sorted(values); pos=(len(ordered)-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
    return ordered[lo]+(ordered[hi]-ordered[lo])*(pos-lo)

def infer(d,seed):
    n=len(d); rng=xorshift32(seed); observed=mean(d); boot=[]
    for _ in range(REPS):
        total=0.0; count=0
        while count<n:
            start=int(rng()*n); take=min(BLOCK,n-count)
            for j in range(take): total+=d[(start+j)%n]
            count+=take
        boot.append(total/n)
    blocks=[sum(d[i:i+BLOCK]) for i in range(0,n,BLOCK)]; ge=0
    for _ in range(REPS):
        value=sum((-x if rng()<0.5 else x) for x in blocks)/n
        if value>=observed-1e-12: ge+=1
    return {"n":n,"mean":observed,"ci95":[quantile(boot,.025),quantile(boot,.975)],
      "bootstrap_replicates":REPS,"block_length":BLOCK,"signflip_replicates":REPS,
      "block_count":len(blocks),"p_one_sided":(ge+1)/(REPS+1)}

def holm(ps):
    order=sorted(enumerate(ps),key=lambda x:x[1]); out=[0.0]*len(ps); running=0.0
    for rank,(idx,p) in enumerate(order): running=max(running,min(1.0,(len(ps)-rank)*p)); out[idx]=running
    return out

def metric(rows,preds,split,key):
    ids=[i for i,r in enumerate(rows) if r["split"]==split]
    if key=="d2": return {"top5_mean_hits":mean([preds[i]["d2_hits"] for i in ids]),
      "top10_mean_hits":mean([preds[i]["d2_hits10"] for i in ids]),"top20_mean_hits":mean([preds[i]["d2_hits20"] for i in ids]),
      "mean_actual_rank":mean([preds[i]["d2_rank"] for i in ids])}
    if key=="d1": return {"top5_mean_hits":mean([preds[i]["d1_hits"] for i in ids])}
    if key=="c0": return {"top5_mean_hits":mean([rows[i]["c0"] for i in ids])}
    return {"top5_mean_hits":mean([rows[i]["equal"] for i in ids])}

def run(skip_archive_check=False):
    OUT.mkdir(parents=True,exist_ok=True)
    rows,parent,archive_check=load_source(skip_archive_check)
    preds=build_predictions(rows)
    if preds!=build_predictions(rows): raise ValueError("deterministic replay mismatch")
    leakage=[]
    for t in (100,101,500,2013,2684,3353):
        original=d2_select(rows,t); mutated=[dict(r) for r in rows]
        for i in range(t,len(mutated)):
            mutated[i]=dict(mutated[i]); mutated[i]["hits"]=[(v+1+j)%6 for j,v in enumerate(mutated[i]["hits"])]; mutated[i]["ranks"]=[v+17+j for j,v in enumerate(mutated[i]["ranks"])]
        if original!=d2_select(mutated,t): raise ValueError(f"future suffix changed selection at {t}")
        leakage.append({"target_offset":t,"selection_unchanged":True})
    splits={s:{"targets":sum(r["split"]==s for r in rows),"M3_D2_family_volatility":metric(rows,preds,s,"d2"),
      "M2_D1_target_standardized":metric(rows,preds,s,"d1"),"M1_C0_raw_rolling100":metric(rows,preds,s,"c0"),"M0_equal_family":metric(rows,preds,s,"equal"),
      "uniform_expected_top5_mean_hits":UNIFORM} for s in ("discovery","validation","blind_oos")}
    blind=[i for i,r in enumerate(rows) if r["split"]=="blind_oos"]
    comps=[("D2_minus_D1",[preds[i]["d2_hits"]-preds[i]["d1_hits"] for i in blind]),
      ("D2_minus_C0",[preds[i]["d2_hits"]-rows[i]["c0"] for i in blind]),
      ("D2_minus_equal",[preds[i]["d2_hits"]-rows[i]["equal"] for i in blind])]
    inference=[{"id":name,**infer(d,14111314+i)} for i,(name,d) in enumerate(comps)]
    adjusted=holm([x["p_one_sided"] for x in inference])
    for x,p in zip(inference,adjusted): x.update({"p_holm":p,"practical_threshold_met":x["mean"]>=PRACTICAL,
      "ci95_lower_positive":x["ci95"][0]>0,"holm_p_below_0_05":p<0.05})
    diagnostics={}
    for split in ("discovery","validation","blind_oos"):
        ids=[i for i,r in enumerate(rows) if r["split"]==split]; names=[preds[i]["d2_family"] for i in ids]
        counts=Counter(names); switches=sum(names[i]!=names[i-1] for i in range(1,len(names)))
        diagnostics[split]={"selected_counts":dict(sorted(counts.items())),"distinct":len(counts),"switches":switches,"switch_rate":switches/max(1,len(names)-1)}
    decision="HISTORICAL_GATE_MET_EXPLORATORY_ONLY" if all(x["practical_threshold_met"] and x["ci95_lower_positive"] and x["holm_p_below_0_05"] for x in inference) else "NO_FAMILY_VOLATILITY_STANDARDIZATION_LIFT_DEMONSTRATED"
    report={"schema_version":"1.0","task_id":"Q141-D2-FAMILY-VOLATILITY-STANDARDIZATION","status":"COMPLETED_HISTORICAL_EXPLORATORY",
      "decision":decision,"source":{"ledger_path":str(SRC.relative_to(ROOT)),"ledger_git_blob_sha1":git_blob_sha(SRC),
      "archive_path":"data/storico_daily.csv","archive_git_blob_sha1_expected":EXPECTED_ARCHIVE,"archive_check":archive_check,
      "parent_report_git_blob_sha1":git_blob_sha(PARENT),"d1_report_git_blob_sha1":git_blob_sha(D1_REPORT),
      "eligible_draws":3404,"archive_cutoff":"2026-11-10","target_count":len(rows),"parent_ci_run_id":43412187676},
      "design":{"families":list(FAMILIES),"window":WINDOW,"lambda":LAMBDA,"formula":"U_f,t = mean_{s=t-100..t-1}(h_f,s - mean_g h_g,s) / sqrt(var_{s=t-100..t-1}(h_f,s - mean_g h_g,s) + 0.25^2)",
      "strict_prior":True,"warmup":"first 100 scored targets use equal-family ranking","split_counts":SPLITS,
      "co_primary_endpoints":[x[0] for x in comps],"holm_family_size":3,"practical_threshold_mean_top5_hits":PRACTICAL,
      "uniform_expected_mean_top5_hits":UNIFORM,"bootstrap_replicates":REPS,"signflip_replicates":REPS,"block_length":BLOCK},
      "metrics_by_split":splits,"blind_oos_inference":inference,"selection_diagnostics":diagnostics,
      "integrity":{"source_ledger_blob_verified":True,"parent_report_blob_verified":True,"d1_report_blob_verified":True,
      "archive_blob_verified_in_parent_ci":True,"parent_ci_run_id":43412187676,"archive_check_local":archive_check,"target_count_verified":True,"split_counts_verified":True,
      "dates_strictly_chronological":True,"all_cutoffs_strictly_prior":True,"family_hit_counts_valid":True,"future_suffix_invariance":leakage,
      "deterministic_replay":True,"d1_replay_matches_pinned_report":abs(splits["blind_oos"]["M2_D1_target_standardized"]["top5_mean_hits"]-0.6194029850746269)<1e-12},
      "limitations":["Historical Blind OOS has already been exposed to prior SONAR research and is not virgin prospective confirmation.",
      "Six Q80-derived families are coarse and do not exhaust the typed Q141 formula universe.",
      "Endpoint is family-specific Top-5 coverage, not exact-quintet probability.",
      "Holm covers the three D2 endpoints only, not the full Q00-Q141 research family.",
      "This experiment remains pinned to the 3,404-draw source through 2026-11-10; later official draws are deliberately excluded from this historical replay.",
      "Local replay did not re-read the canonical archive bytes; archive lineage is pinned to the C0 report and verified by parent CI run 43412187676."],
      "next_action":"Keep D2 as historical exploratory only; complete typed Q90/Q7 AST lineage and common-source behaviour atlas; preserve Q60 and B11 freezes append-only."}
    ledger_path=OUT/"q141_d2_family_volatility_standardization_target_ledger_2026-11-13.csv"
    with ledger_path.open("w",encoding="utf-8",newline="") as f:
        w=csv.writer(f); w.writerow(["target_index","target_date","cutoff_date","split","d2_family","d2_top5_hits","d2_top10_hits","d2_top20_hits","d2_mean_actual_rank","d1_family","d1_top5_hits","c0_top5_hits","equal_family_top5_hits"])
        for r,p in zip(rows,preds): w.writerow([r["index"],r["date"],r["cutoff"],r["split"],p["d2_family"],p["d2_hits"],p["d2_hits10"],p["d2_hits20"],f"{p['d2_rank']:.10f}",p["d1_family"],p["d1_hits"],r["c0"],r["equal"]])
    report_path=OUT/"q141_d2_family_volatility_standardization_report_2026-11-13.json"
    report_path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    outputs={report_path.name:report_path,ledger_path.name:ledger_path,
      SCRIPT.name:SCRIPT,TEST.name:TEST}
    manifest={"schema_version":"1.0","task_id":"Q141-D2-FAMILY-VOLATILITY-STANDARDIZATION","status":"LOCAL_REPLAY_COMPLETE_REMOTE_READBACK_PENDING",
      "source_ledger_git_blob_sha1":EXPECTED_LEDGER,"archive_git_blob_sha1_expected":EXPECTED_ARCHIVE,"preregistration_git_blob_sha1":"d826cb27d2d1bf0387a61b0061d7f05784f771b3",
      "outputs":{name:{"bytes":path.stat().st_size,"sha256":sha256(path),"git_blob_sha1":git_blob_sha(path)} for name,path in outputs.items()}}
    manifest_path=OUT/"q141_d2_family_volatility_standardization_manifest_2026-11-13.json"
    manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    checkpoint={"schema_version":"1.0","task_id":"Q141-D2-FAMILY-VOLATILITY-STANDARDIZATION","status":"LOCAL_REPLAY_COMPLETE_REMOTE_READBACK_PENDING",
      "decision":decision,"report_path":str(report_path.relative_to(ROOT)),"ledger_path":str(ledger_path.relative_to(ROOT)),
      "manifest_path":str(manifest_path.relative_to(ROOT)),"next_action":report["next_action"],
      "governance":{"research_only":True,"canonical_archive_mutated":False,"active_engine_mutated":False,"engine_promoted":False,
      "q60_freeze_mutated":False,"b11_freeze_mutated":False,"protected_prs_6_7_8_untouched":True,"merge":False,"rebase":False}}
    checkpoint_path=OUT/"q141_d2_family_volatility_standardization_checkpoint_2026-11-13.json"
    checkpoint_path.write_text(json.dumps(checkpoint,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"decision":decision,"metrics_by_split":splits,"blind_oos_inference":inference,
      "selection_diagnostics":diagnostics,"ledger_rows":len(rows),"report":str(report_path),"ledger":str(ledger_path),
      "manifest":str(manifest_path),"checkpoint":str(checkpoint_path)},indent=2))
    return report

if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--skip-archive-check",action="store_true")
    args=parser.parse_args(); run(skip_archive_check=args.skip_archive_check)
