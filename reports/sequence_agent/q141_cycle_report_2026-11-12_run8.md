# VinciCasa SONAR — Q141 cycle checkpoint (2026-11-12)

## Completed in this cycle

### Q141-C3 — canonical formula rank consensus
- Frozen sample: 120 raw Q80 subset-mean formulas, 113 unique canonical IDs, 12 per subset size k=1..10.
- Strict-prior walk-forward: 3,354 targets; Discovery 2,013, Validation 671, Blind OOS 670.
- Primary Blind OOS Borda Top-5 delta vs equal-family: +0.011343 (1.134 percentage points), 95% circular block-bootstrap CI [-0.000299, +0.023284], raw block sign-flip p=0.09405, Holm-adjusted p=1.000 across 48 paired tests.
- Point estimate exceeds the +0.005 practical threshold, but the interval crosses zero and the corrected test is not significant. Borda Top-10 vs equal-family has Holm p=0.059997, still above 0.05. The 18 exact uniform-null tests also do not survive Holm.
- Decision: no robust consensus lift demonstrated; do not tune on the historical Blind OOS.

### Q141-A3 — Q90 typed AST import
- Pinned Q90 artifact 13627507532, SHA-256 12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077.
- All 17 source artifact members verified.
- Imported 330,429 formulas into typed per-number-score ASTs: 262,599 linear means, 29,070 pairwise interactions, 38,760 conditional gates.
- 330,429 unique source IDs and 330,429 unique canonical AST IDs; zero duplicates.
- 20 Discovery-selected features from the 59-feature Q89 matrix; Q90 source archive 3,401 draws through 2026-11-07.
- Persisted as seven deterministic gzip JSONL shards. Workflow 43275487478 succeeded; exact remote readback verified SHA-256, byte length, Git blob SHA-1 and JSON parsing for all eight output files.

## Data and interpretation boundaries
- Q141 eligible source prefix: 3,404 draws through 2026-11-10. Contest 315 / 2026-11-11 remains quarantined pending primary-source confirmation.
- Q90 metrics remain tied to their own 3,401-draw archive and Discovery-selected feature subset. Do not pool Q90, Q7 and Q141 performance ledgers without source and scoring reconciliation.
- Q7's 1,023 formulas score 658,008 candidate quintets; they are not per-number formulas and must use a distinct AST output type.
- Historical Blind OOS is exposed research history, not virgin prospective evidence.
- The Q141-C3 and Q90-A3 workflows are dedicated validations. Broad repository CI on the latest branch head is pending/action-required; do not claim full project CI success.

## Repository governance
- PR #89 remains open and draft. Branch head at checkpoint: adb7eac82948174a9e838372001a7b313364db64. PR base remains 0bf1ef0d39afb671ff83e519489f16b0c24eb15a while main is 70dcf8cc128884d9739959406d5662ef76daa253 (one commit ahead); no automatic rebase.
- PRs #6, #7 and #8 remain open, unmerged and unchanged.
- No canonical archive mutation, no forecast shadow insertion, no engine promotion and no merge.

## Next action — Q141-A4
Import Q7's 1,023 quintet-ranking formulas into a separate typed AST namespace/output type, preserve source archive and candidate-scoring lineage, verify all 658,008 candidate combinations, then reconcile source windows and semantics before building a common-source formula behaviour atlas.
