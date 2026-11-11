# Q127 checkpoint — low/high balance transition

- Protocol committed before calculation; protocol commit `944dce696aaa2446d9c71f075590e1d8966c7f88`; protocol blob `36dd14b940d4eeccead81ff3e82048eadd72598c`.
- Canonical archive: 3,404 draws, 2017-07-17 through 2026-11-10; blob `40f317e2d0067e061c46ab799d66f777a0e087c0`.
- Statistic: L_t counts values 1..20; previous state is L_(t-1); exact null is Hypergeometric(40,20,5).
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- Models: M0 exact combinatorial marginal; M1 prior-only unconditional shrinkage alpha=200; M2 prior-only one-step previous-state conditional shrinkage alpha=200 toward M1.
- Blind OOS inference: six endpoints; 50,000 paired block sign-flips and 10,000 circular moving-block bootstrap replicates, block length 20; Holm across six.
- Validation checks: 20/20; future-suffix mutation: 9/9; all prequential probability masses within 1e-12.
- Decision: **NO_LOW_HIGH_BALANCE_TRANSITION_LIFT_DEMONSTRATED**.
- No forecast freeze, Q60 record, production scorer, or existing PR was modified.

## Limitations

- The lower/upper partition at 20/21 is one fixed coarse partition and cannot represent all draw geometry.
- This transition diagnostic is adjacent to prior parity, median, range and gap-state studies; incremental evidence must be interpreted in the context of the broader Q00-Q127 search family.
- Historical Blind OOS has prior exposure to SONAR research and is not independent prospective confirmation.
- Holm correction covers only six local Q127 endpoints, not the full Q00-Q127 research family.
- This is a structural distribution diagnostic, not a full five-number predictor.

## Next action

After official publication of contest 315, score existing immutable 11-Nov freezes without retuning; continue append-only Q60 paired collection. No automatic merge or engine promotion.
