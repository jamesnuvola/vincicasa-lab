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
