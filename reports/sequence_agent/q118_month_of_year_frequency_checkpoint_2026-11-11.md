# Q118 recovery checkpoint

- Protocol committed before computation at 2026-11-11T11:46:47Z.
- Source: data/storico_daily.csv, 3,404 draws through 2026-11-10, pinned Git blob 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Walk-forward: 3,204 strict-prior targets; split 1,922 / 641 / 641.
- Validation selected alpha=3200 from the fixed grid; the largest shrinkage wins, indicating month-specific rates do not justify a meaningful departure from global frequency.
- Structural validation: 15/15; future-suffix mutation 9/9; deterministic replay passed.
- First wrapper validation had one false failure because the assertion referenced cutoff_date while the in-memory row field was cutoff; the assertion was corrected and the full suite rerun at 15/15. No data, formula, or scored metric changed.
- Q118 freeze for 2026-11-11 is research-only, cutoff 2026-11-10, and is not a Q60 pair.
- No production scorer, Q60 record, or existing freeze was changed. No merge or promotion.
- Next: after the official 11-Nov draw is published, score this immutable freeze; retain Q60 at 23/200 until a complete paired target is verified.

## CI recovery

- First Node 20 replay run 43016008865 reached the Q118 step after all preceding repository checks passed, then failed at parse time because the local variable `fs` redeclared the imported `node:fs` binding.
- Root cause was a naming collision only; no statistical calculation or persisted result was implicated.
- Corrected the local variable to `freezeStats`; the next CI run must still complete before the Node 20 replay is declared passed.

- Second replay diagnostic showed the Node runner's mean helper returned a sum instead of an average. Corrected the helper to divide by the sample length; the precomputed V8 report/ledger were unaffected. A full replay is being repeated before accepting CI.

- After both fixes, the persisted Node runner was executed in a V8 replay harness against the pinned archive and fetched report/ledger/validation/freeze. It passed: 3,204 targets, alpha=3200, four inference comparisons within tolerance, byte-identical 3,205-line ledger, freeze match, and 9/9 future-suffix checks. This is not yet a Node 20 CI pass.

- Second Node 20 run reached the replay step but failed the byte-identical ledger comparison: 12-decimal floating-point serialization differed across runtimes. The ledger and replay serializer are now canonicalized to 10 decimal places; the report records this precision. A new Node 20 run is still required.
