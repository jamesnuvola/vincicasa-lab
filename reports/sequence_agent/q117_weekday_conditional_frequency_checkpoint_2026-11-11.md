# Q117 checkpoint — weekday-conditioned frequency

- Protocol was committed before the computation.
- Source: main 04fed58ab8a4226da3cd2bc2a495a12095941355, archive blob 40f317e2d0067e061c46ab799d66f777a0e087c0, 3,404 draws through 2026-11-10.
- Targets: 3,204, strict prior, splits 1,922 / 641 / 641.
- Alpha grid: 25, 50, 100, 200, 400, 800, 1600. Selected on Validation only: 1600.
- Validation checks: 14/14; future-suffix mutation 9/9; deterministic ledger replay PASS.
- Blind OOS inference: 4 endpoints, 50,000 block sign-flips, 10,000 circular block-bootstrap replicates, block length 20, Holm across four endpoints.
- Prospective research freeze: 2026-11-11, cutoff 2026-11-10, timestamp 2026-11-11T11:05:38Z, status FROZEN_PENDING.
- Limitations: historical Blind OOS is not virgin; historical forecasts are reconstructed; model is not production scorer.
- Q60 remains unchanged at 23/200; contest-314 exact-number provenance remains pending official primary listing.
- No merge, no promotion, no edits to PR #6, #7, #8.
