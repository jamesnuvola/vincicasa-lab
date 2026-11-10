# Q60-H97 independent interim replay — 2026-11-10

## Scope

Independently recomputed the already registered 22 prospective paired freezes dated 2026-10-19 through 2026-11-09 from the branch's raw `shadow_forecasts.csv`, `position_mix_shadow.csv`, and canonical `data/storico_daily.csv`.

No forecast was generated, reconstructed, retuned, or edited. For every paired target:
- both engines had an evaluated pre-existing freeze;
- both `history_cutoff` fields equal the preceding calendar date;
- the actual quintet was read from the canonical archive;
- hits were recomputed from the frozen Top5, Top10, and Top20 lists.

The canonical archive currently ends on 2026-11-09. No later target is present in this snapshot.

## Recomputed paired results

22 complete pairs, 2026-10-19 through 2026-11-09.

| Prefix | Global `freq_100` mean hits | Positional mix mean hits | Mean paired delta | Positional wins / losses / ties |
|---|---:|---:|---:|---:|
| Top5 | 0.7272727 | 0.9545455 | +0.2272727 | 6 / 1 / 15 |
| Top10 | 1.2727273 | 1.4545455 | +0.1818182 | 7 / 4 / 11 |
| Top20 | 2.5454545 | 2.5454545 | 0.0000000 | 7 / 7 / 8 |

Exact two-sided paired sign-flip tests were independently enumerated over the non-zero paired differences:

| Prefix | Non-zero pairs | Raw exact p | Holm-adjusted p (family size 3) |
|---|---:|---:|---:|
| Top5 | 7 | 0.1250000 | 0.3750000 |
| Top10 | 11 | 0.4316406 | 0.8632813 |
| Top20 | 14 | 1.0000000 | 1.0000000 |

These exact results match the persisted exploratory report. The persisted circular moving-block bootstrap intervals (10,000 replicates, block length 3) are not independently regenerated in this replay; they remain as reported in the branch's exploratory analysis.

## Interpretation

The positional mix has higher descriptive Top5 and Top10 mean hit counts in this small sample, while Top20 coverage is equal. None of the exact paired tests survives Holm correction. This does not validate H97 and does not support a model promotion.

The registered primary Q60 gate remains 22/200 complete pairs, with 178 additional pairs required. The positional engine has 0/22 Top20 5-of-5 outcomes; `freq_100` has 1/22. Exact McNemar p=1.0. Promotion remains disallowed.

## Next action

Continue append-only collection of the two existing engines, frozen before each target with previous-day cutoff. Do not retune. Re-run the registered H97 three-endpoint paired inference at 200 complete pairs, alongside the unchanged primary Q60 Top20 5-of-5 gate. Human review remains mandatory.
