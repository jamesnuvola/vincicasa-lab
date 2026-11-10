# SONAR Q97 — five-model RRF consensus checkpoint (2026-11-10)

- Status: POST_HOC_EXPLORATORY_COMPLETE; gate NOT_MET.
- Source Q94 run 42755127353, artifact 13735162512; ledger SHA-256 be4e24f4a4a90261950583cf5752065bd3b735d8351d3637fba4fadeaed67b04.
- Archive: 3,403 draws through 2026-11-09; 3,203 strict-prior targets.
- Splits: Discovery 1,921; Validation 641; historical Blind OOS 641.
- Formula: sum of 1/(20+rank) across five fixed rankings; ties by ascending number.
- Blind Top-20 difference vs Equal42: -0.003120125 hits/target; 95% CI [-0.018720749, +0.014040562].
- Block sign-flip raw p 0.707746; global Holm p 1.000000.
- 15 paired tests, 50,000 sign flips, 10,000 circular block bootstraps, block length 20.
- All prior cutoffs and 16,015 source rank vectors checked; source snapshot and target ledger persisted.

Post-hoc exploratory only: component families were previously examined and historical Blind OOS is not virgin. No promotion, production change, freeze change or merge. Stop retrospective tuning; continue Q60 prospective collection.

## Execution and persistence recovery

- Workflow run 42848795188: six regression tests passed and the strict-prior replay completed successfully.
- The final workflow push failed with `remote: fatal error in commit_refs`; this was a repository-write failure, not an analytical or test failure.
- Report, checkpoint and validation were then persisted through the GitHub connector. SHA-256 readback matches the validation record for the script, report, checkpoint, source snapshot and target ledger.
- The workflow was changed to upload an evidence artifact instead of pushing from the runner; no successful rerun of that revised workflow is claimed.
