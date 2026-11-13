# Q141-A12 — supplementary mechanical-dependence diagnostic

**Status:** explanatory diagnostic on the same pinned historical source; not a separate confirmatory test.

## Source
- Q141-A7 artifact run: 43348144964
- Artifact ID: 14003350043
- Canonical archive blob SHA-1: 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb
- Feature matrix SHA-256: 81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047
- Draws evaluated for this diagnostic: 3,356 (2017-09-05 through 2026-11-12)

## Measured lag-1 correlations

| Series | Level autocorrelation | First-difference autocorrelation |
|---|---:|---:|
| Sum of five numbers | +0.023838 | -0.494887 |
| Range (max - min) | +0.002440 | -0.509954 |

The corresponding first-difference covariances and level variances are:

| Quantity | Sum | Range |
|---|---:|---:|
| Cov(ΔX_t, ΔX_(t-1)) | -585.534254 | -46.493739 |
| Var(X_t) | 605.958463 | 45.674575 |
| -Cov(ΔX_t, ΔX_(t-1)) / Var(X_t) | 0.966294 | 1.017935 |

## Root cause

For an independent level series X_t, define D_t = X_t - X_(t-1). Then:

`Cov(D_t, D_(t-1)) = -Var(X_t)`,

and, when adjacent level variances are equal, the lag-1 correlation of differences is approximately -0.5. The measured correlations are close to this mechanical signature while the level autocorrelations remain near zero.

Therefore, the positive one-step Markov log-loss gain on sum_transition and range_transition is not by itself evidence that the next lottery draw is predictable. Adjacent difference categories inherit dependence because they share the middle draw.

The IID 5-of-40 control confirms this interpretation: the observed Blind OOS log-loss gain for range_transition has raw empirical p=0.026487, but Holm-adjusted p=0.105947 across the four difference-feature/metric comparisons. The sum-transition log-loss comparison is not positive relative to the IID null (raw p=0.983508). No mechanical-feature test survives Holm.

## Decision

Exclude these two first-difference streams from any aggregate claim of predictive skill unless a future prospective protocol demonstrates incremental value beyond the IID mechanical null. Do not promote the Markov selector or modify existing frozen forecasts.
