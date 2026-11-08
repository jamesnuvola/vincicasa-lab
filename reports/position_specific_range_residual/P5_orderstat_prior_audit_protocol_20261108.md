# P5 Order-Statistic Prior Audit — 2026-11-08

Purpose: reinterpret the existing P5 pooled/rolling logistic ranker against the correct maximum order-statistic baseline, not a uniform candidate-rank baseline.

Exact P5 marginal under a uniform 5-subset of 1..40:
\[
\pi_5(n)=\binom{n-1}{4}/\binom{40}{5},\quad n=5..40.
\]
Primary fixed prior ranking is descending (pi_5(n)), tie-break lower number. Theoretical Top5 is {36,37,38,39,40}; expected coverage is calculated exactly. The same test dates as the ranker report are evaluated on canonical history. A fixed empirical-frequency baseline uses only dates before test start.

This is a baseline audit, not a re-fit. The ranker report has aggregate rates only; no paired target-level test can be claimed. Preserve this finding and request the Q90 feature matrix/target-level ranks before any new ranker experiment. No engine promotion or merge.
