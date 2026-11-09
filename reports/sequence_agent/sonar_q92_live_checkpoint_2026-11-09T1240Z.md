# VinciCasa SONAR — Q92 live progress checkpoint
Captured: 2026-11-09T12:40Z (GitHub job/artifact observations)

## Scope and immutable identity

- Experiment: Q92, exhaustive equal-weight 10-feature subset grammar, strict-prior walk-forward.
- Source commit: `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.
- Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Formula universe: `C(27,10)=8,436,285`; 15 contiguous rank shards × 562,419 formulas.
- Targets: 3,352; Discovery 2,012, Validation 670, Blind OOS 670.
- Expected rows: 25,308,855 formula×split metrics; global Holm family 75,926,565 catalog tests.

## Verified gates

- Exact-source full project CI, run [42615360700](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615360700): SUCCESS.
- Q92 synthetic acceptance, run [42615347316](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347316): SUCCESS.
- Q92 artifact-backed preflight in run [42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368): SUCCESS, 11/11 steps.
- Preflight reconciled archive SHA/count/date/final quintet and the same-archive Q89 frozen candidate/control.
- Earlier tuple-vs-list guard failure was corrected; no new shard failure is observed in the current run.

## Shard progress at capture

Run-level API state is still `queued`; matrix job-level states are authoritative. Six of 15 shards completed successfully (40% formula coverage): indices 0, 1, 2, 3, 4, 7. Five are in progress (5, 6, 8, 9, 10); four are queued (11, 12, 13, 14). No aggregation job has started.

Each completed shard reports 1,687,257 metric rows (562,419 formulas × 3 splits) and 3,352 target-ledger rows. Total verified completed metric rows: 10,123,542.

| Shard | Artifact ID | ZIP bytes | ZIP SHA-256 (independently downloaded and matched to upload log) | Completed UTC |
|---:|---:|---:|---|---|
| 0 | 13673307210 | 59,875,272 | `480c04cb85d6c778c8755aef6c6e1f538b68a754334ed4d1c91dad75229b7af1` | 12:28:55 |
| 1 | 13673685700 | 60,623,592 | `6ba32ceedfb72c77c28f91dc3e1a0bdd83cafa6d5e6fd2f1a18732f0b59137e1` | 12:30:49 |
| 2 | 13675565276 | 60,470,670 | `e6b7817e45f29643cf03173f61e311f7f0a37738a9aa70479f1f4cdad01e2bd7` | 12:40:15 |
| 3 | 13674500369 | 60,964,278 | `4ba5cf712742ccb9e41b9389ffef39c7a0fa279655b418c763b2ef0fb1311370` | 12:40:20 |
| 4 | 13671944602 | 61,300,310 | `1b751b0c260bb0848b1e54c2e8cce3cbd80f3cd754e547fed31504584366c8a9` | 12:29:11 |
| 7 | 13672609798 | 61,542,275 | `734cbaa3a9ce7942ede457ebf9d18c60c545192a1fe8c94f87ed7a2145111f6c` | 12:38:33 |

For all six downloaded artifacts, the ZIP digest matched the digest printed by GitHub's upload log. Each shard report/manifest matches the registered source checkout SHA and canonical archive SHA. The manifests contain per-file byte counts and SHA-256 values for metrics CSV, target ledger and report.

## Leakage and reproducibility checks actually performed

- Source inspection: Q81 feature construction calls `feature_matrix(i,...)`, whose docstring and implementation use `prefix[i]` / `draws[:i]`; occurrence, pair and gap states are updated only after scoring target `i`.
- Across all six artifact ledgers, the common core fields (target date, cutoff date, prior-draw count, actual quintet, status) are identical.
- Each ledger has 3,352 unique monotonically ordered target dates; first target 2017-09-05 uses cutoff 2017-09-04 and 50 prior draws; final target 2026-11-08 uses cutoff 2026-11-07 and 3,401 prior draws.
- All artifact SHA-256 receipts were independently checked after download.
- Limitation: the full Q92 acceptance replay against all 15 shard artifacts has not run; these checks do not replace global aggregation/acceptance.

## Statistical status — no predictive conclusion yet

Shard reports are `SHARD_COMPLETE_NOT_TASK_COMPLETE`; catalog-level Holm remains pending. Discovery and Validation metrics exist only inside partial shards; no global top-100 Discovery pool, Validation freeze, paired Blind OOS inference, adjusted p-values or accepted Q92 result has been produced.

Same-archive Q89 control remains the previously accepted technical baseline: Blind Top-5 11.7910% vs uniform 12.5000%, with no formula/split passing Holm at 0.05. This does not establish Q89 predictive skill.

## Next quantitative hypothesis (proposal only; not preregistered)

After Q92 completion and human review, propose Q93 with `C(27,11)=13,037,895` equal-weight 11-feature formulas. Discovery top-100 → Validation freeze; Blind OOS never used for selection. Compare a frozen Q93 candidate against Q92 on a new prospective 670-target holdout after the 2026-11-08 cutoff. Proposed primary minimum practical lift: paired Top-5 ≥ 0.005 absolute; 95% circular block-bootstrap lower bound > 0; block sign-flip p-value Holm-adjusted < 0.05 across Top-5/10/20 and mean-rank endpoints. This is only a proposal and must be preregistered before any Q93 execution.

## Next actions

1. Monitor shards 5, 6, 8, 9, 10 and queued 11–14; retry only failed shards.
2. Preserve immutable artifacts and reconcile each upload/download digest and source manifest.
3. Once all 15 shards complete, run the global aggregator and acceptance replay; reconcile 25,308,855 metric rows and 75,926,565 Holm tests.
4. Freeze Discovery top-100 → Validation candidate; run paired Blind OOS against same-archive Q89 with the preregistered block bootstrap/sign-flip and Holm family of four endpoints.
5. Persist append-only outputs/receipts and verify exact Git blob/tree readback plus result-branch CI before human review.

PR #23 remains draft/open. PR #6, #7 and #8 remain open/unmerged and untouched. No merge, engine promotion or shadow insertion.
