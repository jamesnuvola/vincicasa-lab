# Q139 checkpoint — weekday-conditioned fixed-size subset model

- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.
- Protocol committed before computation; source pinned to main 0bf1ef0d39afb671ff83e519489f16b0c24eb15a and archive blob fcb453ed06c8002314f826dbac79d6935f9ac103.
- The disputed 2026-11-11 row is excluded; eligible history ends 2026-11-10 with 3,404 draws.
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- M0 uniform; M1 pooled frequency; M2 target-weekday-conditioned number frequency; alpha=200 fixed before computation.
- Exact 5-of-40 subset normalization; each target scored before updating global and weekday counts.
- Validation: 30/30; future-suffix invariance 9/9.
- Holdout inference: 12 endpoints; 10,000 paired block sign-flips and 10,000 circular block-bootstrap replicates per endpoint; Holm correction across all 12.
- Decision: NO_WEEKDAY_INCREMENTAL_LIFT_DEMONSTRATED.
- No archive, freeze, Q60 gate, production engine, or protected PR is modified.

## Results by split

- discovery: M0/M1/M2 joint log-loss = 13.396972368289 / 13.410385095184 / 13.429027502823; gains M2 vs M1 = -0.018642407639 joint and -0.00010310788 Brier.
- validation: M0/M1/M2 joint log-loss = 13.396972368288 / 13.404685502432 / 13.411641022558; gains M2 vs M1 = -0.006955520126 joint and -0.000035642683 Brier.
- blind_oos: M0/M1/M2 joint log-loss = 13.396972368288 / 13.40023974931 / 13.411912660718; gains M2 vs M1 = -0.011672911409 joint and -0.000069869675 Brier.

## Next action

If weekday conditioning fails to improve on the pooled frequency model on historical Blind OOS after Holm correction, retain M0 as reference and M1/M2 as research controls; prioritize source-clean prospective freezes rather than further calendar or lag variants.
