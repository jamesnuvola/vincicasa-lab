# Q138 checkpoint — number-identity-specific lag-1 heterogeneity

- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.
- Protocol was committed before Q138 computation (branch research/q138-number-identity-lag1-heterogeneity-20261112; protocol commit 7a15f1a15304860baf1b383dc78f04a750de2fcd).
- Source: pinned main archive blob fcb453ed06c8002314f826dbac79d6935f9ac103; 3,405 rows include the disputed 2026-11-11 row, which is excluded; eligible prefix is 3,404 draws through 2026-11-10.
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- M0 uniform exact 5-of-40; M1 pooled lag-1 recurrence tilt; M2 identity-specific lag-1 effects shrunk toward pooled conditional rates; fixed alpha=200.
- Blind OOS point gains for M2 vs M1: joint log-loss +0.001759644 and marginal Brier +0.000008525 per target. Both are small and uncertain.
- All six Holm-adjusted p-values are 1.000; all six 95% block-bootstrap intervals include zero. Discovery and Validation do not support M2.
- Validation: 29/29; future-suffix invariance 9/9; deterministic replay matched.
- No archive, freeze, Q60 gate, production engine, or protected PR is modified.

## Interpretation

Q138 tests per-number lag-1 heterogeneity beyond a pooled lag-1 recurrence tilt. It is related to Q111 and Q112, and remains inside a large exploratory research family. The historical Blind OOS is not virgin. No predictive lift is demonstrated.

## Next action

Keep M0 as reference; retain M1/M2 as research controls only. Resolve primary provenance for contest 315 and continue clean prospective collection before testing further related lag structures.
