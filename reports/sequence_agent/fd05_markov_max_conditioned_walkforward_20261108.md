# SONAR FD-05 — Markov-conditioned P5 maximum walk-forward audit

**Status:** EXPLORATORY / NULL RESULT / NO PROMOTION  
**Branch:** `research/fd05-markov-max-context-20261108`  
**Archive:** `data/storico_daily.csv`; Git blob SHA `5d2efd70684e918b27d8f06386d545647898336d`; 3401 draws through 2026-11-07.  
**Parent:** `76ab0f33aa261a2dcb0d8c5f6f59889facb32c13` (main snapshot inspected at cycle start).

## Research question and registered hypothesis

FD-04 showed that a decayed unconditional maximum-frequency model did not beat the exact order-statistic baseline. FD-05 tests whether the maximum's recent temporal context adds useful information:

[
P(M_t=n mid B(M_{t-1})=b)
]

where (M_t=P5_t), and (B) is a fixed four-bin partition derived from the analytical null CDF, not fitted to blind outcomes. Context bins are `5-31` (25.8220%), `32-36` (31.4709%), `37-38` (18.9891%), `39-40` (23.7179%).

For each bin (b), estimate a decayed prior-only conditional count distribution (C_{b,n}(t)), and shrink it toward the exact null (p_0(n)=\binom{n-1}{4}/\binom{40}{5}):

[
p_t(n)=\frac{\alpha p_0(n)+C_{b,n}(t)}{\alpha+\sum_{k=5}^{40}C_{b,k}(t)}.
]

Pair counts use only historical pairs (j<t), context (B(M_{j-1})), outcome (M_j), and weight (2^{-(t-j)/h}). The current context is (B(M_{t-1})). No target or future observation enters its own estimate.

## Protocol

- Chronological strict-prior walk-forward; each target uses only the prefix before it.
- Fixed split indices: discovery [200,1700), validation [1700,2550), blind OOS [2550,3401).
- Fixed 16-configuration grid: (h\in\{60,120,240,480\}), Dirichlet ESS (\alpha\in\{50,200,500,1000\}).
- Validation selection criterion: lowest multiclass Brier score. Selected configuration: **h60_a200**.
- Blind primary endpoint: paired multiclass Brier difference model minus analytical null. One-sided block sign-flip permutation with block length 7, 5,000 replicates; Holm correction over all 16 fixed configurations.
- Selected-model uncertainty: moving-block bootstrap, block 7, 2,000 replicates; fixed seeds 20261108 and 20261109.
- Secondary endpoints: Top-5/10/20 hit share, mean rank, log loss.
- Exact order-statistic baseline is analytical, not learned from the target period.

## Selected-model results vs exact null

| Split | Targets | Null Top5 | Model Top5 | Null Top10 | Model Top10 | Null Top20 | Model Top20 | Null Brier | Model Brier | Null log loss | Model log loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| discovery | 1500 | 49.7333% | 49.5333% | 77.2667% | 77.2000% | 97.5333% | 97.2667% | 0.929500 | 0.929670 | 2.856103 | 2.860162 |
| validation | 850 | 51.0588% | 51.4118% | 78.7059% | 78.8235% | 97.6471% | 97.5294% | 0.924472 | 0.924246 | 2.809316 | 2.811257 |
| blind_oos | 851 | 52.5264% | 52.4089% | 76.8508% | 77.0858% | 96.9448% | 96.5922% | 0.927413 | 0.927529 | 2.864504 | 2.865823 |

Blind selected-model deltas (model minus null):
- Brier: **0.000116870**; moving-block bootstrap 95% CI [-0.000379288, 0.000600269].
- Log loss: **0.001319412** (positive is worse).
- Top-5 hit share: **-0.1175 percentage points**; bootstrap 95% CI [-0.3525, 0.0000] pp.
- Selected config's block-permutation raw p=0.681864; Holm-adjusted p=1.000000.
- Across the 16 fixed configs, the smallest raw one-sided Brier-improvement p=0.407119 (h120_a1000); its Holm-adjusted p=1.000000. No configuration supports improvement.

## Diagnosis

The Markov context does not yield a reliable predictive lift. The validation winner improves Brier only on the validation segment; on blind OOS its Brier and log loss are worse than the exact-null distribution, and its Top-5 share is slightly lower. The block-bootstrap interval includes zero, and all Holm-adjusted block tests are 1.000000. This is a null diagnostic, not a failed integrity check.

## Prospective shadow freeze

For the next draw after cutoff 2026-11-07, using previous maximum 38 and selected config h60_a200:
- Model Top-5 max candidates: **40, 39, 38, 37, 36**.
- Exact-null Top-5 candidates: **40, 39, 38, 37, 36**.
- Model Top-10 candidates: 40, 39, 38, 37, 36, 35, 34, 33, 32, 31.
- Model top-five candidate probabilities are recorded in the JSON freeze.

This is a shadow research freeze for evaluating a later outcome; it is not a lottery recommendation or evidence of winning odds.

## Integrity, reproducibility and gates

- CSV structure, strict ascending dates, 5 unique values in [1,40], and ascending quintets are checked by the runner.
- All scores are based on maxima (M_t=n5_t); contexts are built from (M_{t-1}) only.
- Grid, splits, fixed context bins, seeds, permutation count, bootstrap count and full candidate metrics are persisted.
- Native Node reproducibility is gated by `node scripts/sonar_fd05_markov_max_walkforward.mjs --check`, which compares the regenerated JSON byte-for-byte at the parsed-object level with the persisted report JSON.
- Exact-head GitHub Actions CI is required; no model promotion, merge, or PR modification is authorized in this cycle.
- PR #6, #7, #8 remain untouched.

## Next iteration

Prioritize Q90 P5 feature-lineage audit and recovery of per-target logistic ranks. If the paired target ledger is unavailable, keep Q90 aggregate comparisons descriptive. Continue append-only prospective freezes and evaluate only after the corresponding official outcome is verified.
