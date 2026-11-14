# Q141-A21 execution recovery note

Date: 2026-11-14

## Attempt 1 — workflow 43553852703

- Focused Python compilation and unit tests: PASS (6/6).
- Pinned Q7 source extraction: PASS (34 rank-ledger parts and 11 formula-catalog chunks).
- Pinned canonical archive commit: fetched and verified; 3,407 draws through 2026-11-13.
- Original Q7 exhaustive rank engine: emitted BATCH_COMPLETE for 20 targets, archive indices 3387–3406, dates 2026-10-25 through 2026-11-13, 1,023 formula masks and 658,008 candidate quintets.
- The workflow step then exited 1 because its postcondition expected the generated CSV under an extra /parts directory. The Q7 engine actually writes directly to reports/sequence_agent/exhaustive_formula_walkforward/part_3387_3407.csv.

## Root cause and correction

The rank computation itself completed. The failure was a workflow path assertion/consumer mismatch, not a numerical or data-validation failure.

The workflow has been corrected in commit 6d14953f4ee8b4e662619aa70ab45539c0baa348:
- output existence check now uses the actual Q7 engine path;
- both A21 processing and deterministic replay consume that same path;
- cleanup removes that exact generated batch file.

The first runner workspace was ephemeral and no A21 result, ledger, or prospective freeze was persisted from the failed attempt. The corrected workflow will recompute the 20 rank rows from the same pinned inputs.

## Guardrails

No archive, latest_metrics, shadow forecast, Q60 gate, production engine, protected PR #6/#7/#8, or main-branch file was modified. No merge or promotion occurred.

## Recovery state

CORRECTED_PATH_PENDING_WORKFLOW_RERUN. Do not claim A21 metrics, freeze, replay, or readback until the corrected workflow completes those steps.
