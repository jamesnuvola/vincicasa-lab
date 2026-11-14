# Q141-A22 — Conditional response-shift audit protocol

## Purpose

Audit the Q141-A21 observation that all 20 appended targets were classified as Q75 high state. Determine whether this is a new state transition or continuation of the preceding high-state run, and whether the formula-profile capture response changed while the state remained high.

This is an exploratory post-extension audit. The A21 responses were visible before A22 was formulated. It is not a confirmatory preregistration and cannot establish prospective prediction.

## Pinned sources

- A20 ledger: reports/sequence_agent/q141_a20_drift_quantile_state_2026-11-14_target_ledger.csv (1,786 rows, targets 1,601–3,386).
- A21 extension: reports/sequence_agent/q141_a21_q7_source_extension_2026-11-14_extension_target_ledger.csv (20 rows, targets 3,387–3,406).
- All rows must retain strict-prior cutoffs and their original target order.
- A21 prospective freeze for 2026-11-14 is not an input response and must remain unchanged.

## Quantitative diagnostics

1. State persistence: observed statistic is 20 high states in the 20 appended targets. Compare with stationary-bootstrap samples of length 20 from (a) all A20 states and (b) the A20 historical Blind OOS state sequence. Expected block lengths: 20, 50, 100, 200.
2. Conditional capture response: compare the A21 20-target mean capture response with stationary-bootstrap samples of length 20 from the immediately preceding terminal A20 high-state run. Expected block lengths: 5, 10, 20, 40.
3. Q75 forecast error: report the 20-target mean MSE gain versus prior-400 mean and a circular moving-block-5 bootstrap interval.

Use 20,000 deterministic stationary-bootstrap replicates per diagnostic, with plus-one Monte Carlo p-values. Apply one joint Holm correction across all 12 state-persistence and conditional-capture block-length tests.

## Interpretation rules

- A high-state run that continues the prior terminal run is not a new state transition.
- Do not infer a regime change from the 20/20 state count unless the dependence-preserving null survives the joint Holm family.
- A conditional response drop is exploratory even if a raw bootstrap tail is small; the audit is post hoc and the scalar capture series does not preserve the complete 1,023-formula cross-sectional vector.
- Structural capture is not candidate-number accuracy or a win probability.
- No model promotion, forecast rewrite, archive mutation, or freeze modification is allowed.

## Next action

Keep the A21 2026-11-14 freeze immutable. After the official target result is ingested, append-only evaluate that freeze and continue the prospective monitor without retuning the Q75 threshold or 400-target window.
