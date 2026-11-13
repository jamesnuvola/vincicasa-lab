# Q141-A14 — Rolling conditional family-information audit

**Protocol status:** retrospective exploratory methodology note, written after the first local exploratory run. This is not a preregistration and not a virgin confirmatory test. The 59-feature matrix and prior Q141 results were already known.

## Hypothesis

A feature family contributes unique predictive information if a fixed rolling model using all 59 features has a higher next-target Top-5 hit share than the same model refit after removing that family. The interpretation threshold is +0.005 hit share (0.025 hits per draw); it was fixed for the final replay after an initial exploratory computation.

## Fixed model

- Source: Q141-A7 artifact run 43348144964, artifact 14003350043.
- Pinned matrix SHA-256: `81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047`.
- Canonical archive blob SHA-1: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
- 59 features partitioned into seven fixed families per the Q141-A7 report.
- For each target, each feature is z-scored across the 40 candidate numbers; zero-variance features become zero.
- Ridge regression, alpha=1000, no intercept (within-target centered features); fixed rolling window=400 previous target rows.
- Each target is scored before its labels are added to the rolling sufficient statistics.
- Variants: full 59 features; seven leave-one-family-out models; equal-feature and equal-family untrained ranking baselines.
- Tie-break: smaller number first. No parameter search or outcome-dependent feature selection.

## Walk-forward and inference

- 3,356 source target rows; first 400 used only for warm-up; 2,956 scored targets.
- Chronological scored-target splits: 60% Discovery, 20% Validation, 20% historical Blind OOS.
- Primary endpoint: Blind OOS per-target Top-5 hit share (hits/5). Uniform reference = 0.125.
- Analysis family: full model minus each of seven leave-one-family-out models, plus full minus equal-feature and equal-family baselines (9 comparisons). Holm is applied within this family only.
- Practical threshold: +0.005 share. A positive historical finding would require a positive 95% block-bootstrap lower bound and Holm-adjusted one-sided block-signflip p<0.05; because this note follows the first exploratory run, the result remains exploratory.
- Block length=20; 20,000 bootstrap and 20,000 block-signflip replicates; HAC lag-20 sensitivity.
- Top-10 and Top-20 are secondary descriptive endpoints.

## Leakage controls

- Target t is fitted only from rows [t-400,t); target t is added only after its score is frozen.
- Feature normalization uses only the current target's 40 feature values, never target labels.
- Source cutoffs must precede target dates.
- Future-suffix mutation must leave target-t scores unchanged.
- Deterministic replay and exact source hash are required.

## Limits and governance

Historical Blind OOS is exposed to prior SONAR research. This model predicts per-number ranking, not exact quintet probability. Feature families share upstream data. Holm covers the nine comparisons in this report only, not the full historical research family. No archive, forecast, shadow ledger, active engine, Q60 gate or protected PR #6/#7/#8 may be modified.
