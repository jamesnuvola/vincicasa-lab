# VinciCasa SONAR hourly checkpoint — 2026-11-09 11:49 UTC

## State recovered

- Q89 refresh report: `Q89_REFRESH_2026_11_08`, status `VALIDATED_PENDING_HUMAN_REVIEW`.
- Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08; SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`; Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Q89 catalog: 4,686,825 nine-feature formulas, 15 shards, 14,060,475 formula×split metric rows, 3,352 scored targets with Discovery/Validation/Blind = 2,012/670/670.
- Global Holm family: 42,181,425 tests; 0 formula/split rows below adjusted 0.05. Q89 formula-family p-values still use the report-declared continuity-corrected normal approximation and are exploratory.
- Frozen Q89 candidate: `P9_06_09_12_14_15_17_18_19_23`.
- Q89 Blind OOS descriptive metrics: Top-5 0.11791044776119403; Top-10 0.23582089552238805; Top-20 0.4955223880597015; mean actual-number rank 20.61402985074627. Uniform baselines: 0.125/0.25/0.5/20.5. This is not evidence of a predictive gain.

## New quantitative stability / reproducibility audit (exploratory, post-hoc)

Compared persisted Q89 candidate-selection files at archive cutoffs 2026-11-07 and 2026-11-08:

- Discovery Top-100 membership intersection: 100/100; Jaccard = 1.000.
- Top-k membership intersections: k=5: 5/5; k=10: 10/10; k=20: 20/20; k=50: 50/50; k=100: 100/100.
- Order: 4,932 concordant / 18 discordant pairs among 4,950; Kendall tau = 0.9927272727272727.
- Mean absolute rank shift = 0.36 positions; maximum = 12 positions; 80/100 formulas remained at the exact same ordinal position.
- The Validation-selected Q89 candidate ID is identical at both cutoffs: `P9_06_09_12_14_15_17_18_19_23`.
- Discovery mean Top-5 share changed 0.1375435106911984 → 0.1374751491053678 (−0.0000683615858306); Validation mean Top-5 share changed 0.12985074626865672 → 0.13014925373134328 (+0.00029850746268656).

Strict-prior ledger replay across the two persisted candidate Blind ledgers:
- Old/new ledger sizes: 670/670; shared target dates: 669 (2025-01-08 through 2026-11-07).
- The old-only target is 2025-01-07; the new-only target is 2026-11-08, consistent with a one-target rolling Blind window.
- On all 669 shared dates, zero mismatches across cutoff_date, prior_draws, actual_quintet, Q89_formula_id, Q89 actual-number rank vector, Top-5/10/20 hit counts and rank_sum.
- This verifies exact replay invariance for the shared Q89 targets under one later archive append. It is a retrospective stability/leakage diagnostic, not predictive evidence and not a preregistered confirmatory test.

### Prospective hypothesis to preregister before the next archive refresh

`Q89-ROLLING-BLIND-STABILITY-02`: when one additional official draw is appended and the Discovery/Validation/Blind boundaries roll by one target, expect (a) Discovery Top-100 Jaccard ≥0.90, (b) Kendall tau ≥0.95 among shared Top-100 members, (c) the selected Q89 formula ID unchanged, and (d) exact strict-prior rank/metric replay on every common target date. Failure of any gate is a stability alert; it does not authorize model promotion. This threshold was formulated after the current audit and must be registered before the next refresh to be confirmatory.

## Q92 preregistration and execution state

- Q92 universe: C(27,10) = 8,436,285 formulas; 15 shards of 562,419; 3,352 targets; split 2,012/670/670; expected 25,308,855 formula×split rows and Holm family 75,926,565.
- Discrete-null calibration amendment replaces the normal tail with deterministic float64 convolution of iid Hypergeometric(40,k,5) counts.
- Paired Blind OOS primary gate versus same-archive Q89: Top-5 delta ≥0.005 absolute, circular block-bootstrap 95% lower bound >0, Holm-adjusted block sign-flip p<0.05 over four endpoints. This is a gate, not an expected gain.
- No historical Q92 shard, aggregate, Discovery/Validation freeze, or Blind OOS result has been produced in this checkpoint.

## Independent exact-uniform sanity check on Q89 Blind OOS (exploratory)

Recomputed the Q89 selected candidate's aggregate number-hit counts from the persisted shares: Top-5 = 395, Top-10 = 790, Top-20 = 1,660 out of 3,350 actual-number observations across 670 draws. For each fixed k-number ranking set, the per-draw hit count follows Hypergeometric(N=40, K=k, draw_size=5); the 670-draw null distribution was built by repeated float64 discrete convolution (mass sums to 1 within 3e-14).

| Endpoint | Observed share | Null expected count | Exact one-sided p for positive lift P(X≥observed) | Exact lower-tail p P(X≤observed) |
|---|---:|---:|---:|---:|
| Top-5 | 0.11791045 | 418.75 | 0.91016729 | 0.09925220 |
| Top-10 | 0.23582090 | 837.50 | 0.97885139 | 0.02340716 |
| Top-20 | 0.49552239 | 1,675.00 | 0.71409148 | 0.29843703 |

Holm over the three fixed endpoints gives adjusted positive-lift p-values = 1.000 for all three. The lower-tail Top-10 raw p=0.02340716 becomes Holm-adjusted 0.07022147; no endpoint is significant at 0.05 after this three-endpoint correction. This is an independent discrete-null sanity check only; it does not correct for the wider historical SONAR experiment-selection exposure, so it is not confirmatory and does not authorize promotion.

## Root cause and CI recovery

- Exact-head CI run `42606749640` for source commit `00502224b7b7c2cf64cff1bb1b51f3514d3874ef` was cancelled when the PR branch advanced. Its log had been inside the full legacy Q80/Q81/Q82/Q83/Q86 regeneration step: Q80 summary at 11:24:39Z, metrics CSV ended at 11:24:40Z, and the Q80 target-ledger export had only emitted its header before cancellation. This was an infrastructure/runtime gate, not a Q92 statistical failure.
- Root cause: the common CI workflow did not scope the expensive legacy catalog regeneration, persisted-output validation and artifact upload away from the Q92 exact-null branch.
- Added branch exclusions for `research/sonar-q92-exact-null-calibration-20261109` to those three CI conditions. CI workflow readback blob SHA: `f34e89e403af650c863daa75547060ac2d5a3178`; edit commit: `82be9386c6920ad4bd5a24e7e0c81d8706081dc6`.
- Added `.github/workflows/ci.yml` to Q92 `SOURCE_CODE_HASH_PATHS` so the exact-head gate is part of the reproducibility digest. Readback blob SHA: `e8fdd03523b0bdd1e4e791bf7aa6dd5839491801`; commit: `b7b3060d236423a99c8d0dac4bbe729b998c6b84`.
- Added `.github/workflows/ci.yml` to the Q92 full-walk-forward push path trigger. Readback blob SHA: `3e1bc7f2d999216283de380e60fed02f97c8c051`; latest PR #23 head: `7a5d195cbdb0de818082093881725a15fa1fffe6`.
- Current exact-head project CI: run [42611974913](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42611974913), IN PROGRESS.
- Current Q92 artifact-backed full walk-forward: run [42611968234](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42611968234), IN PROGRESS at “Wait for full project CI on this exact source commit”. No Q92 shard jobs are observed yet.
- Older full-walk-forward run [42606741630](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42606741630) ended FAILURE after its exact-head CI was cancelled; no shard execution.
- Adjacent branch CI [42607100534](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42607100534) completed SUCCESS, but it is on commit `a76e0ff04c0b23c0bde7cc143a45961cbc9c0834`, not the current PR #23 exact head.

## Q92 exact-head preflight poller recovery — 2026-11-09 11:55 UTC

### Second root cause (verified)

The Q92 preflight run [42611968234](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42611968234) failed after the general exact-SHA query selected the newest CI run by `workflow_id + head_sha` only. It selected run [42612163220](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42612163220), which was a cancelled `push` event on checkpoint branch `research/sonar-hourly-checkpoint-20261109-1149`, despite having the same source SHA `7a5d195cbdb0de818082093881725a15fa1fffe6`. The relevant CI run for PR #23 was [42611974913](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42611974913), event `pull_request`, exact Q92 branch, same SHA, and it completed SUCCESS. The polling selector did not filter `head_branch` or event and treated the unrelated cancelled run as a gate failure.

### Implemented correction and regression evidence

- Added `scripts/sonar_q92_ci_gate.py`: filters workflow ID, exact source SHA and exact expected branch; prefers PR-event runs when available; selects active runs before completed runs and sorts by created time/run attempt/ID.
- Added `tests/test_sonar_q92_ci_gate.py` with six synthetic cases: unrelated checkpoint push ignored; active PR run preferred over a cancelled PR run; latest completed attempt selection; push fallback; SHA/workflow/branch mismatch filtering; empty-state formatting.
- Local isolated Python regression: **6/6 tests PASS**.
- On latest PR #23 head `0003de0ab7f469a8523fa5370828f6d1d4fe43aa`, exact-head CI run [42612676089](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612676089) is IN PROGRESS; the dedicated `Test Q92 exact-head CI run selector` step is already SUCCESS.
- Latest artifact-backed Q92 run [42612668612](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612668612) is IN PROGRESS at exact-head CI wait. **No Q92 shard jobs have started.**
- Earlier Q92 run [42612641888](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612641888) on superseded commit `f90251affd55962f796477d32ebf42059b1cfa38` ended FAILURE because its exact-head CI was cancelled when PR #23 advanced; no shard execution.
- Synthetic Q92 runner acceptance [42612641910](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612641910) and global Holm/paired inference acceptance [42612641787](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612641787) completed SUCCESS on that superseded head. The latest preflight will replay the synthetic regressions on the current exact head.

Readback identities on PR #23 head `0003de0ab7f469a8523fa5370828f6d1d4fe43aa`:
- CI workflow blob: `83e868bbb44e2046bd8e542fb6a2eca031048efc`.
- Q92 common source-hash manifest blob: `647025282b57938ca66549757ef512e2bfd3dfb5`.
- Q92 full-walkforward workflow blob: `dcf28fe7c50411e97a1628cd2f20a152bdf9751b`.
- CI gate helper blob: `73e88f5a77049f5371fb83e1f2f9cbce8068a10e`.
- CI gate regression test blob: `6f1ebf57309a7c8f727452a87924124e8446c8f0`.

## Updated immediate next action

1. Wait for exact-head full project CI [42612676089](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612676089) to complete SUCCESS.
2. Confirm Q92 preflight [42612668612](https://github.com/jamesnuvola/vincasa-lab/actions/runs/42612668612) passes its exact branch/sha gate and replays all synthetic regressions.
3. Only after that, start the 15 immutable Q92 shards. Preserve shard checkpoints and do not proceed to global aggregation unless every shard artifact reconciles.
4. Apply discrete-null p-value replay and global Holm, freeze Discovery→Validation, then paired Blind OOS against same-archive Q89. Persistence, digest/byte readback, exact-head CI and human review remain mandatory.

## Next action

1. Confirm exact-head CI `42611974913` completes SUCCESS with the legacy Q80-Q86 regeneration scoped out and all other project checks intact.
2. Allow Q92 preflight `42611968234` to compile, run strict-prior/selective-rank/compact-output/discrete-null synthetic regressions, and reconcile archive/Q89 freeze/amendments.
3. Only after preflight success, run the 15 immutable shards; recover from persisted shard checkpoints on any failure.
4. Aggregate 25,308,855 rows; replay discrete p-values and global Holm; freeze Discovery→Validation candidate; then evaluate paired Blind OOS versus same-archive Q89.
5. Acceptance, append-only persistence, digest verification, byte-readback, exact-head CI and human review remain mandatory.

PR #23 remains draft/open/unmerged. PR #6, #7 and #8 remain open/unmerged and untouched. No automatic merge, promotion or shadow insertion.
