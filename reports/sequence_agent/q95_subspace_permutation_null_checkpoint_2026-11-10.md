# SONAR Q95 constrained spectral-subspace permutation null — checkpoint

- Task: Q95-SPECTRAL-SUBSPACE-PERMUTATION-NULL-01
- State: ACCEPTANCE_PASS
- Archive: 3403 draws, 2017-07-17 through 2026-11-09
- Strict-prior targets: 3203; splits: {'discovery': 1921, 'validation': 641, 'blind_oos': 641}
- Fixed node-label permutations: 999; seed: 9501
- Global Holm family: 6 tests
- Diagnostic gate: NOT_SUPPORTED
- Q93 ledger SHA-256: c6312eab612c278abed9df1050f8dc873ee20b6176d0fe6684958edee60a3eab
- Q94 manifest SHA-256: 61ec19fbe10c651e339a47bd131338ae5545fedaffb6690ab3bae0bc958ec6a1

## Statistical design amendment before execution

The earlier proposal specified 99 permutations. Before any Q95 outcome analysis, the count was raised to 999 because a six-test Holm family with 99 permutations has a minimum attainable adjusted p-value of 0.06, making alpha=0.05 unattainable. Seeds and constrained transformation are unchanged. Validation and historical Blind OOS use all 640 nonzero circular shifts.

## Next action

Run independent replay, append-only persist all evidence, verify exact Git bytes and replay the persisted head read-only. Historical Blind OOS remains exploratory. No promotion, merge or freeze changes.

## Independent acceptance

- Validator status: PASS.
- Strict-prior cutoffs: 3203/3203.
- Permutation overlaps replayed: 3199797.
- Global Holm tests replayed: 6.
- Diagnostic gate: NOT_SUPPORTED.
