# VinciCasa SONAR — cycle 22 (2026-11-13)

## Recovery
- Recovered Q141-A11 checkpoint and verified its report, ledger and source lineage.
- Main branch is newer than PR #90; this cycle is isolated on a new branch from the current main head.
- Canonical archive blob: '6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb'; source matrix SHA-256: '81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047'.
- Existing 2026-11-13 freezes remain pending and unchanged.

## Q141-A12 result
- 11 structural category streams, 51 fixed categories.
- 400-row warmup; 2,956 prior-only targets.
- Discovery 1,774; Validation 591; historical Blind OOS 591.
- Blind full-11 mean log-loss gain: 0.01534343.
- Blind core-9 mean log-loss gain: -0.00264627.
- Blind core-9 mean Brier gain: -0.00098681.
- The apparent full-11 gain is dominated by sum/range first-difference streams.
- Under 2,000 IID uniform 5-of-40 simulations, the difference-feature gains are compatible with the mechanical null after Holm correction.
- Decision: no Markov lift demonstrated in the nine non-differenced structural features.

## Integrity
- Source hash, matrix shape, dates, cutoffs, fixed vocabulary, deterministic replay and future-suffix invariance checked.
- Historical Blind OOS is exploratory, not virgin confirmation.
- No prospective result was read or appended; no active engine or shadow freeze was changed.

## Next action
Review this mechanical-dependence diagnosis. Do not promote the Markov model. If retained, register a separate prospective structural-category forecast only after human review; continue append-only collection for existing prospective gates.
