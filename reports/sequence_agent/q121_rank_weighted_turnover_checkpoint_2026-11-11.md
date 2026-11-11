# Q121 checkpoint — rank-weighted forecast turnover

- Protocol committed before calculation; protocol commit: 14abdc13e3b3958a15ee7d093db6948e20a217df (2026-11-11T13:49:00Z).
- Source main commit 04fed58ab8a4226da3cd2bc2a495a12095941355; archive blob 40f317e2d0067e061c46ab799d66f777a0e087c0; 3404 draws through 2026-11-10.
- Exact APP scorer blob 7ccb9a2abfe452ec535913b70225bc109f692304; app data blob 25c0b2316662664deff9e2157e60ec56cfa3a640; APP data row-by-row matches canonical archive: true.
- Walk-forward: 3203 strict-prior targets; Discovery / Validation / historical Blind OOS = 1922 / 641 / 640.
- M2 adds fixed rank-displacement bins conditional on the Q117 overlap state; shrinkage 200; no tuning.
- Recovery: first replay failed on an out-of-scope normalization variable; second replay failed because the manifest read generated outputs before write. Both root causes were corrected in runner commits becc75e17baf3690d9ecf4304942d1c44655b5d2 and 71b2a8e537e27c371255b10022267696a4dde2f3; final replay status is recorded by CI.
- Blind OOS M2 vs M1 Brier gain -0.00003229626311062189; log-loss gain -0.00019060258266446925.
- Blind OOS M2 vs M0 Brier gain 0.00029975463704955097; log-loss gain 0.0006891334975616837.
- Holm family size 4; 19/19 checks; future-suffix invariance 9/9; deterministic replay true.
- Separate Q121-only 2026-11-11 hit-count freeze; not a Q60 pair.
- Limitations: historical Blind OOS is not virgin; Q121 Holm does not cover Q00-Q121; rank displacement is a calibration diagnostic, not a lottery prediction.
- Next action: evaluate only after official contest 315 publication; no retuning; continue Q60 append-only.
