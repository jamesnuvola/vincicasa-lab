# Q60 — primary-source eligibility reconciliation (2026-11-13)

## Finding

The current official VinciCasa root archive now exposes all five numbers for every Q60 paired target date from 2026-10-19 through 2026-11-12, inclusive. The table contains 25 consecutive contests (292–316). In particular:
- Contest 315 / 2026-11-11: **1, 21, 22, 27, 29**.
- Contest 316 / 2026-11-12: **2, 4, 7, 23, 33**.

Primary source: https://www.vincicasa.it/archivio-estrazioni (retrieved 2026-11-13; table lines 165–195). The expanded details also show the numbers for contests 315 and 316 at lines 197–219. The November monthly subpage remains stale, but the root archive is current. The earlier Q134/Q132 quarantine based on the monthly page is superseded for these two dates; no repository outcome row is changed by this note.

## Gate reconciliation

The current main gate file `reports/sequence_agent/prospective_promotion_gate.json` was read directly:
- Git blob SHA-1: `ab6600494731d873ea6aca2cd705e948fd3f6198`
- Status: `INSUFFICIENT_PROSPECTIVE_CASES`
- Paired target dates: **25**, 2026-10-19 through 2026-11-12.
- All 25 dates fall within the official root archive's visible result table.
- Position Top20 exact-quintet hits: **0**.
- Global Top20 exact-quintet hits: **1**.
- Mean Position Top20 hits: **2.48**.
- Exact McNemar p-value: **1.000**.
- Required sample: **200**.
- Promotion allowed: **false**.

Therefore the 25 complete pairs are now source-clean with respect to the official five-number outcomes. The prior provisional ceiling of 23 is superseded. This does not alter the gate's sample-size requirement: **25/200 remains insufficient**, and no engine or strategy is promoted.

## Guardrails and next action

- No canonical archive mutation, no gate mutation, no freeze mutation, no model promotion.
- Continue append-only collection of new paired freezes with official prior history.
- Next action: accumulate 175 additional complete, source-verified paired targets; then rerun the registered gate and obtain human review. Do not infer promotion from the current hit counts.
- Q145 target 2026-11-13 remains pending because contest 317 is not yet exposed in the official root archive.
- PRs #6, #7, and #8 remain untouched and unmerged.
