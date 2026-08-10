#!/usr/bin/env python3
"""
Rigenera src/data.json a partire da data/storico_daily.csv.

Da lanciare dopo aver aggiunto nuove estrazioni al CSV:
    python3 scripts/rigenera_dati.py

Calcola:
  - freq  : frequenza storica di ogni numero in ogni posizione (il "pavimento")
  - prof  : profilo RITORNO per (posizione, numero) = distanze di ritorno
            piu' frequenti + finestra massima (cap 10 per P1/P5, 15 per P2/P3/P4)
  - draws : le estrazioni recenti servite all'app (da RECENT_FROM in poi)
"""
import csv, json, os
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(BASE, "data", "storico_daily.csv")
OUT = os.path.join(BASE, "src", "data.json")

VALID_RANGE = {0: (1, 36), 1: (2, 37), 2: (3, 38), 3: (4, 39), 4: (5, 40)}
CAP = {0: 10, 1: 15, 2: 15, 3: 15, 4: 10}
MIN_USCITE = 5        # sotto questa soglia il numero non riceve premio RITORNO
BONUS_MIN_HITS = 3    # una distanza da' rinforzo solo con almeno 3 ritorni reali
RECENT_FROM = "2026-04-01"  # da quando includere le estrazioni nell'app

rows = list(csv.DictReader(open(CSV)))
draws = np.array([[int(r[f"n{i}"]) for i in range(1, 6)] for r in rows])
dates = [r["data"].strip() for r in rows]
N = len(rows)

freq = {}
for p in range(5):
    lo, hi = VALID_RANGE[p]
    pos = draws[:, p]
    freq[p] = {int(n): round(float(np.mean(pos == n)), 5) for n in range(lo, hi + 1)}

profiles = {}
for p in range(5):
    lo, hi = VALID_RANGE[p]
    pos = draws[:, p]
    profiles[p] = {}
    for n in range(lo, hi + 1):
        occ = np.where(pos == n)[0]
        if len(occ) < MIN_USCITE:
            profiles[p][int(n)] = None
            continue
        gaps = np.diff(occ)
        vals, counts = np.unique(gaps, return_counts=True)
        order = np.lexsort((vals, -counts))       # piu' frequenti prima, a parita' la piu' vicina
        top3 = vals[order[:3]]
        wmax = int(min(int(top3.max()), CAP[p]))  # finestra = 3a distanza piu' frequente, tagliata al cap
        hot = sorted(
            int(d) for d, c in zip(vals, counts)
            if d in top3 and c >= BONUS_MIN_HITS and d <= wmax
        )
        profiles[p][int(n)] = {"h": hot, "w": wmax}

recent = [
    {"d": dates[t], "n": [int(x) for x in draws[t]]}
    for t in range(N) if dates[t] >= RECENT_FROM
]

json.dump(
    {"freq": freq, "prof": profiles, "draws": recent, "histN": N, "lastDate": dates[-1]},
    open(OUT, "w"), separators=(",", ":"),
)
print(f"{OUT}: {N} estrazioni storiche, {len(recent)} recenti, ultima {dates[-1]}")
