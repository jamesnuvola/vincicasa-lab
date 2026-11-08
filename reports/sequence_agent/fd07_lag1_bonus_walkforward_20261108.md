# SONAR FD-07 — strict-prior lag-1 carryover bonus audit

**Status:** EXPLORATORY / NO LIFT CONFIRMED / NO PROMOTION  
**Branch:** `research/fd07-lag1-bonus-20261108`  
**Base:** FD-06 isolated research branch  
**Archive:** `data/storico_daily.csv`, Git blob SHA `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 draws through 2026-11-07.

## Hypothesis and protocol

Hypothesis: a number appearing in the immediately previous draw may carry a small short-term recurrence signal beyond its exponentially decayed historical frequency. For each number (n), score:

[
S_{n,t}(h,lambda)=F_{n,t}(h)+lambda,SD_t(F_h),I(nin D_{t-1})
]

where (F_{n,t}(h)) is exponential frequency with half-life (h) draw steps, (SD_t(F_h)) is the cross-number population standard deviation of the 40 historical scores, and (D_{t-1}) is the previous draw. The lag bonus is standardized to the score dispersion, not a raw additive count.

Grid registered for this cycle: (hin{60,120,200,400}), (lambdain{0,0.25,0.5,1,1.5,2}) (24 models). Target splits are fixed by row index:
- discovery: targets 200–1699 (1,500);
- validation: 1700–2549 (850);
- blind OOS: 2550–3400 (851).

For every target, rank scores are computed from draws strictly before the target; target draw is incorporated only after scoring. Choose one configuration by maximum validation Top-5 hit count, ties favor lower (lambda), then lower (h). Primary endpoint is count of actual drawn numbers appearing in the model's candidate Top 5, divided by five target numbers. Random-ranking expectation is 0.625 hits/target = 12.5% of target numbers.

## Results — validation selection and blind evaluation

Selected by validation: **h=200, (lambda=2)**.

| Segment | Selected FD-07 | Same-half-life no-lag baseline (h=200, λ=0) | Lag-1-only Top 5 |
|---|---:|---:|---:|
| Discovery (1,500) | 935/7,500 = 12.4667% | 923/7,500 = 12.3067% | 961/7,500 = 12.8133% |
| Validation (850) | 539/4,250 = 12.6824% | 514/4,250 = 12.0941% | 535/4,250 = 12.5882% |
| Blind OOS (851) | 548/4,255 = 12.8790% | 559/4,255 = 13.1375% | 523/4,255 = 12.2914% |

The selected model is 11 hit counts below its matched no-lag baseline on blind OOS ((-0.2585) percentage points of the five-number hit share). The validation-selected lift does not transfer.

Paired block diagnostics against same-half-life no-lag baseline:
- block length 7; 121 complete non-overlapping blocks; final 4 target rows omitted from the block test;
- 50,000 sign-flip replicates, two-sided p = **0.64967**;
- 20,000 block-bootstrap replicates; 95% CI for mean hit-count difference per target: **[-0.05785, +0.03306]**;
- equivalent 95% CI for hit-share percentage-point difference: **[-1.157, +0.661]**.

## Random Top-5 null and multiple testing

For each target with five distinct actual numbers, random Top-5 overlap follows Hypergeometric((N=40,K=5,n=5)). A common null distribution for the blind aggregate was simulated using 20,000 replicates of 851 independent overlaps. One-sided upper-tail p-values were calculated for all 24 grid configurations plus the lag-1-only comparator (family size 25), followed by Holm adjustment.

- Selected h=200, λ=2: blind 548 hits; raw Monte Carlo p = **0.22219**, Holm p = **1.000**.
- Best uncorrected blind grid candidate h=200, λ=0.5: 572 hits (13.4430%); raw p = **0.02675**, Holm p = **0.66872**.
- Lag-1-only: 523 hits; raw p = **0.67242**, Holm p = **1.000**.

No model survives Holm correction. The best raw configuration is a post-hoc blind observation and is not selected/promoted.

## Prospective shadow freeze

Cutoff: **2026-11-07**. Shadow target date: **2026-11-08**. The validation-selected FD-07 model (h=200, λ=2) frozen Top 5 is:

**38, 16, 12, 31, 28**

This is a research ranking of individual candidates, not a full five-number lottery prediction or a betting recommendation. Freeze persisted separately; target outcome was not used.

## Integrity, reproducibility, limitations

- Canonical archive structural audit passed: dates strictly increasing; 5 distinct integers in [1,40] per row; exact bounds and count verified.
- Archive Git blob SHA pinned to `5d2efd70684e918b27d8f06386d545647898336d`.
- Strict-prior feature construction: historical score and lag-1 draw only; no target draw is added until after scoring.
- Model selection uses validation only; blind metrics and p-values are evaluation only.
- The Monte Carlo null is a random Top-5 selection benchmark. It does not prove lottery predictability; temporal independence is a modelling assumption for this null.
- The paired block test excludes four tail targets because 851 is not divisible by seven.
- This cycle's calculation was executed in the V8 CodeMode runtime against the fetched canonical CSV. The branch CI workflow was extended to run `node --check`, execute the persisted Node script, and compare its JSON output exactly with the saved result. At the final commit, the GitHub combined-status endpoint returned an empty status list; therefore the CI execution result is **not verified here** and is not counted as passed. Native Node execution remains unconfirmed in this run.
- No main update, PR, merge, or engine promotion. PR #6/#7/#8 remain outside this experiment.

## Decision and next action

**FD-07 fails as a candidate predictive lift.** Keep FD-01/FD-02/FD-05/FD-06 results frozen. Next, avoid searching further lag coefficients against this same blind segment; use append-only prospective scoring and, if another feature hypothesis is tested, pre-register one primary endpoint and family before new outcomes are observed. The prospective Q60 gate remains separate and is not incremented by this retrospective experiment.
