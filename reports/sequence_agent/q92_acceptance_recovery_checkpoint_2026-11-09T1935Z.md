# VinciCasa SONAR — Q92 acceptance recovery checkpoint

Captured: 2026-11-09 19:35 UTC

## Canonical input and experiment identity

- Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Last draw: 3,7,10,16,27.
- Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q92: C(27,10) = 8,436,285 equal-weight formulas; 15 shards × 562,419.
- Walk-forward targets: 3,352; Discovery/Validation/Blind OOS = 2,012/670/670.
- Expected metric rows: 25,308,855; global Holm family: 75,926,565 formula × split × endpoint tests.
- Same-archive Q89 control: `P9_06_09_12_14_15_17_18_19_23`; Blind OOS Top-5 share 11.7910%, below the 12.5000% uniform number-rank baseline.

## Recovered execution and measured preliminary output

Q92 full workflow run [42668016985](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668016985), source checkout `593f259a99ac5cf95dc599e32cbc62ee4f15d15a):

- Preflight passed.
- All 15/15 formula shards completed successfully.
- Artifact reconciliation passed: shard coverage 0–14, internal byte counts and SHA-256 receipts matched, and no divergent retry artifacts were found.
- Aggregation completed and printed its complete summary.
- The fail-closed acceptance replay then failed before acceptance because of a Python module-binding defect.

Preliminary aggregation values from the failed run (not acceptance-validated and not persisted as an accepted result):

- Global Holm family: 75,926,565 tests; zero formula/split rows below adjusted 0.05; minimum reported Holm endpoint maximum 1.0.
- Discovery→Validation selected candidate: `P10_01_08_11_12_14_15_16_18_19_23`; Blind OOS was not used for selection.
- Candidate Blind OOS Top-5 share: 11.1642%, versus 12.5000% uniform; Top-10 23.9701% versus 25.0000%; Top-20 48.5373% versus 50.0000%; mean actual-number rank 20.8510 versus 20.5.
- Paired Q92−Q89 Blind OOS Top-5 delta: −0.0062687 (−0.6269 percentage points), 95% circular block-bootstrap CI [−0.0167164, +0.0041791], raw block sign-flip p=0.268737, Holm p=0.619769.
- Paired primary decision: `NO_SIGNIFICANT_GAIN`.

These values are diagnostic evidence from the aggregation log only. They are not an accepted model result, do not justify promotion, and the historical Blind OOS is prior-exposed/exploratory.

## Root cause and correction

The acceptance validator called:

`q92a.metric_summary_from_compact_counts(...)`

but the function is defined in `sonar_q92_common.py` and imported as `q92`; the aggregate-common module `q92a` does not expose it. This caused:

`AttributeError: module 'sonar_q92_aggregate_common' has no attribute 'metric_summary_from_compact_counts'`

The current Q92 research branch now reads the helper from `q92.metric_summary_from_compact_counts`. A regression test was added to assert the correct module binding and reject the old call.

- Current Q92 branch head: `739f4134a2dc93c756669bf2f206170d773e1a2f`.
- Validator blob at current head: `f304d7a6e2c1729d7434f9b81b08c5265e78c507`.
- Regression-test blob: `6605e9d83b11f96935e3f43197cdf6b70c46d64c`.
- Exact-head full project CI: [run 42683289035](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42683289035) — SUCCESS on current head `739f4134...`.

Important: that general CI run passed, but it skipped the Q92-specific acceptance workflow. The fresh Q92 full walk-forward/acceptance run on `739f4134...` has not yet been independently observed in the available run evidence. Do not treat Q92 as accepted or complete.

The 15 shards from run 42668016985 are source-hash-bound to `593f259a...`. The corrected validator/test changed registered source hashes, so those old artifacts must not be silently reused as exact-head evidence. A fresh exact-source Q92 run must complete all 15 shards and replay acceptance.

## Leakage, bias and reproducibility audit

Verified from the Q92 source and preregistration:

- Each target feature matrix is computed from the strict prefix before that target.
- Historical target outcomes are used only after their own prior-only state has been constructed.
- Discovery selects a top-100 pool; Validation freezes one candidate; Blind OOS is excluded from selection.
- The catalog null uses discrete upper-tail convolution of Hypergeometric(40,k,5) number-hit counts, and the registered global Holm family covers all 75,926,565 formula/split/endpoint tests.
- Paired Blind OOS inference uses 20,000 circular moving-block bootstrap and block sign-flip replicates, block length 7, with Holm over four paired endpoints.
- A paired improvement over Q89 is not sufficient: the absolute uniform Top-5 gate must also pass.
- The historical Blind OOS is exposed to prior SONAR work and cannot be described as untouched prospective confirmation.

## Next action

1. Verify the Q92 full workflow triggered on exact source head `739f4134...`; confirm its preflight, 15/15 shards, artifact receipts and aggregate job.
2. Confirm the new module-binding regression executes in the Q92 synthetic workflow.
3. Re-run the complete fail-closed acceptance replay on the fresh exact-source artifacts.
4. Persist report, manifest, shortlist, paired ledger and metric parts append-only; reread exact bytes and verify hashes.
5. Run exact-head CI after persistence.
6. Keep Q92 pending human review/integration; no engine promotion, shadow insertion or merge.
7. After Q92 acceptance and human review, proceed to the separately preregistered Q84 dynamic-field experiment proposal stored alongside this checkpoint.

## Guardrails

- PR #23 remains open/draft; no merge or engine promotion.
- PR #6, #7 and #8 remain untouched and unmerged.
- The immutable 2026-10-25 target freeze remains unchanged.
- Evidence presence or successful shard jobs do not equal task completion.
