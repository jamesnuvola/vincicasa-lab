# SONAR PSR-08 — Adjacent pair joint gap-state walk-forward protocol

**Status:** exploratory; this protocol was persisted after the initial computation, not before it. It is not a formal preregistration.
**Branch:** research/sonar-psr08-adjacent-joint-gap-20261108
**Archive pin:** Git blob SHA 5d2efd70684e918b27d8f06386d545647898336d; 3,401 draws, 2017-07-17 through 2026-11-07.
**No promotion, merge, or edits to PR #6, #7, #8, #13.**

## Quantitative hypothesis

For each adjacent ordered pair (i,i+1), the gap (G_{i,t-1}=P_{i+1,t-1}-P_{i,t-1}) of the immediately preceding draw may condition the next draw's joint pair distribution (X_{i,t}=(P_{i,t},P_{i+1,t})). Under independent uniform 5-subset draws, this state should add no predictive information.

The four primary endpoints are blind-OOS multiclass Brier improvements against a global pair-joint shrinkage model with the same validation-selected alpha. Positive improvement means the conditional model has lower Brier loss.

## Exact prior

For (1le a<ble40):

[
\pi_i(a,b)=\frac{\binom{a-1}{i-1}\binom{40-b}{4-i}}{\binom{40}{5}}.
]

This counts the (i-1) selected numbers below (a), the pair (a,b), and the (4-i) selected numbers above (b). Each adjacent pair's support has 666 cells and the prior count sum is exactly 658,008.

The exact gap-prior quartile cutpoints are [3, 5, 10], with state intervals:
- S1: gap ≤ 3
- S2: gap 4–5
- S3: gap 6–10
- S4: gap ≥ 11

## Shrinkage models

For pair cell (x=(a,b)), prior (pi_i(x)), conditional state (s_t), strict-prior training count (c_{i,t,s}(x)), and state sample size (N_{t,s}):

[
q_{i,t}(x\mid s_t)=\frac{c_{i,t,s_t}(x)+\alpha\pi_i(x)}{N_{t,s_t}+\alpha}.
]

The global comparator is

[
q^G_{i,t}(x)=\frac{c_{i,t}(x)+\alpha\pi_i(x)}{N_t+\alpha}.
]

Alpha grid: [100, 300, 1000]. Choose alpha separately per adjacent pair by maximum validation mean Brier improvement (B(q^G,y)-B(q,y)); ties select smaller alpha. The blind OOS is not used to select alpha.

Multiclass Brier loss:

[
B(q,y)=\sum_{x\in\mathcal X_i}(q(x)-\mathbf1[x=y])^2
=1-2q(y)+\sum_xq(x)^2.
]

## Walk-forward and splits

- Warmup target row index 300 (zero-based), 3,101 scored targets.
- For target row (t), training outcomes are rows (j=2,ldots,t-1), so (N_t=t-2); conditioning feature for each historical training target (j) is gap from draw (j-1), outcome is pair from draw (j).
- Target feature uses only draw row (t-1); assert its date is strictly before target date.
- Chronological split: discovery 50%, validation 25%, blind OOS 25%; exact counts 1,550 / 775 / 776.
- Primary inference: circular moving-block bootstrap, block length 7, 2,000 replicates, deterministic per-pair seeds; centered-null one-sided p-value and percentile 95% CI.
- Holm–Bonferroni correction across four predeclared pair-level primary Brier endpoints.
- Log-loss, exact-prior comparisons and state-frequency counts are secondary/descriptive; they do not change the primary family.

## Integrity and limitations

- Archive chronology, sorted unique 5-number rows, range 1..40 and Git blob pin checked fail-closed.
- At every target, assert train_n=t−2 and cutoff date < target date.
- Exact pair-prior normalization and conditional/global probability normalization checked.
- Target × pair ledger keys are unique; stable CSV order and 12-decimal output serialization.
- The protocol is documented post-computation, not formally preregistered. The historical blind slice has been inspected in prior SONAR work and is not lab-wide independent confirmation.
- Pairwise distributions do not validate a full five-number ticket. No causal or physical Navier–Stokes interpretation is claimed.

## Decision rule and next action

No promotion. Preserve PSR-08 as exploratory if no pair survives Holm at 0.05. Freeze cutpoints and alpha grid; do not tune on the inspected blind slice. The next confirmatory stage should be a prospectively registered append-only shadow evaluation on at least 200 new targets, with a validation-selected explicit GLOBAL_ONLY fallback, then human review.
