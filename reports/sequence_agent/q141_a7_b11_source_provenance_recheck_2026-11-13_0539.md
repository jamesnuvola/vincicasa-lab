# Q141-A7 / B11 — source provenance recheck (2026-11-13 05:39 Europe/Rome)

## Decision

The B11 prospective experiment remains active and unchanged. No target outcome was available at this check. The first prediction remains frozen; no efficacy statistic is computed.

## Root-cause resolution: contest 315 source exposure

The earlier Q134/Q132 audit correctly quarantined contest 315 while the retrieved primary-source page did not expose its five numbers. At 05:39 Europe/Rome on 2026-11-13, the official VinciCasa archive root now visibly lists:

- Contest 315, 2026-11-11: **1, 21, 22, 27, 29**.
- Contest 316, 2026-11-12: **2, 4, 7, 23, 33**.

Official source: https://www.vincicasa.it/archivio-estrazioni

The contest 315 detail page is also available at https://www.vincicasa.it/archivio-estrazioni/concorso-315/11-novembre-2026; its extracted text confirms contest/date but does not expose the numbers. The archive root table is therefore the direct source for the exact combination. The official bulletin archive lists a bulletin for 11 November, but the linked PDF exceeded the browser reader's content-size limit and was not independently inspected.

## Repository reconciliation

- Main and research-branch `data/storico_daily.csv` have the same Git blob SHA-1: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
- Archive count: 3,406 draws through 2026-11-12.
- Both contest 315 and 316 rows match the official archive root.
- Pinned A7 code commit `1a6f27adc158c47c300c992be3ef38bfa99505ec` was fetched; script blob SHA-1: `b278f9e61483e9ea8ba0b8efc2c70844ecdd859b`.

This closes the recorded primary-source exposure gap for the historical input row 2026-11-11 as of this check. It does not change the archive or retroactively alter the frozen prediction.

## Frozen prediction and quantitative check

- Target: 2026-11-13, scheduled 20:00 Europe/Rome.
- Frozen at: 2026-11-13T02:48:10.854369Z.
- Prior cutoff: 2026-11-12; 3,406 prior draws.
- M0 Top-5 set: `{1, 7, 25, 27, 36}`.
- M1 Top-5 set: `{1, 7, 25, 27, 36}`.
- Set intersection: 5/5; Jaccard = 1; divergence `D_t = 1 - |M0∩M1|/5 = 0`.

Therefore the paired Top-5 hit-share difference for this first target is exactly zero regardless of the eventual winning combination. The target still counts as the first frozen B11 observation; it is not dropped or replaced.

For a fixed Top-5 set under a uniform 5-of-40 draw:
- Expected number of hits = 0.625.
- Exact 5/5 probability = 1/658,008 ≈ 0.00000151973836.
- This is a mathematical null baseline, not evidence that either SONAR ranking is calibrated.

## Protocol integrity

- Frozen predictions: 1/200.
- Official outcomes reconciled: 0/200.
- No interim efficacy peeking.
- No retuning, no threshold changes, no family remapping.
- No new retrospective Blind OOS claim: all historical holdouts have already been exposed to SONAR research.
- Q141-A8 remains a draft for a new independent 200-target sample only after B11 closes. It is not run or tuned on B11.
- No canonical archive mutation, no forecast replacement, no shadow insertion, no engine promotion, no merge/rebase.
- PRs #6, #7 and #8 remain untouched.

## Next action

After the official contest 317 result is published, verify it from the official VinciCasa archive, append only the outcome/status to the B11 ledger while preserving the frozen prediction bytes, then freeze the next target using only the now-available prior history. Run the registered efficacy analysis only after 200 consecutive eligible outcomes are reconciled.
