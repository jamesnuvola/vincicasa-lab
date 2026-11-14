# Q141-A19 — Residual Subspace Drift Detection

**Decision:** RESIDUAL_DRIFT_PREDICTIVE_VALUE_NOT_CONFIRMED

## Frozen quantitative hypothesis

Pre-target drift in a fixed 64-dimensional sketch must improve one-step-ahead capture MSE by at least 0.001 versus the prior-400 mean in both Validation and historical Blind OOS, with positive block-bootstrap lower bounds and Holm-adjusted block-signflip p<0.05.

## Design

- Source: Q7 commit 7a37cab601c5f9386131a00246963f8e4aeabf74; 1,023 masks and 3,386 target rows.
- Mask-lattice residual coordinates: 967D (embedded in 1023D); deterministic sketch dimension: 64; k=6.
- Drift: overlap change between adjacent 400-target windows, both ending before the target.
- Prediction: rolling one-feature OLS on the prior 400 drift/capture pairs.
- Scored targets: 2,186; splits {'discovery': 1311, 'validation': 437, 'blind_oos': 438}.

## Results

| Split | Targets | Mean drift | Mean capture | MSE gain vs mean400 | 95% block CI | MSE gain vs mean20 |
|---|---:|---:|---:|---:|---:|---:|
| discovery | 1311 | 0.149074 | 0.593936 | -0.000323 | [-0.000732, 0.000012] | 0.001998 |
| validation | 437 | 0.119258 | 0.634772 | -0.000120 | [-0.000443, 0.000196] | 0.001526 |
| blind_oos | 438 | 0.110172 | 0.631884 | -0.000291 | [-0.000706, 0.000087] | 0.000782 |

## Registered holdout tests

| Test | Raw p | Holm p |
|---|---:|---:|
| validation_mse_vs_mean400 | 0.770561 | 1.000000 |
| validation_mse_vs_mean20 | 0.001700 | 0.010199 |
| validation_drift_capture_corr | 0.120000 | 0.600000 |
| blind_oos_mse_vs_mean400 | 0.949503 | 1.000000 |
| blind_oos_mse_vs_mean20 | 0.191290 | 0.765162 |
| blind_oos_drift_capture_corr | 0.415000 | 1.000000 |

## Leakage and reproducibility

- Both subspace windows end at target index t (exclusive); the target profile is used only as the response.
- The rolling regression uses only the preceding 400 drift/capture pairs.
- Future-suffix mutation checks cover the pre-target drift and prediction at three target indices.
- Full deterministic replay and remote Git readback are delegated to the dedicated workflow.

## Limitations

- The 64-dimensional Gaussian sketch is a fixed approximation to the 967-dimensional residual space; results are conditional on the registered seed and projection.
- The 400-row windows overlap heavily, so observations are serially dependent; block bootstrap and block sign-flip are used, but sign-flip inference assumes block-level symmetry.
- The circular-shift correlation null preserves the marginal sequence of drift and capture within each holdout but does not preserve all cross-window dependence.
- The A19 design follows inspection of A18; historical Blind OOS is not virgin confirmation.
- Capture is a structural fit statistic derived from realized formula-rank profiles, not a measure of exact-ticket predictive accuracy.
- No production engine, canonical archive, forecast freeze or Q60 gate is modified.

## Next action

Keep A19 research-only. If results are not confirmed, do not tune the sketch seed or windows on this historical panel; instead freeze a prospective drift monitor and evaluate it unchanged.


Full deterministic replay: byte-identical (verified by the dedicated workflow).
