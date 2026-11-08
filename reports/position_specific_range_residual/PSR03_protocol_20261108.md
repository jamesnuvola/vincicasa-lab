# SONAR PSR-03 — Protocol lock (2026-11-08)

**Scope:** five separate ordered-position series; research-only. No motor replacement, merge, or promotion.

## Hypothesis
For each ordered position P_i, the previous draw's same position P_i(t-1) may provide incremental information about the next P_i(t) after accounting for the exact order-statistic marginal.

## Fixed state definition
The state is the previous same-position value, binned by quartiles of the exact uniform-combination prior:
[
pi_i(n)=rac{inom{n-1}{i-1}inom{40-n}{5-i}}{inom{40}{5}},quad n=i,ldots,35+i.
]
Analytical cutpoints (P1–P5): [4,6,11], [9,14,19], [16,22,27], [24,29,34], [32,37,39]. These are fixed from the prior PMF, not learned from future targets.

## Models
Global empirical shrinkage:
[
q_{i,t}(n)=rac{c_{i,t}(n)+alphapi_i(n)}{N_t+alpha}.
]
Lag-1 state-conditioned shrinkage:
[
q_{i,t}(nmid s)=rac{c_{i,t,s}(n)+alphapi_i(n)}{N_{t,s}+alpha}.
]
Fixed alpha grid: [50,100,200,500]. At each position select the alpha with lowest validation Brier improvement (baseline minus candidate); tie-break toward lower alpha. No alpha selection on blind OOS.

## Temporal protocol
- Canonical data/storico_daily.csv, 3,401 draws through 2026-11-07.
- Warmup 300; strict expanding window; training target indices 1..t−1, with state of each training target sourced from its preceding draw. Score target t before adding it.
- 50% discovery / 25% validation / 25% blind OOS: 1,550 / 775 / 776 targets.
- Primary endpoint: blind-OOS paired Brier improvement vs global empirical shrinkage at the validation-selected alpha, separately for P1–P5.
- Inference: circular moving-block bootstrap, block length 7, 2,000 replicates, fixed seed base 20261108 with position offset P*2027; one-sided benefit p-value, percentile 95% CI; Holm correction across five primary position endpoints.
- Top-1/5/10/20, mean rank and log-loss are secondary descriptive endpoints. No independent-marginal ticket assembly.

## Guardrails
- Audit sorted distinct numbers, dates, support and exact prior normalization.
- For every target-position: cutoff must equal prior draw date and train_n == target_index − 1.
- Preserve all position results, including negative and non-significant results.
- No active engine replacement, merge, or PR #6/#7/#8 modification.
