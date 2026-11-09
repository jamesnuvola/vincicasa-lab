# VinciCasa SONAR — Q92 live recovery checkpoint

**Recorded:** 2026-11-09 16:39 UTC  
**Research source commit:** `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`  
**Research branch:** `research/sonar-q92-exact-null-calibration-20261109`  
**Q92 workflow run:** [42648067242](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648067242)  
**Exact-head full project CI:** [42648082850](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648082850)

## Verified live execution state

- Exact-head full project CI: **SUCCESS** on `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`.
- Q92 preflight: **SUCCESS**; all 11 listed steps completed, including exact-head CI wait, compilation, synthetic regressions, canonical archive/Q89 freeze replay and pre-execution amendment checks.
- Q92 matrix: **14/15 shard jobs SUCCESS**; shard 13 is still `IN_PROGRESS`; no shard failure was reported at checkpoint time.
- Q92 artifacts: **14 immutable shard artifacts** visible; all are named `q92-20261108-shard-<index>-attempt-1`, are not expired, and identify the same source SHA `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`.
- Shard 12 and shard 13 were the last running jobs in the preceding poll; in the latest poll shard 12 had completed and shard 13 remained in progress.
- Aggregate job has not yet appeared because the matrix dependency has not completed. No aggregate report, candidate freeze, paired inference or accepted Q92 result exists yet.
- Do not infer the contents or metrics of the running shard from its job status.

## Canonical experiment identity

- Archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q92 formula universe: `C(27,10)=8,436,285`; 15 contiguous lexicographic shards × 562,419 formulas.
- Walk-forward: 3,352 scored targets; Discovery/Validation/Blind OOS = 2,012/670/670.
- Expected compact metric rows: 25,308,855; target ledger rows: 3,352.
- Global Holm family: 75,926,565 formula × split × endpoint tests.
- Formula batch size: 2,048; 275 batches per shard; 4,120 global batches.
- Same-archive Q89 frozen candidate: `P9_06_09_12_14_15_17_18_19_23`; historical Blind OOS Top-5 share 11.7910% versus uniform 12.5000%. No demonstrated predictive gain.

## Code and leakage audit performed this cycle

Read back from exact source `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`:

- Runner blob: `d9cf7bbe1a8d3db7cddaac6628ef3cde989a7a56`.
- Feature-stack blob: `f9cbf1c64deb2f2eabf7e6f35ba2523a9404625b`.
- Null-calibration blob: `c0aba3411a39d4d6473f35ace082e4f853b59f2`.
- Q92 common blob: `647025282b57938ca66549757ef512e2bfd3dfb5`.
- Preregistration blob: `4457e898ec5c1ccd904d443c68b4ad8f5770c4e7`.
- Aggregator blob: `1118808988269bd102ad61c5439ad88f48202260`.
- Acceptance validator blob: `c6250a995aa2feb6615de697acb967e9a3205a6e`.

Manual source inspection confirms:
1. `build_feature_stack` computes the feature matrix at index `i` using `prefix[i]`, `position_prefix[i]`, prior occurrence lists, `draws[i-1]` and lagged `draws[i-lag]`.
2. Feature state is updated only after the feature matrix for index `i` has been computed.
3. The Q92 runner scores target `i` only after retrieving the standardized prior-only feature matrix; target values are used to score actual-number ranks, not to build that target's feature state.
4. Exact ties in selective ranking are resolved by lower number ID.
5. The target ledger records target date, cutoff date `i-1`, prior draw count `i`, and actual quintet.
6. The retrospective per-target best formula is explicitly labelled descriptive, not an ex-ante selection rule.
7. Discrete null p-values use convolution of iid Hypergeometric(40,k,5) hit counts; the normal approximation is retained only as an audit comparison.

This is a source-level review, not a substitute for completed artifact reconciliation and acceptance replay.

## Statistical protocol and limitations

- Discovery top-100 → Validation selection/freeze; Blind OOS excluded from candidate selection.
- Global Holm-Bonferroni family is 8,436,285 × 3 splits × 3 endpoints = 75,926,565.
- Paired Q92−Q89 Top-5 gate: mean delta ≥ 0.005; circular moving-block bootstrap 20,000 replicates, block length 7, 95% lower bound > 0; block sign-flip 20,000 replicates, Holm across four paired endpoints.
- Absolute uniform gate: selected candidate Blind OOS Top-5 share > 0.125 and its already-global-Holm-adjusted Blind OOS Top-5 p-value < 0.05.
- Earlier failed run 42615347368 had generated all 15 historical shard artifacts before the absolute-baseline amendment. Therefore the historical Blind OOS remains exposed/exploratory, not prospective independent confirmation.
- The exact iid Hypergeometric null assumes independent uniform 5-of-40 lottery draws. Holm controls family-wise error only if the component p-values are valid under that null.
- No Q92 predictive conclusion can be made before the complete aggregate and acceptance replay; no result is being claimed in this checkpoint.

## Next actions

1. Re-poll run 42648067242 until shard 13 completes or fails.
2. Confirm 15/15 successful shard jobs and 15 source-bound artifacts.
3. Wait for the aggregate job; inspect all logs and artifacts.
4. Reconcile exact source/archive hashes, formula-rank intervals, dimensions, target ledgers and raw artifact digests.
5. Run global Holm, Discovery→Validation freeze, selected-candidate adjusted-p replay, absolute-uniform gate and paired Q89 inference.
6. Complete fail-closed acceptance, compact-bundle digest readback, append-only result-branch persistence and Git tree/blob byte readback.
7. Persist results and limits in a separate result branch; request human review.

## Guardrails

- PR #23 remains research-only/open; no merge or engine promotion.
- PR #6, #7 and #8 are explicitly excluded from all writes and remain untouched.
- No shadow-stream insertion.
- No automatic merge or model promotion.
