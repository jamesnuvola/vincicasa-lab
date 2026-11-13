# Q114 — second-order active-engine Top20 hit-count regime

- Base main commit: `04fed58ab8a4226da3cd2bc2a495a12095941355`.
- Source Q113 ledger: 3,203 rows, blob `79ad1092d71c4c93aa7365bcd4e8ee48d42df569`, targets 2018-02-03 through 2026-11-10.
- Source Q113 freeze: blob `ea9387df6ad3c1afd31d19e225892bb624d79f13`, target 2026-11-11, cutoff 2026-11-10.
- Evaluated 3,202 targets after excluding the first source row (no second-lag state); splits 1,920 / 641 / 641.
- M2 vs M1 Blind OOS gains: Brier `-0.002170488200`; log-loss `-0.007417608877`.
- One-sided improvement p-values: Brier `0.990740`, log-loss `0.997240`; Holm-adjusted both 1.000000.
- Circular block-bootstrap 95% CIs: Brier `[-0.003753023539, -0.000524817442]`; log-loss `[-0.011931015219, -0.002743333938]`.
- Decision: `NO_SECOND_ORDER_HIT_REGIME_INCREMENTAL_LIFT_DEMONSTRATED`.
- Validation: 17/17; future mutation 9/9; deterministic replay PASS.
- Prospective add-on freeze: 2026-11-11 08:42:54 Europe/Rome; cutoff 2026-11-10; H[t-1]=`2`, H[t-2]=`4`; pair support `150`; first-order PMF matches Q113 exactly (max difference 0).
- Q60 remains 23/200; 177 paired prospective targets remain. No historical freezes reconstructed; no model promotion or merge.
- Next: await official 2026-11-11 outcome; append score only, do not retune; continue Q60.
