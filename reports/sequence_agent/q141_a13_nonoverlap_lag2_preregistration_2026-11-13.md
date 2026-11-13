# Q141-A13 — Non-overlapping lag-2 structural transitions

**Protocol status:** historical exploratory diagnostic, written before A13 execution. It follows the Q141-A12 mechanical-dependence diagnosis and is not a virgin confirmatory test.

## Quantitative hypothesis

Q141-A12 found that adjacent first differences of sum and range have strong negative lag-1 dependence because adjacent differences share the middle draw. A13 tests a distinct relation: whether the category of a first difference at row (t-2) contains information about the category at row (t), after removing all raw-draw overlap between training examples and the target.

The registered practical thresholds are:
- pooled mean log-loss gain (baseline minus lag-2 model): **+0.005 nats per target**;
- pooled mean multiclass Brier gain: **+0.001 per target**.

Positive gain favours the lag-2 model.

## Fixed streams and model

- Streams: `sum_transition`, `range_transition`, using the exact fixed vocabularies and bin boundaries from the pinned Q141-A12 builder.
- Forecast: (P(Y_tmid Y_{t-2})), with transition counts from prior training endpoints only.
- Baseline: expanding marginal category frequency computed on exactly the same phase-matched training endpoints.
- Baseline Dirichlet smoothing: (alpha=0.5) per category.
- Transition row shrinkage toward that baseline: (alpha_T=20).
- No parameter search, feature selection, or bin retuning.

## Mechanical non-overlap construction

For target index (t), retain training endpoints (s) satisfying:
- (s equiv t pmod 4);
- (s le t-4);
- (sge4).

A training transition uses (Y_{s-2}ightarrow Y_s). Since each first difference uses two consecutive draw rows, that example consumes raw draw rows ([s-3,s]). Training endpoints are spaced by four, so these four-row blocks are pairwise disjoint. The target transition (Y_{t-2}ightarrow Y_t) consumes rows ([t-3,t]), disjoint from the latest training block ending at (t-4).

The modulo-4 phase-matched marginal baseline uses the same training endpoints, so the comparison isolates transition information rather than giving the model a different sample.

## Chronological design

- Source artifact: Q141-A7 workflow run **43348144964**, artifact **14003350043**.
- Canonical archive Git blob SHA-1: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
- Feature matrix SHA-256: `81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047`.
- Q141-A12 feature-builder Git blob SHA-1: `208035ce9d2e949b47cf4caa9cf2ddf71018348c`.
- 3,356 source rows; 400-row warmup; 2,956 strict-prior targets.
- Chronological split 60/20/20: Discovery 1,774; Validation 591; historical Blind OOS 591.
- Primary endpoint: pooled two-stream mean log-loss gain on Blind OOS.
- Secondary endpoint: pooled two-stream mean Brier gain on Blind OOS.
- Confirmatory Holm family: the two pooled endpoints.
- Separate exploratory Holm family: four stream-specific metric tests.
- Uncertainty sensitivity: circular moving-block bootstrap, block length 20, 20,000 replicates.
- Mechanical null: 2,000 independent uniform unordered 5-of-40 sequences, scored with the exact same modulo-4 phase sampler; fixed seed `14111313`.

## Integrity gates

- Pin and verify source matrix, archive and A12 feature-builder hashes.
- All target cutoffs must precede target dates.
- Training endpoints must match target phase modulo 4 and end no later than (t-4).
- Training four-draw blocks must be pairwise disjoint and disjoint from target block ([t-3,t]).
- Future-suffix mutation must not change a frozen target score.
- Full replay must be deterministic.
- Baseline and transition probabilities must each sum to one.

## Interpretation and governance

The historical Blind OOS has already been exposed to prior SONAR research and is exploratory, not virgin confirmation. The IID simulation assumes independent uniform 5-of-40 draws; it is a statistical reference, not a physical mechanism model. A13 forecasts two structural categories, not individual numbers or exact tickets. Even a positive historical result would require a separate prospective preregistration and human review.

Do not alter B11 or any other frozen forecast. Do not mutate the canonical archive, active engine or shadow forecasts. No merge, rebase or engine promotion. PRs #6, #7 and #8 remain untouched.
