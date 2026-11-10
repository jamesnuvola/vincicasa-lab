# Q87 — Node/graph phase lag

Data: 10 November 2026. Status: **PREREGISTERED_PENDING_EXECUTION**.

## Hypothesis

Q85 used scalar RMS acceleration; Q86 preserved the signed instantaneous direction of velocity versus acceleration. Q87 tests a different missing dimension: whether changes in the per-number node field tend to precede or follow changes in the corresponding row of the pair-residual graph.

For each of the 40 numbers, construct two causal time series from the six-feature node field and the 40×40 pair graph:

- node transition magnitude: Euclidean norm of the six-dimensional node velocity;
- graph-row transition magnitude: Euclidean norm of the corresponding 40-dimensional graph-row velocity.

Over the last **80 prior field transitions**, compute Pearson cross-correlations at lags 1, 2 and 3. Positive lag means node activity leads graph activity; negative lag means graph activity leads node activity. Require at least 30 paired observations; zero-variance series return neutral correlation 0.

## Four frozen operators

All use fixed alpha 0.20; no tuning on Validation or Blind OOS.

1. `NODE_LEADS_GRAPH`: forward-lag correlation × per-number reversion signal.
2. `GRAPH_LEADS_NODE`: backward-lag correlation × per-number graph signal.
3. `PHASE_ASYMMETRY`: forward minus backward correlation × the mean node/graph signal.
4. `BIDIRECTIONAL_PHASE_COHERENCE`: mean forward/backward correlation × the mean node/graph signal.

## Walk-forward and inference

- Frozen archive: 3,402 draws through 2026-11-08; 3,202 targets with at least 200 prior draws.
- Chronological splits: Discovery 1,921; Validation 640; historical Blind OOS 641.
- Compare the four new operators with all eight Q86-DIR models (12 total).
- Exact-null family: 12 models × 3 splits × 3 endpoints = 108 tests, global Holm.
- Paired family: Validation and historical Blind OOS × four registered comparators × Top5/Top10/Top20/mean actual rank = 32 tests, moving-block bootstrap (block 20, 2,000 replicates), Holm.
- Select one Q87 operator on Discovery only. Freeze before Validation and historical Blind OOS.

## Leakage and interpretation safeguards

For target index i, the current node and graph states are functions of draws strictly before i. The current velocity is the difference between two such prior-only states. Lagged correlations use only transition records ending at the current pre-target state. The actual target quintet is read only after the 12 rankings have been constructed.

This is a test of lagged transition magnitudes, not a physical fluid model. Historical Blind OOS is already exposed to earlier SONAR research and remains exploratory. Acceptance validates reproducibility and leakage controls, not predictive efficacy. No promotion, freeze change, shadow insertion or automatic merge is permitted.
