# Q84 — Dynamic Field / State-Flow hypothesis

**Experiment ID:** Q84-DYNAMIC-FIELD-01  
**Recorded:** 2026-11-09 19:35 UTC  
**Status:** PREREGISTERED_NOT_EXECUTED  
**Archive frozen for protocol design:** 3,402 draws through 2026-11-08; SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.  
**Execution dependency:** Q92 acceptance and human review must be completed before this experiment is run. No Q92 result is promoted by this protocol.

## Research question

Does the *current shape and movement of the feature field* contain information that is not captured by static frequency/rule rankings?

This experiment does not assume one rule repeats, that rules never repeat, or that the system is periodic. It searches the entire prior state history for analogous field configurations, regardless of their age, and records the temporal gaps of the analogues.

## Quantitative hypothesis

A state-space analogue ranker that combines the present field with its velocity and acceleration may outperform a static prior-only ranking by at least **0.005 absolute Top-5 number-hit share** on the historical Blind OOS segment.

The selected dynamic variant must also exceed the uniform number-rank expectation of **0.125 Top-5 hit share**. Both conditions are required; a relative gain over a weak static baseline alone is insufficient.

This historical test is exploratory because the archive has prior SONAR exposure. It cannot establish prospective predictive value.

## Frozen state representation

Use the registered 27 prior-only Q80 per-number features, with no new target-derived feature.

Group the 27 standardized per-number feature columns into six families:

1. Frequency: columns 0–7.
2. Trend: columns 8–10.
3. Gap/recurrence: columns 11–14.
4. Position: column 15.
5. Pair/neighbor structure: columns 16–18.
6. Lag/recent structure: columns 19–26.

For target index (i), compute each feature using draws strictly earlier than (i). Standardize each feature across the 40 numbers for that target, then average within each family. The resulting field (S_i) is a 6 × 40 matrix (240 values), retaining number identity and family identity.

Freeze the flow operators:

- Level: (L_i=S_i).
- Velocity: (V_i=S_i-S_{i-7}).
- Acceleration: (A_i=V_i-V_{i-7}=S_i-2S_{i-7}+S_{i-14}).

Three preregistered dynamic variants:

- `FIELD_L`: level only.
- `FIELD_LV`: level + velocity.
- `FIELD_LVA`: level + velocity + acceleration.

All variants use the same fixed (K=25) nearest historical states. No parameter search over K, lag, weights, or feature groups is allowed in this experiment.

## Forecast rule

- Earliest eligible target: index 89 (zero-based), so at least 25 prior eligible state/outcome pairs exist (state indices 64 through 88).
- For target (i), the analogue pool contains only state indices (j<i), with their outcomes from draw (j).
- Standardization mean and scale for distance are computed from the analogue pool only. Dimensions with near-zero scale use scale 1.
- Distance is mean squared Euclidean distance in the selected level/flow dimensions.
- Select the 25 smallest distances; deterministic tie-break is earlier target index.
- Weight analogue (j) by (w_j=1/(d_j+0.001)), normalized to sum to one.
- Number (n)'s score is the weighted fraction of analogue outcomes containing (n).
- Rank all 40 numbers by descending score; exact score ties are resolved by ascending number.

This is a state-analogue model: the outcome at historical state (j) is usable only for a later target (i>j). Neither the current target outcome nor any future outcome enters the current field, its velocity/acceleration, the distance scale, or the analogue pool.

## Controls and selection

Static controls, scored on the identical eligible targets:

- `STATIC_FREQ_50`: frequency in the previous 50 draws.
- `STATIC_EQUAL27`: equal-weight mean of the 27 standardized Q80 features.

Uniform number-rank expectations: Top-5 0.125, Top-10 0.25, Top-20 0.5, mean actual-number rank 20.5.

Chronological split of the eligible target sequence:

- Discovery: first 60%.
- Validation: next 20%.
- Blind OOS: final 20%.

Choose one dynamic variant on Validation by highest Top-5 number-hit share; tie-break lower mean actual-number rank, then variant ID. Independently choose one static control on Validation by the same rule. Freeze both IDs before reading Blind OOS metrics. Discovery and Validation are selection/development data; Blind OOS is not used for selection.

## Statistical protocol

Catalog-level endpoints: number-hit shares in Top-5, Top-10 and Top-20.

- Exact one-sided discrete null: sum of iid Hypergeometric(40,k,5) number-hit counts over each split.
- Global Holm-Bonferroni family: 5 ranking methods × 3 chronological splits × 3 endpoints = **45 tests**.
- Paired Blind OOS comparison: frozen Validation-selected dynamic variant minus frozen Validation-selected static control.
- Paired endpoints: Top-5, Top-10, Top-20 hit share and mean actual-number rank.
- Circular moving-block bootstrap: 20,000 replicates, block length 7, seed 840025, 95% percentile interval.
- Circular block sign-flip: 20,000 replicates, block length 7, seed 840026, two-sided.
- Holm correction across the four paired endpoints.

Primary practical gate:

1. Mean paired Blind OOS Top-5 delta ≥ +0.005.
2. 95% block-bootstrap lower confidence bound > 0.
3. Holm-adjusted paired Top-5 sign-flip p < 0.05.
4. Frozen dynamic variant Blind OOS Top-5 share > 0.125.
5. Its global Holm-adjusted Blind OOS Top-5 catalog p-value < 0.05.

Failure of any condition means **NO DEMONSTRATED GAIN**. A positive result remains historical/exploratory and cannot trigger model promotion.

## Event-level diagnostics

For each target, preserve the 25 analogue target dates and their temporal gaps. Report whether close analogues recur in compact clusters or are dispersed across the archive; do not assume periodicity.

Also retain:

- nearest-state distance and median of the 25 selected distances;
- Top-5/10/20 overlap with both static controls;
- dynamic-only and static-only recovered actual numbers;
- paired rank correlations between each dynamic variant and each static control;
- per-target prior cutoff, actual quintet, and actual-number ranks;
- lifecycle and recurrence summaries for each variant, including null/negative intervals.

These are diagnostics, not additional opportunities to select a winner after Blind OOS.

## Acceptance and leakage tests

Required before accepting the experiment:

- For any target (i), replacing draw (i) or any later draw leaves (S_i,V_i,A_i), the analogue pool, and its 40-number ranking unchanged.
- Every analogue index is strictly less than the target index.
- Every analogue state is itself constructed from draws strictly before its own target.
- The target ledger has one row per eligible target, unique chronological target dates, exact immediate-prior cutoffs and exact archive quintets.
- All five methods are scored on identical targets and splits.
- Validation selection is replayable; Blind OOS is never used to select a variant or parameter.
- Exact p-values, global 45-test Holm vector, paired inference, code hashes and archive hashes are reproducible.
- Outputs are persisted append-only and reread byte-for-byte.
- Exact-head CI passes and human review/integration is recorded before any promotion.

## Limits and next action

- This is a finite six-family representation of the registered 27 features, not an exhaustive mathematical description of the system.
- The 7-target velocity/acceleration lag and K=25 are fixed design choices, not inferred physical laws.
- Historical Blind OOS has prior SONAR exposure; a future prospective shadow of at least 200 complete paired targets remains necessary for promotion consideration.
- Q92 is still pending acceptance on its corrected exact source head. Run Q84 only after Q92 acceptance and human review; do not use unaccepted Q92 metrics as a baseline.
- No Q84 code, historical score, result, or predictive claim is asserted by this preregistration.
