# Q141-B9 — Q7 factorial feature-family attribution

**Status:** preregistered; execution pending.  
**Registered:** 2026-11-12, before the B9 computation.

## Hypothesis

Within Q7's fixed 1,023-formula subset grammar, individual feature families and selected pairs may have stable marginal or interaction effects on the strict-prior percentile rank of the realized quintet.

This is a factorial attribution of the existing formula universe, not a new prediction engine.

## Pinned source and target frame

- Q7 commit: `7a37cab601c5f9386131a00246963f8e4aeabf74`.
- Q7 archive: 3,387 draws through 2026-10-24; blob `7dab05ba49ace909fe8783eef729605049c65e50`.
- Q7 walk-forward manifest: `aae2c7768c9d37bf633a13939f2b686bcce83a27`.
- Q7 runner: `ad1c7fa721f316b3af0018f5da4a0a905bb62dcf`.
- Q141 archive prefix identity: `fcb453ed06c8002314f826dbac79d6935f9ac103`.
- Candidate universe: 658,008 sorted 5-of-40 quintets; formula universe: all 1,023 non-empty subsets of 10 feature families.
- Eligible targets 101–3386: 3,286 total; Discovery 1,972, Validation 657, Blind OOS 657.
- Contest 315 and all Q141 suffix rows after 2026-10-24 are excluded.

## Per-target effect definitions

For each target, convert the already frozen strict-prior formula ranks to:

`p = 1 - (rank - 1)/(658008 - 1)`.

For each feature family i, compute a balanced marginal effect by averaging:

`p(S ∪ {i}) - p(S)`

over all 511 non-empty subsets S of the other nine feature families.

For each pair i,j, compute a balanced second-order interaction by averaging:

`p(S ∪ {i,j}) - p(S ∪ {i}) - p(S ∪ {j}) + p(S)`

over all 255 non-empty subsets S of the remaining eight feature families.

This yields 10 main-effect and 45 pairwise-interaction endpoints (55 total). Excluding the empty background subset keeps every term inside the registered Q7 formula universe and makes the contrasts balanced.

## Inference and gates

- Report target-level effect series and Discovery / Validation / Blind OOS summaries.
- Blind OOS: two-sided block sign-flip tests, block length 20, 20,000 replicates.
- 95% circular moving-block bootstrap intervals, 20,000 replicates.
- Holm-Bonferroni across all 55 registered endpoints.
- Practical effect threshold: absolute mean effect at least 0.005 percentile units.
- No selection or tuning on Validation or Blind OOS.
- A feature/pair is only flagged if both Holm-adjusted p<0.05 and the practical threshold are met.

## Guardrails and limitations

All formula ranks must come from the pinned Q7 strict-prior runner and its hash-verified target parts. The runner must score and write the target before adding that draw to state. The Q7 archive must match the Q141 prefix exactly. The current target outcome is only an evaluation label for ranks already produced from prior data.

The analysis is descriptive factorial attribution, not causal inference and not a deployable predictor. Historical Blind OOS is exposed prior research history, not virgin prospective evidence. Holm controls the 55 B9 endpoints only; it does not account for the full Q00–Q141 research family.

No canonical archive edits, shadow insertion, engine promotion, automatic merge, or changes to PRs #6/#7/#8. A null result is an acceptable completed stage.
