# Q141-C0 — Prior-only formula-family anticipation test

**Registration:** 2026-11-12, before this experiment's computation  
**Status:** PREREGISTERED — execution pending  
**Parent:** Q141 Formula Universe & Behaviour Mapping  
**Source:** base-main archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103`; eligible draws through 2026-11-10 only.

## Hypothesis

A formula family that has produced more Top-5 hits in the preceding 100 scored targets will, on average, produce more Top-5 hits on the next target. A selector that chooses the best family from this strictly prior rolling history may improve the next-target ranking over static combinations of the same families.

The policy is fixed in advance: rolling window 100; maximize mean prior Top-5 number hits; tie-break by lower prior mean actual-number rank, then family ID. The first 100 scored targets use the equal-family ensemble as a deterministic warm-up. No window or threshold tuning is permitted in this experiment.

## Prior-only feature grammar and semantic deduplication

Start from the exact 27 Q80 features, with the same strict-prefix definitions and per-target z-score over numbers 1..40. Q80's `recent_5` is exactly identical to `freq_5`, and `recent_10` is exactly identical to `freq_10`; these are aliases, not independent formula inputs. Verify both equalities on every target and remove the aliases from equal-feature weighting. The resulting 25 unique features are assigned once to six non-overlapping families:

- `frequency_level`: `freq_5`, `freq_10`, `freq_20`, `freq_50`, `freq_100`, `freq_250`, `freq_500`, `freq_all`, `recent_3`.
- `frequency_change`: `trend_5_vs_50`, `trend_10_vs_100`, `trend_20_vs_250`.
- `recency_gap`: `age_since_hit`, `gap_mean`, `gap_sd`, `overdue_ratio`.
- `position_dependence`: `position_log_frequency`, `pair_count_with_last_draw`.
- `neighbour_field`: `neighbor_pm1_history`, `neighbor_pm2_history`.
- `lag_memory`: `lag_1`, `lag_2`, `lag_3`, `lag_5`, `lag_10`.

For each family, its score is the arithmetic mean of its standardized feature columns. All ties are resolved by lower number first. This is a six-family diagnostic, not an exhaustive mathematical universe.

## Selector and controls

For target t:
1. Construct all 25 unique feature columns using only draws strictly before t.
2. Rank numbers independently under each of the six family scores.
3. If at least 100 earlier scored targets exist, choose the family with the best mean Top-5 hit count over the immediately preceding 100 targets; tie-break by lower mean rank then family ID. Otherwise use the equal-family ensemble.
4. Score the target only after the family choice and all rankings are frozen.
5. Update family-performance history only after scoring target t.

Compare:
- Dynamic rolling-100 family selector (primary candidate).
- Equal-family ensemble: equal mean of the six family score vectors.
- Equal-feature ensemble: equal mean of the 25 unique standardized feature columns.
- Fixed family selected on Discovery only by mean Top-5 hits, tie-break by lower mean rank then family ID; evaluate only on Validation and Blind OOS.
- Uniform 5-of-40 expectations: Top-5/10/20 hit shares 0.125/0.25/0.5; mean actual-number rank 20.5.

## Walk-forward and inference

- Minimum prior history: 50 draws.
- Eligible source: 3,404 draws, 2017-07-17 through 2026-11-10; exclude the 2026-11-11 contest 315 row.
- Expected scored targets: 3,354; chronological split rule: target offset / scored targets <0.60 Discovery, <0.80 Validation, otherwise Blind OOS. Expected counts: 2,013 / 671 / 670.
- Discovery is descriptive and selects the fixed-family control only. Validation and Blind OOS remain untouched by policy or hyperparameter selection. The dynamic selector may update online from outcomes strictly earlier than each target; its update rule remains fixed.
- Paired endpoints: Top-5, Top-10, Top-20 number-hit share and mean actual-number rank. Report dynamic-minus-control for hit shares and control-minus-dynamic for mean rank, so positive always favours dynamic.
- Paired inference: non-overlapping 20-target block sign-flip randomization and circular moving-block bootstrap, 20,000 replicates, fixed seeds. Holm correction spans all 24 Validation/Blind × three controls × four endpoints.
- Absolute-uniform check: exact discrete convolution of Hypergeometric(40,k,5) per-target hit counts for dynamic Top-5/10/20 in Validation and Blind OOS; Holm across six tests.
- Primary practical threshold: Blind OOS Top-5 hit-share improvement at least +0.005, Holm-adjusted paired p<0.05, and 95% block-bootstrap lower bound >0.

## Behaviour map

Also report per-family split performance; Top-5 success co-occurrence; Top-5 candidate-set Jaccard overlap; pairwise union coverage and unique-hit gain; lag-1 autocorrelation of family Top-5 hits; dynamic family selection counts and switches. Any per-target oracle-best family is descriptive only and cannot select the same target's ranking.

## Acceptance and limitations

Require exact source Git-blob SHA, 3,404 eligible rows, 3,354 unique chronological target rows, split counts, strict cutoff and future-suffix invariance tests, deterministic rank/tie policy, alias identity checks, replayable inference, complete Holm denominators, and exact output SHA readback.

This is historical exploratory research in a heavily exposed SONAR archive, not virgin prospective confirmation. The family grammar is finite and coarse; the 100-target selector may chase noise. A valid null result is a completed experiment. No engine promotion, shadow insertion, archive mutation, merge or changes to PRs #6/#7/#8.
