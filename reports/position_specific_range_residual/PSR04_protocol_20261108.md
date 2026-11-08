# SONAR PSR-04 — Continuous Same-Position Lag-1 Kernel Protocol

Research-only; no active-engine change.

## Hypothesis
For ordered position P_i, use the exact uniform-combination order-statistic prior pi_i(n)=C(n-1,i-1)C(40-n,5-i)/C(40,5), n=i..35+i.
With query x_t=P_i(t-1) and training lag feature x_s=P_i(s-1), use K_h(x_t,x_s)=exp(-0.5((x_t-x_s)/h)^2).
Candidate q_i,t(n|x_t)=[sum_(s<t)K_h(x_t,x_s)I(P_i(s)=n)+100*pi_i(n)]/[sum_(s<t)K_h(x_t,x_s)+100].
Comparator q_global=[c_i,t(n)+100*pi_i(n)]/[N_t+100].

## Frozen design
- Warmup 300; strict expanding prefix; each target scored before adding its row.
- Alpha fixed 100; h grid {2,4,6,10}; per-position h selected on validation Brier versus global shrinkage, ties to smaller h.
- Chronological split 50/25/25; primary blind-OOS paired Brier improvement.
- Circular moving-block bootstrap, block 7, 2,000 replicates, deterministic seed; one-sided benefit; Holm across five positions.
- Secondary log loss, Top-1/5/10/20 and mean rank descriptive.

## Leakage and reproducibility
- Target and future rows excluded; query is preceding same-position value, train feature is s-1 for target s.
- Canonical archive blob SHA, date order, sorted/distinct draw support, prior normalization, strict train count and unique target-position-bandwidth keys checked.
- Script runs twice and requires byte-identical report and ledger; CI uploads JSON, Markdown and CSV artifacts.
- Position marginals are dependent; no joint ticket is built.
- Historical blind partition is reused from PSR-01/02/03, not independent prospective evidence. Holm family covers PSR-04 five endpoints only.
- No promotion, merge, or active motor replacement.



**Persisted ledger precision:** numeric score columns are formatted to 9 decimal places for byte-stable cross-runtime hashes; model probabilities, proper scores and aggregate metrics are calculated at full precision (the report JSON is rounded to 12 decimal places).

## Result
See PSR04_results_20261108.md and PSR04_results_20261108.json. Next experiment: PSR-05 signed same-position displacement residual.
