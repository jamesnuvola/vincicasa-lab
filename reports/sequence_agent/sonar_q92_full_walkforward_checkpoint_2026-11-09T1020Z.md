# VinciCasa SONAR — Q92 preflight checkpoint, persistence fixture recovery 2

Recorded: 2026-11-09 (latest GitHub Actions/log and Git blob observations).

## State retained

Q89 same-archive control (archive 3,402 draws through 2026-11-08) is acceptance/persistence verified by [run 42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), exact-byte checkpoint commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`, exact-head project CI [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) SUCCESS. Q89 frozen candidate `P9_06_09_12_14_15_17_18_19_23` Blind Top-5 11.7910% vs uniform 12.5%, no formula/split Holm row below 0.05; no predictive gain, no promotion.

Q92 remains preregistered: `C(27,10)=8,436,285`, 15 shards, Discovery 2,012 / Validation 670 / Blind OOS 670; family Holm 75,926,565. Exact discrete Hypergeometric convolution calibration is preregistered before any full historical Q92 run. No historical Q92 shard has run.

## Quantitative compute finding

Q92 selective exact rank-kernel seeded hosted synthetic benchmark [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310): 4,096 sampled formulas, five actual-number indices, 25 reps; batch 2,048 median 0.001478670 s vs argsort baseline 0.011959963 s, 8.0883x speedup with exact rank parity. Batch 4,096 was slightly slower at 0.001492336 s. Synthetic throughput only.

## Persister synthetic acceptance: two fixture defects found and corrected

CI coverage was repaired on isolated branch `research/sonar-q92-persister-synthetic-ci-20261109` so aggregate-core workflow includes this branch and compiles/runs the persister regressions.

1. Run [42599960145](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599960145) failed after 9/9 aggregate-common and 8/8 discrete-calibration tests passed. The three persister tests reached fixture setup but failed with `TypeError: PosixPath + str` because `bundle/base + filename` mixed Path and string. Corrected to manifest-relative string paths and `bundle / relative` at file access; commit `968f0fd91f0bc2fb614d625aaf68d07eee743349`, test blob `8106dd878c3f259b2a82b35461ce148a910fb853`.

2. Follow-up run [42599960145](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42599960145) then failed in two persistence tests with `Q92_PERSIST_BLOCKED: shard count mismatch`. Root cause: synthetic manifest omitted `shard_count` although the persister requires 15 in both report and manifest. Added `"shard_count":15` to the synthetic manifest fixture. Correction commit `2baf5dc21e9a40c77ab74950baa030e48e88cf8c`, test blob readback `b5e6f02d716f4e8cdabecd35ee522630ac9d0291`.

Targeted rerun [42600056059](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42600056059) on exact commit `2baf5dc...`: QUEUED at last observation. Main CI is skipped on these isolated fixture commits by `[q80-reuse-artifact]`; this avoids launching a redundant exhaustive Q80-Q86 catalog run.

Full project CI [42598985535](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598985535) on preflight code head `72f0d7b9dc23b9e0c2d979f49382768b722ce071` remains IN PROGRESS at the exhaustive Q80-Q86 catalog step; exact-head full CI success is not observed.

## Next

1. Poll synthetic run `42600056059`; inspect logs if failure and repair/test again.
2. Confirm full CI run `42598985535` reaches SUCCESS.
3. Only after both gates and immutable shard artifact/recovery checks, execute historical Q92 strictly prior-only, aggregate 25,308,855 metric rows, apply global Holm, freeze candidate Discovery→Validation, and paired Blind OOS compare to Q89.
4. Acceptance, source/output hashes, append-only persistence byte readback and human review remain mandatory.

No Q92 predictive metrics yet; no merge, engine promotion or shadow insertion. PR #6, #7 and #8 untouched.
