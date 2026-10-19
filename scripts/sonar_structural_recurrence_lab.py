#!/usr/bin/env python3
"""Rebuild canonical VinciCasa structural signatures; validates the full archive first."""
import csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data/storico_daily.csv"
OUT=ROOT/"reports/daily_lab/structural_signatures.csv"
FIELDS="date numbers sum range odd even low_le20 high_gt20 overlap_prev1 gap1 gap2 gap3 gap4 sum_bin range_bin odd_cat low_cat overlap_cat gap1_bin gap2_bin gap3_bin gap4_bin sum_delta range_delta sum_transition range_transition mean_gap".split()
def binv(x,edges,names):
 return names[next((i for i,e in enumerate(edges) if x<e),len(edges))]
def main():
 if not DATA.exists(): raise SystemExit("PIPELINE BLOCKED: canonical archive missing")
 with DATA.open(newline="",encoding="utf-8-sig") as f:
  r=csv.DictReader(f)
  if r.fieldnames!=["data","n1","n2","n3","n4","n5"]: raise SystemExit("PIPELINE BLOCKED: invalid archive header")
  rows=[]
  for ln,x in enumerate(r,2):
   try: d=x["data"]; a=tuple(int(x["n"+str(i)]) for i in range(1,6))
   except Exception as e: raise SystemExit(f"PIPELINE BLOCKED row {ln}: {e}")
   if len(set(a))!=5 or tuple(sorted(a))!=a or min(a)<1 or max(a)>40: raise SystemExit(f"PIPELINE BLOCKED invalid draw row {ln}")
   rows.append((d,a))
 dates=[d for d,a in rows]
 if len(rows)<1000 or dates!=sorted(dates) or len(set(dates))!=len(dates): raise SystemExit("PIPELINE BLOCKED archive order/integrity")
 out=[]; prev=None; ps=pr=None
 for d,a in rows:
  s=sum(a); ran=a[-1]-a[0]; odd=sum(n%2 for n in a); low=sum(n<=20 for n in a); ov=len(set(a)&set(prev)) if prev else 0
  g=[a[i+1]-a[i] for i in range(4)]; sd=s-ps if ps is not None else None; rd=ran-pr if pr is not None else None
  out.append(dict(date=d,numbers="-".join(map(str,a)),sum=s,range=ran,odd=odd,even=5-odd,low_le20=low,high_gt20=5-low,overlap_prev1=ov,
   gap1=g[0],gap2=g[1],gap3=g[2],gap4=g[3],sum_bin=binv(s,[80,100,120,140],["S<80","S80-99","S100-119","S120-139","S140+"]),
   range_bin=binv(ran,[20,25,30,35],["R<20","R20-24","R25-29","R30-34","R35+"]),odd_cat=f"O{odd}",low_cat=f"L{low}",
   overlap_cat="X0" if ov==0 else "X1" if ov==1 else "X2+",
   gap1_bin=binv(g[0],[4,8,13],["G1-3","G4-7","G8-12","G13+"]),gap2_bin=binv(g[1],[4,8,13],["G1-3","G4-7","G8-12","G13+"]),
   gap3_bin=binv(g[2],[4,8,13],["G1-3","G4-7","G8-12","G13+"]),gap4_bin=binv(g[3],[4,8,13],["G1-3","G4-7","G8-12","G13+"]),
   sum_delta="" if sd is None else sd,range_delta="" if rd is None else rd,
   sum_transition="NA" if sd is None else ("UP_BIG" if sd>=15 else "UP" if sd>=5 else "DOWN_BIG" if sd<=-15 else "DOWN" if sd<=-5 else "FLAT"),
   range_transition="NA" if rd is None else ("EXPAND_BIG" if rd>=5 else "EXPAND" if rd>=1 else "CONTRACT_BIG" if rd<=-5 else "CONTRACT" if rd<=-1 else "STABLE"),mean_gap=format(sum(g)/4,".6g")))
  prev=a; ps=s; pr=ran
 OUT.parent.mkdir(parents=True,exist_ok=True)
 with OUT.open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(out)
 if len(out)!=len(rows) or out[-1]["date"]!=dates[-1]: raise SystemExit("INCOMPLETE: signatures failed cutoff/row-count check")
 print(f"STRUCTURAL_SIGNATURES_OK rows={len(out)} cutoff={dates[-1]}")
if __name__=="__main__": main()
