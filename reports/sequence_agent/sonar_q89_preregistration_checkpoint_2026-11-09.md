# VinciCasa SONAR — Q89 preregistration checkpoint

Date: 2026-11-09

## Recovered Q80 evidence

- PR #8 head at recovery: `0f865d6585a768f623e7c56cfffc5fd4a48a7888`; PR #8 remains open/draft and is not modified by this branch.
- Run `40372963487` completed SUCCESS on its then-current head, but its Q80 queue report was not acceptance-clean. Exact cause: the queue validator used generic `SPLITS=(discovery, validation, oos)`, while Q80 emits `blind_oos`; the validator reported an invalid Q80 split/feature count.
- Run `40372554318` was CANCELLED; it did not establish a formula-count failure.
- The later PR branch contains the fix: Q80 validation uses `Q80_SPLITS=(discovery, validation, blind_oos)`.
- Current persisted Q80 report: 3,401 draws through 2026-11-07; 3,351 scored targets; 27 features; 3,303 formulas; 9,909 formula×split rows; splits 2,011/670/670.
- Q80 metrics blob `28a4dac5526afd83243cb7e81246ce6756c31593` and ledger blob `d9305b715bdac41ad407c9e302694060f2266297` were read back. Metrics contain 3,303 formulas per split; ledger contains 3,351 rows. Target dates, actual quintets, immediate prior cutoffs and prior-draw counts reconcile against the branch archive.
- Q80 queue status is `VALIDATED_PENDING_HUMAN_REVIEW`, with no validation errors. It is not COMPLETE and does not imply promotion.
- The immutable 2026-10-25 prospective freeze remains in `shadow_forecasts.csv` (43 rows for that target); it was not changed.
- Research branch archive is one draw behind main: branch through 2026-11-07 (3,401 draws), main through 2026-11-08 (3,402). Q89 pins the 2026-11-07 snapshot for same-target comparability with Q88; the 2026-11-08 draw is intentionally excluded.

## New quantitative hypothesis Q89

- Evaluate all `C(27,9)=4,686,825` unordered nine-feature equal-weight formulas.
- Use 30 balanced contiguous lexicographic shards (156,227 or 156,228 formulas each), 1,024-formula batches, 15 concurrent jobs.
- Score 3,351 strict-prior targets: Discovery 2,011; Validation 670; Blind OOS 670.
- Expected 14,060,475 formula×split rows and 42,181,425 formula×split×endpoint tests.
- Replace the earlier binomial/normal approximation with conservative Chernoff upper bounds for sums of per-target Hypergeometric(40,k,5) hit counts, k=5,10,20; apply one global Holm-Bonferroni correction.
- Select Discovery top-100, freeze one candidate using Validation only, then read Blind OOS only for that frozen candidate.
- The per-target best-formula ledger is retrospective/descriptive, not a forecast.
- Q89 is preregistered but not run. No Q89 shard, aggregate, Holm result or candidate exists yet.

## Gates

- Q80 outputs are persisted and independently reconciled on the branch snapshot.
- Q80 queue split-label defect is fixed in the current branch.
- Q89 exact-head CI must pass before a run-request commit starts the 30-shard walk-forward.
- Acceptance, chunked Git Data API persistence/readback, exact-head CI and human review/integration are separate gates.
- No merge, automatic promotion or shadow insertion.

## Exact-head CI and concurrency checkpoint (2026-11-09)

- Exact-head push CI run `42667513762` on commit `513b9a91db1d34b0609ce1176f076722244cbaac` completed SUCCESS. The Q89 protocol test step succeeded (9 unit tests), and the existing Q80 and Q88 acceptance validators both returned no errors.
- Added a further preflight compile gate for `persist_q89_outputs.py` and `sonar_research_queue.py` in CI; the change is on commit `87d2be3061e0eeaeac7380041d6f342e99c43da9`.
- The subsequent exact-head push CI run `42668177660` was CANCELLED at job setup when concurrent pull_request runs for draft PR #24 entered the same branch concurrency group. This was an orchestration cancellation, not a test failure.
- PR #24 is temporarily closed (not merged) while the push-only exact-head CI and Q89 run-request workflow execute. Reopen it for human review after the run/persistence gates; no merge is authorized.
- Next: run the exact-head CI on the current checkpoint commit; only after SUCCESS, add the Q89 run-request file with a `[q89-run]` commit message. The Q89 workflow then waits for CI on that exact SHA before launching the 30 shards.

## Q89 full walk-forward request

- The exact-head CI on parent `3bd82d03343dc85871b237c96b5ae0ecc7eff189` completed SUCCESS in run `42668311363`.
- The CI step compiled the Q89 runner, aggregator, persistence script and queue validator; ran the nine Q89 unit tests; and ran the Q80 and Q88 acceptance validators. The overall workflow concluded SUCCESS.
- A separate run request is now committed as `reports/sequence_agent/q89_run_request_2026-11-09.json` with status `RUN_REQUESTED`.
- The request pins the protocol blob `cd2f9af7e78e943949443646f453515ca5e59ece`, archive SHA `3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed`, 4,686,825 formulas, 30 shards and 3,351 scored targets.
- The Q89 workflow must wait for SUCCESS of `ci.yml` on the exact run-request commit SHA before starting any shard. The parent CI success does not substitute for this exact-head gate.
- At checkpoint time no Q89 shard has been launched and no Q89 predictive result exists.

## Persistence failure and recovery checkpoint

- Full Q89 walk-forward run `42668855015`: all 30 shard jobs SUCCESS; aggregate job SUCCESS; fail-closed Q89 acceptance returned an empty error list.
- Aggregate artifact `sonar-q89-aggregate`: 495,303,500 bytes; archive digest `sha256:82e08396f62e33f469f601a20732688133baa633fbb22ae79a2d67bdb375c88e`.
- The persistence job `129359549834` failed before branch-ref update. Its log ends with GitHub API HTTP 502 after six retries; the branch remains at the run-request head `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`. No aggregate outputs were committed to the experiment branch by that failed job.
- This is an infrastructure/API failure after successful shard computation and aggregate acceptance, not a statistical or data-validation failure.
- Recovery reuses the immutable aggregate artifact from run `42668855015`; it does not rerun the 30 shards.
- The Q89 acceptance validator's combinadic rank calculation is optimized with precomputed prefix sums. The persistence script now relies on one queue-driven fail-closed validation pass, adds API method/path diagnostics, throttles writes slightly, and retries transient 5xx/429 responses for a longer bounded window.
- The recovery workflow waits for exact-head CI, downloads the original aggregate artifact by run ID, persists report/manifest/469 metric parts/ledger/queue/checkpoint through Git Data API, verifies every blob's SHA and bytes, then waits for persisted exact-head CI.
- Q89 remains pending repository persistence and persisted-head CI. It is not COMPLETE and not promoted.

## Recovery attempt 2 — exact-head CI condition correction

- Recovery commit `ae271ee786d68d0b4d0212fb8deced9edc42f884` correctly compiled the optimized validator/persistence code and passed the Q89 unit tests and Q80/Q88 validators.
- Its exact-head CI nevertheless failed because a broad string replacement accidentally added `[q89-persist-recovery]` to the persisted-output validator step. That step therefore ran before the aggregate artifact was restored and correctly failed closed with missing report/manifest/ledger and unvalidated queue status.
- Corrected the CI condition: the full persisted-output validator now runs only for `[q89-persisted]` commits (or a PR head that actually contains the persisted report). The recovery marker still runs protocol tests and compiles the persistence code, but does not pretend outputs are already persisted.
- The original aggregate artifact from run `42668855015` remains the source; no shards are rerun. Recovery request attempt 2 is now registered.

## Recovery attempt 3 — incremental Git tree persistence

- Recovery attempt 2 downloaded the original aggregate artifact and passed exact-head CI, but failed at `POST /git/trees` with HTTP 422: GitHub timed out on one request containing all 469 metric-part paths.
- All blob creation and the earlier aggregate acceptance succeeded; the branch ref was not advanced, so no aggregate outputs were partially committed.
- Root cause is the oversized single tree request, not a data/metric failure.
- Persistence is now split into 25 metric-part files per Git tree/commit. Each chunk uses branch-head compare-and-swap, verifies the resulting commit/tree, and reads back every new blob byte-for-byte. Existing paths are accepted only if their immutable Git blob SHA and size match; this supports recovery from partial chunk commits.
- Report, manifest, target ledger, queue status and checkpoint are held for the final `[q89-persisted]` commit. Intermediate `[q89-persist-chunk]` commits skip the full CI job; the final commit runs the Q89 acceptance validator.
- Unit tests now cover chunk partitioning and Git blob SHA calculation. The recovery request reuses aggregate artifact from run `42668855015`; no shard is rerun.

## Recovery attempt 4 — explicit mutable queue snapshot

- Recovery attempt 3 passed exact-head CI, restored the accepted aggregate artifact and ran the fail-closed queue validator, but stopped before any Git ref update.
- The idempotent resume guard found the pre-existing `research_queue_status.json` from the Q89 run-request commit. It differed from the newly generated Q89-validated queue snapshot and was treated as an immutable conflict.
- Root cause: the queue status is a deliberately mutable generated snapshot, unlike the immutable metrics parts, report, manifest and target ledger.
- The persistence script now explicitly permits replacement of only `reports/sequence_agent/research_queue_status.json`; every other existing output path remains fail-closed unless SHA and size match exactly. A regression test enforces this allowlist.
- The 25-file chunked Git Data API strategy remains. The original accepted aggregate artifact is reused; no historical shard is rerun.
