# PSR-11 Protocol — Prior Top-20 overlap-state inclusion frequency

**Experiment ID:** SONAR_PSR11_PRIOR_TOP20_OVERLAP_STATE  
**Protocol state:** preregistered in repository before result computation (Git commit sequence recorded).  
**Archive pin:** `data/storico_daily.csv`; expected blob SHA `5d2efd70684e918b27d8f06386d545647898336d`; 3,401 draws through 2026-11-07.

## Quantitative hypothesis
Let (D_t) be the sorted five-number draw. Before target (t), construct a Top-20 set (T_{t-1}^{(100)}) by ranking number frequencies in the 100 draws strictly before the previous draw, rows (t-101,ldots,t-2), with ties resolved by ascending number. Define the previous-draw overlap state (R_t=|D_{t-1}cap T_{t-1}^{(100)}|), binned as (S_t=0) for (R_tin{0,1}), (S_t=1) for (R_tin{2,3}), and (S_t=2) for (R_tin{4,5}).
Hypothesis: (S_t) may condition the next draw's per-number inclusion frequencies.

For each target and number (n), strict-prior unconditional inclusion frequency is
(q_{0,t}(n)=C_t(n)/N_t), using only outcome draws (u=200,ldots,t-1).
The conditional estimate is
(q_t(n\mid S_t=s)=\frac{C_{s,t}(n)+\alpha q_{0,t}(n)}{N_{s,t}+\alpha}),
where (C_{s,t}(n)) counts prior outcome draws (u<t) whose ex-ante state (S_u=s) and which include (n); (N_{s,t}) is that state's prior outcome exposure. The candidate is the five numbers with largest (q_t(n\mid S_t)), ties ascending. This is a marginal inclusion ranking; it does not define a coherent joint probability over all 5-subsets.

## State reference under uniform 5-of-40
For a fixed Top-20 set and uniform 5-subset, (R\sim Hypergeometric(40,20,5)), with exact mass
(P(R=r)=\binom{20}{r}\binom{20}{5-r}/\binom{40}{5}).
The fixed state bins have masses 0.17082467082467082, 0.6583506583506583, 0.17082467082467082 (exact counts 112404, 433200, 112404 out of 658008). These are null reference masses, not fitted cutpoints.

## Walk-forward / splits
- Warm-up target index (t=300) (zero-based); score targets (t=300,ldots,3400), total 3,101.
- For each target, predictor state uses (D_{t-1}) and a frequency ranking from rows (t-101,ldots,t-2), never target (D_t).
- Conditional and global outcome counts update only after the target score; training outcomes are (u=200,ldots,t-1) only.
- Chronological splits: discovery [300,1700) = 1,400; validation [1700,2550) = 850; blind historical tail [2550,3401) = 851.
- Alpha grid fixed before computation: {0,25,50,100,200,500,1000}. Select alpha on validation by Top-5 hit count vs actual; tie-break lower multiclass inclusion Brier, then larger alpha. Discovery is descriptive; no parameter selection on the tail.
- Baseline 1: strict-prior unconditional inclusion frequency (q_0), Top-5 ranked from the same training outcomes. Baseline 2: exact uniform Top-5 reference (expected hit-share 12.5%).

## Endpoints and inference
- Primary: Top-5 hit-share (number of actual drawn values contained by the frozen candidate Top-5 divided by (5\times targets)).
- Secondary: mean per-target inclusion Brier (40 binary inclusion labels), log-loss, Top-10/Top-20 coverage, and mean rank; descriptive unless specified.
- Blind tail: exact one-sided uniform-null p-value for total Top-5 hits via convolution of the Hypergeometric(40,5,5) overlap distribution across targets.
- Paired model-vs-unconditional baseline: block sign-flip test on target-level Top-5 hit difference and Brier gain, block length 7, 20,000 replicates, deterministic PRNG; percentile moving-block bootstrap 95% CI, 2,000 replicates, block length 7. Use only 121 complete blocks (847 targets); report the four-target tail omitted from paired block inference.
- Holm correction across the 21 preregistered blind tests: 7 alpha configurations × (exact Top-5 uniform null, paired Top-5 gain vs global frequency, paired Brier gain vs global frequency). Family-wise alpha 0.05.

## Integrity gates
Validate canonical archive blob SHA, unique increasing dates, five distinct integers 1..40 per draw; strict prior target cutoff; state window excludes (D_{t-1}) from the frequency ranking; all state exposure counts and candidate lists are deterministic; no duplicate candidates; persist target ledger with target/cutoff, state, training exposure, alpha, Top-5, actual, hit counts and target losses; replay committed outputs byte-for-byte in CI.

## Interpretation / guardrails
The 2025-02-05 through 2026-11-07 historical tail has been exposed in previous SONAR research; this is not independent or prospective confirmation. Conditioning on past frequency overlap is only a statistical hypothesis; no physical fluid-dynamics mechanism is implied. No live shadow insertion, engine promotion, merge, or automatic PR merge. Q60 prospective gate remains separate and append-only.
