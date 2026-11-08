# FD-09 preregistration — odd-count-conditioned frequency

**Registered before computation:** 2026-11-08  
**Archive cutoff:** 2026-11-07 (3,401 draws; Git blob SHA `5d2efd70684e918b27d8f06386d545647898336d`)  
**Status:** preregistered; outcomes not yet computed.

## Hypothesis

The parity composition of the immediately previous draw, summarized by its odd-number count, may condition the inclusion frequency of each number in the next draw. This is distinct from FD-08's previous-draw sum-state conditioning and FD-07's individual-number lag-1 recurrence bonus.

For target draw t and candidate n, let state s(t) be:
- state 0: previous draw has 0 or 1 odd numbers;
- state 1: previous draw has 2 or 3 odd numbers;
- state 2: previous draw has 4 or 5 odd numbers.

Using only historical target rows j<t, with the condition state derived from draw j-1, score:
[
S_{n,t}(\alpha)=\frac{C_{n,s(t),t}+\alpha F_{n,t}}{E_{s(t),t}+\alpha}
]
where C is the count of n in historical draws whose preceding draw state is s(t), E is that state's exposure in historical target rows, and F is the unconditional historical per-draw frequency of n. If E+alpha=0, use F. Candidate ranking sorts descending score, ties by ascending n. Scores sum to 5 and are interpreted as per-number inclusion probabilities for Brier/log-loss.

## Registered grid and selection

- State partition: fixed 3 bins above; no outcome-derived tuning.
- alpha: {0, 25, 50, 100, 200, 500, 1000}; 21 models.
- Minimum history: 300 draws.
- Discovery targets: indices 300–1699 (1,400 targets).
- Validation: indices 1700–2549 (850 targets).
- Blind retrospective OOS: indices 2550–3400 (851 targets).
- Primary endpoint: Top-5 hit-share = total actual numbers in forecast Top 5 / (5 × targets).
- Selection: maximize validation Top-5 hit count; tie-break lower validation Brier, then larger alpha. Blind OOS is evaluation only and cannot select the model.

## Statistical family and controls

- Primary null: uniform random Top-5 selection with overlap distribution Hypergeometric(N=40,K=5,n=5), aggregated exactly across 851 targets by convolution.
- Correct Holm family: 22 exact-uniform p-values (21 registered conditional models plus the unconditional historical-frequency baseline).
- Paired comparator: unconditional historical-frequency Top-5 on the same targets. Use non-overlapping blocks of 7 targets; omit any incomplete tail block; two-sided deterministic Monte Carlo sign-flip with 20,000 replicates; Holm over 22 paired configurations (21 models plus baseline placeholder).
- Selected-model uncertainty: circular moving-block bootstrap length 7, 10,000 replicates, 95% percentile interval for paired Top-5 hit-share difference.
- Report Top-10/Top-20 hit-share, mean rank, Brier and log-loss as secondary descriptive endpoints.
- No engine promotion, PR, merge, or modifications to PR #6/#7/#8. This is retrospective exploratory evidence; prospective append-only Q60 remains separate.

## Leakage/reproducibility audit

For every target t, use only draw rows with indices <t. Conditional training row j is allowed only for 1≤j<t and uses state of draw j-1. Score target t before adding its actual numbers to global or conditional counts. Splits are fixed by target index. The archive structure and SHA must be revalidated. Code, JSON, report and target ledger will be persisted and read back byte-for-byte; native Node and CI status will be stated only if actually run.
