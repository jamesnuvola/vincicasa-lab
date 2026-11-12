# Q141-C3 — Canonical Formula Rank Consensus

**Registration:** 2026-11-12  
**Status before execution:** preregistered; no outcome metrics computed  
**Source:** `data/storico_daily.csv`, Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`  
**Eligible source:** 3,404 draws through 2026-11-10; contest 315 / 2026-11-11 excluded  
**Parent registry:** Q141-B1 canonical Q80 equal-weight subset registry

## Hypothesis

A number supported by many algebraically distinct Q80 formulas may rank more reliably than a number selected by averaging six coarse feature families or 25 individual features. A rank-based consensus may be more robust than averaging formula scores because formula outputs have different scales and can contain near-ties.

Primary confirmatory hypothesis: the Borda mean-rank consensus over a fixed, deterministic sample of canonical formulas improves Blind OOS Top-5 number-hit share by at least **0.005 absolute** over the equal-family baseline, with a positive 95% block-bootstrap lower bound and Holm-adjusted paired block sign-flip p < 0.05.

This is a research test, not a claim that number outcomes are predictable.

## Frozen formula sample

Use the Q141-B1 deterministic sample of 120 raw equal-weight Q80 formulas: 12 per raw subset size k=1..10, seed 14120261112. Collapse only exact alias-equivalent formulas using Q141-B1's canonical weighted-mean signatures. Expected sample: 113 unique canonical formula IDs. Each unique ID receives one vote; raw alias multiplicity does not increase its weight.

The sample is not exhaustive over the 9,808,263 canonical formulas. No formula is selected by Discovery performance.

## Frozen ranking policies

For each target and each formula, evaluate its canonical weighted mean on the 40 candidates using only the strict historical prefix, then rank candidates with ascending-number tie-breaks.

1. **Borda mean-rank:** rank candidates by their mean rank across the 113 unique formulas (lower is better).
2. **Median-rank:** rank by the median of the 113 formula ranks.
3. **Top-5 vote:** rank by the number of formula Top-5 votes; ties are broken by mean rank, then ascending number.

Controls:
- **Equal-family:** equal average of the six Q80 family score vectors defined in Q141-C0.
- **Equal-feature:** equal average of the 25 exact canonical Q80 feature columns.

No weights, thresholds or formula sample members are tuned on target outcomes.

## Walk-forward and splits

- Strict-prior feature state: target i may use only draws with index < i; score target before updating history.
- Minimum prior history: 50 draws.
- Expected scored targets: 3,354.
- Chronological splits: Discovery 2,013; Validation 671; Blind OOS 670.
- Discovery is descriptive for this frozen experiment; Validation and Blind OOS are not used to tune the three consensus rules.
- Historical Blind OOS is exposed SONAR research history, not virgin prospective evidence.

## Endpoints and inference

Endpoints: Top-5, Top-10, Top-20 number-hit share and mean rank of the five realized numbers.

Paired comparisons: each of the three consensus policies against both controls, on Validation and Blind OOS, across all four endpoints: 48 tests total. Use non-overlapping chronological 20-target block sign-flip tests (20,000 deterministic Monte Carlo replicates), circular moving-block bootstrap 95% intervals (20,000 replicates), and Holm-Bonferroni over the complete 48-test family.

Uniform 5-of-40 reference: expected Top-5/10/20 shares 0.125 / 0.25 / 0.5 and mean realized-number rank 20.5. Exact per-target Hypergeometric(40,k,5) convolution tests for each consensus policy × Validation/Blind × Top-5/10/20: 18 tests, Holm-Bonferroni across all 18.

Primary gate: Blind Borda-vs-equal-family Top-5 delta >= +0.005, lower 95% block-bootstrap bound > 0, and Holm-adjusted p < 0.05. All other results are secondary/descriptive; no post-hoc promotion.

## Leakage, bias and reproducibility controls

- Pin and verify source archive Git blob and cutoff; exclude contest 315.
- Formula sample and canonical IDs are deterministic and frozen before execution.
- Feature state updates only after scoring the target.
- Synthetic tests mutate target outcomes and future suffixes; pre-target formula ranks must remain unchanged.
- Stable `math.fsum` canonical formula scoring; ascending-number deterministic tie-break.
- Report all 113 formula IDs and raw representations, all target-level outcomes, seeds, split counts, endpoints, p-values, adjusted p-values and intervals.
- Persist catalog, target ledger, report, manifest and checkpoint; verify exact Git readback.
- No canonical archive mutation, shadow insertion, engine promotion, automatic merge or changes to PRs #6/#7/#8.

## Interpretation limits

This experiment tests a deterministic sample of 113 canonical Q80 subset-mean formulas, not the entire 9,808,263-formula universe, Q90 interactions/gates or Q7 quintet-ranking formulas. Formula ranks are highly dependent because formulas share input features; this is not an independent-voter model. Holm controls the preregistered 48 paired and 18 uniform-null tests for this experiment, not the full Q00–Q141 research history. A null result does not establish that all formulas are useless; a positive historical result would still require prospective frozen forecasts.

## Next action

If no robust consensus lift is found, do not tune the consensus rules against Blind OOS. Prioritize durable Q90 AST import and Q7 typed-output integration, then design a new common-source behaviour atlas.
