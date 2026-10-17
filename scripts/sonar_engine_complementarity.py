#!/usr/bin/env python3
"""Reproduce the SONAR three-engine complementarity experiment.
Standard library only. Run from repository root:
  python scripts/sonar_engine_complementarity.py
Outputs JSON summary and per-target CSV under reports/sequence_agent/.
"""
import csv, json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"storico_daily.csv"
OUT=ROOT/"reports"/"sequence_agent"
MIN_HISTORY=200
NUMBERS=range(1,41)

def read_draws():
    with DATA.open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        if reader.fieldnames != ["data","n1","n2","n3","n4","n5"]:
            raise RuntimeError(f"Unexpected archive header: {reader.fieldnames}")
        out=[]
        for row in reader:
            nums=tuple(int(row[f"n{i}"]) for i in range(1,6))
            if len(set(nums))!=5 or tuple(sorted(nums))!=nums or any(n<1 or n>40 for n in nums):
                raise RuntimeError(f"Invalid draw: {row}")
            out.append({"date":row["data"],"nums":nums})
        if len(out)<=MIN_HISTORY or any(out[i]["date"]<=out[i-1]["date"] for i in range(1,len(out))):
            raise RuntimeError("Archive is too short or not strictly chronological")
        return out

def sum_bin(s): return min(7,s//25)
def range_bin(r): return min(5,r//7)
def odd_count(nums): return sum(n%2 for n in nums)
def rank(scores): return sorted(NUMBERS,key=lambda n:(-scores[n],n))
def hits(ranking,actual,k): return len(set(ranking[:k]) & set(actual))
def percentile(scores):
    vals=sorted(scores[n] for n in NUMBERS)
    return {n: next((i/39 for i,v in enumerate(vals) if v>=scores[n]),1.0) for n in NUMBERS}
def signature(draw): 
    ns=draw["nums"]
    return (sum_bin(sum(ns)),range_bin(ns[-1]-ns[0]),odd_count(ns))
def feature_rankings(history):
    latest=history[-1]
    momentum={}
    decay={}
    analog={}
    transition={}
    for n in NUMBERS:
        momentum[n]=sum(n in d["nums"] for d in history[-20:])/20 - sum(n in d["nums"] for d in history[-120:-20])/100
        decay[n]=sum(math.exp(-age/60) for age,d in enumerate(reversed(history[-200:])) if n in d["nums"])
        analog[n]=0.0
        transition[n]=0.0
    current=[signature(d) for d in history[-3:]]
    for j in range(3,len(history)):
        prior=[signature(d) for d in history[j-3:j]]
        dist=sum(abs(current[z][0]-prior[z][0])*.5 + abs(current[z][1]-prior[z][1])*.7 + abs(current[z][2]-prior[z][2])*.35 for z in range(3))
        w=math.exp(-dist/2.8)*math.exp(-(len(history)-j)/350)
        if w>.015:
            for n in history[j]["nums"]: analog[n]+=w
        if signature(history[j-1])[:2] == signature(latest)[:2]:
            w2=math.exp(-(len(history)-j)/250)
            for n in history[j]["nums"]: transition[n]+=w2
    ap,dp=percentile(analog),percentile(decay)
    a_score={n:(ap[n]+dp[n])/2 for n in NUMBERS}
    return {"M":rank(momentum),"A":rank(a_score),"T":rank(transition)}

def allocate(rankings, composite, m,a,t):
    selected=[]; seen=set()
    for source,limit in (("M",m),("A",a),("T",t)):
        pass
    lists=[rankings["M"][:m],rankings["A"][:a],rankings["T"][:t]]
    changed=True
    while changed:
        changed=False
        for values in lists:
            n=next((x for x in values if x not in seen),None)
            if n is not None:
                seen.add(n); selected.append(n); changed=True
    for n in composite:
        if len(selected)>=20: break
        if n not in seen: seen.add(n); selected.append(n)
    return selected[:20]

def main():
    draws=read_draws(); rows=[]
    for i in range(MIN_HISTORY,len(draws)):
        history,target=draws[:i],draws[i]
        rankings=feature_rankings(history); pct={k:{n:(40-r.index(n))/39 for n in NUMBERS} for k,r in rankings.items()}
        composite=rank({n:sum(pct[k][n] for k in ("M","A","T"))/3 for n in NUMBERS})
        allocations={"10M_5A_5T":allocate(rankings,composite,10,5,5),"5M_10A_5T":allocate(rankings,composite,5,10,5),"5M_5A_10T":allocate(rankings,composite,5,5,10),"8M_8A_4T":allocate(rankings,composite,8,8,4),"4M_8A_8T":allocate(rankings,composite,4,8,8)}
        actual=set(target["nums"]); cats={k:[] for k in ("all3","MA","MT","AT","onlyM","onlyA","onlyT","none")}
        top={k:set(v[:20]) for k,v in rankings.items()}
        for n in target["nums"]:
            m,a,t=(n in top[k] for k in ("M","A","T"))
            key="all3" if m and a and t else "MA" if m and a else "MT" if m and t else "AT" if a and t else "onlyM" if m else "onlyA" if a else "onlyT" if t else "none"
            cats[key].append(n)
        row={"target_date":target["date"],"history_cutoff":history[-1]["date"],"split":"discovery" if i<len(draws)*.6 else "validation" if i<len(draws)*.8 else "oos","actual":" ".join(map(str,target["nums"]))}
        for k,r in rankings.items():
            row[k+"_top20_hits"]=hits(r,target["nums"],20)
            row[k+"_top20"]=" ".join(map(str,r[:20]))
        for k,v in allocations.items():
            row[k+"_top20_hits"]=hits(v,target["nums"],20); row[k+"_top20"]=" ".join(map(str,v))
        for k,v in cats.items(): row[k+"_correct"]=" ".join(map(str,v))
        rows.append(row)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"engine_complementarity_ledger.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    splits={"all":rows,"discovery":[r for r in rows if r["split"]=="discovery"],"validation":[r for r in rows if r["split"]=="validation"],"oos":[r for r in rows if r["split"]=="oos"]}
    metrics={}
    strategies=("M","A","T","10M_5A_5T","5M_10A_5T","5M_5A_10T","8M_8A_4T","4M_8A_8T")
    for split,subset in splits.items():
        metrics[split]={"n":len(subset),"strategies":{}}
        for strategy in strategies:
            values=[int(r[strategy+"_top20_hits"]) for r in subset]; n=len(values)
            metrics[split]["strategies"][strategy]={"mean_top20_hits":round(sum(values)/n,6),"p_at_least_3":round(sum(v>=3 for v in values)/n,6),"p_at_least_4":round(sum(v>=4 for v in values)/n,6),"top20_5of5_count":sum(v==5 for v in values)}
    report={"agent":"SONAR engine complementarity experiment","status":"EXPLORATORY_NOT_PROMOTED","archive_last_date":draws[-1]["date"],"total_draws":len(draws),"targets":len(rows),"minimum_history":MIN_HISTORY,"definitions":{"M":"freq(last 20)-freq(previous 100)","A":"equal blend of rank percentiles for half-life-60 recency and analogues of previous three-draw coarse signatures","T":"recency-weighted successors of historical draws whose preceding draw has matching coarse sum/range bins"},"metrics":metrics,"guardrail":"Chronological retrospective only. Multiple variants explored; no strategy promotion. Validate on a newly frozen prospective sample."}
    (OUT/"engine_complementarity_report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__": main()
