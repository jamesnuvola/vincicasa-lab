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

Hypothesis: batch 4,096 and formula-major score/rank layout would preserve full ranks and yield at least 10% more formula throughput than the number-major batch-1,024 kernel.

GitHub synthetic benchmark [42597014932](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597014932), head `439f06435f5edba027a2706fd1275a7ac48a4dc0):

| Kernel | Median batch time | Throughput |
|---|---:|---:|
| Baseline full stable rank, 1,024 formulas | 1.297649 ms | 789,119 formulas/s |
| Candidate formula-major full stable rank, 4,096 formulas | 5.718953 ms | 716,215 formulas/s |

Measured speedup: **0.907613x (−9.24%)**. Rank parity was exact, but the registered 1.10 throughput threshold failed. The optimization is rejected. Timings include score multiplication and rank extraction; separate component attribution was not measured.

## Engineering experiment 02 — selective exact actual-number rank (rejected at batch 4,096)

A preregistered amendment `Q92-RANK-KERNEL-02` introduced exact rank extraction for each of the five actual numbers against all 40 prior-only scores:

[
r(a)=1+sum_{n=1}^{40}\mathbf{1}[s_n>s_a]
+sum_{n<a}\mathbf{1}[s_n=s_a].
]

The method preserves lower-number tie priority and exactly matches the five actual-number rows from a full stable rank matrix. It changes no feature, formula, split, selection, p-value, Holm family or paired endpoint.

GitHub synthetic benchmark [42597521050](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521050), head `7b77cf9c368f95b423d9405485697511cb562686):

| Kernel | Median time | Throughput |
|---|---:|---:|
| Baseline full rank, batch 1,024 | 1.918685 ms | 533,699 formulas/s |
| Candidate selective rank, batch 4,096 | 9.234402 ms | 443,559 formulas/s |

Measured speedup: **0.831103x (−16.89%)** against the 1.25x registered threshold. Exact rank parity across the full seeded 4,096-formula sample was TRUE. The candidate is rejected at batch 4,096. The result suggests a batch/hosted-BLAS throughput interaction; the benchmark does not isolate components. Local synthetic tests had shown 3.3124x, demonstrating that local timings do not transfer to hosted CI.

The associated aggregate/paired-inference synthetic acceptance [42597521059](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521059) was SUCCESS.

## Engineering experiment 03 — fixed-sample batch-size sweep (preregistered, pending CI)

Persisted amendment:
`reports/sequence_agent/q92_rank_kernel_03_batch_sweep_preregistration_2026-11-09.json`.

Protocol:
- Same seeded 4,096-formula sample and five synthetic actual numbers.
- Baseline full stable rank over a fixed 4,096-formula sample, batch 1,024 (four batches).
- Candidate selective exact ranks over the same sample with batch sizes `512, 1024, 2048, 4096` (8, 4, 2, 1 batches).
- 25 timed repetitions per configuration.
- Exact rank parity for all five actual numbers and all 4,096 formulas at every candidate size.
- Select the maximum median formula throughput among the four fixed sizes; require at least **1.25x** versus baseline. If none reaches the threshold, reject the optimization.
- The batch size in the historical runner remains 4,096 until the hosted sweep identifies a winner and the runner/aggregator batch contract is updated.

Current gates on branch `research/sonar-q92-selective-rank-batch-sweep-20261109`, head `8428d599896eff6f23f30375b82fdbe5813ab949`:
- Q92 runner synthetic + batch sweep [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310): QUEUED.
- Q92 global Holm/paired-inference synthetic [42597830337](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830337): IN PROGRESS.
- Exact-head full project CI [42597830288](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830288): PENDING.
- Prior selective-rank head full CI [42597521087](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521087): IN PROGRESS; not the current batch-sweep head.

No final CI conclusion is asserted for experiment 03 yet.

## Implementation and reproducibility

- Formula universe remains `C(27,10)=8,436,285`; formula grammar is unchanged.
- Q92 strict-prefix state remains: target index `i` uses only draws `[0:i)`, cutoff `i-1`.
- Splits remain 2,012 Discovery / 670 Validation / 670 Blind OOS.
- Discovery global top-100 → one Validation freeze; Blind OOS excluded from selection.
- Global Holm family remains 75,926,565 formula×split×endpoint tests with discrete Hypergeometric convolution raw p-values.
- Paired Blind OOS remains Q92 vs same-archive Q89 with block bootstrap/sign-flip and Holm over four endpoints.
- Synthetic rank kernels and throughput results are engineering evidence only, not predictive evidence.
- No automatic merge, engine promotion, shadow insertion, or changes to PR #6, #7, or #8.

## Blockers and next iteration

1. Observe the GitHub fixed-sample batch sweep; record all four medians, exact parity, best batch and speedup.
2. If at least one batch reaches 1.25x, update Q92 `FORMULA_BATCH_SIZE`, shard report and aggregate validator to the selected size, then rerun synthetic acceptance and exact-head full CI. If not, reject selective ranking.
3. Implement an artifact-backed 15-shard historical execution and append-only persistence workflow. Current Q92 workflows verified here are synthetic acceptance only.
4. Before historical execution, validate shard timeout/recovery, artifact completeness, source/archive identity, global Holm replay, Discovery→Validation freeze, paired Blind OOS, acceptance validator, exact-byte persistence/readback and exact-head CI.
5. Run historical Q92 only after all gates, then require human review before any promotion.

Current decision: **experiments 01 and 02 rejected on hosted throughput; experiment 03 is preregistered and pending; Q92 historical walk-forward remains unexecuted.**
