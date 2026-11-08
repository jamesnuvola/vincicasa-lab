# SONAR PSR-06 — Previous-Draw Range-State Position Marginals

**Status:** exploratory protocol, no engine promotion.  
**Branch:** research/sonar-psr06-range-conditioned-geometry-20261108  
**Isolation:** does not change the active engine or PR #6/#7/#8.

## Hypothesis
The full range R of the immediately preceding draw may condition the next ordered-position marginal distribution. Under the ideal independent-draw model it should not; the experiment measures whether a small, theoretically defined conditioning state shows stable empirical lift or merely sampling variance.

## Exact state definition
For a uniform 5-subset of 1..40:
Pr(R=r) = (40-r) C(r-1,3) / C(40,5), r=4..39.
Exact theoretical quartile cutpoints are 23, 28, 33. States:
- R <= 23
- 24 <= R <= 28
- 29 <= R <= 33
- R >= 34

These cuts are derived from the combinatorial range distribution, not from the dataset or target outcomes. Their theoretical state masses are approximately 27.99%, 24.28%, 27.32%, 20.40%.

## Model
Exact positional prior:
pi_i(n) = C(n-1,i-1) C(40-n,5-i) / C(40,5), n=i..35+i.
Conditional state model:
qS_i,t(n|s) = [c_i,t,s(n) + alpha*pi_i(n)] / [N_t,s + alpha].
Global comparator, same alpha:
qG_i,t(n) = [c_i,t(n) + alpha*pi_i(n)] / [N_t + alpha].

The predictor state is the range of draw t-1, known before target draw t. Training rows j=2..t-1 use the range of draw j-1 as feature and draw j as outcome. Strict prefix expected train_n=t-2. Warmup 300.

## Selection and inference
Alpha grid fixed: 50, 100, 200, 500. Select alpha per position using validation mean Brier improvement vs global shrinkage with the same alpha; ties choose lower alpha. Chronological split: 50% discovery, next 25% validation, final 25% blind OOS. Primary endpoint: paired Brier improvement on blind OOS vs global comparator. Circular moving-block bootstrap: block 7, 2,000 replicates, fixed seed base 20261108; Holm correction across five position-level primary tests.

## Controls
- Archive Git blob SHA checked against the pinned canonical history.
- Strict-prefix and cutoff chronology assertions at every target.
- Exact prior and conditional probability normalization assertions.
- Duplicate grid key and expected row-count checks.
- Persisted JSON/Markdown, selected target ledger and validation alpha grid.
- Re-run on CI and byte-diff committed outputs for reproducibility.

## Limits
The historical blind partition overlaps previous PSR experiments, so it is not untouched lab-wide evidence. Five marginal positions are dependent; this is not a joint-ticket model. Historical state association is not causal and may be noise. No promotion or merge without prospective independent validation and human review.

## Next action
Preserve PSR-06 P3 as an exploratory positive point estimate only. The next iteration is a fixed prospective P3-only shadow freeze with alpha=500 and the four theoretical range states unchanged; score paired Brier vs the exact order-statistic prior as primary, with log-loss and Top-1/Top-5 secondary. Do not tune on the historical blind OOS. Accumulate 200 complete prospective paired targets before inference; correct any multi-endpoint family and compare with global shrinkage and the active engine. The five-position PSR-06 model remains null/no promotion.

## Execution record — 2026-11-08

- GitHub Actions CI run #640 (run ID 42477089443) completed **success** on this isolated branch. The PSR-06 step, archive SHA pin, strict-prefix assertions, probability normalization, report generation, upload and persistence step all passed.
- Canonical archive: 3,401 draws through 2026-11-07; Git blob SHA `5d2efd70684e918b27d8f06386d545647898336d`.
- Persisted results: 3,101 walk-forward targets (1,550 discovery / 775 validation / 776 blind OOS), 15,505 selected target-position ledger rows and 62,020 internal alpha-grid rows. The exact validation grid is 20 aggregate rows.
- Validation selected alpha=500 for all five positions (upper end of the fixed grid). Blind OOS paired Brier improvements vs global shrinkage: P1 −0.000966533 (95% block CI [−0.001770376, −0.000184973]); P2 −0.000533459 (CI [−0.001081021, +0.000011431]); P3 +0.000071761 (CI [−0.000399809, +0.000546137]); P4 −0.000326438 (CI [−0.000918608, +0.000286634]); P5 −0.000182730 (CI [−0.000917556, +0.000529922]). One-sided raw p-values are 0.991004, 0.972014, 0.400300, 0.840580, 0.675162; all Holm-adjusted p-values are 1.000000.
- P3 remains a weak exploratory positive point estimate only; its CI includes zero and Holm p=1. P1 shows a negative Brier improvement whose nominal CI is below zero. No lift survives inference; no promotion.
- Artifact ZIP #13615813503 was downloaded. The Git blob SHA of each of the five files (protocol, JSON, Markdown, target ledger, validation grid) computed from the ZIP matched the corresponding repository SHA exactly. Target ledger counts, per-split rows, unique date-position keys, train_n=t−2, validation-grid cardinality and FNV fingerprints all passed local artifact audit.
- Next CI run must reproduce the committed PSR-06 result files byte-for-byte. The historical blind split is not lab-wide untouched; prospective shadow evidence remains separate.


## Supplemental root-cause control — range-state marginal goodness-of-fit

A chi-square goodness-of-fit diagnostic compared the prior-draw range-state frequencies in the selected target ledger with the exact theoretical state masses. This is a marginal-distribution control only; it does not test predictive dependence.

- All walk-forward targets (N=3,101): observed counts [898, 777, 800, 626] for states Q1–Q4; expected [868.01, 753.07, 847.33, 632.60]; chi-square(3)=4.508879, raw p=0.211500.
- Discovery (N=1,550): observed [465, 396, 382, 307]; expected [433.86, 376.41, 423.53, 316.20]; chi-square(3)=7.592791, raw p=0.055222.
- Validation (N=775): observed [213, 181, 208, 173]; expected [216.93, 188.21, 211.76, 158.10]; chi-square(3)=1.818740, raw p=0.610865.
- Blind OOS (N=776): observed [220, 200, 210, 146]; expected [217.21, 188.45, 212.04, 158.30]; chi-square(3)=1.719265, raw p=0.632659.
- Holm adjustment across the three split-specific checks: discovery p=0.165665; validation p=1.000000; blind OOS p=1.000000. None is significant at 0.05. The full-window check is reported descriptively and overlaps these partitions.

Interpretation: the range-state predictor's marginal frequency is not detectably inconsistent with the exact combinatorial distribution in this walk-forward sample after split-wise correction. This does not establish independence, but it supplies no evidence that the PSR-06 null result is caused by a gross state-frequency imbalance. The weak P3 positive remains calibration/score inconsistent and is not promoted.


## Next iteration after the range-state marginal control

Register and freeze the P3-only candidate prospectively before target outcomes are available. Keep the selected alpha=500, exact theoretical state cutpoints (23, 28, 33), and model formula fixed. Record the full probability vector, Brier, log-loss, Top-1/Top-5, global-shrinkage comparator and exact prior comparator per target. Use append-only freezes; do not retroactively fill or replace forecasts. Require 200 paired prospective targets and human review before any promotion consideration. This shadow action is a plan, not an execution or validation claim.
