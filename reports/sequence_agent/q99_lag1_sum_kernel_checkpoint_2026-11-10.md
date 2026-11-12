# Q99 — post-run checkpoint (2026-11-10)

## Status
**HISTORICAL_EXPLORATORY_COMPLETE / NO_PREDICTIVE_LIFT_DEMONSTRATED.** Research-only. No merge, production change, freeze change or promotion.

## Frozen design
- Protocol committed before scoring: `reports/sequence_agent/q99_lag1_sum_kernel_protocol_2026-11-10.json`.
- Canonical archive: 3,403 draws through 2026-11-09; source blob `8d3e19f0b417024ba32e576697eac0648d12ab86`.
- Exact 5-of-40 sum PMF: integer DP across sums 15..190; 658,008 subsets.
- State: previous draw sum; lag-1 kernel over standardized sum distance.
- Fixed prior strength 200; bandwidths 0.25, 0.5, 1.0, 2.0.
- Walk-forward: 3,103 targets; Discovery 1,400 / Validation 850 / historical Blind OOS 853.
- Validation-only bandwidth selection by multiclass Brier; selected h=2.0.
- Blind inference: Brier and log-loss gains, circular block bootstrap 10,000, block sign-flip 50,000, block length 20; Holm across 8 bandwidth × endpoint tests.

## Measured result
- Discovery Brier gain for h=2.0: -0.000591845; log-loss gain: -0.0514550.
- Validation Brier gain for h=2.0: -0.000532613; log-loss gain: -0.0398807.
- Historical Blind OOS Brier gain: -0.000285067; 95% block-bootstrap CI [-0.000495209, -0.000074566].
- Historical Blind OOS log-loss gain: -0.0292763; 95% CI [-0.0490847, -0.0121326].
- One-sided block sign-flip p: 0.993220 (Brier), 0.999240 (log loss); Holm-adjusted p=1.000 for both.
- All eight registered Blind OOS tests have Holm-adjusted p=1.000.
- The model underperformed the exact null in both primary scoring rules across Discovery, Validation and historical Blind OOS.

## Root-cause / recovery log
1. The first leakage-test draft compared realized scores after mutating target/future values. That necessarily changes the realized score even when forecasts are unchanged. Corrected the test to compare the forecast probability vector itself.
2. The first inference implementation referenced a nonexistent `raw_p` property in Holm aggregation, which would have yielded null adjusted p-values. Corrected Holm to consume `block_signflip_p_one_sided` and reran the full analysis. The final report has numeric Holm values.
3. A persistence wrapper initially expected an in-memory `validation` object; the runner's contract correctly exposes serialized `validationText`. The wrapper was corrected before any result files were written.
4. No hypothesis, source data, split, bandwidth grid, prior strength or scoring endpoint was changed during recovery.

## Integrity
- 3,403 valid sorted 5-of-40 draws; dates unique and increasing.
- 3,103/3,103 strict-prior target cutoffs; all transition outcome indices < target index.
- 12,412 forecast PMFs normalized; maximum probability-sum error <= 1e-12.
- Future-mutation invariance and deterministic prediction replay passed.
- Exact null count is 658,008; PMF sums to one.
- Full ledger contains 3,103 target rows plus header.
- Historical Blind OOS has been examined in prior SONAR research; it is not a virgin prospective holdout.
- The model forecasts only the sum marginal, not a coherent quintet distribution.

## Decision / next action
Stop retrospective tuning of this lag-1 sum-state kernel. Continue Q60 append-only prospective collection. The canonical archive ends on 2026-11-09; the 2026-11-10 freezes remain pending and must only be scored after the official draw is published. Never reconstruct missing freezes.
