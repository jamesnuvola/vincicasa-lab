# SONAR FD-02 — Band-conditioned residual audit
**Status: EXPLORATORY / NOT PROMOTABLE**  
**Run timestamp:** 2026-11-08 02:43:29 Europe/Rome  
**Branch:** `research/fd02-band-conditioned-residual-20261108`  
**Implementation:** `scripts/sonar_fd02_band_conditioned_residual.mjs`, blob SHA `10a7285ea4a737d7e9f19371260787f14a579cb2`  
**Archive:** `data/storico_daily.csv`, blob SHA `5d2efd70684e918b27d8f06386d545647898336d`; 3,401 draws, 2017-07-17 through 2026-11-07. Archive validation passed: dates strictly ordered/unique, five distinct integers in 1..40 per draw.

## Hypothesis and protocol
FD-01's Gaussian smoothing may have a boundary/label-space effect. Compare, with the same prior-only 200-draw half-life:
- **RAW:** exponential-decayed frequency (c_n(t)), no number-space smoothing.
- **FD-01 DIFF:** normalized Gaussian kernel on labels 1..40, (sigma=4).
- **FD-02 REF:** same (sigma=4), reflective-boundary image kernel (period 80, image terms (m=-3,ldots,3)).

Every target's scores use only rows strictly before the target; score ties resolve by ascending number. Chronological split indices: discovery [200,1700) = 1,500 targets; validation [1700,2550) = 850; blind OOS [2550,3401) = 851. Top-k metric is the share of actual individual numbers ranked <=k; mean rank averages five actual number ranks per draw.

## Walk-forward metrics

| Split | Model | Top5 hit % | Top10 hit % | Top20 hit % | Mean rank | Top5 hits |
|---|---|---:|---:|---:|---:|---:|
| Discovery | RAW | 12.3067 | 25.0133 | 50.1867 | 20.4323 | 923 |
| Discovery | FD-01 DIFF | 12.6533 | 25.2267 | 50.7600 | 20.3125 | 949 |
| Discovery | FD-02 REF | 12.7200 | 25.0933 | 50.6800 | 20.3105 | 954 |
| Validation | RAW | 12.0941 | 24.9176 | 49.4824 | 20.5713 | 514 |
| Validation | FD-01 DIFF | 12.9882 | 24.9647 | 49.6706 | 20.4704 | 552 |
| Validation | FD-02 REF | 12.7765 | 25.0118 | 49.5294 | 20.4748 | 543 |
| Blind OOS | RAW | 13.1375 | 25.8049 | 49.6357 | 20.4919 | 559 |
| Blind OOS | FD-01 DIFF | 13.5605 | 25.0999 | 49.7767 | 20.5065 | 577 |
| Blind OOS | FD-02 REF | 13.5135 | 24.9119 | 49.4947 | 20.5152 | 575 |

Uniform rank baseline: Top5 12.5%, Top10 25%, Top20 50%, mean rank 20.5. Blind OOS has no all-five-in-Top5 draw for any candidate.

## Paired model-vs-RAW comparison (blind OOS)
Paired Top5 hit counts per target; one-sided 7-target block sign-permutation (20,000 reps), moving-block bootstrap (block=7, 5,000 reps). Holm correction across the two candidate-vs-RAW comparisons:

| Comparison | Extra Top5 hits | Delta Top5 pp | Block p | Holm p | Bootstrap 95% CI, hits/target |
|---|---:|---:|---:|---:|---:|
| FD-01 DIFF − RAW | +18 | +0.423 | 0.26654 | 0.53307 | [-0.03878, 0.08108] |
| FD-02 REF − RAW | +16 | +0.376 | 0.29439 | 0.53307 | [-0.04230, 0.07991] |

Both confidence intervals include zero. **The pilot's apparent Top5 gain is not a statistically supported improvement over the simpler decayed-frequency baseline on this blind slice.** Top10/20 and mean rank do not show a consistent advantage.

## Conditional randomization diagnostic
Post-hoc diagnostic hypothesis: perhaps the smoothed candidates contain a number-identity association beyond the coarse numeric band composition. For each blind target, hold fixed (a) the forecast Top5 count in each band [1–5], [6–10], [11–30], [31–35], [36–40] and (b) the actual draw's count in each band. Randomly reassign forecast identities uniformly within each band without replacement; compare total Top5 hits. Monte Carlo upper-tail p-values use 10,000 replicates; Holm correction covers this three-model diagnostic family only.

| Model | Observed hits | Conditional analytic expectation | MC null mean | MC 95% interval | Upper-tail p | Holm p |
|---|---:|---:|---:|---:|---:|---:|
| RAW | 559 | 529.350 | 529.159 | [491,568] | 0.06879 | 0.06879 |
| FD-01 DIFF | 577 | 545.800 | 546.169 | [521,572] | 0.01060 | 0.02400 |
| FD-02 REF | 575 | 545.350 | 545.372 | [522,569] | 0.00800 | 0.02400 |

This suggests a conditional identity-level association for the two smoothed variants relative to the band-preserving null on the reused blind slice. It **does not** establish superiority over RAW (paired tests above are non-significant). The diagnostic was generated after inspecting the FD-01 blind metrics; the blind slice is therefore reused, not an independent confirmatory test. Holm is limited to these three candidates and does not cover the full SONAR catalog or all previous experiments. Treat the conditional p-values as hypothesis-generating only.

## Reproducibility and integrity
- The committed script's computation was replayed in the CodeMode V8 runtime after injecting the exact archive text in place of the Node filesystem read and stripping Node import/shebang lines. Archive validation passed and outputs reproduced the reported metrics, paired tests, conditional randomization and next-target scores.
- The script blob SHA and archive blob SHA were fetched and verified. Native GitHub Actions/CI on this branch was **not** run; no CI or human-review claim is made.
- No engine promotion, PR creation, merge, or edits to PR #6/#7/#8.

## Append-only prospective freeze
A new FD-02 experimental forecast freeze is persisted separately for target **2026-11-08**, cutoff **2026-11-07**, at 2026-11-08 02:43:29 Europe/Rome. See `reports/sequence_agent/fd02_prospective_freeze_2026-11-08.json`. It is a shadow freeze, distinct from the existing official `position_seed_mix_top20_v1` freeze/registered Q60 comparison.

## Next iteration
1. Keep RAW, FD-01 DIFF and FD-02 REF frozen as candidates; do not retune against this blind slice.
2. Evaluate the append-only prospective shadow stream over at least 200 targets, with identical dates and pre-target cutoffs.
3. For any future conditional diagnostic, register its statistic and test family before reading new outcomes; include block-aware inference and broader experiment-family correction.
4. Keep the repository research queue's Q60 status `INSUFFICIENT_PROSPECTIVE_CASES` until its registered 200 paired target minimum is met. This FD-02 report does not complete Q60.
