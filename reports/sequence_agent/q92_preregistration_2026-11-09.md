# Q92 preregistration — ten-feature equal-weight formula catalog

**Status: preregistered with pre-execution amendment; full walk-forward execution pending.** This protocol does not mark Q92 complete.

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
- 15 contiguous shards × 562,419 formulas; batch size 1,024; 8,239 batches.
- Metric rows: 25,308,855; target ledger rows: 3,352.
- Global Holm family: **75,926,565** formula×split×endpoint tests (3 endpoints).

## Candidate selection and paired blind comparison
Discovery ranks each catalog's top 100 by Top-5 hit share; tie-break lower mean rank then lexicographic formula ID. Validation freezes one Q92 candidate and one Q89 control. The Q89 nine-feature catalog must be re-run on this exact 2026-11-08 archive and split layout; the old Q89 candidate from the 2026-11-07 archive is not an admissible control.

Primary endpoint: paired Blind OOS Top-5 hit-share difference (Q92−Q89). Secondary endpoints: Top-10, Top-20 hit-share and mean rank. Inference: circular block bootstrap 20,000 reps (block 7, seed 920027), block sign-flip 20,000 reps (block 7, seed 920028), and Holm correction over four paired endpoints. Uniform baselines: Top-5 12.5%, Top-10 25%, Top-20 50%, mean rank 20.5.

Catalog-level p-values use the discrete upper-tail convolution of iid Hypergeometric(40,k,5) number-hit counts for each registered split size and Top-k endpoint. The null assumes independent uniform 5-of-40 draws; convolution is deterministic float64, with underflowed extreme tails floored to the smallest positive subnormal. This calibrates the catalog-level null, not predictive skill.

## Pre-execution protocol amendment — 2026-11-09

`Q92-NULL-CALIBRATION-01` replaces the continuity-corrected normal approximation before the full walk-forward run. A full-support audit over the 75,926,565-test family found relative tail discrepancies up to 68.22% for Top-5 with 670 targets and 49.48% for Top-5 with 2,012 targets near the first Holm step (`alpha/m = 6.58531e-10`). Formula universe, feature stack, strict-prior cutoff, chronological splits, candidate selection, paired endpoints and seeds are unchanged. See the amendment JSON and audit report in `reports/sequence_agent/`.

## Pre-execution compact-output amendment — 2026-11-09

`Q92-METRIC-OUTPUT-COMPACT-01` defines `compact_counts_v1`: seven integer sufficient statistics per formula×split row (`number_hits_top5`, `number_hits_top10`, `number_hits_top20`, `all5_top5`, `all5_top10`, `all5_top20`, `rank_sum`). Split and formula rank are implicit in deterministic split-major/formula-rank order. The acceptance validator reconstructs means and discrete exact raw p-values, recomputes global Holm, and checks raw/adjusted p-value vector SHA-256. Per-row adjusted p-values and redundant formula/feature labels are not persisted; the global adjusted vector is replayable from the counts and registered method.

## Acceptance and guardrails
Acceptance requires exact formula/shard coverage, strict-prefix reconciliation, all metric and ledger dimensions, global Holm family, frozen candidate IDs, paired ledger arithmetic and inference replay, append-only persistence with byte-for-byte readback, exact-head CI, and human review/integration. No automatic merge, promotion or shadow insertion. PRs #6, #7 and #8 remain untouched; the 2026-10-25 freeze is immutable.

Limitations: this finite equal-weight subset catalog does not exhaust weighted, nonlinear, conditional, interaction or infinite formula spaces. Historical Blind OOS has prior SONAR exposure and is not independent prospective confirmation.

## Next action
Trigger the artifact-backed Q92 full walk-forward workflow with exact-head synthetic/full-CI preflight, 15 deterministic shards, global Holm/selection/paired Blind OOS acceptance and append-only compact persistence.
