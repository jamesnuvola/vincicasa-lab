# Q89 incremental refresh protocol — canonical archive through 2026-11-08

**Status: preregistered; implementation and execution pending.**

## Hypothesis and exact split transition

Refresh the accepted nine-feature Q89 catalog from the 2026-11-07 archive (3,401 draws) to canonical main through 2026-11-08 (3,402 draws) using exact additive per-target metric deltas. The formula universe remains C(27,9)=4,686,825 with 15 shards × 312,455 formulas.

Old splits: Discovery/Validation/Blind OOS = 2,011/670/670.  
New splits: Discovery/Validation/Blind OOS = 2,012/670/670.

Three affected targets, all scored from strict prefixes:

| Offset | Archive index | Target date | Cutoff | Actual quintet | Split movement |
|---:|---:|---|---|---|---|
| 2011 | 2061 | 2023-03-09 | 2023-03-08 | 5 19 32 33 37 | old Validation → new Discovery |
| 2681 | 2731 | 2025-01-07 | 2025-01-06 | 5 17 18 23 33 | old Blind OOS → new Validation |
| 3351 | 3401 | 2026-11-08 | 2026-11-07 | 3 7 10 16 27 | new Blind OOS target |

For every formula and additive metric count:

- Discovery(new) = Discovery(old) + score(target offset 2011)
- Validation(new) = Validation(old) − score(target offset 2011) + score(target offset 2681)
- Blind(new) = Blind(old) − score(target offset 2681) + score(target offset 3351)

Recompute means, rates, raw hypergeometric-normal p-values and global Holm after these integer adjustments.

## Candidate selection

Discovery top-100 by Top-5 number-hit share; tie-break lower mean rank, then lexicographic formula ID. Select one candidate on Validation with the same rule. Blind OOS is never used for selection. Freeze this Q89 candidate as the control for Q92 on the exact same archive/splits.

## Persistence and acceptance

Persist the 15 deterministic formula delta shards (one row per P9 formula, seven metric counts for each of the three target offsets), target-delta ledger, refreshed candidate shortlist/selection, report and manifest. The prior accepted Q89 metric catalog plus these delta shards reconstructs the refreshed split metrics; do not duplicate the complete 14,060,475-row catalog.

Acceptance requires exact archive lineage, target cutoff reconciliation, 4,686,825 formula rank coverage with 312,455 rows per shard, split totals 2,012/670/670, global Holm family 42,181,425, deterministic Discovery/Validation selection, append-only byte-exact persistence, current-head CI, and human review.

## Limitations

This is an incremental exact update of the accepted Q89 base catalog, not a full re-evaluation of all targets. The catalog-level p-values remain approximate and exploratory. Historical Blind OOS is not independent prospective confirmation. Q92 ten-feature execution is gated until the refreshed Q89 control is accepted.

## Guardrails and next action

No automatic merge, engine promotion, or shadow insertion. Preserve the 2026-10-25 freeze; PRs #6, #7, #8 remain untouched. Implement the delta runner/aggregator/acceptance tests and workflow, then execute after current-head Q89 acceptance/CI.
