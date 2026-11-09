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

GitHub synthetic benchmark run [42597014932](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597014932), head `439f06435f5edba027a2706fd1275a7ac48a4dc0):

| Kernel | Median batch time | Throughput |
|---|---:|---:|
| Baseline full stable rank, 1,024 formulas | 1.297649 ms | 789,119 formulas/s |
| Candidate formula-major full stable rank, 4,096 formulas | 5.718953 ms | 716,215 formulas/s |

Measured speedup: **0.907613x (−9.24%)**. Rank parity was exact, including the full 4,096-formula synthetic sample, but throughput threshold 1.10 failed. This optimization is rejected. Evidence points to the changed GEMM orientation plus continuing full 40-number sorting as a poor tradeoff on the hosted runner; the timing includes both score matrix multiplication and rank extraction, so component-level attribution is not separately measured.

The first runner synthetic failure (run 42596807272) was a test fixture with only three score columns passed to a rank kernel that correctly requires 40 numbers. The next failure (42596927888) was the benchmark's missing `scripts/` import path. Both were diagnosed and corrected; neither was a statistical result.

## Engineering experiment 02 — exact selective actual-number ranking (preregistered, pending CI)

A pre-execution amendment is persisted:
`reports/sequence_agent/q92_rank_kernel_02_preregistration_2026-11-09.json`.

For every formula batch, Q92 continues to compute the 40-number score matrix from the same 27 strict-prior features. Instead of materializing a full stable argsort for all 40 numbers and every formula, it computes the exact stable rank of each of the five actual numbers by comparing that score against all 40 scores:

[
r(a)=1+sum_{n=1}^{40}mathbf{1}[s_n>s_a]
+sum_{n<a}mathbf{1}[s_n=s_a].
]

This preserves lower-number tie priority and is algebraically identical to selecting the five actual-number rows from a full rank matrix. It changes no formula, feature, target split, selection rule, p-value, Holm family or paired endpoint. The target quintet is used only to extract the five ranks after the prior-only 40-number scores exist.

Registered acceptance:
- Seed 920092; 4,096 formulas sampled by combinadic rank.
- Actual-number seed 920093.
- Baseline batch 1,024; candidate batch 4,096; 25 timed repetitions.
- Minimum throughput speedup **1.25x**.
- Exact rank parity for all five actual numbers across all 4,096 formulas; zero mismatches.
- Batch loop count per 562,419-formula shard: 550 → 138 (75% fewer).

Local synthetic evidence (not GitHub CI): exact parity for all 4,096 formulas, zero mismatch. Baseline throughput 793,114 formulas/s; selective-rank candidate 2,627,128 formulas/s; **3.3124x** speedup. This local measurement is not accepted as hosted CI evidence or predictive evidence.

## Selective-rank code and CI heads

Branch `research/sonar-q92-selective-rank-20261109`, commit `7b77cf9c368f95b423d9405485697511cb562686`.

Implemented and persisted:
- `rank_actual_numbers`: exact five-actual-number rank calculation against all 40 scores with finite/shape/index fail-closed checks.
- Q92 runner uses number-major score matrix and selective rank extraction; seven compact metric counts remain the same sufficient statistics.
- Synthetic tests compare selective ranks to full stable rank for 4,096 random formulas and for tied-score cases; strict-prior replay checks report batch fields.
- Seeded benchmark script now compares baseline full ranks with candidate selective ranks and gates 1.25x.
- Amendment JSON is included in the source hash manifest.
- Both Q92 runner and aggregate synthetic workflows include the selective-rank branch and amendment path.

Current runs:
- Runner + selective benchmark [42597521050](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521050): IN PROGRESS.
- Global Holm/paired-inference synthetic acceptance [42597521059](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521059): IN PROGRESS.
- Exact-head full project CI [42597521087](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597521087): QUEUED.
- Earlier full project CI on code head `385a0359` [42596605959](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596605959): IN PROGRESS at exhaustive Q80-Q86 formula-grammar validation; prior archive/app-data, prospective-gate, diagnostics, evolutionary and positional/regime/residual/hazard steps passed.
- Aggregate synthetic acceptance on rank-kernel code head `385a0359` [42596605799](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42596605799): SUCCESS; 9 aggregate tests and 8 discrete-null tests both reported OK.

No final CI conclusion is asserted for the selective-rank head yet.

## Statistical and leakage guardrails

- Target index `i` feature state is strictly `draws[0:i]`; cutoff date is `i-1`.
- Chronological splits remain 2,012 Discovery / 670 Validation / 670 Blind OOS.
- Formula universe remains `C(27,10)=8,436,285`.
- Discovery global top-100 → one Validation freeze; Blind OOS excluded from selection.
- Global Holm family remains 75,926,565 formula×split×endpoint tests using discrete Hypergeometric convolution raw p-values.
- Paired Blind OOS remains Q92 vs same-archive frozen Q89 with block bootstrap/sign-flip and Holm over four endpoints.
- Engineering benchmarks are synthetic and are not predictive evidence.
- No merge, engine promotion, shadow insertion, or change to PR #6, #7, or #8.

## Blockers and next iteration

1. Observe Q92 selective-rank runner synthetic and benchmark result. Reject or repair if exact parity fails or measured speedup is below 1.25x.
2. Verify aggregate synthetic acceptance and exact-head full CI on the same final selective-rank head.
3. Implement an artifact-backed 15-shard historical execution workflow and append-only persistence. Current Q92 workflows verified here are synthetic acceptance only.
4. Before historical execution, validate shard timeout/recovery, artifact completeness, source/archive identity, global Holm replay, Discovery→Validation freeze, paired Blind OOS, acceptance validator, exact-byte persistence/readback and exact-head CI.
5. Run historical Q92 only after those gates, then retain human review before any engine promotion.

Current decision: **experiment 01 rejected; experiment 02 is preregistered and awaiting GitHub synthetic acceptance; Q92 historical walk-forward remains unexecuted.**
