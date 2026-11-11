# Q126 checkpoint — squared-gap concentration transition

- Protocol was committed before calculation; protocol Git blob 69d237c31ace1ecad42aac13db14f789e5e92f0a.
- Canonical archive: 3,404 draws, 2017-07-17 through 2026-11-10; CSV blob 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Application modelDraws blob 25c0b2316662664deff9e2157e60ec56cfa3a640; 3,404 rows reconciled by date and ordered numbers.
- Statistic: G = sum of squared four internal adjacent gaps; exact 5-of-40 enumeration = 658008 subsets; support size 864; exact-null quartile cutpoints q25/q50/q75 = 182/284/396.
- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.
- Models: M0 exact combinatorial marginal; M1 prior-only unconditional marginal, alpha=200; M2 prior-only one-step previous-state conditional model, alpha=200 shrinkage toward M1.
- Blind OOS inference: six preregistered endpoints; 50,000 paired block sign-flips and 10,000 circular block-bootstrap replicates, block length 20; Holm across six.
- Decision: **NO_SQUARED_GAP_CONCENTRATION_TRANSITION_LIFT_DEMONSTRATED**.
- Validation checks: 20/20; future-suffix mutation: 9/9.
- No forecast freeze, Q60 record, production scorer, or existing PR was modified.
- Recovery 1: the first Node 20 replay found a byte mismatch in the 12-decimal ledger serialization; values were canonicalized to 9 decimals.
- Recovery 2: the next replay passed the report after split means were aligned, but found a one-unit-at-9-decimals difference at ledger row 226 (10.912065719 vs 10.912065718), attributable to cross-runtime floating-point serialization. All floating ledger and aggregate outputs are now canonicalized to 6 decimals; corrected replay remains pending.

## Limitations

- Historical Blind OOS is not a virgin holdout and is not prospective confirmation.
- The scalar G compresses the full gap vector; this test does not cover every possible structure.
- Holm covers the six local Q126 endpoints, not the entire Q00-Q126 research family.
- This is a statistical structure diagnostic, not a physical fluid-dynamics model.

## Next action

After official publication of contest 315, score existing immutable 11-Nov freezes without retuning; continue append-only Q60 paired collection. No automatic merge or engine promotion.
