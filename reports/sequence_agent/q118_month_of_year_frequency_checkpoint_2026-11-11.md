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
