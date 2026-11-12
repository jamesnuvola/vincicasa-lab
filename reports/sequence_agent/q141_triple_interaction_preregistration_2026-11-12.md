# Q141-B5 — Exhaustive three-way interaction walk-forward

**Registration date:** 2026-11-12  
**Status:** Preregistered before execution  
**Source:** `data/storico_daily.csv`, Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`  
**Eligible prefix:** 3,404 draws through 2026-11-10; contest 315 / 2026-11-11 excluded.

## Quantitative hypothesis

Across all 2,300 unordered triples from the 25 canonical Q80 features, adding a fixed standardized pure three-way product to the matched additive score increases the mean next-target Top-5 hit share.

For candidate number n and triple (i,j,k):

- Additive control: (A_{ijk,t}(n)=z_{i,t}(n)+z_{j,t}(n)+z_{k,t}(n))
- Three-way interaction: (T_{ijk,t}(n)=A_{ijk,t}(n)+Z_{40}(z_i z_j z_k))

The product term is standardized across the 40 candidate numbers using only features available before target t. If its population standard deviation is below (10^{-12}), the interaction term is zero. Coefficient is fixed at 1; no tuning.

## Universe and evaluation

- 25 canonical features; exact alias pairs already collapsed by Q141-B1.
- (C(25,3)=2,300) triples, fully enumerated without sampling.
- 2,300 additive controls + 2,300 interaction formulas = 4,600 formula variants.
- 3,354 strict-prior targets, split chronologically: Discovery 2,013; Validation 671; historical Blind OOS 670.
- Every target is scored before updating occurrence and pair state with its outcome.
- Target outcomes are used only to score rankings already computed from the prior prefix.

## Endpoints and inference

Primary: target-level mean Top-5 hit-share delta (interaction minus additive). Practical threshold: +0.005.

Secondary: Top-10 and Top-20 deltas. Uniform expectations: 0.125, 0.25 and 0.5 for Top-5/10/20 hit share.

Thirteen registered tests: nine interaction-vs-additive endpoint/split tests and four Validation/Blind Top-5 uniform controls. Use one-sided chronological block sign-flip (block length 20, 20,000 replicates), circular moving-block bootstrap CIs (20,000 replicates), and Holm-Bonferroni across all 13 tests. Seed: 14120261115.

No triple-specific p-values, no post-hoc triple selection, and no oracle scoring. Historical Blind OOS is exposed research history, not virgin prospective evidence. Holm controls this registered batch only, not the full Q00–Q141 research history.

## Decision and governance

A lift requires a positive Blind OOS Top-5 delta above +0.005, Holm-adjusted p below 0.05, and directionally positive Validation. No result can authorize engine promotion. Research-only; no archive mutation, shadow insertion, auto-promotion or auto-merge. PRs #6, #7 and #8 remain untouched.

## Next step after this batch

Import Q90 interaction/gate ASTs and Q7 candidate-quintet ASTs as separate typed output families, then reconcile archive and feature lineage before pooled behaviour analysis.
