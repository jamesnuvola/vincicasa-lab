# Q90 Edge-Field Decomposition — execution checkpoint

- Task: Q90-EDGE-FIELD-DECOMPOSITION-01
- State: ACCEPTANCE_PASS
- Archive: 3403 draws, 2017-07-17 through 2026-11-09
- Strict-prior targets: 3203; splits: {'discovery': 1921, 'validation': 641, 'blind_oos': 641}
- Models: Q90::FULL_EDGE_TRANSFER, Q90::DEGREE_MAIN_TRANSFER, Q90::PAIR_INTERACTION_TRANSFER, Q90::NODE_ONLY_INERTIA, BASE::EQUAL42
- Exact-null Holm family: 45; paired block-bootstrap Holm family: 32
- Primary historical Blind OOS gate: NOT_MET
- Pair-interaction Top20 lift vs degree-main: -0.02808112
- Pair-interaction Top20 lift vs Equal42: -0.01404056

## Next action

Run the independent validator, persist the catalog/ledger/report/manifest/checkpoint/validation append-only, read back exact bytes, and replay on the persisted head. Historical Blind OOS remains exploratory; no promotion or freeze changes.

## Independent acceptance

- Validator status: PASS.
- Strict-prior cutoffs: 3,203/3,203.
- Rank vectors replayed: 16015.
- Signal values replayed: 1024960.
- Primary predictive gate: NOT_MET.
