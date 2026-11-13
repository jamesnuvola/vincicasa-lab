# Q143 — Top20 score-mass calibration

Specification timestamp: 2026-11-13 17:43:03 Europe/Rome  
Base commit: 4a55fb7da216bd3850b79f862bf10b2cbcafa968  
Status: retrospective exploratory experiment; not promotable.

## Hypothesis
The active engine's Top20 score-mass share x_t = sum(score ranks 1..20) / sum(score ranks 1..40) should be positively associated with the next target's Top20 hit count and improve forecasts beyond the uniform expectation 2.5 and a rolling-400 mean.

The practical primary threshold is an MSE reduction of at least 0.01 hit-count-squared per target versus the rolling-400 mean.

## Frozen model
For each evaluated target t, fit ordinary least squares on exactly the previous 400 target records:
prediction = clip[0,5](mean_Y + beta * (x_t - mean_x)).
No hyperparameter is tuned. x_t uses draws strictly before target t; the actual target is used only to form its hit count after the forecast feature is frozen.

## Data and splits
- 3,406 draws, 2017-07-17 through 2026-11-12.
- Scoring warm-up: 200 prior draws; raw records: 3,206.
- Calibration window: 400 prior target records.
- Evaluated records: 2,806, 2019-03-09 through 2026-11-12.
- Chronological split: Discovery 1,683; Validation 561; Blind OOS 562.

Blind OOS is chronological but not a virgin confirmatory sample because the archive and related SONAR research have been inspected in the broader project.

## Baselines and inference
Baselines: uniform Top20 expected hits 2.5 with hypergeometric variance 20*(5/40)*(35/40)*(20/39), and the mean Top20 hits over the previous 400 targets.

Four Blind OOS endpoints: MSE and MAE improvement versus each baseline. Positive favors rolling OLS. Confidence intervals: 20,000 circular moving-block bootstrap replicates, block 20. P-values: 20,000 block sign-flip replicates, block 20. Holm correction across these four endpoints only.

## Leakage and reproducibility
- Exact helpers are extracted from committed src/VinciCasaLab.jsx.
- For each target, only the strict historical prefix is passed to the scorer.
- Rolling regression uses target records ending before the current target.
- Full-history ranking must reproduce the committed active-engine frozen Top20.
- CI compares recomputed report and ledger byte-for-byte.
- Unit tests cover archive parsing, scorer parity, prior-only cutoff, rolling-window isolation, deterministic inference, Holm and the uniform baseline.

## Governance
One exploratory feature/model pair only. Holm is local to Q143 and does not cover all prior SONAR experiments. No engine promotion or forecast rewrite. Existing freezes remain append-only.
