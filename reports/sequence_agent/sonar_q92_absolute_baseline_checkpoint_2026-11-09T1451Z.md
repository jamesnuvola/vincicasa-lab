# VinciCasa SONAR — Q92 absolute-baseline audit checkpoint

**Recorded:** 2026-11-09 14:51:32 UTC  
**Research branch:** `research/sonar-q92-absolute-baseline-audit-20261109`  
**Base source commit:** `10986cb6bf256550821d79f3139b3b37798887cf`  
**State:** code and protocol amendment prepared; full integration CI and corrected historical rerun not yet verified.

## Verified prior state

- Canonical archive remains the 3,402-draw archive through 2026-11-08, Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Q89 same-archive control is recorded as `VALIDATED_PENDING_HUMAN_REVIEW`; its prior Blind OOS Top-5 share was 11.7910%, below the uniform expectation 12.5%.
- Q92 run `42615347368` completed preflight and all 15 shards, but its aggregate job failed at canonical archive quintet validation because tuple values were compared with a list returned by `sorted()`.
- The tuple/list fix and regression tests are present at commit `10986cb6bf256550821d79f3139b3b37798887cf`. The associated project CI run `42629662800` completed SUCCESS, but its Q92-specific branch-only test steps were skipped; this is not evidence that the dedicated Q92 full walk-forward has rerun.
- The old 15 shard artifacts are bound to their previous source checkout/hash manifest. They must not be mixed with the corrected source. A corrected exact-head run must regenerate all 15 shards.

## Exposure caveat for the amendment

The earlier failed Q92 run `42615347368` had already generated all 15 shard artifacts before the absolute-baseline amendment was registered. No aggregate was accepted and those artifacts were not used to select this gate in the present cycle, but this is an amendment before the corrected replay, not before any historical Q92 computation. Therefore the historical Blind OOS and the new absolute-baseline status are exploratory, not untouched prospective confirmation. Confirmatory evidence requires a new preregistered prospective holdout of 670 new draws.

## New methodological finding

The Q92 paired primary comparison is relative to Q89. Since the recorded Q89 Blind OOS Top-5 share is below the uniform baseline, a paired improvement of 0.005 over Q89 could still leave Q92 below uniform. A relative lift alone must not be presented as absolute predictive advantage.

The aggregate already computes a global Holm family of 75,926,565 formula×split×endpoint tests, but the selected candidate's own adjusted p-values were not exposed in the selection/report/acceptance summary. This checkpoint adds that audit trail and an absolute-baseline evidence status.

## Pre-execution amendment Q92-ABSOLUTE-BASELINE-01

For the Validation-frozen candidate, persist raw and global Holm-adjusted p-values for Top-5/Top-10/Top-20 in Discovery, Validation and Blind OOS.

Absolute Blind OOS Top-5 evidence is `ABSOLUTE_LIFT_SUPPORTED` only if both:
1. `mean_number_hits_top5 > 0.125`;
2. the candidate's Top-5 p-value adjusted in the already registered 75,926,565-test global Holm family is < 0.05.

This does not change formula universe, feature stack, candidate selection, split definitions, global family or paired Q92-vs-Q89 inference. Technical acceptance may complete with `NOT_DEMONSTRATED`; that status does not permit promotion.

For 670 Blind OOS targets, the uniform expectation is 418.75 Top-5 hits across the 5 actual numbers per target. Under the discrete iid Hypergeometric(40,5,5) null, the one-sided unadjusted 5% tail first occurs at 450 total hits (share 0.134328). The first Holm step threshold for a 75,926,565-test family is 6.58531e-10; the corresponding first-step reference is 533 hits (share 0.159104). The actual selected-candidate adjusted p-value must be read from the complete Holm vector; the first-step count is diagnostic only, not a substitute for Holm rank.

## Implementation

Changes on this branch:

- `scripts/sonar_q92_aggregate_common.py`: added selected-formula Holm extraction and absolute uniform-baseline evidence helpers.
- `scripts/aggregate_sonar_q92_ten_feature.py`: selection, manifest and report now expose candidate-specific raw/adjusted p-values and absolute-baseline evidence.
- `scripts/validate_sonar_q92_ten_feature.py`: reconstructs the selected candidate's Holm p-values from the compact metric parts and full adjusted vector; independently recomputes the baseline evidence and compares selection, report and manifest.
- `tests/test_sonar_q92_aggregate_common.py`: added mapping and gate regressions.
- `reports/sequence_agent/q92_preregistration_2026-11-09.json` and `.md`: recorded amendment before the corrected full walk-forward rerun.
- `.github/workflows/sonar-q92-full-walkforward.yml`: acceptance summary now carries the selected-candidate Holm and baseline evidence.

### Important indexing correction

The aggregate p-value vector is **shard-major**, then split-major within each shard, formula-rank ascending within split, then endpoint order. The first helper draft assumed global split-major ordering. This was caught by code-path inspection before any Q92 results were accepted, corrected to use:

`offset = (shard_index * shard_size * 3 + split_index * shard_size + local_rank) * 3`

A synthetic mapping regression uses 3 shards × 4 formulas × 3 splits × 3 endpoints and checks formula rank 6 / split 1 maps to endpoint indices 54–56. The helper now validates only the selected three-value slice, avoiding repeated scans of the full 75.9M-value vector.

## Tests and validation actually completed in this cycle

- Independent local helper regression replay: PASS for shard-major index mapping, invalid vector/rank/split rejection, and both positive/negative absolute-baseline gate cases.
- GitHub repository readback: modified helper, aggregator, validator, tests, preregistration JSON/Markdown and workflow were fetched back from this branch with the new blob SHAs.
- **Not yet run:** the repository's full Python test suite on this branch, exact-head project CI, dedicated Q92 synthetic preflight, corrected 15-shard historical walk-forward, global Holm aggregation, acceptance validator, artifact byte readback, result-branch persistence, or human review.
- No new Q92 Discovery, Validation or Blind OOS measurements exist from this cycle.

## Next action

1. The PR #23 head was fast-forwarded to commit `497f664e6c19fab2070c533a9e0b16d415fd513d`; exact-head project CI run `42641511859` passed, while Q92-specific steps in that general CI were skipped.
2. Verify the dedicated Q92 preflight/run on the corrected exact head; its push-run status is not exposed by the connected run-list action.
3. Regenerate all 15 shard artifacts because source hashes changed.
4. Run aggregation and acceptance; inspect Discovery, Validation, selected-candidate global Holm values, absolute uniform-baseline status and paired Q89 inference.
5. Persist accepted artifacts append-only and verify artifact digest plus Git blob byte readback.
6. Treat historical Blind OOS as exploratory; require a new prospective 670-draw holdout for confirmation. Request human review. No merge, engine promotion or shadow insertion is authorized.

PR #6, #7 and #8 are out of scope and must remain untouched.
