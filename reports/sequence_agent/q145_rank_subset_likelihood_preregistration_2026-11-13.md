# Q145 — Rank-to-subset likelihood calibration

**Registration:** 2026-11-13, before the 20:00 target; the separate prospective freeze records its exact timestamp.  
**Status:** research-only; one prospective freeze created for 2026-11-13.  
**Parent:** Q144 branch `research/q144-shadow-rank-ensemble-20261113`, PR #95.  
**Pinned sources:** canonical archive blob `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`; Q144 ledger blob `c14e13b0c8e7f7a8c20ae40c9af56101f5209762`; Q144 freeze blob `df20af45433ae8693b90e06124d31df0ad345dfe`.

## Question and quantitative hypothesis

Q144 evaluated only Top-20 hit counts. Q145 tests whether its frozen rank lists can be converted into a coherent probability distribution over all `C(40,5)=658,008` unordered quintets, and whether that distribution assigns better log score than the uniform 5-of-40 null.

For a ranked list, define fixed utility
`u(r)=(21-r)/20` for ranks 1..20 and `u=0` outside Top20. Fix temperature `T=1` before evaluation and set `w_i=exp(u_i/T)`. The probability of unordered quintet `S` is
`P(S)=product(i in S) w_i / e_5(w_1,...,w_40)`,
where `e_5` is the fifth elementary symmetric polynomial, computed by descending dynamic programming. No temperature fitting, ranking retuning, or outcome-dependent selection is permitted.

Primary endpoint: per-target complete-quintet log-likelihood gain over uniform,
`g_t = log(C(40,5)) + sum(i in draw_t) log(w_i) - log(e_5(w))`.
Positive values favour the rank-derived PMF. Secondary endpoint: Brier-score gain of the 40 exact marginal inclusion probabilities over the uniform marginal 0.125.

Models: Q144 family-balanced Borda Top20; Q144 equal-type-inclusion Top20; frozen APP Top20 where available. Uniform 5-of-40 is the null baseline.

## Historical walk-forward and splits

Use only Q144's already frozen pre-target Top20 lists and verify each actual quintet against the pinned canonical archive. Preserve Q144's chronological split: first 18 targets Discovery, next 6 Validation, final 7 historical Blind OOS. APP is available on 19 targets only (6 Discovery, 6 Validation, 7 Blind OOS).

**Critical limitation:** the Q144 aggregation and this rank-to-PMF transformation are being audited after the historical outcomes existed and after Q144's Top20 results were inspected. Therefore all historical splits, including the seven-date Blind OOS, are exploratory and cannot be treated as virgin confirmation. No model selection is performed on these splits.

## Inference and multiplicity

For descriptive historical Blind OOS only:
- Report mean log-likelihood gain and Brier gain for each model and each chronological split.
- Use the likelihood-ratio e-process against the conditional uniform null, with Ville p-value `min(1, exp(-max(0, max cumulative log-LR)))`. Because the historical transformation is post-hoc, these p-values are diagnostic only, not confirmatory.
- Use exact one-sided sign-flip randomization for paired Borda-minus-inclusion and Borda-minus-APP log-score differences; state its symmetry/exchangeability assumption.
- Use 20,000 circular moving-block bootstrap replicates, block length 2, fixed seeds, for descriptive 95% intervals.
- Apply Holm across the five registered diagnostic p-values (three model-vs-uniform e-processes and two paired sign-flip contrasts).

## Prospective freeze

Before the 2026-11-13 20:00 draw, transform the already frozen Q144 Borda and equal-type-inclusion Top20 lists into two 5-of-40 PMFs and persist:
- all 40 weights and marginal inclusion probabilities;
- `e_5` normalizer, modal quintet and its assigned probability;
- source archive and Q144 freeze hashes;
- a null outcome field, to be reconciled append-only only after the official result is published.

This is a research probability forecast, not a claim that the modal ticket is more likely in reality. Do not alter Q144, the 43 pending component freezes, APP, Q60, B11, the canonical archive, or any protected PR.

## Decision rule

No historical lift claim and no engine promotion. The 2026-11-13 freeze is the first prospective observation for Q145. Continue the fixed algorithm without retuning; accumulate at least 100 consecutive prospective target dates before a confirmatory assessment. If the official result is unavailable or sources conflict, keep the outcome pending and do not score it.
