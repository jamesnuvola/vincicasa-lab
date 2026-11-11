# Q119 recovery checkpoint

- Protocol first committed before computation at 2026-11-11T12:16:54Z (commit 16bea54a23ae95a33650660e7ac81475f41137b7); metadata timestamp was corrected before analysis.
- Pinned source: `data/storico_daily.csv`, 3,404 draws through 2026-11-10, Git blob `40f317e2d0067e061c46ab799d66f777a0e087c0`.
- Initial in-memory attempt stopped at the date validator because the orchestration string over-escaped the regular-expression digit token. No experiment outputs were persisted. The harness regex was corrected and the full calculation rerun.
- Full deterministic replay executed twice in the V8 harness; report, validation, freeze, and 3,205-line ledger were byte-identical.
- Walk-forward: 3,204 strict-prior targets; Discovery/Validation/Blind OOS = 1,922/641/641.
- Validation selected alpha=3200 from the fixed grid; alpha selection is based only on the Validation segment. Blind OOS is used only for inference.
- Structural validation: 16/16; future-suffix mutation 9/9.
- Cross-calendar Holm includes four raw endpoints each from Q117 and Q118 plus four Q119 endpoints (12 total).
- Research-only position-marginal freeze for 2026-11-11, cutoff 2026-11-10. It is not a joint five-number forecast and not a Q60 pair.
- Next: after the official 11-Nov draw is published, score the immutable Q117/Q118/Q119 research freezes; do not retune or update Q60 from these probability-only freezes.
- No production changes, no Q60 edits, no merge, no promotion. PRs #6, #7, #8 untouched.
