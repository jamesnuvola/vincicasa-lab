# Q106 checkpoint — analog-successor vote ablation

- Protocol preregistered before scoring; source main commit 1a61088205f843fdb0d6656c01a54969b555a392.
- Canonical archive: 3403 draws through 2026-11-09; official target 2026-11-10 excluded while pending.
- Walk-forward: 3203 strict-prior targets; Discovery/Validation/historical Blind OOS = 1921/641/641.
- Full scorer is extracted from exact committed UI source; ablation changes only analog coefficient 0.10 to zero and renormalizes remaining weights.
- Decision: NO_INCREMENTAL_ANALOG_LIFT_DEMONSTRATED.
- Validation: 14/14 checks PASS.
- Recovery: no failed run checkpoint required; if workflow fails, inspect job logs, preserve protocol, correct runner only, then rerun --write and --check.
- Recovery commands: node scripts/sonar_q106_analog_ablation.js --write; node scripts/sonar_q106_analog_ablation.js --check.
- Next: await official contest 314 publication; append-only freeze evaluation and Q60 progression only.
