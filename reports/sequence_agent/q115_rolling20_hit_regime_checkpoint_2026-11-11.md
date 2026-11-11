# Q115 — rolling-20 active-engine Top20 hit-count regime

- Protocol committed before calculation at 2026-11-11T08:42:55Z.
- Base main commit: `04fed58ab8a4226da3cd2bc2a495a12095941355`.
- Source Q113 ledger: 3,203 rows, blob `79ad1092d71c4c93aa7365bcd4e8ee48d42df569`, targets 2018-02-03 through 2026-11-10.
- Evaluated 3,183 targets after 20-target warm-up; chronological splits 1,901/641/641.
- State: LOW if trailing-20 hit sum <=45; MID 46..54; HIGH >=55. Shrinkage alpha=200.
- Blind gains M20 vs M0: Brier -0.001547726095; log-loss -0.003654164475.
- Blind gains M20 vs M1: Brier -0.000033334271; log-loss +0.000700616791.
- Decision: `NO_ROLLING20_INCREMENTAL_LIFT_DEMONSTRATED`.
- Inference: 50,000 block sign-flips; 10,000 circular block-bootstrap replicates; block length 20; Holm family size 4.
- Analytical validation: 19/19; future mutation 9/9; deterministic replay PASS.
- Recovery: initial Node 20 replay exposed a one-unit difference at the 12th decimal in one log-loss cell. Ledger numeric serialization was canonicalized to 10 decimals; no formula or metric changed.
- Final dedicated Node 20 replay: run 42991167922, SUCCESS on Node 20.20.2. Syntax and ledger/inference/manifest replay passed.
- General repository CI: latest run 42991285883 was still in progress at the last check; do not claim it passed.
- Prospective add-on freeze: 2026-11-11 09:42:55 Europe/Rome, cutoff 2026-11-10; trailing-20 sum 55, state HIGH, support 493; active Top20 copied unchanged from Q113.
- Q60 remains 23/200; 177 paired targets remain. No missing historical freezes reconstructed; no model promotion or merge.
- Next: await official 2026-11-11 result; score the freeze without retuning.
