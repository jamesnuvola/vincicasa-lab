# VinciCasa SONAR — Q92 preflight checkpoint, corrected CI timeline

Recorded: 2026-11-09. This checkpoint corrects the run-ID attribution in the immediately preceding fixture-recovery note; the latter is retained append-only.

## Verified baseline

- Q89 same-archive control for 3,402 draws through 2026-11-08: acceptance/persistence verified in [42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), byte-readback checkpoint commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; exact-head project CI [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) SUCCESS.
- Frozen Q89 candidate `P9_06_09_12_14_15_17_18_19_23`: Blind Top-5 11.7910% vs uniform 12.5%; no catalog formula/split Holm row below 0.05. Pending human review, not promoted.
- Q92 preregistered universe `C(27,10)=8,436,285`, 15 shards, Discovery 2,012 / Validation 670 / Blind OOS 670, Holm family 75,926,565. Discrete Hypergeometric convolution amendment is pre-execution; no historical Q92 shard has run.

## Compute experiment

Seeded synthetic rank-kernel benchmark [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310): batch 2,048 median 0.001478670 s vs argsort baseline 0.011959963 s (8.0883x), exact rank parity, 4,096 formulas sampled, five actual-number indices, 25 reps. Batch 4,096 was slightly slower at 0.001492336 s. Synthetic compute only, no prediction claim.

## Corrected persister CI timeline

- Runs [42599781629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599781629) (commit `9a39364...`) and [42599820244](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599820244) (commit `6513ae9...`) failed in persister fixture setup with `TypeError: PosixPath + str`. Before the persister tests, Q92 aggregate-common tests passed 9/9 and null-calibration tests passed 8/8. Fix persisted in `968f0fd91f0bc2fb614d625aaf68d07eee743349`, blob `8106dd878c3f259b2a82b35461ce148a910fb853`: keep relative artifact paths as strings, join with `bundle / path` only at I/O.
- Run [42599960145](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599960145) on commit `968f0fd...` reached the persister and failed two tests with `Q92_PERSIST_BLOCKED: shard count mismatch`; marker SHA mismatch fail-closed test passed. Root cause was synthetic manifest fixture missing `shard_count=15`. Fix persisted in `2baf5dc21e9a40c77ab74950baa030e48e88cf8c`, test blob `b5e6f02d716f4e8cdabecd35ee522630ac9d0291`.
- Targeted rerun [42600056059](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42600056059) on exact commit `2baf5dc...`: QUEUED at last observation.

The Q92 aggregate-core workflow was amended to include the isolated persister branch and the persister source/test in branch/path filters, compile and test commands. Main CI was skipped on fixture-only commits by the existing `[q80-reuse-artifact]` guard to avoid duplicate long catalog jobs.

## Full project CI and limits

Full project CI [42598985535](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598985535) on preflight code head `72f0d7b9dc23b9e0c2d979f49382768b722ce071` remains IN PROGRESS at exhaustive Q80-Q86 catalog tests; no exact-head full CI SUCCESS observed.

No full Q92 historical shard, aggregate/Holm acceptance, Discovery→Validation freeze or paired Blind OOS inference exists. No merge, engine promotion or shadow insertion; PR #6, #7 and #8 remain untouched.

## Next action

Poll `42600056059`; if it fails, inspect its decoded job logs and repair on the isolated branch. Then verify full CI `42598985535`. Only after synthetic and full CI gates, immutable shard/recovery and acceptance-readback gates, run Q92 strict-prior against the canonical archive, apply global Holm, freeze through Discovery→Validation, compare paired Blind OOS to same-archive Q89, and persist append-only with byte readback and human review.
