# Q141-A15 — Formula Behaviour Redundancy

**Protocol status: retrospective methodology note; not a tamper-evident preregistration.** The panel extraction was complete and the first analysis computation had occurred before this document was committed. All inferential results therefore remain exploratory.

## Question and quantitative hypothesis

Do the 1,023 Q7 finite-grammar formula masks contain many redundant rank-behaviour trajectories, and does equal weighting of behaviour clusters improve the next-target rank statistic relative to equal weighting of formulas?

The sample is fixed at 128 masks, selected deterministically within feature-count strata k=1..10 with quotas 5,10,16,23,22,22,17,10,2,1. The selection is evenly spaced within each stratum and is not outcome-selected.

For target t and formula f, normalize the actual quintet rank as r[f,t]=(rank[f,t]-1)/(658008-1). The uniform expected mean is 0.5. Remove common target difficulty by subtracting the median r across the 128 sampled formulas for each target. Estimate Spearman correlations of these residual series using Discovery only (target indices 1–2031).

Build deterministic complete-linkage clusters, merging only when the minimum cross-cluster Spearman correlation is at least 0.90. Freeze the resulting clusters before Validation (2032–2708) and historical Blind OOS (2709–3386). Within a cluster, formulas are equally weighted; clusters receive equal weight.

## Endpoints and thresholds

- Primary Blind OOS endpoint: equal-formula mean rank percentile minus cluster-balanced mean rank percentile. Positive favours cluster balancing. Practical threshold: +0.002.
- Secondary Blind OOS endpoint: 0.5 minus cluster-balanced mean rank percentile. Positive beats the uniform expected mean rank.
- Interpretation requires at least 30% compression (no more than 90 clusters from 128), positive lower 95% block-bootstrap bounds, and Holm-adjusted p<0.05 for both endpoints.
- Inference: 20,000 circular moving-block bootstrap replicates, block length 20; 20,000 block sign-flip replicates; Newey–West lag-20 sensitivity; Holm across the two endpoints.
- Top20/Top100 formula-vote shares are descriptive only, not separate confirmatory endpoints.

## Data and guardrails

Source: Q7 finite-grammar branch research/exhaustive-formula-catalog-20261025, head 7a37cab601c5f9386131a00246963f8e4aeabf74; 3,387 draws through 2026-10-24, 3,386 scored strict-prior targets, 1,023 masks and 658,008 possible quintets. The 128-mask sample and panel are pinned in the A15 branch. Each target date, immediately preceding cutoff, actual quintet and rank vector were reconciled to the pinned Q7 archive before panel persistence.

No validation or blind outcomes are used to construct clusters. No per-formula p-value search is performed; Holm covers only the two aggregate A15 endpoints, not the wider Q7/SONAR research family. The historical Blind OOS has already been exposed to earlier SONAR research and is not virgin prospective evidence. A15 measures rank-behaviour redundancy, not calibrated ticket probabilities or a promoted predictor.

## Decision rule

A15 is a research-only diagnostic. Even if thresholds were met, it would not authorize engine promotion. A negative result returns the lab to semantic AST equivalence and complementary-formula mapping rather than further tuning this cluster selector.
