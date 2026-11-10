# VinciCasa SONAR — Q92 pre-execution checkpoint (2026-11-09 10:40 UTC)

## Verified evidence and repository state
- Q89 refresh control is accepted and byte-persisted on the canonical 3,402-draw archive through 2026-11-08; archive SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`, Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Frozen Q89 candidate `P9_06_09_12_14_15_17_18_19_23`: Blind OOS Top-5 hit-share 11.7910% versus uniform 12.5000%; no formula/split Holm row below 0.05. No predictive gain and no promotion.
- Q92 discrete-null calibration and compact sufficient-statistic amendments are registered before full walk-forward.
- Q92 selective-rank batch sweep [42597830310](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42597830310) and synthetic acceptance [42598046222](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598046222) are SUCCESS. On 4,096 seeded formulas/25 repetitions, batch 2,048 median 0.001478670 s versus stable argsort 0.011959963 s: 8.0883246× speedup, exact rank parity. Batch 4,096 was 8.0142562×. Engineering evidence only.
- Selective rank kernel, 2,048 batch size, aggregator/validator batch checks and minimum practical effect gate are now in code. The 0.005 Top-5 threshold is registered before Q92 Blind OOS; candidate selection remains Discovery→Validation only.
- Parent code head `5013f56e38b25ef796f1a7f04bb667ef9b5ab1a5` full project CI run [42605233762](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42605233762) was IN PROGRESS at checkpoint refresh. The final preregistration commit in this checkpoint is expected to trigger a new exact-head CI run and the artifact-backed Q92 workflow.

## Q92 scope
- Formula universe: 8,436,285 equal-weight 10-feature subsets over 27 prior-only features.
- 15 shards × 562,419 formulas; batch size 2,048; 275 batches per shard, 4,120 globally.
- 3,352 strict-prior targets; Discovery 2,012 / Validation 670 / Blind OOS 670; global Holm family 75,926,565.
- Primary paired Blind OOS endpoint: Q92−same-archive Q89 Top-5 hit-share. Acceptance requires mean delta ≥0.005, Holm-adjusted block sign-flip p<0.05 and 95% circular block-bootstrap lower bound >0.

## Execution workflow and recovery
- The full workflow push trigger is restricted to the main Q92 preregistration JSON, so staged code/amendment commits cannot launch historical shards before the final protocol is frozen.
- Preflight waits for full project CI on the exact source SHA, then runs strict-prior/selective-rank, compact-output and discrete-null synthetic regressions and reconciles Q89 same-archive candidate/paired ledger.
- Each shard artifact is immutable per run attempt. On a failed workflow rerun, successful prior-attempt shard artifacts are retained; the aggregate downloader verifies raw artifact SHA/bytes and rejects conflicting duplicate shard outputs.
- Global aggregation and fail-closed acceptance precede the compact bundle upload. The workflow downloads the uploaded bundle and SHA-256 byte-verifies its digest, then commits result summaries/manifest/selection/inference/receipt to `research/sonar-q92-results-20261108` without merge. A post-push Git-tree/blob readback verifies committed bytes.
- Result-branch CI and human review remain pending before any promotion.

## Current limitation / next action
- No historical Q92 shard has run; no Q92 Discovery/Validation/Blind result exists.
- Next: observe exact-head CI and the new full workflow run. If preflight passes, monitor 15 shard jobs, rerun only failed jobs and preserve successful artifacts; then inspect global Holm, frozen candidates, paired Blind OOS, artifact digest readback and result-branch byte readback.
- PR #6, #7 and #8 are untouched. No auto-merge, promotion or shadow insertion.
