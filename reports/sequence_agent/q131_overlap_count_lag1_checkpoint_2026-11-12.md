# Q131 checkpoint — overlap-count lag-1 Markov diagnostic

- Generated: 2026-11-12T00:41:31Z
- Source main commit: 06e9e470054a86a0b710657db35e0c2259ef6b0a
- Source data blob: 40f317e2d0067e061c46ab799d66f777a0e087c0
- Canonical archive: 3,404 draws through 2026-11-10.
- Walk-forward: 3,204 targets after 200-draw warm-up; 1,922 / 641 / 641 chronological split.
- Models: exact hypergeometric M0; marginal prequential M1; lag-1 conditional M2, shrinkage 200.
- Initial exploratory computation preceded the formal written specification; retain EXPLORATORY status.

## Current decision

`NO_OVERLAP_MARKOV_INCREMENTAL_LIFT_DEMONSTRATED`

- M1 and M2 underperform M0 in Discovery, Validation and Blind OOS on Brier and log-loss.
- M2 underperforms M1 on all six segment/metric comparisons.
- Four Blind OOS inference endpoints have Holm-adjusted p-values of 1.0; all bootstrap intervals include zero.
- Contest 315 remains provisional: Sisal confirms contest and prize counts; two secondary sources agree on 1, 21, 22, 27, 29. Do not append to canonical archive or increment Q60.
- Q60 remains 23/200; no missing freezes reconstructed.

## Recovery / next action

1. If replay fails, inspect the exact failing check and compare the committed ledger prefix before changing statistical logic.
2. Do not modify the source archive or historical freezes in this experiment.
3. Wait for the official five-number combination for contest 315; then evaluate existing freezes append-only.
4. Continue Q60 toward 200 complete prospective paired targets.
5. Keep this PR draft and require human review; do not merge or promote any engine.
