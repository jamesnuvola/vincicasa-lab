# Q60-H100 — exclusive-candidate complementarity after size control

**Status:** exploratory, not confirmatory.  
**Prepared:** 2026-11-10 11:47 Europe/Rome.  
**Branch:** `research/q60-nov09-reconciliation-20261110-run11`.

## Question

Do the positional engine's Top20 candidates that are absent from the global `freq_100` Top20 add more winning numbers than the same-sized global-only slice? This controls the unequal-union-size issue that would make a raw union-hit comparison misleading.

For each paired target, let (I_t=|G_t\cap P_t|) and (m_t=20-I_t). Both exclusive slices (P_t\setminus G_t) and (G_t\setminus P_t) contain exactly (m_t) candidates.

Primary paired endpoint:

[
D_t=|A_t\cap(P_t\setminus G_t)|-|A_t\cap(G_t\setminus P_t)|.
]

Under the equal-size exchangeability null, swapping the two exclusive slices within each target leaves the null distribution unchanged. We enumerate all (2^{22}) sign assignments.

For each exclusive slice, the absolute null is target-specific:

[
K_t\sim\operatorname{Hypergeometric}(N=40, K=m_t, n=5),
]

with exact discrete convolution across targets. The union (G_t\cup P_t) is tested separately using its actual target-specific size.

## Source and prior-only audit

The replay uses 22 already frozen paired targets from **2026-10-19 through 2026-11-09**. Both forecasts use the previous calendar day's cutoff and were frozen before the nominal 19:00 Europe/Rome draw time. No missing freeze was reconstructed.

Input Git blob SHAs:

- global ledger: `ffd9ab70fb27897d0dd3126391ca931b60ba25ac`
- positional ledger: `3b2fe6055d2075308fba742022dd6e527f634770`
- canonical archive: `8d3e19f0b417024ba32e576697eac0648d12ab86`

## Measured results

- Mean Top20 Jaccard: **0.65560**.
- Mean intersection: **15.82** candidates.
- Each engine contributes a mean **4.18** exclusive candidates per target (range 3–5).
- Mean union size: **24.18** (range 23–25).
- Positional-only hits: **11**.
- Global-only hits: **11**.
- Primary paired difference: **0.000 hits/target**.
- Exact two-sided paired sign-flip: **p = 1.000**.
- Circular block bootstrap, length 3, 10,000 replicates, seed 1001002: 95% CI for mean paired difference **[-0.3636, +0.4091]**.

Size-adjusted exact nulls:

| Endpoint | Observed | Expected | Exact upper-tail p |
|---|---:|---:|---:|
| Positional-only hits | 11 | 11.5 | 0.61723 |
| Global-only hits | 11 | 11.5 | 0.61723 |
| Union hits | 67 | 66.5 | 0.50226 |

The 10-test Holm family includes H97's three cascade endpoints, H98's shared-winner rank displacement, H99's MRR and DHG, and the four H100 endpoints. Every adjusted p-value is **1.000**.

**Decision: no incremental complementarity demonstrated.**

## Current pending target

On the current main ledgers, both unchanged engines have a pre-target freeze for **2026-11-10**, each with history cutoff **2026-11-09**. The global freeze time is 10:53:16+01:00 and the positional freeze time is 10:55:31+01:00. Their Top20 intersection is 17/20 (Jaccard 0.73913). The target outcome is not yet present in the canonical archive, so this pair remains `FROZEN_PENDING` and is not included in the 22-pair results above.

## Limitations

- H100 was formulated after inspecting the same 22 targets used in H97-H99; it is exploratory, not a new blind OOS result.
- The union is larger than either individual Top20; its hits are therefore evaluated against target-specific hypergeometric expectations, not compared naively with a Top20 baseline.
- No discovery/validation/blind split is claimed for H100: it is a fixed-engine paired replay, not a newly fitted model.
- The Q60 primary Top20 5-of-5 promotion gate remains unchanged at 200 complete paired targets. Current official gate: 22/200; promotion disabled.

## Future confirmatory protocol

Use the next **178 complete paired targets**, including the already frozen 2026-11-10 pair once its canonical outcome is available. Keep `freq_100` and `position_seed_mix_top20_v1` unchanged. The primary endpoint is the paired positional-only minus global-only hit difference, with exact within-target sign-flip inference. Secondary endpoints are the target-specific hypergeometric excess for each exclusive slice and the union. Apply Holm across the four H100 endpoints; retain Q60's independent 5-of-5 primary promotion gate. No backfill, no freeze reconstruction, no retuning, no automatic promotion.
