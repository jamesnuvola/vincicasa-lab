# Q146 — official-source quarantine sensitivity (2026-11-13)

## Purpose and scope

This is a post-hoc provenance sensitivity audit of the already frozen Q146 target ledger. It does not change the preregistered Q146 result, Q145 freeze, canonical archive, shadow forecasts, Q60 gate, or any engine. The sensitivity is descriptive and is not a new confirmatory test.

## Primary-source status at 2026-11-13 20:50 Europe/Rome

The official VinciCasa November archive at https://www.vincicasa.it/archivio-estrazioni/2026/novembre lists contests 315 (11 November), 316 (12 November), and 317 (13 November) as “In programmazione / In attesa”. The official Sisal November archive lists the contest detail links for 315 and 316, but the retrieved official detail-page text exposes the date and prize profile, not the five drawn numbers:

- Contest 315 detail: https://www.sisal.it/estrazioni/vincicasa/concorso-315/11-novembre-2026
- Contest 316 detail: https://www.sisal.it/estrazioni/vincicasa/concorso-316/12-novembre-2026
- Sisal November archive: https://www.sisal.it/estrazioni/vincicasa/2026/novembre

The canonical repository archive (Git blob SHA-1 `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`) contains:
- 2026-11-11: 1, 21, 22, 27, 29
- 2026-11-12: 2, 4, 7, 23, 33

These two rows are repository-present but their five numbers are not exposed in the primary-source pages retrieved in this audit. Treat both as unresolved for source-clean prospective evaluation; do not infer that repository/archive agreement is independent official verification.

## Q146 Blind OOS source-clean sensitivity

The original Q146 historical Blind OOS contains seven targets (2026-11-06 through 2026-11-12). The final two targets (11 and 12 November) are excluded here because their numbers are not primary-source exposed. The five source-visible targets 6–10 November are retained.

This is a post-hoc subset sensitivity computed from the persisted Q146 target ledger (Git blob SHA-1 `f2200d709bc036570f2fcd47ea73acaedd655b04`); no model, ranking, weight, temperature, or outcome was refit.

| Endpoint | Mean Brier gain | 95% circular block-bootstrap CI | Exact two-sided sign-flip p | Holm p |
|---|---:|---:|---:|---:|
| Borda vs uniform | -0.0000018986 | [-0.0000450621, +0.0000339165] | 0.9375 | 1.0000 |
| Equal-type inclusion vs uniform | +0.0000180318 | [-0.0000243225, +0.0000603862] | 0.6875 | 1.0000 |
| APP vs uniform | -0.0000175628 | [-0.0000707225, +0.0000299659] | 0.6250 | 1.0000 |
| Borda vs inclusion | -0.0000199304 | [-0.0000419976, -0.0000019989] | 0.3125 | 1.0000 |
| Borda vs APP | +0.0000156642 | [-0.0000106046, +0.0000419331] | 0.5625 | 1.0000 |

Bootstrap: 20,000 circular moving-block replicates, block length 2, target-level scores only; deterministic Mulberry32 seeds 14605–14609. Exact sign-flip enumerates all 32 assignments for five target-level differences. Holm correction covers these five sensitivity endpoints. With only five targets, the inference is extremely low-power; this subset is a provenance check, not a replacement for the preregistered seven-target result.

No endpoint is significant after Holm, and no positive, stable pairwise calibration advantage is demonstrated.

## Consequences and guardrails

- Preserve the Q145 freeze for target 2026-11-13 exactly as recorded (history cutoff 2026-11-12). Do not rewrite it. Because its history cutoff includes the unresolved 11–12 November rows, do not count it as a source-clean confirmatory prospective case until those outcomes are verified from a primary source.
- The current main research queue reports 25 complete prospective paired cases. At least the latest two dates are source-unresolved in this audit; therefore 25 must not be described as 25 source-clean cases. A provisional ceiling is 23, subject to recomputation against the per-target paired ledger and all other gate conditions.
- Do not append or reconstruct missing freezes. Keep unresolved results quarantined from Q60 eligibility until primary-source number exposure is obtained.
- Next action: retrieve the official Bollettini Ufficiali or another primary-source record that exposes all five numbers for contests 315 and 316; then run an append-only provenance reconciliation. If primary evidence remains unavailable, preserve the quarantine.
- No canonical archive mutation, no engine promotion, no merge, no rebase, and no changes to PRs #6, #7, or #8.
