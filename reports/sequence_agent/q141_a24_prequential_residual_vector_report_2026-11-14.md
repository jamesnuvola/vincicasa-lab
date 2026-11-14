# Q141-A24 — Prequential Residual-Vector Forecast Audit

**Status:** PERSISTENCE_VECTOR_LIFT_NOT_CONFIRMED  
**Scope:** research-only; no candidate-number or winning-probability claim.

## Design

- 1,023 formula residual coordinates; fixed mask rank 56; residual rank 967.
- 138 source rows, all Q75-high; 40-row warm-up; 98 one-step forecasts.
- Discovery / Validation / historical Blind OOS exposed: 58 / 20 / 20.
- Persistence-1 compared with prior-20 and prior-40 vector means.
- Holdout inference uses the 40 Validation+Blind rows, block lengths 5/10/20, 20,000 block sign-flips and 20,000 circular block-bootstrap replicates; Holm across six endpoints.

## Results

| Split | Targets | Persistence MSE | Mean20 MSE | Mean40 MSE | Gain vs Mean20 | Relative gain |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 58 | 0.107124388304 | 0.054631879571 | 0.053756973933 | -0.052492508733 | -0.960840248327 |
| Validation | 20 | 0.090547875093 | 0.047921339319 | 0.048069166206 | -0.042626535774 | -0.889510526616 |
| Blind OOS exposed | 20 | 0.099234148373 | 0.051189880639 | 0.05100002161 | -0.048044267733 | -0.938550102737 |

## Inference

| Endpoint | Block | Gain | p raw | p Holm | Bootstrap 95% CI |
|---|---:|---:|---:|---:|---|
| persistence1_vs_mean20_L5 | 5 | -0.045335401754 | 1 | 1 | [-0.060001953749, -0.0313870203] |
| persistence1_vs_mean20_L10 | 10 | -0.045335401754 | 1 | 1 | [-0.054901890745, -0.034722648774] |
| persistence1_vs_mean20_L20 | 20 | -0.045335401754 | 1 | 1 | [-0.053371229098, -0.037299574409] |
| persistence1_vs_mean40_L5 | 5 | -0.045356417825 | 1 | 1 | [-0.059685494557, -0.031646129763] |
| persistence1_vs_mean40_L10 | 10 | -0.045356417825 | 1 | 1 | [-0.054707956754, -0.035140285571] |
| persistence1_vs_mean40_L20 | 20 | -0.045356417825 | 1 | 1 | [-0.053261877531, -0.037585447354] |

## Limits

- All 138 multivariate source rows are Q75-high-state rows; conclusions are conditional on this selected regime.
- The 20-row historical Blind OOS segment was already visible in A21-A23 and is exposed exploratory evidence, not a virgin holdout.
- The 40-row pooled Validation plus Blind OOS inference is dependent on the chosen chronological segmentation; only the last 20 rows are labelled Blind OOS exposed.
- Block sign-flip assumes approximate symmetry and exchangeability of block-level paired loss sums.
- The forecast target is the next formula-rank residual vector, not the next winning quintet, exact-ticket probability, or monetary return.
- Residual coordinates are 1,023 ambient coordinates with a fixed 56-dimensional mask subspace removed; loss is normalized by residual rank 967.
- This test does not establish causal or physical dynamics and does not validate Q75 as a predictor.

No production promotion, no merge, no freeze mutation. The historical Blind OOS is exposed.
