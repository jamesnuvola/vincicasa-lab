# Q60-H99 — ranking quality across all five drawn numbers

**Status:** exploratory, not confirmatory.  
**Prepared:** 2026-11-10 10:47 Europe/Rome.  
**Branch:** `research/q60-nov09-reconciliation-20261110-run11` (PR #36).

## Question and definitions

H99 asks whether the positional engine ranks the five drawn numbers higher *within its Top20*, compared with `freq_100`, without changing either frozen list.

For each target and each engine, define:

\[
MRR5@20=\frac{1}{5}\sum_{n\in A_t}\frac{\mathbf 1(r(n)\le20)}{r(n)}
\]

\[
DHG5@20=\frac{1}{5}\sum_{n\in A_t}\frac{\mathbf 1(r(n)\le20)}{\log_2(r(n)+1)}
\]

A missing winning number contributes zero. These are ranking-quality diagnostics over all five outcomes, not conditional-on-hit metrics.

## Source and strict-prior audit

Replayed directly from the branch's frozen global and positional CSV ledgers and canonical archive. Input blob SHAs:

- global ledger: `ffd9ab70fb27897d0dd3126391ca931b60ba25ac`
- positional ledger: `3b2fe6055d2075308fba742022dd6e527f634770`
- canonical archive: `8d3e19f0b417024ba32e576697eac0648d12ab86`

The 22 matched targets run from **2026-10-19 through 2026-11-09**. For every pair, both history cutoffs equal the previous calendar day and both freeze timestamps precede the nominal 19:00 Europe/Rome draw time. No missing freeze was reconstructed.

## Measured results (22 pairs)

| Metric | Global | Positional | Difference P−G |
|---|---:|---:|---:|
| Top5 hits per target | 0.7273 | 0.9545 | 0.2273 |
| Top10 hits per target | 1.2727 | 1.4545 | 0.1818 |
| Top20 hits per target | 2.5455 | 2.5455 | 0 |
| MRR5@20 | 0.100276 | 0.104427 | 0.004151 |
| DHG5@20 | 0.186497 | 0.191337 | 0.004840 |

Exact two-sided paired sign-flip tests over all (2^{22}=4,194,304) sign assignments:

- MRR5@20: p = **0.396014**; 95% circular moving-block bootstrap interval for the mean difference = [-0.004142, 0.011621].
- DHG5@20: p = **0.676882**; 95% interval = [-0.015141, 0.025010].

Bootstrap: 10,000 circular moving-block replicates, block length 3, seed 9901. These estimates are exploratory because H99 was formulated after inspecting the same cohort.

## Multiple testing and interpretation

Applied Holm to the six inspected secondary endpoints: H97 Top5/Top10/Top20, H98 shared-winner rank displacement, H99 MRR5@20 and H99 DHG5@20. Adjusted p-values are recorded in the JSON report. None approaches 0.05. This is not confirmatory evidence for a positional ranking advantage.

## Future confirmatory protocol

For the next **178 genuinely new paired freezes** after H99 registration:

1. Keep `freq_100` and `position_seed_mix_top20_v1` unchanged; never retune on outcomes.
2. Require previous-day history cutoff and timestamp before nominal draw time.
3. Evaluate MRR5@20 and DHG5@20 as secondary endpoints, paired by target; retain Q60 Top20 5-of-5 as the primary promotion endpoint.
4. Use exact/Monte Carlo paired sign-flip inference and circular moving-block bootstrap (block 20, 10,000 replicates, fixed seed recorded before collection).
5. Apply Holm across the registered H97/H98/H99 secondary family. No promotion without 200 paired targets and human review.

## Limits and next action

This 22-pair replay is not a historical discovery/validation/blind-OOS split. H99 was post-hoc on the same 22 outcomes, so it is descriptive only. Official `main` Q60 remains **21/200**; PR #36 branch has the 22/200 reconciliation. Continue append-only prospective collection; do not reconstruct the absent 2026-11-10 freeze.
