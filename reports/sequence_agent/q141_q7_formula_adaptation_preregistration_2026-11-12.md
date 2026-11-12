# Q141-B6 — Prequential adaptation over the Q7 quintet formula universe

Status: preregistered; execution pending  
Date: 2026-11-12

## Hypothesis

A formula that ranked realized quintets well over the previous 100 scored targets may retain enough temporal usefulness that selecting it before the next target improves exact quintet rank. This is tested on the separate Q7 quintet-scoring grammar, not pooled with per-number formula families.

For target t, choose the formula mask m minimizing the mean zero-based exact quintet rank over targets t-100 through t-1. The current target rank is excluded from the selector.

## Source and lineage

- Q7 source commit: 7a37cab601c5f9386131a00246963f8e4aeabf74
- Q7 archive Git blob: 7dab05ba49ace909fe8783eef729605049c65e50; 3,387 draws through 2026-10-24.
- Q7 walk-forward manifest: aae2c7768c9d37bf633a13939f2b686bcce83a27.
- Q7 strict-prior runner: ad1c7fa721f316b3af0018f5da4a0a905bb62dcf.
- Q141 archive blob: fcb453ed06c8002314f826dbac79d6935f9ac103.

Execution verifies that the Q7 archive is an exact prefix of the pinned Q141 archive, all 34 Q7 rank-part SHA-256 values, every target/cutoff row, and all 1,023 formula masks. The pinned Q7 runner scores each target before adding that target to its state. Q141 rows after the Q7 prefix, including contest 315, are not used.

## Policy and controls

- Dynamic selector: minimum mean exact quintet rank over the previous 100 scored targets; ties go to the smallest integer mask.
- Static control: one formula selected on Discovery only and frozen for Validation and Blind OOS.
- Uniform formula control: per-target expected rank and Top-20/Top-100 rate across all 1,023 registered formula IDs.
- The theoretical uniform quintet null has mean zero-based rank 329,003.5, Top-20 probability 20/658,008 and Top-100 probability 100/658,008.

## Chronological evaluation

After a 100-target warm-up, 3,286 targets are evaluated:
- Discovery: 1,972
- Validation: 657
- Historical Blind OOS: 657

The splits are chronological 60% / 20% / 20%. The Blind segment is historical and already exposed to earlier SONAR research; it is not virgin prospective evidence.

## Endpoints and inference

Primary: Blind OOS normalized percentile gain versus uniform formula selection, with practical threshold +0.005.

Secondary: Top-20 excess and Top-100 excess versus uniform formula expectation; normalized percentile gain versus the Discovery-frozen static formula.

The 11 registered aggregate tests (3 Discovery, 4 Validation, 4 Blind) use one-sided paired chronological block sign-flip inference and circular moving-block bootstrap intervals, block length 100, 20,000 replicates, fixed seed 14120261116. Apply Holm-Bonferroni across all 11 tests.

No formula-specific current-target p-values are computed. The selector's 1,023-way search is evaluated prequentially as one fixed policy.

## Acceptance and governance

Verify source hashes, exact archive prefix identity, all formula masks, all rank-part hashes, strict-prior cutoffs, current-target/future-suffix invariance and deterministic replay. No canonical archive edits, forecast-freeze reconstruction, shadow insertion, engine promotion or automatic merge. PRs #6, #7 and #8 remain untouched.

A null result is a valid research result. Next, persist the Q90 59-feature matrix and 330,429-formula bundle as hash-pinned repository objects, then model its per-number ASTs separately.
