# Q145 source reconciliation addendum — 2026-11-13

## Finding after the Q145 freeze

The Q145 prospective freeze uses history cutoff 2026-11-12. At registration, the November monthly archive page was stale and showed contests 315 and 316 as "In programmazione / In attesa". A fresh source check later in this run resolves the cutoff value:

- The official contest-specific page for contest 316/26, dated 12 November 2026, explicitly publishes the result **2, 4, 7, 23, 33**: https://www.vincicasa.it/archivio-estrazioni/concorso-316/12-novembre-2026
- The official general archive also lists contest 316 (12 November) as **2, 4, 7, 23, 33**, and contest 315 (11 November) as **1, 21, 22, 27, 29**: https://www.vincicasa.it/archivio-estrazioni
- The official November monthly page remains stale, showing contests 315, 316 and 317 as pending: https://www.vincicasa.it/archivio-estrazioni/2026/novembre

Decision: prefer the contest-specific detail page plus the general archive for contest 316; classify the November monthly page as stale. The repository's 2026-11-12 cutoff row is therefore independently confirmed. The Q145 freeze and its probability vectors are not changed.

At the time of this source check, contest 317 (13 November) is still shown as pending on the monthly page. Its outcome remains null in the Q145 freeze. Do not reconcile or score it until an official result is published and independently confirmed.

This addendum is append-only source provenance; it does not change the Q145 algorithm, historical scores, frozen probabilities, canonical archive, Q60, B11, or any engine.
