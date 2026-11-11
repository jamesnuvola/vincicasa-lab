# Q116 — Active-engine Top20 marginal hit-count calibration

- Run timestamp: 2026-11-11 10:47:17 Europe/Rome (09:47:17 UTC).
- Main reference commit: 04fed58ab8a4226da3cd2bc2a495a12095941355.
- Pinned Q113 source ledger blob: 79ad1092d71c4c93aa7365bcd4e8ee48d42df569.
- Compact source blob: b4ea460d0080f7abbec0b4d563a6089a3146fff5; 116020 bytes; 3,203 targets from 2018-02-03 through 2026-11-10.
- Hypothesis: test whether the reconstructed active-engine Top20 hit-count distribution departs from exact Hypergeometric(40,20,5), especially in mean and 5/5 upper tail.
- Results: full-sample mean 2.505775835155; expected 2.5. Full-sample Pearson X² 12.463676081537, raw p undefined, Holm p 0.347496995388. Blind OOS mean 2.525741029641; Pearson X² 2.42872582024, raw p undefined, Holm p 1. Blind 5/5 20/641, exact one-sided p undefined, Holm p 1.
- Full sample has a nominal Pearson p below 0.05, but it does not survive Holm across 12 endpoints; Blind OOS shows no departure.
- Validation: 14/14; future suffix mutation 9/9; deterministic replay PASS.
- Limitations: post-hoc on a previously examined ledger; historical reconstruction, not contemporaneous forecasts; no virgin holdout; no number-identity prediction.
- Operational state: main queue Q60 = 23/200 (177 remain). Main shadow file contains 43 global pending freezes for 2026-11-11; positional file contains 1 pending freeze. The official Sisal detail page confirms contest 314/date and prize counts but does not expose the five numbers in its text; the official VinciCasa archive still lists contest 313 as its latest visible result. Treat the 2026-11-10 exact-number provenance as unresolved pending an official number listing.
- Q115: dedicated Node 20 replay run 42991167922 SUCCESS; general CI run 42991516829 SUCCESS; a later evolutionary-only run 42991526493 was cancelled, not failed.
- Next: await the 2026-11-11 draw; score all pending freezes without retuning; resolve contest-314 exact-number provenance before treating 23/200 as fully confirmed.
- No merge, no promotion, no edits to PR #6, #7 or #8.
