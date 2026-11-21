# Q141 persistence recovery — 2026-11-12

## Observed failure

Workflow run 43223714658 (head \`a80698ae050c29bbaafd5360b2f3f29dcb08421c\`) completed all Q141-B1, C0, C1 and C2 test/analysis/artifact-upload steps successfully, then failed only in the append-only Git persistence step.

Root cause: a prior push run (43223302175, head \`9f56acd87b5eaa2edd15f9d1bf6b253d0b7181e8\`) persisted the first Q141-B1 output bundle while the newer run was preparing its own output commit. The newer push was rejected as non-fast-forward; its rebase then encountered add/add conflicts on the five Q141-B1 generated files already created by the prior run.

This was a persistence race, not an experiment or test failure.

## Recovery checkpoint

The failed run's artifact was retained and downloaded:
- Artifact ID: \`13947257039\`
- Artifact name: \`q141-b1-formula-registry-a80698ae050c29bbaafd5360b2f3f29dcb08421c\`
- ZIP size: 114,031 bytes; uncompressed files: 828,143 bytes.
- It contains the registry, full 3,354-row target ledger, walk-forward report, manifest and checkpoint.
- The artifact report records 3,354 strict-prior targets, 402,480 sampled formula comparisons, zero stable score/rank mismatches, and 2,311 legacy NumPy rank differences due sub-tolerance floating-point near-ties.

The artifact is the recovery source for the latest B1 output; the previous successful push run's files remain available in the branch until the latest bundle is persisted.

## Corrective action

Updated \`.github/workflows/ci.yml\` to:
1. use a common ref-name concurrency key for push and pull-request runs on the same branch;
2. resolve only known Q141 generated-output add/add or modify conflicts in favor of the current run's generated bundle;
3. fail closed on any unexpected conflict outside the explicit Q141 output allowlist.

No source archive, historical freeze, shadow forecast, engine, or protected PR was modified.

## Next action

Run the workflow from the latest branch head after all prior runs have completed; verify the new output bundle is committed and read back by exact Git blob SHA and manifest hashes. Keep PR #89 draft and do not merge or promote an engine.
