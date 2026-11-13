# Q142 — Fixed 42-rule family exact FWER audit

**Status:** retrospective audit specification, written after the historical ledger and D5 result were already visible. This is explicitly **not preregistered** and cannot be treated as confirmatory.

## Quantitative hypothesis

At least one of the 42 fixed Top20 rule configurations has an excess 5/5 or 4+/5 coverage rate over the exact uniform 5-of-40 null in one or more chronological partitions, after controlling family-wise error across all 42 rules × 3 partitions × 2 endpoints (252 tests) with Holm at alpha 0.05.

The family-level temporal-stability diagnostic is the Spearman correlation of the 42 per-rule 5/5 rates between Discovery, Validation and historical Blind OOS. This is descriptive and has no confirmatory p-value.

## Data and strict-prior audit

- Canonical archive: data/storico_daily.csv, 3,406 draws through 2026-11-12; expected Git blob SHA-1 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.
- Fixed-rule ledger: reports/sequence_agent/historical_rule_ledger.csv, 134,652 rows = 3,206 targets × 42 rules; expected Git blob SHA-1 472d6b094c4d533412207baa5cbdc8d9bd43e89e.
- Each target must be exactly the canonical archive suffix after 200 prior draws.
- Each ledger cutoff must equal the immediately preceding archive date; each actual quintet, Top20 uniqueness, hit_count and all5 flag are recomputed.
- The ledger evaluation mode is RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW. This audit verifies ledger alignment and scoring; it does not regenerate all 42 rankings.

## Chronological partitions

For N=3,206 targets, split by target order:
- Discovery: first floor(0.60N) = 1,923 targets.
- Validation: next floor(0.20N) = 641 targets.
- Historical Blind OOS: remaining 642 targets.

The word "historical" is essential: this is not a virgin holdout because the rule family was developed after the full historical series was available.

## Exact nulls and tests

For a fixed Top20 set under an IID uniform 5-of-40 draw:
- P(5/5) = C(20,5)/C(40,5).
- P(4+/5) = [C(20,4)C(20,1)+C(20,5)]/C(40,5).
- Expected number of hits in Top20 = 2.5.

For each rule, split and endpoint, compute the exact one-sided Binomial upper-tail probability with the relevant hypergeometric event probability. Apply one Holm step-down correction across all 252 tests. This handles arbitrary dependence within the defined 252-test family, but not the broader Q00–Q141 search.

## Decision

Support requires at least one Holm-adjusted p < 0.05. Any result is still exploratory because the 42-rule family was selected after historical inspection. No engine promotion, archive mutation, prospective freeze mutation, PR merge or automatic promotion is permitted.

## Next action

If no family-wise excess is found, do not add another selector from this ledger. Preserve all already-frozen prospective forecasts append-only and wait for official outcomes. Reconcile only after the official result is published.
