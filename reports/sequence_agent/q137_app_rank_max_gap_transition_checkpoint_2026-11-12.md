# Q137 checkpoint — APP rank-space maximum-gap lag-1 transition

- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.
- Source: pinned Q123 rank ledger, 3,204 strict-prior targets through 2026-11-10; disputed 2026-11-11 excluded.
- Split: Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- Exact null: 658,008 five-rank subsets; support 1..36; exact quartile state thresholds 10, 13, 17.
- M0 exact combinatorial PMF; M1 unconditional prequential shrinkage alpha=200; M2 previous-gap-state conditional shrinkage alpha=200.
- Blind OOS: all six gains are negative; all six one-sided block sign-flip p-values are high and Holm-adjusted p-values equal 1.000.
- Validation: 29/29; future suffix invariance 9/9; deterministic replay matched.
- No archive, freeze, Q60 gate, production engine, or protected PR is modified.

## Recovery

- First Node 20 replay failed at parse time because the runner contained duplicate const ledger declarations. The duplicate block was removed; the validation now checks scored.length.
- Second Node 20 replay failed with ReferenceError: combinationCount was not defined. The report now reads the exact enumeration count from nullData.combinations.
- Third Node 20 replay failed with ReferenceError: alpha was not defined in report metadata. The report now uses the fixed ALPHA constant.
- Fourth Node 20 replay executed the experiment but the byte-diff check found split_results omitted because the runner referenced splitSummary instead of the local summary variable. The reference was corrected.
- Fifth Node 20 replay executed the experiment but the byte-diff check found the persisted checkpoint did not match the runner-generated recovery text. The checkpoint and runner text were reconciled.
- All five failures were runner/artifact assembly or serialization defects; no target, estimator, split, alpha value, random seed, score, or inferential result was changed.
- The next replay must confirm byte-identical report, ledger, validation, checkpoint, and manifest before this experiment is treated as technically complete.

## Next action

Keep M0 as the reference; do not promote M1/M2. Continue source-clean prospective collection and resolve contest 315 primary number provenance before evaluating the dependent 2026-11-12 freezes.
