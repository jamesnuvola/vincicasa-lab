# Q141-A5 / B10 — Q90 feature-lineage and redundancy-balanced Borda

**Registration:** 2026-11-12, before the B10 walk-forward run.  
**Scope:** structural lineage audit of Q90's 59-feature source matrix and 330,429-formula catalogue, plus one confirmatory aggregation experiment.  
**Research-only:** no engine promotion, no shadow insertion, no canonical archive mutation, no merge.

## Source and lineage

- Q90 artifact run `42504717670`, artifact `13627507532`, ZIP SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`.
- Q90 archive Git blob `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 draws through 2026-11-07.
- Q90 matrix: 3,351 targets × 40 candidate numbers × 59 features, float32, each feature row normalized across candidates and declared strictly prior-only.
- Q90 feature selection chose 20 of 59 features on Discovery; Validation and Blind use that frozen subset. The 39 unselected features remain outside the current Q90 formula grammar.
- Q90 formula catalog: 330,429 formula IDs, split metrics 991,287 rows, target ledger 3,351 rows.
- Q90 is an exact normalized-line-ending prefix of Q141 archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103`: 3,401 vs 3,405 data rows. Four Q141 suffix rows dated 2026-11-08 through 2026-11-11 are excluded. The Q141-C6 checkpoint's 3,404 count is an off-by-one metadata error; it does not change the Q90 source window used here.
- The previously persisted Q90 typed AST manifest reports 330,429 unique AST IDs and zero duplicates. All seven shard Git blob SHAs were re-read from the research branch and matched the manifest.

## Structural hypothesis

The Q90 grammar has 4,845 distinct four-feature base quartets. Every quartet appears in exactly 15 operator variants: one linear L4, six pairwise I4, and eight conditional G4 variants. The I4 product factors and G4 gate feature are members of the same four-feature base set. This creates 67,830 additional formula rows beyond the 4,845 unique four-feature base sets. The remaining L5-L8 linear formulas have one formula per feature subset.

The 20 selected feature columns also exhibit non-trivial rank dependence. Mean absolute pairwise Spearman correlation across the 40 candidate numbers and all 3,351 targets is computed as a descriptive structural measure; it is not used to choose formulas or weights.

## B10 hypothesis and fixed sample

**Hypothesis:** raw formula-weighted Borda may over-count repeated operator variants of the same four-feature base subset. A base-set-balanced Borda, giving each distinct sampled feature subset total weight 1, should improve Blind OOS Top-5 hit share over raw formula-weighted Borda by at least `+0.005`.

Deterministic, outcome-independent sample:

- Select 100 four-feature quartets by the smallest SHA-256 of `Q141-B10|Q4|` + canonical sorted feature indices; include all 15 variants per quartet (1,500 formulas).
- Select 100 linear formulas each from L5, L6, L7 and L8 by the smallest SHA-256 of `Q141-B10|Lk|` + formula ID (400 formulas).
- Total: 1,900 formulas across 500 distinct base feature sets.
- Raw Borda weight: 1 per formula.
- Balanced Borda weight: `1 / sampled_formula_count_for_exact_base_feature_set`, so every base set contributes total weight 1.
- Higher formula score ranks first; score rounded to 12 decimals; ties resolve to lower number ID.

## Walk-forward and endpoint

- 3,351 targets: Discovery 2,011; Validation 670; Blind OOS 670.
- For target `t`, only Q90 feature matrix row `t` is used; the target quintet is read only after formula rankings and both Borda rankings are frozen.
- Linear score: arithmetic mean of selected feature columns.
- Interaction score: four-feature mean plus 0.25 × candidate-wise z-score of the selected feature-pair product across 40 candidates.
- Gate score: four-feature mean plus 0.25 × indicator(gate feature ≥ registered threshold).
- One confirmatory endpoint: Blind OOS mean Top-5 hit-share difference, balanced minus raw Borda.
- Practical threshold: `+0.005`.
- Discovery and Validation are reported for stability, but not used for post-hoc selection.

## Statistical plan

- Paired target-level effect.
- 95% circular moving-block bootstrap, block length 20, 20,000 replicates, seed `14120261112`.
- One-sided non-overlapping chronological block sign-flip test, block length 20, 20,000 replicates, with the final partial block weighted by its target count.
- One confirmatory endpoint; no multiplicity correction is required within B10. Feature correlations and split-wise summaries are descriptive only.
- No lift unless point estimate ≥ +0.005, the 95% interval is wholly positive, and one-sided block p < 0.05.

## Leakage, bias and reproducibility controls

- Verify ZIP SHA-256 and all 17 member SHA-256 values.
- Verify feature matrix shape, dtype, finite values, archive blob, target/cutoff dates, actual quintets and Q90 target-ledger alignment.
- Verify 100 quartets × 15 variants and 100 long linear formulas per size; no outcome-based sampling.
- Verify all Q90 formula references stay within the Discovery-selected 20 features.
- Reconcile per-formula Top-5 hit shares for all 1,900 sampled formulas against the original Q90 split metrics to < `1e-12`.
- Future-suffix and target-outcome invariance; update-free target scoring; tie-order test.
- Full deterministic replay must produce byte-identical report, ledger, sample, feature audit and manifest.

## Limits

This tests one fixed sample (1,900/330,429 formulas), not the entire formula universe. Q90's 20-feature subset is Discovery-selected; the 39 other features are not represented. Historical Blind OOS is exposed SONAR research history, not virgin prospective evidence. Top-5 hit share is a per-number ranking diagnostic, not a five-number winning-combination forecast. A null result does not establish that all structural redundancy corrections are ineffective.

## Next action

Q141-A6: design a tractable, deterministic 59-feature expansion. The same declared Q90 grammar over all 59 features would contain approximately 2.616 billion formulas, so exhaustive enumeration is not appropriate. Use a pre-registered stratified/covering sample across all 59 features and feature families, preserve the Q90/Q89 source lineage, and evaluate only with strict-prior walk-forward.
