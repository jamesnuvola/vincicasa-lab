# Q141-A23 — Multivariate Conditional Block-Null Audit

**Decision:** MULTIVARIATE SHIFT NOT CONFIRMED  
**Data:** 118 reference targets (2026-06-29–2026-10-24) and 20 extension targets (2026-10-25–2026-11-13); 1,023 formula-rank dimensions, residualized to 967 dimensions.

## Result

- Observed energy distance: **0.669682**
- Observed mean-shift RMS: **0.065404**
- Full-vector moving-block null: 20,000 replicates at each block length 5, 10 and 20; six tests corrected together by Holm.

| Block | Energy null median | Energy null q95 | Energy p raw | Energy p Holm | Mean-shift p raw | Mean-shift p Holm |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 0.389887 | 0.692570 | 0.058947 | 0.172191 | 0.082046 | 0.172191 |
| 10 | 0.350642 | 0.645790 | 0.042398 | 0.169592 | 0.057397 | 0.172191 |
| 20 | 0.347880 | 0.467689 | 0.000050 | 0.000300 | 0.008500 | 0.042498 |

The energy-distance result is significant only at block length 20 after Holm; block lengths 5 and 10 are not significant. The mean-shift endpoint is significant only at block length 20. The pre-registered robustness rule requires energy significance at all three block lengths and mean-shift significance at two or more. It therefore **fails**.

## Historical model context (inherited, not recomputed)

| Split | Targets | Q75 MSE gain vs mean-400 | Q75 MSE gain vs A19 OLS |
|---|---:|---:|---:|
| Discovery | 911 | -0.000081 | 0.000241 |
| Validation | 437 | -0.000336 | -0.000216 |
| Blind OOS | 438 | -0.000034 | 0.000257 (Holm p=0.068997) |

These split metrics are inherited from A20/A21/A22 and are not evidence that A23 predicts draw numbers. The 20-target extension is retrospective and already exposed to prior SONAR analysis.

## Limits and next step

The null preserves complete contemporaneous formula vectors and local temporal blocks, but assumes the preceding 118-target high-state run is a valid stationary continuation reference. The test concerns formula-profile distribution shift only—not exact-ticket accuracy or win probability. Keep the 14 November A21 freeze unchanged; wait for the official result and continue prospective monitoring without retuning.
