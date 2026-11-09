# VinciCasa SONAR — Q92 full walk-forward preflight checkpoint

Recorded: 2026-11-09 (automation cycle; status captured from GitHub Actions and repository readback)

## Verified baseline and preregistration

- Canonical archive for Q92: 3,402 draws through 2026-11-08; archive SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 same-archive control was acceptance-validated and append-only persisted in run [42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), with byte readback checkpoint commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; exact-head project CI run [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) succeeded.
- Q89 frozen candidate `P9_06_09_12_14_15_17_18_19_23`; Blind OOS Top-5 11.7910% vs uniform 12.5%. No formula/split Holm row below 0.05. This is a negative predictive-evidence control, pending human review, not a promoted engine.
- Q92 preregistered catalog is `C(27,10)=8,436,285`, 15 shards, 3,352 targets with Discovery 2,012 / Validation 670 / Blind OOS 670; global catalog Holm family 75,926,565 tests. Blind OOS is excluded from selection.
- Pre-execution amendment Q92-NULL-CALIBRATION-01 replaced the normal approximation with deterministic float64 discrete convolution of iid Hypergeometric(40,k,5) tails. The stated null assumes independent uniform 5-of-40 draws; calibration is not predictive evidence.

## Quantitative compute hypothesis and measured synthetic result

Hypothesis Q92-RANK-KERNEL-03: the selective exact actual-number rank kernel at batch size 2,048 should achieve at least the preregistered 1.25x throughput improvement over the full stable argsort baseline while preserving exact rank vectors.

Seeded hosted synthetic benchmark [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310) reports:
- 4,096 sampled formulas, five actual-number indices, 25 timed repetitions.
- Baseline median 0.011959963 s; batch-2,048 median 0.001478670 s.
- Measured speedup 8.0883x; exact rank parity PASS.
- Batch 4,096 was slightly slower than 2,048 (0.001492336 s median); selected batch size 2,048.
- Scope is synthetic compute performance only; no historical outcomes were evaluated.

## Root-cause diagnosis and CI repair in progress

The fail-closed append-only Q92 persister and synthetic regressions were added on preflight head `72f0d7b9dc23b9e0c2d979f49382768b722ce071`. Inspection found that the Q92 aggregate-core synthetic workflow did not include the new preflight branch in its push branch filter and did not include the persister source/test in path filters, compilation, or test commands. Therefore the newly added persister regressions were not guaranteed to run automatically.

A separate branch `research/sonar-q92-persister-synthetic-ci-20261109` was created without changing PR #6, #7, or #8. Workflow repair:
- commit `9a39364a7244933a189c9be590cec92291d151af`: added the branch and persister source/test path, compile and test commands.
- commit `6513ae97c89c0abfa0c03a9989b499f39507829b`: clarified workflow name; exact workflow blob SHA readback is `976ec59002d65a5bfb176b458c4d438200b0fed6`.

Observed Actions status at checkpoint:
- Q92 aggregate-core synthetic acceptance run [42599781629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599781629), on commit `9a39364...`: IN PROGRESS.
- Follow-on synthetic acceptance run [42599820244](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599820244), on commit `6513ae9...`: QUEUED.
- Main project CI for the checkpoint branch [42598985535](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598985535), on `72f0d7b...`: IN PROGRESS at exhaustive Q80-Q86 catalog tests; exact-head full CI has not passed.
- A push CI run [42599781607](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599781607) on commit `9a39364...` was SKIPPED by the `[q80-reuse-artifact]` guard to avoid dispatching another expensive main CI run.

## Strict limits / current status

- No full historical Q92 shard has run.
- No Q92 global aggregate, Holm catalog acceptance, Discovery→Validation candidate freeze, or paired Blind OOS inference exists yet.
- The synthetic persister acceptance run has not yet been observed as SUCCESS; pending runs must be polled.
- The exact-head full project CI is not yet SUCCESS.
- Q89 is only the same-archive control and shows no predictive advantage over uniform Top-5.
- No merge, engine promotion, or shadow insertion is authorized; human review remains mandatory.

## Next actions

1. Poll synthetic Q92 aggregate-core runs `42599781629` and `42599820244`; if a test fails, inspect the failing step, repair on the isolated branch, and rerun the targeted synthetic workflow.
2. Confirm full project CI on the preflight exact head; do not infer success from partial jobs.
3. Ensure artifact-backed immutable 15-shard execution/recovery and acceptance/readback gates are complete before launching historical Q92.
4. Execute Q92 strictly prior-only against the 2026-11-08 archive; aggregate all 25,308,855 formula×split metric rows, apply the preregistered 75,926,565-test Holm family, freeze only via Discovery→Validation, and compare Blind OOS paired to same-archive Q89.
5. Persist report, manifest, source hashes, output hashes, limitations and checkpoint append-only; verify byte readback and exact-head CI.
