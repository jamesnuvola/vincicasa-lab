# VinciCasa SONAR — Q141 cycle 18 (2026-11-13)

## Decision

Completed a design-power audit for the deferred Q141-A8 hypothesis. No new historical walk-forward was run because prior Blind OOS periods have been exposed by earlier research. No prospective outcome exists yet for B11 contest 317. The correct work was to audit whether the proposed A8 confirmatory design can detect its stated minimum effect.

## Recovered and independently checked state

- Repository: `jamesnuvola/vincicasa-lab`.
- Research branch: `research/q141-a7-fresh59-behaviour-20261113`.
- Branch head before this cycle: `e33d6b9d80003b50cb80e8122bc3da01acb1be4e`.
- `main`: `05f84e57fd0d2028c3f641742e39db4f1629db8c`.
- PR #90: open, draft; 45 commits ahead, 0 behind at the pre-cycle check.
- PR #89: open, draft. PRs #6, #7 and #8: open and unmerged; none was modified.
- Canonical archive `data/storico_daily.csv`: 3,406 rows through 2026-11-12, Git blob `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`; main and research branch copies agree.
- Official VinciCasa archive at 06:43 Europe/Rome lists contest 316 (12 November) as latest; contest 317 is not yet published. The B11 target is scheduled for 20:00.
- B11 checkpoint: `PREDICTION_FROZEN_REMOTE_VERIFIED`, one forecast frozen, zero outcomes reconciled, prediction SHA-256 `009f56ae414852c223a81a7d209e17bc4f94076b72556c87d15273001470a1f3`.

## B11 integrity audit

Fetched the freeze JSON, ledger, manifest, checkpoint and official-prior attestation from the research branch. Recomputed Top-5 and Top-10 from all 40 stored score vectors using the recorded rounding/tie policy:

- 40 unique score-vector numbers.
- M0 Top-5 and Top-10 exactly match the stored rankings.
- M1 Top-5 and Top-10 exactly match the stored rankings.
- Top-5 intersection = 5/5; divergence `D=0`.
- M1 family weights sum to `0.9999999999999999`.
- Target date is after the prior cutoff; freeze timestamp is before the scheduled target time.
- One ledger row remains `PENDING_OFFICIAL_PUBLICATION`.
- Snapshot, ledger and checkpoint hashes agree with the manifest/readback.
- Main archive blob matches the pinned B11 archive blob.

The first B11 target therefore has exactly zero paired Top-5 difference by construction, regardless of its eventual outcome. It remains in the 200-target sample and must not be dropped.

## New quantitative result: Q141-A8 power audit

Implemented `scripts/sonar_q141_a8_power_audit.py` and six unit tests. The audit enumerates the exact hypergeometric distribution for the symmetric difference of two Top-5 sets and simulates the registered ten-block exact sign-flip test under a +0.020 conditional hit-share sensitivity alternative.

- 10 scenarios (replacement size 1–5; 50 or 200 active targets).
- 20,000 Monte Carlo datasets per scenario.
- 1,024 sign configurations per dataset.
- Six unit tests passed.
- Full audit replayed twice with identical output.
- Null rejection rates were 0.37%–1.78%, below the 2.5% raw Holm worst-case threshold.
- Estimated power ranged 3.0%–6.3% with 50 active targets, and 11.1%–51.3% even with all 200 targets active.

This shows that the current A8 design is underpowered for its stated +0.020 conditional effect under the specified block test. It is not a predictive result and uses no draw outcomes.

A8 remains a draft. Before activation, its endpoint/block statistic must be clarified and the sample size or scoring endpoint redesigned. The conditional and unconditional hit-share effects are algebraically linked because non-divergent targets have exactly zero paired Top-5 difference.

## CI status

On the current pre-cycle branch head `e33d6b9`, the latest A7 workflow run `43367439499` and general CI run `43367439469` both concluded `action_required` and returned zero jobs. The API does not expose a more specific reason; these are neither test failures nor successful validations of that head. Earlier runs `43367111516` and `43367111537` succeeded on the earlier commit `351b9751`. No claim of current-head CI success is made.

The A8 unit tests, `py_compile`, CLI run and deterministic replay were completed locally in the Python analysis environment; no dedicated GitHub Actions workflow was executed for this audit. The Python host emitted a non-blocking spreadsheet warm-up warning at interpreter startup, but compilation, all six unit tests and the CLI exited successfully.

## Governance

No B11 forecast, ledger row or canonical archive row was changed. No merge, rebase, shadow insertion or engine promotion. PR #6, #7 and #8 were not modified.

## Next action

1. Wait for official publication of contest 317.
2. Append only its verified outcome to B11, preserving the frozen prediction hash.
3. Freeze the next target before reading its outcome.
4. Keep B11 efficacy analysis closed until 200 consecutive eligible outcomes are reconciled.
5. Before A8 is activated, redesign its confirmatory endpoint/block statistic and power target; do not use B11 outcomes for that redesign.
