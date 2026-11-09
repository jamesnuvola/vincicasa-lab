# SONAR Q89 — run-started checkpoint

Captured: 2026-11-09T17:57:14.153Z

## Exact-head gates

- Protocol commit: `41569225101dd13e4e359fc1b79622afb19fc909`.
- Queue validator/persistence/workflow commit: `513b9a91db1d34b0609ce1176f076722244cbaac`.
- Persistence compile-gate commit: `87d2be3061e0eeaeac7380041d6f342e99c43da9`.
- Recovery checkpoint commit: `3bd82d03343dc85871b237c96b5ae0ecc7eff189`.
- Run-request commit / frozen execution head: `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`.
- Exact-head CI on the run-request commit: run `42668854880`, conclusion **SUCCESS**.
- Q89 protocol test step passed; it compiled the runner, aggregator, persistence script and queue validator, ran 9 unit tests, and ran Q80 and Q88 acceptance validators with no errors.

## Q89 execution

- Full walk-forward workflow: run `42668855015`.
- Preflight waited for and accepted exact-head CI on `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`.
- Matrix: 30 shards, max parallel 15.
- At checkpoint: 14 shard jobs in progress, 15 queued, 0 shard artifacts published; the preflight job is complete. No shard failure observed.
- The workflow is pinned to `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`; do not move the experiment branch while it runs because persistence checks the expected branch head.
- No Discovery, Validation, Blind OOS, Holm, candidate or predictive result has been produced yet.

## Research definition

- 4,686,825 nine-feature equal-weight formulas over 27 prior-only features.
- 3,351 targets with at least 50 prior draws; split 2,011/670/670.
- 30 balanced lexicographic shards; 1,024-formula batches.
- 14,060,475 formula×split rows; global Holm family 42,181,425 formula×split×endpoint tests.
- Conservative Chernoff upper bounds for sums of per-target Hypergeometric(40,k,5) hit counts, k=5,10,20.
- Discovery top-100 → Validation freeze → Blind OOS read only for the frozen candidate.
- Per-target best-formula ledger is retrospective/descriptive, not a forecast.

## Branch/PR safety

- PR #24 is temporarily closed, not merged, to prevent concurrent pull_request CI from cancelling the exact-head push CI. Reopen only after Q89 persistence and exact-head CI.
- PR #6, #7 and #8 remain untouched; no merge or promotion is authorized.
- No change to the immutable 2026-10-25 prospective freeze or `shadow_forecasts.csv`.
