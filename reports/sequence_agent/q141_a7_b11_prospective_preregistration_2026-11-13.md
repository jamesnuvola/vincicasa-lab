# Q141-A7 / B11 — Prospective confirmation protocol

**Preregistration:** 2026-11-13  
**Frozen historical cutoff:** 2026-11-12  
**Frozen code branch:** research/q141-a7-fresh59-behaviour-20261113  
**Frozen rule:** Q141-A7 M1, stability-weighted family aggregation  
**Comparator:** M0 equal-family aggregation

## Objective

Test whether the fixed stability-weighted family rule has prospective incremental value after the historical A7 analysis. No historical Blind OOS row may be relabelled as prospective.

## Prospective sample

- First target: the first officially verified VinciCasa draw strictly after 2026-11-12.
- Collect the next **200 consecutive eligible draws**.
- An outcome with uncertain provenance is quarantined and does not count toward 200 until resolved from an authoritative source.
- No interim efficacy analysis, threshold adjustment, parameter tuning, family remapping or model selection.
- Integrity monitoring is allowed (date, source, schema, cutoff, hash and missing-row checks), but performance summaries remain hidden until all 200 eligible outcomes are locked.

## Frozen models

- Seven family definitions and their 59 feature indices remain exactly as in Q141-A7.
- Family score: mean of that family's per-target z-scored feature values across the 40 candidate numbers.
- M0: equal arithmetic mean of the seven family scores.
- M1: family weights proportional to 1 / (0.10 + mean normalized absolute rank turnover across the previous five target rows), normalized to sum to one.
- Ties: score rounded to 12 decimals, then ascending number.
- The five target rows immediately preceding the first prospective target are the historical rows through 2026-11-12; they may supply prior rank history for the first prospective weight calculation.
- Every target feature row and M1 weight vector must be frozen and hashed before the target outcome is appended or read.

## Primary and secondary endpoints

- Primary: paired M1 minus M0 Top-5 per-number hit share over the 200 targets.
- Secondary: paired M1 minus M0 Top-10 per-number hit share.
- Uniform references: 12.5% Top-5 and 25% Top-10.
- Practical minimum primary improvement: +0.005 (0.5 percentage points).

## Inference

- Paired per-target difference: (M1 hits - M0 hits) / 5.
- Non-overlapping blocks of 20 targets: 10 blocks.
- Exact two-sided block sign-flip test over all 2^10 sign configurations.
- Circular moving-block bootstrap, block length 20, 20,000 replicates, percentile 95% interval.
- Holm-Bonferroni across the two registered endpoints.
- No alternative window lengths, smoothing constants, family definitions or endpoint substitutions may be explored on these 200 targets.

## Decision rule

A historical research signal is eligible for independent human review only if the primary mean improvement is at least +0.005, its 95% interval lower bound is above zero, and its Holm-adjusted p-value is below 0.05, with all provenance and leakage gates passing. This protocol does not itself authorize engine promotion or deployment.

If the primary criterion fails, record the negative result and do not retune against the same 200 outcomes. Any new hypothesis requires a new future sample and a new preregistration.

## Leakage and provenance controls

1. Before each draw, persist the 40-number score vectors, M0/M1 top-5 and top-10 sets, family turnover values, M1 weights, target date, prior cutoff, source archive blob, code commit and prediction hash.
2. Do not append the target outcome until the prediction record is frozen.
3. After official publication, reconcile the exact five numbers and source URL, then append the outcome and calculate hit counts.
4. If the archive changes retroactively, preserve the original prediction snapshot and separately document the correction.
5. Keep the 200-target ledger append-only and hash-chain each prediction/outcome record.

## Governance

Research only. No production engine change, shadow insertion, canonical archive rewrite, automatic merge or promotion. PR #90 remains draft pending human review. PRs #6, #7, #8 and #89 remain untouched.
