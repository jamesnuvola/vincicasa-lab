# Q141-A7 / B11 — Fresh 59-feature rebuild and stability-weighted family aggregation

**Preregistration date:** 2026-11-13  
**Code branch:** research/q141-a7-fresh59-behaviour-20261113  
**Pinned source commit:** 05f84e57fd0d2028c3f641742e39db4f1629db8c  
**Pinned archive Git blob:** 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb

## 1. Motivation

Q141-A6 found no lift from a broader deterministic Full-59 formula sample versus the historical Selected-20 control. The next question is not whether more formulas help, but whether family aggregation should account for pre-target rank-profile stability rather than giving each family a fixed equal vote.

The 59 feature values are rebuilt from the complete canonical archive through 2026-11-12. The existing Q90 feature matrix is used only as a pinned historical-prefix integrity check; the entire 59-feature matrix is recomputed and must match the Q90 prefix bit-for-bit before any evaluation proceeds.

## 2. Quantitative hypothesis

For each target, calculate a score for each of seven feature families by averaging the family’s per-target z-scored feature values across the 40 candidate numbers.

- **M0 — equal-family baseline:** arithmetic mean of the seven current family scores.
- **M1 — stability-weighted:** compute each family’s mean normalized absolute rank turnover over the previous five target rows (four consecutive rank transitions), then set weights proportional to 1 / (0.10 + turnover). Normalize weights to sum to one and apply them to the current family scores.
- The first five target rows use equal weights because no five-row prior rank history exists.
- Candidate ranking ties are resolved by score rounded to 12 decimal places, then ascending number.

**Primary hypothesis:** M1 improves Blind OOS Top-5 per-number hit share over M0 by at least +0.005 (0.5 percentage points).

**Secondary endpoint:** the same paired difference for Top-10 hit share. It is confirmatory only as a secondary endpoint and is Holm-corrected with the primary endpoint.

No model parameter is fitted or selected from Discovery, Validation or Blind OOS. The window (5), smoothing constant (0.10), family definitions and aggregation rules are fixed in this preregistration.

## 3. Data and temporal design

- Canonical archive: 3,406 draws, 2017-07-17 through 2026-11-12.
- Pinned archive blob: 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.
- Minimum prior history: 50 draws.
- Target rows: 3,356.
- Chronological splits by target index: Discovery 2,014; Validation 671; historical Blind OOS 671.
- Each feature row for target draw i uses only draws[:i]. Recursive EWMA, occurrence, pair and regime state is updated only after the target row has been scored.
- Q90 prefix: run 42504717670, artifact q90-expanded-formula-grammar-bundle, archive through 2026-11-07. The recomputed first 3,351 feature rows must be bit-identical to its (3351,40,59) matrix. The five new target rows extend through 2026-11-12.

## 4. Inference

- Paired per-target hit-share differences: (M1_hits - M0_hits) / 5.
- Non-overlapping block sign-flip, block length 20, 20,000 Monte Carlo replicates, two-sided.
- Circular moving-block bootstrap, block length 20, 20,000 replicates, percentile 95% interval.
- Holm-Bonferroni across the two registered Blind OOS endpoints (Top-5 and Top-10).
- Practical threshold: +0.005.
- Uniform references are 12.5% for Top-5 and 25% for Top-10; equal-feature aggregation is descriptive only.

## 5. Integrity gates

1. Exact archive blob, 3,406-row count and last date must match.
2. All 59 feature columns must be present, finite and per-target centered.
3. Q90’s 3,351-row prefix must match bit-for-bit.
4. All target dates must be strictly increasing; each cutoff must precede its target.
5. The scoring code must use current features and only prior family-rank rows for adaptive weights.
6. Future-suffix mutation and deterministic replay tests must pass.
7. Report, ledger, manifest, checkpoint and matrix artifact hashes must be recorded and independently read back.

## 6. Interpretation and governance

The historical Blind OOS has already been exposed to prior SONAR research and is **not virgin prospective evidence**. This experiment evaluates per-number ranking hit share, not exact five-number ticket probability. Feature families share information and are not independent.

A positive historical result would require genuinely prospective confirmation after 2026-11-12. No engine promotion, shadow insertion, canonical archive mutation, rebase, merge or change to PRs #6, #7 or #8 is authorized by this experiment.
