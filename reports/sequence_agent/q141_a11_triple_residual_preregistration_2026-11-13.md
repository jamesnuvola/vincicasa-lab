# Q141-A11 — third-order co-occurrence residual behaviour

**Status:** preregistered historical exploratory walk-forward; not prospective confirmation.  
**Source:** pinned Q141-A7 artifact from workflow run 43348144964, artifact 14003350043; archive Git blob 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb, 3,406 draws through 2026-11-12.  
**Source matrix:** 3,356 rows, 40 numbers, 59 feature channels; actual target quintets and target/cutoff dates are carried in the artifact.

## Question and quantitative hypothesis

Do third-order co-occurrence residuals contain information about the next 5-of-40 draw after removing all additive single-number and pairwise effects?

For each target t, use only the immediately preceding 200 observed quintets to compute triple counts Y_ijk over all choose(40,3) triples. Fit the balanced lower-order decomposition

Y_ijk = mu + a_i + a_j + a_k + b_ij + b_ik + b_jk + R_ijk.

Let S_i be the sum of Y over triples containing i, Q_ij the sum over triples containing pair ij, and n=40. The orthogonal lower-order terms are

mu = mean(Y_ijk)
a_i = (S_i - choose(n-1,2)*mu) / choose(n-2,2)
b_ij = (Q_ij - (n-2)*mu - (n-3)*(a_i+a_j)) / (n-4).

The resulting third-order residuals satisfy sum over k not i,j of R_ijk = 0 for every pair ij, removing all lower-order single and pair contributions.

For target quintet S_t, T3_t is the sum of R_ijk over its ten triples. Under the exact uniform unordered 5-of-40 reference,

Var0(T3_t) = (p3 - 3*p4 + 3*p5 - p6) * sum R_ijk^2,
p_q = (5)_q/(40)_q, with p6=0 for k=5.

Define Z3_t = T3_t / sqrt(Var0(T3_t)).

**Primary hypothesis:** Blind OOS mean Z3_recent is at least +0.10, with one-sided martingale-normal p-value below 0.05 after Holm correction and a positive 95% interval lower bound.

**Secondary recency control:** form U_t = R_recent/sqrt(V_recent) - R_stale/sqrt(V_stale), where stale is the 200 draws immediately before recent. U_t retains zero pair margins; standardize its target score by its own exact conditional variance. The secondary mean standardized contrast must be at least +0.05 and pass the same corrected inference.

## Walk-forward, baseline and inference

- Recent window: exactly 200 draws [t-200,t).
- Stale control: exactly 200 draws [t-400,t-200).
- Warmup: 400 prior target rows.
- Target rows: 400..3355 inclusive, expected 2,956.
- Chronological split: Discovery 1,774; Validation 591; historical Blind OOS 591.
- Baseline: uniform unordered 5-of-40; each standardized score has conditional mean 0 and variance 1.
- No parameter tuning, window search, feature selection or Discovery calibration.
- Under independent uniform draws, each standardized score is a martingale difference with predictable variance 1. Primary inference uses the martingale-normal approximation with predictable variance n; Newey-West HAC and ACF at lags 20, 50 and 100 are reported as dependence sensitivities.
- Holm correction across the two registered Blind OOS endpoints only.
- Practical thresholds: +0.10 for primary and +0.05 for normalized recency contrast.

## Integrity and reproducibility

- Pin and verify A7 artifact SHA-256 and archive blob SHA-1.
- Verify matrix shape, 59 feature channels, finite values, unique chronological dates and cutoff strictly before each target.
- For every target, both windows are disjoint and strictly prior.
- Verify every pair marginal of the triple residual tensor is zero within numerical tolerance.
- Verify analytic conditional variance against exhaustive enumeration of all 5-subsets on a small synthetic n=8 problem.
- Future-suffix mutation test: modifying rows after a target cannot change that target's scores.
- Deterministic full replay, finite-value checks, complete target ledger, manifest hashes and remote Git readback.

## Interpretation limits

Historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation. Holm covers only the two A11 endpoints, not the full Q00-Q141 research family. The martingale null assumes independent uniform 5-of-40 draws; the normal approximation is asymptotic and its Lindeberg proxy/HAC/ACF diagnostics must be reviewed. A positive score test would not itself prove exact-ticket probability improvement or justify engine promotion. Any positive historical result requires a separately preregistered prospective replication. No B11 outcome is read or used.

## Governance

Research only. No canonical archive mutation, shadow insertion, production-engine change, automatic merge or rebase. PRs #6, #7 and #8 remain untouched; PR #90 remains draft for human review.
