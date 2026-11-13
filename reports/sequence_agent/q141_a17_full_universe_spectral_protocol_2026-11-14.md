# Q141-A17 — Full-Universe Prequential Spectral Mapping

**Protocol status:** frozen on the research branch before the A17 calculation. This is a structural generalization test on the fixed Q7 historical panel, not a forecast of VinciCasa numbers or tickets.

## Question

A16 found a stable six-dimensional subspace among a deterministic sample of 128/1,023 Q7 formula-rank trajectories. Does that six-dimensional structure generalize to the complete 1,023-formula finite grammar when the basis is estimated only from an initial historical prefix and evaluated sequentially on later target rows?

## Quantitative hypothesis

Freeze k=6 from A16 and a 400-target initial training prefix. After the first 400 targets:

1. Fit a six-dimensional PCA basis using only the first 400 formula-rank vectors.
2. Freeze preprocessing parameters (column means and standard deviations) from that same prefix.
3. For every later target, evaluate the fraction of the realized, row-centered 1,023-formula rank vector captured by the frozen basis:
   capture_t = ||U_6^T z_t||² / ||z_t||².
4. Partition the 2,986 sequential evaluations chronologically into Discovery 1,792, Validation 597 and historical Blind OOS 597.
5. Primary acceptance requires both Validation and Blind OOS mean capture >= 0.75 and an upper-tail empirical p < 0.05 after Holm correction against an independent-column circular-shift null.

The 0.75 practical threshold is deliberately below A16's approximately 0.83–0.86 six-dimensional subspace overlap. It is not selected from A17 holdout results.

## Pinned source

- Q7 branch: research/exhaustive-formula-catalog-20261025
- Q7 commit: 7a37cab601c5f9386131a00246963f8e4aeabf74
- Walk-forward manifest Git blob: aae2c7768c9d37bf633a13939f2b686bcce83a27
- Formula catalog manifest Git blob: 5cdf9c24431ea23b2176aa6a19133b7f4435980c
- Canonical source archive Git blob: 7dab05ba49ace909fe8783eef729605049c65e50
- 3,387 source draws, 3,386 scored target rows, 1,023 formula masks, 658,008 candidate quintets.
- Source archive ends on 2026-10-24. It is intentionally pinned to the Q7 panel and is not silently extended with later draws.

## Strict-prior alignment

For target row j (zero-based within the 3,386-row ledger):

- prior_draws must equal j+1;
- cutoff_date must equal archive date j;
- target_date and actual_quintet must equal archive row j+1;
- every rank column must be an integer in [1, 658008].

The rank vector for a target is an outcome descriptor computed by Q7 using only the archive prefix ending at its cutoff. A17 never uses the target's actual quintet to fit the PCA basis.

## Frozen preprocessing and statistic

- Convert rank to [0,1] using (rank-1)/658007.
- Subtract the median across the 1,023 formula ranks within each target row to remove common target difficulty.
- Estimate each formula column's mean and sample standard deviation from the first 400 rows only; freeze them.
- Fit the top six right-singular vectors on the standardized first 400 rows.
- Canonicalize component signs by making each component's largest-absolute loading positive.
- Evaluate every later target against the same frozen basis and frozen preprocessing.

The exact Haar-random-subspace expected capture for any fixed nonzero vector is k/p = 6/1023. It is a geometric reference, not the primary null.

## Temporal dependence control

Use 199 deterministic independent circular shifts, one nonzero shift per formula column. This preserves each formula's marginal trajectory and circular serial ordering while destroying synchronous cross-formula alignment. For each surrogate, repeat row-centering, train-prefix standardization, six-component PCA and the same three holdout evaluations.

Empirical upper-tail p-values use (1 + exceedances)/(199 + 1). Apply Holm across the two primary holdout tests (Validation and Blind OOS). The circular-shift null is a dependence diagnostic, not a deployable forecast and not a complete model of every possible nonstationarity.

For each observed split mean, calculate a 95% circular moving-block bootstrap interval with block length 20 and 20,000 replicates. Discovery is descriptive; Validation and Blind OOS are the registered holdouts.

## Integrity and reproducibility

- Verify pinned manifest and archive Git blob identities.
- Verify SHA-256 of every ledger part against the Q7 walk-forward manifest.
- Verify all 11 formula catalog chunks and the complete set of masks 1–1023.
- Reconcile all 3,386 target dates, cutoffs and actual quintets against the pinned 3,387-draw archive.
- Verify matrix shape, rank bounds, finite values and exact split counts.
- Test future-suffix invariance: changing any row after the 400-row training prefix must not change the fitted basis or frozen scaler.
- Run the full calculation twice and require byte-identical outputs.
- Record the complete target ledger, null distribution, eigenvalues, formula loadings, report, checkpoint and remote readback receipt.

## Interpretation limits

This measures whether the rank-profile vector of the realized quintet across formulas lies in a low-dimensional subspace learned before the target. It does not predict the actual numbers, does not establish causal laws, and does not show that any individual formula is useful. The historical Blind OOS is not virgin prospective evidence because the Q7 panel has already been used in prior SONAR research. The circular-shift null preserves individual column sequences but is still a specified surrogate null, not proof against all temporal confounding.

No engine, production scorer, canonical archive, prospective freeze or Q60 gate may be changed. No merge, rebase or promotion is authorized. PRs #6, #7 and #8 must remain untouched.
