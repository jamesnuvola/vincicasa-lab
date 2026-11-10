# Q60-H97 — prospective rank-cascade hypothesis (registered plan, 2026-11-10)

## Motivation

In the 22 complete prospective pairs currently available (2026-10-19 through 2026-11-09), the positional mix has descriptively higher mean Top5 and Top10 hit counts than `freq_100`, while Top20 mean coverage is equal. The exact paired tests do not support a difference after Holm correction, and the sample is too small for a decision.

This is a hypothesis for continued evaluation of the already frozen engines, not a new engine and not a change to the registered Q60 promotion gate.

## Quantitative hypothesis

For each paired prospective target (t), define:

[
Delta_{k,t}=H^{position}_{k,t}-H^{freq100}_{k,t}, quad k in {5,10,20}
]

where (H_{k,t}) is the number of the five actual winning numbers contained in the pre-target frozen Top-k list.

Secondary alternative: at least one of the three mean paired differences is positive and statistically distinguishable from zero after a single Holm correction across the three endpoints.

[
H_{0,k}: E[Delta_k]=0 qquad H_{1,k}: E[Delta_k]
e 0
]

The direction of any estimated effect will be reported; two-sided tests are retained to avoid optimistic directional selection.

## Frozen evaluation protocol

- Continue collecting the existing `position_seed_mix_top20_v1` and `freq_100` forecasts only when each was frozen before the target and uses the previous-day canonical cutoff.
- Require 200 complete paired prospective targets; no missing freeze may be reconstructed.
- Do not change either engine, rank list, parameters, or candidate-set definitions during collection.
- Calculate Top5, Top10 and Top20 hit counts from the frozen lists only after the canonical target outcome is available.
- Use paired exact sign-flip randomization tests for the three mean-difference endpoints.
- Apply one global Holm correction across the three endpoints.
- Use a circular moving-block bootstrap with block length 20 and 10,000 replicates for uncertainty intervals; fix and record the random seed before the 200-target analysis.
- Report the full paired per-target ledger, wins/losses/ties, means, intervals and adjusted p-values.

## Guardrails

- This secondary ranking analysis cannot replace or weaken the registered Q60 primary promotion gate.
- The primary gate remains 200 complete paired targets and the registered Top20 5-of-5 comparison; promotion remains disallowed until that gate and human review are satisfied.
- The 22-target interim results are exploratory and are not used to retune either engine.
- Historical Discovery/Validation/Blind OOS results are not pooled with this prospective series.
- No automatic merge, no model promotion, and no freeze edits.

## Interim evidence at registration

For 22 pairs:

| Endpoint | Global mean | Position mean | Difference | Exact two-sided p | Holm p | Circular block-bootstrap 95% CI |
|---|---:|---:|---:|---:|---:|---:|
| Top5 | 0.7273 | 0.9545 | +0.2273 | 0.1250 | 0.3750 | [0.0000, 0.4091] |
| Top10 | 1.2727 | 1.4545 | +0.1818 | 0.4316 | 0.8633 | [-0.1364, 0.4545] |
| Top20 | 2.5455 | 2.5455 | 0.0000 | 1.0000 | 1.0000 | [-0.3636, 0.3636] |

No endpoint is significant after Holm correction. The intervals include zero. The interim sample therefore does not support the hypothesis; it only motivates continuing the already registered prospective observation without retuning.

## Next action

Append the next genuinely pre-target pair when available, keep the existing engines frozen, and rerun the registered Q60 gate plus this secondary analysis at the 200-pair threshold. Until then, report only interim descriptive statistics and keep promotion disabled.
