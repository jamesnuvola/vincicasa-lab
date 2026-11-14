# Q141-A25 — Mask-Cardinality Conditional Dynamics

**Protocol timestamp:** 2026-11-14 08:41 Europe/Rome  
**Classification:** exploratory post-hoc decomposition of the exposed A24 panel; not confirmatory preregistration  
**Parent:** Q141-A24 / PR #107  
**Scope:** research-only. No candidate-number forecast, production promotion, freeze mutation, canonical archive change, or Q60 update.

## Question

A24 found that one-step persistence of the full 1,023-coordinate residual vector was substantially worse than prior-20 and prior-40 means. Does that aggregate failure conceal a complexity-dependent effect across the finite Q7 mask lattice?

The 1,023 masks are the non-empty subsets of ten base dimensions. We partition them deterministically by mask cardinality:

- low order: cardinality 1–3 (175 masks);
- central order: cardinality 4–7 (792 masks);
- high order: cardinality 8–10 (56 masks).

The partition is defined only by the finite combinatorial grammar, not by observed outcomes.

## Fixed source and representation

- Reuse the exact six A23 source snapshots/calibration/lineage objects, verified against the A23 input manifest.
- Reuse the exact A24 target ledger and report; verify their Git blob SHA-1 values.
- 138 rows from 2026-06-29 through 2026-11-13; all are Q75-high-state.
- 1,023 formula coordinates; fixed 56-column mask-lattice residualization; residual rank 967.
- First 400 Q7 scored targets supply the already-frozen per-formula scaler.
- The A23 canonical implementation supplies parsing, temporal validation, mask basis, residualization and deterministic RNG.

## One-step forecasts and loss

For each target row t, use only rows strictly before t:

- Persistence-1: residual vector t-1.
- Mean-20: arithmetic mean of residual vectors t-20 through t-1.
- Mean-40: arithmetic mean of residual vectors t-40 through t-1.

For each fixed cardinality stratum, calculate squared error summed over its formula coordinates and divided by the number of coordinates in that stratum. Mean-40 is descriptive secondary context; the registered inferential comparator is Mean-20.

Chronological scored splits are inherited unchanged from A24:
- Discovery: 58 targets.
- Validation: 20 targets.
- Historical Blind OOS exposed: 20 targets.

The 40 Validation+Blind rows form the inferential panel. The final 20 rows are already exposed in A21–A24 and are not a virgin holdout.

## Quantitative hypothesis

Primary hypothesis: high-order masks (cardinality 8–10) have a positive one-step persistence lift over Mean-20, relative MSE gain at least +1% in both Validation and historical Blind OOS, with a positive lower 95% block-bootstrap bound and Holm-adjusted one-sided block-sign-flip p<0.05 at block lengths 5, 10 and 20.

Secondary structural contrast: the persistence gain for high-order masks exceeds the gain for low-order masks. Test high-minus-low gain at the same three block lengths.

The single Holm family contains 12 endpoints: three strata × three block lengths, plus three high-minus-low contrasts. 20,000 block-sign-flip and 20,000 circular moving-block bootstrap replicates are used per endpoint with fixed deterministic seeds.

Acceptance requires the high-order practical and inferential conditions plus positive, Holm-significant high-minus-low contrasts at all three block lengths. No threshold, split, stratum, seed or window is tuned after the calculation.

## Leakage, source parity and reproducibility

- Every target uses only prior residual vectors; target/future-suffix mutation tests must leave forecasts unchanged.
- All 138 target rows are reconciled to the A23 ledger with strict-prior cutoffs and actual quintets.
- A25 must reproduce every A24 full-vector Persistence-1, Mean-20 and Mean-40 per-target MSE within 1e-9 after weighting the three strata by their coordinate counts and dividing by residual rank 967.
- Input Git blob SHA-1 values are checked against the A23 manifest and the pinned A24 report/ledger.
- Report, group ledger, validation, checkpoint and manifest must replay byte-for-byte.

## Interpretation limits

This is a post-hoc diagnostic because the A24 panel and outcomes were already visible. All 138 rows belong to one selected Q75-high regime; the result cannot be generalized to low-state periods. The 40-row inferential panel is small and temporally dependent. The three strata are deterministic combinatorial complexity bands, not semantic AST families or independent formula samples. The endpoint is residual-rank-vector MSE, not winning-number accuracy, exact-ticket probability or monetary return. Holm covers the 12 A25 endpoints only, not the full Q00–Q141 research history.

## Governance and next action

No production engine, candidate list, canonical archive, Q60 gate, or forecast freeze is modified. PRs #6, #7 and #8 remain untouched. No merge or engine promotion is authorized.

If complexity-stratified persistence also fails, stop adding persistence variants. Continue the separate common-source typed-AST evaluator, keeping per-number and quintet endpoints distinct, and wait for genuinely new prospective targets before confirmatory claims.
