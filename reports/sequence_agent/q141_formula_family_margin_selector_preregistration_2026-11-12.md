# Q141-C2 — Current-state family selection by standardized score margin

**Registered:** 2026-11-12, before C2 computation  
**Status:** PREREGISTERED — execution pending  
**Parent:** Q141 Formula Universe & Behaviour Mapping  
**Source:** `data/storico_daily.csv`, Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`; 3,404 eligible draws through 2026-11-10. Exclude contest 315 / 2026-11-11.

## Quantitative hypothesis

The formula family with the largest standardized current-target Top-5/Top-6 score margin is more useful on that target than an equal-family ensemble. This tests whether the *current prior-only state* carries information about which family is useful, without relying on the near-zero persistence of past family hit counts found in Q141-C0.

## Frozen selection rule

Reuse exactly the six Q141-C0 families and 25 unique Q80 features. For each family and target:
1. Compute its score for all 40 numbers as the arithmetic mean of its per-target standardized feature columns.
2. Sort its 40 scores descending.
3. Compute the standardized margin:
   `(fifth-largest score - sixth-largest score) / population_sd(all 40 family scores)`.
4. If the population standard deviation is below `1e-12`, define the margin as zero.
5. Select the family with the largest margin; break exact ties by ascending family ID.

This is an ex-ante, current-state policy. It uses no target outcome and has no rolling-success warm-up, tunable threshold, or selected lookback. All six family rankings and the selected family are frozen before the target quintet is read.

## Baselines and endpoints

Compare the margin-selected family against:
- Equal-family ensemble (same six family scores, equal weights).
- Equal-feature ensemble (same 25 unique standardized features, equal weights).
- Fixed family selected on Discovery only by mean Top-5 hits, with lower mean actual rank and family ID as deterministic tie-breakers; frozen for Validation and Blind OOS.

Endpoints: Top-5, Top-10 and Top-20 winning-number hit share; mean rank of the five actual numbers. Uniform 5-of-40 expectations are 0.125, 0.25, 0.5 and mean rank 20.5.

## Walk-forward and statistical controls

- 3,404 eligible draws; minimum prior history 50; 3,354 targets.
- Chronological split: Discovery 2,013; Validation 671; Blind OOS 670, using the fixed Q141-C0 rule.
- All feature construction uses only draws strictly before each target. Update the history state only after all rankings and the target metrics are frozen.
- Paired inference: non-overlapping 20-target block sign-flip and circular moving-block bootstrap, 20,000 replicates, deterministic seeds.
- Holm-Bonferroni across all 24 Validation/Blind × 3 comparators × 4 endpoints.
- Exact discrete-convolution uniform-null checks for margin-selected Top-5/10/20 in Validation and Blind OOS; Holm across six tests.
- Secondary descriptive calibration: Spearman association between the pre-target selected-family margin and that family's realized Top-5 hits, six families × three splits, Holm across 18 tests. This diagnostic cannot change the policy.

**Primary practical gate:** Blind OOS Top-5 hit-share gain over equal-family at least +0.005, Holm-adjusted paired p<0.05, and 95% block-bootstrap lower bound above zero.

## Interpretation and limitations

A large score margin is not automatically calibrated confidence; C2 tests whether it is. The six families are coarse Q80-derived groups, not the full mathematical formula universe. The historical archive is exposed to extensive prior SONAR research and is not virgin prospective evidence. The uniform null assumes independent uniform 5-of-40 draws. Holm controls this registered C2 test family, not the whole Q00-Q141 research history.

A valid null result completes this experiment. No family or engine is promoted; no shadow insertion, archive mutation, auto-merge, or changes to PRs #6/#7/#8.
