# Q133 checkpoint — 2026-11-12

## Completed
- Recovered main at `50078e442509564bbc1d150ac6aea82421e22979`.
- Replayed 3,204 targets / 134,568 ledger rows / 42 configurations per target.
- Recomputed all Top20 hit counts and checked exact previous-calendar-day cutoffs.
- Ran 1,000 conditional randomizations per target, 10,000 paired circular block-bootstrap replicates (block 20), Holm across nine endpoints.
- Exactly enumerated all 658,008 5-subsets for each Top5/Top10/Top20 family null on the provisional contest-315 freezes.
- Preserved Q60 at 23/200.
- Dedicated Node 20 replay passed on both push and PR: runs 43145400153 and 43145405208; report matched and manifest 14/14 verified.

## Results
- Discovery mean maximum-hit difference +0.01747; nominal p for M>=4 = 0.01199, Holm = 0.10789.
- Validation mean difference -0.03095.
- Blind OOS mean difference -0.01953.
- Overall descriptive difference +0.0003826467 (weighted over the three chronological split means).
- Decision: `NO_FAMILYWISE_MAX_DISTRIBUTION_LIFT_DEMONSTRATED`.

## CI recovery history
1. Run 43144765617: duplicate `last` declaration caused a Node SyntaxError; renamed the target grouping variable.
2. Run 43144853286: Git blob SHA header and CSV regexes were double-escaped; corrected the NUL byte and regex literals.
3. Run 43144927106: persisted overall summary still used a value from the earlier RNG pass; changed to a split-size-weighted aggregate.
4. Run 43145054221: interpretation text still contained the old overall difference; synchronized it.
5. Run 43145167999: exact Top10/Top20 histograms differed in zero-count support; made the distribution map data-driven and initialized bins on first count.

The final dedicated Node 20 replay is SUCCESS. The general repository CI was still running when this checkpoint was written; it is not marked complete here.

## Data and governance blockers
- Main contains the 2026-11-11 row, inserted by legacy updater run 43136027472 at 01:39:53 UTC.
- Official Sisal confirms contest 315 and its prize profile, but retrieved official text does not expose the five numbers; the official VinciCasa archive and official bulletin index still stop at contest 314. Secondary sources agree on 1,21,22,27,29.
- `latest_metrics.json` and `active_engine_walkforward.json` end at 2026-11-10 (3,404 draws), while canonical CSV has 3,405 draws.
- 43 global and one positional forecast for 2026-11-11 remain pending. Q60 remains 23/200.
- Q132 strict parser PR #80 is open and unmerged; main still uses the legacy proximity parser. The strict parser also needs an existing-row reconciliation path.

## Next action
1. Obtain primary-source confirmation of all five contest-315 numbers.
2. Reconcile the already-appended row without rewriting freezes.
3. Refresh sequence-agent metrics after archive update.
4. Evaluate the 43 global and one positional 2026-11-11 freezes append-only; update Q60 only if eligible.
5. Await the general repository CI; no merge or promotion without human review.
