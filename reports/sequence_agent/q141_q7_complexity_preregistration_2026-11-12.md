# Q141-A4 / Q141-B8 — Q7 typed AST import and formula-complexity walk-forward

**Registration:** 2026-11-12, before execution  
**Status:** preregistered; no results are implied by this document.

## Purpose

1. Import Q7's 1,023 quintet-ranking formulas into a distinct typed AST namespace with output type `quintet_score`.
2. Test one new quantitative hypothesis on the existing Q7 strict-prior rank matrix: within the fixed grammar, formula complexity (number of included feature families) is positively associated with the next target's realized-quintet ranking percentile.

Q7 is not coerced into the per-number Q80/Q90 AST type.

## Pinned sources and boundary

- Q7 source commit: `7a37cab601c5f9386131a00246963f8e4aeabf74`.
- Q7 archive blob: `7dab05ba49ace909fe8783eef729605049c65e50`; 3,387 draws, 2017-07-17 through 2026-10-24.
- Q7 formula-catalog manifest blob: `5cdf9c24431ea23b2176aa6a19133b7f4435980c`.
- Q7 strict-prior walk-forward manifest blob: `aae2c7768c9d37bf633a13939f2b686bcce83a27`.
- Q7 runner blob: `ad1c7fa721f316b3af0018f5da4a0a905bb62dcf`.
- Q141 archive blob used only for exact-prefix reconciliation: `fcb453ed06c8002314f826dbac79d6935f9ac103`.

The Q7 archive must be an exact prefix of Q141. The complexity experiment uses only the Q7 source through 2026-10-24. Later rows, including the quarantined contest 315, are not used.

## Typed AST semantics

- Candidate universe: all 658,008 sorted distinct 5-number subsets of 1..40.
- Formula universe: all 1,023 non-empty subsets of the 10 Q7 feature families.
- Each selected family score is additively smoothed with alpha 0.5, then z-normalized across the complete candidate quintet universe for that target.
- Formula score is the **sum** (unit weight) of its selected standardized family scores.
- AST output type: `quintet_score`; namespace: `Q7`.
- Preserve source formula ID/mask and source snapshot top-20 for 2026-10-25 separately from canonical AST identity.

## Quantitative hypothesis

For each eligible target, compute the Spearman correlation between:
- formula complexity: number of included feature families (1..10);
- normalized percentile of the realized quintet's one-based rank under each formula, where `percentile = 1 - (rank - 1)/(658008 - 1)`.

Primary Blind OOS estimand: mean per-target Spearman rho. Minimum practical effect: +0.02.

Secondary registered controls:
1. Mean percentile across all 1,023 formulas versus the random-quintet expectation 0.5.
2. High-complexity (6–10 families) minus low-complexity (1–2 families) mean percentile; practical margin +0.005.
3. High- versus low-complexity Top-20 rate difference.

Random-quintet references: expected one-based rank 329,004.5; Top-20 probability 20/658,008; Top-100 probability 100/658,008.

## Walk-forward and splits

- Retain the 100-target burn-in used by Q141-B6 for paired comparability.
- Eligible target indices 101–3386 inclusive: 3,286 targets.
- Chronological 60/20/20 split: Discovery 1,972; Validation 657; Blind OOS 657.
- Q7 runner must score the target from prior state, write its rank row, and only then add the target draw to state.
- The target outcome is used only to evaluate ranks generated before that target.
- Discovery and Validation are descriptive diagnostics; no parameter tuning or winner selection is permitted.

## Inference

- Block length 20.
- 20,000 one-sided block sign-flip replicates.
- 20,000 circular moving-block bootstrap replicates for 95% intervals.
- Seed 14120261120.
- Holm-Bonferroni across the four registered Blind OOS tests.
- The correction covers these four endpoints only, not the entire Q00–Q141 research family.

## Acceptance and limitations

- Verify all pinned source Git blob hashes, all Q7 rank-part SHA-256 hashes, dimensions, formula IDs, feature masks, candidate quintets and row cutoffs.
- Inspect the pinned runner order: score and persist target ranks before adding the target to state.
- Deterministic AST IDs and gzip outputs; complete remote Git readback.
- Historical Blind OOS is exposed prior research history, not virgin prospective evidence.
- This is a structural association test, not a deployable predictor and not proof of draw predictability.
- No canonical archive edits, shadow insertion, engine promotion, automatic merge, or changes to PRs #6/#7/#8.

A valid null result is an acceptable completed research stage.
