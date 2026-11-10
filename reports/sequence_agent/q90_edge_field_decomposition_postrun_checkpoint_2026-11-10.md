# SONAR Q90 Edge-Field Decomposition — final post-run checkpoint

Date: 2026-11-10

## Final execution state

- Task: Q90-EDGE-FIELD-DECOMPOSITION-01.
- Source archive: 3,403 draws, 2017-07-17 through 2026-11-09; Git blob SHA-1 8d3e19f0b417024ba32e576697eac0648d12ab86; SHA-256 ba0c8f4e78805e72d04a1b731e1882a9edd3ac71a2bc35c92409540d9ebdec61.
- Strict-prior targets: 3,203; Discovery 1,921; Validation 641; historical Blind OOS 641.
- Regression tests: 11/11 PASS.
- Walk-forward: PASS.
- Independent acceptance: PASS.
- Append-only Git Data API persistence: PASS; exact-byte readback PASS.
- Persisted-head read-only replay: PASS.
- Persisted head: a1b841465f98fe85f7b9e26301ee32644aaf74ef.
- Dedicated Q90 workflow run: 42745636428; all three jobs completed successfully.

## Measured primary result

The fixed focal model was Q90::PAIR_INTERACTION_TRANSFER.

- Blind OOS Top20: 2.5319812793 hits/target.
- Degree/main-effect Top20: 2.5600624025; pair-interaction delta -0.0280811232.
- Equal42 Top20: 2.5460218409; pair-interaction delta -0.0140405616.
- Paired block-bootstrap 95% CI vs degree/main: [-0.0592823713, 0.0046801872].
- Paired Holm p vs degree/main: 1.0; paired Holm p vs Equal42: 1.0.
- Exact-null Holm p for focal Top20: 1.0.
- Predictive gate: NOT_MET.

## Decomposition diagnostics

- Pair-interaction residual accounts for about 84.4% of edge-change Frobenius energy; additive main effects about 15.6%.
- Maximum residual row-sum absolute error: 3.33e-15.
- Maximum reconstruction error: 4.44e-16.
- Main/residual Frobenius inner product is numerically zero (order 1e-17).
- Despite dominating edge-change energy, the pair-interaction component did not improve the Top20 ranking. Energy concentration is not predictive evidence.

## Reproducibility and leakage checks

- 3,203/3,203 prior cutoffs checked; each target used draws[:i] and all five rankings were frozen before reading the target quintet.
- 16,015 ranking vectors replayed.
- 1,024,960 raw/smoothed signal values replayed.
- 32,030 decomposition diagnostics replayed.
- 45 exact Hypergeometric null tests in one global Holm family.
- 32 paired moving-block bootstrap tests (block length 20, 2,000 replicates) in one global Holm family.
- Immutable freezes were not modified; no engine promotion.
- Historical Blind OOS has been exposed in prior SONAR experiments and remains exploratory, not virgin prospective confirmation.

## Persistence references

- Report: reports/sequence_agent/q90_edge_field_decomposition_report.json
- Validation: reports/sequence_agent/q90_edge_field_decomposition_validation.json
- Manifest: reports/sequence_agent/q90_edge_field_decomposition_manifest.json
- Target ledger: reports/sequence_agent/q90_edge_field_decomposition_target_ledger.csv.gz
- Protocol: reports/sequence_agent/q90_edge_field_decomposition_protocol_2026-11-10.json
- Persistence commit: a1b841465f98fe85f7b9e26301ee32644aaf74ef.

## Diagnosis and next hypothesis

The additive/common-degree component explains only about 15.6% of edge-change energy, while the zero-row-sum pair residual carries about 84.4%. Yet projecting the full residual into the fixed transfer operator does not improve the ranking. The missing information is therefore unlikely to be captured by raw residual energy alone.

Next experiment: Q91 spectral coherence of the pair-interaction residual. For each strict-prior target, compute the symmetric zero-row-sum residual E_pair and its eigenspectrum. Freeze low-rank projections using k=1, 2 and 4 leading nonzero modes, with no parameter search on Validation or historical Blind OOS. Compare these projections against full residual, degree/main effects, node-only inertia and Equal42. Add a preregistered spectral null that preserves the residual eigenvalue spectrum while randomizing eigenvector orientation within the orthogonal complement of the all-ones vector. Measure mode-energy concentration and temporal persistence as diagnostics, but promote no model unless the Top20 paired block-bootstrap CI, global Holm correction and prospective gate all pass.

## Remaining project blocker

Research queue remains blocked at Q60: only 21 complete prospective paired targets are registered against the required minimum of 200. Do not reconstruct missing historical freezes. Continue append-only prospective collection. Q92's expanded 10-variable formula walk-forward remains a separate open draft and was not re-run in this cycle.

## Guardrails

PR #31 remains draft and stacked on the Q89 research branch. PRs #6, #7 and #8 remain open and unchanged. No merge, no engine promotion, no freeze changes.