# Q125 checkpoint — APP rank-decile calibration

- Protocol committed before calculation; protocol blob `9578af100c8b137404ece91732f9ff40dbca3034`.
- Parent Q123 source ledger blob `36d7af1fb3cceda5976eb99a78931f58d1a3d28a`; 3,204 strict-prior target rows, 2018-02-02 through 2026-11-10.
- Split sizes: 1,922 / 641 / 641.
- Blind OOS decile counts: 316, 358, 328, 324, 293, 320, 309, 302, 334, 321.
- Blind OOS omnibus conditional-randomization p=0.562321883906; Holm=0.562321883906.
- Blind OOS top-heavy trend gain/target=0.211388455538; p=0.199390030498; Holm=0.398780060996.
- Trend block-20 bootstrap 95% CI: [-0.281630265211, 0.682527301092].
- Decision: **NO_RANK_DECILE_PROFILE_SKILL_DEMONSTRATED**.
- Validation: 18/18 local checks.

## Provenance and limitations

- Q125 reuses the fixed Q123 prior-only rank ledger; it does not rerun the APP scorer.
- Q123 strict-prior and future-suffix checks (9/9) are inherited, not rerun.
- Historical Blind OOS is not a virgin holdout.
- No forecast freeze, Q60 record, production engine, or protected PR was modified.

## Next action

- Wait for official contest 315 publication; evaluate immutable Q123/Q124 freezes without retuning; append only complete Q60 pairs.
