# SONAR FD-04 — P5 order-statistic baseline audit

**Status:** EXPLORATORY / NO PROMOTION  
**Branch:** research/fd04-p5-order-statistic-null-20261108  
**Archive:** data/storico_daily.csv; blob SHA 5d2efd70684e918b27d8f06386d545647898336d; 3401 draws through 2026-11-07.

## Root-cause hypothesis

The Q90 pooled logistic P5 ranker report compared its P5 Top-5 hit rate (42.7935% on 673 targets from 2025-01-01 through 2026-11-04) with a 12.5% uniform-rank baseline. That reference is inappropriate for P5: P5 is the maximum order statistic of a 5-number sample without replacement from 1..40. Under the uniform lottery null, the exact marginal distribution is:

p(max=n) = C(n-1,4) / C(40,5), for n=5,...,40.

The theoretically optimal P5 ranking under this null is descending numeric order, not a uniform 40-candidate rank.

## Exact order-statistic baseline

| Metric | Exact baseline |
|---|---:|
| Top 5 candidates (36–40) | 50.6644% |
| Top 10 candidates (31–40) | 78.3428% |
| Top 20 candidates (21–40) | 97.6438% |
| Expected rank of the actual maximum | 6.833333 |

## Walk-forward test of temporal P5 frequency

A prior-only exponentially decayed estimate of historical maxima was tested with half-lives h={100,200,500} and Dirichlet prior ESS α={50,200,500}. Each target score uses only maxima from draws strictly before that target. Splits: discovery [200,1700), validation [1700,2550), blind OOS [2550,3401). The configuration with the lowest validation multiclass Brier score was h100_a500 (h=100, α=500).

| Split | Targets | Exact Top5 | Model Top5 | Exact Top10 | Model Top10 | Exact Top20 | Model Top20 | Exact mean rank | Model mean rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| discovery | 1500 | 49.7333% | 49.7333% | 77.2667% | 77.2000% | 97.5333% | 97.3333% | 7.0307 | 7.0573 |
| validation | 850 | 51.0588% | 51.0588% | 78.7059% | 78.8235% | 97.6471% | 97.7647% | 6.7071 | 6.7129 |
| blind_oos | 851 | 52.5264% | 52.5264% | 76.8508% | 76.8508% | 96.9448% | 96.8273% | 7.0129 | 6.9965 |

Selected blind proper-score comparison:
- Exact baseline Brier 0.927413; model 0.927622 (model-minus-baseline 0.000209).
- Exact baseline log loss 2.864504; model 2.867154 (model-minus-baseline 0.002650).
- Moving-block bootstrap 95% CI, Top5 hit delta: [0.000000, 0.000000]; Brier delta: [-0.000257, 0.000671]; log-loss delta: [-0.002138, 0.007467] (block=7, 2,000 reps).
- Block-sign permutation, block=7, 5,000 reps: selected raw/Holm p values Top5 lift 1.000000/1.000000, Brier improvement 0.805839/1.000000, log-loss improvement 0.837033/1.000000.
- Holm correction was applied across the 9 registered configurations separately for Top5, Brier, and log-loss. No adjusted evidence of gain.

## Audit of the existing Q90 logistic result

| Period | Targets | Logistic Top5 rate (reported) | Exact numerical Top5 baseline, actual archive | Difference |
|---|---:|---:|---:|---:|
| 2023 | 365 | 49.5900% | 49.5890% (181) | 0.0010 pp |
| 2024 | 366 | 43.4400% | 52.4590% (192) | -9.0190 pp |
| 2025 | 365 | 41.9200% | 51.7808% (189) | -9.8608 pp |
| 2026_ytd | 308 | 43.8300% | 52.2727% (161) | -8.4427 pp |
| pooled_test | 673 | 42.7935% | 52.0059% (350) | -9.2125 pp |

For the pooled 2025-01-01–2026-11-04 period, the logistic report has 288/673 Top5 hits (42.7935%); the fixed order-statistic Top5 set 36–40 hit the actual maximum 350/673 times (52.0059%). This is aggregate comparison only. The cited Q90 JSON does not include target-level logistic candidate ranks, so a paired test cannot be reconstructed. Do not interpret this table as a paired p-value.

## Decision and root cause

- The 12.5% uniform-rank P5 baseline materially understates P5’s intrinsic Top5 success rate; exact order-statistic Top5 baseline is 50.6644%.
- The temporal maximum-frequency model selected by validation has the same Top5 hit rate as numerical order in discovery, validation, and blind OOS; no Top5 lift.
- On blind OOS, Brier and log loss are slightly worse than the exact baseline. Confidence intervals include zero and Holm-adjusted block tests do not support improvement.
- The Q90 logistic aggregate P5 Top5 rate is below the exact numerical baseline in pooled test and 2024–2026 periods. Paired significance remains unavailable because target-level ranks are not persisted in the cited JSON.

**Decision:** FD-04 is a valid null/diagnostic result. No engine promotion, merge, or PR creation. PR #6, #7, and #8 remain untouched.

## Integrity and reproducibility

- Archive validation: strictly increasing dates; five distinct integers in [1,40] per draw.
- Each walk-forward target uses only historical maxima strictly before its target.
- Exact order-statistic baseline is derived analytically, not fitted on blind OOS.
- Grid, block lengths, deterministic permutation seed, and bootstrap seed are recorded in the script and JSON.
- The analysis was executed in ChatGPT V8 Code Mode against the fetched archive. The persisted Node script was not run in native Node in this cycle; GitHub Actions/CI on this branch was not run.

## Next iteration

Audit Q90 feature lineage and recover per-target P5 forecast ranks from the workflow artifact if available. Register the exact order-statistic rank as the primary baseline before rerunning P5 models. If target-level model ranks cannot be recovered, keep the logistic result descriptive and do not claim paired predictive lift.
