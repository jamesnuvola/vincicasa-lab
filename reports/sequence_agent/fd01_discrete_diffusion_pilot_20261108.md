# SONAR FD-01 — Discrete diffusion / temporal residual pilot
**Status: EXPLORATORY; NOT A PROMOTED ENGINE**  
**Date:** 2026-11-08  
**Archive:** `data/storico_daily.csv`, blob SHA `5d2efd70684e918b27d8f06386d545647898336d`  
**Scope:** 3,401 draws, 2017-07-17 through 2026-11-07. Strict prior-only scoring; minimum history 200. Split targets [200,1700), [1700,2550), [2550,3401): 1,500/850/851. No claim Navier–Stokes governs lottery outcomes.

## Formula
`c_n(t)=Σ_{j<t} 2^{-(t-1-j)/h} 1[n∈D_j]`

`q_n(t)=Σ_{k=1}^{40} exp(-(n-k)^2/(2σ²)) c_k(t) / Σ_{k=1}^{40} exp(-(n-k)^2/(2σ²))`

Rank descending by q; ties ascending number. The Gaussian operates on ordered labels 1..40, a hypothesis rather than established physical adjacency. Exploratory 4×4 grid: h∈{50,100,200,500}, σ∈{0.5,1,2,4}; selected on validation Top-5 hit rate only: h=200, σ=4.

| Split | Targets | Top5 % | Top10 % | Top20 % | Mean rank | All five Top5 |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 1,500 | 12.6533 | 25.2267 | 50.7600 | 20.3125 | 0 |
| Validation | 850 | 12.9882 | 24.9647 | 49.6706 | 20.4704 | 0 |
| Blind OOS | 851 | 13.5605 | 25.0999 | 49.7767 | 20.5065 | 0 |

Uniform rank baseline: Top5 12.5%, Top10 25%, Top20 50%, mean rank 20.5. Blind Top5: 577/4,255 number-cases vs 531.875 expected; deterministic MC 10,000 per-target random 5-subsets gave one-sided p=0.01480, unadjusted. This is a narrow metric-specific exploratory signal; mean rank is slightly worse than uniform and Top10/20 near baseline. Not enough for promotion.

## Target 2026-11-07 score (cutoff 2026-11-06)
Top10: 40,39,38,37,36,35,34,33,32,28. Actual: 12,16,27,31,38; ranks 22,21,14,12,3 (1/5 Top5, 1/5 Top10, 2/5 Top20). Retrospective scoring of completed target, not a future forecast.

## Decision
Keep FD-01 exploratory. Freeze the formula and test a direct decayed-frequency baseline plus a boundary-reflected kernel; diagnose label-space/band effects with conditional randomization; require fresh prospective OOS and registered correction before any promotion. No auto-merge or queue-completion claim without full validators, exact-head CI, persistence and human review.
