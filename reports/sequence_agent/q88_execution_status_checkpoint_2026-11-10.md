# Q88 execution-status checkpoint — 10 November 2026

## Verified research result
- Q88 signed node-to-graph transfer walk-forward: completed.
- Independent acceptance replay: PASS.
- Workflow run 42731530270; artifact 13725366402.
- 3,402 canonical draws through 2026-11-08; 3,202 strict-prior targets.
- Discovery/Validation/historical Blind OOS: 1,921/640/641.
- 15 models; 48,030 rank vectors replayed; 256,160 transfer values replayed.
- 135 exact-null Holm tests and 96 paired moving-block bootstrap Holm tests.
- Unit tests 10/10 PASS.
- Selected on Discovery only: DYN::TRANSFER_BLEND.
- Historical Blind OOS Top20 2.531981 vs Equal42 2.546022; delta −0.014041; paired 95% CI [−0.035920,+0.007800]; paired Holm 1.000; exact-null Holm 1.000. Primary gate NOT_MET.

## Repository persistence
The Q88 code, preregistration, tests, protocol, compact result summary, validation summary, artifact reference and checkpoints are saved on the Q88 research branch and have been read back. The complete 3.05 MB target ledger and full report remain in artifact 13725366402 (SHA-256 67c3130b42429b49441d1be01449d86c58a191e6be06303c3a21f1787f65ee36; expiry 2026-11-17). They are **not yet committed to the repository**. Do not mark repository persistence complete.

## Current-head checks
- Read-only Q88 workflow run 42732568481: PASS; Python compilation and 10/10 tests. Full read-only artifact replay was skipped because the complete ledger/report are not yet committed on this head.
- General CI run 42732568648: IN_PROGRESS. Archive audit, generated-data rebuild/audit, prospective-gate test, engine syntax check, and SONAR analysis/queue compilation passed. Evolutionary-lab execution is in progress; positional/regime/residual lab and application build remain pending at checkpoint time.
- Earlier full acceptance run 42731530270 is on the same Q88 code; subsequent changes were workflow/documentation/result-summary only, not model code.

## Workflow permission diagnosis
Attempts to run PR workflows requesting write permissions remained pending without jobs. The PR workflow was restored to read-only. No write-permission run is treated as successful. A trusted persistence path still requires repository-approved execution or a verified connector upload path.

## Next actions
1. Finish current-head general CI and record its final conclusion.
2. Obtain an approved trusted write path to commit the full ledger/report; do not infer persistence from the workflow artifact.
3. Trigger read-only exact-head replay after full outputs are committed.
4. Next research hypothesis (not yet implemented): compare signed graph-to-node transfer against a node-only autoregressive null and degree/strength-preserving edge-label randomization, preregistered before execution.

No engine promotion, no immutable freeze modification, no prospective shadow insertion, no automatic merge. PR #6, #7 and #8 remain untouched.
