# PSR-12 Protocol — Lag-1 number-inclusion transition

**Experiment ID:** SONAR_PSR12_LAG1_INCLUSION_TRANSITION  
**Status:** exploratory historical study; no promotion or shadow insertion.  
**Protocol commit sequence:** registered on the isolated research branch before the deterministic replay that will generate the persisted result bundle. An earlier in-session calculation was exploratory and is not treated as independent confirmation.  
**Canonical archive:** `data/storico_daily.csv`; expected Git blob SHA `5d2efd70684e918b27d8f06386d545647898336d`; 3,401 draws, 2017-07-17 through 2026-11-07.

## Quantitative hypothesis

For number n and target index t, let (Y_{n,u}=1[n\in D_u]). The strict-prior unconditional inclusion baseline is

[
q_{0,n,t}=\frac{\sum_{u=0}^{t-1}Y_{n,u}}{t}.
]

Let the lag-1 state for each number be (A_{n,u}=1[n\in D_{u-1}]), for outcome rows (u=1,\ldots,t-1). Define prior-only exposure and transition counts

[
E_{n,t}=\sum_{u=1}^{t-1} A_{n,u},\qquad
C_{n,t}=\sum_{u=1}^{t-1} A_{n,u}Y_{n,u}.
]

For shrinkage alpha,

[
p_{1,n,t}(\alpha)=\frac{C_{n,t}+\alpha q_{0,n,t}}{E_{n,t}+\alpha}.
]

The ex-ante inclusion score for target t is

[
\hat q_{n,t}(\alpha)=
\begin{cases}
p_{1,n,t}(\alpha), & n\in D_{t-1},\\
q_{0,n,t}, & n\notin D_{t-1}.
\end{cases}
]

The candidate Top-5 ranks descending (hat q), with ties broken by ascending number. This tests a per-number transition effect, not a joint distribution over all 5-subsets; no exact five-number coherence is claimed.

## Fixed design

- Warm-up: target index t=200 (zero-based); total scored targets 3,201.
- Discovery: t in [200,1800), 1,600 targets; 2018-02-02 through 2022-06-20.
- Validation: t in [1800,2600), 800 targets; 2022-06-21 through 2024-08-28.
- Blind historical OOS: t in [2600,3401), 801 targets; 2024-08-29 through 2026-11-07.
- Alpha grid fixed: {0,25,50,100,200,500,1000}.
- Validation-only selection: maximize mean inclusion Brier gain (baseline minus candidate); tie-break by log-loss gain, then Top-5 hit-share gain, then larger alpha. Discovery is descriptive; blind tail is not used for alpha selection.
- Baseline: strict-prior global inclusion frequencies (q_0), with the same Top-5 ranking/tie rule.

## Endpoints and inference

- Primary proper score: per-target 40-label inclusion Brier; gain = baseline Brier − candidate Brier.
- Secondary: Top-5 hit-share (intersection count / (5\times targets)) and binary marginal inclusion log-loss; gains are baseline minus candidate.
- Blind-tail grid audit: 7 alphas × 3 paired endpoints = 21 tests plus 7 exact uniform-null Top-5 tests. Under uniform 5-of-40, each target Top-5 overlap follows Hypergeometric(40,5,5); aggregate tail probabilities are computed by exact discrete convolution across blind targets. Paired model-vs-global tests use one-sided block sign-flip, 20,000 replicates, non-overlapping complete blocks of length 7. Holm-Bonferroni covers the full 28-test family, family-wise alpha 0.05.
- 95% intervals: deterministic circular moving-block bootstrap, block length 7, 2,000 replicates. Point metrics use all 801 blind targets; inference uses 114 complete blocks (798 targets), omitting the final 3-target tail only from block inference.
- Fixed PRNG seed: 20261108. All output canonicalization is deterministic.

## Integrity gates

- Verify archive Git blob SHA, 3,401 row count, strict ascending unique dates, 5 distinct integers in [1,40] per draw.
- For every target, global training outcomes are rows [0,t); lag-state training outcomes are rows [1,t); target D_t is never included in counts or state estimation.
- Verify cutoff = date[t−1] < target date[t], train_n=t, global count total=5t, and lag exposure total=5(t−1).
- Check all scores are finite and in [0,1], target ledgers have unique ordered keys, and exact replay matches persisted JSON/CSV byte-for-byte.
- Synthetic tests cover lag state, shrinkage endpoints, strict-prefix isolation, range and deterministic replay.

## Interpretation and guardrails

The historical blind tail has been inspected in prior SONAR work and is not independent confirmation across the project. Any nominal effect is exploratory and must be adjusted for the declared PSR-12 test family; broader experiment-selection bias remains. A marginal inclusion model is not a coherent joint lottery model. Do not alter Q60 freezes, add PSR-12 to the prospective shadow stream, merge automatically, or promote any engine. Next action is to reconcile the already-frozen 2026-11-08 Q60 target only after the official result is available, then continue append-only prospective collection.
