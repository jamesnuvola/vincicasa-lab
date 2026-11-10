# Q93 recovery checkpoint — first workflow attempt

Date: 2026-11-10

## Attempt 1

- Workflow: Q93 Spectral Coherence, run 42752400217.
- Evaluate job: failed at regression tests; 8 tests passed, 2 failed.
- The Q93 walk-forward, independent acceptance, artifact upload and persistence jobs were skipped. No Q93 target scores or statistical results were produced.

## Root cause

The two failing tests were the exact node-label permutation-conjugation checks. The implementation formed (P V) and then also permuted the feature matrix by (P^T) before multiplying by ((P V)^T). But ((P V)^T X) already equals (V^T P^T X); permuting (X) again applied (P^T) twice.

This was an implementation error in the spectral-null projection, not a failure of the eigenspectrum or walk-forward logic.

## Correction

Commit: `b78407f9550fc32c857f00b94f8329d6ee110e88`.

The corrected operator is now:
[
S_{perm}X=(P V)\Lambda(P V)^T X
]
with the original feature matrix (X) unchanged. This is exactly ((P S P^T)X), preserves the eigenvalues and all-ones null direction, and randomizes the node-label alignment once rather than twice.

## Current status

- The correction is committed to the Q93 research branch.
- The same two regression tests are retained unchanged as acceptance checks.
- No walk-forward or statistical result has been claimed.
- Next action: verify the rerun's regression tests; only then execute the 3,203-target strict-prior walk-forward, independent replay, append-only persistence and persisted-head read-only replay.
- No merge, promotion or freeze modification.
