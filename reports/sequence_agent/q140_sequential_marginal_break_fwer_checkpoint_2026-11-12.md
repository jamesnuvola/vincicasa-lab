# Q140 checkpoint — 2026-11-12

## Source and recovery
- Main commit: 0bf1ef0d39afb671ff83e519489f16b0c24eb15a.
- Archive blob: fcb453ed06c8002314f826dbac79d6935f9ac103; 3,405 data rows.
- Eligible prefix: 3,404 draws through 2026-11-10.
- Contest 315 row (2026-11-11, 1 21 22 27 29) excluded: official archive still lists it as pending.

## Hypothesis and method
- Test per-number marginal change between first and recent 100 draws of a rolling 200-draw window.
- Exact two-sided Fisher conditional hypergeometric p-value per number.
- 3,204 targets x 40 numbers = 128,160 tests.
- Implemented Bonferroni threshold 3.9003433750e-7 (slightly more conservative than 0.05/128160).
- M0 uniform; M1 always-on recent-100 shrinkage alpha=200; M2 adjusts only globally flagged numbers.
- Exact fixed-size subset distribution normalized by e5.

## Measured results
- Targets: 3,204 (1,922 / 641 / 641).
- Targets with alarm: 0.
- Individual number-target flags: 0.
- Decision: NO_SEQUENTIAL_MARGINAL_CHANGE_LIFT_DEMONSTRATED.
- M1 versus uniform: negative log-loss and Brier gain in Discovery, Validation and Blind OOS.
- M2 generated no alarms and therefore equals uniform for all targets.
- Holdout inference: 12 endpoints, 10,000 paired block sign-flips and 10,000 circular block-bootstrap replicates, block length 20, Holm correction.

## Integrity
- Replay recovery: the first CI run detected that the checkpoint's em dash made UTF-8 bytes exceed character count; after recording this recovery, the final manifest was rebuilt from the actual encoded file bytes.
- 32/32 checks passed.
- Future-suffix invariance: 9/9.
- Source hash, strict-prior cutoffs, deterministic replay and exact normalization verified.

## Repository reconciliation at recovery
- Main shadow ledger: 1,321 rows = 1,278 evaluated + 43 pending; pending target 2026-11-12 consists of 42 global configurations (24 family, 12 pair, 6 chain) plus one APP engine row.
- latest_metrics.json: 1,320 total = 1,278 evaluated + 42 pending. The one-row difference is the pending APP row appended by sonar_active_engine_walkforward.mjs after sonar_sequence_agent.py writes latest_metrics.json in the workflow.
- Current positional register is reports/sequence_agent/position_mix_shadow.csv: 26 data rows = 25 evaluated (one excluded pre-protocol row plus 24 paired dates through 2026-11-11) + one 2026-11-12 pending freeze with cutoff 2026-11-11. The separate reports/daily_lab/positional_shadow_forecasts.csv is a legacy file (two rows) and is not the current positional register. Thus the 2026-11-12 inventory is 43 sequence-agent forecasts (42 global + one APP) plus one positional freeze = 44 pending forecasts; all 44 use the disputed 2026-11-11 cutoff.
- Q60 gate lists 24 paired dates through 2026-11-11; 2026-11-11 remains quarantined, leaving 23 source-clean pairs.

## Limits and next action
- Exploratory within Q00-Q139; historical Blind OOS is not virgin.
- No alarms do not prove stationarity; higher-order dependence is outside scope.
- Reconcile contest 315 primary provenance and stale metrics/shadow-ledger mismatch before accepting new prospective pairs.
- No archive, freeze, Q60 gate, or production engine changed. No merge or promotion.
