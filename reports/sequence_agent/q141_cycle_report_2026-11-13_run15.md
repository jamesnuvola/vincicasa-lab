# VinciCasa SONAR — Q141 cycle 15 (2026-11-13)

## Decision

**Q141-A7 / B11 completed. Stability-weighted family aggregation did not demonstrate a useful lift. M1 remains research-only and is not promoted.**

## Recovered source and matrix

- Canonical main commit: 05f84e57fd0d2028c3f641742e39db4f1629db8c.
- Canonical archive: 3,406 draws, 2017-07-17 through 2026-11-12.
- Archive Git blob SHA-1: 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.
- Recomputed feature matrix: 3,356 × 40 × 59, float32.
- Q90 source artifact: run 42504717670; 3,351 historical target rows through 2026-11-07.
- The recomputed first 3,351 rows matched the Q90 matrix bit-for-bit (maximum absolute difference 0); five new rows extend the matrix through 2026-11-12.
- Target ledger: 3,356 rows; Discovery 2,014, Validation 671, Blind OOS 671.

## Quantitative hypothesis

M1 weights each of seven feature families by the inverse of its mean normalized absolute rank turnover across the previous five target rows:

w_f proportional to 1 / (0.10 + turnover_f).

M0 is the equal-family mean. No parameter was fitted or selected from the evaluation periods. The first five target rows use equal weights because they lack five preceding target-rank rows.

Primary endpoint: Blind OOS Top-5 per-number hit share, M1 minus M0, practical threshold +0.005. Secondary endpoint: Top-10, Holm-corrected with the primary endpoint.

## Measured results

| Split | Targets | M0 equal-family Top-5 | M1 stability Top-5 | Delta (pp) | M0 Top-10 | M1 Top-10 | Delta (pp) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Discovery | 2,014 | 12.3237% | 12.3039% | -0.0199 | 25.1043% | 24.8858% | -0.2185 |
| Validation | 671 | 12.0715% | 11.4456% | -0.6259 | 24.2027% | 24.1729% | -0.0298 |
| Blind OOS | 671 | 12.9061% | 12.9955% | +0.0894 | 25.6036% | 25.1565% | -0.4471 |

Uniform references: 12.5% Top-5 and 25% Top-10. Equal-feature aggregation was descriptive only.

### Blind OOS inference

- Top-5 delta: +0.0008942 (+0.0894 percentage points).
- 95% circular moving-block bootstrap CI: [-0.0050671, +0.0071535].
- Two-sided non-overlapping block sign-flip p: 0.84056; Holm p: 0.84056.
- Top-10 delta: -0.0044709 (-0.4471 percentage points).
- 95% CI: [-0.0116244, +0.0026826].
- Two-sided block sign-flip p: 0.22674; Holm p: 0.45348.
- Block length 20; 34 blocks; 20,000 replicates.

The primary delta is far below the +0.005 practical threshold and its interval includes zero. The secondary endpoint is negative. **The hypothesis is not confirmed.**

## Diagnostics and integrity

- All 59 features recomputed from the canonical archive.
- Q90 prefix exact bitwise match.
- Target/cutoff chronology and 50-draw minimum history checked.
- State updates occur only after the target feature row is scored.
- Five unit tests passed on the final code head, including deterministic replay, future-suffix mutation invariance, schema partition, tie handling and stability-weight behavior. The final run emitted no RuntimeWarning.
- Dedicated workflow 43348824830: success.
- General Test VinciCasa Lab workflow 43348824797: success.
- Output validation passed for 3,356 ledger rows and manifest SHA-256 values.
- Artifact 14002069267 digest: 7a27e5eae699e9f98383d5f54daba2d5ac8634245475273ba6253a753f0ce470.
- Downloaded matrix matched the independent local rebuild exactly.
- Report, ledger, manifest and checkpoint Git blobs were read back and matched recorded hashes.

## Limitations

- The historical Blind OOS is exposed to prior SONAR work; it is not virgin prospective evidence.
- The endpoint is per-number ranking hit share, not exact five-number ticket probability.
- Feature families share source information and are not independent.
- A historical result, positive or negative, does not establish the presence or absence of lottery predictability.

## Governance and next action

- PR #90 remains draft and validation-only.
- PR #89 and PRs #6, #7, #8 were not modified.
- No merge, rebase, canonical archive mutation, shadow insertion or engine promotion.
- Main archive still ends on 2026-11-12; no later official draw was present at this checkpoint.
- Freeze M1 and M0. Begin a prospective 200-draw evaluation only after each official result is verified; write/freeze the prediction ledger before the result is available, do not retune or inspect efficacy between targets, and run one final paired analysis after all 200 targets. See the prospective preregistration.
