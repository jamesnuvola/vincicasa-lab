# Q124 checkpoint — tie-aware ordinal sensitivity

- Protocol commit: 1aefa4e21eb28c95619f0e9c58b449d8b723f822 (committed before calculation).
- Archive: 3,404 draws through 2026-11-10; SHA 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Walk-forward: 3,204 strict-prior targets; splits 1,922 / 641 / 641.
- Decision: **NO_TIE_NEUTRAL_ORDINAL_SKILL_DEMONSTRATED**.
- Blind tie-neutral mean rank: 20.336661466459; null 20.5.
- Mean deterministic tie-break advantage: 0.
- Tie-bearing forecasts: 0/641.
- Independent replay: exact key-metric match.
- Q123 freeze reconciliation: exact 40/40 numbers and scores.
- Validation: 17/17.

## Recovery and guardrails

- First execution and independent replay agree on the frozen summary and inferential statistics.
- No production scorer, prior freeze, Q60 record, or protected PR was modified.

## Next action

- After official publication of contest 315, evaluate immutable Q123/Q124 freezes without retuning; append only eligible Q60 pairs.
