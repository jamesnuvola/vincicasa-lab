# Q129 checkpoint — family-wise maximum Top20 hit audit

- Protocol committed before final calculation: e8f94633ddbf4c08e36d0f331d47a068269d5f2d; protocol blob 07d88d9aa62909b180c282d215bd3036617a311a.
- Base main: 06e9e470054a86a0b710657db35e0c2259ef6b0a.
- Source ledger blob: 553e08a3c7a0aabd092d3977b75bf959e90b8b3b; 134,568 rows; 3,204 targets; 42 fixed rule configurations per target.
- Statistic: maximum Top20 overlap across all 42 rule configurations for each target.
- Conditional null: 1,000 independent uniform 5-of-40 draws per target; seed 0x01292027.
- Discovery / Validation / historical Blind OOS: 1,922 / 641 / 641 targets.
- Blind OOS observed mean max: 4.24804992; null mean: 4.26743370; gain: -0.01938378; one-sided p: 0.813187.
- Paired circular moving-block bootstrap: 10,000 replicates, block 20; 95% CI [-0.06154134, 0.02171451].
- Decision: NO_FAMILYWISE_MAX_HIT_LIFT_DEMONSTRATED.
- 11/11 observation provisional only: secondary-source consensus 1, 21, 22, 27, 29; official archive/bulletin has not exposed the combination. Exact family p(max Top20 5/5) 0.35916737. No canonical archive or Q60 update.
- Validation: 12/12 checks; 134,568 strict-prior rows; 658,008 exact 5-of-40 combinations.
- Limitations: 42-rule family selected after archive; historical Blind OOS not virgin; broader Q00-Q128 multiplicity not corrected; conditional randomization assumes independent uniform draws.
- No scorer change, freeze mutation, Q60 increment, engine promotion, or automatic merge.
- Next: await official contest 315 combination, then append-only score existing 43 global and one positional freeze.

## Replay recovery — 2026-11-12

- Exact-head replay runs 43117898470 (push) and 43117940502 (pull request) failed at the source-blob guard before statistical recomputation.
- Root cause: the runner compared the pinned Git blob SHA with a SHA-1 recomputed from decoded working-tree text. These are not the same verification layer; checkout/text representation can differ even when the committed tree contains the pinned blob.
- Correction: the runner now checks `git rev-parse HEAD:reports/sequence_agent/historical_rule_ledger.csv` against the protocol blob SHA and requires `git diff --quiet HEAD -- <source path>` before parsing the source. All row-level strict-prior, count, actual-combination, and hit-count checks remain active.
- No protocol, source ledger, statistical result, target freeze, canonical archive, Q60 record, or production scorer was changed.
- The updated runner blob is `cfba32f0005eee8f62368587f887137e983845dc` (9,735 UTF-8 bytes).
- Fresh exact-head replay is pending.
