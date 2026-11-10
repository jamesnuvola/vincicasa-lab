# SONAR Q93 Spectral Coherence — recovery and execution checkpoint

Date: 2026-11-10

## Recovered state

- Q90 is present on the parent research line and is pinned to the canonical archive: 3,403 draws through 2026-11-09, Git blob SHA-1 `8d3e19f0b417024ba32e576697eac0648d12ab86`.
- Q90 strict-prior evaluation covers 3,203 targets (Discovery 1,921; Validation 641; historical Blind OOS 641). Its pair-interaction residual carries about 84.5% of edge-change energy but its Top20 gate was NOT_MET.
- Q91 is already registered in PR #12 for nested strict-prior anticipation over the Q80 3,303-formula catalog. It is not available for spectral coherence.
- Q91's prior run 42256671154 completed its regression tests, nested walk-forward, acceptance validator, and exact Git Data API persistence. The job log contains 34 `Q91_PERSIST_VERIFIED` part records and `Q91_PERSIST_COMMIT: a9b9da49f812ae8671841f009efd00d61e70c37f`. The persisted Q91 result is based on 3,398 draws through 2026-11-04. Its checkpoint still says exact readback pending, so that metadata is stale relative to the workflow log.
- The Q91 branch archive is through 2026-11-04; the Q80 base branch checkpoint is through 2026-11-07; canonical main/Q90 archive is through 2026-11-09. Q91 needs an archive-aligned refresh before it can be called current.
- Q91 selected `EXPANDING_TOP5` on Discovery. Its historical Blind OOS Top5 mean was 0.1181 versus the uniform 0.125 baseline; Top20 mean was 0.4906 versus 0.5; mean actual rank was 20.6419 versus 20.5. Its Holm-adjusted policy family did not establish a significant advantage.
- Q92 (the expanded 10-variable formula grammar) remains a separate open research task and was not executed in this cycle.

## Q93 hypothesis and implementation

The spectral-coherence continuation described in the Q90 checkpoint is registered as Q93 to avoid colliding with the already-used Q91 identifier and Q92.

The Q93 protocol fixes:
- 3,203 strict-prior targets and the same 60/20/20 chronological split;
- Q90 pair-interaction residual as spectral input;
- low-rank operators using k=1, 2 and 4 leading nonzero eigenmodes by absolute eigenvalue, with complete tie groups retained;
- k=2 as the fixed focal hypothesis;
- signed cosine between each node's six-feature delta and its low-rank spectral projection of prior features;
- alpha 0.20, EWMA window 20, decay 0.80;
- 99 fixed node-label permutation conjugations, seed 9301, preserving the eigenvalue spectrum, symmetry and all-ones null direction;
- 72 exact-null Holm tests, 48 paired moving-block bootstrap Holm tests (block 20, 2,000 replicates), and 9 spectral randomization Holm tests.

The permutation null is deliberately described as node-label permutation conjugation, not as an arbitrary Haar rotation. The truncated spectral operator may have a nonzero diagonal; it is used as a feature operator, not interpreted as a zero-self-loop adjacency matrix.

Files committed on this branch:
- protocol: `reports/sequence_agent/q93_spectral_coherence_protocol_2026-11-10.json`;
- engine: `scripts/sonar_q93_spectral_coherence.py`;
- tests: `tests/test_sonar_q93_spectral_coherence.py`;
- independent validator: `scripts/validate_sonar_q93_spectral_coherence.py`;
- append-only persistence: `scripts/persist_sonar_q93_outputs.py`;
- workflow: `.github/workflows/sonar-q93-spectral-coherence.yml`.

## Corrections made before execution

- Replaced function-attached state with local EWMA histories to keep repeated runs isolated.
- Preserved the full 99-permutation rank-mean matrix separately from its per-target mean so the ledger and paired tests use the intended arrays.
- Added Holm-adjusted values to the persisted exact, paired and randomization test records.
- Corrected the validator to use the actual `q87.read_draws()` return contract.
- Corrected the permutation-conjugation regression test.

These are code-level corrections only. No Q93 walk-forward or Q93 statistical result has yet been executed or accepted.

## Current state and next action

- Protocol and implementation are committed.
- Q93 tests, walk-forward, acceptance validator, artifact upload, Git Data API persistence and persisted-head read-only replay are registered in the workflow but have not yet been verified as executed.
- The current canonical archive remains pinned to the Q90 source archive; no data or freeze was modified.
- Next action: obtain a successful Q93 workflow run; if it fails, inspect the exact failed step, correct the root cause, and rerun from the pinned archive. Persist only after independent acceptance passes.
- The Q93 primary gate requires k=2 to beat the full pair-residual comparator, Equal42 and the permutation mean by at least 0.10 Top20 hits/target, with positive paired block-bootstrap lower bounds, Holm p<0.05, exact-null Holm p<0.05 and spectral randomization Holm p<0.05.
- Historical Blind OOS remains exploratory, not virgin prospective confirmation.

## Guardrails

- No automatic merge or model promotion.
- No modification of PRs #6, #7 or #8.
- No overwrite or reconstruction of immutable freezes.
- Q60 prospective promotion gate remains open: 21 complete paired cases against the required 200.
