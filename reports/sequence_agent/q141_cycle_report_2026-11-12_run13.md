# VinciCasa SONAR — Q141 cycle 13 (2026-11-12)

## Q141-A5 — Q90 lineage and feature redundancy

- Recovered the Q141-C6 checkpoint and pinned Q90 artifact (run `42504717670`, artifact `13627507532`).
- Re-verified the artifact ZIP SHA-256 and all 17 member SHA-256 values.
- Re-read the Q90 AST manifest and all seven remote AST shards: all Git blob SHAs match; 330,429 source IDs, 330,429 canonical AST IDs, zero exact AST duplicates. The stale Q90 AST checkpoint is corrected to `REMOTE_GIT_READBACK_VERIFIED` with a receipt.
- Q90 uses 20 of 59 Discovery-selected features; 39 features are absent from the current formula grammar. All 330,429 formulas reference only the selected 20.
- The 4-feature grammar contains 4,845 base quartets, each represented by exactly 15 variants (1 L4, 6 I4, 8 G4): 72,675 formula rows over 4,845 base sets. I4 interaction factors and G4 gate features are members of the same base quartet. Total distinct base feature sets across sizes 4–8: 262,599.
- The 20 selected features have mean absolute pairwise Spearman rank correlation 0.221576 across 40 candidates and 3,351 targets. The largest pair is `gap_hazard_empirical` vs `gap_hazard_residual` at 0.915784; no selected pair has identical ranks on every target.

## Q141-B10 — redundancy-balanced Borda

**Hypothesis:** one total vote per distinct base feature set should improve Blind OOS Top-5 hit share by at least +0.005 versus one vote per formula.

- Deterministic sample: 100 quartets × 15 variants = 1,500 formulas, plus 100 linear formulas for each of L5–L8 = 400; total 1,900 formulas and 500 base sets.
- Walk-forward: 3,351 targets (Discovery 2,011 / Validation 670 / Blind 670); target outcome is read only after both rankings are frozen.
- Discovery: raw 12.7598%, balanced 13.0980%, delta +0.3381 pp.
- Validation: raw 11.8507%, balanced 12.0000%, delta +0.1493 pp.
- Blind OOS: raw 12.4179%, balanced 12.4776%, delta +0.0597 pp; uniform reference 12.5%.
- Primary Blind effect +0.000597; 95% circular block-bootstrap CI [-0.004478, +0.005672]; one-sided block sign-flip p=0.44708; practical threshold +0.005. No lift demonstrated.
- Replayed formula-level Top-5 hit shares match original Q90 split metrics to a maximum absolute difference below 2.14e-15 in all splits. Seven local tests passed. Two complete runs produced byte-identical outputs.

## Lineage correction

The prior C6 checkpoint reported 3,404 Q141 draws. The current Q141 Git blob contains 3,405 data rows. The Q90 source contains 3,401 draws and is an exact prefix after normalizing line endings; four later rows (2026-11-08 through 2026-11-11) are excluded. B10 uses only the pinned Q90 source, so the count error does not change its experiment window.

## Governance and next action

No merge, rebase, canonical archive mutation, shadow insertion or engine promotion. PRs #6, #7 and #8 remain protected. PR #89 remains draft.

Next: Q141-A6 should expand coverage to all 59 features through a deterministic stratified/covering design. Exhaustive enumeration under the same Q90 grammar would require **2,615,511,595 formulas** (about **7,915.5×** the 20-feature universe), so a complete brute-force catalog is not tractable. Preregister coverage quotas and sample size before examining outcomes; keep historical Blind OOS exposed and reserve prospective evidence for a future untouched period.