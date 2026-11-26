# VinciCasa SONAR — Q141 cycle 9 (2026-11-12)

**Status:** Q7 typed AST import and Q7 complexity walk-forward completed; exact remote Git readback verified.  
**Research branch:** `research/q141-formula-universe-behaviour-mapping-20261112`  
**PR:** #89, open and draft; no merge.

## 1. Recovered state

- Q141-A3 Q90 AST import: 330,429 typed per-number ASTs, remote readback previously verified.
- Q141-C3 rank consensus: no robust lift demonstrated.
- Q141-B6 Q7 rolling formula adaptation: no formula persistence lift demonstrated.
- Q7 source is pinned at commit `7a37cab601c5f9386131a00246963f8e4aeabf74`; its archive is 3,387 draws through 2026-10-24 and an exact prefix of the Q141 archive.
- Q7 contains 1,023 quintet-scoring formulas over 658,008 candidate quintets. It remains a distinct output type from Q80/Q90 per-number formulas.

## 2. Q141-A4 — Q7 typed AST import

Imported all 1,023 Q7 formulas as `quintet_score` AST records:
- 1,023 unique source formula IDs;
- 1,023 unique canonical AST IDs;
- 10 feature-family definitions preserved;
- additive smoothing alpha 0.5 and z-normalization over the complete candidate universe encoded;
- 1,023 source top-20 candidate snapshots for target 2026-10-25 retained separately from AST identity.

This is a structural import, not a predictive result.

## 3. Q141-B8 — formula complexity hypothesis

**Preregistered hypothesis:** within the fixed Q7 grammar, the number of included feature families (1–10) is positively associated with the next target's realized-quintet ranking percentile.

Source window: Q7 archive through 2026-10-24. Contest 315 and later Q141 suffix rows are excluded. The Q7 runner's score/write operation precedes `add_draw(state, draw)`; this order was checked against the pinned runner source. All 34 rank-matrix parts were SHA-256 verified, and every target date, prior cutoff, prior-draw count and actual quintet was reconciled.

Eligible targets: 3,286, with the preregistered 100-target burn-in and chronological splits:
- Discovery: 1,972
- Validation: 657
- Blind OOS: 657

### Split evidence

| Split | Mean per-target Spearman rho | Mean percentile across 1,023 formulas | High (6–10) minus low (1–2) percentile |
|---|---:|---:|---:|
| Discovery | +0.008905 | 0.500314 | +0.000091 |
| Validation | +0.010951 | 0.503292 | +0.001761 |
| Blind OOS | +0.005265 | 0.494254 | -0.004469 |

Random-quintet reference: mean percentile 0.5; expected one-based rank 329,004.5.

### Blind OOS registered tests

| Endpoint | Effect | 95% moving-block CI | Raw p | Holm p |
|---|---:|---:|---:|---:|
| Mean per-target Spearman rho (practical margin 0.02) | +0.005265 | [-0.005947, +0.016739] | 0.99545 | 1.000 |
| Mean percentile vs 0.5 | 0.494254 | [0.474798, 0.514058] | 0.73206 | 1.000 |
| High-low percentile delta (margin 0.005) | -0.004469 | [-0.013064, +0.004045] | 0.98765 | 1.000 |
| High-low Top-20 rate delta | 0 | [0, 0] | 1.00000 | 1.000 |

All four registered tests use block length 20, 20,000 block sign-flip replicates and Holm-Bonferroni correction. None supports the hypothesis. The primary upper confidence bound (+0.01674) is below the preregistered practical effect (+0.02).

A descriptive nuance: Blind OOS mean percentile by exact complexity level declines from 0.499846 at one family to 0.492529 at ten families. The mean within-target Spearman and the pooled complexity-stratum means are different estimands; the former is small and nonsignificant, while the high-vs-low mean contrast is negative and also nonsignificant. Do not interpret either as a causal complexity penalty.

## 4. Recovery and root-cause corrections

The first run computed the experiment and pushed outputs, but remote readback failed because manifest paths were stored relative to `reports/sequence_agent` while the verifier expected repository-relative paths.

Two subsequent attempts exposed the same path issue in the producer: `Path.relative_to` compared relative output paths to an absolute workspace root. The importer was corrected to use resolved absolute paths for both operands. The readback verifier was kept strict rather than weakened.

- First readback failure: workflow run 43283392442.
- Repeated pre-persistence path failure on the older checkout: 43283630715 / 43283652913.
- Corrected run: [43283772495](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43283772495), success.

The corrected run passed all 12 unit tests, completed AST import and walk-forward, persisted outputs, and verified five remote files by byte length, SHA-256 and Git blob SHA-1. Receipt: `q141_q7_ast_complexity_remote_readback_2026-11-12.json`.

Dedicated Q141-C3 run 43283772543 and Q90 AST run 43283772483 also completed successfully on code head `5430f24`. Broad repository CI was still pending at the last check; it is not claimed as passed.

## 5. Interpretation and limitations

- No complexity-associated predictive improvement was demonstrated.
- Mean Blind OOS percentile across all Q7 formulas was 0.494254, below the random reference 0.5, with an interval spanning 0.5.
- No formula reached Top-20 in the 657 Blind OOS targets across the fixed 1,023-formula Q7 family; this is descriptive and not a separate confirmatory claim.
- Holm controls the four B8 endpoints only, not the complete Q00–Q141 research family.
- Historical Blind OOS is exposed prior research history, not virgin prospective evidence.
- Q7 ranks complete quintets; do not merge its metrics with per-number Q80/Q90 metrics.
- No engine promotion, no shadow insertion, no canonical archive edit, no merge.

## 6. Next iteration — Q141-B9

Preregistered Q7 factorial attribution of 10 feature-family main effects and 45 pairwise interactions (55 endpoints). Each target uses only the pinned strict-prior rank vector. Main effects compare paired non-empty background subsets; pair interactions use balanced difference-in-differences over non-empty backgrounds. Blind OOS will use two-sided block sign-flip tests and Holm correction across all 55 endpoints. Execution is pending; no B9 results are claimed.

PR #89 remains open/draft and based on the older main SHA `0bf1ef0d39afb671ff83e519489f16b0c24eb15a`; current main has advanced. Rebase/integration remains a human-review task. PRs #6, #7 and #8 were not modified.
