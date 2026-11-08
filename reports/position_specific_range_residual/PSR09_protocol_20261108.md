# PSR-09 Protocol — Position-wise recency marginal calibration

**Registration state:** protocol committed before PSR-09 computation  
**Experiment ID:** `SONAR_PSR09_POSITION_RECENCY_MARGINALS`  
**Data source:** `data/storico_daily.csv`  
**Pinned Git blob SHA:** `5d2efd70684e918b27d8f06386d545647898336d`  
**Pinned coverage:** 3,401 draws, 2017-07-17 through 2026-11-07

## Quantitative hypothesis

For each sorted draw position (i\in\{1,\ldots,5\}), estimate its marginal law from the last (W) pre-target draws, with an exact uniform 5-of-40 order-statistic prior as Dirichlet pseudo-counts:

\[
q_{i,t,W,\alpha}(n)=\frac{C_{i,t,W}(n)+\alpha\pi_i(n)}{W+\alpha},\quad
\pi_i(n)=\frac{\binom{n-1}{i-1}\binom{40-n}{5-i}}{\binom{40}{5}}.
\]

Here (C_{i,t,W}(n)) counts the value (n) in position (i) among the (W) draws immediately preceding target (t). Unsupported position/value cells have exact prior probability zero and remain zero. All input rows must have date < target date.

**Claim to test:** the selected rolling position marginal improves future multiclass Brier score over (a) the exact order-statistic prior and (b) a cumulative all-prefix position-marginal estimator with the same α.

## Fixed candidate grid and selection

- Window grid (W\in\{30,90,180,365,730\}) draws.
- Prior strength α ∈ {100, 300, 1000}.
- Candidate grid is fixed before computation (15 pairs per position).
- Select (W,α) independently for each position using validation mean Brier improvement against the cumulative all-prefix empirical marginal with the same α.
- Deterministic tie-break: larger α first (more shrinkage), then larger (W).
- Discovery is descriptive only; no hyperparameter selection on discovery or blind OOS.

## Chronological design

Warm-up: first 200 draws. Targets are zero-based archive rows (t=200,\ldots,N-1), with prefix rows strictly before (t). Split the 3,201 targets chronologically:
- Discovery: first 60%, floor = 1,920 targets.
- Validation: next 20%, floor = 640 targets.
- Blind OOS: remaining 641 targets.

The historical blind partition has been inspected in prior SONAR work; it is not an independent or pristine confirmation. This experiment is retrospective/exploratory regardless of its p-values.

## Endpoints and inference

- Primary: per-position blind-OOS mean Brier improvement (exact prior Brier minus candidate Brier), five endpoints.
- Secondary: per-position blind-OOS mean Brier improvement against the cumulative empirical marginal with the same selected α, five endpoints.
- Secondary descriptive metric: log-loss improvement, no promotion decision based on it.
- Inference: circular moving-block bootstrap, block length 7, 2,000 replicates; 95% percentile CI and one-sided centered-null p-value.
- Holm adjustment across the ten (5 primary + 5 secondary) position/comparator endpoints; family-wise α=0.05.
- A positive improvement favors the candidate. All probabilities must normalize; primary baseline is the exact combinatorial prior. No ticket-level or full joint-distribution claim is made.

## Integrity / anti-leakage gates

1. Verify canonical archive blob SHA and row count, unique strictly increasing dates, five distinct ascending integers in 1..40.
2. For every target, feature cutoff is the immediately preceding archive date; all training rows satisfy date < target.
3. Prefix length is (t) rows for zero-based target row (t); no target or later row enters its own forecast.
4. Verify exact order-statistic prior sums to one at each position.
5. Verify all candidate and comparator probability vectors sum to one within (10^{-12}).
6. Replay must reproduce JSON, Markdown and per-position ledger outputs byte-for-byte.
7. No automatic merge, engine promotion, or retrospective modification of shadow freezes.

## Decision and next gate

A historical improvement does not authorize promotion. Prospective promotion remains governed by the existing SONAR Q60 gate: at least 200 complete pre-target paired shadow targets; no missing freezes reconstructed. If PSR-09 is null or non-significant, record the negative evidence and do not append a competing candidate to the live shadow stream without human review.
