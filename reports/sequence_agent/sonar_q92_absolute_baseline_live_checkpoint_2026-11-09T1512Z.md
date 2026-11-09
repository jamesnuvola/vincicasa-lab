# VinciCasa SONAR — live checkpoint after Q92 absolute-baseline amendment

**Recorded:** 2026-11-09 15:12 UTC  
**Source/PR head:** `497f664e6c19fab2070c533a9e0b16d415fd513d`  
**PR:** #23, open draft; no merge performed.  
**Checkpoint branch:** `checkpoint/sonar-q92-absolute-baseline-live-20261109`

## Completed in this cycle

1. Recovered Q92 state: the prior full run `42615347368` completed all 15 shard jobs, but the aggregate job failed on tuple-versus-list archive validation. No accepted Q92 aggregate was produced.
2. Verified the tuple/list fix at `10986cb6bf256550821d79f3139b3b37798887cf`; the exact-head project CI run `42629662800` passed, though Q92-specific steps in that general PR CI were skipped.
3. Added the pre-execution amendment `Q92-ABSOLUTE-BASELINE-01`: a relative paired gain over the below-uniform Q89 control is not enough to claim absolute predictive value.
4. Implemented selected-candidate raw and global Holm-adjusted p-value reporting for Top-5/10/20 in each split; added the absolute Blind OOS gate: mean Top-5 share >0.125 and selected candidate's global Holm-adjusted Blind OOS Top-5 p<0.05.
5. Added fail-closed replay in the acceptance validator, report/manifest/selection fields, and acceptance-summary output.
6. Caught and corrected a vector-indexing issue before accepting any Q92 results: the global p-value vector is shard-major, split-major within each shard, formula-rank ascending, then endpoint. The selected-candidate offset now follows that exact layout.
7. Added synthetic regressions for shard-major mapping and both positive and negative absolute-baseline gate cases. An isolated local replay of the helper logic passed.
8. Read back the modified repository files and verified blob SHA values; the amendment and code are persisted on PR #23's head.

## Current exact-head CI

- Run `42641511859`, PR #23 head `497f664e6c19fab2070c533a9e0b16d415fd513d`: **SUCCESS**.
- This is the general project CI. Its Q92-specific conditional steps were skipped, so it does not validate the new Q92 aggregator/validator integration.
- The dedicated Q92 push workflow is not exposed by the connected workflow-run listing action. Its status is therefore **unverified**, not assumed successful.
- No `research/sonar-q92-results-20261108` branch exists at this checkpoint; no new accepted aggregate or Q92 Discovery/Validation/Blind OOS measurements are available.

## Quantitative context

- Q92 catalog: `C(27,10)=8,436,285` formulas, 15 shards, 562,419 formulas/shard.
- Chronological targets: Discovery 2,012; Validation 670; Blind OOS 670.
- Metric rows: 25,308,855; global Holm family: 75,926,565 tests.
- Uniform Top-5 mean hit-share baseline: 0.125. Q89 same-archive prior Blind OOS Top-5 share: 0.117910.
- For 670 targets, the uniform null expectation is 418.75 Top-5 hits. The discrete one-sided unadjusted 5% tail first occurs at 450 hits; the first Holm-step reference for 75,926,565 tests is 533 hits. The actual selected-candidate Holm p-value must be extracted from the complete global vector; these counts are calibration references only.

## Next action

1. Verify the dedicated Q92 preflight on exact head `497f664e6c19fab2070c533a9e0b16d415fd513d`.
2. Regenerate all 15 shard artifacts because the source hash manifest changed; do not reuse artifacts from the failed earlier source.
3. Run aggregation, candidate-specific Holm replay and absolute uniform-baseline reporting.
4. Run fail-closed acceptance, append-only artifact persistence, digest readback and Git blob readback.
5. Review Discovery, Validation, Blind OOS and paired Q89 inference. Human review remains mandatory.

PR #6, #7 and #8 were not modified; no merge, engine promotion or shadow insertion occurred.
