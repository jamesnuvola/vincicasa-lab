# Q141-A26 — Typed-AST semantic mapping and operator-group transfer ablation

Status: COMPUTED_REPLAY_VERIFIED
Decision: NO_SEMANTIC_OPERATOR_SUBGROUP_INCREMENTAL_LIFT_DEMONSTRATED

## Structural semantic audit
Q90: 330,429 typed ASTs; Q7: 1,023.
Shared concepts: cooccurrence, gap_structure, number_occurrence, position_rank, sum_regime.
Q90-only: neighbourhood, novelty, transition. Q7-only: decade_composition, parity.
Shared concept coverage: Q90 features 70.0%; Q7 families 80.0%.
No cross-output raw AST equality; exact cross-type equivalence is prohibited. Coarse signatures are relatedness, not functional identity.

| Split | n | Q7+Q80 baseline MAE | Linear-only MAE | Nonlinear-only MAE | All-Q90 MAE |
|---|---:|---:|---:|---:|---:|
| discovery | 1872 | 0.203908 | 0.204730 | 0.205114 | 0.204763 |
| validation | 657 | 0.202259 | 0.203236 | 0.203329 | 0.203550 |
| blind_oos | 657 | 0.205230 | 0.205141 | 0.204900 | 0.205358 |

## Blind OOS primary tests

| Model | MAE gain | 95% block CI | p raw | p Holm | Gate |
|---|---:|---:|---:|---:|---|
| m1_linear | +0.000089 | [-0.000945, +0.001085] | 0.439328 | 0.439328 | FAIL |
| m2_nonlinear | +0.000330 | [-0.000546, +0.001188] | 0.205490 | 0.410979 | FAIL |

Full-Q90 reproduction-control gain: -0.000128.
C5 parity: 24 metrics; max absolute error 4.673e-15.

## Limits

3,186 strict-prior forecasts; 100 warm-up rows; 50-target feature window.
Discovery is expanding-prequential; Validation and Blind coefficients are frozen after Discovery.
Q90 has 330,429 ASTs, but the behaviour ledger is a fixed 700-formula sample. Q90 selected 20 of 59 features.
Q7 and Q90 cutoffs differ; only 3,286 exact aligned targets are used. Historical Blind OOS is exposed and this decomposition is exploratory.
Endpoint is Q7 formula-universe rank quality, not winning-number or exact-ticket prediction. Holm covers two A26 tests only.

Replay verified: True.

Next: rebuild Q90 and Q7 from one identical current canonical archive and collect genuinely prospective common-source targets; do not tune on this exposed Blind OOS.
