# SONAR FD-03 — Diffusion grid family-wise audit

**Status: EXPLORATORY / NOT PROMOTABLE**  
**Branch:** `research/fd03-diffusion-grid-audit-20261108`  
**Archive:** `data/storico_daily.csv`, blob SHA `5d2efd70684e918b27d8f06386d545647898336d`; 3,401 draws, 2017-07-17 through 2026-11-07.  
**Code blob SHA:** `ad6e695c3a602fdba16fdbad0434ac311af2c5c9`  
**Metrics artifact blob SHA:** `cc511446c4ad27baabe9d1693d95234b722c05df`

## Hypothesis and root-cause question

FD-01 selected Gaussian diffusion parameters `h=200, sigma=4` by validation Top-5 hit rate and reported an unadjusted blind-slice Top-5 excess. FD-02 showed that this apparent gain was not significant in a paired comparison against the simpler same-half-life RAW frequency baseline. FD-03 asks whether the FD-01 Top-5 signal survives a full correction across its registered 4×4 hyperparameter grid and whether diffusion consistently beats RAW with matched temporal half-life.

This is a retrospective audit of the previously inspected blind slice, not a fresh confirmatory sample. The full grid correction is reported, but it cannot correct for every earlier SONAR experiment or prior look at these targets.

## Strict-prior walk-forward protocol

- Every target score uses only draws with index strictly less than that target; scores are ranked descending with ties broken by ascending number.
- Minimum history: 200 draws.
- Grid inherited from the FD-01 registration: half-life `h ∈ {50, 100, 200, 500}`; Gaussian `sigma ∈ {0.5, 1, 2, 4}`; 16 variants.
- Chronological splits: discovery [200,1700) = 1,500 targets; validation [1700,2550) = 850; blind OOS [2550,3401) = 851.
- Top-k is the share of actual individual numbers ranked in the model's Top-k. Mean rank averages the five actual numbers.
- Uniform Top-5 null: exact convolution of the hypergeometric overlap distribution for independent uniform 5-subsets per target. Holm adjustment across all 16 grid candidates.
- Matched RAW comparisons use the unsmoothed exponential occurrence field with the same half-life as each candidate; one-sided block-sign permutation (block=7 targets, 10,000 repetitions), Holm across 16 comparisons, and moving-block bootstrap (block=7, 2,000 repetitions) 95% intervals.

## Selected FD-01 configuration

| Split | FD-01 h=200 sigma=4 Top5 | RAW h=200 Top5 | FD-01 Top10 | RAW Top10 | FD-01 Top20 | RAW Top20 | FD-01 mean rank | RAW mean rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery | 12.6533% | 12.3067% | 25.2267% | 25.0133% | 50.7600% | 50.1867% | 20.3125 | 20.4323 |
| Validation | 12.9882% | 12.0941% | 24.9647% | 24.9176% | 49.6706% | 49.4824% | 20.4704 | 20.5713 |
| Blind OOS | 13.5605% (577) | 13.1375% (559) | 25.0999% | 25.8049% | 49.7767% | 49.6357% | 20.5065 | 20.4919 |

Selected blind Top-5 excess vs uniform: 577 observed vs 531.875 expected; exact one-sided p=0.01515, Holm-adjusted p=0.24240 across 16 grid candidates.

Selected blind paired FD-01 − RAW h=200: +18 hits, +0.4230 percentage points; block p=0.25977, Holm p=1.00000. Moving-block bootstrap 95% CI=[-0.0376,0.08226] hits/target (equivalent to -0.752 to 1.645 percentage points). The interval includes zero.

**Decision:** the raw p-value for the selected model is not family-wise robust (Holm p=0.24240), and diffusion does not significantly outperform the matched RAW baseline (paired Holm p=1.00000; CI includes zero). Top-10 and mean-rank outcomes are not consistently favorable. FD-01 remains exploratory; no promotion is justified.

## Full registered grid

| Model | Validation Top5 | Blind Top5 (hits) | Exact p vs uniform | Holm p (16) | Paired p vs matched RAW | Holm p (16) | Moving-block bootstrap 95% CI (hits/target) |
|---|---:|---:|---:|---:|---:|---:|---:|
| FD h=50 sigma=0.5 | 12.0000% | 12.7145% (541) | 0.33506 | 1.00000 | 0.79932 | 1.00000 | [-0.0329, 0.01528] |
| FD h=50 sigma=1 | 12.4706% | 12.5264% (533) | 0.48588 | 1.00000 | 0.78452 | 1.00000 | [-0.06345, 0.02585] |
| FD h=50 sigma=2 | 12.4941% | 12.6910% (540) | 0.35299 | 1.00000 | 0.63834 | 1.00000 | [-0.0611, 0.047] |
| FD h=50 sigma=4 | 12.4000% | 12.1034% (515) | 0.80202 | 1.00000 | 0.89301 | 1.00000 | [-0.09871, 0.02115] |
| FD h=100 sigma=0.5 | 12.6118% | 13.1140% (558) | 0.10543 | 1.00000 | 0.28837 | 1.00000 | [-0.01528, 0.02938] |
| FD h=100 sigma=1 | 12.3765% | 12.0564% (513) | 0.82833 | 1.00000 | 0.97860 | 1.00000 | [-0.09283, 0.00353] |
| FD h=100 sigma=2 | 12.8941% | 12.8555% (547) | 0.23638 | 1.00000 | 0.59684 | 1.00000 | [-0.0658, 0.0517] |
| FD h=100 sigma=4 | 12.8706% | 12.5734% (535) | 0.44702 | 1.00000 | 0.75832 | 1.00000 | [-0.07873, 0.03995] |
| FD h=200 sigma=0.5 | 12.0941% | 13.0670% (556) | 0.12415 | 1.00000 | 0.63364 | 1.00000 | [-0.02938, 0.0235] |
| FD h=200 sigma=1 | 12.3529% | 12.6910% (540) | 0.35299 | 1.00000 | 0.82322 | 1.00000 | [-0.07051, 0.03055] |
| FD h=200 sigma=2 | 12.7294% | 12.8085% (545) | 0.26738 | 1.00000 | 0.70523 | 1.00000 | [-0.07756, 0.04465] |
| FD h=200 sigma=4 | 12.9882% | 13.5605% (577) | 0.01515 | 0.24240 | 0.25977 | 1.00000 | [-0.0376, 0.08226] |
| FD h=500 sigma=0.5 | 12.0706% | 12.8085% (545) | 0.26738 | 1.00000 | 0.63114 | 1.00000 | [-0.02938, 0.02233] |
| FD h=500 sigma=1 | 12.2353% | 12.5264% (533) | 0.48588 | 1.00000 | 0.77192 | 1.00000 | [-0.06816, 0.03643] |
| FD h=500 sigma=2 | 12.4706% | 12.8085% (545) | 0.26738 | 1.00000 | 0.56554 | 1.00000 | [-0.06463, 0.0564] |
| FD h=500 sigma=4 | 11.9059% | 12.9495% (551) | 0.18083 | 1.00000 | 0.46715 | 1.00000 | [-0.05993, 0.06698] |

## Integrity, reproducibility, and gates

- Archive schema/date/number validation passed; 3,401 rows with five distinct integers 1–40 per draw and strict chronological dates.
- The walk-forward implementation was run against the fetched canonical archive. Every target used only the strict historical prefix.
- The script and JSON result were written to the FD-03 branch and re-read through GitHub Contents API with exact content equality. Blob SHAs are recorded above.
- Native GitHub Actions/CI on this branch was **not run**. No PR was created; no human review or integration occurred.
- PR #6, #7, #8 were not changed. No engine promotion or merge.

## Next iteration

Keep FD-01 and the matched RAW baseline frozen. Treat this audit as hypothesis-generating because the blind slice has already been inspected. Continue append-only prospective shadow freezes; preregister the primary metric and correction family before new target outcomes, and wait for at least 200 complete paired prospective targets before any promotion review.
