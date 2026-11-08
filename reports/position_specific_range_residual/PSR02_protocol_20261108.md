# SONAR PSR-02 — Position-Specific Prior-Conditioned Odd-Count Residual Lab

**Status:** preregistered experiment, research-only. No motor replacement or promotion.

## Hypothesis
The odd-count composition of the previous sorted draw, binned as 0–1, 2–3, or 4–5 odd numbers, may condition the next draw's marginal position distribution. This is a position-specific adaptation of the FD-09 state definition, not a repeat of its unordered-number inclusion endpoint.

For each position i, candidate n and current state s:
\[
q_{i,t}(n\mid s)=\frac{c_{i,t,s}(n)+\alpha\pi_i(n)}{N_{t,s}+\alpha},\quad \alpha=100,
\]
where (pi_i(n)=\binom{n-1}{i-1}\binom{40-n}{5-i}/\binom{40}{5}) is the exact sorted-position marginal. Alpha is fixed before execution. The global comparator uses the same training target rows, same prior and same alpha without state conditioning.

## Walk-forward protocol
- Canonical archive; 300-draw warmup.
- At target t, train targets j=1..t−1 only; state for j comes from draw j−1. The target state is from draw t−1. Strict cutoff and expanding window.
- Chronological 50% discovery / 25% validation / final 25% blind OOS; no alpha selection on validation.
- Primary endpoint: per-position Brier improvement of state-conditioned distribution vs global empirical shrinkage in final blind OOS.
- Circular moving-block bootstrap, block length 7, 2,000 replicates, fixed seed; one-sided benefit test. Holm correction across five positions.
- Top-1, log-loss and comparisons to exact prior are secondary/descriptive.

## Controls
- Audit archive dates, sorted distinct five-number rows, position domains and target-index cutoff.
- The same target rows and prior are used for state and global comparator.
- Preserve per-target scores; no post-hoc state-bin or alpha tuning.
- Position dependence means marginals are not independently combined into a ticket.
- Historical blind period overlaps prior SONAR explorations; prospective Q60 remains the independent gate.

## Decision
No promotion from this experiment. Preserve null or positive position results; if any blind OOS endpoint is promising, it must be frozen prospectively and evaluated under Q60 before human review.
