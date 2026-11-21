# VinciCasa SONAR — Q141 cycle 12

**Cycle:** Q141-C6 — prior-only Q80/Q90 selector-transition state  
**Execution date:** 2026-11-12  
**Dedicated workflow:** [43319706282](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43319706282) — success  
**Branch:** `research/q141-formula-universe-behaviour-mapping-20261112`

## Recovered state

Q141-C5 was already complete and remotely read back before this cycle. Its primary result was no incremental Q90 transfer lift: Blind OOS MAE improvement -0.00012838, 95% moving-block interval [-0.00109252, 0.00084291], one-sided block sign-flip p=0.59487.

C5's manifest retained the Q80 report/manifest hashes from an earlier Q80 replay. The current Q80 report and manifest had since been regenerated, while the Q80 target ledger SHA-256 and archive lineage remained unchanged. C6 detected this source-lineage drift, allowed only those two documented metadata files, and revalidated the current Q80 report, manifest, archive identity and unchanged ledger hash. All other C5 lineage entries and both C5 output files remained exact. This recovery is recorded in the C6 report.

## New quantitative hypothesis

The occupancy entropy and switch rate of the previous 50 fully active Q80/Q90 selector labels may add information about next-target Q7 formula-universe meta-quality beyond the fixed Q7+Q80+Q90 rolling-state model.

- M2: nine existing Q7/Q80/Q90 rolling predictors.
- M3: M2 plus four prior-only transition predictors (Q80 switch rate/entropy; Q90 switch rate/entropy).
- Fixed ridge alpha 1.0; training-only standardization; no tuning.
- Training begins at target offset 100; first scored Discovery target offset 150.
- Expanding-prequential Discovery; coefficients frozen for Validation and Blind OOS.
- 50 previous labels only; no warm-up labels and no oracle family labels.
- One confirmatory endpoint: Blind OOS MAE(M2) - MAE(M3), practical threshold +0.005.

## Measured results

| Split | Targets | M2 MAE | M3 MAE | MAE improvement |
|---|---:|---:|---:|---:|
| Discovery | 1,822 | 0.203899 | 0.204624 | -0.000725 |
| Validation | 657 | 0.203712 | 0.203689 | +0.000023 |
| Blind OOS | 657 | 0.205286 | 0.205594 | -0.000308 |

Blind OOS primary:
- Improvement: **-0.00030843** (negative means M3 is worse).
- 95% circular moving-block interval: **[-0.00125377, +0.00057576]**.
- One-sided block sign-flip p: **0.735113**.
- Practical threshold: +0.005.
- Decision: **NO_Q80_Q90_TRANSITION_STATE_LIFT_DEMONSTRATED**.

The four transition summaries therefore do not demonstrate incremental predictive value. No multiplicity correction was needed for the single preregistered confirmatory endpoint; all other model comparisons and correlations remain descriptive.

Blind OOS descriptive state: Q80 mean switch rate 0.06958 and normalized family entropy 0.25033; Q90 mean switch rate 0.12565 and entropy 0.33361. Their correlations with Q7 meta-quality were small (absolute value at most 0.07765); no inferential claims are made from these descriptive associations.

The target is Q7 formula-universe meta-quality, not the winning quintet or winning numbers. Q90 remains a fixed 700-formula sample from 330,429, and its 20-feature subset was selected within its own Discovery process. Historical Blind OOS has prior SONAR exposure and is not virgin prospective evidence.

## Recovery and validation

Three initial attempts did not complete:
1. C5 lineage check found the Q80 report/manifest metadata replay drift; only these two entries were permitted after exact Q80 ledger/archive revalidation.
2. A subsequent run exposed the C5 report schema key mismatch (primary_blind_oos); corrected without changing the preregistered endpoint.
3. Workflow quoting for shell array expansion and Git blob NUL/newline checks was corrected before the final run.

Final run 43319706282:
- 6 synthetic tests passed.
- Walk-forward completed: 3,136 scored targets (1,822 / 657 / 657).
- 3,286 source rows aligned; 0 mismatches.
- Deterministic full replay passed.
- Output persistence passed.
- Exact remote Git readback passed for 2 output files and 22 code/source lineage entries.
- Checkpoint status: REMOTE_GIT_READBACK_VERIFIED.

The C6 report, target ledger, manifest, checkpoint and remote-readback receipt are persisted. The remote manifest blob is `2cef2dd7ad86211eb348aef0b1141839397f3083`; report blob `89209a8b3648e779e7857ed72c748648c569d646`; ledger blob `5fcbdb89ec03d98aafc0fc585553a961210a8577`.

## Repository governance

PR #89 remains open and draft. The research branch is still behind main by two commits; no rebase or merge was attempted. The general CI check remains action-required/pending and is not claimed as passed. Q141-C3 completed successfully on the same head; Q141-A3 was still running at the time of this report. PRs #6, #7 and #8 were not modified. No canonical archive mutation, forecast insertion or engine promotion occurred.

## Next iteration

**Q141-A5 — full Q90 AST-to-feature lineage and redundancy audit.** Reconcile all 330,429 typed Q90 ASTs with the 59 source features and the 20-feature Discovery-selected subset; quantify feature coverage, operator/family duplication, exact versus semantic equivalence, and common-mode redundancy. Do not launch another selector variant until this lineage is resolved. Then extend the Behaviour Atlas across Q80, Q90 and Q7 while preserving distinct output types.
