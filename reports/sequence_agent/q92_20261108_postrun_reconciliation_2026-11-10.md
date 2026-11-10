# Q92 post-run reconciliation — 2026-11-10 11:47 Europe/Rome

## Source and execution

- Source checkout: `64118b89a59cf689dea6c90a7736db6ef7aca0a3`
- Canonical archive: 3,402 draws through 2026-11-08; SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Workflow run: [42777967290](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42777967290), attempt 2.
- Preflight: PASS.
- All 15 immutable shards: PASS.
- Aggregation and independent numerical acceptance: PASS.
- Accepted bundle: artifact ID `13753661277`, 204,386,242 bytes; uploaded-bundle digest readback verified as `ebcd5d6f484dca960c3fd69a8f8e340a51ac08449646e95d88d91b02ae842205`.
- Result branch: `research/sonar-q92-results-20261108-64118b89a59cf689dea6c90a7736db6ef7aca0a3`.
- Result commit created by the workflow: `4e8698e` (full commit recorded by GitHub in the branch history).

## Root cause of the overall aggregate-job failure

The accepted files were committed and pushed successfully to the dynamically named result branch. The final Git readback step then failed because the workflow hard-coded:

`origin/research/sonar-q92-results-20261108`

instead of resolving:

`origin/$RESULT_BRANCH`

The actual branch includes the source SHA suffix. The push therefore succeeded, but the verifier inspected a different branch and reported the first expected path missing. This is a post-persistence verification-path defect, not a shard, aggregation, or statistical-acceptance failure.

The same hard-coded branch appears in both the existing-result comparison block and the final Git-tree/blob readback block in `.github/workflows/sonar-q92-full-walkforward.yml`. Future reruns should use `os.environ["RESULT_BRANCH"]` in both Python blocks (and import `os` in the first block).

## Repository readback performed in this recovery

The GitHub Contents API successfully returned all nine expected files from the actual result branch:

1. `q92_20261108_report.json`
2. `q92_20261108_manifest.json`
3. `q92_20261108_candidate_shortlist.csv`
4. `q92_20261108_candidate_selection.json`
5. `q92_20261108_paired_blind_ledger.csv`
6. `q92_20261108_paired_inference.json`
7. `q92_20261108_shard_artifact_manifest.json`
8. `q92_20261108_acceptance_summary.json`
9. `q92_20261108_persistence_receipt.json`

This establishes that the paths exist and are readable on the pushed result branch. The workflow's intended byte-for-byte Git-tree/blob verification did **not** complete because of the wrong branch reference; do not label that job PASS. The artifact bundle itself did pass its SHA-256 byte-readback step.

## Acceptance and measured result

The independently generated acceptance summary reports:

- 8,436,285 formulas.
- 3,352 strict-prior scored targets.
- Discovery / Validation / historical Blind OOS: 2,012 / 670 / 670.
- 25,308,855 metric rows.
- Global Holm family: 75,926,565 tests.
- Selected candidate: `P10_01_08_11_12_14_15_16_18_19_23`.
- Paired primary decision versus Q89: `NO_SIGNIFICANT_GAIN`.
- Blind OOS Top5 mean hits: 0.111642 versus uniform 0.125; absolute lift −0.013358; global-Holm p=1.0.
- Paired Top5 mean delta versus Q89: −0.006269; 95% block-bootstrap interval [−0.016716, +0.004179]; Holm sign-flip p=0.619769.

The historical Blind OOS is explicitly exploratory and is not prospective confirmation.

## Metadata inconsistency retained for transparency

The report and manifest status fields still say `AGGREGATED_PENDING_ACCEPTANCE_VALIDATION`; the acceptance summary says `ACCEPTANCE_PASS_PENDING_ARTIFACT_PERSISTENCE`; the receipt says `ACCEPTANCE_PASS_ARTIFACT_PERSISTED_PENDING_RESULT_BRANCH_CI_AND_HUMAN_REVIEW`.

Do not infer a completed result-branch CI from these fields. The acceptance summary is the source for the numerical acceptance decision; the receipt records the artifact bundle and result branch; the final Git readback job failed as described above. A future metadata-normalization change should be append-only and must not rewrite the accepted historical output silently.

## Next action

1. Correct the result-branch variable in both workflow readback blocks.
2. Add a lightweight read-only verifier or replay that validates the actual dynamic result branch without rerunning the 15 expensive formula shards.
3. Verify all nine Git files against the receipt's per-file SHA-256 and Git blob/tree identifiers.
4. Keep PR #23 open for human review; do not merge or promote the candidate.
