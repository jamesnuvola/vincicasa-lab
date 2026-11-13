# Q141-A16 — Spectral Formula Behaviour Mapping

**Decision:** STABLE_LOW_DIMENSIONAL_RANK_BEHAVIOUR_STRUCTURE_DETECTED_EXPLORATORY

The leading six-dimensional rank-behaviour subspace is stable across the two historical holdouts, but this is a structural result, not a prediction claim.

## Split spectra

| Split | Targets | Participation ratio | Entropy rank | k80 | k90 | Top-6 variance |
|---|---:|---:|---:|---:|---:|---:|
| discovery | 2031 | 7.578 | 10.918 | 6 | 8 | 81.09% |
| validation | 677 | 7.295 | 10.492 | 6 | 8 | 81.97% |
| blind_oos | 678 | 7.159 | 10.424 | 6 | 8 | 81.79% |

## Holdout eigenspace stability

| Holdout | Observed overlap | Random-subspace mean | Random q99 | Exceedances / 20,000 | Raw p | Holm p |
|---|---:|---:|---:|---:|---:|---:|
| Validation | 0.855889 | 0.046895 | 0.074793 | 0 | 0.00005000 | 0.00010000 |
| Blind OOS | 0.831053 | 0.046966 | 0.074517 | 0 | 0.00005000 | 0.00010000 |

Discovery k80 = 6. Random-subspace expectation k/128 = 0.046875.

## Interpretation and limits

- A15's participation ratio of approximately 7.58 is reproduced in Discovery; Validation and Blind OOS are approximately 7.30 and 7.16.
- The six-dimensional Discovery subspace explains at least 80% of the rank-residual correlation trace in all three splits.
- Both holdout overlaps exceed the registered 0.75 threshold and geometric random-subspace null after Holm correction.
- This supports stable low-dimensional structure in sampled formula rank trajectories, not predictive power, causal structure, or semantic AST equivalence.
- Historical Blind OOS is exposed to prior SONAR research; future predictive confirmation requires a new frozen signal and prospective outcomes.

The 3,386-row target ledger, 384-row eigenspectrum, component loadings, protocol, validation and checkpoint are persisted alongside this report.
