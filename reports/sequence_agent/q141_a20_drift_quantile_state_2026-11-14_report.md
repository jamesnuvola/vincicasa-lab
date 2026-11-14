# Q141-A20 — Drift Quantile-State Capture Audit

**Decision:** DRIFT_Q75_STATE_CAPTURE_SKILL_NOT_CONFIRMED

## Method

- Pinned source: Q141-A19 ledger; Git blob 5613d5176ed48dd63df186258a53039e65840555.
- Rolling window: 400; current state threshold: prior-only q75.
- Prediction: prior-400 mean capture in the same high/low state; minimum state count 25.
- First 400 Discovery rows are calibration-only.

## Results

| Split | N | High N | High rate | Mean capture | MSE gain vs mean400 | 95% block CI | MSE gain vs A19 OLS | Holm p vs mean400 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| discovery | 911 | 61 | 0.067 | 0.608676 | -0.000081 | [-0.000390, 0.000193] | 0.000241 | 1.000000 |
| validation | 437 | 179 | 0.410 | 0.634772 | -0.000336 | [-0.000689, 0.000068] | -0.000216 | 1.000000 |
| blind_oos | 438 | 118 | 0.269 | 0.631884 | -0.000034 | [-0.000397, 0.000308] | 0.000257 | 1.000000 |

## Holm-corrected tests

| Test | Raw p | Holm p |
|---|---:|---:|
| discovery_mse_gain_vs_mean400 | 0.688516 | 1.000000 |
| discovery_mse_gain_vs_a19_ols | 0.220039 | 1.000000 |
| validation_mse_gain_vs_mean400 | 0.972551 | 1.000000 |
| validation_mse_gain_vs_a19_ols | 0.887956 | 1.000000 |
| blind_oos_mse_gain_vs_mean400 | 0.596070 | 1.000000 |
| blind_oos_mse_gain_vs_a19_ols | 0.011499 | 0.068997 |

## Integrity

- Source rows are strict-prior; cutoff dates precede target dates.
- Each forecast uses 400 prior drift/capture pairs and current pre-target drift only.
- Mutating target response and all later rows leaves the probe prediction unchanged.
- Dedicated workflow performs tests, deterministic replay, and remote readback.

## Limitations

- q75 was selected as one nonlinear diagnostic after reviewing A19; historical holdouts are not virgin evidence.
- A19 source panel ends 2026-10-24 and is separate from main through 2026-11-13.
- The rolling windows overlap; block methods use length 20 and sign-flip assumes approximate block-level symmetry.
- State frequency varies with the drift distribution; high/low is a relative rolling state, not a fixed physical regime.
- Structural capture is not exact-ticket accuracy or probability of winning.
- No production engine, canonical archive, forecast freeze, Q60 gate, or protected PR is modified.

## Next action

Keep research-only. Do not tune additional thresholds on this panel; freeze a prospective drift-state monitor unchanged or retire this predictor family.
