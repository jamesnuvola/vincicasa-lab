# Q141-A23 — Multivariate Conditional Block-Null Audit

**Protocol date:** 2026-11-14  
**Status:** registered before the A23 computation  
**Parent evidence:** Q141-A18, A19, A20, A21 and A22  
**Scope:** research only; no production promotion and no forecast mutation.

## Question

Does the 2026-10-25 through 2026-11-13 extension show a multivariate shift in the 1,023 Q7 formula-rank trajectories relative to the immediately preceding 118-target Q75-high run (2026-06-29 through 2026-10-24), after conditioning out the fixed 56-column mask-lattice design and preserving the complete cross-formula vector at each time point?

## Fixed source and chronology

- Q7 formula masks: 1..1,023, ordered by `rank_mask_0001` through `rank_mask_1023`.
- Candidate quintets: 658,008.
- Calibration: the first 400 scored Q7 target rows only; per-row median centering, then per-formula mean and sample standard deviation exactly as A17.
- Mask-lattice residualization: intercept + 10 main effects + 45 pair interactions; design rank 56; no outcome-derived feature selection.
- Reference block: 118 complete multivariate target rows from 2026-06-29 through 2026-10-24, all classified Q75-high using strict-prior state labels.
- Extension block: 20 complete multivariate target rows from 2026-10-25 through 2026-11-13.
- Each row's formula ranks must reconcile to the pinned Q7 rank ledger and its target's immediately preceding cutoff. The extension source must match the persisted A21 source blob SHA-1 `95ba0f108c602707568bdc448cd7394b7dfd6e18`.

## Statistics and null

The primary endpoint is the biased V-statistic energy distance between the 20-row extension and 118-row reference in the 967-dimensional mask-lattice residual space, using Euclidean distance between full residual vectors. The secondary endpoint is the squared Euclidean distance between their mean residual vectors divided by 967.

The conditional null resamples **whole 1,023-formula rows**, never individual formula columns, from the 118-row reference using circular moving blocks of lengths 5, 10 and 20 to create pseudo-extensions of length 20. This preserves contemporaneous cross-formula dependence and local temporal dependence within each sampled block. The reference sample remains fixed in each replicate.

- 20,000 replicates per block length.
- Deterministic xorshift32 PRNG with registered seeds in code.
- One-sided upper-tail Monte Carlo p-values with +1 correction.
- Holm family: the six tests (two endpoints × three block lengths), family-wise alpha 0.05.
- No tuning of block lengths, endpoint definitions, standardization, mask design, or practical thresholds after inspecting results.

## Practical confirmation rule

A multivariate response shift is considered supported only if:
1. the energy-distance p-value is Holm-adjusted below 0.05 for all three block lengths; and
2. the mean-shift endpoint is Holm-adjusted below 0.05 for at least two of the three block lengths; and
3. the observed energy distance is at least 1.25 times the median null energy distance for every block length.

Failure to meet this rule is reported as not confirmed, not as proof of no shift.

## Leakage and interpretation safeguards

- First-400 calibration parameters are frozen and precede the evaluated reference and extension rows.
- The 56-column mask-lattice design is deterministic and uses only mask IDs.
- No target row is used to fit its own rank, scaler, or mask design.
- A22/A21 outcomes were already visible before this A23 protocol; therefore this is an exploratory retrospective audit, not virgin prospective evidence.
- The 14 November A21 freeze remains immutable and pending. No 14 November outcome is used.
- Structural energy/capture statistics are not exact-ticket accuracy, win probability, or evidence of a profitable strategy.
- Historical Discovery/Validation/Blind OOS model scores are inherited unchanged from A20/A22 for context; A23's new confirmatory-style test is limited to the terminal reference/extension comparison and remains exploratory due to prior exposure.

## Reproducibility and persistence

The implementation must emit a source snapshot, target ledger, null summaries, report, test suite, manifest and readback receipt. A deterministic replay must reproduce the persisted outputs. No merge, rebase of protected PRs, canonical archive mutation, freeze rewrite, or engine promotion is permitted.
