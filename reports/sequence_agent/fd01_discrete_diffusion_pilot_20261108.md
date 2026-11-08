# SONAR FD-01 — Discrete diffusion / temporal residual pilot
**Status: EXPLORATORY; NOT A PROMOTED ENGINE**  
**Date:** 2026-11-08  
**Branch:** `research/fluid-dynamics-residual-20261108`

## Archive and leakage controls
- Canonical input: `data/storico_daily.csv`, blob SHA `5d2efd70684e918b27d8f06386d545647898336d`.
- 3,401 draws, 2017-07-17 through 2026-11-07.
- Every target score used only rows strictly preceding that target.
- Minimum history: 200 draws.
- Splits by target row index: discovery [200,1700), validation [1700,2550), blind OOS [2550,3401); respectively 1,500, 850, 851 targets.
- No claim that Navier–Stokes governs the lottery. This is a discrete diffusion-inspired feature/ranking hypothesis.

## Formula
For number n and target t, exponentially decayed prior occurrence field:
\[
c_n(t)=\sum_{j<t}2^{-(t-1-j)/h}\mathbf{1}[n\in D_j].
\]
Discrete Gaussian diffusion/smoothing over number-space:
\[
q_n(t)=\frac{\sum_{k=1}^{40}e^{-(n-k)^2/(2\sigma^2)}c_k(t)}
{\sum_{k=1}^{40}e^{-(n-k)^2/(2\sigma^2)}}.
\]
Rank numbers descending by q; ties by ascending number. The smoothing is over the ordered labels 1..40 (a hypothesis, not an established physical adjacency).

A 4x4 exploratory grid was evaluated: half-life h in {50,100,200,500} draws; sigma in {0.5,1,2,4}. Select the configuration by validation Top-5 per-number hit rate (not by blind OOS): h=200, sigma=4.

## Selected configuration metrics
Metric Top-k = share of actual individual numbers assigned rank <= k; mean rank averages the five actual number ranks per draw.

| Split | targets | Top5 hit % | Top10 hit % | Top20 hit % | Mean rank | all five in Top5 |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 1,500 | 12.6533 | 25.2267 | 50.7600 | 20.3125 | 0 |
| Validation | 850 | 12.9882 | 24.9647 | 49.6706 | 20.4704 | 0 |
| Blind OOS | 851 | 13.5605 | 25.0999 | 49.7767 | 20.5065 | 0 |

Uniform rank baseline: Top5 12.5%, Top10 25%, Top20 50%, mean rank 20.5. Blind OOS Top5 hits = 577 / 4,255 number-cases; uniform expected = 531.875. A deterministic-seed Monte Carlo with 10,000 independent per-target uniform 5-subset rankings, holding actual historical draws fixed, estimated one-sided p=0.01480 for the selected configuration's blind Top5 count. This p-value is unadjusted; the pilot grid and exploratory scope mean it is not sufficient for promotion. Mean rank is marginally worse than uniform (20.5065 vs 20.5); Top10/Top20 are near baseline. The apparent Top5 improvement is a narrow, metric-specific signal and requires registered replication and correction for the full experiment family.

## Ex-ante score for target 2026-11-07
Cutoff 2026-11-06; configuration h=200, sigma=4. Top 10: 40,39,38,37,36,35,34,33,32,28.
Actual draw: 12,16,27,31,38. Ranks: 12->22, 16->21, 27->14, 31->12, 38->3. Thus 1/5 actual numbers landed Top5, 1/5 Top10, 2/5 Top20. This is a retrospective scoring result for the already completed target, not a future prediction.

## Decision / next experiment
- Exploratory pilot only; no model promotion.
- Freeze this exact formula and configuration before next prospective evaluation.
- Next: residual diagnosis, assess boundary bias and whether ordered-number Gaussian smoothing is just a label artifact; compare against non-diffusion exponential-frequency baseline and matched randomization, using a preregistered small family and fresh chronological OOS. Investigate conditional interactions only after primary replication.
- Do not label any queue task complete without validators, persisted outputs, current-head CI, and review/integration.
