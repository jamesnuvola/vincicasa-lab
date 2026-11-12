# Q133 checkpoint — 2026-11-12

## Completed
- Recovered main at `50078e442509564bbc1d150ac6aea82421e22979`.
- Replayed 3,204 targets / 134,568 ledger rows / 42 configurations per target.
- Recomputed every Top20 hit count and checked exact previous-day cutoffs.
- Ran 1,000 conditional randomizations per target, 10,000 paired circular block-bootstrap replicates (block 20), Holm across nine endpoints.
- Exactly enumerated 658,008 5-subsets for each Top5/Top10/Top20 family null on the provisional contest-315 freezes.
- Preserved Q60 at 23/200.

## Results
- Discovery mean maximum-hit difference +0.01747; nominal p for M>=4 = 0.01199, Holm = 0.10789.
- Validation mean difference -0.03095.
- Blind OOS mean difference -0.01953.
- Overall descriptive difference +0.000063.
- Decision: `NO_FAMILYWISE_MAX_DISTRIBUTION_LIFT_DEMONSTRATED`.

## Blockers
- Main contains the 2026-11-11 row, inserted by legacy updater run 43136027472 at 01:39:53 UTC.
- Official Sisal confirms contest 315 and prize profile, but retrieved official text does not expose the five numbers; official VinciCasa archive still shows pending. Secondary sources agree on 1,21,22,27,29.
- `latest_metrics.json` and `active_engine_walkforward.json` end at 2026-11-10 (3,404 draws), while canonical CSV has 3,405 draws.
- 43 global and one positional forecast for 2026-11-11 remain pending. Q60 remains 23/200.
- Q132 strict parser PR is open and not merged; main still uses the legacy proximity parser.

## Recovery / next action
No analysis-runtime test failure occurred. GitHub Node 20 replay and overall CI remain pending until this branch workflow runs. If replay fails, preserve this checkpoint and use the workflow log; do not alter frozen forecasts or Q60. Next: official primary-number provenance, sequence-agent refresh, append-only evaluation of 2026-11-11 freezes.
