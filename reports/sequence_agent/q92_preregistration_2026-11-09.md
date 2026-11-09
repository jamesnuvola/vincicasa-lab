# Q92 preregistration — ten-feature equal-weight formula catalog

**Status: preregistered with pre-execution amendments; full walk-forward execution pending.** This protocol does not mark Q92 complete.

## Quantitative hypothesis
Exhaustively extend the finite 27-feature equal-weight formula grammar from nine to ten prior-only features. A Discovery→Validation-selected ten-feature formula may improve Blind OOS number-hit ranking over a nine-feature candidate selected by the identical procedure on the same canonical archive and split boundaries. Blind OOS is excluded from candidate selection.

## Canonical archive and walk-forward
- `main` commit: 6cca9022d4311a3f9aba2925fce8c653dc6b63ab
- Archive Git blob: `77ca692a6082809fcc6c471501617433ec7c36cf` — 3,402 draws, 2017-07-17 through 2026-11-08; latest draw `3, 7, 10, 16, 27`.
- Minimum prior history: 50; scored targets: 3,352; target dates: 2017-09-05 through 2026-11-08.
- Split rule: Discovery when offset/N < 0.60; Validation when offset/N < 0.80; otherwise Blind OOS. Expected split counts: **2,012 / 670 / 670**.
- Strict prefix: target index i uses only draws[0:i]; cutoff is date i−1; rank all 40 numbers before scoring target i.

## Formula universe and compute plan
- Feature count: 27; formula size: 10; exact catalog: **C(27,10) = 8,436,285** equal-weight subsets.
- Deterministic lexicographic combinadic ranks 0..8,436,284.
- 15 contiguous shards × 562,419 formulas; selected batch size **2,048**; 275 batches per shard, 4,120 batches globally.
- Metric rows: 25,308,855; target ledger rows: 3,352.
- Global Holm family: **75,926,565** formula×split×endpoint tests (3 endpoints).

## Candidate selection and paired blind comparison
Discovery ranks each catalog's top 100 by Top-5 hit share; tie-break lower mean rank then lexicographic formula ID. Validation freezes one Q92 candidate and one Q89 control. The Q89 nine-feature catalog must be re-run on this exact 2026-11-08 archive and split layout; the old Q89 candidate from the 2026-11-07 archive is not an admissible control.

Primary endpoint: paired Blind OOS Top-5 hit-share difference (Q92−Q89). Secondary endpoints: Top-10, Top-20 hit-share and mean rank. Inference: circular block bootstrap 20,000 reps (block 7, seed 920027), block sign-flip 20,000 reps (block 7, seed 920028), and Holm correction over four paired endpoints. Uniform baselines: Top-5 12.5%, Top-10 25%, Top-20 50%, mean rank 20.5.

**Practical-effect gate preregistered before Q92 Blind OOS:** the primary decision requires mean Top-5 paired delta ≥ **0.005** (0.5 percentage points), Holm-adjusted block sign-flip p < 0.05, and the 95% block-bootstrap lower bound > 0. At 670 draws this is approximately 17 additional number hits over 3,350 actual-number observations. It is a decision threshold, not a forecast.

Catalog-level p-values use the discrete upper-tail convolution of iid Hypergeometric(40,k,5) number-hit counts for each registered split size and Top-k endpoint. The null assumes independent uniform 5-of-40 draws; convolution is deterministic float64, with underflowed extreme tails floored to the smallest positive subnormal. This calibrates the catalog-level null, not predictive skill.

## Pre-execution engineering amendments — 2026-11-09
- `Q92-NULL-CALIBRATION-01` replaces the continuity-corrected normal approximation before full walk-forward. The full-support audit found relative tail discrepancies up to 68.22% for Top-5 at 670 targets and 49.48% for Top-5 at 2,012 targets near the first Holm step (`alpha/m = 6.58531e-10`). Formula universe, feature state, splits and selection are unchanged.
- `Q92-METRIC-OUTPUT-COMPACT-01` defines `compact_counts_v1`: seven integer sufficient statistics per formula×split row. Acceptance reconstructs means and discrete p-values, recomputes global Holm, and checks raw/adjusted vector SHA-256.
- `Q92-RANK-KERNEL-02/03` replaces full 40-number argsort materialization with exact selective ranks for the five actual numbers. The preregistered 4,096-formula/25-repetition sweep selected batch 2,048 at **8.0883×** median throughput versus full stable argsort (0.001478670 s vs 0.011959963 s); exact rank parity was observed. Batch 4,096 was slightly slower (8.0143×). This is synthetic engineering evidence only; no historical target or split outcome was used.
- `Q92-MINIMUM-PRACTICAL-EFFECT-01` adds the 0.005 primary effect-size threshold. The candidate selection procedure is unchanged and Blind OOS is not used for tuning.

## Acceptance and guardrails
Acceptance requires exact formula/shard/batch coverage, strict-prefix reconciliation, all metric and ledger dimensions, global Holm family, frozen candidate IDs, paired ledger arithmetic and inference replay, append-only persistence, uploaded-bundle SHA-256 byte readback, Git-tree/blob byte readback of result-branch files, exact-head full project CI and human review/integration. The compact metric bundle and shard outputs remain in immutable GitHub Actions artifacts with a repository-persisted receipt; summary/manifest/selection/inference files are committed to a dedicated result branch. Result-branch CI remains pending until observed. No automatic merge, promotion or shadow insertion. PRs #6, #7 and #8 remain untouched; the 2026-10-25 freeze is immutable.

Limitations: this finite equal-weight subset catalog does not exhaust weighted, nonlinear, conditional, interaction or infinite formula spaces. The discrete null assumes independent uniform draws. Historical Blind OOS has prior SONAR exposure and is not independent prospective confirmation. Per-target retrospective-best formulas are descriptive upper bounds only and are never used for ex-ante selection. The minimum effect threshold is a decision gate, not a predictive forecast.

## Next action
The artifact-backed workflow waits for full project CI on its exact source commit, reruns the Q92 synthetic regressions, then evaluates all 15 immutable strict-prior shards. It aggregates global Holm, freezes Discovery→Validation candidates, validates paired Blind OOS against the same-archive Q89 control, downloads and SHA-256-verifies the uploaded compact bundle, and persists an append-only result receipt with Git-tree/blob byte readback. Human review remains mandatory.

## Pre-execution amendment — Q92-ABSOLUTE-BASELINE-01

Registered 2026-11-09 14:51:32 UTC, before the corrected full walk-forward rerun.

The paired Q92-vs-Q89 Top-5 comparison is a relative test. Because the same-archive Q89 reference has a prior Blind OOS Top-5 share below the uniform expectation of 0.125, a positive paired lift over Q89 could still leave Q92 below uniform.

The aggregator and acceptance validator will therefore expose and independently replay the selected Validation-frozen Q92 candidate's raw and global Holm-adjusted p-values for Top-5, Top-10 and Top-20 in Discovery, Validation and Blind OOS. The absolute Blind OOS evidence status is PASS only when:

1. the selected candidate's Blind OOS mean number-hits Top-5 share is strictly greater than 0.125; and
2. its Top-5 p-value, adjusted in the already registered global family of 75,926,565 formula×split×endpoint tests, is below 0.05.

This amendment does not change the formula universe, feature stack, Discovery→Validation selection, paired Q89 inference, global Holm family, or Blind OOS isolation. It changes reporting and the threshold for making an absolute above-uniform claim. Technical acceptance may complete while the absolute gate is NOT_DEMONSTRATED; that outcome does not justify engine promotion.

