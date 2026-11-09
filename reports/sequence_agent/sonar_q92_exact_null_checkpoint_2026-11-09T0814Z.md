# VinciCasa SONAR — Q92 exact-null calibration checkpoint

Recorded: 2026-11-09 08:14 Europe/Rome (07:14:33 UTC)

## Verified prerequisite: Q89 same-archive control
- Q89 refresh run [42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631): SUCCESS; all 15 delta shards and aggregate/acceptance/persistence job succeeded.
- Exact-byte persistence checkpoint: commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; 22 files, 47,651,846 bytes, all byte-readback verified.
- Archive: 3,402 draws through 2026-11-08; blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`; SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 candidate frozen before Blind OOS: `P9_06_09_12_14_15_17_18_19_23`; Blind Top-5 11.7910% versus uniform 12.5%; no catalog formula/split Holm row below 0.05. Pending human review; not promoted.
- Q89 exact-head project CI [42575002564](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002564): SUCCESS.

## Quantitative calibration finding
Q92 family: 75,926,565 tests; first Holm step alpha/m = 6.58531e-10. Full-support audit over N=670 and 2,012 and Top-k=5/10/20 found normal-tail relative error up to 68.22% for Top-5/N=670, 49.48% for Top-5/N=2,012, and 44.11%/29.09% for Top-10. Top-20 errors are smaller (2.74%/0.91%).

Pre-execution amendment `Q92-NULL-CALIBRATION-01` replaces the normal approximation with deterministic float64 convolution of iid Hypergeometric(40,k,5). Formula universe, strict-prior feature state, split, candidate freeze, paired endpoints and seeds remain unchanged. Independence remains an assumption; this is calibration, not predictive evidence.

## Code and local test evidence
- Added `scripts/sonar_q92_null_calibration.py` and `tests/test_sonar_q92_null_calibration.py`.
- Updated Q92 shard runner, global aggregator, validator and synthetic workflows to use/replay discrete p-values with explicit field names.
- Local Python synthetic regressions: 7/7 PASS.
- GitHub CI on this amendment head: pending; no full Q92 shard has run.

## Next action
1. Verify synthetic acceptance and full project CI on exact head.
2. Implement immutable artifact-backed 15-shard Q92 execution/recovery and append-only exact-byte persistence.
3. Execute Q92 on the 2026-11-08 canonical archive only after CI gates pass.
4. Apply global Holm, Discovery→Validation freeze and paired Blind OOS; acceptance/readback and human review remain mandatory.

No merge, promotion or shadow insertion. PRs #6, #7 and #8 remain untouched.
