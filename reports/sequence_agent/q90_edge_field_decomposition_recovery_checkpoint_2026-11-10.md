# Q90 Edge-Field Decomposition — recovery checkpoint

Date: 2026-11-10

## First execution attempt

- Workflow run: 42744851623.
- Python compilation: PASS.
- Regression tests: 10/11 PASS; one assertion failed.
- Walk-forward was not started; no statistical results or output artifacts were generated.

## Root cause

The additive-only synthetic test correctly reconstructed a zero pair-interaction residual to floating-point precision, but its energy fraction was 1.0317724486240898e-32, not bitwise 0.0. The implementation's reconstruction, symmetry, zero-diagonal, zero-row-sum and orthogonality invariants passed; the failure was an over-strict exact-zero assertion in the test.

## Correction

Changed only the synthetic test assertion from exact equality to a tolerance < 1e-28. The residual matrix remains checked elementwise against zero at absolute tolerance 1e-12. No formula, parameter, target, split, archive, or registered statistical test was changed.

## Recovery action

Re-run the complete Q90 workflow from the same pinned archive and preregistered protocol. If regression tests pass, continue to the strict-prior walk-forward, independent replay, append-only persistence, exact-byte readback and persisted-head read-only replay.

## Guardrails

No model promotion, no merge, no freeze changes. PRs #6, #7 and #8 remain untouched.
