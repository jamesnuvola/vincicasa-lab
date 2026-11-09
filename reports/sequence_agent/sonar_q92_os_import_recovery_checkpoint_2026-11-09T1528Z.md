# VinciCasa SONAR — Q92 aggregate checkout-SHA recovery checkpoint

Captured: 2026-11-09T15:28Z  
Research branch: `research/sonar-q92-exact-null-calibration-20261109`  
Exact current head: `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`  
PR: #23, draft/open. No merge or promotion.

## Canonical experiment identity

- Archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 same-archive frozen control: `P9_06_09_12_14_15_17_18_19_23`; Blind OOS Top-5 11.7910% versus uniform 12.5000%. Q89 has no demonstrated predictive gain.
- Q92: `C(27,10)=8,436,285` equal-weight formulas; 15 shards × 562,419; 3,352 strict-prior targets; Discovery/Validation/Blind OOS = 2,012/670/670; 25,308,855 formula×split metric rows; global Holm family 75,926,565 tests.
- Selection: Discovery top-100 → Validation freeze. Blind OOS excluded from selection.
- Catalog null: discrete convolution of iid Hypergeometric(40,k,5), not the normal approximation. The calibration amendment was registered before the corrected full rerun; it changes p-value calibration, not predictive features.

## Recovered failures and root causes

1. Run [42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368), source `45aab4d...`: all 15 shards completed, but aggregation rejected the canonical final quintet because a tuple was compared with a list. The tuple/list normalization and regression were added.
2. Run [42629657240](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42629657240), source `10986cb...`: artifact reconciliation passed for all 15 source-matched artifacts. Aggregation then failed at `aggregate_sonar_q92_ten_feature.py:602` with `NameError: name 'os' is not defined`. The previous user-facing diagnosis that this run was still failing on tuple/list validation was incomplete; the actual logged terminal exception was the missing `os` import.
3. Run [42641497327](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42641497327), source `497f664...`: preflight passed; at checkpoint capture GitHub exposed 4 shard artifacts, 4 completed shard jobs, 5 in progress and 6 queued. This source is superseded and its artifacts are not reusable for the new exact source.
4. Run [42642886979](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42642886979), source `61a8f9f...`: cancelled when newer source commits were pushed; no jobs/artifacts were produced for that run.

## Implemented correction on PR #23 branch

- Added `import os` to the Q92 aggregator.
- Added `aggregate_checkout_sha(environ=None)`, with explicit `GITHUB_SHA` and `LOCAL_UNPINNED` behavior.
- Replaced the direct `os.environ` expression in manifest generation with the helper.
- Added regression `test_aggregate_checkout_sha_uses_environment_and_local_fallback`, covering environment lookup, explicit mapping and local fallback.
- Aggregator update commit: `9387525f56329ae0955b6f8ad374daa505ef4e1d`; final test update commit/head: `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`.
- Aggregator blob SHA read back: `1118808988269bd102ad61c5439ad88f48202260`.
- Regression-test blob SHA read back: `1c532afdf6773cb1e6a452018a400046e3cf1991`.
- Both files were fetched again from the branch and their content/blob SHAs matched the update responses.

## Validation on the exact current head

- Q92 aggregate/global-Holm/paired synthetic acceptance [42644697629](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697629): SUCCESS. The aggregate-common suite ran 15 tests; the discrete-null suite ran 8 tests; both reported OK. The new checkout-SHA regression is present in the successful log.
- Q92 runner synthetic acceptance [42644697502](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697502): SUCCESS. Runner suite 6 tests and null-calibration suite 8 tests, both OK.
- Exact-head full project CI [42644709284](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644709284): IN PROGRESS at capture.
- Corrected artifact-backed Q92 full walk-forward [42644697822](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42644697822): PENDING with no jobs at capture. The workflow uses a fixed concurrency group; an older attempt still exposed queued/in-progress shard jobs. No shard on the current exact head has been verified as started.
- The Q92 source-hash list includes both the aggregator and aggregate test module. Therefore the new source change invalidates artifacts generated under prior SHAs; all 15 shards must be regenerated on `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`. Do not reuse prior artifacts.

## Leakage and inference guardrails

- For target index i, feature state uses draws before i only; target outcomes enter after ranking for scoring.
- The historical 670-target Blind OOS had already been exposed by earlier Q92 shard computation before the absolute-baseline amendment. Treat all historical Q92 Blind OOS claims as exploratory, not prospective confirmation.
- Relative paired lift over Q89 is insufficient for an absolute claim. The selected candidate must also exceed the uniform Top-5 share 0.125 and have its selected-candidate Top-5 p-value below 0.05 after the full 75,926,565-test Holm correction.
- Paired Q92−Q89 primary gate: Top-5 lift ≥0.005; circular moving-block bootstrap 20,000 replicates, block length 7, 95% lower bound >0; block sign-flip 20,000 replicates with Holm across four endpoints.
- No Discovery, Validation, Blind OOS aggregate, candidate freeze, Holm result, or paired historical result is yet accepted from the corrected exact head.

## New quantitative hypothesis — Q93 proposal only

After Q92 is fully accepted and human-reviewed, test an 11-feature equal-weight catalog:
`C(27,11)=13,037,895` formulas. Selection remains Discovery top-100 → Validation freeze. Confirmatory evaluation must use a new prospective 670-target holdout after the 2026-11-08 cutoff, never the historically exposed Q92 Blind OOS. Proposed gate: paired Top-5 lift ≥0.005 versus the frozen Q92 candidate, 95% block-bootstrap lower bound >0, and Holm-adjusted block sign-flip p<0.05 across Top-5/10/20/mean-rank. Q93 is not preregistered, implemented, or executed.

## Next actions

1. Complete exact-head project CI on `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`.
2. Let the current concurrency-group slot clear; verify Q92 preflight on the exact same head.
3. Regenerate all 15 shards on `f60fddd8fad066d424bceb6b24d4a5dacbb0c790`; require source/archive identity, exact code hashes, artifact manifests and byte digests.
4. Run global Holm aggregation, Discovery→Validation freeze, absolute-uniform evidence, paired Q89 inference and fail-closed acceptance.
5. Persist outputs append-only and verify artifact and Git-tree/blob bytes.
6. Request human review; no merge, engine promotion or shadow insertion.

## Guardrails

PR #6, #7 and #8 remain untouched. PR #23 remains draft/open. No automatic merge, no engine promotion and no shadow insertion.
