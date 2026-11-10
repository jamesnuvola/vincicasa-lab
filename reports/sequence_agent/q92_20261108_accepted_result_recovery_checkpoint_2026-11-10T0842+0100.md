# Q92 accepted-result recovery checkpoint — 2026-11-10 08:42 Europe/Rome

## Verified source and execution

- Source checkout: `449d2e9925a9d68385912025b9937c8b5e0851a2`
- Canonical archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`
- Archive: 3,402 draws; 3,352 scored targets; chronological splits Discovery 2,012 / Validation 670 / Blind OOS 670.
- Formula universe: 8,436,285 equal-weight 10-feature formulas; 15 shards; 25,308,855 formula/split metric rows; global Holm family 75,926,565 tests.
- All 15 shards completed successfully. The aggregate step completed global Holm aggregation, fail-closed acceptance replay, manifest/summary construction, artifact upload, and uploaded-bundle SHA-256 byte readback.
- Accepted bundle artifact: ID `13743351872`, 204,386,240 bytes, digest `2bc547a399b8017d3e93b34683662ecb3adb96002a26b2bd2835b48384856bc6`; byte readback matched.
- Persistence receipt artifact: ID `13742758649`; it records `ACCEPTANCE_PASS_ARTIFACT_PERSISTED_PENDING_RESULT_BRANCH_CI_AND_HUMAN_REVIEW`.

## Measured result (historical exploratory, not prospective confirmation)

Selected candidate frozen before Blind OOS: `P10_01_08_11_12_14_15_16_18_19_23`.

Features: `freq_10 + trend_5_vs_50 + age_since_hit + gap_mean + overdue_ratio + position_log_frequency + pair_count_with_last_draw + neighbor_pm2_history + lag_1 + lag_10`.

Same-archive Q89 control: `P9_06_09_12_14_15_17_18_19_23`.

| Split | Q92 Top5 | Q92 Top10 | Q92 Top20 | Q89 Top5 | Q89 Top10 | Q89 Top20 |
|---|---:|---:|---:|---:|---:|---:|
| Discovery (2,012) | 0.137177 | 0.262028 | 0.509642 | 0.137475 | 0.259642 | 0.512922 |
| Validation (670) | 0.129851 | 0.254328 | 0.502388 | 0.130149 | 0.243582 | 0.498806 |
| Blind OOS (670) | 0.111642 | 0.239701 | 0.485373 | 0.117910 | 0.235821 | 0.495522 |

Paired Blind OOS:
- Primary Top5 mean delta Q92 minus Q89: `-0.0062686567`.
- 95% circular moving-block bootstrap CI (20,000 reps, block 7): `[-0.0167164, +0.0041791]`.
- Circular block sign-flip raw p: `0.2687366`; Holm-adjusted p across four paired endpoints: `0.6197690`.
- Primary decision: `NO_SIGNIFICANT_GAIN`; minimum practical Top5 delta +0.005 was not met.
- Q92 absolute Blind OOS Top5 share: `0.1116418` versus uniform expectation `0.125`; absolute lift `-0.0133582`; raw discrete-null p `0.9942229`; global Holm-adjusted p `1.0`; absolute baseline gate `NOT_DEMONSTRATED`.
- The historical Blind OOS had prior SONAR exposure and is explicitly exploratory, not untouched prospective confirmation.

## Root cause of the failed workflow conclusion

The numerical computation and acceptance replay did not fail. The only failed step was Git result-branch persistence.

Job `129682451212`, step 14, failed with:
`warning: here-document ... delimited by end-of-file (wanted 'PY')`
followed by
`syntax error: unexpected end of file`.

Cause: the closing `PY` delimiter inside the shell `if` block was indented in the YAML block scalar, so Bash did not recognize it as the here-document terminator. The result branch did not exist; no repository output overwrite occurred.

## Recovery change committed

Workflow fix committed to this Q92 branch:
- Commit: `64118b89a59cf689dea6c90a7736db6ef7aca0a3`
- Corrected the here-document delimiter indentation.
- Changed the result branch to be source-SHA-scoped (`research/sonar-q92-results-20261108-<full-source-sha>`) in the receipt, persistence step, and readback step. This prevents a later exact-head rerun from colliding with a different source checkout's immutable outputs.
- This commit is a workflow correction only; it does not alter the formula universe, feature definitions, candidate-selection rule, splits, or any forecast.

The new exact-head workflow/CI triggered by this correction has **not yet been verified at checkpoint creation**. The accepted artifact from the previous source SHA remains retained and its digest/receipt were independently read back.

## Guardrails and next action

- No merge, no engine promotion, no freeze modification.
- PRs #6, #7, and #8 were not modified.
- PR #23 remains draft and requires human review.
- Next: verify the exact-head CI for the workflow fix; verify the new Q92 run completes all 15 source-hash-bound shards, acceptance replay, append-only result-branch commit and Git blob byte readback; then inspect the newly generated result independently. Keep the historical Blind OOS classified as exploratory. Do not promote even if technical acceptance passes.
