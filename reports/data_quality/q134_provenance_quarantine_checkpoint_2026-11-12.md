# Q134 checkpoint — 2026-11-12

## Recovery state
- Current main: 0bf1ef0d39afb671ff83e519489f16b0c24eb15a.
- Q132 PR #80 remains open/draft; its strict row-bound parser is not on main.
- Q133 PR #81 remains open/draft and is based on older main commit 50078e442509564bbc1d150ac6aea82421e22979.
- Q133's clean historical source ledger ends at 2026-11-10: 3,204 targets, split 1,922 / 641 / 641. Its dedicated replay and full repository CI on head 795056cfa29dc16d6714630a4feb4d89d03a53a0 both completed successfully.

## Root cause
The scheduled updater on main still uses flattened HTML text and a 260-character proximity window. It appended 2026-11-11 = 1,21,22,27,29 without preserving the raw HTML. The exact token origin cannot be reconstructed. The official VinciCasa archive still shows contest 315 pending; the official Sisal detail confirms contest/date/prize profile but the retrieved text does not expose the five numbers. Secondary sources agree, which is corroboration but not primary number provenance.

## Measured downstream impact
- Main archive: 3,405 rows through 2026-11-11.
- latest_metrics.json: 3,405 draws / 3,205 targets.
- APP active walk-forward: OOS 641 targets, ending 2026-11-11.
- 43 global freezes and one positional freeze for 2026-11-11 are marked EVALUATED using the provisional numbers.
- Q60 gate reports 24 paired dates, including 2026-11-11. Excluding the one unresolved date gives 23 eligible pairs.
- 43 global + one positional freeze for 2026-11-12 are pending but all use 2026-11-11 as their history cutoff. They are not clean primary-source forecasts until the prior outcome is verified.

## Quantitative rule
N_eligible = N_reported - I(unresolved date is included)
24 - 1 = 23.

The APP OOS count has a clean upper bound of 640 after excluding 2026-11-11, but its aggregate metrics were not recomputed from a per-target APP ledger; do not quote adjusted APP OOS means or p-values.

## Decision
Q134 is a provenance-quarantine audit, not a predictive experiment. A new predictive walk-forward was deliberately not run because main's current metrics and next-target history include an unresolved outcome. Q133 is the last clean historical-prefix walk-forward through 2026-11-10.

## No mutation
The canonical CSV, generated JSON, existing freezes, promotion gate and production engine were not changed. No historical freeze was reconstructed. No Q60 increment is accepted by this audit.

## Next action
1. Obtain primary-source confirmation of the five numbers for contest 315.
2. Keep 2026-11-11 excluded from Q60 until then.
3. Do not score the 2026-11-12 freezes as clean primary OOS while their cutoff remains 2026-11-11.
4. After human review, apply a provenance-aware gate/refresh; preserve all freeze identities and timestamps.
