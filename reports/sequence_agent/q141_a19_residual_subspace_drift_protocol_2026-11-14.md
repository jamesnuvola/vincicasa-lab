# Q141-A19 — Residual Subspace Drift Detection protocol

Date: 2026-11-14  
Status: frozen before the dedicated historical run  
Parent: Q141-A18 / PR #101  
Source: Q7 exhaustive formula panel, pinned commit `7a37cab601c5f9386131a00246963f8e4aeabf74`

## Quantitative hypothesis

A pre-target residual-subspace drift statistic, measured in a fixed 64-dimensional sketch of the A18 mask-residual profiles, improves one-step-ahead prediction of the next target's structural capture score versus the prior-400 mean by at least 0.001 MSE in both Validation and historical Blind OOS. Both holdouts must have a positive 95% circular block-bootstrap lower bound and Holm-adjusted one-sided block-signflip p below 0.05.

This is a forecast of a structural score, not a forecast of any candidate number or exact five-number ticket.

## Frozen construction

- Q7 source: 1,023 formula masks and 3,386 scored target profiles.
- Mask residualization: A18 design, intercept + 10 main effects + 45 pair interactions.
- Standardization: A17 scaler fitted on the first 400 target profiles only.
- Sketch: one fixed Gaussian 967×64 matrix, QR-orthonormalized; seed 1419001.
- Principal dimension: k=6.
- Subspace windows: two adjacent windows of 400 target profiles.
- Drift at target t: `1 - ||U_old.T @ U_recent||_F^2 / 6`; both bases use rows strictly before t.
- Capture response at t: energy share of the target residual sketch projected onto the recent six-dimensional basis. It is the response only, never a same-target predictor.
- Predictor: one-feature OLS with intercept, trained on the prior 400 observed (drift, capture) pairs; prediction clipped to [0,1]. No fitted hyperparameters.
- Primary baseline: prior-400 mean capture.
- Secondary baseline: prior-20 mean capture.
- First scored target index: 1200 (zero-based), after 800 rows to form drift and 400 prior labeled pairs.
- Chronological split: Discovery 1,311; Validation 437; historical Blind OOS 438.

## Inference

- Primary effect: baseline MSE minus drift-model MSE; positive favours drift.
- Practical threshold: +0.001 MSE in both holdouts.
- Confidence intervals: 20,000 circular block-bootstrap replicates, block length 20.
- Significance: 20,000 block-level sign-flip replicates, one-sided for positive MSE gain.
- Correlation diagnostic: Pearson correlation between drift and capture; 999 circular shifts of drift within each holdout, with shifts excluding the nearest 5% of the sequence.
- Holm correction across six registered holdout tests: two baselines × two holdouts plus one drift/capture correlation test per holdout.
- Discovery is descriptive; no discovery-driven retuning is permitted.

## Leakage and reproducibility controls

- Every drift feature uses two windows ending at t (exclusive).
- Every OLS fit uses only the preceding 400 completed (drift, capture) pairs.
- The current target capture is used only as the response after prediction.
- Future-suffix mutation checks must leave the pre-target drift and prediction unchanged.
- Q7 archive, walk-forward manifest, 34 rank parts and 11 formula chunks are SHA-verified by the inherited A17 loader.
- Dedicated CI must run unit tests, full experiment, isolated byte-identical replay, strict-prior ledger validation and remote Git readback.

## Limitations known before execution

- The 64-dimensional sketch approximates the 967-dimensional residual space and is conditional on the fixed seed.
- Rolling windows overlap; block inference is used, but block sign-flip assumes block-level symmetry.
- Circular-shift correlation tests do not preserve every cross-window dependency.
- A19 follows inspection of A18; historical Blind OOS is exploratory, not virgin confirmation.
- The response is a structural fit score, not number-level or ticket-level predictive accuracy.
- No production engine, canonical archive, forecast freeze or Q60 gate may be modified.

## Decision rule

Confirm only if both Validation and historical Blind OOS satisfy the practical MSE threshold, bootstrap lower bound >0, and Holm-adjusted p<0.05 against the prior-400 mean. Otherwise record a negative or inconclusive result and do not tune the sketch seed, window sizes or regression after viewing the holdouts.
