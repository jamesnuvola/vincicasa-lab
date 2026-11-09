
# VinciCasa SONAR — Q92 pre-execution checkpoint (2026-11-09 10:40 UTC)

## Verified state before this checkpoint
- Q89 refresh control is accepted and byte-persisted on the canonical 3,402-draw archive through 2026-11-08; archive SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`, Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Frozen Q89 candidate `P9_06_09_12_14_15_17_18_19_23`: Blind OOS Top-5 hit-share 11.7910% versus uniform 12.5000%; no formula/split Holm row below 0.05. No predictive gain, no promotion.
- Q92 discrete-null calibration amendment is pre-execution; full catalog walk-forward has not run.
- Exact-head full project CI on prior PR #23 head `853a8592b0a0024a4a259aecb9ec6b3b923b4747`: run [42588944269](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588944269) SUCCESS. Q92 runner synthetic acceptance on that head: [42588940380](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588940380) SUCCESS. These gates precede selective-rank integration; the new code commit needs its own exact-head CI.
- Q92 rank-kernel batch sweep [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310) and synthetic acceptance [42598046222](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598046222) both SUCCESS. On 4,096 seeded formulas and 25 repetitions, batch 2,048 median 0.001478670 s versus full stable argsort baseline 0.011959963 s: 8.0883246× speedup with exact rank parity. Batch 4,096 was 8.0142562× and slightly slower. Synthetic engineering evidence only.
- Q92 catalog remains 8,436,285 formulas, 3,352 strict-prior targets (Discovery 2,012 / Validation 670 / Blind OOS 670), global Holm family 75,926,565 tests.

## Pre-execution improvements recorded
- The exact selective actual-number rank kernel is documented; lower-number tie-break matches stable argsort.
- Batch 2,048 selected from the preregistered sweep: 275 batches per shard and 4,120 globally; formula universe and metrics unchanged.
- A minimum practical Top-5 paired effect gate of 0.005 (0.5 percentage points, approximately 17 extra hits over 670 Blind OOS draws) is registered before Q92 Blind OOS, in addition to Holm-adjusted block sign-flip p<0.05 and a positive 95% block-bootstrap lower bound.
- An artifact-backed workflow is prepared. It waits for full project CI on the exact source SHA, runs Q92 synthetic regressions and verifies the Q89 same-archive freeze/paired ledger. Shards are uploaded independently with run-attempt identity for checkpoint recovery; aggregation, acceptance, bundle upload and append-only result-branch persistence are wired.
- Result branch target: `research/sonar-q92-results-20261108`. No merge or promotion is part of the workflow.

## Limitation / next action
- At checkpoint creation, this workflow has not been triggered and no historical Q92 shard has run. No Q92 Discovery/Validation/Blind result exists.
- Next: integrate the selective kernel and amendments, trigger the workflow, verify exact-head CI and preflight, then monitor 15 shard jobs and recover only failed jobs while preserving successful artifacts. Acceptance, artifact digests and result-branch byte readback must be observed. Human review remains mandatory.
- PR #6, #7 and #8 untouched; no auto-merge, promotion or shadow insertion.
