# VinciCasa SONAR — Q92 preflight checkpoint (synthetic persistence regression recovery)

Recorded: 2026-11-09, latest repository/Actions observations in this automation cycle.

## Accepted prerequisite (unchanged)

Q89 same-archive control for the canonical 3,402-draw archive through 2026-11-08 was accepted and byte-readback persisted in run [42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; exact-head project CI [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) succeeded. Frozen Q89 candidate `P9_06_09_12_14_15_17_18_19_23` Blind Top-5 is 11.7910% versus uniform 12.5%; no formula/split Holm row below 0.05. It is a control without predictive evidence, pending human review.

Q92 remains preregistered at `C(27,10)=8,436,285`, 15 shards, 3,352 targets (Discovery 2,012 / Validation 670 / Blind OOS 670), Holm catalog family 75,926,565. Discrete Hypergeometric convolution amendment is pre-execution; its independent uniform 5-of-40 null assumption is explicit.

## Compute experiment

The preregistered selective exact actual-number rank-kernel batch-size experiment measured 8.0883x median synthetic speedup at batch 2,048 (baseline 0.011959963 s; candidate 0.001478670 s), exact rank-vector parity, 4,096 sampled formulas, five actual-number indices and 25 repetitions. Batch 4,096 was slightly slower (0.001492336 s). The result is synthetic throughput only, not predictive evidence. Result record: [Q92-RANK-KERNEL-03](https://github.com/jamesnuvola/vincicasa-lab/blob/research/sonar-q92-full-walkforward-preflight-20261109/reports/sequence_agent/q92_rank_kernel_03_batch_sweep_result_2026-11-09.json).

## Root cause: first targeted persistence synthetic CI failure

I added branch/path/compile/test coverage to the Q92 aggregate-core synthetic workflow on isolated branch `research/sonar-q92-persister-synthetic-ci-20261109`. The workflow successfully compiled the persister and tests; Q92 aggregate-common regressions (9/9) and discrete calibration regressions (8/8) passed.

The persister fixture then errored in all three tests before invoking persistence behavior:
`TypeError: unsupported operand type(s) for +: 'PosixPath' and 'str'`.
Cause: `make_bundle()` constructed `report_path=bundle/base+...` and `marker_path=bundle/base+...`; `bundle/base` is a Path, then string concatenation is invalid. This is a test-fixture path composition defect, not a persister acceptance result.

Correction persisted in commit `968f0fd91f0bc2fb614d625aaf68d07eee743349` (test blob SHA-256 not declared; Git blob SHA readback is `8106dd878c3f259b2a82b35461ce148a910fb853`): keep manifest-relative paths as strings (`base + filename`) and resolve them with `bundle / path` only at file access.

Targeted rerun:
- Q92 aggregate-core synthetic acceptance [42599960145](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599960145), exact commit `968f0fd...`: QUEUED at last observation.
- Earlier runs [42599781629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599781629) and [42599820244](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599820244): FAILURE due the fixture TypeError, now corrected.
- Main project CI [42598985535](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598985535) on preflight head `72f0d7b9dc23b9e0c2d979f49382768b722ce071`: still IN PROGRESS at exhaustive Q80-Q86 catalog tests; no exact-head full CI SUCCESS observed.

## Limits and next action

No full historical Q92 shard, global aggregate, catalog Holm acceptance, Discovery→Validation freeze, or paired Blind OOS inference has run. Q92 is not predictive-evidence validated and is not promoted.

1. Poll run `42599960145`; inspect decoded job logs if it fails and repair/retry the targeted synthetic test.
2. Observe the full project CI run `42598985535` to conclusion.
3. Only then pass artifact-backed immutable shard/recovery, acceptance, source-hash and append-only byte-readback gates before any historical Q92 launch.
4. Keep Q89 same-archive control and strict-prior feature construction; selection uses Discovery→Validation only; Blind OOS remains untouched until freeze.
5. Persist subsequent result/checkpoint revisions append-only and require human review.

PR #6, #7 and #8 remain untouched. No merge, engine promotion or shadow insertion.
