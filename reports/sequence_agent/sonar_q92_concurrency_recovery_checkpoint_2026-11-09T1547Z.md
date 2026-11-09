# VinciCasa SONAR — Q92 concurrency recovery checkpoint

**Recorded:** 2026-11-09 15:47 UTC  
**PR #23 head:** `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c` (open, draft)  
**Research branch:** `research/sonar-q92-exact-null-calibration-20261109`  
**Checkpoint branch:** `checkpoint/sonar-q92-concurrency-recovery-20261109`

## Canonical experiment identity

- Archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Frozen same-archive Q89 candidate: `P9_06_09_12_14_15_17_18_19_23`; prior Blind OOS Top-5 share 11.7910% versus uniform 12.5000%. No demonstrated predictive gain.
- Q92 universe: `C(27,10)=8,436,285` equal-weight formulas; 15 shards × 562,419; 3,352 strict-prior targets; Discovery/Validation/Blind OOS = 2,012/670/670; 25,308,855 formula×split metric rows; global Holm family 75,926,565 tests.
- Selection: Discovery top-100 → Validation freeze; Blind OOS excluded from selection.
- Exact discrete Hypergeometric convolution is the registered null; normal approximation is not used for the Holm tail.

## Methodological amendment retained

The pre-execution amendment `Q92-ABSOLUTE-BASELINE-01` is present in the PR #23 ancestry. Relative paired lift over Q89 is insufficient for an absolute predictive claim.

For the Validation-frozen candidate, the report/validator must expose raw and global Holm-adjusted p-values for Top-5/10/20 across Discovery, Validation and Blind OOS.

Absolute Blind OOS Top-5 evidence is supported only when both:
1. mean Top-5 number-hit share > 0.125; and
2. the selected candidate's Top-5 p-value, adjusted in the registered 75,926,565-test global Holm family, is < 0.05.

Paired Q92−Q89 primary gate remains Top-5 lift ≥ 0.005, circular moving-block bootstrap (20,000 replicates, block length 7) with 95% lower bound > 0, and block sign-flip (20,000 replicates) with Holm across four endpoints. Technical acceptance may return `NOT_DEMONSTRATED`; that is not promotion evidence.

The historical Q92 Blind OOS has been exposed by earlier shard computation. Even if the corrected run produces a valid historical aggregate, it remains exploratory and is not a prospective independent confirmation.

## Root cause addressed in this cycle: stale workflow concurrency

Before this cycle, `.github/workflows/sonar-q92-full-walkforward.yml` used a fixed concurrency group with `cancel-in-progress: false`. A stale Q92 run on source `497f664e6c19fab2070c533a9e0b16d415fd513d` retained active shard jobs and blocked the newer run on `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`. The newer source was waiting without jobs.

The workflow was updated on PR #23 to keep the same Q92 concurrency group and set `cancel-in-progress: true`. This is appropriate because every shard manifest includes the exact workflow/source hashes: a new source SHA invalidates the prior run's artifacts. Stale work must not block a corrected exact-head run.

- Workflow blob before: `2336ed338f22bfd969fc1a52b7f006cbf29617ca`.
- Intermediate dynamic-group commit `d7a065897c5177571a22c3219dd6c156aa4daa9e` was superseded; its Q92 preflight failed because the exact-head CI run was cancelled when the next commit arrived. No shards ran on that SHA.
- Final workflow commit: `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`.
- Workflow blob read back: `0719d97e7dea37cd2592c472ee2feb1a9c419c2d`.
- Final policy: group `sonar-q92-full-walkforward-20261108`, `cancel-in-progress: true`.

### Observed cancellation/restart evidence

- Stale run [42641497327](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42641497327), source `497f664...`, was cancelled after the policy change. It had 7 successful shard artifacts and 8 cancelled shard jobs; aggregate was cancelled. Those artifacts remain immutable but are not reusable for the new exact source.
- Pending run [42644697822](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697822), source `f60fddd...`, was cancelled when superseded. It had no jobs/artifacts.
- Run [42648039409](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648039409), source `d7a0658...`, failed preflight because its exact-head CI was cancelled during supersession. No shard ran on that SHA.
- Corrected Q92 run [42648067242](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648067242), exact source `8f7ac10...`, is now **IN PROGRESS**; its preflight job has started. No shard is yet verified started at checkpoint capture.
- Exact-head full project CI [42648082850](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648082850), source `8f7ac10...`, is **IN PROGRESS** in its validation job. The Q92 preflight waits for this exact-head CI.
- Previous source `f60fddd...` synthetic runner and aggregate/global-Holm acceptance runs [42644697502](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697502) and [42644697629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697629) were SUCCESS. They validate the code state on that source, not the new workflow commit. The exact-head preflight on `8f7ac10...` will rerun the Q92 synthetic regressions.

## New quantitative hypothesis / active gate

The active quantitative hypothesis is Q92-ABSOLUTE-BASELINE-01: a Q92 formula selected without using Blind OOS may demonstrate (a) a paired Top-5 improvement of at least 0.005 over frozen same-archive Q89 and (b) absolute Top-5 evidence above the uniform 0.125 null after the complete global Holm family. These are separate gates; passing the paired gate alone cannot establish absolute predictive advantage.

Q93 remains proposal-only: `C(27,11)=13,037,895` equal-weight formulas; if Q92 completes and is human-reviewed, a later confirmatory test would require a new prospective 670-target holdout after 2026-11-08. Q93 is not preregistered, implemented or executed.

## Leakage, bias and reproducibility controls

- For target index i, feature state must use only draws before i; target outcomes are used only after ranking for scoring.
- Discovery→Validation is the only candidate selection path; Blind OOS is never used to select.
- All shard artifacts must match exact source SHA, archive SHA, declared code hashes, dimensions and deterministic formula intervals.
- Old artifacts from source SHAs `497f...`, `f60f...` or `d7a0658...` must not be mixed with `8f7ac10...`.
- The absolute-baseline and paired historical Blind OOS results remain exploratory because this holdout was previously exposed.

## Next actions

1. Wait for exact-head full project CI [42648082850](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648082850) to complete successfully.
2. Verify Q92 preflight [42648067242](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648067242) passes on the same SHA.
3. Regenerate all 15 shards on `8f7ac10...`; do not reuse partial artifacts from older SHAs.
4. Reconcile all shard manifests, raw artifact digests, formula intervals, target ledgers and source hashes.
5. Run global Holm aggregation, Discovery→Validation freeze, selected-candidate Holm replay, absolute-uniform evidence and paired Q89 inference.
6. Run fail-closed acceptance, append-only persistence, artifact digest readback and Git blob/tree byte readback.
7. Request human review. No merge, engine promotion or shadow insertion is authorized.

## PR guardrails

PR #6, #7 and #8 remain open and untouched. PR #23 remains open/draft and its head is `8f7ac10...`. No merge was performed.
