# Q141-A25 — Mask-Cardinality Conditional Dynamics

**Decision:** NO_MASK_CARDINALITY_PERSISTENCE_LIFT_DEMONSTRATED

**Classification:** exploratory post-hoc decomposition of the exposed A24 panel; not confirmatory preregistration.

## Design

- 1,023 Q7 masks partitioned by cardinality: low 1–3 (175), central 4–7 (792), high 8–10 (56).
- 138 Q75-high rows; 40 warm-up; 98 strict-prior forecasts.
- Discovery / Validation / historical Blind OOS exposed: 58 / 20 / 20.
- Persistence-1 compared with Mean-20; Mean-40 is descriptive secondary context.
- 20,000 block-sign-flips and circular moving-block bootstrap replicates; block lengths 5, 10, 20; Holm family 12.

## Split results

| Split | Stratum | n formulas | Persistence MSE | Mean-20 MSE | Mean-40 MSE | Gain vs Mean-20 | Relative gain |
|---|---|---:|---:|---:|---:|---:|---:|
| discovery | low | 175 | 0.125665 | 0.063930 | 0.063322 | -0.061734 | -96.57% |
| discovery | central | 792 | 0.085043 | 0.043047 | 0.042333 | -0.041995 | -97.56% |
| discovery | high | 56 | 0.254360 | 0.134783 | 0.131674 | -0.119577 | -88.72% |
| validation | low | 175 | 0.102997 | 0.055864 | 0.055399 | -0.047133 | -84.37% |
| validation | central | 792 | 0.079663 | 0.041705 | 0.041970 | -0.037958 | -91.02% |
| validation | high | 56 | 0.115037 | 0.063095 | 0.063354 | -0.051942 | -82.32% |
| blind_oos_exposed | low | 175 | 0.127619 | 0.064567 | 0.063275 | -0.063052 | -97.65% |
| blind_oos_exposed | central | 792 | 0.071743 | 0.035717 | 0.035544 | -0.036026 | -100.87% |
| blind_oos_exposed | high | 56 | 0.300102 | 0.177030 | 0.180228 | -0.123071 | -69.52% |

## Inferential checks

| Endpoint | Block | Mean gain | p raw | p Holm | Bootstrap 95% CI |
|---|---:|---:|---:|---:|---|
| low_L5 | 5 | -0.055092 | 1.000000 | 1.000000 | [-0.072979, -0.039398] |
| low_L10 | 10 | -0.055092 | 1.000000 | 1.000000 | [-0.072093, -0.041407] |
| low_L20 | 20 | -0.055092 | 1.000000 | 1.000000 | [-0.067052, -0.043097] |
| central_L5 | 5 | -0.036992 | 1.000000 | 1.000000 | [-0.052077, -0.022799] |
| central_L10 | 10 | -0.036992 | 1.000000 | 1.000000 | [-0.044992, -0.027096] |
| central_L20 | 20 | -0.036992 | 1.000000 | 1.000000 | [-0.044024, -0.029961] |
| high_L5 | 5 | -0.087507 | 1.000000 | 1.000000 | [-0.158732, -0.039577] |
| high_L10 | 10 | -0.087507 | 1.000000 | 1.000000 | [-0.156207, -0.044315] |
| high_L20 | 20 | -0.087507 | 1.000000 | 1.000000 | [-0.127547, -0.047466] |
| high_minus_low_L5 | 5 | -0.032414 | 0.780711 | 1.000000 | [-0.106657, 0.019643] |
| high_minus_low_L10 | 10 | -0.032414 | 0.753412 | 1.000000 | [-0.104393, 0.014989] |
| high_minus_low_L20 | 20 | -0.032414 | 1.000000 | 1.000000 | [-0.069562, 0.004617] |

## Parent A24 parity

Maximum absolute per-target MSE difference after weighted reconstruction: **NaN** (required < 1e-9).

## Interpretation and limits

- This is a post-hoc decomposition because the A24 panel and outcomes were already exposed.
- All 138 source rows are Q75-high-state; no inference is made about low-state periods.
- The 40-row pooled Validation plus exposed Blind OOS panel is small and temporally dependent.
- Mask cardinality is a combinatorial complexity stratum, not a semantic AST family or a set of independent formula observations.
- The final 20-target historical Blind OOS was visible in A21-A24 and is not virgin confirmation.
- The endpoint is formula-rank residual-vector MSE, not winning-number accuracy, exact-ticket probability, or monetary return.
- Holm correction covers the 12 registered A25 endpoints only, not the full Q00-Q141 research family.

## Next action

Stop adding persistence variants if no stratum passes. Continue the common-source typed-AST evaluator with identical strict-prior cutoffs and separate per-number and quintet endpoints; keep prospective freezes append-only.

No production promotion, merge, archive mutation, Q60 update or freeze change.
