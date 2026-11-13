#!/usr/bin/env python3
"""Q142 exact family-wise audit of the existing 42-rule strict-prior ledger."""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from collections import defaultdict
from pathlib import Path

LEDGER_BLOB = "472d6b094c4d533412207baa5cbdc8d9bd43e89e"
ARCHIVE_BLOB = "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb"
EXPECTED_DRAWS, EXPECTED_TARGETS, EXPECTED_RULES, WARMUP = 3406, 3206, 42, 200

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def git_blob_sha1(data):
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()

def parse_numbers(value, n, sorted_values=False):
    xs = tuple(int(x) for x in value.strip().split())
    if len(xs) != n or len(set(xs)) != n or any(x < 1 or x > 40 for x in xs):
        raise ValueError(f"invalid {n}-number set: {value!r}")
    if sorted_values and tuple(sorted(xs)) != xs:
        raise ValueError(f"numbers not ascending: {value!r}")
    return xs

def validate_row(row, prior_date, actual):
    if row["history_cutoff"] != prior_date:
        raise ValueError(f"wrong cutoff at {row['target_date']}")
    if parse_numbers(row["actual_numbers"], 5, True) != actual:
        raise ValueError(f"wrong actual at {row['target_date']}")
    top20 = parse_numbers(row["top20"], 20)
    hits = len(set(top20) & set(actual))
    if int(row["hit_count"]) != hits or int(row["all5_top20"]) != int(hits == 5):
        raise ValueError(f"hit-count mismatch at {row['target_date']}/{row['config_id']}")
    if row["evaluation_mode"] != "RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW":
        raise ValueError("unexpected evaluation mode")
    return hits

def log_choose(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)

def binomial_tail(n, k, p):
    if k <= 0: return 1.0
    if k > n: return 0.0
    lp, lq = math.log(p), math.log1p(-p)
    terms = [log_choose(n,j) + j*lp + (n-j)*lq for j in range(k,n+1)]
    m = max(terms)
    return min(1.0, math.exp(m) * math.fsum(math.exp(x-m) for x in terms))

def holm(items):
    order = sorted(range(len(items)), key=lambda i:(items[i]["p_raw"],i))
    out, running, m = [1.0]*len(items), 0.0, len(items)
    for rank, i in enumerate(order):
        running = max(running, min(1.0,(m-rank)*items[i]["p_raw"]))
        out[i] = running
    return [dict(x,p_holm=out[i]) for i,x in enumerate(items)]

def split_bounds(n):
    return int(n*0.60), int(n*0.80)

def ranks(xs):
    order=sorted(range(len(xs)),key=lambda i:xs[i]); out=[0.0]*len(xs); i=0
    while i<len(order):
        j=i+1
        while j<len(order) and xs[order[j]]==xs[order[i]]: j+=1
        r=((i+1)+j)/2
        for k in range(i,j): out[order[k]]=r
        i=j
    return out

def spearman(a,b):
    x,y=ranks(a),ranks(b); mx=sum(x)/len(x); my=sum(y)/len(y)
    num=sum((u-mx)*(v-my) for u,v in zip(x,y))
    dx=sum((u-mx)**2 for u in x); dy=sum((v-my)**2 for v in y)
    return num/math.sqrt(dx*dy) if dx and dy else 0.0

def run(root):
    ap=root/"data/storico_daily.csv"; lp=root/"reports/sequence_agent/historical_rule_ledger.csv"
    ab,lb=ap.read_bytes(),lp.read_bytes()
    if git_blob_sha1(ab)!=ARCHIVE_BLOB: raise ValueError("archive blob SHA mismatch")
    if git_blob_sha1(lb)!=LEDGER_BLOB: raise ValueError("ledger blob SHA mismatch")
    archive_dates=[]; draws={}
    with ap.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d=r["data"]; q=tuple(int(r[f"n{i}"]) for i in range(1,6))
            if tuple(sorted(q))!=q or len(set(q))!=5: raise ValueError("bad archive draw")
            archive_dates.append(d); draws[d]=q
    if len(archive_dates)!=EXPECTED_DRAWS or archive_dates!=sorted(archive_dates) or len(set(archive_dates))!=len(archive_dates): raise ValueError("archive row count/order mismatch")
    archive_index={d:i for i,d in enumerate(archive_dates)}
    bydate=defaultdict(list); configs=set()
    with lp.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d=r["target_date"]
            if d not in draws: raise ValueError("target missing from archive")
            pos=archive_index[d]
            if pos<WARMUP: raise ValueError("insufficient prior history")
            r["_hits"]=str(validate_row(r,archive_dates[pos-1],draws[d]))
            bydate[d].append(r); configs.add(r["config_id"])
    dates=sorted(bydate); expected=archive_dates[WARMUP:]; cfg=sorted(configs)
    if dates!=expected or len(dates)!=EXPECTED_TARGETS: raise ValueError("target suffix mismatch")
    if len(cfg)!=EXPECTED_RULES: raise ValueError("rule count mismatch")
    for d in dates:
        rr=bydate[d]
        if len(rr)!=EXPECTED_RULES or sorted(r["config_id"] for r in rr)!=cfg: raise ValueError(f"incomplete rule rows at {d}")
        if len({r["history_cutoff"] for r in rr})!=1 or len({r["actual_numbers"] for r in rr})!=1: raise ValueError("target alignment mismatch")
    n=len(dates); c1,c2=split_bounds(n)
    splits=[("discovery",0,c1),("validation",c1,c2),("blind_oos_historical",c2,n)]
    p5=math.comb(20,5)/math.comb(40,5)
    p4=(math.comb(20,4)*math.comb(20,1)+math.comb(20,5))/math.comb(40,5)
    tests=[]; stats={}; ensemble={}; any5=set()
    for name,start,end in splits:
        ds=dates[start:end]; ss={}
        for cid in cfg:
            hh=[int(next(r for r in bydate[d] if r["config_id"]==cid)["_hits"]) for d in ds]
            f5=sum(x==5 for x in hh); f4=sum(x>=4 for x in hh)
            ss[cid]={"n":len(ds),"five_count":f5,"fourplus_count":f4,"five_rate":f5/len(ds),
                     "fourplus_rate":f4/len(ds),"mean_top20_hits":sum(hh)/len(ds)}
            tests.append({"split":name,"endpoint":"5of5","config_id":cid,"n":len(ds),"count":f5,"p_raw":binomial_tail(len(ds),f5,p5)})
            tests.append({"split":name,"endpoint":"4plus","config_id":cid,"n":len(ds),"count":f4,"p_raw":binomial_tail(len(ds),f4,p4)})
        for d in ds:
            rr=bydate[d]; ensemble[d]=sum(int(r["_hits"]) for r in rr)/EXPECTED_RULES
            if any(int(r["all5_top20"])==1 for r in rr): any5.add(d)
        stats[name]={"n":len(ds),"first":ds[0],"last":ds[-1],
                     "ensemble_mean_top20_hits":sum(ensemble[d] for d in ds)/len(ds),"config":ss}
    adj=holm(tests); lookup={(x["split"],x["endpoint"],x["config_id"]):x for x in adj}
    for name,_,_ in splits:
        for cid in cfg:
            z=stats[name]["config"][cid]
            for ep,key in [("5of5","5"),("4plus","4")]:
                t=lookup[(name,ep,cid)]; z[f"p{key}_raw"]=t["p_raw"]; z[f"p{key}_holm"]=t["p_holm"]
    winner=sorted(cfg,key=lambda c:(-stats["discovery"]["config"][c]["five_count"],c))[0]
    winner_split={name:{"config_id":winner,**stats[name]["config"][winner]} for name,_,_ in splits}
    corr={}
    for a,b in [("discovery","validation"),("discovery","blind_oos_historical"),("validation","blind_oos_historical")]:
        corr[f"{a}_vs_{b}"]=spearman([stats[a]["config"][c]["five_rate"] for c in cfg],
                                     [stats[b]["config"][c]["five_rate"] for c in cfg])
    sig=[x for x in adj if x["p_holm"]<0.05]
    best=min(adj,key=lambda x:x["p_raw"])
    pvals={name:{ep:min((x for x in adj if x["split"]==name and x["endpoint"]==ep),key=lambda x:x["p_raw"])
                 for ep in ("5of5","4plus")} for name,_,_ in splits}
    decision="FWER_CONTROLLED_EXCESS_DETECTED" if sig else "NO_FWER_CONTROLLED_EXCESS_DEMONSTRATED"
    report={
      "task_id":"Q142","status":"COMPLETED_HISTORICAL_WALK_FORWARD_AUDIT","decision":decision,
      "hypothesis":"At least one of 42 fixed Top20 rules has excess 5/5 or 4+/5 coverage over the exact 5/40 null in a chronological split after Holm correction.",
      "analysis_governance":{"preregistered_before_data_inspection":False,"retrospective":True,"not_a_new_forecast":True,"no_engine_promotion":True,"protected_prs":[6,7,8]},
      "source":{"archive_git_blob_sha1":git_blob_sha1(ab),"archive_sha256":sha256(ab),"archive_draws":len(archive_dates),"archive_last_date":archive_dates[-1],
                "ledger_git_blob_sha1":git_blob_sha1(lb),"ledger_sha256":sha256(lb),"ledger_bytes":len(lb),"ledger_rows":len(dates)*len(cfg)},
      "integrity":{"targets":len(dates),"rules":len(cfg),"strict_prior_cutoffs_equal_previous_archive_date":True,
                   "actuals_match_archive":True,"top20_and_hit_counts_recomputed":True,
                   "evaluation_mode":"RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW",
                   "rankings_regenerated":False},
      "null":{"p_top20_5of5":p5,"p_top20_4plus":p4,"expected_top20_hits":2.5,
              "assumption":"IID uniform 5 distinct numbers from 1..40; forecasts predictable from prior history"},
      "multiple_testing":{"tests":len(adj),"family":"42 rules x 3 chronological splits x 2 endpoints",
                          "correction":"Holm step-down","alpha":0.05,"significant":len(sig),
                          "global_Q00_Q141_multiplicity_covered":False},
      "splits":{name:{"n":stats[name]["n"],"first":stats[name]["first"],"last":stats[name]["last"],
                      "ensemble_mean_top20_hits":stats[name]["ensemble_mean_top20_hits"],
                      "top5_5of5":sorted(({"config_id":c,**stats[name]["config"][c]} for c in cfg),
                                         key=lambda x:(-x["five_rate"],x["config_id"]))[:5]}
                for name,_,_ in splits},
      "discovery_selected_winner":{"config_id":winner,"selection":"highest Discovery 5/5 count; lexical tie-break","by_split":winner_split},
      "spearman_rank_stability":corr,
      "any_rule_5of5":{"targets":len(any5),"n":len(dates),"rate":len(any5)/len(dates),"descriptive_only":True},
      "best_unadjusted_test":best,"best_unadjusted_by_split_endpoint":pvals,
      "decision_criteria":{"support":"at least one Holm p < 0.05","observed":decision},
      "limitations":["Rule family selected after historical outcomes; chronological splits do not remove global post-selection.",
                     "Historical Blind OOS is not virgin prospective evidence.",
                     "Holm covers only 252 tests, not the broader Q00-Q141 search.",
                     "Audit verifies ledger cutoff/outcome alignment but does not regenerate the 42 rankings.",
                     "No future prediction claim follows."],
      "next_action":"Keep the 43 2026-11-13 pending shadow freezes append-only; reconcile only after official publication; do not add another selector from this audit."
    }
    out=root/"reports/sequence_agent"; out.mkdir(parents=True,exist_ok=True)
    rp=out/"q142_rule_family_fwer_audit_report_2026-11-13.json"
    cp=out/"q142_rule_family_fwer_audit_summary_2026-11-13.csv"
    mp=out/"q142_rule_family_fwer_audit_report_2026-11-13.md"
    manifestp=out/"q142_rule_family_fwer_audit_manifest_2026-11-13.json"
    checkpointp=out/"q142_rule_family_fwer_audit_checkpoint_2026-11-13.json"
    rp.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    rows=[]
    for name,_,_ in splits:
      for ep in ("5of5","4plus"):
       for cid in cfg:
        t=lookup[(name,ep,cid)]; z=stats[name]["config"][cid]
        rows.append({"split":name,"endpoint":ep,"config_id":cid,"n":t["n"],"count":t["count"],
                     "rate":z["five_rate"] if ep=="5of5" else z["fourplus_rate"],
                     "null_rate":p5 if ep=="5of5" else p4,
                     "mean_top20_hits":z["mean_top20_hits"],"p_raw":t["p_raw"],"p_holm_252":t["p_holm"],
                     "selected_in_discovery":int(cid==winner)})
    with cp.open("w",newline="") as f:
      w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    best5=min((x for x in adj if x["endpoint"]=="5of5"),key=lambda x:x["p_raw"])
    best4=min((x for x in adj if x["endpoint"]=="4plus"),key=lambda x:x["p_raw"])
    lines=["# Q142 — Fixed 42-rule family exact FWER audit","",
      f"Decision: {decision}. Holm-significant tests: {len(sig)}/{len(adj)}.","",
      "Retrospective audit only. The 42-rule family was developed after historical outcomes were available; this is not a virgin holdout or a new forecast.","",
      "| Split | N | First | Last | Mean Top20 hits across 42 rules |",
      "|---|---:|---|---|---:|"]
    for name,_,_ in splits:
      z=stats[name]; lines.append(f"| {name} | {z['n']} | {z['first']} | {z['last']} | {z['ensemble_mean_top20_hits']:.6f} |")
    lines += ["",f"Exact nulls: P(5/5)={p5:.9f}; P(4+/5)={p4:.9f}; E[hits]=2.5.",
      f"Best 5/5 raw test: {best5['config_id']} / {best5['split']}, {best5['count']}/{best5['n']}, p={best5['p_raw']:.6g}, Holm={best5['p_holm']:.6g}.",
      f"Best 4+/5 raw test: {best4['config_id']} / {best4['split']}, {best4['count']}/{best4['n']}, p={best4['p_raw']:.6g}, Holm={best4['p_holm']:.6g}.",
      f"Discovery winner: {winner}; rates: "+ "; ".join(f"{s} {winner_split[s]['five_count']}/{winner_split[s]['n']} ({winner_split[s]['five_rate']:.4%})" for s,_,_ in splits)+".",
      "Spearman rank correlations: "+ "; ".join(f"{k}={v:.4f}" for k,v in corr.items())+".",
      f"At least one rule hit 5/5 on {len(any5)}/{len(dates)} targets ({len(any5)/len(dates):.2%}); descriptive only.",
      "","Cutoffs and actuals were checked against the canonical archive. Holm covers 252 tests only; global Q00-Q141 multiplicity and post-hoc rule selection remain uncorrected.",
      "","Next action: preserve pending prospective forecasts unchanged and reconcile only after official publication."]
    mp.write_text("\n".join(lines)+"\n")
    source_paths=["scripts/sonar_q142_rule_family_fwer_audit.py","tests/test_sonar_q142_rule_family_fwer_audit.py",
                  "reports/sequence_agent/q142_rule_family_fwer_audit_protocol_2026-11-13.md"]
    man={"task_id":"Q142","status":"OUTPUTS_COMPUTED","source":{"archive_git_blob_sha1":git_blob_sha1(ab),"ledger_git_blob_sha1":git_blob_sha1(lb)},
         "source_code":{},"outputs":{},"targets":len(dates),"rules":len(cfg),"tests":len(adj),"holm_significant":len(sig)}
    for p in source_paths:
      b=(root/p).read_bytes(); man["source_code"][p]={"bytes":len(b),"sha256":sha256(b),"git_blob_sha1":git_blob_sha1(b)}
    for p in (rp,cp,mp):
      b=p.read_bytes(); man["outputs"][str(p.relative_to(root))]={"bytes":len(b),"sha256":sha256(b),"git_blob_sha1":git_blob_sha1(b)}
    manifestp.write_text(json.dumps(man,indent=2,sort_keys=True)+"\n")
    checkpointp.write_text(json.dumps({"task_id":"Q142","status":"OUTPUTS_COMPUTED","decision":decision,
      "targets":len(dates),"rules":len(cfg),"tests":len(adj),"holm_significant":len(sig)},indent=2,sort_keys=True)+"\n")
    return report

def main():
    p=argparse.ArgumentParser(); p.add_argument("--root",default="."); a=p.parse_args()
    r=run(Path(a.root))
    print(json.dumps({"task_id":r["task_id"],"decision":r["decision"],"targets":r["integrity"]["targets"],
                      "rules":r["integrity"]["rules"],"tests":r["multiple_testing"]["tests"],
                      "holm_significant":r["multiple_testing"]["significant"]},sort_keys=True))

if __name__=="__main__":
    main()
