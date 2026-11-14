# Q145 outcome reconciliation — contest 317 (2026-11-13)

**Status:** OUTCOME_RECONCILED_DESCRIPTIVE_ONLY  
**Freeze:** unchanged; this file is an append-only outcome addendum.

## Source reconciliation

The canonical repository archive at main commit `975b8f570102ef80dc82643c425da8831534bf75` now contains:

- 2026-11-13: **2, 16, 21, 27, 30**
- Archive blob: `d9b4fd19654bb430c41954d2695c67ff41b8ebae`

The repository updater `scripts/aggiorna_estrazioni.py` reads the official VinciCasa URLs `https://www.vincicasa.it/archivio-estrazioni` and `https://www.vincicasa.it/`. Workflow [43534315854](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43534315854) completed successfully and its log recorded: `Aggiunta: 2026-11-13 -> [2, 16, 21, 27, 30]`.

The original Q145 freeze remains byte-for-byte unchanged. It was frozen at 19:18:07 Europe/Rome on 13 November with cutoff 12 November. The old cutoff archive blob and source shadow blob remain recorded in the freeze.

## Q145 prospective score — one target only

Actual quintet: **2 · 16 · 21 · 27 · 30**.

| Model | Top20 hits | Top10 hits | Modal Top5 hits | Actual quintet probability | Gain vs uniform (nats) |
|---|---:|---:|---:|---:|---:|
| Borda | 4/5 | 4/5 | 2/5 | 0.000006305331 | +1.422857 |
| Equal-type inclusion | 4/5 | 3/5 | 2/5 | 0.000005705299 | +1.322857 |
| Uniform | — | — | — | 0.000001519738 | 0 |

Both Q145 distributions assigned the realized quintet about 4.15× and 3.75× the uniform probability, respectively. This is a one-target log-score observation, not evidence of a validated advantage.

## Main Sequence Agent — 43 frozen configurations

The 43 pre-target rows in `reports/sequence_agent/shadow_forecasts.csv` were evaluated descriptively against the same result:

- 41 unique Top20 sets.
- Top20 hit-count histogram: 1 hit: 2 configs; 2 hits: 5; 3 hits: 17; 4 hits: 17; 5 hits: 2.
- 2/43 Top20 sets achieved 5/5; 19/43 achieved 4+/5.
- Mean Top20 hits: 3.2791.
- No Top10 or Top5 achieved 5/5.

An exact joint null was calculated by enumerating all 658,008 possible 5-of-40 quintets against the same 43 frozen Top20 sets, thereby retaining dependence between configurations:

- P(at least one Top20 5/5) = 0.392816.
- P(at least two Top20 5/5) = 0.200210.
- P(at least 19 configurations with 4+ Top20 hits) = 0.069770.

These are descriptive post-outcome family statistics, not confirmatory p-values: the summary endpoints were not preregistered for this single target. The original 43 CSV rows remain `FROZEN_PENDING`; this addendum does not edit or overwrite them. The normal Sequence Agent reconciliation still needs to append outcome fields.

## Decision

- Q145 freeze unchanged.
- No engine promotion.
- No retuning after the target.
- Continue prospective accumulation with the frozen PMF and retain one-target outcomes in chronological order.
- Do not interpret a single positive log-score as proof of predictability.
