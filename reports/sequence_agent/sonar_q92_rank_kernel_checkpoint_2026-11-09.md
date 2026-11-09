# VinciCasa SONAR — Q92 rank-kernel checkpoint

Recorded: 2026-11-09

## Recovered accepted statistical state

- Canonical archive: 3,402 draws through 2026-11-08.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 same-archive refresh is technically accepted and byte-readback verified; exact-head CI on the persisted Q89 head passed.
- Q89 frozen formula: `P9_06_09_12_14_15_17_18_19_23`.
- Q89 Blind OOS Top-5 share 11.7910% vs uniform 12.5000%; no formula/split row survived global Holm at 0.05. Q89 remains pending human review, not promoted.
- Q92 exact discrete-null calibration, global Holm aggregator, acceptance validator and strict-prior runner are present. No historical Q92 shard has been run.

## Engineering experiment 01 — formula-major full-rank kernel (rejected)

GitHub benchmark [42597014932](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597014932), head `439f06435f5edba027a2706fd1275a7ac48a4dc0):

| Kernel | Median batch time | Throughput |
|---|---:|---:|
| Baseline full stable rank, 1,024 formulas | 1.297649 ms | 789,119 formulas/s |
| Candidate formula-major full stable rank, 4,096 formulas | 5.718953 ms | 716,215 formulas/s |

Speedup **0.907613x (−9.24%)**. Rank parity exact, but the 1.10 threshold failed. Rejected.

## Engineering experiment 02 — selective exact actual-number rank at batch 4,096 (rejected)

The selective rank formula compares each actual number's score against all 40 prior-only scores, preserving stable lower-number tie priority. It changes no formula, feature, split, selection, p-value, Holm family or paired endpoint.

GitHub benchmark [42597521050](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42597521050), head `7b77cf9c368f95b423d9405485697511cb562686`:

| Kernel | Median time | Throughput |
|---|---:|---:|
| Baseline full rank, batch 1,024 | 1.918685 ms | 533,699 formulas/s |
| Selective rank, batch 4,096 | 9.234402 ms | 443,559 formulas/s |

Speedup **0.831103x (−16.89%)** vs registered 1.25x threshold. Exact rank parity across all 4,096 seeded formulas was TRUE. Rejected at batch 4,096. Hosted/local timing discrepancy is material; no component attribution is claimed.

## Engineering experiment 03 — fixed-sample batch sweep (PASS; batch 2,048 selected)

Preregistration persisted at:
`reports/sequence_agent/q92_rank_kernel_03_batch_sweep_preregistration_2026-11-09.json`.

Initial GitHub synthetic benchmark [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310), source head `8428d599896eff6f23f30375b82fdbe5813ab949`, 4,096 fixed formulas, seeds 920092/920093, 25 repetitions, full stable-rank baseline batch 1,024 (four batches). All candidate sizes had exact parity for five actual-number ranks across all 4,096 formulas.

| Selective-rank batch | Batches | Median time | Throughput | Speedup vs baseline |
|---:|---:|---:|---:|---:|
| 512 | 8 | 2.047235 ms | 2,000,747 formulas/s | 5.8420x |
| 1,024 | 4 | 1.597362 ms | 2,564,228 formulas/s | 7.4873x |
| **2,048** | **2** | **1.478670 ms** | **2,770,057 formulas/s** | **8.0883x** |
| 4,096 | 1 | 1.492336 ms | 2,744,690 formulas/s | 8.0143x |

The initial sweep passed the preregistered 1.25x gate and selected batch 2,048. Baseline fixed-sample median was 11.959963 ms, throughput 342,476 formulas/s.

A confirmation benchmark ran inside the current batch-2,048 code acceptance [42598046222](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598046222), head `4ab71fec66eaa7bbd0331ea6340347a55a5e8882`:

| Selective-rank batch | Median time | Throughput | Speedup vs baseline |
|---:|---:|---:|---:|
| 512 | 1.322020 ms | 3,098,289 formulas/s | 2.9856x |
| 1,024 | 1.048274 ms | 3,907,375 formulas/s | 3.7653x |
| **2,048** | **1.013098 ms** | **4,043,044 formulas/s** | **3.8960x** |
| 4,096 | 1.076438 ms | 3,805,143 formulas/s | 3.6667x |

The second sweep also passed the 1.25x gate and selected batch 2,048. Timings vary between runs, but the selected batch and threshold pass are stable. Both sweeps report full-sample rank parity TRUE.

Persisted reports, readback verified:
- Initial result: `reports/sequence_agent/q92_rank_kernel_03_batch_sweep_result_2026-11-09.json`, blob SHA-1 `07ceb1ede258c3c8e3e53520930cc6a3fbb75053`.
- Confirmation: `reports/sequence_agent/q92_rank_kernel_03_batch_sweep_confirmation_2026-11-09.json`, blob SHA-1 verified after readback.

These are synthetic compute-performance measurements, not predictive evidence.

## Batch 2,048 implementation and current CI

Branch `research/sonar-q92-batch2048-acceptance-20261109`, code head `4ab71fec66eaa7bbd0331ea6340347a55a5e8882`:
- Q92 common `FORMULA_BATCH_SIZE` set to 2,048.
- Per-shard batch count 275; full catalog batch count 4,120.
- Aggregator validation derives batch size/count from Q92 common, replacing hard-coded 4,096/138.
- Regression tests updated to assert 275/4,120.
- Measured sweep and confirmation reports are persisted on the checkpoint branch.

Verified CI:
- Q92 runner strict-prior synthetic + batch sweep [42598046222](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598046222): **SUCCESS**. Five Q92 walk-forward tests and eight null-calibration tests reported OK; batch sweep PASS, exact full-sample rank parity TRUE, selected 2,048 with 3.8960x confirmation speedup.
- Global Holm/paired-inference synthetic acceptance [42598046252](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598046252): **SUCCESS**.
- Exact-head full project CI [42598046287](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42598046287): **IN PROGRESS**. No final conclusion yet.

## Statistical and leakage guardrails

- Target index `i` feature state is strictly `draws[0:i]`; cutoff date `i-1`.
- Splits remain 2,012 Discovery / 670 Validation / 670 Blind OOS.
- Formula universe remains `C(27,10)=8,436,285`.
- Discovery global top-100 → one Validation freeze; Blind OOS excluded from selection.
- Global Holm family remains 75,926,565 formula×split×endpoint tests using discrete Hypergeometric convolution raw p-values.
- Paired Blind OOS remains Q92 vs same-archive Q89 with block bootstrap/sign-flip and Holm over four endpoints.
- Synthetic rank kernels and throughput results are engineering evidence only.
- No automatic merge, engine promotion, shadow insertion, or changes to PR #6, #7, or #8.

## Blockers and next iteration

1. Complete exact-head full project CI on the batch-2,048 code.
2. Implement a full artifact-backed 15-shard historical execution workflow and append-only persistence. Q92 workflows verified so far are synthetic acceptance only.
3. Validate shard timeout/recovery, artifact completeness, source/archive identity, global Holm replay, Discovery→Validation freeze, paired Blind OOS, acceptance validator, exact-byte persistence/readback and exact-head CI.
4. Run historical Q92 only after all gates, then retain human review before any promotion.

Current decision: **experiments 01 and 02 rejected; experiment 03 passed twice and selected batch 2,048; historical Q92 walk-forward remains unexecuted.**
