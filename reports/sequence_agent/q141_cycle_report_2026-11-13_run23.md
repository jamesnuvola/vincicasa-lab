# VinciCasa SONAR — cycle 23 (2026-11-13)

## Recovery
- Recovered Q141-A12 checkpoint: REMOTE_GIT_READBACK_VERIFIED.
- A12 source branch head was isolated; the canonical main archive blob remains 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.
- Source matrix SHA-256: 81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047; shape 3,356 × 40 × 59.
- A7 source artifact 14003350043 remains available and unexpired.
- B11 remains one frozen prediction and zero reconciled outcomes at the 11:05 local check; the official archive still ends at contest 316 / 2026-11-12.

## Q141-A13 hypothesis and design
- Test lag-2 transition from sum/range first-difference category at t-2 to category at t.
- To eliminate shared-draw overlap, train only on prior endpoints in the same modulo-4 phase as target t.
- Each training example consumes raw draw rows [s-3,s]; examples are spaced by four; latest s ≤ t-4; target uses [t-3,t].
- Baseline marginal category frequency uses the identical phase-matched sample.
- Fixed alpha 0.5 / transition shrinkage 20; no parameter search.
- 2,956 targets; Discovery 1,774, Validation 591, historical Blind OOS 591.
- Confirmatory endpoints: pooled two-feature log-loss and Brier gain; Holm across two. Feature-specific metrics are exploratory with separate Holm across four.

## Results
- Blind pooled log-loss gain: -0.00335589.
- Blind pooled Brier gain: -0.00120642.
- IID 5-of-40 null simulation: 2000 replicates; results and adjusted p-values are in the machine-readable report.
- Practical thresholds: +0.005 nats and +0.001 Brier gain.
- Decision is recorded in the JSON report; no engine or forecast is promoted.

## Integrity and limits
- Source hashes, fixed A12 feature-builder blob, dates, strict-prior cutoffs, phase matching, non-overlapping training/target windows, future-suffix invariance and deterministic replay are checked.
- Historical Blind OOS is exploratory, not virgin confirmation.
- This is a structural-category diagnostic, not a number/ticket predictor.
- B11 freeze and canonical archive remain unchanged.

## Next action
Review A13 and its IID mechanical control. If any effect appears, require a new prospective preregistration and human review; do not reuse historical Blind OOS as confirmation.
