# VinciCasa SONAR — Q92 rank-kernel optimization checkpoint

Recorded: 2026-11-09

## Recovered accepted state

- Canonical archive: 3,402 draws through 2026-11-08.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 same-archive refresh is accepted technically and byte-readback verified; exact-head CI on the persisted Q89 head passed.
- Q89 frozen formula: `P9_06_09_12_14_15_17_18_19_23`.
- Q89 Blind OOS Top-5 share 11.7910% vs uniform 12.5000%; no global Holm formula/split row below 0.05. Q89 is pending human review, not promoted.
- Q92 discrete-null calibration, global Holm aggregator, acceptance validator and strict-prior runner are present on the research stack. The exact-null amendment supersedes the previous normal-tail approximation before historical execution.

## New quantitative engineering hypothesis: Q92-RANK-KERNEL-01

For the same finite Q92 formula subset and prior-only feature state, a formula-major contiguous rank kernel (formula batch 4,096; score matrix `B x 40`; stable row-wise rank) will:
1. preserve every rank vector exactly under the lower-number tie-break; and
2. deliver at least 10% higher formula throughput than the prior number-major kernel (batch 1,024; score matrix `40 x B`) on the seeded synthetic benchmark.

The batch partition changes from 550 to 138 batches per 562,419-formula shard (75% fewer batch-loop iterations). This is a computational hypothesis only, not a prediction-quality claim.

### Local exploratory microbenchmark (not GitHub CI)

Seed: 920092; synthetic standardized state; random equal-weight ten-feature subsets; 20 timed repetitions; median kernel latency:

| Kernel | Formulas/timed batch | Median latency | Throughput |
|---|---:|---:|---:|
| Existing number-major rank kernel | 1,024 | 1.247553 ms | 820,807 formulas/s |
| Candidate formula-major rank kernel | 4,096 | 4.325642 ms | 946,912 formulas/s |

Observed throughput change: **+15.36%**. Exact rank equality was observed for a common 1,024-formula sample and for all 4,096 formulas in a separate local seeded comparison (zero rank mismatches; score maximum absolute difference 0).

These are local synthetic measurements; they do not substitute for the committed seeded benchmark run on GitHub Actions or the historical Q92 walk-forward.

## Implementation persisted on isolated branch

Branch: `research/sonar-q92-rank-kernel-20261109`
Code head at checkpoint: `385a0359fb23b8c599d31a7c2883cb5565ec0508`

Changes:
- `scripts/sonar_q92_common.py`: batch size 4,096 and benchmark source hash.
- `scripts/sonar_per_number_condition_10plus_shard.py`: contiguous formula-major weights, row-wise stable ranking and formula-major actual-rank indexing.
- `tests/test_sonar_q92_walkforward_shard.py`: tie-break, matrix shape and batch-count regression updates.
- `scripts/aggregate_sonar_q92_ten_feature.py`: strict batch-manifest validation updated to 4,096/138.
- `tests/benchmark_sonar_q92_rank_kernel.py`: seeded benchmark; exact common-rank comparison; 25 repetitions; preregistered speedup threshold 1.10.
- Q92 synthetic workflows include the rank-kernel branch and benchmark.

### CI state observed (not yet final at checkpoint)

- Prior Q92 exact-head full project CI at `853a8592b0a0024a4a259aecb9ec6b3b923b4747`: SUCCESS (run 42588944269).
- Prior Q92 shard synthetic acceptance: SUCCESS (run 42588940380).
- Prior Q92 aggregate/paired inference synthetic acceptance: SUCCESS (run 42588936692).
- Rank-kernel branch synthetic runner/benchmark workflow: run 42596595274 was superseded/cancelled by later branch commits; a latest run was queued/in progress when this checkpoint was recorded.
- Rank-kernel branch aggregate synthetic workflow: run 42596605799 in progress.
- Rank-kernel branch exact-head full project CI: run 42596605959 in progress.

No final CI conclusion is asserted for the rank-kernel branch here.

## Statistical and leakage guardrails

- Q92 strict-prefix definition remains unchanged: target index `i` uses only draws `[0:i)`; cutoff date is `i-1`.
- Chronological splits remain 2,012 Discovery / 670 Validation / 670 Blind OOS.
- Formula universe remains `C(27,10)=8,436,285`; no catalog expansion occurred.
- Candidate freeze remains Discovery global top-100 followed by one Validation selection; Blind OOS is excluded from selection.
- Global catalog Holm family remains 75,926,565 formula×split×endpoint tests, with discrete Hypergeometric convolution raw p-values.
- Paired Blind OOS remains Q92 vs same-archive frozen Q89 with block bootstrap/sign-flip and Holm over four endpoints.
- Synthetic benchmark outputs are not historical predictive evidence.
- No automatic merge, engine promotion, shadow insertion, or changes to PR #6, #7, or #8.

## Blockers and next iteration

1. Verify the latest Q92 rank-kernel synthetic runner benchmark on GitHub Actions and capture the measured throughput ratio. If below 1.10 or rank mismatches occur, reject/repair the kernel before any historical execution.
2. Verify aggregate synthetic acceptance and exact-head full project CI on the same final code head.
3. Add a full artifact-backed 15-shard execution/persistence workflow (currently the checked Q92 workflows are synthetic acceptance only); validate timeout, artifact completeness, immutable recovery, and exact-byte append-only persistence.
4. Only after those gates, execute the historical 15 shards, aggregate all 25,308,855 formula×split metric rows, replay the 75,926,565-test Holm family, freeze Discovery→Validation candidates, and evaluate paired Blind OOS.
5. Persist complete reports/artifacts, validator readback and exact-head CI; human review remains mandatory.

Current decision: **rank-kernel optimization is exploratory and not accepted yet; Q92 historical walk-forward has not run.**
