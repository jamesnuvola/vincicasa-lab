# Q122 checkpoint — score-margin hit-count calibration

- Preregistration committed before calculation: 030271b054d347bdbe49515ef1a3b67cc4f1dec3.
- Canonical archive: 3,404 draws through 2026-11-10; blob 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Exact APP scorer and APP data hashes pinned; APP data reconciles row-by-row.
- 200 prior-only calibration forecasts (target indices 200–399) set q33/q67; outcomes do not enter threshold selection.
- 3,004 scored targets; Discovery/Validation/Blind OOS = 1,802/601/601.
- q33=0.024527431706, q67=0.068544672898.
- Decision: NO_BOUNDARY_MARGIN_INCREMENTAL_HIT_COUNT_LIFT_DEMONSTRATED.
- Q60 unchanged at 23/200; no historical freeze reconstructed.
- PRs #6, #7, #8 untouched; no merge or production promotion.

## Blind OOS

| Model | Brier | Log-loss |
|---|---:|---:|
| M0 exact uniform | 0.73951262639 | 1.481771512205 |
| M1 unconditional | 0.740137130688 | 1.483008241957 |
| M2 margin-state | 0.740855886796 | 1.485229983574 |

## Next action

Verify contest 315 after official publication; score Q122 freeze without retuning and continue Q60 append-only collection.
