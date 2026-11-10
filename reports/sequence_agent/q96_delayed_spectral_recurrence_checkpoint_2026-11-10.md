# SONAR Q96 delayed spectral recurrence — checkpoint

- Task: Q96-DELAYED-SPECTRAL-RECURRENCE-01
- State: ACCEPTANCE_PASS
- Archive: 3403 draws, 2017-07-17 through 2026-11-09
- Strict-prior targets: 3203; splits: {'discovery': 1921, 'validation': 641, 'blind_oos': 641}
- Fixed lags: [2, 3, 5]; requested modes: 2
- Constrained node-label permutations: 999; seed: 9601
- Global Holm family: 9 lag-by-split tests
- Diagnostic gate: NOT_SUPPORTED

## Interpretation boundary

This is a geometric recurrence diagnostic, not a forecasting model. The target quintet is not read. Historical Blind OOS is exploratory. No promotion or freeze changes are permitted.

## Next action

Run independent exact replay, append-only persist all outputs, verify Git readback and replay the persisted head read-only. If no lag passes Validation and historical Blind OOS after global Holm correction, close the spectral recurrence line and prioritize Q92 acceptance plus Q60 prospective collection.

## Independent acceptance

- Validator status: PASS.
- Strict-prior cutoffs: 3203/3203.
- Permutation overlaps replayed: 9599391.
- Global Holm tests replayed: 9.
- Diagnostic gate: NOT_SUPPORTED.
