# Q141-D5 — Formula-level Behavioural Diversity

**Registration:** 2026-11-13, before full D5 execution. Research-only; no engine promotion, freeze mutation, archive mutation or merge. PRs #6, #7 and #8 remain protected.

## Hypothesis
A fixed, outcome-independent sample of 700 Q90 formulas (100 each from L4, L5, L6, L7, L8, I4 and G4) produces four current-target, prior-only behavioural features: normalized entropy of 3,500 Top-5 votes over 40 numbers; unique Top-5 signature share; mean pairwise Top-5 intersection divided by five, computed as sum_i C(v_i,2)/(C(700,2)*5); and fifth-versus-sixth vote margin divided by 700.

These features are hypothesized to reduce next-target Q7 meta-quality MAE by at least +0.005 beyond the frozen Q141-C5 Q7+Q80+Q90 M2 baseline. The target is mean percentile across 1,023 quintet-scoring formulas, not a winning-number forecast.

## Frozen sample and scoring
Q90 artifact 13627507532, ZIP SHA-256 12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077; matrix 3,351×40×59, SHA-256 681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49; catalogue 330,429 formulas, SHA-256 a61f77ede7136d4eb88a57932488590741fd0b84ace8307d5dd90c192d520586. Sample is the lowest SHA-256 of Q141-B7| + formula ID within each family; expected ordered ID digest 3ee52f0f270eafb6a8c54c7a7166fe55f2c7730a59ae700ea50b92be6a5412ae. Linear score is selected-feature mean; I4 adds 0.25 times candidate-wise z-score of the selected feature-pair product; G4 adds 0.25 times the registered gate indicator. Round to 12 decimals; ties by lower number. Q90's 20 selected features are inherited from its Discovery selection over 59 available features.

## Sources and alignment
Q7 ledger: 3,286 targets, archive through 2026-10-24. Q90 family ledger: 3,351 targets, archive through 2026-11-07. C5 ledger: 3,186 persisted M2 predictions. Join on prior_draws, target date, cutoff, actual quintet and split. Recompute all seven Q90 family Top-5 shares for all 3,286 common targets and require max error ≤1e-12. Verify every C5 baseline row against Q7 outcomes and source report; recompute C5 M2 split MAE/RMSE/mean error to 1e-12.

## Walk-forward
D5 residual learner uses ridge alpha 1 on Q7 mean percentile minus C5 M2 prediction, with the four D5 features. Offsets 100–149 are residual warm-up. Score offsets 150–1971 (Discovery 1,822), 1972–2628 (Validation 657), 2629–3285 (Blind OOS 657). Discovery fits expand using offsets 100..t−1 only; coefficients freeze after Discovery using offsets 100–1971 (1,872 rows). Standardization uses training rows only. Residual corrections are not clipped; only baseline plus correction is clipped to [0,1]. Current target is scored before its outcome can enter a later fit.

## Primary inference
Blind OOS mean abs_error(C5 M2) minus abs_error(D5 M3), positive favours D5. Practical threshold +0.005. 95% circular moving-block bootstrap, block 20, 20,000 replicates, seed 14120261114; one-sided chronological block sign-flip, block 20, 20,000 replicates, seed 14120261115. Support requires point estimate ≥0.005, lower CI >0 and p<0.05. One confirmatory endpoint; no within-experiment multiplicity correction required. Global Q00–Q141 multiplicity is not covered.

## Controls and limits
Verify source Git blob SHA, Q90 ZIP/matrix/catalogue SHA, sample digest, strict-prior date/cutoff/actual alignment, Q90 family share replay, C5 baseline report replay, future-suffix invariance and two byte-identical full runs. Historical Blind OOS has prior SONAR exposure and is not virgin prospective evidence. 700 formulas are a fixed sample, not all 330,429; Q7 meta-quality is not winning-number prediction.

**Decision:** if D5 fails, archive and stop adding formula-diversity meta-features. If it passes, require a new prospective replication without historical retuning; no automatic promotion.
