# Q141-C6 — Prior-only selector-transition state

Status: preregistered before execution  
Date: 2026-11-12  
Branch: research/q141-formula-universe-behaviour-mapping-20261112

## Quantitative hypothesis

The occupancy entropy and switch rate of the preceding 50 fully active selector labels from Q80 and Q90 may contain incremental information about the next target's Q7 formula-universe meta-quality beyond the existing Q7+Q80+Q90 rolling-state model.

This is a meta-quality endpoint, not a direct prediction of the winning quintet or five winning numbers.

## Pinned sources

- Q7: 1,023 quintet-score formulas; 3,286 targets; archive through 2026-10-24; blob 7dab05ba49ace909fe8783eef729605049c65e50.
- Q80/C0: six per-number families; 3,354 targets; archive through 2026-11-10; blob fcb453ed06c8002314f826dbac79d6935f9ac103.
- Q90/B7: seven families; fixed sample 700/330,429 formulas; 3,351 targets; archive through 2026-11-07; blob 5d2efd70684e918b27d8f06386d545647898336d; artifact SHA-256 12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077.

Q7 defines the chronological target split. Every source join must match target date, cutoff date, actual quintet and prior-draw index. Contest 315 and all rows beyond Q7's pinned prefix remain excluded.

## Transition features

For each target, use only the 50 preceding Q80/Q90 target-ledger rows. Read selected_family, not oracle_best_family_descriptive_only. The latter is target-outcome hindsight and is prohibited.

For each source separately:
- switch rate = adjacent family-label changes / 49;
- occupancy entropy = Shannon entropy over the 50 labels divided by ln(K), where K is the fixed family count (6 or 7).

The first Q7 row with 50 fully active selector labels in both sources occurs at target offset 100. To avoid partial warm-up windows, model training begins at offset 100 and the first scored Discovery prediction is offset 150 (50 training rows). Warm-up labels are rejected, not imputed.

## Models and walk-forward

- M2: the fixed nine rolling-state predictors from Q141-C5 (Q7 + Q80 + Q90).
- M3: M2 plus four transition predictors (Q80 switch rate/entropy; Q90 switch rate/entropy).
- Ridge alpha 1.0; standardization fitted on training rows only.
- Discovery predictions are expanding-prequential from offset 150 through 1,971.
- Final Discovery coefficients are frozen for Validation and Blind OOS. Rolling predictors use only the previous 50 rows; target scoring precedes state advancement.
- Expected scored rows: Discovery 1,822; Validation 657; Blind OOS 657.

## Confirmatory endpoint

Blind OOS MAE(M2) - MAE(M3); positive values favour transition state. Practical threshold +0.005. One-sided non-overlapping block sign-flip test and circular moving-block 95% interval, block length 20, 20,000 deterministic replicates. This is one confirmatory endpoint; all other comparisons/correlations are descriptive.

## Governance and limitations

Q90 remains a fixed 700-formula sample from 330,429 and its feature subset was selected within its own Discovery process. Q80/Q90 selector labels are prior-only, but the historical Blind OOS has prior SONAR exposure and is not virgin prospective evidence. No tuning, no oracle labels, no holdout refit, no merge, no engine promotion, no shadow insertion, no canonical archive mutation. PRs #6/#7/#8 remain outside this work.
