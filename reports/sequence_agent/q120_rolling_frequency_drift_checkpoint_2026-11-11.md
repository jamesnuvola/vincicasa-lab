# Q120 checkpoint — rolling-window frequency drift

- Protocol committed before computation: e25af7d278d8efd825a708e199e417335196c4f0.
- Source main commit 04fed58ab8a4226da3cd2bc2a495a12095941355; archive blob 40f317e2d0067e061c46ab799d66f777a0e087c0; 3,404 draws through 2026-11-10.
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- Validation selected window: 2000 draws; fixed alpha 200.
- Blind OOS gains vs M0: log-loss -0.004372655740; marginal Brier -0.000024461902.
- Blind OOS gains vs M1: log-loss -0.001839870882; marginal Brier -0.000009501615.
- Twelve registered one-sided tests received Holm correction; no incremental lift demonstrated.
- Exact enumeration: 658008 subsets, mass 1.00000000000006; future-suffix mutation 9/9.
- Q120 research-only Top20 freeze for 2026-11-11, cutoff 2026-11-10; FROZEN_PENDING, not a Q60 pair.
- Deterministic replay is scheduled for the dedicated Node 20 runner.
- Limitations: historical Blind OOS is not virgin; Holm covers Q120 only; no production changes or promotion.
- Next action: evaluate only after official contest 315 publication; do not retune.
