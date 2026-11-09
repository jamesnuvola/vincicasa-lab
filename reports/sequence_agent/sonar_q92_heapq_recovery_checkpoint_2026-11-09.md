# SONAR recovery checkpoint — Q92 acceptance replay and next field hypothesis

Captured: 2026-11-09 21:43 Europe/Rome

## Verified Q84 baseline and sensitivity evidence

Source reconciliation checkpoint: `checkpoint/sonar-q92-q84-next-20261109T1935Z`.

The original Q84 flow-state atlas is already executed and persisted:
- Canonical archive: 3,402 draws through 2026-11-08; 3,202 eligible targets.
- Chronological splits: Discovery 1,921; Validation 640; Blind OOS 641.
- 129 atlas entries: 42 fixed strategies, 2 ensembles, 84 conditional strategies, 1 retrospective oracle.
- 1,152 strategy × split × endpoint tests; zero Holm-adjusted p-values below 0.05.
- Status: `EXPLORATORY_NOT_PROMOTABLE`.

The separately registered K-neighborhood sensitivity experiment is also persisted and accepted:
- Run 42687283584: success; fail-closed acceptance PASS; exact-byte Git-object readback PASS.
- 16,010 rank vectors reconciled; 3,202 target rows/cutoffs; 36 global Holm tests.
- K selected on Discovery only: K=50.
- Blind OOS mean hits (Top5 / Top10 / Top20):
  - Equal-weight 42: 0.6084 / 1.2449 / 2.5460.
  - Flow K=10: 0.5975 / 1.2543 / 2.5242.
  - Flow K=20: 0.5928 / 1.2496 / 2.5257.
  - Flow K=50: 0.5913 / 1.2621 / 2.5304.
- K=50 minus equal-weight Top20 paired delta: -0.01560 hits/target; 95% block-bootstrap CI [-0.04368, +0.01092]; Holm p=1.0. Top5 delta: -0.01716 hits/target.
- Decision: `NO_DEMONSTRATED_GAIN`. Narrowing K alone did not help. Mean effective analogue counts were 9.75/10, 19.52/20, 48.72/50, indicating little weight concentration.

## Q92 full walk-forward: shards and aggregation completed; acceptance failed

Run: 42683275995. Source head before the acceptance fix: `739f4134a2dc93c756669bf2f206170d773e1a2f`.

Verified:
- Preflight PASS.
- All 15/15 deterministic shards completed successfully.
- All 15 immutable shard artifacts were downloaded, byte/hash checked and reconciled; duplicate/rerun artifacts were identical.
- 8,436,285 formulas; 3,352 scored targets; 25,308,855 formula × split metric rows.
- Discovery / Validation / Blind OOS: 2,012 / 670 / 670.
- Global Holm family: 75,926,565 formula × split × endpoint tests; zero formula/split rows below 0.05.
- Aggregator completed and emitted `NO_SIGNIFICANT_GAIN`.
- Selected candidate: `P10_01_08_11_12_14_15_16_18_19_23`; Q89 control: `P9_06_09_12_14_15_17_18_19_23`.
- Paired Blind OOS Top5 delta Q92−Q89: -0.0062687; 95% block-bootstrap CI [-0.0167164, +0.0041791]; raw sign-flip p=0.2687366; Holm p=0.6197690. Other endpoints did not meet the registered practical-effect/significance gate.
- These are aggregated but NOT acceptance-validated or persisted as accepted results.

Root cause of failed acceptance replay:
- `scripts/validate_sonar_q92_ten_feature.py` called `heapq.heappush` and `heapq.heapreplace` to maintain the Discovery top-100 heap but omitted `import heapq`.
- The exception was `NameError: name 'heapq' is not defined` at `validate_metric_parts`, line 149.
- The failure occurred after all shards and global aggregation succeeded; it was not a walk-forward, leakage, artifact-integrity or statistical failure.

## Corrective change persisted and read back

On branch `research/sonar-q92-exact-null-calibration-20261109`:
- Validator fix commit: `7c9e2e222616656b72976df3793dffc6bdf2c7a5`.
- Regression-test commit / current head at checkpoint: `5ba980df7e1a843b452ea89eacc1f181fc9a74bb`.
- Added the missing `heapq` import.
- Added a regression test that checks the import and both heap operations.
- Re-fetched both files from GitHub and verified exact blob SHAs:
  - Validator: `42155b01edbef20470a08e5e77e53f1fdf8d5275`.
  - Test: `5186effb6c619495344187561fd5bde6a285b8fd`.
- PR #23 remains open/draft; no merge or model promotion.

Because the validator and regression test are included in Q92's source-code hash manifest, the old shard artifacts are intentionally not reused for an acceptance claim on the changed source head. The full workflow's path filter includes both changed files and should rerun all 15 shards on the new exact commit. Current-head CI and the rerun acceptance result are still pending at checkpoint time.

## New quantitative hypothesis for the next dynamic-field experiment

H1 — the 13-dimensional aggregate state loses identity-preserving cross-number structure. The K sensitivity suggests that changing analogue neighborhood size does not resolve the diffuse state representation. A new experiment should preserve the 40 number identities as a field rather than compressing them into a small set of draw-level aggregates.

Proposed state at each target: a 40 × 6 number-state matrix, computed strictly from the prefix before that target:
1. short-window occurrence residual (5 draws);
2. medium-window occurrence residual (20 draws);
3. long-window occurrence residual (80 draws);
4. current gap-age standardized against that number's prior inter-arrival history;
5. gap-age velocity / recent change;
6. co-occurrence residual / local-neighborhood signal.

The field's change should be measured with robustly scaled per-number velocity and acceleration; compare a frozen, small registered set of distances/kernels, not an unbounded search. Historical analogue outcomes are the next draw after each past state, never the state target itself. All 40 numbers must receive a rank for every eligible target.

Protocol:
- Register formulas, windows, scaling, distance kernels, age decay and tie-breaks before scoring.
- Fit scaling and select variants on Discovery only; freeze one candidate on Validation.
- Report Discovery, Validation and historical Blind OOS against uniform and existing Q84 comparators, with paired block-bootstrap intervals, block sign-flip tests and Holm correction across the complete registered family.
- The existing historical Blind OOS has already been inspected by earlier SONAR experiments; label it exploratory rather than a pristine independent confirmation. Do not tune on it. Keep the prospective shadow gate separate and append-only; no reconstruction of missing freezes.
- Minimum practical Top5 effect remains +0.005 absolute hit share, with a positive lower 95% paired block-bootstrap bound and Holm-adjusted p<0.05 as the registered promotion criterion.
- Do not reuse the superseded, unexecuted 240-dimensional draft as if it were the Q84 protocol. This is a new hypothesis requiring its own implementation, tests, manifest, and acceptance report.

## Next action

1. Allow the exact-head Q92 workflow to rerun all 15 shards after the heapq fix.
2. Require aggregate replay, fail-closed acceptance, output bundle byte readback, append-only result-branch persistence, result-branch Git blob readback, and exact-head CI before calling Q92 accepted.
3. In parallel, implement and test the new identity-preserving 40 × 6 field experiment on a separate research branch; do not promote it or merge automatically.
4. Preserve PR #6, #7 and #8 unchanged and unmerged.
