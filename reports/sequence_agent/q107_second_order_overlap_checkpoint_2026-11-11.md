# Q107 — second-order overlap memory checkpoint (2026-11-11)

- Status: NO_SECOND_ORDER_INCREMENTAL_LIFT_DEMONSTRATED.
- Preregistered before scoring; fixed alpha=200; no parameter selection.
- Source main commit: 161273b72804c2b6e815e41f20b90dabfea4fdfa.
- Analysis uses exactly 3,403 draws through 2026-11-09; the extra 2026-11-10 row present on main is explicitly excluded because the official archive/bulletin still show contest 314 pending.
- Walk-forward: 3,100 targets; Discovery/Validation/historical Blind OOS = 1,860/620/620.
- Primary comparison: second-order M2 versus first-order M1; secondary comparison M2 versus exact Hypergeometric(40,5,5) null.
- Blind OOS selected no parameters; four preregistered endpoints corrected with Holm.
- Validation: 12/12 PASS.
- Historical Blind OOS is not virgin because Q102 previously examined lag-1 overlap memory on the same archive.
- No engine, freeze, Q60, H101 or H102 record changed.
- Next action: wait for official publication of contest 314; append-only reconcile the existing pending freezes; continue Q60 without reconstructing missing freezes.
