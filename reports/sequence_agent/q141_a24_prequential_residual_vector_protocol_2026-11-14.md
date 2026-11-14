# Q141-A24 — Prequential Residual-Vector Forecast Audit

**Protocol timestamp:** 2026-11-14 07:42 Europe/Rome  
**Classification:** retrospective exploratory audit; not confirmatory preregistration  
**Parent:** Q141-A23  
**Scope:** research-only. No winning-number forecast, production promotion, freeze mutation, or canonical archive change.

## Question

Do the full 1,023-dimensional Q7 formula-rank residual vectors exhibit one-step temporal persistence that predicts the next residual vector more accurately than simple prior-window means?

The target is the next *formula-rank residual vector*, not the next winning quintet, a ticket probability, or monetary return.

## Fixed source and representation

- Reuse the exact Q141-A23 source snapshots and calibration, with Git blob SHA checks against the A23 input manifest.
- 138 rows: 118 reference rows plus 20 extension rows, 2026-06-29 through 2026-11-13.
- All 138 rows are Q75-high-state; conclusions are conditional on this selected regime.
- 1,023 formula coordinates; fixed mask-lattice design rank 56; residual rank 967.
- First 400 Q7 scored targets supply the already-frozen per-formula scaler. No scaler is refit on the 138-row evaluation panel.
- The mask basis is deterministic and depends only on the 1,023 formula-mask IDs.

## One-step forecasts

For target row t, use only rows strictly before t:

- Persistence-1: copy residual vector t-1.
- Mean-20: arithmetic mean of residual vectors t-20 through t-1.
- Mean-40: arithmetic mean of residual vectors t-40 through t-1.

Loss is squared Euclidean error divided by the fixed residual rank 967. The first 40 rows are warm-up only.

Chronological scored splits are fixed by row index:
- Discovery: 58 targets.
- Validation: 20 targets.
- Historical Blind OOS exposed: 20 targets.

The final 20 rows have already been visible in A21-A23; the label “Blind OOS exposed” is deliberate and does not imply a virgin holdout.

## Quantitative hypothesis

Primary comparison: Persistence-1 versus Mean-20.

Practical requirement: relative MSE gain must be at least +1% in both Validation and historical Blind OOS.

Inferential requirement: the one-sided block-sign-flip p-value must remain below 0.05 after Holm correction at each of block lengths 5, 10, and 20, using the pooled 40 Validation+Blind rows.

Secondary comparison: Persistence-1 versus Mean-40, included in the same six-test Holm family.

- 20,000 block sign-flip replicates per endpoint and block length.
- 20,000 circular moving-block bootstrap replicates per endpoint and block length for 95% intervals.
- Fixed xorshift32 seeds in the runner.
- No threshold, window, split, or seed tuning after calculation.

The block sign-flip test assumes approximate symmetry and exchangeability of block-level paired loss sums. Bootstrap intervals are descriptive under the chosen moving-block resampling scheme.

## Leakage and reproducibility controls

- Each forecast uses vector indices strictly less than its target index.
- Target and future vectors are mutated in tests; the earlier forecast must remain unchanged.
- Every target row is checked against the A23 ledger and strict-prior cutoff.
- All source Git blob hashes are checked against the A23 input manifest.
- The runner writes report, ledger, validation, checkpoint, and manifest; replay must reproduce all six output files byte-for-byte.
- No historical target row is used to fit its own forecast.

## Interpretation limits

This is an exploratory audit formulated after A23 outcomes and the source panel were already visible. The historical Blind OOS is exposed, the panel is small, and all rows are from one selected high-state regime. A positive result would only indicate temporal predictability of the residual rank-vector representation; it would not establish prediction of lottery numbers or winning probability. A negative result would not prove absence of all possible structure.

## Governance and next action

No production engine, candidate list, canonical archive, Q60 gate, or forecast freeze is modified. PRs #6, #7, and #8 remain untouched. No merge or engine promotion is authorized.

Next action: wait for the official 2026-11-14 draw result, append it only after primary-source verification, then register a new genuinely prospective multivariate test before observing the next target.
