# Q141-A9 — distributional scoring of complete 5-number subsets

**Status:** preregistered historical exploratory walk-forward; not a prospective confirmation.  
**Source archive:** 3,406 draws through 2026-11-12; expected Git blob 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.  
**Target count:** 3,356 after a 50-draw minimum history.  
**Chronological split:** Discovery 2,014; Validation 671; historical Blind OOS 671.

## Hypothesis

The 40-number score vectors from Q141-A7 may contain information about the complete unordered 5-of-40 subset, not merely Top-5/Top-10 hit counts. Converting a score vector into a normalized fixed-size subset distribution may reveal whether equal-family (M0) or stability-weighted (M1) scores carry incremental joint information.

For score vector s=(s1,...,s40), temperature T>0, and a five-number subset S:

P_T(S|s) = exp(sum(s_i/T for i in S)) / e5(exp(s1/T),...,exp(s40/T))

where e5 is the fifth elementary symmetric polynomial. This is a normalized probability distribution over all 658,008 unordered subsets.

## Models and calibration

- M0: arithmetic mean of the seven Q141-A7 family score vectors.
- M1: the fixed Q141-A7 stability weights, calculated from only the previous five target rows.
- U: exact uniform distribution over all 5-of-40 subsets.
- Calibrate one temperature per model using Discovery outcomes only, from the fixed grid [0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 5, 8, 13, 21, 34]; choose the temperature with minimum mean joint negative log probability. Freeze both temperatures before Validation and Blind OOS. No temperature selection on Validation or Blind OOS.
- Discovery metrics are calibration-sample diagnostics and are not unbiased estimates of generalization.

## Endpoints and inference

- Primary: Blind OOS joint log-score gain M1 versus M0, defined as NLL(M0) - NLL(M1); positive favours M1.
- Secondary: joint log-score gains M1 versus U and M0 versus U.
- Secondary: marginal inclusion Brier-score gains for M1 versus M0, M1 versus U, and M0 versus U.
- Practical threshold for the primary endpoint: at least +0.005 nats per draw.
- Blind OOS uncertainty: circular moving-block bootstrap, block length 20, 20,000 replicates; one-sided block sign-flip test, block length 20, 20,000 Monte Carlo replicates.
- Holm correction across all six pre-specified Blind OOS endpoints. No unadjusted endpoint will be used for a promotion decision.
- Historical Blind OOS is already exposed to prior SONAR research and is therefore exploratory, not a virgin confirmatory holdout. A positive historical result would require a separately preregistered prospective replication.

## Integrity controls

- Rebuild Q141-A7's 59-feature matrix from the pinned canonical archive.
- Preserve Q141-A7's strict score-before-update semantics and its exact family definitions, rank rounding, and tie handling.
- Every target feature and score vector must use only draws strictly before that target.
- Fit temperatures only on Discovery; never inspect Validation/Blind OOS while calibrating.
- Verify fixed-size subset probability normalization and that marginal inclusion probabilities sum to five.
- Future-suffix mutation test: changing draws after a target cutoff must not change that target's feature vector or score.
- Deterministic replay, archive blob pinning, date/cutoff audit, finite-value checks, and remote Git readback.
- No B11 prospective outcome is read or used. No existing freeze, canonical archive, production scorer, Q60 record, or protected PR is modified.

## Decision rule

A historical signal is recorded only if the primary Blind OOS gain is at least +0.005 nats/draw, its 95% block-bootstrap lower bound is above zero, and its Holm-adjusted one-sided p-value is below 0.05. Even then, the result is only a candidate for new prospective confirmation, not authorization to promote a motor.

## Limitations

The fixed-size exponential-family distribution is a scoring representation of the A7 ranking, not a derived physical model of the lottery. Temperature calibration may be misspecified. The historical Blind OOS is not virgin after the wider SONAR research programme; Holm controls only the six A9 endpoints, not the complete historical Q00–Q141 research family.