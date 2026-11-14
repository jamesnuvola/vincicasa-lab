# Q141-A26 — Typed-AST semantic mapping and operator-group transfer ablation

**Protocol frozen:** 2026-11-14 09:38 Europe/Rome.  
**Status:** post-hoc decomposition; the historical Blind OOS was already exposed.

## Hypothesis
At least one Q90 typed-AST operator subgroup—linear_mean or nonlinear pairwise_interaction plus conditional_gate—improves the Q7+Q80 prior-only meta-quality baseline by at least 0.005 MAE in historical Blind OOS. Acceptance also requires a 20-target moving-block 95% CI lower bound above zero and Holm-adjusted one-sided block-sign-flip p below 0.05.

## Models
- M0: Q7 rolling-50 mean formula percentile plus Q80 rolling-50 equal-family state.
- M1: M0 plus Q90 linear_mean_L4..L8 state.
- M2: M0 plus Q90 pairwise_interaction_I4 and conditional_gate_G4 state.
- M3: M0 plus all seven Q90 operator-family states; reproduction control against Q141-C5.

## Walk-forward contract
Q7 supplies 3,286 aligned target rows: Discovery 1,972, Validation 657, Blind OOS 657. First 100 rows are warm-up; rolling feature window is 50. Discovery fits expand prequentially using only earlier scored targets. Validation and Blind coefficients are frozen after Discovery. Current and future Q7/Q80/Q90 outcomes are excluded from every predictor.

## Typed semantic contract
Q90 has 330,429 imported per_number_score ASTs; Q7 has 1,023 quintet_score ASTs. Output types and candidate universes differ. The ontology records broad related concepts only; no exact cross-output equivalence or formula pooling is allowed. Q90 behaviour is represented by a fixed 700-formula sample, not all 330,429 ASTs.

## Source and limits
Source branch research/q141-formula-universe-behaviour-mapping-20261112 is pinned to commit 6bc727a46c65fecceff3410a7a635e42c62b4af5. Q7 cutoff 2026-10-24; Q90 cutoff 2026-11-07. Historical Blind OOS is not virgin prospective evidence. Holm covers two A26 tests only, not the entire Q00-Q141 family. The estimand is Q7 formula-universe rank quality, not a winning-number forecast.

No merge, archive mutation, shadow insertion or engine promotion. PRs #6, #7 and #8 remain untouched.
