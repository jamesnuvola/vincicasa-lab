# Q141-A18 — Mask-Lattice Residual Spectral Mapping

## Status and purpose

This protocol is frozen before execution of the A18 experiment. A18 tests whether the low-dimensional structure reported by Q141-A17 remains after removing the deterministic mask-lattice effects induced by the registered 10-family finite grammar.

A18 is a structural analysis of realized historical formula-rank profiles. It is not a forecast of the five numbers or of a ticket.

## Pinned source

- Q7 branch: `research/exhaustive-formula-catalog-20261025`
- Q7 commit: `7a37cab601c5f9386131a00246963f8e4aeabf74`
- Formula masks: 1,023 non-empty subsets of 10 registered feature families.
- Scored target rows: 3,386; the first raw archive row is explicitly unscored.
- Candidate quintets: 658,008.
- The source archive ends on 2026-10-24. It is intentionally pinned and is not silently extended with current main data.

## Quantitative hypothesis

After removing the mask-lattice intercept, 10 family main effects and 45 pairwise interactions, the top-six residual subspace must:

1. capture at least 0.50 of residual energy in both Validation and historical Blind OOS;
2. exceed the conditional circular-shift null in both holdouts with Holm-adjusted one-sided p < 0.05;
3. exceed the 99th percentile of the corresponding conditional null in both holdouts; and
4. retain adjacent split subspace overlap of at least 0.75 for Discovery→Validation and Validation→Blind OOS.

All four requirements are conjunctive. Failure of any requirement means NOT CONFIRMED. No threshold may be changed after observing results.

## Mask-lattice design

For formula mask (m\in\{1,\ldots,1023\}), let (x_j(m)\in\{0,1\}) indicate inclusion of family (j). The fixed design matrix contains:

- one intercept;
- 10 main-effect columns (x_j);
- 45 pair-interaction columns (x_i x_j), (i<j).

The design has 56 columns and is expected to have rank 56, leaving 967 residual dimensions. For each target row, the standardized 1,023-mask rank profile is projected onto the orthogonal complement of this design.

## Strict-prior walk-forward

- Rank normalization: ((rank-1)/658007).
- Each target row is median-centered across its 1,023 formula masks.
- Per-mask means and sample standard deviations are estimated only from the first 400 target rows and frozen.
- The residual PCA basis is refitted separately at each split using exactly the 400 target rows immediately preceding that split.
- Discovery, Validation and Blind OOS use the fixed A17 chronological split: 1,792 / 597 / 597 targets after the 400-row warm-up.
- For every evaluated target, the basis training window ends strictly before the target.
- The historical Blind OOS is not virgin prospective evidence.

## Conditional null

Generate 199 seeded surrogates. Independently circular-shift each residual formula-mask trajectory, then reproject each surrogate target row onto the residual space of the same 56-column mask design. Fit the same split-specific prior-only PCA procedure and measure mean holdout capture.

This null preserves each residual column's circular temporal sequence before re-projection and conditions the final row profiles on the registered mask-lattice residual space. Re-projection changes exact marginal/autocorrelation properties; this limitation is explicit. Minimum attainable raw Monte Carlo p is 0.005.

Holm correction is applied to the two primary holdout tests (Validation and historical Blind OOS). Discovery is descriptive.

## Uncertainty and reproducibility

- 20,000 circular moving-block bootstrap replicates per split.
- Block length 20.
- Fixed seeds are recorded in code and report.
- Unit tests cover design rank, residual orthogonality/idempotence, strict-prior windows, suffix invariance, null determinism and circular autocorrelation preservation.
- Full replay must be byte-identical.
- Remote Git readback must match exact blob hashes before checkpoint finalization.

## Governance and limitations

- No production engine, canonical archive, prospective freeze or Q60 gate may be changed.
- No automatic merge or model promotion.
- PRs #6, #7 and #8 must remain untouched.
- This experiment cannot establish predictive skill or causality. The grammar covers only the registered 1,023 masks of 10 declared families, not all possible mathematical formulas.
