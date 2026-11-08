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
Preserve all positive point estimates, keep prospective freezes append-only, and examine calibration/state null controls before a new hypothesis.