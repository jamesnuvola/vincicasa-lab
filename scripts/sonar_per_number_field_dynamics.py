#!/usr/bin/env python3
"""Q84 per-number field dynamics: causal 40-node, six-state walk-forward."""
from __future__ import annotations
import csv, gzip, hashlib, io, json, math, os
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
import numpy as np
import sonar_strategy_atlas as q84
import sonar_strategy_atlas_k_sensitivity as ksens
from sonar_sequence_agent import CONFIGS, MIN_HISTORY, read_draws, feature_scores

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"reports"/"sequence_agent"
ARCHIVE=ROOT/"data"/"storico_daily.csv"
PROTOCOL=OUT/"q84_per_number_field_protocol_2026-11-09.json"
CATALOG=OUT/"q84_per_number_field_catalog.jsonl"
LEDGER=OUT/"q84_per_number_field_target_ledger.csv.gz"
REPORT=OUT/"q84_per_number_field_report.json"
MANIFEST=OUT/"q84_per_number_field_manifest.json"
CHECKPOINT=OUT/"q84_per_number_field_checkpoint_2026-11-09.json"
VALIDATION=OUT/"q84_per_number_field_validation.json"

EQUAL_ID="BASE::EQUAL42"
FLOW_ID="BASE::FLOW_K50"
VARIANTS=("MOMENTUM","REVERSION","FLOW","GRAPH")
ALPHAS=(0.10,0.20,0.30)
FIELD_IDS=tuple(f"FIELD::{v}::A{int(round(a*100)):02d}" for v in VARIANTS for a in ALPHAS)
MODEL_IDS=(EQUAL_ID,FLOW_ID)+FIELD_IDS
SPLITS=("discovery","validation","blind_oos")
ENDPOINTS=(("top5",5),("top10",10),("top20",20))
EXPECTED_SHA1="77ca692a6082809fcc6c471501617433ec7c36cf"
EXPECTED_SHA256="5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b"
EXPECTED_DRAWS=3402
EXPECTED_LAST="2026-11-08"
EXPECTED_TARGETS=3202


def sha256_file(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""): h.update(block)
    return h.hexdigest()


def json_dump(path,obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,sort_keys=True)+"\n",encoding="utf-8")


def zscore(values):
    x=np.asarray(values,dtype=np.float64)
    sd=float(np.std(x))
    return np.zeros_like(x) if not np.isfinite(sd) or sd<1e-12 else (x-float(np.mean(x)))/sd


def pair_counts(draws):
    out=np.zeros((40,40),dtype=np.float64)
    for draw in draws:
        for a,b in combinations(draw["nums"],2):
            out[a-1,b-1]+=1.0
            out[b-1,a-1]+=1.0
    return out


def pair_residual_graph(history):
    recent=history[-80:]
    older=history[-400:-80] if len(history)>=400 else history[:-80]
    if len(recent)<40 or len(older)<80: return np.zeros((40,40),dtype=np.float64)
    p_pair=(5.0/40.0)*(4.0/39.0)
    pseudo=20.0
    r=(pair_counts(recent)+pseudo*p_pair)/(len(recent)+pseudo)
    o=(pair_counts(older)+pseudo*p_pair)/(len(older)+pseudo)
    edge=np.log((r+1e-12)/(o+1e-12))
    np.fill_diagonal(edge,0.0)
    return 0.5*(edge+edge.T)


def field_state(history):
    if len(history)<100: raise ValueError("field state requires at least 100 prior draws")
    rates=[]
    for width in (5,20,80):
        counts=np.zeros(40,dtype=np.float64)
        for draw in history[-width:]: counts[np.asarray(draw["nums"],dtype=int)-1]+=1
        rates.append(counts/float(width))
    z5,z20,z80=(zscore(x) for x in rates)
    last=np.full(40,-1,dtype=np.int64)
    for index in range(len(history)-1,-1,-1):
        for number in history[index]["nums"]:
            slot=int(number)-1
            if last[slot]<0: last[slot]=index
        if np.all(last>=0): break
    zgap=zscore(np.log1p((len(history)-1-last).astype(np.float64)))
    zv=zscore(z5-z20)
    za=zscore((z5-z20)-(z20-z80))
    momentum=zscore(.25*z5+.20*z20+.10*z80+.15*zv+.10*za-.20*zgap)
    reversion=zscore(-.25*z5-.20*z20-.10*z80-.15*zv-.10*za+.20*zgap)
    flow=zscore(.15*z5+.10*z20+.05*z80+.30*zv+.25*za-.15*zgap)
    edge=pair_residual_graph(history)
    graph_signal=zscore((edge@np.tanh(flow))/math.sqrt(39.0))
    graph=zscore(.70*flow+.30*graph_signal)
    features=np.column_stack([z5,z20,z80,zgap,zv,za])
    signature=hashlib.sha256(np.asarray(np.column_stack([features,graph_signal]),dtype="<f8").tobytes()).hexdigest()
    return {"features":features,"signals":{"MOMENTUM":momentum,"REVERSION":reversion,"FLOW":flow,"GRAPH":graph},
            "graph_signal":graph_signal,"signature":signature}


def field_state_for_target(draws,target_index):
    if target_index<=0 or target_index>len(draws): raise ValueError("invalid target prefix boundary")
    return field_state(draws[:target_index])


def rank_from_scores(scores):
    x=np.asarray(scores,dtype=np.float64)
    if x.shape!=(40,) or not np.isfinite(x).all(): raise ValueError("invalid 40-number score vector")
    order=np.lexsort((np.arange(1,41),-x))
    return q84.rank_vector_from_order((order+1).tolist())


def slug(model_id):
    return model_id.replace("::","_").lower()


def ledger_fields():
    fields=["target_date","cutoff_date","prior_draws","actual_quintet","split","flow_turbulence","flow_effective_n","field_state_sha256"]
    for model in MODEL_IDS: fields += [f"rank_{slug(model)}_{n:02d}" for n in range(1,41)]
    return fields


def exact_upper_tail(observed,targets,k):
    if targets<=0: return 1.0
    maximum=5*targets
    if observed<=0: return 1.0
    if observed>maximum: return 0.0
    denom=math.comb(40,5)
    pmf=np.zeros(6,dtype=np.float64)
    for x in range(6):
        if x<=k and 5-x<=40-k: pmf[x]=math.comb(k,x)*math.comb(40-k,5-x)/denom
    nfft=1
    while nfft<maximum+1: nfft<<=1
    spectrum=np.fft.rfft(pmf,n=nfft)
    dist=np.maximum(np.fft.irfft(spectrum**int(targets),n=nfft)[:maximum+1],0.0)
    mass=float(dist.sum())
    if not np.isfinite(mass) or mass<=0: raise ValueError("hypergeometric convolution lost mass")
    dist/=mass
    return float(np.clip(dist[int(observed):].sum(),0.0,1.0))


def compute_experiment(draws=None):
    draws=read_draws() if draws is None else draws
    dates=[d["date"].isoformat() for d in draws]
    if len(draws)!=EXPECTED_DRAWS or dates[-1]!=EXPECTED_LAST: raise ValueError("canonical archive count/date mismatch")
    total=len(draws)-MIN_HISTORY
    if total!=EXPECTED_TARGETS or len(CONFIGS)!=42: raise ValueError("unexpected target or Q84 rule count")
    ranks=np.empty((total,len(MODEL_IDS),40),dtype=np.int8)
    hits=np.empty((total,len(MODEL_IDS),3),dtype=np.int8)
    actual_ranks=np.empty((total,len(MODEL_IDS),5),dtype=np.int8)
    splits=[q84.split_name(i,total) for i in range(total)]
    split_counts=dict(Counter(splits))
    if split_counts!={"discovery":1921,"validation":640,"blind_oos":641}: raise ValueError("chronological split mismatch")
    states,prior_hits,prior_turb=[],[],[]
    signatures,turbulence,effective_n=[],[],[]
    for t,draw_index in enumerate(range(MIN_HISTORY,len(draws))):
        history=draws[:draw_index]
        target=draws[draw_index]
        state=q84.flow_state(history)
        context=ksens.flow_context_for_k(state,states,prior_hits,prior_turb,50)
        flow_weights,_,_,eff_n,turb,_,_,_,_=context
        base=feature_scores(history)
        fixed=np.empty((len(CONFIGS),40),dtype=np.int8)
        for s,config in enumerate(CONFIGS):
            fixed[s]=q84.rank_vector_from_order(q84.strategy_order(base,config))
        equal=q84.weighted_borda_rank(fixed,np.ones(len(CONFIGS),dtype=np.float64))
        flow_rank=q84.weighted_borda_rank(fixed,flow_weights)
        base_z=zscore(41.0-equal.astype(np.float64))
        field=field_state(history)
        candidate=[]
        for variant in VARIANTS:
            signal=zscore(field["signals"][variant])
            for alpha in ALPHAS: candidate.append(rank_from_scores(base_z+alpha*signal))
        current=np.vstack([equal,flow_rank]+candidate)
        actual=np.asarray(target["nums"],dtype=np.int16)
        fixed_hits=np.sum(fixed[:,actual-1]<=20,axis=1)
        if fixed_hits.shape!=(len(CONFIGS),): raise ValueError("Q84 flow memory must retain all 42 fixed-rule outcomes")
        ar=current[:,actual-1]
        hh=np.column_stack([np.sum(ar<=5,axis=1),np.sum(ar<=10,axis=1),np.sum(ar<=20,axis=1)]).astype(np.int8)
        ranks[t],hits[t],actual_ranks[t]=current,hh,ar
        signatures.append(field["signature"])
        turbulence.append(None if turb is None else float(turb))
        effective_n.append(float(eff_n))
        states.append(state)
        prior_hits.append(fixed_hits.astype(np.float64))
        prior_turb.append(turb)

    indices={s:np.asarray([i for i,x in enumerate(splits) if x==s],dtype=np.int64) for s in SPLITS}
    metrics,tests=[],[]
    for mi,model in enumerate(MODEL_IDS):
        for split in SPLITS:
            idx=indices[split]
            h=hits[idx,mi,:]; r=actual_ranks[idx,mi,:]; n=len(idx)
            row={"strategy_id":model,"split":split,"targets":n,
                 "mean_hits_top5":float(h[:,0].mean()),"mean_hits_top10":float(h[:,1].mean()),
                 "mean_hits_top20":float(h[:,2].mean()),"mean_rank_actual_numbers":float(r.mean()),
                 "top20_4plus":int(np.sum(h[:,2]>=4)),"top20_5of5":int(np.sum(h[:,2]==5)),
                 "top20_5of5_rate":float(np.mean(h[:,2]==5)),
                 "top20_hit_distribution":{str(k):int(np.sum(h[:,2]==k)) for k in range(6)},
                 "p_values_raw":{}}
            for j,(endpoint,k) in enumerate(ENDPOINTS):
                p=exact_upper_tail(int(h[:,j].sum()),n,k)
                test_id=f"FIELD|{model}|{split}|{endpoint}"
                tests.append({"test_id":test_id,"p_raw":p})
                row["p_values_raw"][endpoint]=p
            metrics.append(row)
    adjusted=q84.holm_adjust(tests)
    for row in metrics:
        row["p_values_holm"]={e:adjusted[f"FIELD|{row['strategy_id']}|{row['split']}|{e}"] for e,_ in ENDPOINTS}
    discovery=[r for r in metrics if r["split"]=="discovery" and r["strategy_id"] in FIELD_IDS]
    selected=sorted(discovery,key=lambda r:(-r["mean_hits_top20"],r["mean_rank_actual_numbers"],r["strategy_id"]))[0]
    selected_id=selected["strategy_id"]; selected_index=MODEL_IDS.index(selected_id)
    paired={}
    for split in ("validation","blind_oos"):
        idx=indices[split]; paired[split]={}
        for comparator,ci,seed in ((EQUAL_ID,0,8400),(FLOW_ID,1,8500)):
            details={}
            for j,(endpoint,_) in enumerate(ENDPOINTS):
                item=q84.bootstrap_paired(hits[idx,selected_index,j],hits[idx,ci,j],seed+j+(0 if split=="validation" else 100))
                item["positive_difference_favors_selected"]=True
                details[endpoint]=item
            rank_item=q84.bootstrap_paired(actual_ranks[idx,ci,:].mean(axis=1),actual_ranks[idx,selected_index,:].mean(axis=1),seed+3+(0 if split=="validation" else 100))
            rank_item["positive_difference_means_lower_selected_rank"]=True
            details["mean_actual_rank_improvement"]=rank_item
            paired[split]["selected_vs_"+comparator]=details
    return {"draws":draws,"dates":dates,"target_dates":dates[MIN_HISTORY:],"ranks":ranks,"hits":hits,
            "actual_ranks":actual_ranks,"splits":splits,"split_counts":split_counts,"indices":indices,
            "signatures":signatures,"turbulence":turbulence,"effective_n":effective_n,
            "metrics":metrics,"tests":tests,"selected_id":selected_id,"selected_row":selected,"paired":paired}


def catalog_entries():
    out=[{"strategy_id":EQUAL_ID,"kind":"BASELINE","definition":"Equal-weight Borda aggregation of 42 registered Q84 fixed rules."},
         {"strategy_id":FLOW_ID,"kind":"BASELINE","definition":"Q84 causal flow-state analogue ensemble, K=50; prior scored targets only."}]
    weights={
      "MOMENTUM":{"z5":.25,"z20":.20,"z80":.10,"zvelocity":.15,"zacceleration":.10,"minus_zgap":.20},
      "REVERSION":{"minus_z5":.25,"minus_z20":.20,"minus_z80":.10,"minus_zvelocity":.15,"minus_zacceleration":.10,"zgap":.20},
      "FLOW":{"z5":.15,"z20":.10,"z80":.05,"zvelocity":.30,"zacceleration":.25,"minus_zgap":.15},
      "GRAPH":{"0.70*FLOW":.70,"0.30*pair_graph_signal":.30}}
    for variant in VARIANTS:
        for alpha in ALPHAS:
            out.append({"strategy_id":f"FIELD::{variant}::A{int(round(alpha*100)):02d}","kind":"FIELD_CANDIDATE",
                "variant":variant,"alpha":alpha,"score":"z(41-equal42_Borda_rank)+alpha*z(field_variant)",
                "weights":weights[variant],"nodes":40,"features":["freq5","freq20","freq80","log_gap_age","velocity","acceleration"],
                "graph":"recent 80 vs prior up to 320; pseudo-count 20; symmetric 40x40; FLOW-weighted adjacency" if variant=="GRAPH" else None})
    return out


def write_outputs(result,sha1,sha256):
    with CATALOG.open("w",encoding="utf-8",newline="") as f:
        for item in catalog_entries(): f.write(json.dumps(item,sort_keys=True,separators=(",",":"))+"\n")
    with LEDGER.open("wb") as raw:
        with gzip.GzipFile(filename="",fileobj=raw,mode="wb",mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf-8",newline="") as f:
                writer=csv.DictWriter(f,fieldnames=ledger_fields()); writer.writeheader()
                for t,target_date in enumerate(result["target_dates"]):
                    i=MIN_HISTORY+t
                    row={"target_date":target_date,"cutoff_date":result["dates"][i-1],"prior_draws":i,
                         "actual_quintet":" ".join(map(str,result["draws"][i]["nums"])),"split":result["splits"][t],
                         "flow_turbulence":"" if result["turbulence"][t] is None else format(result["turbulence"][t],".12g"),
                         "flow_effective_n":format(result["effective_n"][t],".12g"),"field_state_sha256":result["signatures"][t]}
                    for mi,model in enumerate(MODEL_IDS):
                        for number,rank in enumerate(result["ranks"][t,mi],1): row[f"rank_{slug(model)}_{number:02d}"]=int(rank)
                    writer.writerow(row)
    report={"status":"COMPUTED_PENDING_ACCEPTANCE","task_id":"Q84-FIELD-DYNAMICS-01",
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "source_archive":{"draw_count":len(result["draws"]),"first_date":result["dates"][0],"last_date":result["dates"][-1],"git_blob_sha1":sha1,"sha256":sha256},
      "source_code_commit":os.environ.get("GITHUB_SHA","LOCAL_UNPINNED"),"target_count":len(result["target_dates"]),
      "split_counts":result["split_counts"],"models":list(MODEL_IDS),"selected_on_discovery_only":result["selected_id"],
      "selection_rule":"Discovery mean Top20 hits; tie lower mean actual rank then stable ID","metrics":result["metrics"],
      "multiple_testing":{"method":"global Holm-Bonferroni","family_size":len(result["tests"]),
        "raw_p_method":"discrete upper-tail convolution of iid Hypergeometric(40,k,5) hit counts"},
      "paired_block_bootstrap":result["paired"],"scope":"HISTORICAL_EXPLORATORY_NOT_PROSPECTIVE_CONFIRMATION",
      "primary_gate":{"minimum_blind_top20":2.5,"minimum_lift_vs_equal42":.10,"paired_ci_lower_bound_gt_zero":True,
        "global_holm_blind_top20_p_lt":.05,"status":"NOT_EVALUATED_UNTIL_VALIDATOR"},
      "limitations":["Historical Blind OOS is prior-exposed, not a virgin holdout.","Pair graph is a historical association descriptor, not physical coupling.",
        "Finite 12-operator grammar; not every possible function of the field.","Uniform independent 5-of-40 is a reference null, not proof of mechanism."],
      "next_action":"If no gain, diagnose node versus graph contributions and temporal stability before expanding operators; reserve new prospective targets for confirmation."}
    json_dump(REPORT,report)
    files={"catalog":{"path":str(CATALOG.relative_to(ROOT)),"sha256":sha256_file(CATALOG),"bytes":CATALOG.stat().st_size},
      "target_ledger":{"path":str(LEDGER.relative_to(ROOT)),"sha256":sha256_file(LEDGER),"bytes":LEDGER.stat().st_size,"rows":len(result["target_dates"])},
      "report":{"path":str(REPORT.relative_to(ROOT)),"sha256":sha256_file(REPORT),"bytes":REPORT.stat().st_size}}
    manifest={"status":"COMPUTED_PENDING_ACCEPTANCE","source_archive_git_blob_sha1":sha1,"source_archive_sha256":sha256,
      "target_count":len(result["target_dates"]),"split_counts":result["split_counts"],"model_count":len(MODEL_IDS),
      "field_candidate_count":len(FIELD_IDS),"rank_vectors":len(result["target_dates"])*len(MODEL_IDS),
      "holm_tests":len(result["tests"]),"ledger_fields":ledger_fields(),"files":files}
    json_dump(MANIFEST,manifest)
    json_dump(CHECKPOINT,{"checkpoint_id":"SONAR-Q84-FIELD-DYNAMICS-2026-11-09","status":"COMPUTED_PENDING_ACCEPTANCE",
      "source_archive_git_blob_sha1":sha1,"source_archive_sha256":sha256,"target_count":len(result["target_dates"]),
      "split_counts":result["split_counts"],"selected_on_discovery_only":result["selected_id"],
      "next_action":"Full replay acceptance, exact-byte persistence and exact-head CI; human review required."})


def main():
    for path in (CATALOG,LEDGER,REPORT,MANIFEST,CHECKPOINT,VALIDATION):
        if path.exists(): raise SystemExit("Q84_FIELD_BLOCKED: append-only output exists: "+str(path))
    protocol=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    raw=ARCHIVE.read_bytes(); sha256=hashlib.sha256(raw).hexdigest(); sha1=q84.git_blob_sha1(ARCHIVE)
    if sha1!=EXPECTED_SHA1 or sha256!=EXPECTED_SHA256: raise SystemExit("Q84_FIELD_BLOCKED: archive SHA mismatch")
    if protocol["source_archive"]["sha256"]!=sha256 or protocol["source_archive"]["git_blob_sha1"]!=sha1:
        raise SystemExit("Q84_FIELD_BLOCKED: protocol/archive identity mismatch")
    result=compute_experiment()
    write_outputs(result,sha1,sha256)
    summary={"status":"COMPUTED_PENDING_ACCEPTANCE","targets":len(result["target_dates"]),
      "splits":result["split_counts"],"models":len(MODEL_IDS),"field_candidates":len(FIELD_IDS),
      "holm_tests":len(result["tests"]),"selected_on_discovery_only":result["selected_id"],"archive_sha256":sha256}
    print("SONAR_Q84_FIELD_SUMMARY_BEGIN"); print(json.dumps(summary,sort_keys=True,separators=(",",":"))); print("SONAR_Q84_FIELD_SUMMARY_END")


if __name__=="__main__": main()
