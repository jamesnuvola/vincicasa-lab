# Q92 result-branch readback repair — 2026-11-10

## Root cause

The full Q92 run `42777967290` completed all 15 shards, global Holm aggregation, fail-closed acceptance, bundle upload, and append-only result-branch push. Its final Git-tree/blob readback step failed because the Python readback block hard-coded:

`origin/research/sonar-q92-results-20261108`

The actual result branch, already supplied to the workflow as `RESULT_BRANCH`, is:

`research/sonar-q92-results-20261108-64118b89a59cf689dea6c90a7736db6ef7aca0a3`

The error was therefore a branch-reference defect, not a missing artifact or failed statistical acceptance.

## Repair committed on the Q92 source branch

- Both hard-coded references now use `origin/` + `os.environ["RESULT_BRANCH"]`.
- The full walk-forward workflow no longer triggers itself on a workflow-file-only edit. This prevents a lightweight readback repair from automatically launching another 15-shard, 8.4M-formula run.
- Added `scripts/verify_sonar_q92_result_branch.py`, a read-only verifier that checks the configured result branch, source ancestry, receipt/summary consistency, all seven receipt-listed output SHA-256 values, the acceptance-summary SHA-256, Git blob IDs, and the artifact-bundle byte-readback attestation.
- Added unit tests for Git blob hashing, receipt/summary consistency, and explicit stale-status warnings.
- Added `.github/workflows/sonar-q92-result-branch-replay.yml`, which runs the lightweight verification without regenerating shards.

## Existing evidence preserved

The result branch remains:

`research/sonar-q92-results-20261108-64118b89a59cf689dea6c90a7736db6ef7aca0a3`

The accepted result bundle is not rewritten. No shard is regenerated. No candidate, split, metric, p-value, or forecast is changed.

The manual GitHub Contents API readback already recorded matching byte lengths and SHA-256 values for all eight result outputs (including the acceptance summary). The new replay workflow is an additional independent check; until it completes, its result is **PENDING**, not PASS.

## Metadata warning retained

The report and manifest still say `AGGREGATED_PENDING_ACCEPTANCE_VALIDATION`; the acceptance summary says `ACCEPTANCE_PASS_PENDING_ARTIFACT_PERSISTENCE`; the receipt says `ACCEPTANCE_PASS_ARTIFACT_PERSISTED_PENDING_RESULT_BRANCH_CI_AND_HUMAN_REVIEW`.

These fields are inconsistent. They have not been silently rewritten. The replay verifier reports this as a warning while independently checking byte identity. Human review must decide whether to issue a clearly versioned status-reconciliation document or a new manifest; the accepted outputs remain immutable.

## Next action

Wait for the read-only result-branch replay and exact-head CI. If both pass, update PR #23 with the evidence and retain the status-metadata warning for human review. Do not rerun the 15 shards merely to repair the readback reference. No merge or engine promotion is authorized.
