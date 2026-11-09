# VinciCasa SONAR hourly checkpoint — 2026-11-09 04:12 UTC

## Status
PARTIAL. Q89's stored acceptance report is VALIDATED_PENDING_HUMAN_REVIEW; a current-head recovery run is still in progress. Q92 is preregistered but not yet implemented/executed. No engine promotion or automatic merge.

## Canonical archive
- main commit: 6cca9022d4311a3f9aba2925fce8c653dc6b63ab
- data/storico_daily.csv blob: 77ca692a6082809fcc6c471501617433ec7c36cf
- 3,402 draws, 2017-07-17 through 2026-11-08
- latest quintet: 3,7,10,16,27

## Q89 verified persisted evidence (archive cutoff 2026-11-07, 3,401 draws)
- 4,686,825 nine-feature equal-weight formulas; 3,351 targets split Discovery 2,011 / Validation 670 / Blind OOS 670.
- 14,060,475 formula/split rows; Holm family 42,181,425 tests; 0 rows below adjusted p=0.05.
- Frozen candidates: Q89 P9_06_09_12_14_15_17_18_19_23; Q88 control P8_00_08_11_12_15_16_19_23.
- Blind OOS Q89: Top-5 11.7612%, Top-10 23.5821%, Top-20 49.5522%, mean rank 20.6137.
- Blind OOS Q88 control: Top-5 10.9851%, Top-10 24.3881%, Top-20 48.6866%, mean rank 20.7731.
- Uniform baseline: Top-5 12.5%, Top-10 25%, Top-20 50%, mean rank 20.5.
- Paired Q89−Q88 Top-5 delta +0.7761 percentage points; block bootstrap 95% CI [−0.2985,+1.8507] pp; sign-flip raw p=0.179841; Holm p=0.539523.
- Top-10 delta −0.8060 pp, Holm p=0.601670; Top-20 delta +0.8657 pp, Holm p=0.601670.
- Decision: NO_SIGNIFICANT_GAIN. Historical blind segment is not independent prospective confirmation. Global formula-family p-values are continuity-corrected normal approximations, exploratory not exact.

## Q89 persisted Git artifacts and blob SHAs
- per_number_condition_9plus_grammar.json — 179d9a6df5f2c790694a0477597e9893528f9e21
- per_number_condition_9plus_paired_inference.json — 88e1b798770004844f72f09afdafabfa2e75e70e
- per_number_condition_9plus_candidate_selection.json — 3fdf178eff9186b49732664a5e82763bfda8343f
- per_number_condition_9plus_formula_metrics_manifest.json — 9a993568bf7863396dbab0d27bc63f7115f5ccac
- per_number_condition_9plus_target_ledger.csv — fe4aba358fcd103eb3c5b74ad3aaa4b360552933

## Q89 workflow gates
- Earlier exact-head recovery run 42538247699: SUCCESS, including acceptance, append-only persistence/readback and current-head CI dispatch.
- Current-head recovery run 42553200315 at bd334b3be896c64483fb611c781e5eb025f41dd3: aggregate SUCCESS; acceptance validator SUCCESS; persistence/readback IN PROGRESS; final run conclusion not yet observed.
- Project CI run 42553200357 on the same head: SUCCESS.
- Do not mutate PR #20 while this persistence run is active.

## Q92 hypothesis and preregistration
- Protocol: reports/sequence_agent/q92_preregistration_2026-11-09.json, blob e7cc679a5df83def6be0b0aa771ceca8e688695d
- Hypothesis: enumerate all C(27,10)=8,436,285 equal-weight ten-feature prior-only formulas and select candidate Discovery→Validation, compare paired blind against refreshed Q89 selection on same archive/splits.
- 15 shards × 562,419 formulas; 3,352 targets; Discovery 2,012 / Validation 670 / Blind OOS 670; 25,308,855 metric rows; Holm family 75,926,565 tests.
- Synthetic combinadic test executed locally: 10,007 rank/unrank round-trips passed; exact 15-shard partition checked; endpoints rank 0=(0..9), rank 8,436,284=(17..26).
- Q92 implementation pending. Crucial prerequisite: refresh Q89 candidate selection on the exact 2026-11-08 canonical archive; do not reuse candidate selected on 2026-11-07.

## Root causes / limitations
- Prior Q89 acceptance failure: lazy CSV DictReader was tied to closed file; materialized rows and added regression test.
- Q91 CI was triggered on Q89 PR merge ref by broad shared paths; compile failed because Q91 script absent from that merge ref. This is workflow scope/merge-ref issue, not Q89 predictive evidence. Do not edit PR #8 base branch.
- Q89 finite equal-weight grammar only; weighted, nonlinear, conditional, and interaction formula families remain open.
- No automatic merge, no engine promotion, no shadow insertion. PRs #6/#7/#8 untouched; immutable 2026-10-25 freeze preserved.

## Next iteration
1. Finish and verify current Q89 persistence run 42553200315, including exact byte readback and final conclusion.
2. On an isolated research branch, implement Q92 combinadic runner, validator, and synthetic regression tests.
3. Refresh Q89 control on canonical 2026-11-08 archive/splits; execute Q92 only after that prerequisite passes.
4. Require acceptance validator, append-only persistence, exact-head CI, and human review/integration before marking Q92 complete.
