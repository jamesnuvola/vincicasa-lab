# VinciCasa SONAR checkpoint — 2026-11-09 04:48Z

## Canonical archive and accepted prior evidence
- Canonical archive: 3,402 draws through 2026-11-08; final quintet 3, 7, 10, 16, 27.
- Canonical archive Git blob SHA-1: 77ca692a6082809fcc6c471501617433ec7c36cf.
- Canonical archive SHA-256: 3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed.
- Q89 accepted base catalog remains the frozen 2026-11-07 version: 4,686,825 nine-feature formulas; 14,060,475 metric rows; 469 compressed metric parts; status VALIDATED_PENDING_HUMAN_REVIEW.

## Q89 incremental refresh — current verified gate
- Workflow run: https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42563200087
- Fifteen of fifteen deterministic three-target delta shards completed SUCCESS.
- Aggregate exact split deltas, global Holm family and Discovery→Validation candidate freeze are still IN_PROGRESS.
- Acceptance validation, append-only persistence, exact-byte readback and exact-head CI have not yet completed.
- No Q89 refreshed quantitative results are accepted or reported from this run.
- Refresh uses three preregistered target offsets 2011, 2681, 3351 to update split counts from 2011/670/670 to 2012/670/670 without rescoring all historical targets.

## Q92 strict-prior ten-feature shard evaluator
- Implementation branch: research/sonar-q92-walkforward-prep-20261109.
- Head at checkpoint: 49d3a7b5c5afb7fffa387bcc893c99b675a08e4f.
- Dedicated synthetic acceptance run: https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42563724367 — SUCCESS.
- Synthetic tests verify vectorized equal-weight formula matrix, stable rank tie-breaking, strict-prefix exclusion of the target draw, and reconciled synthetic metric/target-ledger outputs.
- Full project CI on this exact head: https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42563724491 — IN_PROGRESS at checkpoint.
- No Q92 historical shard evaluation has started.

## Root causes recovered
1. Q89 full-refresh aggregator was hard-coded to 3,401 archive draws and split 2011/670/670; incremental delta protocol was implemented and triggered instead.
2. Q92 runner prototype on PR #22 base main could not import Q80/Q81 feature-stack modules; prototype was removed from PR #22 core and moved to the Q80 research branch. PR #22 remains combinadic-only.
3. Q92 vectorized formula-weight input validation expected transposed dimensions; corrected to (formula_count, feature_count).
4. Q92 synthetic replay fixture did not create the archive bytes used for source SHA; corrected with a deterministic synthetic archive file.
5. Q92 full shard execution is gated behind explicit [q92-execute] commit marker; no full shards were triggered.

## Protocol discrepancy requiring addendum before Q92 execution
- Preregistered global batch count: ceil(8,436,285 / 1,024) = 8,239.
- Shard-local runner batches: 15 × ceil(562,419 / 1,024) = 8,250.
- This is a computational partition-count difference, not a formula coverage gap, but it must be documented and reflected in acceptance before any Q92 full run.

## Next action
1. Finish Q89 aggregate, fail-closed acceptance, append-only persistence/readback and exact-head CI.
2. Integrate the accepted Q89 same-archive control outputs into the Q92 walk-forward branch.
3. Implement Q92 global aggregator, Holm validator, paired Blind OOS inference, persister and exact-head workflow; add the batch-partition addendum.
4. Run Q92 only after the Q89 control status is acceptance-validated and the complete Q92 gate passes.
5. Keep all candidate engines pending human review; no merge, promotion or shadow-stream insertion.

PR #6, #7 and #8 are to remain untouched and unmerged. PR #22 remains draft; the Q92 walk-forward branch is not yet a PR.
