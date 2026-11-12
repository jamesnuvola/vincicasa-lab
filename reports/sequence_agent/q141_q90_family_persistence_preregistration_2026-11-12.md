# Q141-B7 — Q90 operator-size family persistence

**Status:** preregistered; not yet executed  
**Registration:** 2026-11-12  
**Primary hypothesis:** a Q90 formula family's mean Top-5 hit share over the previous 100 targets predicts its next-target family-average Top-5 hit share, yielding at least +0.005 over an equal-family ensemble on Blind OOS.

## Source and eligibility
- Q90 artifact run `42504717670`, artifact `13627507532`, ZIP SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`.
- Q90 source archive blob `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 draws through 2026-11-07.
- It is an exact prefix of Q141's 3,404-draw eligible archive through 2026-11-10. Contest 315 (2026-11-11) remains excluded.
- Feature matrix: 3,351 × 40 × 59 float32, strictly prior-only. Q90's 20-feature subset was selected on Discovery and is frozen for Validation/Blind.

## Universe and deterministic sample
Full Q90 catalog: 330,429 formulas. Evaluate 700 formulas, exactly 100 from each family:
- linear mean sizes L4, L5, L6, L7, L8;
- pairwise interaction I4;
- conditional gate G4.

Within each family, select the 100 IDs with lexicographically smallest SHA-256 of `Q141-B7|` + formula_id. This sampling does not use outcomes or formula performance.

Scoring must reproduce Q90 exactly:
- linear: mean of selected feature columns;
- interaction: four-feature mean + 0.25 × z-score of the selected feature-pair product across 40 candidates;
- gate: four-feature mean + 0.25 × indicator(gate feature ≥ threshold);
- float64 calculations, score rounded to 12 decimals; ties resolve to lower number ID.

## Walk-forward policy
- 3,351 targets: Discovery 2,011; Validation 670; Blind OOS 670.
- For each target, compute each sampled formula's Top-5 hit share. Family outcome is the mean over its 100 formulas.
- Select the family with the largest mean family outcome over the preceding 100 scored targets. State updates only after the current target is scored. Ties are lexicographic.
- First 100 targets use the equal-family baseline; they become selector history only after scoring.
- Compare rolling selector with (a) equal-family mean and (b) the family selected once on Discovery and frozen for Validation/Blind.
- Primary endpoint: Blind OOS rolling-selector minus equal-family Top-5 hit share. Practical threshold +0.005.

Discovery is descriptive/in-sample because Q90 feature selection used Discovery outcomes. Validation/Blind are chronological holdouts relative to that feature-selection step, but historical Blind OOS is exposed SONAR research history, not virgin prospective evidence.

## Statistical plan
- Paired target-level effects; chronological blocks of 20.
- 20,000 Monte Carlo non-overlapping block sign-flips (one-sided positive alternative).
- 20,000 circular moving-block bootstrap replicates for 95% percentile intervals.
- Seed `14120261112`.
- Holm-Bonferroni across six registered comparisons: rolling vs equal-family and Discovery-static vs equal-family in each split.
- Uniform 5-of-40 reference Top-5 share: 0.125.

No lift is declared unless the primary Blind effect is at least +0.005, its 95% block-bootstrap interval is positive, and Holm-adjusted p < 0.05.

## Acceptance and leakage controls
Verify ZIP and member hashes, feature matrix source/date/cutoff fields, target ledger reconciliation, deterministic 100-per-family sample, exact Q90 score/rank semantics, current-target exclusion, update-after-score order, future-suffix/target-outcome invariance, and all six Holm-adjusted comparisons.

## Limits
This is a 700-formula sample, not all 330,429 Q90 formulas. Family-average hit share is a meta-research diagnostic, not a deployable number ranking or five-number forecast. Discovery is in-sample; historical Blind OOS is exposed. Holm controls this six-test family only, not the full Q00–Q141 research history.

**Governance:** research-only; no merge, engine promotion, shadow insertion or canonical archive mutation; PRs #6/#7/#8 protected.
