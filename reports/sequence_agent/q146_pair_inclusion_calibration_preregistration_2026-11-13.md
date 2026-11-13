# Q146 — Pair-inclusion calibration audit of Q145 rank-to-subset PMFs

## Status
Preregistered before computing Q146 pair-level outcomes. Research-only. No freeze, canonical archive, active engine, Q60 gate, or existing PR is modified.

## Question and hypothesis
Q145 maps each frozen Top20 ranking to a fixed-size 5-of-40 probability mass function (PMF). Q145 evaluated complete-quintet log likelihood and single-number marginal Brier score. Q146 tests a distinct implication: whether the same PMF supplies useful *pairwise co-inclusion marginals*.

For a 40-number weight vector w and unordered pair {i,j}, define

P(i,j included) = w_i w_j e_3(w excluding i,j) / e_5(w),

where e_k is the k-th elementary symmetric polynomial. Under the uniform 5-of-40 null, every pair has probability 10 / C(40,2) = 1/78.

The primary hypothesis is that Borda's mean target-level pairwise Brier improvement over the uniform pair baseline is at least +0.00005, with positive validation and historical blind-OOS point estimates. This is a marginal pair calibration diagnostic, not a joint 780-dimensional likelihood and not a claim that pair events are independent.

## Frozen models and data
- Borda Q144 Top20, equal-type-inclusion Q144 Top20, and APP Top20 where available.
- Rank utility and temperature are exactly Q145: u(r)=(21-r)/20 for ranks 1..20, zero outside; w=exp(u), T=1.
- No parameter fitting, rank changes, or model selection.
- Q144 target ledger and Q145 source archive/shadow/manifest hashes are pinned in code.
- Q145 upstream verifier must pass before Q146 evaluation.
- Q145 2026-11-13 prospective freeze remains untouched and outcome-pending.

## Endpoints
1. Primary: per-target mean pairwise Brier gain vs uniform, averaged over the 780 unordered pairs.
2. Secondary: per-target mean pairwise Bernoulli composite log-score gain vs uniform. This is a sum of marginal pair scores, not the joint log probability of the five-number subset.
3. Paired comparisons: Borda vs equal-type inclusion; Borda vs APP.

For each target, the 10 observed pairs are the 10 unordered pairs among the five drawn numbers. The model's 780 pair inclusion probabilities must sum to 10 (within 1e-10); the observed pair count must equal 10. Uniform pair probability is 10/780.

## Chronological splits
Use the existing 31 Q144 target rows in chronological order without reordering:
- Discovery: first 18.
- Validation: next 6.
- Historical blind OOS: final 7.

These are historical splits, not a virgin prospective test. APP is available on 19 rows (6/6/7). The 2026-11-13 Q145 freeze is not part of these historical scores.

## Inference and multiplicity
- 20,000 circular moving-block bootstrap replicates, block length 2, resampling target-level scores (never individual pairs).
- Exact two-sided sign-flip enumeration for the 7 blind targets (128 assignments); symmetry/exchangeability is an assumption and will be stated.
- Holm correction across five registered blind endpoints: Borda vs uniform, inclusion vs uniform, APP vs uniform, Borda vs inclusion, Borda vs APP.
- Report Discovery, Validation, and Blind point estimates, confidence intervals, raw p-values, and Holm-adjusted p-values.
- Because the PMF was specified after Q144 historical outcomes were inspected, all historical Q146 inference is exploratory. The seven-row blind segment is not confirmatory.

## Decision rule
Q146 is a diagnostic only. No engine promotion or prospective freeze is allowed. The primary hypothesis is not supported unless the primary Borda endpoint has (a) mean gain >= +0.00005, (b) a positive block-bootstrap 95% interval, (c) Holm-adjusted p <= 0.05, and (d) positive Validation and historical Blind point estimates. Failure means retain the Q145 model unchanged and wait for the append-only prospective sample.

## Leakage and reproducibility
- Re-run the Q145 upstream verifier against pinned source hashes.
- Validate each historical target against the canonical archive.
- Validate all 1,364 shadow rows and their strict-prior cutoff / pre-draw freeze timestamps through the upstream verifier.
- Validate Q144 Top20 uniqueness, range, hit counts, and APP availability flags.
- Deterministic seed per endpoint; deterministic replay must produce byte-identical report and ledger.
- Do not use target outcomes to construct or alter the target's frozen ranking.
