# VinciCasa SONAR — Q92 aggregation recovery checkpoint

Captured: 2026-11-09T13:52Z

## Canonical experiment identity

- Experiment: Q92 ten-feature equal-weight formula catalog.
- Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Formula universe: `C(27,10)=8,436,285`; 15 shards × 562,419 formulas.
- Targets: 3,352; Discovery / Validation / Blind OOS = 2,012 / 670 / 670.
- Expected metric rows: 25,308,855; global Holm family: 75,926,565 formula×split×endpoint tests.
- Same-archive Q89 candidate: `P9_06_09_12_14_15_17_18_19_23`; Q89 Blind OOS Top-5 11.7910% versus uniform 12.5000%. Q89 remains without demonstrated predictive advantage.

## Previous full Q92 execution — verified state

Workflow run: [42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368).

- Preflight: SUCCESS, 11/11 steps.
- All 15/15 shard jobs: SUCCESS.
- All 15 immutable artifacts exist and are unexpired.
- Total artifact ZIP size: 923,521,258 bytes.
- Artifact source checkout SHA: `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.
- The aggregate job downloaded all 15 artifacts and reported `Q92_ARTIFACT_RECONCILIATION_PASS`: shard coverage 0..14, each internal file size/SHA matched its artifact manifest, and no divergent rerun artifacts were found.
- GitHub artifact metadata exposes 15 ZIP SHA-256 digests; the download log printed matching SHA-256 digests for all 15 ZIPs.
- The aggregate failed before reading formula metrics or producing any statistical result.

## Root cause

The aggregate log ended with:

`Q92_AGGREGATION_BLOCKED: canonical archive quintet invalid`

In `scripts/aggregate_sonar_q92_ten_feature.py::load_archive`, the check compared `values != sorted(values)`. The Q80 archive loader returns each draw as a tuple, while `sorted(values)` returns a list. Valid ordered quintets were therefore rejected solely because tuple and list compare unequal.

This is an aggregation input-validation defect, not a malformed archive, shard failure, leakage finding, or predictive result. No Discovery/Validation/Blind statistics or candidate selection were produced by that failed aggregate.

## Correction persisted

- Aggregator fix commit: `299784fa05d908648bdb09a7a233803b00683c39`.
- Aggregator blob SHA: `f43083a45bc528a592f60a901ef27264a2b3aab5`.
- Regression-test commit: `10986cb6bf256550821d79f3139b3b37798887cf`.
- Test blob SHA: `80a6670deeaf270da407855330721aaa97828b31`.
- Readback confirmed the tuple normalization and two new regression tests are present.
- Valid tuple/list containers are tested; unsorted, duplicate, out-of-range, wrong-length quintets are tested as fail-closed cases.

The shard source hash manifest includes the aggregator and test paths. To preserve exact-source reproducibility, the corrected commit must rerun all 15 shards rather than silently reuse artifacts produced at `45aab4d...`.

## Current CI state

- Full project CI run [42629662800](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42629662800) was IN PROGRESS at checkpoint capture. Archive audit, generated-data rebuild and audit had passed; SONAR retrospective refresh was running.
- No passing result for the corrected exact head has yet been observed.
- No new Q92 full-walk-forward run or aggregate result has yet been verified after the fix.

## Leakage, inference and limits

- Q92's registered feature-state contract remains strict-prior: features for target index i are built from draws before i; target outcomes are used only for scoring.
- Discovery top-100 → Validation freeze; Blind OOS excluded from selection.
- Catalog p-values use the preregistered discrete convolution of iid Hypergeometric(40,k,5) hit counts; global Holm family size 75,926,565.
- Paired Q92-vs-Q89 Blind OOS inference is fixed at 20,000 circular block-bootstrap and block sign-flip replicates, block length 7, Holm over four endpoints.
- Primary practical gate: Top-5 paired lift ≥ 0.005, 95% block-bootstrap lower bound > 0, Holm-adjusted sign-flip p < 0.05.
- Historical Blind OOS has prior SONAR exposure and is not independent prospective confirmation.

## Next actions

1. Wait for full project CI on exact head `10986cb6bf256550821d79f3139b3b37798887cf`.
2. Verify the corrected Q92 full-walk-forward workflow starts and passes preflight.
3. Rerun all 15 shards on the corrected exact source commit; do not reuse the old source-hash-bound artifacts.
4. Require 15/15 success, exact archive/source identities, internal artifact manifests and ZIP digest reconciliation.
5. Run global Holm aggregation, Discovery-to-Validation freeze, paired Blind OOS inference and the fail-closed validator.
6. Persist accepted outputs append-only, verify uploaded bundle digest and Git-tree/blob byte readback, then require human review.
7. Keep Q93 as proposal only: 11-feature catalog versus Q92 on a new prospective 670-target holdout, primary paired Top-5 lift ≥0.005 with block-bootstrap lower CI >0 and Holm-adjusted block sign-flip p<0.05 across four endpoints. It is not preregistered or executed.

## Guardrails

- No automatic merge, engine promotion, or shadow insertion.
- PR #6, #7 and #8 remain untouched.
- PR #23 remains draft/open.
