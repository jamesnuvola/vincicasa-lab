# Q141-D1 — Standardized relative family-advantage selector

**Protocol status:** PREREGISTERED before D1 computation  
**Date:** 2026-11-13  
**Parent:** Q141 Formula Universe & Behaviour Mapping  
**Branch:** `research/q141-d1-standardized-family-advantage-20261113`

## Research question

Does standardizing each formula family's prior Top-5 hit advantage relative to the other families on the same historical target improve the next-target family choice, beyond the raw rolling-100 selector already tested in Q141-C0?

Q141-C0 selected the family with the largest raw mean Top-5 hit count over the preceding 100 targets. D1 tests one fixed alternative: normalize each target's cross-family hit dispersion before aggregating prior family utility. This downweights the implicit influence of targets on which all families move together and gives each prior target a comparable scale.

## Pinned source and sample

- Source: `reports/sequence_agent/q141_formula_family_behaviour_target_ledger_2026-11-12.csv`
- Source Git blob SHA-1: `4620ac88199256d90bf8e11a852206bfeb817812`
- Parent Q141-C0 report: `reports/sequence_agent/q141_formula_family_behaviour_report_2026-11-12.json`
- Archive Git blob SHA-1: `fcb453ed06c8002314f826dbac79d6935f9ac103`
- Eligible archive: 3,404 draws through 2026-11-10; contest 315 and later rows excluded.
- Scored targets: 3,354; chronological split: Discovery 2,013, Validation 671, historical Blind OOS 670.
- Six fixed families: frequency_change, frequency_level, lag_memory, neighbour_field, position_dependence, recency_gap.

## Quantitative hypothesis

For each prior target (s), let (h_{f,s}) be family (f)'s Top-5 hit count, and let (ar h_s) and (v_s) be the mean and population variance across the six families on that same target.

Define the target-standardized relative family advantage:

[
z_{f,s} = \frac{h_{f,s}-\bar h_s}{\sqrt{v_s+\lambda^2}},
\qquad \lambda=0.25.
]

For target (t), compute only from the immediately preceding 100 scored targets:

[
R_{f,t}=\frac{1}{100}\sum_{s=t-100}^{t-1} z_{f,s}.
]

Select the family with the largest (R_{f,t}). Ties are resolved by lower mean prior actual-number rank over the same 100 targets, then lexicographic family ID. For the first 100 scored targets, use the existing equal-family ranking, matching Q141-C0's deterministic warm-up.

The fixed window (100), scale floor (0.25), family set, and tie policy are not tuned on Validation or Blind OOS.

## Comparators and endpoints

- **M0:** existing equal-family Top-5 ranking.
- **M1:** Q141-C0 raw rolling-100 family selector, read from the pinned ledger's `selected_family` and `dynamic_top5_hits`.
- **M2:** D1 target-standardized relative-advantage selector.
- **Uniform reference:** expected Top-5 hits = 0.625 per target under independent uniform unordered 5-of-40 draws.

Two co-primary Blind OOS endpoints, both expressed as mean Top-5 hit-count improvement (positive favours D1):
1. M2 minus M1 (increment over the existing raw rolling selector).
2. M2 minus M0 (increment over equal-family ranking).

Practical threshold for each endpoint: **+0.025 Top-5 hits per target**, equivalent to +0.005 in Top-5 hit share.

A historical pass requires both co-primary endpoints to meet the practical threshold, have a circular moving-block bootstrap 95% lower bound above zero, and have Holm-adjusted one-sided block sign-flip p-values below 0.05. A pass would remain exploratory and require a new prospective freeze.

## Walk-forward and inference

- All family outcomes used for target (t) have target offsets strictly less than (t).
- M2 is scored before the target's outcome is added to any later window.
- Discovery is descriptive only; no model parameter is selected there.
- Validation is a locked chronological diagnostic; no tuning is permitted.
- Blind OOS is a historical, previously exposed segment, not virgin confirmation.
- Paired uncertainty: circular moving-block bootstrap, block length 20, 20,000 replicates.
- Paired null: block sign-flip randomization, 20,000 replicates, deterministic seed.
- Holm family size: the two co-primary endpoints.
- Also report Top-10/Top-20 hit counts and mean actual rank as exploratory diagnostics, not extra confirmatory endpoints.

## Integrity gates

- Verify the pinned source ledger Git blob SHA and exact 3,354-row count.
- Verify unique chronological target indices and strict cutoff dates.
- Verify split counts 2,013 / 671 / 670.
- Verify all six family columns exist and all family hit counts are integers in [0,5].
- Verify D1 target (t) reads only rows (t-100,ldots,t-1), never row (t) or a future suffix.
- Mutating any target/future family outcomes must not change the D1 selection or score for an earlier target.
- Deterministic replay must reproduce the complete target ledger and report.
- No target outcome, canonical archive, active engine, Q60 freeze, or existing prospective record may be rewritten.

## Limitations and governance

This is a retrospective historical diagnostic on an archive and Blind OOS segment already exposed to extensive SONAR research. It does not create virgin evidence. The target is family-specific Top-5 coverage, not an exact quintet probability or a claim that the draw is predictable. The six Q80-derived families are coarse and do not exhaust Q141's formula grammar. Standardization may amplify noisy cross-family differences when dispersion is small; the fixed scale floor is intended to limit that effect, not guarantee calibration.

Research only. No engine promotion, shadow insertion, canonical archive mutation, automatic merge or rebase. PRs #6, #7 and #8 remain untouched.
