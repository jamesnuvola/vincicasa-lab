# SONAR PSR-07 — CI root-cause checkpoint (2026-11-08)

## Failed run

- GitHub Actions run: 42482070222
- Commit: 39af9bf2228b39d2f30594eb849c4b16221564b8
- Workflow: SONAR PSR-07 Prior Median State Lab
- Failure stage: unit/synthetic tests; canonical walk-forward did not execute and no historical metrics were produced.

## Root cause

The exact integer-count quartile routine returned P3 cutpoints **[15, 20, 26]**, while the protocol/code/test had expected **[15, 21, 26]**.

The discrepancy came from a prior exploratory floating-point cumulative calculation: the theoretical P3 CDF is exactly 0.5 at value 20, because the distribution is symmetric around 20.5. With the registered quantile convention (smallest integer m such that CDF(m) >= q), the median cutpoint is 20, not 21. The CI's exact combinatorial count correctly exposed the earlier rounding error.

## Verified correction

- Exact cutpoints: [15, 20, 26].
- States: P3<=15; 16..20; 21..26; P3>=27.
- Exact prior masses: 26.386913%, 23.613087%, 27.761972%, 22.238028% (rounded).
- Updated protocol, state labels, exact-count mass ranges, and boundary tests.
- Added tests for the lower-median convention at P3=20 and the next state at P3=21.

This is a mathematical definition correction, not an observed predictive result. The failed run produced no walk-forward metrics. Retry the pinned archive run and then verify generated report/ledger persistence and byte reproducibility.


## Second replay mismatch — numeric serialization root cause

- Replay runs: push run 42482327342 and pull-request run 42482331231, both on commit a69439bf936a5d6c875d3eaf8af8fe2b146726e3.
- The walk-forward and unit tests completed successfully, but the persisted-output comparison failed. The validation aggregate JSON contained last-bit differences around 1e-18; the target ledger SHA-256 changed from 9f9fef21824b1332e5d4c8a381573a0f0d066e60b10d781ee4ad3d6395dfd7d2 to af61169216618d7b9174c33931a867f42941095fd7343430b66508c7746114f7. A few per-target values crossed the 12-decimal rounding boundary by 1e-12.
- Root cause: floating-point reductions (NumPy dot/mean) and 12-decimal ledger serialization were too sensitive to last-bit runner variation. Archive SHA, dates, code path and train-prefix checks did not change; this was output numeric canonicalization, not a target leakage finding.
- Correction: use Python math.fsum for score/reduction/mean calculations; canonicalize JSON numbers to 12 significant digits; round target-ledger floats to 9 decimal places; add a regression test for ULP-level numeric noise.
- The next run must pass the persisted-output byte-diff guard. Until then, reproducibility is not claimed.


## One-time canonical-output rebaseline checkpoint

The first canonicalized replay intentionally changed JSON numeric formatting (12 significant digits) and selected-ledger precision (9 decimal places) relative to the original pre-canonicalization report. This is a representation change, not a change to the pinned archive, target set, model, alpha selection, or inferential decision. A tracked one-run rebaseline flag is being used only to persist this canonical format. The flag must be removed afterward, and a subsequent clean replay must pass the byte-diff guard before reproducibility is claimed.


## Canonical rebaseline output persisted

- Rebaseline workflow run 42482566102 completed successfully on 2026-11-08; unit/synthetic tests, pinned canonical walk-forward, report generation and artifact upload passed.
- The generated canonical JSON/Markdown/CSV were committed by the workflow at commit fef805ce9ee8bbe5fc5532f4eb41c337906ecef6. The selected target ledger contains 15,505 rows and its SHA-256 recorded in the report is f2ad33ff6cf7e8c6941dc730cb922fe0e93ed3fc5fdb2a8a42a512541b430b90.
- The one-run flag is now being removed. The next run must execute the strict persisted-output diff without bypass. Reproducibility remains unconfirmed until that strict run passes.
