# Q141-D1 — independent metric recomputation (Python CI pending)

**Date:** 2026-11-13  
**Status:** Historical analysis computed from the pinned Q141-C0 ledger; repository Python replay and output persistence are still pending. This note is not a CI pass or prospective confirmation.

## Source and design

- Target ledger Git blob: `4620ac88199256d90bf8e11a852206bfeb817812`
- Archive Git blob: `fcb453ed06c8002314f826dbac79d6935f9ac103`
- Eligible archive: 3,404 draws through 2026-11-10; the D1 target ledger contains 3,354 scored targets.
- Chronological split: Discovery 2,013; Validation 671; historical Blind OOS 670.
- Six Q80-derived families; rolling window 100; fixed scale floor lambda=0.25.
- D1 target score: (z_{f,s}=(h_{f,s}-\bar h_s)/\sqrt{v_s+0.25^2}), averaged over the preceding 100 targets. Tie-break: lower prior mean actual-number rank, then family ID.
- M0: equal-family ranking. M1: Q141-C0 raw rolling-100 family selector. M2: D1 standardized relative-advantage selector.
- Uniform Top-5 reference: 0.625 mean hits per target.

## Measured metrics

Mean Top-5 hits per target (Top-5 hit share in parentheses):

| Split | D1 M2 | C0 M1 raw rolling-100 | Equal-family M0 |
|---|---:|---:|---:|
| Discovery (2,013) | 0.627422 (12.5484%) | 0.649776 (12.9955%) | 0.634873 (12.6975%) |
| Validation (671) | 0.614009 (12.2802%) | 0.612519 (12.2504%) | 0.579732 (11.5946%) |
| Blind OOS (670) | 0.619403 (12.3881%) | 0.626866 (12.5373%) | 0.600000 (12.0000%) |

Blind OOS additional diagnostics:

| Metric | D1 M2 | C0 M1 | Equal M0 |
|---|---:|---:|---:|
| Top-10 mean hits | 1.249254 | 1.270149 | 1.213433 |
| Top-20 mean hits | 2.555224 | 2.588060 | 2.520896 |
| Mean actual-number rank (lower is better) | 20.320299 | 20.190448 | 20.511642 |

## Blind OOS paired inference

Two preregistered co-primary endpoints; positive values favour D1. Inference uses 20,000 circular moving-block bootstrap replicates and 20,000 one-sided block sign-flip replicates, block length 20. Holm family size = 2.

| Endpoint | Mean gain (hits/target) | 95% block-bootstrap CI | Raw p | Holm p |
|---|---:|---:|---:|---:|
| D1 minus C0 raw selector | -0.007463 | [-0.031343, +0.014925] | 0.755712 | 0.755712 |
| D1 minus equal-family | +0.019403 | [-0.041791, +0.080597] | 0.268137 | 0.536273 |

Practical threshold: +0.025 mean Top-5 hits per target (+0.5 percentage points of Top-5 hit share). Neither endpoint meets the threshold, neither confidence interval excludes zero, and neither Holm-adjusted p-value is below 0.05.

**Decision:** `NO_STANDARDIZED_FAMILY_ADVANTAGE_LIFT_DEMONSTRATED`. D1 is below C0 in Blind OOS and only descriptively above equal-family; no predictive advantage is established.

## Integrity observations from this independent recomputation

- 3,354 source rows and split counts match the preregistration.
- Target indices are consecutive; every stored cutoff date is strictly before its target date.
- Deterministic replay reproduced the D1 selector.
- Six future-suffix mutation checks (offsets 100, 101, 500, 2,013, 2,684, 3,353) left the corresponding current selector unchanged.
- This note was computed from the pinned ledger in an independent JavaScript pass. The repository Python script and unit tests have been committed but have **not yet completed CI**.

## Root cause / limitations

- D1 is still a meta-selector over six coarse Q80-derived families, not the full typed Q141 formula universe and not an exact-quintet probability model.
- Historical Blind OOS has already been exposed to previous SONAR research; it is exploratory, not virgin evidence.
- The per-target standardization may amplify noisy cross-family dispersion despite the fixed scale floor.
- Holm covers only the two registered D1 endpoints, not the entire Q00-Q141 research history.
- The parent Q141-C0 report's Git blob changed during the existing Q141 CI persistence commit, while the pinned archive and target-ledger blobs remained unchanged. The D1 script was corrected to validate the parent report's source lineage dynamically rather than pinning a volatile report blob.
- A synthetic test fixture was also corrected to include the warm-up and family Top-10/Top-20 fields required by the full prediction path.

## Next action

Wait for the corrected Q141-D1 CI run, require the Python replay to reproduce these metrics, then verify remote Git readback of report, ledger, manifest and checkpoint. Do not tune lambda/window on this historical Blind OOS. Next substantive research task: complete Q90/Q7 typed-AST lineage and reconcile their different archive snapshots before a common-source formula behaviour atlas. Preserve Q141-A7 B11 and main Q60 prospective freezes append-only.
