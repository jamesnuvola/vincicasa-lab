# Q141-A20 — Drift Quantile-State Capture Audit

Date: 2026-11-14
Status: Research-only; historical exploratory holdouts
Parent: Q141-A19 (research/q141-a19-residual-subspace-drift-20261114)

## Frozen quantitative hypothesis

A rolling, prior-only 75th-percentile threshold of the Q141-A19 residual-subspace drift statistic defines a high/low state. A state-conditional mean of the prior 400 structural-capture responses should improve next-target MSE by at least 0.001 versus the prior-400 unconditional mean in both Validation and historical Blind OOS. Confirmation additionally requires a positive 95% circular block-bootstrap lower bound and Holm-adjusted one-sided block-signflip p-value below 0.05.

## Fixed design

- Source: exact Q141-A19 target ledger, pinned by Git blob SHA-1 5613d5176ed48dd63df186258a53039e65840555.
- Window: 400 previous drift/capture pairs.
- State threshold: empirical lower order statistic at floor((n-1)*0.75).
- Current state: high iff current pre-target drift is greater than or equal to the threshold; otherwise low.
- Prediction: mean capture among prior-window rows in the same state.
- Fallback: prior-400 unconditional mean only if the selected state has fewer than 25 prior rows.
- First 400 Discovery rows are calibration-only.
- Primary comparator: A19 prior-400 rolling mean.
- Secondary comparator: frozen A19 prior-only linear drift OLS prediction.
- Metrics: MSE gain; MAE gain descriptive only.
- Uncertainty: 20,000 circular block-bootstrap replicates, block length 20.
- Tests: 20,000 block-signflip replicates, block length 20.
- Multiplicity: Holm across six one-sided MSE comparisons (three splits times two comparators).

## Temporal contract

For target row t, use only drift and capture from [t-400,t) and current pre-target drift drift[t]. Current capture is response-only. All cutoffs must precede target dates. The implementation includes target-response and future-suffix mutation checks.

## Interpretation guardrails

This experiment predicts a structural capture score derived from formula-rank profiles. It does not predict candidate numbers, an exact five-number ticket, or a probability of winning. Historical Blind OOS has been exposed to earlier SONAR research and is not virgin prospective evidence. The q75 threshold is a single fixed nonlinear diagnostic selected after A19; no q/window tuning is allowed on this panel.

## Decision rule

A20 is confirmed only if both Validation and historical Blind OOS satisfy all three primary conditions. Otherwise retain the result as negative/exploratory and do not promote a model or engine.

## Next action

If not confirmed, do not search additional thresholds on the same historical panel. Freeze a prospective drift-state monitor unchanged or retire this predictor family.
