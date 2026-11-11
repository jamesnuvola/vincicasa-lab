# Q108 — post-run source reconciliation (2026-11-11)

## Finding

The archive provenance remains conflicted after the Q108 analysis was run.

- The official VinciCasa November archive still lists contest 314 (10 November 2026) as **In programmazione / In attesa**: https://www.vincicasa.it/archivio-estrazioni/2026/novembre
- The official Sisal result page identifies contest 314 dated 10 November 2026 and publishes its prize distribution (0 five-point winners, 13 four-point, 329 three-point, 3,008 two-point), but the five drawn numbers are not exposed in the text representation available to this audit: https://www.sisal.it/estrazioni/vincicasa/concorso-314/10-novembre-2026
- An independent third-party result page reports **1, 7, 11, 22, 25**, matching the row automatically appended to `data/storico_daily.csv`: https://www.estrazionedellotto.it/vinci-casa/risultati-vinci-casa

## Data-governance decision

The Q108 analysis therefore continues to use only the 3,403-row prefix through 2026-11-09. The appended 2026-11-10 row remains excluded. This is deliberately conservative: official confirmation that contest 314 occurred is not the same as official text-level confirmation of its exact five-number combination.

No canonical archive row, generated app data, forecast freeze, Q60 record, H101 or H102 record was changed.

## Next action

Obtain an official bulletin or an official rendering that exposes the exact five numbers for contest 314. Only then reconcile the existing appended row and evaluate pre-existing freezes. Do not reconstruct missing forecasts or create retrospective freezes.
