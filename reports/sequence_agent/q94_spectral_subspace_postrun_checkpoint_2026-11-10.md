# SONAR Q94 post-run diagnostic checkpoint — 2026-11-10

## Verified state

- Q93 spectral-coherence experiment: independent acceptance PASS; its historical predictive gate was NOT_MET.
- Q93 dedicated workflow: successful read-only replay on the accepted branch head.
- Q93 generic CI issue: the generic workflow called `python -m pytest` without installing pytest. The Q93 branch was corrected to invoke the unittest-based test file directly. Q94's dedicated workflow subsequently ran `tests/test_sonar_q93_spectral_coherence.py` through that exact built-in unittest path and passed.
- Q94 task: `Q94-SPECTRAL-SUBSPACE-PERSISTENCE-01`.
- Q94 workflow run 42755127353: strict-prior walk-forward, independent acceptance, append-only persistence and exact persisted-head read-only replay all succeeded.
- Q94 workflow run 42755463806: source Q93 tests, Q94 regression tests and read-only replay of the already-persisted Q94 outputs all succeeded.
- Generic CI run 42755463736: completed successfully, including archive audit, generated-data audit, prospective-gate test, evolutionary lab, positional/regime/residual/hazard lab and application build.
- Current Q94 PR head after the Q93-test-runner check: `3c3b1c9366468a3d9a9f67d361ddb13ff7365122`.
- Persisted Q94 output commit: `bb3db69cbf7b20dfd5465465d14ea11e4cb5d1e7`.
- No merge, engine promotion or immutable freeze modification.

## Q94 measured evidence

Pinned archive: 3,403 draws, 2017-07-17 through 2026-11-09; SHA-1 `8d3e19f0b417024ba32e576697eac0648d12ab86`.

Strict-prior targets: 3,203; chronological split 1,921 Discovery / 641 Validation / 641 historical Blind OOS.

Replay counts:
- 3,203/3,203 strict-prior cutoffs.
- 3,203 subspace-stability values.
- 16,015 ranking vectors.
- 45 exact-null tests, 24 paired moving-block bootstrap tests and 9 circular-shift randomization tests, each family Holm-corrected.

Focal `Q94::STABILITY_WEIGHTED` Top20 mean hits:
- Discovery: 2.51536.
- Validation: 2.49922.
- Historical Blind OOS: 2.54602.

On Blind OOS the focal result exactly matched Equal42's aggregate Top5/Top10/Top20 metrics. It exceeded Q90 pair-interaction by only 0.01404 Top20 hits/target (95% paired block-bootstrap CI [-0.01096, +0.03744], Holm p=1.0), and exceeded Q93 k=2 by 0.00936 (CI [-0.01560, +0.03276], Holm p=1.0). The primary gate was NOT_MET; exact-null and circular-shift Holm p-values were both 1.0.

Mean normalized leading-subspace overlap:
- Discovery: 0.04985 (median 0.03557).
- Validation: 0.04602 (median 0.03590).
- Historical Blind OOS: 0.04653 (median 0.03671).
- No target in any split had overlap >=0.5.

For two independent random 2D subspaces in the 39D all-ones-orthogonal space, the theoretical expected normalized squared overlap is 2/39 = 0.05128. The observed means are near this reference. This is a descriptive theoretical comparison only; Q94 did not run a formal test of the overlap statistic against a Haar or node-label random-subspace null.

## Root-cause interpretation

The Q94 persistence weight is typically very small and never reaches 0.5. Consequently, the focal convex rank blend mostly falls back to Equal42, while the opposite-weight control mostly reproduces the unweighted Q93 spectral ranking. This explains why the persistence-weighted model did not add predictive value: the leading k=2 pair-residual eigenspace appears to have little one-step label-aligned persistence under the current construction.

This does not prove that all graph structure is uninformative. It says the specific leading-subspace persistence statistic tested here did not identify a stable predictive component.

## Next registered research question — Q95

Before adding another spectral forecast operator, test whether the observed consecutive-subspace overlap is distinguishable from a constrained random-label null:

1. Recompute each target's current and previous leading k=2 subspaces using strict prefixes only.
2. Compare observed overlap with 99 fixed node-label permutation conjugations of the previous basis. These preserve orthonormality and the all-ones-orthogonal subspace; label them as a constrained permutation null, not a Haar rotation.
3. Compare split-level mean overlap and the association between prior-only overlap and the paired per-target Top20 advantage of Q93 k=2 over Equal42.
4. Use block-aware uncertainty and one preregistered Holm family.
5. Only if excess persistence is demonstrated should a new stability-conditioned ranking be considered. Otherwise close this spectral-persistence branch rather than adding more weights.

Q95 is a proposed next experiment only; it has not yet been implemented or run.

## Remaining project blocker

The main research queue still reports Q60 as INSUFFICIENT_PROSPECTIVE_CASES: 21 complete paired targets against the required 200. Continue append-only prospective collection; do not reconstruct missing freezes. Q92 remains a separate incomplete research task.

PRs #6, #7 and #8 were checked and remain open/unmerged. Q94 PR #33 remains draft. No automatic merge or model promotion.
