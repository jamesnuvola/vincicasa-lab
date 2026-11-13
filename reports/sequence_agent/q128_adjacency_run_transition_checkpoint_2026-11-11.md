# Q128 checkpoint — adjacent-run-count transition

- Protocol committed before calculation: 637528eeea81f4cd34ed62aad8ba2d324f74ce67; protocol blob 25c6a837251719412b41d0f9a5161adfedeacbdc.
- Base main: ea46a70c4c90db5dad44d5374a97f89a84e50ad9; canonical archive blob 40f317e2d0067e061c46ab799d66f777a0e087c0, 3,404 draws through 2026-11-10.
- Statistic: number of adjacent integer pairs in the sorted five-number draw, support 0..4.
- Exact null: C(4,a) * C(36,5-a) / C(40,5); denominator 658,008; expected count 0.5.
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- Models: M0 exact null; M1 unconditional prequential alpha=200; M2 previous-state conditional alpha=200 toward M1.
- Blind OOS: all six proper-score gains negative; all six Holm-adjusted p-values 1.000; decision NO_ADJACENT_RUN_TRANSITION_LIFT_DEMONSTRATED.
- Validation: 24/24 checks; future-suffix mutation 9/9; max probability-mass error 2.220446049250313e-16.
- No forecast freeze, Q60 record, production scorer, or protected PR was changed.

## Limitations

- Historical Blind OOS is not a virgin holdout; Q98's broad lag-1 geometry kernel is related prior research.
- Holm correction is local to Q128's six endpoints, not the complete Q00-Q128 research family.
- This is a structural distribution diagnostic, not a quintet predictor.

## Next action

After official publication of contest 315, append the verified outcome and score only immutable existing freezes; continue append-only Q60 paired collection.

## Replay recovery

- The first persisted-head Node 20 replay failed before execution because `utf8Bytes` was declared twice in the ES module. The duplicate trailing declaration was removed; the statistical algorithm and results are unchanged.
- After the duplicate-helper fix, Node 20 found that the report differed only in JSON serialization (zero differing paths). The next replay exposed schema drift in the validation artifact: 14 check identifiers had been renamed in the runner, while all persisted check booleans were true. The identifiers are now aligned to the persisted validation schema; statistical calculations and scores are unchanged.

## CI status at artifact generation

The exact-head Node 20 replay and general repository CI must be observed after this branch is pushed. Do not infer CI success from the local calculation.
