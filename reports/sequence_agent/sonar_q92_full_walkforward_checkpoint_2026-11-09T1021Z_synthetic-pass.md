# VinciCasa SONAR — Q92 preflight checkpoint, persister synthetic acceptance PASS

Recorded: 2026-11-09 (current repository and Actions readback).

## Verified research baseline

- Canonical Q92 archive: 3,402 draws through 2026-11-08, SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 same-archive control acceptance/persistence: [run 42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631), checkpoint commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; exact-head project CI [42576056851](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42576056851) SUCCESS.
- Frozen Q89 `P9_06_09_12_14_15_17_18_19_23`: Blind Top-5 11.7910% vs uniform 12.5%, no formula/split Holm row below 0.05. No predictive advantage, no promotion.
- Q92 catalog `C(27,10)=8,436,285`, 15 shards, Discovery 2,012 / Validation 670 / Blind OOS 670, global Holm family 75,926,565. Exact discrete Hypergeometric convolution is preregistered before full execution. No historical Q92 shard has run.

## Compute benchmark

Seeded hosted synthetic rank-kernel sweep [42597830310](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42597830310): batch 2,048 median 0.001478670 s vs argsort baseline 0.011959963 s, 8.0883x speedup with exact rank parity; 4,096 formula sample, five actual-number indices, 25 reps. Batch 4,096 was slightly slower (0.001492336 s). Synthetic throughput only.

## Targeted CI recovery completed

Three fixture defects were found sequentially in Q92 append-only persister acceptance:
- Path type mismatch `PosixPath + str`, corrected at commit `968f0fd91f0bc2fb614d625aaf68d07eee743349`.
- Synthetic manifest missing `shard_count=15`, corrected at commit `2baf5dc21e9a40c77ab74950baa030e48e88cf8c`.
- Synthetic paired-inference object missing the persister's `multiple_testing.endpoints`, endpoint metrics, block length and replicate fields, corrected at commit `8782534e200ea9c0b54e8782ee38bbe837a33ce1`.

The targeted Q92 aggregate-core synthetic acceptance now passes:
- [Run 42600172269](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600172269), exact commit `8782534...`: **SUCCESS**.
- Decoded job log confirms aggregate-common 9/9 PASS, discrete-null calibration 8/8 PASS, append-only persister 3/3 PASS (copy/checkpoint exact bytes in synthetic fixture; append-only duplicate rejected; marker SHA mismatch fails closed).
- The workflow branch/path filters and compile/test commands were repaired and readback verified.

I also amended the Q92 ten-feature synthetic workflow branch filter to include the isolated preflight branch so runner tests can be observed on the same source line. Workflow commit `29132867bc96ddf212ae4dfb465de01c3163960a`, workflow blob readback SHA `f183a25293310476d908429a973c84b2ff0d2123`. Exact-head runner synthetic acceptance [42600283544](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600283544) is QUEUED; main CI [42600283313](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600283313) is QUEUED and should be skipped by the fixture-only commit guard.

## Full project CI and remaining gates

Full project CI [42598985535](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598985535) on Q92 preflight source head `72f0d7b9dc23b9e0c2d979f49382768b722ce071` remains IN PROGRESS at exhaustive Q80-Q86 catalog tests; exact-head full CI SUCCESS has not been observed.

No full historical Q92 shard, global catalog Holm acceptance, Discovery→Validation candidate freeze, or paired Blind OOS inference has been produced. The persister synthetic PASS validates fixture behavior, not historical output acceptance.

## Next actions

1. Poll exact-head Q92 runner synthetic acceptance [42600283544](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600283544) and confirm PASS.
2. Observe full project CI [42598985535](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598985535) to conclusion; do not infer success from partial tests.
3. Confirm immutable 15-shard artifact/recovery, strict-prior feature cutoff, source hash envelope, aggregator/validator and append-only byte-readback gates before historical Q92.
4. Execute Q92 only after all prerequisites; global Holm over 75,926,565 tests; candidate selection Discovery→Validation; paired Blind OOS compare to same-archive Q89.
5. Persist final report, manifest, source/output hashes, limitations and checkpoint append-only, verify readback, then require human review.

No merge, engine promotion or shadow insertion. PR #6, #7 and #8 remain untouched.
