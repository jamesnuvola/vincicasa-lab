# Q141-A14 — Rolling conditional family-information audit

**Decision:** `NO_FAMILY_CONDITIONAL_LIFT_DEMONSTRATED`

- Source: Q141-A7 artifact 14003350043; matrix SHA-256 `81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047`.
- Archive Git blob SHA-1: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
- Scored targets: 2956 (warm-up 400); splits: Discovery 1774, Validation 591, Blind OOS 591.
- Model: rolling 400-target ridge, alpha=1000; 59 features in seven fixed families.

## Top-5 hit share by split

| Split | Full ridge | Equal feature | Equal family | Uniform expectation |
|---|---:|---:|---:|---:|
| discovery | 0.125366 | 0.125479 | 0.124126 | 0.125000 |
| validation | 0.126565 | 0.124873 | 0.123519 | 0.125000 |
| blind_oos | 0.117766 | 0.127919 | 0.127919 | 0.125000 |

## Blind OOS family ablations

| Family removed | Full − ablated Top-5 share | 95% block CI | p Holm (9) |
|---|---:|---:|---:|
| baseline | -0.002707 | [-0.015567, +0.009137] | 1.000000 |
| ewma_hit_dynamics | +0.001015 | [-0.004738, +0.006768] | 1.000000 |
| gap_dynamics | -0.001692 | [-0.010152, +0.006768] | 1.000000 |
| cooccurrence_novelty | +0.003384 | [-0.005415, +0.012183] | 1.000000 |
| rank_trajectory | +0.002707 | [-0.006091, +0.010829] | 1.000000 |
| residual_surprise | +0.000338 | [-0.001354, +0.002369] | 1.000000 |
| regime_transition_affinity | -0.005076 | [-0.013536, +0.003723] | 1.000000 |

## Full model versus simple baselines

| Comparison | Top-5 share delta | 95% block CI | p Holm (9) |
|---|---:|---:|---:|
| Full − equal feature | -0.010152 | [-0.025381, +0.004399] | 1.000000 |
| Full − equal family | -0.010152 | [-0.026058, +0.004738] | 1.000000 |

## Interpretation and limits

The full ridge is below both simple ranking baselines in Blind OOS. Co-occurrence/novelty and rank-trajectory ablations have positive point estimates, but neither reaches the +0.005 practical threshold; all nine primary comparisons have Holm-adjusted p-values of 1.0.
The historical Blind OOS is exposed to previous SONAR exploration and is not virgin prospective confirmation. This experiment ranks individual numbers; it does not estimate exact quintet probabilities. Feature families share upstream history. The fixed ridge alpha/window were not tuned.
No engine, archive, shadow forecast, prospective freeze, Q60 gate or protected PR #6/#7/#8 was modified.
