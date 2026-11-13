# Q141-D4 — Family Top-5 consensus under disagreement states

**Registration:** 2026-11-13 14:48 UTC  
**Status:** preregistered before D4 outcome calculation  
**Scope:** historical exploratory research only; no forecast, production engine, shadow row, or promotion.

## 1. Question and hypothesis

Do the seven Q89 feature families' pre-target Top-5 sets contain useful agreement information, and does a vote-based family consensus add value specifically when the families disagree more than usual?

For each target t, use the 59-feature matrix X_t in R^(40×59), whose columns are per-target z-scores across the 40 candidates and whose lineage is documented as strict-prior-only.

The fixed seven-family partition is:
- baseline_legacy: the 27 features not listed in Q89's new_feature_family_map;
- ewma_hit_dynamics;
- gap_dynamics;
- cooccurrence_novelty;
- rank_trajectory;
- residual_surprise;
- regime_transition_affinity.

Each family score for candidate n is the arithmetic mean of that family's feature z-scores. Rank each family independently, descending score, ties by ascending number. Let T_f,t be its Top-5 set.

The pre-target agreement statistic is the mean pairwise Jaccard similarity:

A_t = (1 / choose(7,2)) * sum_(f<g) |T_f,t intersect T_g,t| / |T_f,t union T_g,t|.

Disagreement state:

H_t = 1[A_t < median(A_(t-100), ..., A_(t-1))], for t >= 100.

Thus H_t=1 denotes unusually high family disagreement. The current target's features may define A_t, but the state threshold uses only the preceding 100 targets. No target outcome enters A_t, its threshold, or H_t.

Two Top-5 selectors are compared:
- **Consensus:** rank candidates by descending number of family Top-5 votes (0–7), then descending mean of the seven family scores, then ascending number.
- **Equal-family mean:** rank by descending arithmetic mean of the seven family score vectors, ties by ascending number.

For target t, let d_t = hits(Consensus_t)-hits(EqualFamily_t), where hits counts the realized numbers in the forecast Top-5.

**Primary hypothesis:** on the historical Blind OOS, the mean d_t in high-disagreement states exceeds the mean d_t in low-disagreement states by at least **+0.025 hits per target** (equivalent to +0.005 of the five-number hit share).

The direction and threshold are fixed. No state reversal, threshold search, family regrouping, or tie-rule change is permitted after outcome inspection.

## 2. Sources and exact alignment

- Q90 artifact ZIP SHA-256: 12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077.
- Q90 matrix member: adaptive_novelty_feature_matrix.npz, SHA-256 681152ddfaa0217889f0a1623f0ce1dc9691ffabdd4901869cb736b58185ec49, shape 3,351 × 40 × 59, float32.
- Q89 feature catalog member SHA-256: 0761324a35faade5e7dc9a053d19146f21d349ba9e8237b334691c6b1e5517a5.
- Q141-A6 artifact ZIP SHA-256: e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc.
- A6 target ledger member SHA-256: 3db21ad7a0d94f3d07f437865282ed306d0a022d9f313095fa4bedbb66d5b32b, 3,351 rows. Target date, cutoff, actual quintet and split must match the Q90 matrix exactly. The A6 ledger supplies realized outcomes only after each forecast ranking has been constructed.
- The pinned Q90 archive ends 2026-11-07 (3,401 draws). The five later main-archive rows are excluded. No post-cutoff main-archive values are used.

The runner must verify the artifact digests, member digests, finite matrix values, exact date/cutoff/actual alignment, prior-draw counts and chronological split counts before scoring.

## 3. Walk-forward splits

Use the fixed A6 chronology:
- Discovery: 2,011 target rows.
- Validation: 670 target rows.
- Historical Blind OOS: 670 target rows.

The first 100 targets are used only to establish the rolling state threshold. Expected evaluated counts are Discovery 1,911, Validation 670, Blind OOS 670. No model parameter is selected on Validation or Blind OOS.

## 4. Endpoints and inference

Blind OOS endpoints:
1. **Primary:** high-disagreement minus low-disagreement mean paired hit difference d_t.
2. **Secondary:** unconditional mean paired hit difference d_t.
3. **Baseline control:** consensus mean hits minus the exact uniform 5-of-40 expectation of 0.625 hits/target.

Inference:
- Primary 95% CI: 20,000 circular moving-block bootstrap replicates, block length 20, resampling state and paired outcome together.
- Primary two-sided p-value: 20,000 circular shifts of the state sequence relative to paired outcomes.
- Secondary 95% CI: same circular moving-block bootstrap.
- Secondary two-sided p-value: 20,000 Monte Carlo sign-flips of non-overlapping 20-target block sums.
- Uniform control: exact upper-tail probability for the total hit count under the conditional Hypergeometric(40, 5, 5) null, convolved across the 670 predictable forecasts.
- Holm correction across the three registered p-values.

Acceptance requires the primary effect ≥ +0.025 hits/target, its 95% CI lower bound > 0, and Holm-adjusted p < 0.05. Discovery and Validation are descriptive replication checks only.

## 5. Integrity and bias controls

1. Recompute family membership from Q89's persisted family map; all 59 features must belong to exactly one group.
2. Use only the target's feature matrix row to compute family scores and agreement.
3. Use exactly the preceding 100 agreement values for the state threshold.
4. Keep outcomes isolated until all Top-5 rankings and state values for the target are fixed.
5. Verify target/cutoff chronology and exact row alignment.
6. Mutate all feature and outcome suffix rows after selected targets; earlier family scores, agreement, threshold, state and rankings must remain unchanged.
7. Run the full experiment twice; report and ledger must be byte-identical.
8. Preserve fixed feature groups, top-five size, tie rules, seeds and inferential constants.

## 6. Interpretation limits

- The historical Blind OOS has been exposed to earlier SONAR research and is not virgin prospective evidence.
- Q89 features are standardized cross-sectionally and include known rank duplicates; equal-family aggregation prevents simple family-size weighting but does not remove within-family redundancy.
- The seven-family grouping is the persisted Q89 grouping, not a newly optimized semantic taxonomy.
- This tests per-number Top-5 selections, not exact five-number ticket probability.
- The Q90 feature matrix ends 2026-11-07; it is not the current 3,406-draw main archive.
- Holm covers these three D4 endpoints only, not the complete Q00–Q141 research family.

## 7. Governance

Research-only. No canonical archive, B11/Q60 freeze, active scorer, or production engine is changed. No shadow insertion, no merge, no rebase, and no engine promotion. PRs #6, #7 and #8 remain untouched. Historical Blind OOS cannot authorize promotion.