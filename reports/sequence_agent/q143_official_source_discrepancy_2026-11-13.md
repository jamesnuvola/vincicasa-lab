# Q143 — Official source discrepancy and last-target sensitivity

**Observed at:** 2026-11-13, before the scheduled 20:00 VinciCasa draw.  
**Repository base:** 4a55fb7da216bd3850b79f862bf10b2cbcafa968.

## Source discrepancy

The repository canonical archive contains 3,406 draws through 2026-11-12. Its final row is contest 316 according to third-party historical archives, with numbers 2, 4, 7, 23, 33.

At the same check, Sisal's official "Ultima estrazione" page reported contest 315 dated 2026-11-11 as its latest result. I did not find an official Sisal result page confirming contest 316 on 2026-11-12. Third-party archives list contest 316, but they are not a substitute for the official source.

Therefore:
- Do not rewrite the canonical archive on this evidence alone.
- Treat the 2026-11-12 row as repository-present but official-source-unconfirmed at this check.
- Do not mark the 2026-11-13 target as drawn or reconcile its pending freezes.
- Preserve all existing freezes; no reconstruction or retuning.

## Q143 sensitivity excluding the final repository target

The primary Q143 analysis used the repository archive through 2026-11-12. As a source-quality sensitivity check, I removed only the final target (2026-11-12) from Blind OOS and recomputed the same four endpoints, without changing the 400-target prior-only model.

Blind OOS then contains 561 targets, 2025-04-30 through 2026-11-11:

| Metric | Rolling OLS | Rolling-400 mean | Uniform 2.5 |
|---|---:|---:|---:|
| MSE | 1.14273 | 1.13602 | 1.13057 |
| MAE | 0.88957 | 0.88805 | 0.88681 |

Baseline loss minus OLS loss (positive favours OLS):

| Endpoint | Improvement | Block-bootstrap 95% CI | Sign-flip p | Holm p (4) |
|---|---:|---:|---:|---:|
| MSE vs rolling mean | -0.00671 | [-0.01431; -0.00072] | 0.03715 | 0.14859 |
| MAE vs rolling mean | -0.00152 | [-0.00449; +0.00120] | 0.32728 | 0.32728 |
| MSE vs uniform | -0.01216 | [-0.02393; -0.00153] | 0.04355 | 0.14859 |
| MAE vs uniform | -0.00276 | [-0.00724; +0.00147] | 0.27194 | 0.54387 |

The sensitivity conclusion is unchanged: rolling OLS remains worse than both baselines; no endpoint survives Holm correction. This does not validate the unconfirmed last repository row; it only shows that removing it does not reverse Q143's negative conclusion.

## Next action

When Sisal publishes the 2026-11-12 result, reconcile it against the repository row before treating the 2026-11-13 forecast cutoff as fully source-confirmed. If the official result differs, quarantine the discrepancy and preserve the already-frozen forecasts unchanged. Continue Q60 append-only; no promotion.
