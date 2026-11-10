# SONAR Q89 — post-run recovery checkpoint (2026-11-10)

## Status

Q89 is analytically computed, independently accepted, persisted in the repository and replayed read-only from the persisted head. Its predictive gate is **NOT MET**. No strategy is promoted.

## Registered question

Does the Q88 signed node-to-graph transfer depend on the true identity mapping between graph neighbors and their prior six-feature states, or can the same apparent effect be reproduced after randomly reassigning neighbor-feature labels?

The experiment used the frozen Q88 operator (alpha 0.20, EWMA window 20, decay 0.80), 39 deterministic unique neighbor-label permutations (Python random.Random seed 8901) plus identity, and one graph-free node-inertia control. The 40x40 edge-delta matrix was not changed by the counterfactuals, so its edge weights and row strengths remained fixed.

## Recovery: first execution failure

- Run 42738690300 failed after the 10 initial regression tests passed.
- Root cause: NumPy advanced indexing, \`ranks[t, :, actual-1]\`, returned shape (5,42), while the ledger expected (42,5).
- Corrective change: introduced \`extract_actual_ranks(rank_matrix, actual_numbers)\`, using \`matrix[:, numbers-1]\` and explicit shape/value checks.
- Added a regression test for model-by-winning-number orientation.
- Corrected code commit: \`af47feac58b00c80bb13b64b66b0ca20e1ac46f8\`.
- Final Q89 regression suite: 11/11 passed.

## Measured experiment

Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08; SHA-256 \`5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b\`.

Walk-forward: 3,202 targets, each ranking frozen using only draws before its target:
- Discovery: 1,921
- Validation: 640
- Historical Blind OOS: 641

Coverage and inference:
- 42 models (identity, 39 permuted mappings, node-only inertia, Equal42 baseline)
- 134,484 rank vectors independently replayed
- 640,400 signal values independently replayed
- 378 exact-null tests, one global Holm family
- 24 paired moving-block bootstrap tests (block length 20, 2,000 replicates), one global Holm family
- 9 neighbor-label randomization tests, one global Holm family

Top20 mean hits per target:

| Split | Identity | Permutation mean | Node-only | Equal42 |
|---|---:|---:|---:|---:|
| Discovery | 2.521083 | 2.518093 | 2.512233 | 2.515357 |
| Validation | 2.489063 | 2.493670 | 2.501563 | 2.498438 |
| Historical Blind OOS | 2.531981 | 2.541582 | 2.530421 | 2.546022 |

Historical Blind OOS primary comparisons:
- Identity minus Equal42: -0.014041; paired block-bootstrap 95% CI [-0.037441, 0.007800]; Holm p=1.000.
- Identity minus permutation-mean control: -0.009600; 95% CI [-0.029124, 0.008963]; Holm p=1.000.
- Neighbor-label randomization Top20 p raw=0.875; Holm p=1.000.
- Identity exact-null Top20 Holm p=1.000.
- Primary gate: **NOT_MET**.

The identity mapping did not outperform the random neighbor-label controls. In the Blind OOS, 34 of 39 permuted controls had Top20 means at least as high as identity (ties included). This is evidence against identity-specific predictive value for this particular Q88 operator; it is not proof that every possible graph representation is useless.

## Acceptance and persistence

- Q89 walk-forward and independent validator: run 42738954011, success.
- Q89 validator status: PASS; strict-prior cutoffs 3,202/3,202.
- Persisted six outputs with Git Data API in commit \`f6991d63ea92f2bd2f3fed50d95b4948c971bb72\`; all six blobs were read back and SHA-256 verified byte-for-byte.
- Persisted target ledger: 8,229,333 bytes, SHA-256 \`53b9469d277a9140e54e6877578e37013556a41ba2a453a6ef4e052c8d6df324\`.
- Persisted report: 120,643 bytes, SHA-256 \`31ddd5568177e068cff6f0ea71b520fabfa1bf613faa90c47054313c9c4fdda9\`.
- Exact persisted-head read-only replay: run 42739942652, success; 134,484 rank vectors and 640,400 signal values reproduced.
- General repository CI: run 42739942552, success on exact head \`9dd1e0bf3acca21e6d40b3ddedf953601a0ba616\`.

Persistence workflow recovery:
- First attempt failed because the Git Data API update endpoint was singular \`git/ref\`; GET correctly uses singular \`git/ref\`, but PATCH requires plural \`git/refs\`.
- Corrected endpoint and exact-byte persistence succeeded.
- A verify-only job initially skipped because GitHub Actions applies an implicit success condition to skipped dependencies; added \`always()\` to the explicit verification condition. Exact-head read-only replay then passed.
- These workflow corrections do not alter Q89 calculations or the registered protocol.

## Limitations

1. Historical Blind OOS has been exposed in prior SONAR research; it is exploratory, not virgin prospective confirmation.
2. The 39 controls permute neighbor-feature labels, not graph edges. They preserve the edge matrix and row strengths but are not a graph-rewiring null.
3. Randomization p resolution is 1/40; Holm correction is applied across the nine registered split-endpoint tests.
4. Exact hypergeometric tests assume independent target draws; moving-block bootstrap is separately reported for serial dependence.
5. The signed transfer is statistical and does not establish physical or causal coupling.
6. The finite Q89 family does not exhaust the formula universe.

## Next preregistered question: Q90 edge-field decomposition

Q89 says the true neighbor-label mapping did not help this fixed operator. The next useful diagnostic is to separate edge-change main effects from pair-specific interaction effects before projecting onto node dynamics.

For each symmetric zero-diagonal edge-change matrix E (n=40):
- Compute off-diagonal mean \`mu\`.
- Compute row sums \`s_i = sum_{j != i} E_ij\`.
- Define additive node/degree effects \`a_i = (s_i - (n-1)*mu)/(n-2)\`.
- For i != j, define \`E_main[i,j] = mu + a_i + a_j\`; set its diagonal to zero.
- Define \`E_interaction = E - E_main\`, with zero diagonal.

This decomposition is exact off-diagonal; the interaction residual is symmetric, zero-diagonal and has zero row sums. Compare fixed, preregistered projections using:
1. full E;
2. degree/common-mode component E_main;
3. pair-specific residual E_interaction;
4. graph-free node inertia;
5. Equal42 baseline.

Keep Q88 smoothing and alpha fixed initially. Walk forward with the same target cutoffs. Use a single global Holm family for exact-null model/split/endpoint tests and paired moving-block bootstrap for Validation and historical Blind OOS. The primary question is whether pair-specific interaction adds information beyond degree/common-mode and node-only controls. No tuning on the historical Blind OOS; any apparent advantage remains exploratory until prospective freezes accumulate.

## Guardrails

- Q89 is **accepted as an analytical experiment**, not as a predictive improvement.
- No model promotion, no prospective freeze insertion, no historical freeze reconstruction.
- No PR merge. PRs #6, #7 and #8 remain untouched.
- Human review is required before any integration.
