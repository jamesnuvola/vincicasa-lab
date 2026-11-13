# Q146 — official-source reconciliation addendum (2026-11-13)

## Correction to the earlier quarantine note

At approximately 20:52 Europe/Rome, the primary VinciCasa root archive became available with the five numbers for contests 315 and 316. This supersedes the conservative quarantine status recorded in `q146_official_source_quarantine_sensitivity_2026-11-13.md`.

The official root archive explicitly lists:
- Contest 316, 12 November 2026: **2, 4, 7, 23, 33**.
- Contest 315, 11 November 2026: **1, 21, 22, 27, 29**.

The same five numbers are repeated in the page's expanded result details. Source: https://www.vincicasa.it/archivio-estrazioni (retrieved 2026-11-13; result rows at lines 165–166 and expanded numbers at lines 197–219).

The earlier monthly page https://www.vincicasa.it/archivio-estrazioni/2026/novembre still shows contests 315–317 as pending (lines 183–185). That page is stale relative to the primary root archive. The correct resolution is to use the current root archive, not to retain the quarantine solely because the monthly page lagged.

## Consequences for SONAR

- The canonical archive rows for 2026-11-11 and 2026-11-12 are now primary-source verified. The canonical archive itself was already correct and was not modified.
- Q146's original seven-target Blind OOS (2026-11-06 through 2026-11-12) can remain the source-clean historical Blind OOS. The original Q146 report and statistics are unchanged; the 5-target calculation in the earlier quarantine note is retained as a conservative historical sensitivity only and is no longer the eligible sample definition.
- Q145's 2026-11-13 freeze remains byte-for-byte unchanged, with history cutoff 2026-11-12 and outcome null. Its historical cutoff is now source-clean through 12 November. The 13 November target itself remains pending; do not score it until the official result appears.
- The previous provisional Q60 ceiling of 23 based on excluding 11–12 November is superseded. Main currently records 25 complete pairs; the two previously unresolved dates are now source-verified. Q60 still has only 25/200 cases and remains ineligible for promotion. Recompute the exact gate ledger before any eligibility count is certified.
- The official root archive currently exposes contest 316 as the latest result; contest 317 (13 November) is not yet listed. No outcome is inserted for 13 November.

## Governance

No canonical archive mutation, no freeze mutation, no gate mutation, no engine promotion, no merge or rebase. PRs #6, #7 and #8 remain untouched. The prior quarantine note is preserved as an accurate record of the earlier page state; this addendum supersedes its eligibility conclusion.
