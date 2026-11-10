# Q95 post-run status and recovery addendum — 2026-11-10

## Final verified state

Q95-SPECTRAL-SUBSPACE-PERMUTATION-NULL-01 is complete as a historical diagnostic experiment.

- Canonical archive: 3,403 draws, 2017-07-17 through 2026-11-09.
- Strict-prior targets: 3,203.
- Chronological splits: Discovery 1,921; Validation 641; historical Blind OOS 641.
- Fixed constrained node-label permutations: 999, seed 9501.
- Replayed permutation overlap values: 3,199,797.
- Circular moving-block bootstrap: block length 20, 2,000 replicates.
- Global Holm family: six tests (three permutation-null tests and three circular-shift association tests).
- Q93 source tests: 10/10 PASS.
- Q94 source tests: 12/12 PASS.
- Q95 regression tests: 12/12 PASS on the corrected branch.
- Independent acceptance: PASS.
- Exact persisted-head read-only replay: PASS.
- Append-only persistence commit: `362c0ad8025c0aac35eacc41ab7cc549117c4b63`.
- Dedicated workflow: run 42758588282, success.
- General CI: run 42758598905, success.
- Evidence artifact: 29,291,573 bytes; SHA-256 `4fae0a83a2cf59cc364ad6771d537dfc8306028f259d4b720dd1f3906bb7658d`; artifact ID 13736528582.

The acceptance report's `persisted_head_replay` field was written before persistence and therefore still says `PENDING`. The workflow subsequently completed the exact persisted-head read-only replay successfully; the run and commit above are the authoritative post-persistence evidence.

## Measured findings

| Split | Observed mean overlap | Constrained permutation mean | Excess | Excess block-bootstrap 95% CI | Spearman rho: overlap vs Q93−Equal42 Top20 | Circular-shift p (Holm) |
|---|---:|---:|---:|---:|---:|---:|
| Discovery | 0.04985 | 0.05124 | -0.00139 | [-0.00304, +0.00021] | -0.04483 | 0.33 |
| Validation | 0.04602 | 0.05130 | -0.00528 | [-0.00712, -0.00340] | +0.07014 | 0.33 |
| Historical Blind OOS | 0.04653 | 0.05127 | -0.00474 | [-0.00771, -0.00133] | -0.00554 | 1.00 |

All three constrained permutation p-values after the single global Holm correction were 1.00. The three circular-shift association p-values after the same six-test Holm correction were 0.33, 0.33 and 1.00.

The primary gate is `NOT_SUPPORTED`. In Validation and historical Blind OOS the observed label-aligned overlap was lower, not higher, than the constrained permutation mean. The overlap also did not positively predict the per-target Q93 k=2 minus Equal42 Top20 advantage. This closes the current one-step spectral-persistence hypothesis; it does not prove that every possible graph structure is uninformative.

## Recovery history

1. First Q95 attempt, run 42758440240: compilation and Q93/Q94 tests passed; 11/12 Q95 tests passed. The single failing fixture used arbitrary orthonormal bases outside the all-ones-orthogonal 39D subspace. The production guard correctly rejected the invalid fixture. No walk-forward ran.
2. Corrected the fixture by projecting into the all-ones-orthogonal subspace before QR. Strengthened the production overlap routine to reject invalid non-empty bases. Corrected Q95 tests then passed 12/12.
3. First full Q95 attempt, run 42758586616: walk-forward and independent acceptance passed, and the 29.3 MB artifact was uploaded. Append-only push was rejected as non-fast-forward because the branch advanced after that runner checked out its older head. No output was written to the remote branch by that attempt.
4. Reran from the latest branch head in run 42758588282. Walk-forward, independent acceptance, artifact upload, append-only push, exact persisted-head read-only replay and job all succeeded. The accepted outputs are on the branch at commit `362c0ad`.

## Next iteration

Do not add another one-step spectral weight. The current one-step persistence hypothesis is closed as NOT_SUPPORTED.

A narrowly scoped Q96 diagnostic may test delayed recurrence at fixed lags 2, 3 and 5: compare each prior-only leading k=2 subspace with the corresponding subspace from those earlier prefixes, against the same constrained node-label null. Pre-register all lag-by-split tests in one Holm family before execution; use no target leakage and do not create a forecast operator unless the recurrence survives Validation and historical Blind OOS. If this also fails, close the spectral branch and concentrate effort on the incomplete Q92 formula acceptance and the Q60 prospective gate.

Q60 remains blocked at 21 complete paired prospective targets versus the required 200. Continue append-only prospective freezes only; never reconstruct missing freezes.

No engine promotion, no automatic merge and no immutable freeze changes. PRs #6, #7 and #8 remain protected and untouched.
