# Q111 — lag-1 exact subset recurrence tilt checkpoint (2026-11-11)

- Protocol committed before scoring; source pinned to main commit 161273b72804c2b6e815e41f20b90dabfea4fdfa and archive blob 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Canonical archive: 3404 draws through 2026-11-10.
- Walk-forward: 3103 strict-prior targets; Discovery/Validation/historical Blind OOS = 1861/620/622.
- Validation-selected beta: 0.
- Blind OOS selected-model log gain: 0.000000000000; Brier gain: 0.000000000000.
- Selected-model Holm-adjusted p-values: 1.000000000000, 1.000000000000.
- Decision: NO_LAG1_RECURRENCE_TILT_SELECTED_ON_VALIDATION.
- Validation: 15/15 checks passed; 9/9 future-mutation checks; deterministic replay.
- Limitation: historical Blind OOS is not virgin because this archive has been repeatedly examined.
- No production scorer changes, no promotion, no merge.
- Next: continue append-only prospective freezes; no retrospective tuning on this archive.
