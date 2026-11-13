# Q141-D3 — Effective feature-rank state and formula-family behaviour

**Registration:** 2026-11-13 12:50 UTC  
**Status at registration:** preregistered; outcomes not yet analysed  
**Research-only:** no forecast, engine change, shadow insertion or promotion.

## 1. Question and quantitative hypothesis

Does the pre-target effective dimensionality of the 59-feature candidate matrix identify states in which nonlinear formula families (pairwise interactions and conditional gates) add more Top-5 ranking information than linear-mean formulas?

For target t, let X_t be the 40 x 59 Q90/Q89 feature matrix available at the target cutoff. Center each column across the 40 candidate numbers, form the population covariance C_t, and calculate the effective rank

r_t = trace(C_t)^2 / trace(C_t C_t).

Normalize by 39, the maximum possible centered rank with 40 candidates:

R_t = r_t / 39.

The state indicator is strictly prequential. For t >= 100, H_t = 1 if R_t exceeds the median of R_{t-100},...,R_{t-1}; otherwise H_t = 0. No target outcome or current/future outcome enters H_t.

For each target, define the nonlinear-family advantage:

D_t = 0.5 * (interaction_top5_t + gate_top5_t) - linear_top5_t.

Primary hypothesis: the mean D_t in high-effective-rank states exceeds the mean D_t in low-effective-rank states by at least **+0.005** (0.5 percentage points) in the historical Blind OOS split.

The direction is fixed: high effective rank should favour interactions/gates relative to linear means. No sign reversal or alternative threshold will be selected after seeing results.

## 2. Source and alignment

- Feature source: Q90 pinned source artifact 13627507532, ZIP SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`.
- Matrix member: `adaptive_novelty_feature_matrix.npz`, shape 3,351 x 40 x 59, float32; source archive blob `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 draws through 2026-11-07.
- Outcomes and family aggregates: Q141-A6 target ledger, artifact 13997032604, ZIP SHA-256 `e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc`.
- Q90 and A6 target rows must match exactly by target date, cutoff date and actual quintet. No row may be reordered or silently dropped.
- The Q90 source is an exact prefix of the then-current Q141 archive; later suffix draws are excluded. This experiment is pinned to the source snapshot above and does not claim current-main coverage.

## 3. Walk-forward splits

The original A6 chronology is retained:
- Discovery: 2,011 rows.
- Validation: 670 rows.
- Historical Blind OOS: 670 rows.

The first 100 rows are a signal warm-up and are not scored. Expected evaluated counts: Discovery 1,911; Validation 670; Blind OOS 670. Each state uses only the preceding 100 feature-state values. All splits remain chronological.

Historical Blind OOS has been exposed to prior SONAR research and is not virgin prospective evidence. This run is exploratory and cannot authorize promotion.

## 4. Endpoints and controls

Co-primary family of three endpoints, evaluated on Blind OOS:
1. Nonlinear advantage: mean(D | H=1) - mean(D | H=0).
2. Pairwise-interaction advantage: mean(interaction_top5 - linear_top5 | H=1) - same conditional mean for H=0.
3. Gate advantage: mean(gate_top5 - linear_top5 | H=1) - same conditional mean for H=0.

For each endpoint report:
- high/low target counts and means;
- unconditional family differences;
- circular moving-block bootstrap 95% CI (20,000 replicates, block length 20);
- circular-shift randomization p-value (20,000 shifts; shift the state sequence relative to outcomes, preserve each series' internal order);
- Newey-West/HAC sensitivity with 20 lags and a linear time trend;
- Holm correction across the three registered endpoints.

Acceptance requires the primary effect >= +0.005, its 95% CI lower bound > 0, and Holm-adjusted p < 0.05. Discovery and Validation are descriptive replication checks; no parameter tuning is permitted from Blind OOS.

Uniform per-number Top-5 reference is 0.125. Formula-type aggregates are means over the deterministic A6 sample (650 linear, 2,100 interaction, 2,800 gate formulas); they are not independent formula-level observations. Inference is at target level.

## 5. Leakage, bias and reproducibility checks

1. Verify source ZIP hashes and exact matrix/ledger row alignment.
2. Verify all 59 features are finite and the matrix shape is exact.
3. Verify every target cutoff precedes its target date.
4. Recompute effective rank from the target's 40 x 59 matrix only.
5. For each t >= 100, verify the state threshold uses exactly rows [t-100,t).
6. Mutate all feature/outcome suffix rows after selected targets; earlier R_t, thresholds and H_t must remain unchanged.
7. Verify deterministic ranking of formula-family aggregates and deterministic RNG seeds.
8. Run the full experiment twice; report and ledger must be byte-identical.
9. Preserve the fixed A6 formula sample; do not reselect formulas by target outcomes.

## 6. Interpretation limits

- The source archive is historical and the Blind OOS has been exposed to previous SONAR research.
- Effective rank is computed from the candidate cross-section, not from a population of independent draws; it is a state descriptor, not a causal measure.
- A6 family aggregates are deterministic sample averages and formula outputs are dependent through shared features and base sets.
- This experiment evaluates per-number Top-5 ranking shares, not exact five-number ticket probabilities.
- A positive association would be hypothesis-generating only and would require a new prospective protocol.

## 7. Governance

No canonical archive mutation, Q60/B11 freeze change, active-engine mutation, shadow insertion, PR merge or engine promotion. PRs #6, #7 and #8 remain untouched. Keep all outputs append-only on the isolated D3 branch.
