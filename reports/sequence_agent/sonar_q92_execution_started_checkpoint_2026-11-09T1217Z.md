# VinciCasa SONAR — Q92 execution-started checkpoint

Recorded after exact-head CI and preflight completion on 2026-11-09.

## Verified run gates

- Source head: `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.
- Exact-head full project CI: [run 42615360700](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615360700) — **SUCCESS**.
- Q92 strict-prior runner synthetic acceptance: [run 42615347316](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347316) — **SUCCESS**. Log confirms regression `test_canonical_archive_last_draw_matches_registered_quintet` passed; suite reported 6 tests OK, plus 8 aggregate tests OK.
- Q92 artifact-backed full walk-forward [run 42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368): preflight **SUCCESS, 11/11 steps**; matrix shards now launched.
- At this checkpoint, shard jobs 0, 1, 2, 3 and 4 were IN PROGRESS at “Run immutable strict-prior formula shard”; remaining 10 shards were QUEUED. No shard artifact had yet appeared and no shard completion was observed. GitHub run-level state was still reported as queued despite active matrix jobs; job-level state is the more precise signal.

## Recovered cause and fixed guard

The previous full run [42612668612](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42612668612) passed exact-head CI but failed preflight at the canonical final-quintet check. The archive parser returns sorted tuples, while the workflow compared to a list. The value was right; the type was wrong.

Commit `45aab4d40c90d2cee976f6fad89156bdf0b6a089` changed the guard to tuple equality and added the canonical archive regression. Readback blob SHAs:
- Workflow: `9c3b390161849b36c08995ea031bbe46e6296444`.
- Test: `13728b02365b6427ca338e5e5ac2e23426067aec`.

## Leakage and selection audit

Repository source readback confirms:
- Q81 computes feature matrix at target index `i` from `q80.feature_matrix(i,...)`, documented and implemented using prefix `draws[:i]`; the running state is updated only after target features are computed.
- Lag features reference indices `i-lag`; position, pair and gap state are all prefix-only.
- Q92 runner ranks all 40 numbers before it scores the target quintet; actual target numbers are used only to compute hit/rank metrics.
- Aggregator constructs Discovery top-100, sorts those candidates by Validation metrics and freezes one candidate; Blind OOS is descriptive and excluded from selection ordering. Acceptance validator replays the freeze and paired Blind OOS ledger.
- This is a historical walk-forward; Blind OOS has previous SONAR exposure and is not prospective independent confirmation.

## Registered quantitative hypothesis

Q92: `C(27,10)=8,436,285` equal-weight formulas; 15 shards × 562,419. Target split 2,012/670/670; expected 25,308,855 formula×split rows; global Holm family 75,926,565.

Primary paired Blind OOS endpoint is Q92 minus same-archive Q89 Top-5 hit-share. Decision gate: mean lift ≥0.005 absolute; circular block bootstrap 20,000 replicates, block length 7, 95% lower bound >0; block sign-flip 20,000 replicates and Holm-adjusted p<0.05 across four endpoints. No Q92 historical endpoint has been computed at checkpoint time.

Q89 control remains accepted/persisted on the 3,402-draw archive through 2026-11-08. Candidate `P9_06_09_12_14_15_17_18_19_23`; Blind Top-5 11.7910% vs uniform 12.5000%; no formula/split Holm row below 0.05. No predictive gain.

## Next action

Monitor run 42615347368. Preserve successful immutable shard artifacts; rerun only failed shards. Once all 15 complete, validate artifact SHA/byte receipts, aggregate formula×split compact sufficient statistics, replay discrete-null p-values and global Holm, freeze Discovery→Validation candidate, then perform paired Blind OOS inference against Q89. Require acceptance, append-only persistence, exact byte readback and result-branch CI before human review. No promotion or merge.

## Guardrails and exploratory next hypothesis

Q93 is only a proposal after Q92 acceptance/review: `C(27,11)=13,037,895`; Discovery top-100 → Validation freeze; comparison against Q92 on a new prospective 670-target holdout after 2026-11-08, not Q92 historical Blind OOS. Proposed gate: Top-5 paired lift ≥0.005, bootstrap lower bound >0, Holm-adjusted sign-flip p<0.05 over four endpoints. Not preregistered, implemented or executed.

PR #23 remains draft/open. PR #6/#7/#8 remain open/unmerged and untouched. No auto-merge, engine promotion or shadow insertion.
