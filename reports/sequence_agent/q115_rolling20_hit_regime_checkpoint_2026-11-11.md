# Q115 — rolling-20 active-engine Top20 hit-count regime

- Protocol committed before calculation at 2026-11-11T08:42:55Z.
- Source Q113 ledger: 3,203 rows; target range 2018-02-03 through 2026-11-10.
- Evaluated 3,183 targets after 20-target warm-up; chronological splits 1,901/641/641.
- State: LOW if trailing-20 hit sum <=45; MID 46..54; HIGH >=55. Shrinkage alpha=200.
- Blind gains M20 vs M0: Brier -0.001547726095; log-loss -0.003654164475.
- Blind gains M20 vs M1: Brier -0.000033334271; log-loss +0.000700616791.
- Decision: NO_ROLLING20_INCREMENTAL_LIFT_DEMONSTRATED.
- Inference: 50,000 block sign-flips; 10,000 circular block-bootstrap replicates; block length 20; Holm family size 4.
- Validation: 19/19 analytical checks; future mutation 9/9; deterministic replay in the analysis runtime.
- Recovery: first Node 20 replay exposed a one-unit difference at the 12th decimal in a log-loss CSV cell. Canonicalized numeric ledger serialization to 10 decimals and relaxed cross-runtime metric equality to 1e-10; the dedicated Node 20 replay must pass before this cycle is considered fully validated.
- Prospective add-on freeze: 2026-11-11 09:42:55 Europe/Rome; cutoff 2026-11-10; trailing-20 sum 55, state HIGH, support 493; active Top20 copied unchanged from Q113.
- Q60 remains 23/200; 177 paired targets remain. No missing historical freezes reconstructed; no model promotion or merge.
- Next: await official 2026-11-11 result; score the freeze without retuning.
