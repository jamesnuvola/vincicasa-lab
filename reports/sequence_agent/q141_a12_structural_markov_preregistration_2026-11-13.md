# Q141-A12 — Structural Markov audit

**Protocol status:** retrospective exploratory diagnostic. This protocol was written after prior historical exploration and is not a prospective preregistration or a virgin confirmatory test.

## Quantitative hypothesis

Test whether the previous category of each of nine non-differenced structural streams improves next-draw category forecasts over an expanding marginal-frequency baseline. The practical target is at least **+0.005 nats per feature** of mean log-loss gain and at least **+0.001** mean multiclass Brier gain on the chronological historical holdout.

Separately test whether apparent skill in 'sum_transition' and 'range_transition' exceeds what is expected under independent uniform unordered 5-of-40 draws. Adjacent first differences share the middle draw, so a positive lag-1 score is not automatically evidence of predictable lottery outcomes.

## Fixed model

- Structural streams: 'sum_bin', 'range_bin', 'odd_cat', 'low_cat', 'overlap_cat', 'gap1_bin'–'gap4_bin', 'sum_transition', 'range_transition' (51 fixed categories across 11 streams).
- Baseline: expanding marginal category frequency with symmetric Dirichlet alpha 0.5 per category.
- Markov: one-step transition row shrunk toward the same prior-only marginal distribution with fixed alpha 20.
- Warmup: 400 matrix rows. Each target uses only categories from rows strictly before the target.
- First undefined transition row is excluded from all training histories.
- No parameter search or retuning.

## Chronological design

- Source: pinned Q141-A7 artifact run 43348144964, artifact 14003350043.
- Canonical archive blob: '6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb'; matrix SHA-256: '81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047'.
- 3,356 target rows; 400-row warmup; 2,956 scored targets.
- 60/20/20 chronological split: Discovery 1,774; Validation 591; historical Blind OOS 591.
- Metrics: multiclass log loss and Brier score, baseline minus Markov (positive is better).
- Inference: circular moving-block bootstrap, block length 20, 20,000 replicates; HAC lag 20; Holm across nine core-feature tests.
- Mechanical null: 2,000 independent uniform 5-of-40 sequences, same length and same scorer; empirical upper-tail tests for log-loss and Brier of both difference features, Holm across four tests.

## Interpretation limits

The historical Blind OOS has been exposed to prior SONAR research and is exploratory, not virgin confirmation. The two difference features are mechanically dependent under IID draws because adjacent differences share one underlying draw. This experiment forecasts structural categories, not numbers or exact tickets. A positive historical score cannot justify model promotion. Any follow-up must be separately frozen and evaluated prospectively.

## Governance

No canonical archive mutation, no shadow or active-engine mutation, no forecast rewrite, no model promotion, no merge or rebase. PRs #6, #7 and #8 remain untouched.
