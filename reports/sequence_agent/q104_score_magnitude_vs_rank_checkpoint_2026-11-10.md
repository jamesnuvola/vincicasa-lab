# Q104 — score-magnitude versus rank-only subset-likelihood checkpoint (2026-11-10)

## Status
NO_INCREMENTAL_SCORE_MAGNITUDE_LIFT_DEMONSTRATED. Research-only; no production engine, prospective freeze, Q60, H101 or H102 record was changed.

## Source and protocol
- Main commit: d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b.
- Archive: 3403 draws through 2026-11-09; blob 8d3e19f0b417024ba32e576697eac0648d12ab86.
- Active scorer: blob 7ccb9a2abfe452ec535913b70225bc109f692304; active report blob ff07b6da4948bb89467067c2552d9b1f78bc9549.
- Protocol blob: d8faed4c6649f36b3e4248b24692082fa7056817; pre-scoring 10×10 paired family including uniform fallback.

## Result
- Targets: 3203 (Discovery 1921 / Validation 641 / historical Blind OOS 641).
- Validation-selected temperatures: magnitude uniform, rank-only uniform.
- Blind paired mean log-likelihood difference (magnitude − rank): 0.
- Paired 50,000 block sign-flips p=1; Holm across 100 pairs p=1.
- Circular block-bootstrap 95% CI: [0, 0].
- Minimum Holm p across the 100 pair family: 0.0099990001.

## Integrity
- 11/11 checks PASS; 3203 strict-prior score vectors.
- Future mutation: 9/9; deterministic replay: 8/8.
- Both representative PMFs exhaustively normalized across 658008 subsets.

## Limitations / next action
- Historical Blind OOS is exposed to prior SONAR research and is not a virgin prospective holdout.
- Stop retrospective tuning on this same cohort; continue Q60 append-only prospective collection.
- Any positive result requires at least 200 prospectively frozen targets and human review; no promotion authorized.
