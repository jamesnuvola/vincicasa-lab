# Q141-B4 — Pairwise multiplicative interaction grammar

**Status:** preregistered before execution  
**Registration date:** 2026-11-12  
**Source archive:** \`fcb453ed06c8002314f826dbac79d6935f9ac103\`  
**Eligible prefix:** 3,404 draws through 2026-11-10; contest 315 excluded.

## Hypothesis

Across the complete 300-pair grammar formed from the 25 canonical Q80 features, adding a fixed, cross-sectionally standardized multiplicative interaction to each additive two-feature score increases mean next-target Top-5 hit share relative to its matched additive control.

This is an operator-family test, not a search for the best pair. All 300 pairs are included with equal weight; no pair is selected after observing outcomes.

## Formula definitions

For each target \(t\), candidate number \(n\), and canonical feature \(i\), let \(z_{i,t}(n)\) be the cross-sectional z-score over the 40 candidate numbers, computed from information available strictly before target \(t\).

For every unordered pair \(i<j\), compare:

- Matched additive control: \(A_{ij,t}(n)=z_{i,t}(n)+z_{j,t}(n)\)
- Interaction-enhanced formula: \(I_{ij,t}(n)=z_{i,t}(n)+z_{j,t}(n)+Z_{40}(z_{i,t}(n)z_{j,t}(n))\)

\(Z_{40}\) standardizes the product across the 40 candidates for that target, using population standard deviation; a near-constant product is set to zero. The interaction coefficient is fixed at 1.0. No coefficient fitting, threshold tuning, feature screening or pair selection is permitted.

The grammar contains all \(\binom{25}{2}=300\) unordered feature pairs, with 300 additive controls and 300 interaction-enhanced formulas. The 25 canonical inputs collapse the exact aliases \`recent_5=freq_5\` and \`recent_10=freq_10\`.

## Walk-forward

- 3,404 eligible source draws; 3,354 targets after 50 prior draws.
- Discovery 2,013; Validation 671; historical Blind OOS 670.
- For each target, build features and all 600 scores from the strict prior prefix.
- Score the target outcome only after rankings are fixed; append it to state only after scoring.
- Rank ties are resolved by ascending number, matching the registered Q141 ranker.
- The 2026-11-11 / contest 315 row remains quarantined.

## Endpoints and inference

Primary: chronological mean target-level Top-5 hit-share delta, interaction-enhanced minus matched additive, separately in each split.

Secondary: analogous Top-10 and Top-20 deltas in each split.

Controls: additive and interaction family Top-5 hit share against the exact uniform expectation 0.125 in Validation and Blind OOS.

The complete registered family contains 13 one-sided tests: nine interaction-minus-additive tests (three endpoints × three splits) and four Top-5 uniform controls (two models × two holdouts). Holm-Bonferroni is applied across all 13. Use 20,000 block sign-flips and 20,000 circular moving-block bootstrap replicates, block length 20, seed 14120261114.

No pair-level p-values or best-pair selection will be reported. Pair-of-family-group summaries are descriptive only.

## Decision and limitations

A historical lift requires a positive Blind OOS primary delta greater than +0.005, Holm-adjusted p below 0.05, and a directionally positive Validation result. Even a pass is exploratory because this historical blind tail has prior SONAR research exposure.

This is only the pairwise interaction operator over Q80's 25 canonical features. It does not include Q89's 32 extension features, Q90 gates, Q7 candidate-quintet ASTs or Q92 output types. A null result is valid evidence and must be retained. No engine promotion, shadow insertion, canonical archive edit or automatic merge is permitted.
