# Q141-C5 — Q90-to-Q7 incremental cross-granularity transfer

**Status:** preregistered before execution  
**Date:** 2026-11-12  
**Research branch:** `research/q141-formula-universe-behaviour-mapping-20261112`

## Hypothesis

The prior-only behaviour of Q90's seven operator/size families adds information about the next target's mean normalized rank percentile across the fixed 1,023-formula Q7 `quintet_score` universe, beyond the Q7+Q80 baseline already tested in Q141-C4.

This is a forecast of formula-universe meta-quality. It is **not** a forecast of the winning quintet or the five winning numbers.

## Pinned source lineage

| Source | Universe | Cutoff | Pinned identity |
|---|---:|---|---|
| Q7 | 1,023 formulas; 658,008 quintets; 3,286 targets | 2026-10-24 | archive blob `7dab05ba49ace909fe8783eef729605049c65e50` |
| Q80/C0 | 6 per-number families; 3,354 targets | 2026-11-10 | archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103` |
| Q90/B7 | 7 families; fixed sample 100 formulas/family from 330,429; 3,351 targets | 2026-11-07 | archive blob `5d2efd70684e918b27d8f06386d545647898336d`; artifact SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077` |

The Q7/Q80/Q90 ledgers must match on target date, cutoff date, actual quintet and prior-draw index for every Q7 target. Q7 defines the 1,972 / 657 / 657 chronological split. Contest 315 and all rows after Q7's pinned prefix remain excluded.

Q90's seven family columns are based on the fixed Q141-B7 sample of 700 formulas, not the full 330,429-formula catalog. Q90 and Q7 remain distinct output types and source lineages.

## Models

- **M0 — Q7-only:** previous-50 mean Q7 formula-universe percentile.
- **M1 — Q7+Q80:** M0 plus the four Q80 rolling-50 family-state features used in Q141-C4. This is the primary comparator.
- **M2 — Q7+Q80+Q90:** M1 plus four analogous Q90 features: rolling-50 equal-family Top-5 share, cross-family dispersion, normalized family entropy, and recent-25 minus previous-25 trend.

Ridge alpha is fixed at 1.0. Standardization is fitted on training rows only. No parameter, feature, family or endpoint selection is allowed after seeing Validation or Blind OOS.

## Walk-forward

- 50 prior target rows for every rolling feature.
- Discovery predictions are expanding-prequential from offset 100 through 1,971; each fit uses only earlier Discovery outcomes.
- At the end of Discovery, coefficients are fitted once and frozen for Validation and Blind OOS.
- Feature state advances only after each target has been scored.
- Expected evaluated rows: Discovery 1,872 (after the 100-target warm-up), Validation 657, Blind OOS 657.

## Confirmatory endpoint and inference

Primary Blind OOS statistic: `MAE(M1) - MAE(M2)`. Positive values favour adding Q90. The minimum practically relevant improvement is **0.005 MAE units**.

Use a one-sided block sign-flip test and a circular moving-block 95% confidence interval, block length 20, 20,000 deterministic replicates. There is one confirmatory endpoint, so no within-experiment multiplicity correction is required. M2 versus M0 and atlas correlations are descriptive only and cannot replace the primary endpoint.

## Atlas outputs (descriptive only)

Report contemporaneous Q80/Q90/Q7 associations, within-source family co-movement, lag-1 correlations, and dynamic family-selector transition/run statistics by split. These are descriptive summaries, not causal effects or pre-target predictors.

## Acceptance and governance

A transfer lift is demonstrated only if the Blind OOS primary effect is at least +0.005, the one-sided p-value is below 0.05, and the 95% interval is wholly above zero. Otherwise record the result as not demonstrated.

Historical Blind OOS has prior SONAR research exposure and is not virgin prospective evidence. No merge, engine promotion, shadow insertion, canonical archive mutation, or modification of PRs #6/#7/#8 is permitted.
