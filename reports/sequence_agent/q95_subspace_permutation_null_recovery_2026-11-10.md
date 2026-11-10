# Q95 recovery checkpoint — 2026-11-10

## Failed first regression attempt

- Workflow run: 42758440240.
- Compilation: PASS.
- Q93 source tests: 10/10 PASS.
- Q94 source tests: 12/12 PASS.
- Q95 tests: 11/12 PASS; one test errored before the walk-forward started.
- Failing test: `test_vectorized_overlap_matches_scalar_loop`.
- Root cause: the test fixture generated arbitrary QR-orthonormal bases in R^40, but Q95's constrained null is defined only for bases in the 39-dimensional subspace orthogonal to the all-ones vector. The production guard correctly rejected that invalid fixture.
- No Q95 walk-forward, statistical analysis, acceptance, or result persistence ran in the failed attempt.

## Recovery

- Updated the test fixture to project random bases into the all-ones-orthogonal subspace before QR orthonormalization.
- Strengthened `overlap_many` to fail closed when either non-empty basis violates the same subspace constraint.
- The constrained permutation transformation itself was not weakened or changed.
- The 999-permutation count, seeds, archive pin, split boundaries, bootstrap settings and global six-test Holm family remain frozen.
- The corrected script and test were reread from GitHub after update.

## Resume point

Rerun the dedicated Q95 workflow from the latest branch head. Only proceed to walk-forward after Q93/Q94 source tests and all Q95 regression tests pass. If the corrected tests fail, diagnose and record the exact failing invariant before changing anything else. No historical freezes or prior accepted outputs are to be modified.
