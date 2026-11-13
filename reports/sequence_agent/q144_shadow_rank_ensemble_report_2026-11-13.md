# Q144 — Family-balanced shadow rank ensemble

**Decision:** no promotion; historical lift not established.

## Design
- 42 pre-target component forecasts per date: 24 family, 12 pair, 6 chain.
- Family-balanced Borda: average 20..1 rank points within each type, then sum the three type scores.
- Equal-type inclusion consensus is a secondary comparator; frozen APP Top20 is an external comparator.
- Chronological splits: 18 Discovery, 6 Validation, 7 historical Blind OOS.

## Results
| Split | Borda mean hits | Inclusion mean hits | APP mean hits | Uniform expectation |
|---|---:|---:|---:|---:|
| Discovery | 2.5556 | 2.6667 | 3.5000 (6 dates) | 2.5000 |
| Validation | 2.1667 | 2.5000 | 2.6667 | 2.5000 |
| Blind OOS | 2.7143 | 2.8571 | 2.2857 | 2.5000 |

Blind OOS paired mean differences:
- Borda − APP: +0.4286; block-bootstrap 95% CI [0.0000, 0.7143]; exact one-sided sign-flip p=0.1875; Holm p=0.5625.
- Borda − inclusion: −0.1429; 95% CI [−0.4286, 0.1429]; p=0.8750; Holm p=0.8750.
- Borda − uniform: +0.2143; 95% CI [−0.3571, 0.5000]; exact hypergeometric-sum p=0.3606; Holm p=0.7213.

No endpoint is significant after Holm. Blind OOS contains only seven target dates.

## Integrity
- 3,406 canonical draws and 1,364 shadow rows pinned by Git blob SHA.
- 31 completed target dates and 1,321 historical rows reconciled against the canonical archive.
- 1,364 strict-prior cutoff and pre-target timestamp checks.
- 42 component forecasts per target (24/12/6); APP is excluded from the ensemble input.
- 43 pending component rows for 2026-11-13 remain outcome-free.
- 42 component rows have a one-day-stale but still prior cutoff; no leakage was detected.\n- Five target groups contain multiple component/APP freeze timestamps; each row was checked independently and all timestamps precede the target draw, while the history cutoff remains consistent within each target.

## Interpretation and next action
This is a retrospective aggregation of forecasts that were individually frozen before their targets. The aggregation rule itself was registered after those historical outcomes existed, so the seven-date Blind OOS is not virgin confirmation. The rule is not a validated engine and does not estimate exact-ticket probability.

Preserve the separate 2026-11-13 Q144 Top20 freeze. Reconcile only after official publication. Accumulate at least 100 consecutive prospective Q144 freezes before confirmatory inference; do not tune weights on the 31 historical dates.
