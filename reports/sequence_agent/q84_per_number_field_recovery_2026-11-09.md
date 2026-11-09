# Q84 per-number field dynamics — recovery checkpoint

- Date: 2026-11-09
- Failed workflow run: [42705370822](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42705370822)
- Failed job: `evaluate-validate-persist`
- Source head at failure: `189adc65fe173cd7a1584b806ed41f4110ace714`
- Unit regressions: **7/7 passed**; Python compilation passed.
- Walk-forward output: **not produced**. No report, target ledger, manifest, validation receipt or result commit was created.

## Root cause

The Q84 analogue kernel learns from the outcomes of all 42 fixed rules. The new experiment initially appended the 14-model comparison hit vector (equal42, flow K50 and 12 field variants) to the analogue memory. After 30 prior targets, the kernel therefore returned 14 weights, while the fixed-rule rank matrix had 42 rows. `weighted_borda_rank` correctly rejected the incompatible dimensions.

This was a state-memory schema mismatch, not evidence about predictive performance and not a target-leakage finding.

## Correction

Commit `8ce0a7cd2d191cbeeacc326d4086a85b8216e612` computes the 42 fixed-rule Top20 hit outcomes directly from the 42-row fixed ranking matrix before storing the current target in analogue memory. A fail-fast shape assertion now requires exactly 42 values. The current target is still appended only after its ranking and outcome have been scored.

## Recovery state

- The original failed run is retained as diagnostic evidence.
- The corrected branch must rerun the complete 3,202-target walk-forward from the canonical 3,402-draw archive.
- Acceptance, exact-byte persistence and exact-head CI remain pending.
- No engine promotion, prospective shadow insertion or immutable-freeze change.
- PRs #6, #7 and #8 remain untouched.

Next action: rerun the corrected exact head, inspect the first complete result and acceptance replay, then persist only if every validator passes.
