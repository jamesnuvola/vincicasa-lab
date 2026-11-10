# Q92 manual result-branch readback verification — 2026-11-10 11:47 Europe/Rome

This is an append-only follow-up to `q92_20261108_postrun_reconciliation_2026-11-10.md`.

## Scope

The aggregate workflow's final Git-tree/blob readback step failed because it queried the wrong hard-coded branch. This follow-up independently fetched the accepted outputs from the actual result branch:

`research/sonar-q92-results-20261108-64118b89a59cf689dea6c90a7736db6ef7aca0a3`

The receipt was fetched from that same branch and used as the expected SHA-256 manifest.

## Exact SHA-256 readback

All eight entries in `receipt.output_sha256` were fetched through the GitHub Contents API and recomputed locally from the returned UTF-8 content. Every byte length and SHA-256 matched the receipt:

| File | Bytes | SHA-256 match |
|---|---:|---|
| `q92_20261108_report.json` | 19,432 | PASS |
| `q92_20261108_manifest.json` | 23,720 | PASS |
| `q92_20261108_candidate_shortlist.csv` | 24,974 | PASS |
| `q92_20261108_candidate_selection.json` | 10,184 | PASS |
| `q92_20261108_paired_blind_ledger.csv` | 133,830 | PASS |
| `q92_20261108_paired_inference.json` | 2,325 | PASS |
| `q92_20261108_shard_artifact_manifest.json` | 12,411 | PASS |
| `q92_20261108_acceptance_summary.json` | 3,770 | PASS |

The acceptance-summary SHA-256 also matches `receipt.summary_sha256`. The persistence receipt itself is present and readable; the separate uploaded artifact bundle had already passed its own SHA-256 byte-readback in the workflow.

## Precise status

- Manual SHA-256 readback of all eight result outputs plus the acceptance summary: **PASS**.
- Result files present and readable on the intended Git branch: **PASS**.
- Original workflow Git-tree/blob readback step: **FAIL**, due to the wrong hard-coded branch reference.
- Separate result-branch CI/replay: **NOT RUN / NOT VERIFIED**.
- Human review and merge: **PENDING**.

The manual hash verification establishes byte identity against the receipt for the fetched files. It does not retroactively change the failed workflow job to PASS.

## Metadata warning

The report and manifest status fields remain `AGGREGATED_PENDING_ACCEPTANCE_VALIDATION`, while the acceptance summary records `ACCEPTANCE_PASS_PENDING_ARTIFACT_PERSISTENCE` and the receipt records `ACCEPTANCE_PASS_ARTIFACT_PERSISTED_PENDING_RESULT_BRANCH_CI_AND_HUMAN_REVIEW`. Preserve this discrepancy in review; do not silently rewrite accepted outputs.

## Next action

Correct both hard-coded result-branch references in the Q92 workflow and add a lightweight read-only result-branch replay before any future expensive shard rerun. Keep the Q92 candidate unpromoted and PR #23 open for human review.
