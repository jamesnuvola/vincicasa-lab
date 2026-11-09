# Q89 Refresh Supplemental Pairing Protocol — 2026-11-09

**Protocol ID:** Q89-refresh-paired-blind-ledger-supplement-2026-11-09  
**Preregistered before execution:** 2026-11-09 02:00 UTC  
**Status:** SUPPLEMENTAL_PREREGISTERED_IMPLEMENTATION_PENDING

## Purpose

The Q89 nine-feature candidate is the same-archive control for the preregistered Q92 ten-feature comparison. Q92's Blind OOS comparison requires target-level paired ranks, not merely the aggregate Q89 Blind OOS hit-share and rank means. This supplement adds a deterministic selected-candidate Blind OOS ledger to the Q89 2026-11-08 archive-aligned refresh.

## No change to the primary Q89 refresh

This supplement does **not** change:
- the 4,686,825-formula Q89 universe;
- the 15-shard formula enumeration;
- the three-target additive refresh offsets (2011, 2681, 3351);
- the Discovery global Top-100 selection rule;
- the Validation-only final candidate freeze;
- the 42,181,425-test global Holm family or its endpoints;
- the selected Q89 candidate ID or any promotion decision.

The selected formula is frozen from Discovery and Validation before this supplemental Blind OOS ledger is generated. Blind OOS outcomes must not feed candidate selection.

## Quantitative definition

For each Blind OOS target offset t in the refreshed split (offsets 2682 through 3351; 670 targets), build the 27-feature standardized state using only the complete archive prefix before target t. For the frozen Q89 candidate feature set F (nine features), rank all 40 numbers by

\[
s_t(n)=\frac{1}{9}\sum_{j\in F}z_{j,t}(n)
\]

with descending score and stable lower-number tie-break. Record the five actual-number ranks and derive Top-5/Top-10/Top-20 hit counts, all-five indicators and rank sum.

## Required artifact

reports/sequence_agent/q89_refresh_20261108_selected_candidate_blind_ledger.csv

Exactly 670 rows, one per Blind OOS target, with:
- target date, cutoff date, prior-draw count, actual quintet;
- frozen Q89 formula ID;
- the five actual-number ranks;
- Top-5/Top-10/Top-20 number-hit counts;
- all-five Top-5/Top-10/Top-20 indicators;
- rank sum.

## Acceptance

The validator must:
1. reconcile the 670 target dates and prior cutoffs against the canonical 2026-11-08 archive and refreshed Blind OOS split;
2. verify the frozen Q89 candidate ID is constant;
3. recompute every target's ranks from the strict-prior feature stack and compare exact rank vectors;
4. recompute hit counts, all-five indicators and rank sums;
5. reconcile the paired ledger's aggregate hit-share/rank metrics to the Q89 selection and report;
6. persist the ledger append-only, verify exact committed bytes, and pass current-head CI.

## Interpretation and limits

This ledger is a same-archive pairing control for Q92. It is descriptive historical Blind OOS evidence, not prospective independent confirmation. It cannot promote a motor, modify the Q60 shadow stream, or replace human review.
