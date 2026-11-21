# Q141-A6 — Full-59 family-stratified covering sample

**Preregistered:** 2026-11-13  
**Status:** execution pending at registration

## Hypothesis

A deterministic pair-covering sample spanning all 59 Q89 features will have a higher per-target mean Top-5 number hit share than an equal-size, equal-grammar sample restricted to the 20 Q90 Discovery-selected features.

Primary endpoint: Blind OOS paired difference in mean per-formula Top-5 hit share, `full59_balanced - selected20_matched`. Minimum practical effect: **+0.005** (0.5 percentage points).

Secondary endpoint: Blind OOS `full59_balanced` mean Top-5 hit share minus the uniform 5-of-40 expectation **0.125**, with the same practical threshold.

## Frozen sample design

- Seed: `14120261113`.
- 350 four-feature blocks per scope.
- Every quartet produces 1 L4 mean, 6 I4 pairwise interactions and 8 G4 conditional gates.
- Add 75 linear subsets at each size L5, L6, L7 and L8.
- 5,550 formulas per scope; 11,100 total.
- Per scope: 650 linear means, 2,100 interactions, 2,800 gates.
- Full-59 sample must cover all 59 features and all 1,711 feature pairs; feature appearances targeted at 23–24 quartets.
- Selected-20 control must cover all 20 features and all 190 pairs; each feature appears exactly 70 times in quartets.

Sample generation uses only feature indices, family labels, fixed seed and coverage state. No target outcomes or formula hit metrics are consulted.

## Formula semantics

- Linear: arithmetic mean of per-target feature z-scores.
- Interaction: four-feature mean plus 0.25 times the candidate-wise population z-score of one pairwise product.
- Gate: four-feature mean plus 0.25 times `indicator(feature >= 0.5 or 1.0)`.
- Ranking: round scores to 12 decimals; ties resolve by candidate number ascending.

## Walk-forward and inference

Use all 3,351 Q90 scored targets with the source split unchanged: Discovery 2,011, Validation 670, Blind OOS 670. The feature lineage is strict prior (`draws[:i]`); the Q90 source archive ends 2026-11-07. Four later Q141 suffix rows are excluded. Historical Blind OOS is exposed, not virgin prospective evidence.

For the two registered Blind OOS endpoints, use a two-sided non-overlapping 20-target block sign-flip test (20,000 replicates), circular moving-block bootstrap CI (block length 20, 20,000 replicates), and Holm-Bonferroni correction across the two endpoints.

Acceptance requires all three: mean primary effect at least +0.005, 95% CI lower bound above zero, and Holm-adjusted p below 0.05. No motor promotion is authorized.

## Required controls

1. Verify source ZIP and all 17 source members, plus matrix, catalog, selection, ledger and split-metrics hashes.
2. Reconcile 3,351 target dates, cutoffs and actual quintets to the source ledger.
3. Verify every cutoff precedes its target.
4. Replay 56 Q90 source formulas (8 per type-size stratum) against the original split metrics; maximum absolute difference <= 1e-12.
5. Verify deterministic IDs, all-feature/all-pair coverage, stable ties and future-suffix invariance.
6. Formula scoring must not receive the target outcome; the actual quintet is used only after rankings are frozen.

## Limitations

The selected-20 control was selected using Discovery outcomes. Both samples are finite deterministic samples, not exhaustive catalogs. Formulas are dependent through shared features and base sets. The historical Blind OOS has already been exposed in prior SONAR research. Top-5 hit share averaged across formulas is a per-number ranking diagnostic, not direct ticket prediction.

## Governance

No canonical archive mutation, shadow insertion, engine promotion or automatic merge. PRs #6, #7 and #8 remain protected.
