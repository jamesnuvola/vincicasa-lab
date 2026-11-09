# SONAR hourly checkpoint — 2026-11-09 04:39 Europe/Rome

## Verified repository state
- Q92 combinadic-core PR #22 head: `51a16a2af84306c8d65daef20dd368dabae7860a`, draft/open, not merged.
- Exact-head dedicated acceptance: PR run 42555422405 SUCCESS; push run 42555397913 SUCCESS.
- Full project CI exact-head: push run 42555397877 SUCCESS; PR run 42555422447 SUCCESS (rechecked 2026-11-09 04:39 UTC).
- Q92 code validated only the finite combinadic catalog helpers and synthetic tests; no Q92 walk-forward shard, aggregate, candidate selection, paired blind inference, output persistence, or full acceptance has been run.

## Canonical archive reconciliation and Q89 same-archive refresh
- Canonical `main` archive blob: `77ca692a6082809fcc6c471501617433ec7c36cf`, 3,402 rows through 2026-11-08; latest draw `3,7,10,16,27`.
- Q89 branch prior archive blob was `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 rows through 2026-11-07.
- Independent line comparison confirmed all 3,401 old records match the main archive after normalizing line endings; only one new row was appended. The apparent mismatch was CRLF versus LF on the 2026-11-07 row, not a data change.
- Updated Q89 branch `research/sonar-q89-nine-feature-20261108` with the canonical archive using contents API. Commit: `5e7301fe2f3bdeb3c85cfd9a4ee810cfdc9c9f77`; reread blob SHA exactly equals canonical `77ca692a6082809fcc6c471501617433ec7c36cf`.

## Runs currently pending at checkpoint
- Q89 matrix refresh on the 2026-11-08 archive: push run 42557762655 IN_PROGRESS; all 15 shard jobs were present and in progress at the last inspection. No refreshed metrics have been accepted yet.
- Q89 PR-triggered recovery run 42557767913 IN_PROGRESS, still downloading/aggregating immutable artifacts from older run 42524743687 (archive through 2026-11-07). These artifacts are not admissible for the new 2026-11-08 archive; acceptance should fail closed on archive/cutoff mismatch. Do not treat this stale recovery as the refreshed result.
- CI push run 42557762695 was CANCELLED by concurrency; current PR CI run 42557767857 is IN_PROGRESS.
- Q91 PR run 42557768007 IN_PROGRESS; its output status has not been checked to completion.
- No output from the refreshed Q89 run has been reported as measured or accepted yet.

## Preregistered quantitative hypothesis Q92
- Finite grammar: all equal-weight unordered 10-feature subsets from 27 prior-only features; exact `C(27,10)=8,436,285`.
- 15 deterministic contiguous shards, 562,419 formulas per shard; batch size 1,024.
- Strict-prefix targets: 3,352, split Discovery/Validation/Blind OOS = 2,012/670/670; each target's features use only draws before that target.
- Metric rows: 25,308,855; global exploratory Holm family: 75,926,565 formula×split×endpoint tests.
- Selection is Discovery top-100 then one frozen candidate in Validation. Blind OOS is excluded from selection.
- Primary paired Blind OOS endpoint: Top-5 hit-share Q92 candidate minus Q89 candidate. Secondary: Top-10, Top-20, mean actual-number rank. Registered circular block bootstrap and block sign-flip (20,000 reps, block 7, fixed seeds), Holm over four paired endpoints.
- Crucial dependency: Q89 must be recomputed/selected on the same 2026-11-08 archive and identical split layout before Q92 candidate comparison.
- Limitations: finite equal-weight subset catalog only; not the infinite mathematical formula universe; retrospective blind tail has prior SONAR exposure; lottery outcome remains stochastic. No promotion/merge.

## Root cause / next action
- Q89 archive refresh is correctly triggered by the archive path change on its branch. The stale recovery event can race it but must not persist stale outputs.
- Wait for all 15 Q89 shards, then aggregate, acceptance validate strict-prefix and archive reconciliation, persist append-only outputs, byte-readback, and exact-head CI. Use only the refreshed Q89 candidate as Q92 control.
- Then implement Q92 runner/aggregator/acceptance/persistence; current PR #22 does not contain those components.
- PRs #6, #7, #8 remain untouched, open/draft and not merged. No automatic merge, shadow insertion or engine promotion.


## Additional verified diagnostics (2026-11-09 04:42 UTC)
- Q92 combinadic regression counts from the exact PR head: 10,007 seeded rank/unrank round trips; 100 lexicographic successor comparisons; 15 contiguous shard intervals; 25-formula sample from shards 0,1,7,14; 550 batch intervals per shard with 562,419 total formulas; p-value helper bounds and deterministic replay tests. Dedicated CI passed. These are helper/unit checks, not full formula walk-forward acceptance.
- Q91 PR-triggered run 42557768007 completed FAILURE. Root cause from decoded job logs: the workflow on PR #20's merge ref reported `Q91_FRESH_EVALUATION_REQUIRED`, then compile failed with `[Errno 2] No such file or directory: scripts/sonar_q91_nested_walkforward.py`. Q91 sources are not present in that merge ref; this is a cross-PR workflow trigger/checkout scope issue, not a model metric failure. No Q91 outputs were evaluated or persisted in this run.
- The current Q89 recovery PR event 42557767913 is downloading the immutable shard artifacts from run 42524743687 (pre-Nov-08 archive). It is a stale-input recovery against a new archive and must be treated as inadmissible; current Nov-08 refresh is the push matrix run 42557762655.
- Current Q89 matrix snapshot: 15 shard jobs are scheduled and each has passed setup, NumPy install and Q89 syntax/unit acceptance; the evaluator step is in progress. No shard has yet been reported complete in the latest snapshot.
- Current project CI push 42557762695 was cancelled by concurrency; PR CI 42557767857 remains in progress. No current-head success has yet been observed for the new archive commit.
