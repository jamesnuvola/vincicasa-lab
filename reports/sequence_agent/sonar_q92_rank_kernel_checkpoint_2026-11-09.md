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

The shard batch partition changes from 550 to 138 batches per 562,419-formula shard (75% fewer batch-loop iterations). This is a computational hypothesis only, not a prediction-quality claim.

### Local synthetic measurement for the benchmark's exact seeded formula-sampling method

Seed: 920092; 4,096 formulas sampled without replacement by combinadic rank; synthetic standardized state; 25 timed repetitions; median kernel latency:

| Kernel | Formulas/timed batch | Median latency | Throughput |
|---|---:|---:|---:|
| Existing number-major rank kernel | 1,024 | 1.289140 ms | 794,328 formulas/s |
| Candidate formula-major rank kernel | 4,096 | 4.395365 ms | 931,891 formulas/s |

Observed throughput change: **+17.32%**, above the registered synthetic threshold of +10%. Exact rank equality was observed across all 4,096 formulas in the local seeded comparison (zero rank mismatches; maximum score absolute difference 0).

These are local synthetic measurements; they do not substitute for the committed benchmark on GitHub Actions or the historical Q92 walk-forward.

## Implementation persisted on isolated research branches

- Kernel code branch: `research/sonar-q92-rank-kernel-20261109`, code head `385a0359fb23b8c599d31a7c2883cb5565ec0508`.
- Validation branch: `research/sonar-q92-rank-kernel-ci-20261109`, latest head `439f06435f5edba027a2706fd1275a7ac48a4dc0`.

Changes:
- `scripts/sonar_q92_common.py`: batch size 4,096; benchmark and strict-prior regression added to source hash manifest.
- `scripts/sonar_per_number_condition_10plus_shard.py`: contiguous formula-major weights, row-wise stable ranking and formula-major actual-rank indexing.
- `tests/test_sonar_q92_walkforward_shard.py`: tie-break test now uses all 40 numbers, formula-major matrix shape, batch count and report batch fields checked.
- `scripts/aggregate_sonar_q92_ten_feature.py`: fail-closed batch manifest validation updated to 4,096/138.
- `tests/benchmark_sonar_q92_rank_kernel.py`: seeded benchmark; rank parity check; 25 repetitions; minimum throughput speedup 1.10. Script import path fixed after CI diagnosis.
- Q92 synthetic workflows include the rank-kernel branch and self-trigger on their workflow-file changes.

## CI evidence and root-cause recovery

### Passed
- Prior Q92 exact-head full project CI at `853a8592b0a0024a4a259aecb9ec6b3b923b4747`: SUCCESS (run [42588944269](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588944269)).
- Prior Q92 shard synthetic acceptance: SUCCESS (run [42588940380](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588940380)).
- Prior Q92 aggregate/paired inference synthetic acceptance: SUCCESS (run [42588936692](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588936692)).
- Rank-kernel branch aggregate synthetic acceptance on code head `385a0359`: SUCCESS (run [42596605799](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596605799)); logs show 9 aggregate tests and 8 discrete-null tests both OK.

### Failures diagnosed and corrected; final reruns pending
1. Runner synthetic run [42596807272](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596807272) failed because the tie-break test passed a 3-number score matrix while the new rank kernel explicitly requires 40 numbers. The fixture was corrected to a 40-number matrix and checks stable tie order. This fix is in commit `79651267fe80cfa671ee5ef6acae207eb5385231`.
2. Runner synthetic run [42596927888](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596927888) then failed because the benchmark script imported Q92 modules without adding the repository's `scripts/` directory to `sys.path`. The bootstrap was added in commit `439f06435f5edba027a2706fd1275a7ac48a4dc0`.

Current gates observed:
- Q92 shard synthetic runner + seeded benchmark: run [42597014932](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597014932) IN PROGRESS on head `439f0643`.
- Exact-head full project CI: run [42597014811](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597014811) IN PROGRESS on head `439f0643`.
- Earlier full project CI on kernel code head `385a0359`: run [42596605959](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596605959) IN PROGRESS; archive audit, app-data rebuild/audit, prospective gate, diagnostics, evolutionary and positional/regime/residual/hazard steps passed; exhaustive Q80-Q86 formula grammar step was running at last observation.
- The prior full CI attempt on head `79651267` was cancelled by the subsequent benchmark-import fix; it is not counted as a pass.

No final CI conclusion is asserted for the rank-kernel validation head yet.

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

1. Verify the current Q92 runner synthetic benchmark on GitHub Actions; capture its actual throughput ratio and rank-parity result. Reject/repair the optimization if speedup is below 1.10 or ranks differ.
2. Verify aggregate synthetic acceptance and exact-head full project CI on the same final validation head.
3. Implement a full artifact-backed 15-shard execution and append-only persistence workflow. Current Q92 workflows observed here are synthetic acceptance workflows only; no historical shard has run.
4. Validate workflow timeout and recovery behavior, artifact completeness, immutable shard identity, global Holm replay, candidate freeze, paired Blind OOS, validator, exact-byte persistence/readback and exact-head CI.
5. Only after those gates, execute the historical 15 shards and persist complete reports/artifacts; human review remains mandatory.

Current decision: **rank-kernel optimization is not accepted until GitHub synthetic benchmark and exact-head CI pass; Q92 historical walk-forward has not run.**
