# Q141-A17 execution recovery and finalization note — 2026-11-14

## Recovered failures

1. **Run 43529661906 — source alignment rejected row 0.**
   - Root cause: the Q7 walk-forward ledger contains 3,387 raw rows, not 3,386 scored rows. Its first row (2017-07-17) is explicitly INSUFFICIENT_HISTORY, has prior_draws=0, a blank cutoff and blank rank columns. The remaining 3,386 rows are scored.
   - Correction: validate and exclude exactly that initial row, then reconcile each scored row j against archive cutoff j and target j+1. Added a dedicated regression test for the initial unscored row.
   - The next full run passed source extraction, strict-prior reconciliation and the experiment step.

2. **Run 43529893613 — no-op persistence commit.**
   - Root cause: an earlier run had already persisted byte-identical artifacts; a duplicate run attempted an empty Git commit.
   - Correction: persistence now checks the staged diff and skips empty commits.

3. **Run 43530452502 — concurrent rebase conflicts.**
   - Root cause: two workflow runs started from different event commits and both attempted to persist the same generated checkpoint, manifest and validation files. The later rebase encountered content conflicts.
   - Correction: serialize the dedicated workflow with cancel-in-progress enabled; stage generated artifacts outside the worktree, fetch the latest remote branch, reset to that exact remote head, restore the staged artifacts, and commit only the resulting delta. No force push or rebase is used in the persistence path.

## Final successful evidence

- Dedicated workflow run 43530977780 completed with conclusion SUCCESS.
- 10/10 unit tests passed.
- 3,387 raw Q7 ledger rows reconciled, including the single initial insufficient-history row; 3,386 scored rows and 1,023 formula masks verified.
- 2,986 evaluated targets: Discovery 1,792, Validation 597, historical Blind OOS 597.
- 199 independent-column circular-shift surrogates and 20,000 block-bootstrap replicates per split completed.
- Full deterministic replay was byte-identical.
- Remote Git readback verified the report, report Markdown, target ledger, null distribution, eigenvalues, component loadings, source lineage, validation record and manifest. Checkpoint and receipt were subsequently refreshed and read back again after the manifest status was closed.

## Statistical disposition

The registered practical threshold of 0.75 mean captured energy was not reached in either holdout (Validation 0.712218; historical Blind OOS 0.712131). The six-dimensional subspace was far above the independent-column circular-shift null (raw p=0.005 in both holdouts; Holm p=0.010), but this null does not condition on the deterministic overlap structure of the 1,023 feature-subset masks. The preregistered A17 hypothesis is therefore NOT CONFIRMED. No number-prediction claim or engine promotion follows.

## Governance

The branch remains a research branch. No merge, rebase of protected work, production-engine change, canonical-archive change or prospective-freeze change was made. PRs #6, #7 and #8 were not modified. Human review remains required.
