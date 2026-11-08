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
