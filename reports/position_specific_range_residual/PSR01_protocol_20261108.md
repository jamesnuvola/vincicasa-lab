# SONAR Position-Specific Range & Residual Lab — PSR-01

**Status:** experiment scaffold persisted; execution and validation pending.  
**Branch:** `research/sonar-position-specific-range-residual-20261108`  
**Isolation:** does not modify active motor, canonical main, or PR #6/#7/#8.

## Hypothesis
Treat the ordered draw as five position-conditioned series. For each position (P_i), estimate its admissible historical range using only past draws:
(L_i(t)=\min\{P_i(s):s<t\}\), (U_i(t)=\max\{P_i(s):s<t\}\).
Investigate whether this past-only range, with separate residual/frequency analysis within the range, yields useful signal compared with all-40 and active SONAR baselines.

## PSR-01 implemented
- Expanding-window chronological walk-forward with a configurable initial warmup (default 250 draws).
- Per-target-date, per-position min/max and range width computed exclusively from prior observations.
- Range-escape coverage measured out-of-sample (actual position value outside past min/max).
- Transparent within-range frequency Top-1 candidate, tie-broken toward smaller number; score separately from range coverage.
- Position-wise hit rate, range width, and average within-range uniform probability exported as JSON summary and CSV detail.

## Interpretation and safeguards
- Past min/max are empirical boundaries, not guaranteed bounds. Never truncate future outcomes silently.
- Positions are ordered and dependent. Marginal results are not a valid independent-five ticket model.
- Report every position, including weak or promising results; no cherry-picking.
- Compare against uniform/range baselines and the active motor; apply paired uncertainty and multiple-testing correction before any promotion.
- Keep candidate frozen and use prospective/blind validation; do not merge or replace the current engine based on exploratory metrics.

## Next stages
1. Run PSR-01 against canonical history and verify artifacts byte-for-byte on rerun.
2. Add residual-conditioned and fluid-inspired position dynamics only after establishing PSR-01 baseline.
3. Jointly reconcile five marginals with strict ascending/distinct constraints; assess full-ticket metrics.
4. Preserve promising variants even if they fail promotion thresholds.

## Execution record
No walk-forward result is claimed in this commit. The execution runtime has not yet been connected to this repository branch.
