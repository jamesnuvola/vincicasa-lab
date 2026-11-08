# SONAR FD-06 — Q90 P5 logistic paired audit against the exact order-statistic null

**Status:** EXPLORATORY / NO PREDICTIVE LIFT / NO PROMOTION  
**Branch:** `research/fd06-q90-p5-orderstat-audit-20261108`  
**Parent:** `76ab0f33aa261a2dcb0d8c5f6f59889facb32c13` (main snapshot)  
**Scope:** Q90 pooled P5 logistic model, feature lineage, paired comparison to descending numeric order.

## Root-cause hypothesis

The prior Q90 P5 logistic report stated 288/673 Top-5 hits (42.7935%) against a 12.5% uniform-rank baseline. FD-04 established that P5 is the maximum order statistic of five numbers sampled without replacement from 1..40. Under the uniform lottery null:

`P(P5=n)=C(n-1,4)/C(40,5), n=5,...,40`.

Descending numeric order is the exact-null ranking. Its theoretical Top-5 set is 36–40, with a 50.6644% hit probability, not 12.5%. FD-06 therefore reproduces the fixed logistic model and compares it target-by-target with the numeric-order ranking.

## Artifact provenance and feature-lineage audit

- Q90 GitHub Actions run: `42267331734`; bundle artifact ID `13528333502`.
- Artifact digest: `sha256:9776534d6ed968cf70c3863e500684430f1086db3124b0e7e3d1ae60c3d4842`.
- Canonical archive blob SHA in the bundle: `dc555356fe6543e17c3d7c91969da10491fe8b4e` (3,398 draws through 2026-11-04).
- Q89 feature matrix: SHA256 `3520db2c9441b9fc48bd091c746564a6de261b18a0cb2eea293bb465bbcfd824`, shape `[3348,40,59]`, dtype float32.
- Q90 target ledger: SHA256 `290a4da31f05bb4d73f4155ec1408b0a0c2e9e6df1479fafb6bd1c410c285404`, 3,348 rows.

Checks performed on the persisted matrix and ledger:
- 3,348 target dates strictly increasing and daily; every cutoff equals the previous calendar date.
- Target dates, cutoffs, actual quintets and prior-draw counts align exactly between NPZ and Q90 ledger.
- 59 unique feature names; matrix finite; quintets contain five distinct ascending integers in 1..40.
- Source review of Q89 feature generator confirms its feature function uses `draws[:i]`; EWMA and other historical state updates occur after target scoring; the feature tensor row is stored before the target update. Actual quintets are used to construct labels/evaluate ranks, not included among the 59 input features. No direct target/future leakage was found in this inspected path.

## Model reproduction protocol

- Input: the immutable Q89 feature matrix plus Q90 target ledger from the bundle.
- Target label: one positive candidate per target, the actual maximum P5 among candidate numbers 1..40.
- Model: `StandardScaler` fitted on training rows only, then `LogisticRegression(C=0.05, max_iter=300, solver="lbfgs")`; 59 features.
- Stable descending probability rank; ascending candidate number breaks exact ties.
- Primary fixed holdout: train target dates through 2024-12-31 (2,675 targets); test 2025-01-01 through 2026-11-04 (673 targets).
- Secondary chronological Q90 split checks use the fixed C=.05 model at each split boundary. Discovery uses first 200 targets as warm-up and evaluates the remaining 1,809 discovery targets. Validation trains on discovery (2,009 targets); blind OOS trains on discovery+validation (2,679 targets). These split checks are secondary/exploratory.

## Exact order-statistic baseline

| Metric | Theoretical exact-null baseline |
|---|---:|
| Top 5 candidates (36–40) | **50.6644%** |
| Top 10 candidates (31–40) | 78.3428% |
| Top 20 candidates (21–40) | 97.6438% |
| Expected rank of actual P5 under descending numeric order | 6.8333 |

## Primary holdout — paired results

| Metric | Q90 logistic | Numeric-order baseline on same 673 targets |
|---|---:|---:|
| Top 1 | 70/673 = 10.4012% | 83/673 = 12.3328% |
| Top 5 | **288/673 = 42.7935%** | **350/673 = 52.0059%** |
| Top 10 | 492/673 = 73.1055% | 516/673 = 76.6716% |
| Top 20 | 610/673 = 90.6389% | 653/673 = 97.0282% |
| Mean rank of actual P5 | 8.7519 | 7.0624 |

- Paired Top-5 delta (logistic minus numeric): **-9.2125 percentage points** (-62 net hits).
- Discordant targets: 56 logistic-only wins versus 118 numeric-only wins (174 total).
- Exact paired McNemar two-sided p = `2.9874e-6`.
- Chronological block sign-flip, non-overlapping block length 7, 200,000 replicates, seed 20261108: two-sided p = **1.5000e-5**.
- Circular moving-block bootstrap (block 7, 20,000 replicates): 95% CI Top-5 delta **[-12.7786, -5.6464] pp**; mean-rank delta CI **[+1.3551, +2.0342 ranks]**.

The reproduction matches the prior reported logistic result exactly at 288/673 Top-5 hits. Relative to the appropriate order-statistic baseline, the model is worse, not better.

## Chronological split checks

| Segment | Train targets / cutoff | Evaluated targets | Logistic Top 5 | Numeric Top 5 | Delta | Mean rank logistic / numeric | Holm p (block sign-flip; 3 split family) |
|---|---|---:|---:|---:|---:|---:|---:|
| Discovery (after 200-target warm-up) | 200 through 2018-03-23 | 1,809 (2018-03-24–2023-03-06) | 46.8767% | 50.1382% | -3.2615 pp | 8.7242 / 6.9900 | 0.002400 |
| Validation | 2,009 through 2023-03-06 | 670 (2023-03-07–2025-01-04) | 44.9254% | 50.5970% | -5.6716 pp | 8.2866 / 6.7269 | 0.014190 |
| Blind OOS | 2,679 through 2025-01-04 | 669 (2025-01-05–2026-11-04) | 43.1988% | 52.0179% | -8.8191 pp | 8.7564 / 7.0732 | 0.000090 |

Secondary block sign-flip raw two-sided p values were 0.001200 (discovery), 0.014190 (validation), and 0.000030 (blind OOS); Holm correction was applied across these three split comparisons. The correction does **not** cover the wider historical SONAR model/feature search. The split results are exploratory and support the same direction: logistic ranking underperforms numeric order.

## Decision and limitations

**FD-06 is a valid paired null/negative diagnostic. No P5 logistic predictive lift is established; do not promote this model.** Keep descending numeric order as the required P5 reference baseline for future comparisons.

Limitations:
- Q90 artifact ends 2026-11-04; subsequent archive rows are outside this audit.
- Block sign-flip assumes exchangeable block signs under the null; exact McNemar is also provided but assumes target-level independence.
- This audit fixes one logistic specification (C=.05); it does not retrospectively correct for every model or feature experiment previously tried.
- This is a retrospective audit, not prospective evidence and not a lottery recommendation.

## Persistence and next action

Artifacts are persisted on this isolated research branch: script, compact result JSON and this report. Local artifact execution completed twice with byte-identical JSON output. Repository CI is still to be checked at the final branch head; this cycle does not alter main or PR #6/#7/#8, and no merge/PR/promotion is authorized.

Next: preserve the P5 order-statistic baseline; test any residual/feature-family hypothesis only against this baseline, register the primary endpoint and correction before evaluation, and keep prospective shadow freezes append-only. Q60 prospective promotion remains separate and is not advanced by this retrospective audit.
