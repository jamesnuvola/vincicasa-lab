#!/usr/bin/env python3
"""Q141-D1: target-standardized relative family-advantage selector."""
from __future__ import annotations
import csv, hashlib, json, math, subprocess
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"
SRC=OUT/"q141_formula_family_behaviour_target_ledger_2026-11-12.csv"
PARENT=OUT/"q141_formula_family_behaviour_report_2026-11-12.json"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
PREREG=OUT/"q141_d1_standardized_family_advantage_preregistration_2026-11-13.md"
LEDGER="q141_d1_standardized_family_advantage_target_ledger_2026-11-13.csv"
REPORT="q141_d1_standardized_family_advantage_report_2026-11-13.json"
MANIFEST="q141_d1_standardized_family_advantage_manifest_2026-11-13.json"
CHECKPOINT="q141_d1_standardized_family_advantage_checkpoint_2026-11-13.json"
CYCLE="q141_cycle_report_2026-11-13_run24.md"

FAMILIES=("frequency_change","frequency_level","lag_memory","neighbour_field","position_dependence","recency_gap")
EXPECTED={"ledger":"4620ac88199256d90bf8e11a852206bfeb817812",
          "archive":"fcb453ed06c8002314f826dbac79d6935f9ac103",
          "parent":"407be84fd8573fe7a12557dbca7b92990e3d04ab"}
SPLITS={"discovery":2013,"validation":671,"blind_oos":670}
N_TARGETS=3354
WINDOW=100
LAMBDA=0.25
BLOCK=20
REPS=20000
SEED=14111313
PRACTICAL=0.025
UNIFORM=0.625

def blob_sha(path):
    return subprocess.check_output(["git","hash-object",str(path)],text=True).strip()

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def mean(values):
    return sum(values)/len(values) if values else 0.0

def load_source():
    for name,path in (("ledger",SRC),("archive",ARCHIVE),("parent",PARENT)):
        if blob_sha(path)!=EXPECTED[name]:
            raise ValueError(f"pinned {name} Git blob mismatch")
    parent=json.loads(PARENT.read_text(encoding="utf-8"))
    if parent["source"]["git_blob_sha1"]!=EXPECTED["archive"] or parent["source"]["eligible_draw_count"]!=3404:
        raise ValueError("Q141-C0 parent archive lineage mismatch")
    if not PREREG.exists():
        raise ValueError("D1 preregistration missing")
    with SRC.open("r",encoding="utf-8-sig",newline="") as f:
        source=list(csv.DictReader(f))
    if len(source)!=N_TARGETS:
        raise ValueError(f"expected {N_TARGETS} targets, got {len(source)}")
    rows=[]; counts=Counter(); prev_index=None; prev_date=""
    for r in source:
        index=int(r["target_index"]); date=r["target_date"]; cutoff=r["cutoff_date"]
        if cutoff>=date: raise ValueError(f"non-prior cutoff at {index}")
        if prev_index is not None and index!=prev_index+1: raise ValueError("target index gap")
        if prev_date and date<=prev_date: raise ValueError("target dates not strictly chronological")
        prev_index=index; prev_date=date; counts[r["split"]]+=1
        hits=[]; hits10=[]; hits20=[]; ranks=[]
        for family in FAMILIES:
            h=float(r[f"{family}_top5_hits"]); h10=float(r[f"{family}_top10_hits"]); h20=float(r[f"{family}_top20_hits"])
            rank=float(r[f"{family}_mean_actual_rank"])
            if not h.is_integer() or not 0<=h<=5: raise ValueError(f"invalid {family} Top5 at {index}")
            if not h10.is_integer() or not 0<=h10<=5: raise ValueError(f"invalid {family} Top10 at {index}")
            if not h20.is_integer() or not 0<=h20<=5: raise ValueError(f"invalid {family} Top20 at {index}")
            if not math.isfinite(rank): raise ValueError(f"invalid rank at {index}")
            hits.append(int(h)); hits10.append(int(h10)); hits20.append(int(h20)); ranks.append(rank)
        rows.append({"index":index,"offset":int(r["target_offset"]),"date":date,"cutoff":cutoff,
            "prior":int(r["prior_draws"]),"split":r["split"],"hits":hits,"hits10":hits10,
            "hits20":hits20,"ranks":ranks,"c0_family":r["selected_family"],
            "c0":int(float(r["dynamic_top5_hits"])),"c0_10":int(float(r["dynamic_top10_hits"])),
            "c0_20":int(float(r["dynamic_top20_hits"])),"c0_rank":float(r["dynamic_mean_actual_rank"]),
            "equal":int(float(r["equal_family_top5_hits"])),"equal10":int(float(r["equal_family_top10_hits"])),
            "equal20":int(float(r["equal_family_top20_hits"])),"equal_rank":float(r["equal_family_mean_actual_rank"])})
    if dict(counts)!=SPLITS: raise ValueError(f"split mismatch: {dict(counts)}")
    return rows

def standardized_scores(history):
    if len(history)!=WINDOW: raise ValueError("exactly 100 prior rows required")
    sums=[0.0]*6; rank_sums=[0.0]*6
    for row in history:
        h=row["hits"]; center=mean(h); variance=mean([(x-center)**2 for x in h])
        denom=math.sqrt(variance+LAMBDA*LAMBDA)
        for j in range(6):
            sums[j]+=(h[j]-center)/denom; rank_sums[j]+=row["ranks"][j]
    return [x/WINDOW for x in sums],[x/WINDOW for x in rank_sums]

def select_family(rows,target_offset):
    if target_offset<WINDOW: return None,None,None
    scores,ranks=standardized_scores(rows[target_offset-WINDOW:target_offset]); best=0
    for j in range(1,6):
        if scores[j]>scores[best]+1e-12: best=j
        elif abs(scores[j]-scores[best])<=1e-12:
            if ranks[j]<ranks[best]-1e-12: best=j
            elif abs(ranks[j]-ranks[best])<=1e-12 and FAMILIES[j]<FAMILIES[best]: best=j
    return best,scores,ranks

def build_predictions(rows):
    out=[]
    for i,row in enumerate(rows):
        j,scores,ranks=select_family(rows,i)
        if j is None:
            out.append({"family":"WARMUP_EQUAL_FAMILY","mode":"equal_family_warmup","h":row["equal"],
                "h10":row["equal10"],"h20":row["equal20"],"rank":row["equal_rank"],"scores":"","ranks":""})
        else:
            out.append({"family":FAMILIES[j],"mode":"standardized_relative_advantage","h":row["hits"][j],
                "h10":row["hits10"][j],"h20":row["hits20"][j],"rank":row["ranks"][j],
                "scores":json.dumps({FAMILIES[k]:round(scores[k],12) for k in range(6)},sort_keys=True,separators=(",",":")),
                "ranks":json.dumps({FAMILIES[k]:round(ranks[k],12) for k in range(6)},sort_keys=True,separators=(",",":"))})
    return out

def metrics(rows,preds,which):
    if which=="d1":
        hs=[p["h"] for p in preds]; h10=[p["h10"] for p in preds]; h20=[p["h20"] for p in preds]; ranks=[p["rank"] for p in preds]
    elif which=="c0":
        hs=[r["c0"] for r in rows]; h10=[r["c0_10"] for r in rows]; h20=[r["c0_20"] for r in rows]; ranks=[r["c0_rank"] for r in rows]
    else:
        hs=[r["equal"] for r in rows]; h10=[r["equal10"] for r in rows]; h20=[r["equal20"] for r in rows]; ranks=[r["equal_rank"] for r in rows]
    m=mean(hs)
    return {"top5_mean_hits":m,"top5_hit_share":m/5.0,"top10_mean_hits":mean(h10),
            "top20_mean_hits":mean(h20),"mean_actual_rank":mean(ranks)}

def xorshift32(seed):
    state=seed&0xffffffff
    def draw():
        nonlocal state
        state^=(state<<13)&0xffffffff; state^=state>>17; state^=(state<<5)&0xffffffff
        state&=0xffffffff
        return state/4294967296.0
    return draw

def quantile(values,p):
    ordered=sorted(values); pos=(len(ordered)-1)*p; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
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
    for rank,(idx,p) in enumerate(order):
        running=max(running,min(1.0,(len(ps)-rank)*p)); out[idx]=running
    return out

def run():
    OUT.mkdir(parents=True,exist_ok=True); rows=load_source(); preds=build_predictions(rows)
    if preds!=build_predictions(rows): raise ValueError("deterministic replay mismatch")
    leakage=[]
    for t in (100,101,500,2013,2684,3353):
        original=select_family(rows,t)[0]; mutated=[dict(r) for r in rows]
        for i in range(t,len(mutated)):
            mutated[i]=dict(mutated[i])
            mutated[i]["hits"]=[(v+1+j)%6 for j,v in enumerate(mutated[i]["hits"])]
            mutated[i]["ranks"]=[v+17+j for j,v in enumerate(mutated[i]["ranks"])]
        if original!=select_family(mutated,t)[0]: raise ValueError(f"future suffix changed selection at {t}")
        leakage.append({"target_offset":t,"selection_unchanged":True})
    by_split={}
    for split in ("discovery","validation","blind_oos"):
        pairs=[(r,p) for r,p in zip(rows,preds) if r["split"]==split]; rr=[x[0] for x in pairs]; pp=[x[1] for x in pairs]
        by_split[split]={"targets":len(rr),"M2_D1":metrics(rr,pp,"d1"),
            "M1_C0_raw_rolling100":metrics(rr,pp,"c0"),"M0_equal_family":metrics(rr,pp,"equal"),
            "uniform_expected_top5_mean_hits":UNIFORM}
    blind=[(r,p) for r,p in zip(rows,preds) if r["split"]=="blind_oos"]
    inference=[{"id":"M2_minus_M1",**infer([p["h"]-r["c0"] for r,p in blind],SEED)},
               {"id":"M2_minus_M0",**infer([p["h"]-r["equal"] for r,p in blind],SEED+1)}]
    adjusted=holm([x["p_one_sided"] for x in inference])
    for x,padj in zip(inference,adjusted):
        x.update({"p_holm":padj,"practical_threshold_met":x["mean"]>=PRACTICAL,
                  "ci95_lower_positive":x["ci95"][0]>0,"holm_p_below_0_05":padj<0.05})
    selected={}
    for split in ("discovery","validation","blind_oos"):
        names=[p["family"] for r,p in zip(rows,preds) if r["split"]==split]; counts=Counter(names)
        switches=sum(names[i]!=names[i-1] for i in range(1,len(names)))
        selected[split]={"selected_counts":dict(sorted(counts.items())),"distinct":len(counts),
                         "switches":switches,"switch_rate":switches/(len(names)-1)}
    gate=all(x["practical_threshold_met"] and x["ci95_lower_positive"] and x["holm_p_below_0_05"] for x in inference)
    decision="HISTORICAL_GATE_MET_EXPLORATORY_ONLY" if gate else "NO_STANDARDIZED_FAMILY_ADVANTAGE_LIFT_DEMONSTRATED"
    report={"schema_version":"1.0","task_id":"Q141-D1-STANDARDIZED-FAMILY-ADVANTAGE",
      "status":"COMPLETED_HISTORICAL_EXPLORATORY","decision":decision,
      "source":{"target_ledger_path":str(SRC.relative_to(ROOT)),"target_ledger_git_blob_sha1":EXPECTED["ledger"],
        "archive_path":"data/storico_daily.csv","archive_git_blob_sha1":EXPECTED["archive"],
        "parent_report_git_blob_sha1":EXPECTED["parent"],"eligible_draws":3404,"archive_cutoff":"2026-11-10","target_count":len(rows)},
      "design":{"families":list(FAMILIES),"rolling_window":WINDOW,"scale_floor_lambda":LAMBDA,
        "standardization":"(family_top5_hits - same_target_mean_across_six_families) / sqrt(same_target_population_variance + lambda^2)",
        "warmup":"first 100 scored targets use existing equal-family ranking",
        "tie_break":"highest rolling mean standardized relative advantage; then lowest rolling mean actual-number rank; then lexicographic family id",
        "strict_prior":True,"split_counts":SPLITS,"co_primary_endpoints":["M2_minus_M1","M2_minus_M0"],
        "practical_threshold_mean_top5_hits":PRACTICAL,"uniform_expected_mean_top5_hits":UNIFORM,
        "bootstrap_replicates":REPS,"signflip_replicates":REPS,"block_length":BLOCK,"holm_family_size":2},
      "metrics_by_split":by_split,"blind_oos_inference":inference,"selection_diagnostics":selected,
      "integrity":{"source_ledger_blob_verified":True,"archive_blob_verified":True,"parent_report_blob_verified":True,
        "target_count_verified":True,"split_counts_verified":True,"target_indices_consecutive":True,
        "dates_strictly_chronological":True,"all_cutoffs_strictly_prior":True,"family_hit_counts_valid":True,
        "future_suffix_invariance":leakage,"deterministic_replay":True},
      "limitations":["Historical Blind OOS is exposed to prior SONAR research and is not virgin prospective confirmation.",
        "The six Q80-derived families are coarse and do not exhaust Q141's typed formula universe.",
        "The endpoint is family-specific Top-5 coverage, not a calibrated exact-quintet probability.",
        "The fixed 100-target window and lambda=0.25 are not tuned here; standardization may still amplify noise.",
        "Holm covers the two registered D1 endpoints, not the full Q00-Q141 research family.",
        "No prospective outcome, Q60 freeze, canonical archive, active engine or existing forecast was changed."],
      "governance":{"research_only":True,"canonical_archive_mutated":False,"active_engine_mutated":False,
        "q60_freeze_mutated":False,"shadow_forecasts_mutated":False,"engine_promoted":False,
        "merge":False,"rebase":False,"protected_prs_6_7_8_untouched":True},
      "next_action":"Keep D1 as a recorded historical null; do not tune the scale floor or rolling window on this Blind OOS. Continue Q141 typed-registry lineage work and preserve Q60 append-only prospective freezes."}
    ledger_path=OUT/LEDGER
    fields=["target_index","target_date","cutoff_date","prior_draws","split","d1_selected_family","d1_selector_mode",
      "d1_top5_hits","d1_top10_hits","d1_top20_hits","d1_mean_actual_rank","d1_family_scores_json",
      "d1_family_rank_tiebreak_json","c0_selected_family","c0_top5_hits","equal_family_top5_hits"]
    with ledger_path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n"); w.writeheader()
        for r,p in zip(rows,preds):
            w.writerow({"target_index":r["index"],"target_date":r["date"],"cutoff_date":r["cutoff"],
              "prior_draws":r["prior"],"split":r["split"],"d1_selected_family":p["family"],
              "d1_selector_mode":p["mode"],"d1_top5_hits":p["h"],"d1_top10_hits":p["h10"],
              "d1_top20_hits":p["h20"],"d1_mean_actual_rank":f'{p["rank"]:.12f}',
              "d1_family_scores_json":p["scores"],"d1_family_rank_tiebreak_json":p["ranks"],
              "c0_selected_family":r["c0_family"],"c0_top5_hits":r["c0"],"equal_family_top5_hits":r["equal"]})
    rp=OUT/REPORT; rp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    prereg=PREREG.read_bytes(); sp=Path(__file__).resolve()
    manifest={"schema_version":"1.0","task_id":report["task_id"],"status":"ARTIFACTS_WRITTEN_LOCAL_READBACK_PENDING",
      "source_ledger_git_blob_sha1":EXPECTED["ledger"],"archive_git_blob_sha1":EXPECTED["archive"],
      "preregistration_git_blob_sha1":hashlib.sha1(f"blob {len(prereg)}\0".encode()+prereg).hexdigest(),
      "script_git_blob_sha1":blob_sha(sp),"script_sha256":sha256(sp),"outputs":{}}
    for path in (rp,ledger_path):
        raw=path.read_bytes()
        manifest["outputs"][path.name]={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
          "git_blob_sha1":hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()}
    mp=OUT/MANIFEST; mp.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    cp=OUT/CHECKPOINT
    cp.write_text(json.dumps({"schema_version":"1.0","task_id":report["task_id"],
      "status":"ARTIFACTS_WRITTEN_LOCAL_READBACK_PENDING","decision":decision,
      "report_path":str(rp.relative_to(ROOT)),"ledger_path":str(ledger_path.relative_to(ROOT)),
      "manifest_path":str(mp.relative_to(ROOT)),"preregistration_path":str(PREREG.relative_to(ROOT)),
      "next_action":report["next_action"],"governance":report["governance"]},indent=2,sort_keys=True)+"\n",encoding="utf-8")
    cycle="# VinciCasa SONAR — ciclo 24: Q141-D1\n\n"
    cycle+=f"Decisione: **{decision}**. Target: 3,354 (Discovery 2,013; Validation 671; Blind OOS 670).\n\n## Blind OOS\n"
    for x in inference:
        cycle+=f"- {x['id']}: {x['mean']:.8f} hit/target; IC95% [{x['ci95'][0]:.8f}, {x['ci95'][1]:.8f}]; p grezzo {x['p_one_sided']:.6f}; Holm {x['p_holm']:.6f}.\n"
    cycle+="\n## Limiti\n- Blind OOS storico già esposto alla ricerca SONAR; non è conferma prospettica vergine.\n- Endpoint = copertura Top-5 della famiglia, non probabilità di cinquina esatta.\n- Nessuna modifica a Q60, archivio canonico, motore attivo o forecast prospettici.\n\n## Prossima azione\nConservare il risultato senza rituning; proseguire il lineage AST Q90/Q7 e le freeze prospettiche append-only.\n"
    (OUT/CYCLE).write_text(cycle,encoding="utf-8")
    print(json.dumps({"decision":decision,"metrics_by_split":by_split,"blind_oos_inference":inference,
      "selection_diagnostics":selected,"report":str(rp),"ledger":str(ledger_path)},indent=2,sort_keys=True))
    return report

if __name__=="__main__": run()
