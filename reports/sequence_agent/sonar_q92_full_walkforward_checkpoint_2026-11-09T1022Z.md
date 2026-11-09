# VinciCasa SONAR — Q92 preflight checkpoint, paired-inference fixture recovery

Recorded: 2026-11-09 (latest Actions log and repository readback).

## Stable research evidence

Q89 same-archive control on the 2026-11-08 archive (3,402 draws) is accepted/persisted: [run 42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), checkpoint commit `95e6d7b24f0a92318741b9fdb82fb856becd5436), exact-head CI [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) SUCCESS. Frozen candidate `P9_06_09_12_14_15_17_18_19_23` Blind Top-5 11.7910% vs uniform 12.5%, with no formula/split Holm row below 0.05; no predictive gain.

Q92 catalog remains `C(27,10)=8,436,285`, 15 shards, Discovery 2,012 / Validation 670 / Blind OOS 670, global Holm family 75,926,565. Discrete Hypergeometric convolution amendment is pre-execution. No historical Q92 shard has run.

Seeded synthetic compute benchmark [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310): exact selective rank-kernel batch 2,048 speedup 8.0883x (median 0.001478670 s vs 0.011959963 s argsort baseline), exact rank parity, 4,096 formula sample, five actual-number indices, 25 repetitions. Batch 4,096 was slightly slower. This is throughput-only evidence.

## CI fixture defects diagnosed and fixes

The Q92 aggregate-core workflow now includes isolated branch `research/sonar-q92-persister-synthetic-ci-20261109`, persister source/test paths, compile and test commands.

1. Runs [42599781629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599781629) and [42599820244](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599820244): fixture failed `PosixPath + str`; corrected relative path composition in commit `968f0fd91f0bc2fb614d625aaf68d07eee743349`.
2. Run [42599960145](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599960145): two tests blocked by synthetic manifest missing `shard_count=15`; fixed in commit `2baf5dc21e9a40c77ab74950baa030e48e88cf8c`.
3. Run [42600056059](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600056059): aggregate-common 9/9 and null-calibration 8/8 passed; fail-closed marker SHA test passed. Two positive-path persistence tests failed in `render_checkpoint()` with `KeyError: 'multiple_testing'`. Root cause: the synthetic paired-inference fixture contained only `primary_decision`, but the persister expects `multiple_testing.endpoints`, endpoint metrics (mean delta, bootstrap CI, sign-flip p-values, n), block length and replicate count. The fixture schema was completed and persisted in commit `8782534e200ea9c0b54e8782ee38bbe837a33ce1`; test blob SHA `e4d171b537f66c5cca06fb81886224b7b2f2755c`.

Targeted rerun [42600172269](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42600172269) on exact commit `8782534...`: QUEUED at last observation. Main CI was skipped on fixture-only commits with `[q80-reuse-artifact]`, avoiding redundant exhaustive catalog work.

## Full project CI

Full project CI [42598985535](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598985535) on Q92 preflight source head `72f0d7b9dc23b9e0c2d979f49382768b722ce071` remains IN PROGRESS at exhaustive Q80-Q86 catalog tests. No exact-head full CI SUCCESS observed.

## Limits and next action

No full historical Q92 shard, global aggregate/Holm acceptance, Discovery→Validation freeze or paired Blind OOS inference exists. The persister's synthetic acceptance is not yet passing; run `42600172269` must be observed and any failure diagnosed. Then full CI must pass. Artifact-backed immutable shard execution/recovery, strict-prior replay, source/output hashes, acceptance and append-only byte readback are prerequisites. No merge, promotion or shadow insertion; PR #6, #7 and #8 untouched.
