# Q141-C4 — Cross-granularity transfer: Q80 per-number behaviour to Q7 quintet-rank quality

**Status:** preregistered; execution pending  
**Registration:** 2026-11-12 21:39 Europe/Rome  
**Branch:** \`research/q141-formula-universe-behaviour-mapping-20261112\`  
**PR:** #89 (draft; no merge)

## Hypothesis

Prior-only rolling behaviour of the six Q80 per-number formula families contains information about the next target's Q7 whole-quintet formula-universe rank quality beyond Q7's own rolling rank-quality baseline.

This is a cross-granularity *meta-forecast*: the outcome is the mean percentile rank of the realized quintet across 1,023 Q7 formulas. It is not a direct prediction of the five winning numbers and is not a lottery-hit forecast.

## Pinned evidence

- Q141 archive: Git blob \`fcb453ed06c8002314f826dbac79d6935f9ac103\`, 3,404 eligible draws through 2026-11-10.
- Q80 C0 behaviour ledger: 3,354 strict-prior target rows, source archive Q141.
- Q7 archive: Git blob \`7dab05ba49ace909fe8783eef729605049c65e50\`, 3,387 draws through 2026-10-24; verified exact prefix of Q141.
- Q7 universe: 1,023 quintet-scoring formulas over 658,008 candidate quintets; 3,286 target rows.
- Contest 315 and the 18 Q141 rows beyond the Q7 source prefix remain excluded.

The two ledgers must match on target date, cutoff date, actual quintet and split; Q7 \`prior_draws\` must equal Q80 C0 \`target_index\`.

## Predictors

Use the previous 50 target rows only:
1. Q7 own-granularity baseline: rolling mean of Q7 \`mean_percentile_all\`.
2. Q80 equal-family rolling mean of Top-5 number hits.
3. Dispersion across the six Q80 family-specific rolling mean Top-5 hit counts.
4. Normalized Shannon entropy of the six rolling family means.
5. Difference between the most recent 25 and preceding 25 Q80 equal-family Top-5 hit counts.

The six Q80 families are frequency change, frequency level, lag memory, neighbour field, position dependence and recency gap. No oracle-best-family field is permitted as a predictor.

## Models

- **Q7-only Ridge:** Q7 rolling-50 mean percentile only.
- **Cross-granularity Ridge:** Q7 rolling-50 mean percentile plus the four Q80 state features.

Both use a fixed Ridge alpha of 1.0, an unpenalized intercept, training-only feature standardization and [0,1] prediction clipping. No tuning or feature selection is permitted.

## Walk-forward

Original chronological splits are Discovery 1,972, Validation 657 and Blind OOS 657. The first 50 Q7 target rows provide the Q7 rolling-feature warmup. The first 100 Discovery rows are reserved to establish at least 50 prior training observations.

- Discovery offsets 100–1,971: expanding prequential fits; every target is predicted using only earlier Discovery outcomes.
- End of Discovery: fit final model coefficients on Discovery offsets 50–1,971.
- Validation and Blind OOS: coefficients remain frozen; rolling features may update only with outcomes strictly earlier than each target.
- Expected evaluated counts: Discovery 1,872; Validation 657; Blind OOS 657.

The target's Q7 score is revealed only after its prediction and can enter later rolling state, never its own predictors.

## Confirmatory endpoint and inference

Primary endpoint: Blind OOS MAE improvement of cross-granularity Ridge over Q7-only Ridge:

\[
\Delta_{\mathrm{MAE}}=\mathrm{MAE}_{Q7-only}-\mathrm{MAE}_{cross}
\]

Positive values favour cross-granularity transfer. Practical threshold: +0.005 percentile units.

Use a one-sided block sign-flip test on paired absolute-error improvement, block length 20, 20,000 replicates, plus a 95% circular moving-block bootstrap interval with 20,000 replicates. Only one confirmatory endpoint is registered; RMSE, bias, correlation and comparison with the 0.5 random reference are descriptive, without confirmatory p-values.

## Acceptance and limitations

Flag for independent prospective shadow replication only if Blind OOS MAE improvement is at least 0.005 and p<0.05. This historical Blind OOS has been exposed by prior SONAR work and is not virgin evidence. The experiment forecasts the rank quality of a fixed formula universe, not the next quintet itself.

No engine promotion, no forecast selection, no shadow insertion, no canonical archive mutation, no merge. PRs #6, #7 and #8 remain protected and untouched.

## Next action

If the transfer hypothesis is not supported, retain the null result and proceed to a descriptive cross-granularity behaviour atlas; do not tune the model on this Blind OOS segment.
