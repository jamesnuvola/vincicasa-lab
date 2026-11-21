# VinciCasa SONAR — Q141 cycle 14 (2026-11-13)

## Q141-A6 — Full-59 covering sample

**Decision: `FULL59_COVERING_SAMPLE_LIFT_NOT_DEMONSTRATED`.** The historical walk-forward completed; no predictive engine is promoted.

### Design and lineage
- Pinned Q90 source bundle SHA-256: `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`; all 17 source members verified.
- Source feature matrix: 3,351 × 40 × 59, float32; Q90 archive through 2026-11-07, an exact prefix of the Q141 archive used by the run (3,405 draws). Four later Q141 rows were excluded.
- Deterministic sample: 5,550 formulas per scope (Full-59 and Selected-20), 11,100 formula IDs; 350 quartets, all 1,711 possible feature pairs covered in Full-59. Grammar per scope: 650 linear means, 2,100 pairwise interactions, 2,800 gates.
- Seed: `14120261113`. The Selected-20 scope is a Discovery-selected historical control, not a neutral random control.
- Walk-forward: 3,351 strict-prior targets; Discovery 2,011, Validation 670, Blind OOS 670; 2017-09-05 through 2026-11-07; 50 prior draws at the first target.

### Results (Top-5 per-number ranking hit share)
| Split | Full-59 | Selected-20 | Full-59 minus Selected-20 |
|---|---:|---:|---:|
| Discovery | 12.6118% | 12.8301% | -0.2183 pp |
| Validation | 12.1962% | 12.1340% | +0.0622 pp |
| Blind OOS | 12.4639% | 12.4583% | +0.0056 pp |

Uniform reference: 12.5%.

Blind OOS Full-59 minus Selected-20:
- Difference: +0.00005578 ( +0.00558 percentage points).
- 95% circular moving-block CI: [-0.002759, +0.002819] ([-0.2759, +0.2819] pp).
- Two-sided non-overlapping 20-target block sign-flip p=0.97085; Holm p=1.000 across the two registered endpoints.
- Practical threshold: +0.005 (0.5 pp), not reached.

Blind OOS Full-59 minus uniform:
- Difference: -0.00036109 (-0.03611 pp).
- 95% CI: [-0.005137, +0.004557]; raw p=0.89481; Holm p=1.000.

No meaningful or statistically supported lift is demonstrated. Full-59 and Selected-20 are both slightly below the uniform Top-5 reference in Blind OOS. The Discovery/Validation/Blind direction is not stable.

### Independent audit and recovery
- 7/7 deterministic tests passed; all 59 features and all 1,711 pairs covered; strict-prior cutoff and score-before-state-update checks passed in the runner.
- Re-read all 3,351 ledger rows independently: contiguous target index, increasing dates, every cutoff before target, prior_draws = index + 50, valid sorted unique five-number outcomes in 1..40, split counts correct, and Top-5 deltas reconcile exactly within floating tolerance.
- Formula catalog: 11,100 unique formula IDs. Each scope has 5,550 unique ASTs. Across both scopes there are 11,085 unique AST IDs because 15 ASTs (the L4/I4/G4 variants of one shared four-feature set) occur in both scopes. This is cross-scope overlap, not within-scope duplication; it makes the scopes slightly less independent and is retained in the audit.
- Q90 scoring replay: 56 formulas × 3 splits = 168 comparisons; maximum absolute discrepancy 2.7756e-17 against tolerance 1e-12.
- Historical Blind OOS is already exposed to prior SONAR research; it is not virgin prospective evidence. The experiment measures average per-number Top-5 ranking quality, not a direct five-number ticket forecast.

### Workflow and persistence status
- Dedicated Actions run [43336028371](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43336028371) completed successfully; job 131592298275, 7/7 tests passed, walk-forward and reproducibility steps succeeded, artifact 13997032604 uploaded.
- The workflow's explicit repository-persist step was **skipped**. However, the five output files were already present in the Q141 research branch. Their remote Git blob SHA-1 values match the manifest and independently computed local Git blob IDs; SHA-256 and byte counts also match for the three manifest outputs and the manifest itself. The A6 checkpoint was updated to `REMOTE_GIT_READBACK_VERIFIED` and read back after the update.
- Artifact ZIP SHA-256: `e139ed4587f04ae584c12bff76bcb49d7cd397d41d7fde5a159cc487570ea3fc`.
- Main advanced separately to `05f84e57fd0d2028c3f641742e39db4f1629db8c), which adds the 2026-11-12 draw to `data/storico_daily.csv` (and `src/data.json`). The Q141 research branch remains divergent; no rebase or merge was performed.

### Next action — Q141-A7
Do not tune or reselect formulas using this historical Blind OOS. Rebuild the full 59-feature matrix from the latest canonical archive now including the 2026-11-12 draw, independently audit every feature's strict-prior lineage, and create a clean prospective/forward protocol. Use a new isolated research branch based on current `main`; do not rebase/merge PR #89 automatically. Keep Q7 quintet scores separate from Q80/Q90 per-number scores. PRs #6, #7 and #8 remain untouched.
