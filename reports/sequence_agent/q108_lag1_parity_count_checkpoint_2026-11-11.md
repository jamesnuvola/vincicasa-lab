# Q108 — lag-1 parity-count checkpoint (2026-11-11)

- Status: NO_LAG1_PARITY_INCREMENTAL_LIFT_DEMONSTRATED.
- Protocol preregistered before scoring; alpha=200 fixed; no tuning.
- Source main commit: 161273b72804c2b6e815e41f20b90dabfea4fdfa.
- Analysis prefix: 3,403 draws through 2026-11-09; the 2026-11-10 row in main is excluded because the official archive still lists contest 314 as pending.
- Walk-forward: 3,102 targets; Discovery/Validation/historical Blind OOS = 1,861/620/621.
- Primary comparison: one-step parity-state M1 versus exact Hypergeometric(40,20,5) M0.
- Historical Blind OOS is not virgin; within-Q108 Holm correction covers two preregistered endpoints only.
- Validation: 12/12 PASS.
- No production scorer, canonical data, Q60, H101/H102 or existing freeze was modified.
- Next action: continue append-only prospective evaluation; reconcile contest 314 only after official publication; do not reconstruct missing freezes.
