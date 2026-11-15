# VinciCasa SONAR — Q141 cycle 17 (2026-11-13)

## Decision

**No new predictive walk-forward was run.** The active B11 prospective protocol has one frozen forecast and zero published target outcomes at 05:39 Europe/Rome, before the scheduled 20:00 draw. Reusing exposed historical Blind OOS or using B11 outcomes to develop A8 would invalidate the confirmatory design. The correct work this cycle was source-provenance reconciliation, forecast-integrity verification, and preservation of the protocol.

## Recovered state

- Branch: `research/q141-a7-fresh59-behaviour-20261113`.
- B11 checkpoint: `PREDICTION_FROZEN_REMOTE_VERIFIED`.
- Target: 2026-11-13 20:00 Europe/Rome.
- Prior cutoff: 2026-11-12; 3,406 draws.
- Frozen predictions: 1; outcomes reconciled: 0.
- Prediction SHA-256: `009f56ae414852c223a81a7d209e17bc4f94076b72556c87d15273001470a1f3`.
- Main and research branch canonical archive blob: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`, 3,406 rows through 2026-11-12.
- Pinned model source commit `1a6f27adc158c47c300c992be3ef38bfa99505ec`; fetched script blob `b278f9e61483e9ea8ba0b8efc2c70844ecdd859b`.

## Root-cause diagnosis and correction

The prior Q134/Q132 provenance warning arose because the official-source extraction available at that time did not expose contest 315's five numbers. A fresh check of the official VinciCasa archive root now lists contest 315 (2026-11-11) as 1, 21, 22, 27, 29 and contest 316 (2026-11-12) as 2, 4, 7, 23, 33. Both rows match the repository archive exactly.

The official archive root is the primary evidence: https://www.vincicasa.it/archivio-estrazioni. The contest 315 detail page confirms the date/contest but its extracted text does not expose the numbers. The official bulletin archive lists the 11 November bulletin, but its linked PDF exceeded the browser reader's content-size limit and was not independently inspected.

This closes the previously recorded source-exposure gap for the B11 historical input as of this check. The canonical archive was not changed.

## Forecast integrity and exact baseline

The frozen M0 and M1 Top-5 sets are both `{1, 7, 25, 27, 36}`; their intersection is 5/5, Jaccard = 1, and divergence `D_t=0`. Thus the paired Top-5 hit-share difference for this first target is necessarily zero regardless of the eventual outcome. The target remains in the protocol and is not dropped.

For any fixed Top-5 under a uniform 5-of-40 draw, expected hits are 0.625 and exact 5/5 probability is 1/658,008. This is only the combinatorial baseline.

Official archive currently exposes contests 315 and 316. At 05:39 local, contest 317 had not yet been drawn/published; scheduled time is 20:00 Europe/Rome.

## Quantitative hypothesis retained, not activated

Q141-A8 remains the next candidate hypothesis for a **new independent 200-target prospective sample after B11 is fully closed**:

- Pre-outcome divergence `D_t = 1 - |Top5(M0)∩Top5(M1)|/5`.
- Divergence prevalence at least 25%.
- Conditional M1-minus-M0 Top-5 hit-share at least +0.020 on divergence-active targets.
- Unconditional improvement at least +0.005, with 95% block-bootstrap lower bound above zero and Holm-adjusted p < 0.05.
- At least 50 divergence-active targets; otherwise conditional endpoint is underpowered.
- Fixed block length 20, 20,000 circular moving-block bootstrap and exact block sign-flip; Holm across conditional and unconditional endpoints.

A8 is not evaluated, tuned, or trained on B11. No new retrospective Blind OOS is claimed because historical holdouts have been exposed to prior SONAR research.

## Verified work

- Read back B11 checkpoint, one-row ledger, frozen prediction and manifest from the repository.
- Manifest Git blob SHA-1 values match fetched prediction, ledger and freeze-report blobs.
- Main and research branch archive blobs match exactly.
- Fetched the exact A7 script at its pinned source commit.
- Independently recomputed Top-5 set intersection, Jaccard and divergence from the frozen lists.
- Calculated exact hypergeometric 5-of-40 baseline.
- Persisted a separate official-source provenance audit and this cycle report; no existing freeze or canonical archive was overwritten.

## Limits

- No target outcome exists yet; no Discovery/Validation/Blind efficacy comparison can be made on the prospective stream.
- One forecast is not evidence of predictive skill.
- The Top-5 paired endpoint is structurally zero for the first target because M0 and M1 have identical unordered sets.
- Official bulletin PDF was not independently parsed due browser size limit; the official archive root table is the source used.
- No full CI workflow was run in this cycle; the actions below are readback/integrity work, not a new CI pass.

## Governance

PR #90 remains draft/open for human review. PR #89 and protected PRs #6, #7 and #8 were not changed. No merge, rebase, canonical archive mutation, shadow insertion, or engine promotion.

## Next action

After the official contest 317 result is published, verify the five numbers from the official archive, append the outcome to the existing B11 ledger without changing the frozen prediction, and freeze the next target using only the now-available history. Keep efficacy analysis closed until all 200 consecutive eligible outcomes are reconciled.
