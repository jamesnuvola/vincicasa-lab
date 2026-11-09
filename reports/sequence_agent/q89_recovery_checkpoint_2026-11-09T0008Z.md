# Q89 recovery checkpoint — 2026-11-09 00:08Z

**Status:** aggregation is in progress; acceptance, persistence and exact-head CI are pending. This checkpoint is not a Q89 completion claim.

## Canonical archive reconciliation
- `main` commit: 6cca9022d4311a3f9aba2925fce8c653dc6b63ab
- `main` archive blob: 77ca692a6082809fcc6c471501617433ec7c36cf; 3,402 draws through 2026-11-08, latest `3, 7, 10, 16, 27`.
- Q89 branch archive blob: 5d2efd70684e918b27d8f06386d545647898336d; 3,401 draws through 2026-11-07, latest `12, 16, 27, 31, 38`.
- Q89 immutable shard artifacts are bound to the 2026-11-07 archive. A current-canonical refresh is still required; do not silently treat these as including 2026-11-08.

## Quantitative hypothesis and preregistered dimensions
Q89 exhaustively evaluates all 4,686,825 equal-weight 9-feature subsets from the 27 prior-only feature catalog. Candidate selection is Discovery top-100 → Validation freeze, and paired Blind OOS comparison against an 8-feature control. Walk-forward dimensions: 3,351 targets; Discovery/Validation/Blind 2011/670/670; 14,060,475 formula-split metric rows; Holm family 42,181,425 tests. Strict prefix features exclude target draw.

The global formula-family p-values use a continuity-corrected normal approximation to the finite-population Hypergeometric null; this remains exploratory and not exact.

## Recovery evidence
- Immutable shard source: run [42524743687](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42524743687).
- Prior aggregation generated metrics but acceptance failed in [run 42534331468](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42534331468); outputs were not accepted or persisted.
- Current recovery aggregation: [run 42538247699](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42538247699), head d062bf9ea5068235a136c8adf011108c89440274. The aggregation step is still in progress; acceptance, persistence and exact-head CI have not run.

The previous acceptance errors reported metric replay mismatches for Q89 and Q88 candidate blocks across Top-5/10/20 and mean rank. A retrieved aggregator blob showed the Q88 actual-rank vector and rank sum being populated from Q89 ranks, inconsistent with separately computed Q88 ranks. This is a confirmed ledger field-mapping defect; the independent Q89 metric replay discrepancy still needs its own numeric diagnostics.

## Guardrails
No merge, promotion or shadow insertion. PRs #6, #7 and #8 remain untouched. The immutable 2026-10-25 freeze is preserved. Historical blind OOS has prior SONAR exposure and is not independent prospective confirmation.

## Next action
Wait for run 42538247699. If acceptance fails, inspect actual/expected replay values, fix Q89 and Q88 fields independently, add targeted regression coverage, and rerun. If acceptance passes, persist all outputs append-only and verify exact bytes plus current-head CI. Reconcile the Q89 archive to canonical main's 2026-11-08 draw before current-canonical coverage is claimed. Only then preregister Q92 (10 features, C(27,10)=8,436,285) as the next expansion.
