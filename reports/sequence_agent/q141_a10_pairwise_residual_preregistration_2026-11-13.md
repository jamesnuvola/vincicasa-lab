# Q141-A10 — rolling pairwise co-occurrence residual score

**Status:** preregistered historical exploratory walk-forward; not prospective confirmation.  
**Source:** pinned Q141-A7 artifact from workflow run 43348144964, artifact 14003350043; source archive Git blob `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`, 3,406 draws through 2026-11-12.  
**Source matrix:** 3,356 target rows, 40 numbers, 59 feature channels; actual quintets and target/cutoff dates are carried in the artifact.  
**Target window:** use target rows 400..3355 (2,956 targets), requiring 400 already observed target rows in the A7 matrix.  
**Chronological split:** Discovery 1,774; Validation 591; historical Blind OOS 591.

## Question and quantitative hypothesis

Do recent pair co-occurrence residuals predict the *joint composition* of the next 5-of-40 draw after removing all additive single-number effects?

For each target t, use only the immediately preceding 200 observed quintets, rows [t-200,t), to form pair counts C_ij. Fit the complete-graph additive nuisance model

`C_ij = mu + alpha_i + alpha_j + R_ij`

by least squares, with `sum_i alpha_i = 0`:
- `mu = sum_{i<j} C_ij / choose(40,2)`
- `alpha_i = (row_sum_i - 39*mu)/38`
- `R_ij = C_ij - mu - alpha_i - alpha_j`

Thus every residual row sum is zero and `sum_{i<j} R_ij = 0`; pair effects cannot be explained by a number's overall frequency.

For the target quintet S, define `T_t = sum_{i<j in S} R_ij`. Under the exact uniform 5-of-40 null, the expectation is zero and the exact variance is

`Var_0(T_t) = (p2 - 2*p3 + p4) * sum_{i<j} R_ij^2`

where `pk = (5)_k/(40)_k` for k=2,3,4. The standardized score is `Z_t = T_t / sqrt(Var_0(T_t))` (zero only if the variance is exactly zero).

**Primary hypothesis:** mean recent-window Z on Blind OOS is at least +0.10 and has a one-sided block-sign-flip p-value below 0.05 after Holm correction, with a circular moving-block-bootstrap 95% lower bound above zero.

**Secondary recency control:** compare recent-window Z with an equally sized stale window [t-400,t-200). The recent-minus-stale Blind OOS mean must be at least +0.05 and its Holm-adjusted one-sided p-value below 0.05 to support recency-specific information. The stale window is a negative/age control, not a model selected on outcomes.

## Baseline, splits and inference

- Baseline: uniform unordered 5-of-40 subset; exact null mean Z=0 and per-target null variance 1.
- Recent window: exactly 200 prior draws.
- Stale control: exactly 200 draws immediately before the recent window.
- No tunable coefficients, feature selection, window search or Discovery calibration.
- Discovery and Validation are reported separately; no parameter or endpoint may be changed after viewing them.
- Blind OOS primary endpoint: mean Z_recent versus zero.
- Blind OOS secondary endpoint: mean (Z_recent - Z_stale) versus zero.
- Circular moving-block bootstrap: block length 20, 20,000 replicates, percentile 95% interval.
- Monte Carlo block sign-flip: block length 20, 20,000 replicates, one-sided.
- Holm correction across the two registered Blind OOS endpoints.
- Practical thresholds are fixed at +0.10 Z units for the primary and +0.05 for the recency-control difference.

## Integrity and reproducibility

- Pin and verify the A7 artifact SHA-256 and the source archive blob SHA-1.
- Verify target dates are unique and chronological; every cutoff precedes its target.
- For each target, use only rows strictly before it; the recent and stale windows are disjoint and precede the target.
- Verify residual row sums and total residual sum are zero within numerical tolerance.
- Verify the analytic null variance against exhaustive enumeration on a small synthetic fixed-size subset problem.
- Future-suffix mutation test: changing rows after a target cannot alter that target's Z score.
- Deterministic replay, finite-value checks, target ledger, manifest hashes and remote Git readback.
- The A7 historical Blind OOS and broader SONAR archive have been repeatedly inspected. A10's historical Blind OOS is exploratory, not virgin confirmatory evidence. Holm covers only the two registered A10 endpoints, not the entire Q00-Q141 research family.

## Interpretation limits

A positive score-test result would indicate that recent pair residuals align with future draw pairs beyond additive number frequencies; it would not by itself prove improved ticket-level probability, exact-quintet prediction, or a deployable engine. Any positive historical result requires a separately preregistered prospective replication. No B11 outcome is read or used. No B11 freeze, canonical archive, production engine, Q60 gate, or protected PR is modified.

## Governance

Research only. No engine promotion, shadow insertion, canonical archive mutation, automatic merge or rebase. PRs #6, #7 and #8 remain untouched. PR #90 remains draft for human review.
