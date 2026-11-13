# Q141-D2 — Family-specific volatility-standardized relative advantage

**Protocol status:** preregistered before D2 computation  
**Date:** 2026-11-13  
**Parent:** Q141 Formula Universe & Behaviour Mapping  
**Branch:** `research/q141-d2-family-volatility-standardization-20261113`

## Research question

D1 standardizes each family against the cross-family dispersion on each historical target, then averages those standardized values. D2 tests a different, fixed normalization: remove each target's common difficulty first, then standardize each family's rolling relative advantage by that family's own trailing volatility.

The hypothesis is that a family with a positive relative edge that is stable across targets should be preferred over a family whose same mean edge is driven by unusually volatile outcomes.

## Pinned source and sample

- Source ledger: `reports/sequence_agent/q141_formula_family_behaviour_target_ledger_2026-11-12.csv`
- Source Git blob SHA-1: `4620ac88199256d90bf8e11a852206bfeb817812`
- Archive: `data/storico_daily.csv`
- Archive Git blob SHA-1: `fcb453ed06c8002314f826dbac79d6935f9ac103`
- Eligible archive: 3,404 draws through 2026-11-10; contest 315 and later excluded.
- Scored targets: 3,354; chronological split: Discovery 2,013, Validation 671, historical Blind OOS 670.
- Six fixed families: frequency_change, frequency_level, lag_memory, neighbour_field, position_dependence, recency_gap.

## Quantitative hypothesis

For each prior target s and family f, define relative family outcome:

[
r_{f,s}=h_{f,s}-ar h_s,qquad
ar h_s=rac{1}{6}sum_{g=1}^{6}h_{g,s}
]

For target t, use only the preceding W=100 scored targets:

[
mu_{f,t}=rac{1}{W}sum_{s=t-W}^{t-1}r_{f,s}
]

[
sigma_{f,t}=
sqrt{rac{1}{W}sum_{s=t-W}^{t-1}(r_{f,s}-mu_{f,t})^2+lambda^2},
qquad lambda=0.25
]

[
U_{f,t}=rac{mu_{f,t}}{sigma_{f,t}}
]

Select the family with the largest U. Ties are resolved by lower mean actual-number rank over the same 100 prior targets, then lexicographic family ID. The first 100 scored targets use equal-family ranking, matching the D1/C0 warm-up.

No parameter search or tuning is permitted. W=100 and lambda=0.25 are fixed before calculation.

## Comparators and endpoints

- M0: equal-family ranking.
- M1: Q141-C0 raw rolling-100 family selector from the pinned source ledger.
- M2: exact Q141-D1 target-standardized selector, recomputed from the same pinned source.
- M3: new D2 family-volatility-standardized selector.
- Uniform reference: expected Top-5 hits = 0.625 per target under independent uniform unordered 5-of-40 draws.

Three preregistered co-primary Blind OOS endpoints, positive values favour D2:
1. M3 minus M2 (increment over D1).
2. M3 minus M1 (increment over C0).
3. M3 minus M0 (increment over equal-family).

Practical threshold for each: +0.025 Top-5 hits per target. Historical pass requires all three to meet the practical threshold, circular moving-block bootstrap 95% lower bounds above zero, and Holm-adjusted one-sided block sign-flip p-values below 0.05. A pass remains exploratory and requires a separate prospective freeze.

## Walk-forward and inference

- Strict prior: selection for target t reads only family outcomes from target rows s<t.
- D2 and D1 use the same prior 100 target rows; score target before any update.
- Discovery is descriptive; Validation and historical Blind OOS are locked diagnostics; no tuning.
- Paired uncertainty: circular moving-block bootstrap, block length 20, 20,000 replicates.
- Paired null: block sign-flip, 20,000 replicates, deterministic seeds.
- Holm family size: three co-primary endpoints.
- Top-10/Top-20 and mean actual rank are exploratory only.

## Integrity gates

- Verify pinned source ledger Git blob SHA and exact 3,354-row count.
- Verify archive Git blob SHA, split counts, unique consecutive indices and strictly increasing dates.
- Verify each cutoff date precedes its target date.
- Verify all six family hit counts are integers in [0,5].
- Verify D2 target t uses exactly rows [t-100, t), not target t or future rows.
- Mutate target/future suffixes and assert earlier selection is unchanged.
- Deterministic replay must reproduce every D2 selection and ledger row.
- No target outcome, canonical archive, active engine, Q60 freeze, B11 freeze or existing prospective record may be rewritten.

## Limitations and governance

This is a historical diagnostic over the already exposed Q141-C0 sample. Its historical Blind OOS is not virgin prospective evidence. The six Q80-derived families are coarse and do not exhaust Q141's typed formula universe. The outcome is per-number Top-5 family coverage, not exact-quintet probability. Holm covers the three registered D2 endpoints, not the entire Q00-Q141 research history.

Research only. No engine promotion, shadow insertion, canonical archive mutation, automatic merge or rebase. PRs #6, #7 and #8 remain untouched.
