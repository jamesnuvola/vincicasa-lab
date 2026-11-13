# Q144 — Family-balanced rank ensemble of pre-target shadow forecasts

**Status:** preregistered research-only experiment  
**Registration date:** 2026-11-13, before calculating any Q144 outcome metrics  
**Source branch:** main at `4a55fb7da216bd3850b79f862bf10b2cbcafa968`  
**Canonical archive:** `data/storico_daily.csv`, blob `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`  
**Shadow source:** `reports/sequence_agent/shadow_forecasts.csv`, blob `ffc5a4eb0c38e4dfc67032e1ef5737689be5fec1`

## Question and hypothesis

The 42 sequence-rule forecasts (24 family, 12 pair, 6 chain) are frozen before each target. Does a family-balanced rank aggregation of those pre-target forecasts produce more Top-20 hits than the independently frozen APP Top-20 on the final chronological holdout?

Primary endpoint: paired mean Top-20 hit difference, Q144 Borda consensus minus APP, on the last seven completed shadow target dates (2026-11-06 through 2026-11-12). Minimum practically relevant effect: **+0.25 hits per draw**.

Secondary endpoints:
1. Q144 Borda consensus minus equal-type inclusion consensus on the same seven targets.
2. Q144 Borda consensus minus the uniform Top-20 expectation of 2.5 hits per draw.

This is an audit of genuinely pre-target component forecasts, but the aggregation rule is being evaluated retrospectively after those outcomes exist. Therefore the historical Blind OOS is **not virgin prospective confirmation**. The separately frozen 2026-11-13 Q144 candidate will be the first genuinely prospective observation for this aggregation rule.

## Frozen aggregation rules

For each target date, use only the 42 pre-existing rows with config_type in `family`, `pair`, or `chain`. Require exactly 24, 12, and 6 rows respectively, all with history_cutoff equal to the previous calendar date. Exclude `app_engine` from aggregation; retain its frozen Top-20 only as a comparator.

For each rule's ordered Top-20, assign Borda points 20,19,...,1 to ranks 1..20 and 0 otherwise. Within each type, average the points across that type's rules. Sum the three type averages. Rank numbers by this score descending, breaking ties by smaller number ascending. The first 20 numbers form Q144 Borda Top-20.

Comparator 2 (equal-type inclusion): within each type, calculate the fraction of that type's rules containing each number in their Top-20; sum the three fractions; rank descending, ties by smaller number ascending.

No weights, windows, thresholds, or tie-breaks will be tuned after outcome inspection.

## Chronological splits

The 31 completed shadow dates are ordered by target date:
- Discovery: first 18 dates (2026-10-12 through 2026-10-30, excluding dates without a draw).
- Validation: next 6 dates (2026-10-31 through 2026-11-05).
- Historical Blind OOS: final 7 dates (2026-11-06 through 2026-11-12).

All splits are descriptive because the aggregation was not frozen before those historical outcomes. Only the 2026-11-13 shadow freeze is prospective for Q144 itself.

## Inference and multiplicity

For the three registered Blind OOS endpoints, use exact paired sign-flip randomization for paired contrasts (2^7 assignments) and the exact convolution of Hypergeometric(40,5,20) for the uniform Top-20 null. Report paired moving/circular block-bootstrap intervals (20,000 replicates, block length 2, fixed seed) as descriptive uncertainty. Apply Holm correction across the three registered endpoints.

Report mean hits, 4+/5 and 5/5 counts for Discovery, Validation, and Blind OOS. Do not select a winning method based on these splits.

## Integrity, leakage and limits

- Reconcile every evaluated target's actual_numbers against the canonical archive.
- Require exactly 42 rule rows per target and exactly 24/12/6 family/pair/chain rows.
- Require strict previous-day cutoff and pre-target frozen_at timestamp.
- Require 43 pending rows for 2026-11-13, with no outcome fields populated.
- Do not rewrite `shadow_forecasts.csv`, the canonical archive, existing freezes, Q60, B11, APP engine, or protected PRs #6/#7/#8.
- Historical results are exposed and low-powered (seven Blind OOS dates); no promotion is possible.
- This experiment evaluates Top-20 sets, not exact five-number tickets.

## Decision rule

No promotion. Q144 remains research-only regardless of the historical result. Preserve the 2026-11-13 Q144 Top-20 as a new append-only research freeze, then score it only after the official result is published and reconciled.
