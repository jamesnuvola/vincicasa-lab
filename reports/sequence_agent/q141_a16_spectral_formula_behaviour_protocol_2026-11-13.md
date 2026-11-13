# Q141-A16 — Spectral Formula Behaviour Mapping

**Protocol status:** committed before the A16 spectral calculations. This is a pre-specified exploratory stability analysis of an already exposed historical panel, not a prospective prediction test or a virgin holdout.

## Question and quantitative hypothesis

A15 found a discovery-only participation-ratio effective dimension of 7.578 among 128 sampled Q7 formula rank trajectories, while complete-linkage at Spearman 0.90 produced 106 clusters. A16 tests whether the apparent low-dimensional structure is stable across the fixed chronological partitions or is an artefact of the Discovery interval.

Primary hypothesis: the leading formula-behaviour eigenspace learned in Discovery remains strongly aligned in both Validation and historical Blind OOS.

## Pinned source and fixed splits

- Parent A15 branch: `research/q141-a15-formula-behaviour-redundancy-20261113`
- Parent A15 head: `0dd2015ac7f89c542e018f44bd5c91d647afd015`
- A15 source panel: 3,386 target rows, 128 fixed formula masks, four aggregated CSV blocks; exact Git blob SHAs are recorded in the A15 manifest.
- Q7 source archive: 3,387 draws from 2017-07-17 through 2026-10-24; exact Git blob SHA is recorded in the A15 manifest.
- Chronological partitions are frozen to A15: Discovery 2,031 targets (indices 1–2031), Validation 677 (2032–2708), historical Blind OOS 678 (2709–3386).

The historical Blind OOS has been exposed to previous SONAR research and is not virgin confirmation.

## Split-local preprocessing

For each split independently:

1. Normalize each formula rank as `(rank - 1) / 658007`.
2. For each target, subtract the median across the same 128 formula ranks to remove common target difficulty.
3. For each formula, apply average ranks across targets within that split.
4. Compute the 128×128 Pearson correlation matrix of those rank-transformed residual trajectories (equivalent to Spearman correlation with average ties).

No Validation or Blind OOS value is used to fit or choose the Discovery basis.

## Frozen spectral construction

- Compute the symmetric correlation-matrix eigendecomposition separately in each split.
- Sort eigenvalues descending; clamp only numerical negative values in [-1e-10, 0] to zero. Larger negative eigenvalues fail closed.
- In Discovery, define k80 as the smallest k whose cumulative eigenvalue mass reaches at least 80%; freeze this k.
- The primary stability statistic for holdout split s is:
  `O_s = ||U_D,k^T U_s,k||_F^2 / k`,
  the mean squared canonical correlation between the Discovery and split-s leading k-dimensional eigenspaces.
- Primary acceptance requires O_s >= 0.75 in both Validation and historical Blind OOS.

## Geometric null and multiplicity

For each holdout, compare observed O_s to 20,000 deterministic Haar-random k-dimensional subspaces in R^128 relative to the fixed Discovery subspace. Generate each null subspace by seeded Gaussian draws and modified Gram–Schmidt. Use upper-tail Monte Carlo p=(1 + count(null >= observed))/(20,001). Apply Holm across the two primary holdout p-values.

This is a geometric random-subspace null, not a time-series sampling null. It tests whether the observed subspaces align more than arbitrary subspaces; it does not establish predictive power or account for every possible temporal dependence.

## Secondary descriptive diagnostics

Report per split:
- participation-ratio effective dimension `(sum lambda)^2 / sum(lambda^2)`;
- entropy effective rank `exp(-sum p_i log p_i)`, where p_i=lambda_i/sum(lambda);
- k80 and k90;
- cumulative variance shares at k=5, 10, 20;
- leading eigenvalue shares and eigengap at k80;
- condition and numerical residual diagnostics for the eigensolver.

These are descriptive, not additional confirmatory endpoints.

## Integrity and guardrails

- Verify all four panel Git blob SHA-1 values against the pinned A15 manifest before parsing.
- Reconcile every panel target index, date, immediate-prior cutoff and actual quintet against the pinned Q7 archive.
- Preserve exact formula-mask column order across all splits.
- Test eigendecomposition reconstruction, orthonormality, eigenvalue ordering, deterministic random-subspace null and future-suffix invariance of the Discovery basis.
- Do not tune k, preprocessing, thresholds, seeds or null after inspecting holdout results.
- No canonical archive, production scorer, prospective freeze, Q60 gate or existing PR is modified.
- No model promotion, merge, rebase or automatic integration is authorized.

## Decision

A16 is a structural stability diagnostic only. Even if the spectral basis is stable, it does not imply that it predicts the next draw. If stability fails, do not add another spectral selector; return to semantic AST equivalence and exact feature/formula mapping. Any later predictive hypothesis must be frozen prospectively before its outcomes are observed.
