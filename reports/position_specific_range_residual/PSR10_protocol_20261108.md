# PSR-10 Protocol — Previous-draw sum-quartile state marginals

**Experiment ID:** SONAR_PSR10_PREVIOUS_SUM_QUARTILE_STATE_MARGINALS  
**Status:** run-local predeclared specification; persisted after computation for traceability, not Git-committed before the computation. This is not an externally timestamped preregistration.  
**Archive:** data/storico_daily.csv; Git blob SHA 5d2efd70684e918b27d8f06386d545647898336d; 3,401 draws, 2017-07-17 through 2026-11-07.

## Quantitative hypothesis

The previous draw's total sum S(t-1) may condition the next draw's sorted-position marginal law. Its state is discretized by exact theoretical quartiles of all uniform 5-of-40 combinations, not by historical sample quantiles.

For position i and value n:
[
\pi_i(n)=\frac{\binom{n-1}{i-1}\binom{40-n}{5-i}}{\binom{40}{5}}
]
[
q_{i,t}(n\mid s)=\frac{C_{i,s,t-1}(n)+\alpha\pi_i(n)}{N_{i,s,t-1}+\alpha}.
]
Here C counts prior transition outcomes u=1,...,t-1 whose predictor state from draw u-1 equals the state s of the previous draw for target t. N is the corresponding state count. The global comparator uses the same transition outcomes u=1,...,t-1 without conditioning on s and the same alpha.

Exact DP over 5-of-40 sums sets cutpoints to the smallest integer sum whose exact CDF reaches 0.25, 0.50, and 0.75. Resulting states: Q1 sum<=86; Q2 87–102; Q3 103–119; Q4>=120. State mass is exact and unequal only due integer-sum ties.

## Selection and design

- Warm-up: target row index 200 (zero-based).
- Walk-forward targets: t=200,...,3400, 3,201 targets.
- Chronological split: discovery 60% (1,920); validation 20% (640); blind OOS remainder (641).
- Alpha grid fixed: {300, 1000, 3000}; independently select per position using validation mean Brier gain vs cumulative global transition marginal with same alpha; tie-break larger alpha.
- Primary blind OOS comparison: selected conditional-state marginal vs global transition marginal with same alpha.
- Secondary comparison: selected conditional-state marginal vs exact order-statistic prior.
- Multiclass Brier: sum over n=1..40 of (p(n)-1[n=y])^2. Log-loss gains descriptive only.
- Inference: circular moving-block bootstrap, block length 7, 2,000 replicates, deterministic xorshift seed; centered one-sided p-value for positive Brier gain; percentile 95% CI.
- Holm correction across 10 endpoints (5 positions × 2 comparators), family-wise alpha 0.05.

## Leakage and integrity gates

1. Parse archive and verify date monotonicity, unique sorted five-number draws, range 1..40.
2. For target t, training transition outcomes u=1,...,t-1 only; predictor for u uses draw u-1; target t and later rows excluded.
3. Target cutoff equals date t-1 and precedes target date.
4. Exact prior and every conditional/global probability vector normalize within 1e-12.
5. Strict-prefix and cutoff checks for every target.
6. Persist five position ledgers with train count, state train count, actual value, probabilities and Brier/log-loss gains.
7. Full-run replay with same pinned archive/options/seed must byte-match JSON, Markdown, and all CSV ledgers.

## Interpretation guardrails

Historical blind tail through 2026-11-07 has been inspected by prior SONAR research; this run is exploratory, not independent confirmation. Five marginals do not define a joint quintet law. No physical Navier–Stokes mechanism is claimed. No candidate enters the live prospective shadow stream and no engine is promoted without human review and the existing prospective gate.
