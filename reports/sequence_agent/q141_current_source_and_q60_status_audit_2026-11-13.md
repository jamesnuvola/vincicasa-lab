# VinciCasa SONAR — current source/prospective status audit

Checked: 2026-11-13, approximately 12:45 Europe/Rome.

## Official results

The official VinciCasa archive currently lists:
- Contest 315, 2026-11-11: 1, 21, 22, 27, 29.
- Contest 316, 2026-11-12: 2, 4, 7, 23, 33.
- Contest 317, 2026-11-13: not yet listed as a published result at the time of this check.

Source: https://www.vincicasa.it/archivio-estrazioni

## Canonical repository state

On `main`, `data/storico_daily.csv` has Git blob SHA-1 `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`; the canonical retrospective report records 3,406 draws through 2026-11-12. The archive now includes contests 315 and 316.

The Q141-D2 experiment deliberately remains pinned to the earlier C0 snapshot: 3,404 eligible draws through 2026-11-10, archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103`. The two later draws are not inserted into D2's historical ledger or split.

## Q60 prospective gate

`reports/sequence_agent/prospective_promotion_gate.json` on `main` has Git blob SHA-1 `ab6600494731d873ea6aca2cd705e948fd3f6198` and records 25 valid complete paired prospective targets against 200 required. `promotion_allowed=false`.

The current 25/200 count supersedes the earlier 23/200 status, because the official archive now exposes the previously pending contest 315 result and contest 316. This is a source reconciliation, not a model promotion. The 200-target gate remains unmet.

No Q60 freeze, shadow forecast, canonical archive, or production engine was modified in this cycle.
