# Q141-A18 execution recovery note — 2026-11-14

## Recovery chronology

1. Run [43535990681](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43535990681) failed in unit test `test_future_suffix_does_not_change_discovery_training_basis`: the test unpacked the three-value `numpy.linalg.svd` return as two values. The test was corrected to use the repository's canonical `fit_basis` helper, which also canonicalizes singular-vector signs.
2. Run [43536189294](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43536189294) passed all 13 tests, extracted the pinned Q7 sources, completed the full computation and replay, but failed in the artifact-validation step because the script emitted `<base>_report_2026-11-14.json` while the workflow expected `<base>_2026-11-14_report.json`. This was a filename-contract mismatch, not a numerical or walk-forward failure.
3. The script's output prefix was aligned with the workflow's dated artifact naming. A subsequent run was cancelled while the workflow registration was being recovered; it produced no persisted result.
4. Final run [43536584067](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43536584067) completed successfully: 13/13 tests, pinned source extraction, full experiment, byte-identical replay, ledger validation, final artifact validation, remote Git readback and artifact upload.

The temporary recovery workflow file was removed. The branch retains one dedicated A18 workflow.

## Final measured result

- 1,023 formula masks; 3,386 historical target rows; 2,986 evaluated rows after 400-row warm-up.
- Mask design: intercept + 10 family main effects + 45 pair interactions = 56 independent columns; residual dimension 967.
- Discovery / Validation / historical Blind OOS: 1,792 / 597 / 597 targets.
- Mean top-six residual capture: Discovery 0.534334; Validation 0.600535; Blind OOS 0.624041.
- Conditional circular-shift null: 199 replicates; Validation and Blind OOS raw p=0.005, Holm p=0.010; zero null exceedances.
- Adjacent subspace overlap: Discovery→Validation 0.643390; Validation→Blind OOS 0.907737. The preregistered 0.75 threshold fails for Discovery→Validation, so the overall hypothesis is **NOT CONFIRMED**.
- A17 raw six-dimensional capture on the same targets was 0.733447 / 0.712218 / 0.712131; mask-lattice residualization reduces the captured energy materially.

## Integrity and limits

- All 3,386 target rows and all 1,023 formula masks reconciled to Q7 commit `7a37cab601c5f9386131a00246963f8e4aeabf74`.
- The source archive is pinned through 2026-10-24, separate from current main.
- Per-mask scaling uses only the first 400 target rows; each split basis uses exactly the 400 rows immediately preceding that split.
- Future-suffix invariance passed; maximum residual projection error is (2.03\times10^{-13}).
- Full replay is byte-identical.
- Nine manifest files match the remote receipt; checkpoint and receipt were independently re-read and their blob hashes match.
- Bootstrap intervals are conditional on the fitted split basis; they do not include basis-refit uncertainty.
- The conditional null preserves each residual column's circular sequence before row-wise re-projection; re-projection changes exact marginal/autocorrelation properties.
- The 199-replicate null has minimum attainable raw p=0.005.
- This is structural analysis of realized historical rank profiles, not a prediction of numbers or quintets. Historical Blind OOS is not virgin prospective evidence.

## Feature-family bit order

The pinned catalog lists the 10 families in this order: number_frequency, pair_interaction, triple_interaction, quadruple_interaction, exact_quintet_recurrence, sorted_position_frequency, gap_pattern, sum_distribution, odd_count, decade_profile. The design contains every main effect and every pair, so its column space is invariant to a consistent permutation of the family-bit order.

## Next action

Human review of draft PR #101, followed by a separate decision on whether to run a prospectively frozen residual-subspace stability monitor. No merge, production promotion, archive mutation or retuning is authorized by this experiment.
