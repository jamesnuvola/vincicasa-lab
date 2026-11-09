# Q89 recovery checkpoint — 2026-11-09 00:21Z

**Status:** the recovery aggregate is still running. Acceptance, output persistence and current-head CI remain pending. No Q89 run is marked complete.

## Hypothesis and registered dimensions
Extend the finite 27-feature equal-weight formula grammar from 8 to 9 features. Select Q89 and Q88 candidates via Discovery top-100 → Validation only; freeze before Blind OOS and compare paired Top-5/10/20 number-hit ranks. The preregistered 07-Nov archive dimensions are 4,686,825 formulas; 3,351 targets (Discovery 2,011 / Validation 670 / Blind 670); 14,060,475 metric rows; Holm family 42,181,425 tests. Formula-family p-values use an exploratory continuity-corrected normal approximation to the finite-population Hypergeometric null.

## Provisional aggregate measured (not accepted)
The aggregation log from [run 42534331468](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42534331468) recorded:
- archive through 2026-11-07; 3,401 draws and 3,351 scored targets;
- 4,686,825 formulas, 14,060,475 metrics, 3,351 target-ledger rows;
- Holm family 42,181,425; **0 formula/split rows with adjusted p < 0.05**; minimum reported Holm p max endpoint = 1.0;
- frozen Discovery/Validation candidate IDs: Q89 P9_06_09_12_14_15_17_18_19_23; Q88 control P8_00_08_11_12_15_16_19_23.

Acceptance then failed with 8 paired metric replay mismatches: Q89 and Q88 each for Top-5, Top-10, Top-20 and mean rank. These aggregate outputs are provisional: acceptance failed, outputs were not persisted, and no paired endpoint p-values or CIs are claimed.

## Current recovery
[Run 42538247699](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42538247699), exact head d062bf9ea5068235a136c8adf011108c89440274, is still in the aggregate step. Acceptance/persistence/current-head CI are pending. Full CI [run 42538247764](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42538247764) is also in progress.

## Archive mismatch
Canonical main is commit 6cca9022d4311a3f9aba2925fce8c653dc6b63ab, archive blob 77ca692a6082809fcc6c471501617433ec7c36cf, 3,402 draws through 2026-11-08 (latest 3, 7, 10, 16, 27). Q89's branch archive blob 5d2efd70684e918b27d8f06386d545647898336d has 3,401 draws through 2026-11-07. The immutable shard artifacts from run 42524743687 are tied to the older archive. A canonical refresh remains necessary.

## Root-cause status
The acceptance failures are verified, but exact expected/actual values were not emitted. GitHub connector reads of the same claimed aggregator blob SHA returned inconsistent field contents, so the suspected Q88 rank-vector/rank-sum mapping is not confirmed. Treat it as a readback inconsistency until stable Git-object evidence or the current runner's acceptance output confirms a defect. Diagnose Q89 metrics separately.

## Guardrails and next action
No merge, promotion or shadow insertion. PRs #6, #7 and #8 are untouched; the immutable 2026-10-25 freeze is preserved. Historical Blind OOS is not independent prospective confirmation.

Wait for run 42538247699. If acceptance fails, emit numeric expected/actual replay diagnostics, verify exact source blobs and patch only confirmed defects. If it passes, persist append-only, verify bytes and exact-head CI. Then refresh Q89 to the 2026-11-08 canonical archive before claiming current coverage. Q92 is the next finite expansion: 10-feature subsets, C(27,10)=8,436,285 formulas, 25,308,855 formula-split rows and Holm family 75,926,565, compared with a Q89 control on identical data/splits.
