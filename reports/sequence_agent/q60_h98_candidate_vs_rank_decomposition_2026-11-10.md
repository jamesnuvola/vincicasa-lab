# Q60-H98 — decomposition of candidate coverage vs rank ordering

**Status:** exploratory diagnostic; no promotion effect.  
**Prepared:** 2026-11-10 09:38 Europe/Rome.  
**Branch:** `research/q60-nov09-reconciliation-20261110-run11` (PR #36).

## Question

The interim H97 comparison shows more positional hits in Top5/Top10 but equal aggregate Top20 hits over 22 paired prospective targets. Is that difference caused by new candidates entering the positional Top20, or by reordering candidates already present in both Top20 lists?

## Frozen source data

Only already-frozen, pre-target rows were read. No forecast list, timestamp, cutoff or target outcome was modified.

- Global shadow ledger: `reports/sequence_agent/shadow_forecasts.csv`, blob SHA `ffd9ab70fb27897d0dd3126391ca931b60ba25ac`.
- Positional shadow ledger: `reports/sequence_agent/position_mix_shadow.csv`, blob SHA `3b2fe6055d2075308fba742022dd6e527f634770`.
- Registered gate on this branch: `reports/sequence_agent/prospective_promotion_gate.json`, blob SHA `cc17e46d737202564ea14f9d58273d1002f96db6`.

The matched sample contains 22 target dates, 2026-10-19 through 2026-11-09. Each row has previous-day cutoff and an existing freeze timestamp before the target date. No missing freeze was reconstructed. The canonical archive on this branch ends at 2026-11-09; no paired 2026-11-10 freeze is present in either ledger at this checkpoint.

## Definitions

For target t:

- (G_t): global `freq_100` Top20.
- (P_t): positional `position_seed_mix_top20_v1` Top20.
- (C_t = G_t \cap P_t): shared Top20 candidates.
- (A_t): five canonical winning numbers.
- (W_t = A_t \cap C_t): winning numbers present in both candidate sets.
- (r_G(n)), (r_P(n)): one-based ranks in the respective frozen Top20 lists.
- For each shared winning number, (delta_{t,n}=r_P(n)-r_G(n)). Negative values mean the positional engine ranks that shared winner earlier.

The target-level diagnostic is the mean of (delta_{t,n}) over (W_t). If (W_t) is empty, the target contributes zero and is separately counted; no target is silently dropped.

## Measured interim results (22 pairs)

### Candidate-set overlap

- Mean shared candidates: **15.818 / 20**.
- Mean Jaccard similarity: **0.6556**.
- Intersection size: 15 on 8 targets, 16 on 10 targets, 17 on 4 targets.

### Top20 coverage decomposition

- Global Top20 hits: **56**.
- Positional Top20 hits: **56**.
- Winning numbers present in both Top20 sets: **45**.
- Global-only Top20 winning numbers: **11**.
- Positional-only Top20 winning numbers: **11**.

Thus the aggregate Top20 hit count is equal, but the two lists do not contain exactly the same winning numbers.

### Top5 / Top10 decomposition

| Endpoint | Global hits | Positional hits | Global hits from shared Top20 | Positional hits from shared Top20 |
|---|---:|---:|---:|---:|
| Top5 | 16 | 21 | 16 | 21 |
| Top10 | 28 | 32 | 28 | 32 |

All Top5 and Top10 winning hits in this 22-target sample were in the intersection (C_t). None of the hits unique to either Top20 candidate set entered that engine's own Top5 or Top10. The observed Top5/Top10 difference is therefore attributable to ordering of shared candidates in this sample, not to unique Top20 candidates entering the first 10 positions.

### Shared-winner rank displacement

Across the 45 shared winning-number observations:

- Hit-weighted mean rank displacement: **−0.4667 positions**.
- Mean of the 22 target-level mean displacements: **−0.2614 positions**.
- Target-level median: **0**.
- Positional earlier / global earlier / tie by target-level mean: **9 / 9 / 4**.

A two-sided exact paired sign-flip test on the 22 target-level means gives **p = 0.76298**. A circular moving-block bootstrap (block length 3, 10,000 replicates, seed 9801) gives a 95% interval of **[−1.947, +1.345] positions**.

This diagnostic does not show a statistically reliable rank-ordering advantage. It is post-hoc relative to the H97 interim results and is explicitly exploratory; its p-value is not confirmatory evidence and does not alter the registered H97 or Q60 gate.

## Quantitative hypothesis H98 for future prospective pairs

For the next **178 genuinely new complete paired targets** after this registration, with no backfill or reconstructed freeze:

[
C_t = G_t \cap P_t, \qquad
W_t = A_t \cap C_t
]

[
D_t =
\begin{cases}
\frac{1}{|W_t|}\sum_{n\in W_t}(r_P(n)-r_G(n)), & |W_t|>0 \\
0, & |W_t|=0
\end{cases}
]

Two-sided hypothesis:

- (H_0: E[D_t]=0)
- (H_1: E[D_t]\ne 0)

Negative (D_t) favours positional ordering among winners already present in both Top20 sets. Report the fraction of targets with (|W_t|=0), candidate overlap, and wins/losses/ties alongside the mean.

Frozen protocol for the future cohort:

1. Use only the two registered engines and their actual pre-target frozen Top20/Top10/Top5 lists; do not retune.
2. Begin with the next genuinely frozen paired target after registration. The absent 2026-11-10 freeze must not be reconstructed.
3. Use a two-sided Monte Carlo paired sign-flip test with 1,000,000 sign draws, plus-one p-value, fixed seed 9802.
4. Use circular moving-block bootstrap, block length 20, 10,000 replicates, seed 9802.
5. At the final analysis, apply Holm across H97 Top5/Top10/Top20 and this H98 rank-displacement endpoint as one four-endpoint secondary family. The primary Q60 Top20 5-of-5 promotion gate remains unchanged.
6. No promotion unless the primary Q60 gate and human review are both satisfied.

The 22 interim targets above are not included in the H98 future-cohort test.

## Current gate and limits

- PR #36 branch gate: **22/200** complete paired targets; 178 remain.
- Official `main` gate remains **21/200** until PR #36 is human-reviewed and integrated.
- No paired 2026-11-10 freeze is present in the source ledgers at this checkpoint.
- H97 interim Top5/Top10/Top20 tests remain non-significant after Holm (0.3750 / 0.8633 / 1.0000).
- This is a prospective shadow diagnostic only; it is not a historical walk-forward discovery/validation/blind-OOS experiment.
- No model promotion, no freeze edit, no merge, and no change to PRs #6, #7 or #8.

## Next action

Continue Q60 append-only collection from the next genuinely pre-target paired freeze. Complete the Q92 rerun independently. Keep both engines and all frozen lists unchanged until the registered sample and human review gates are met.
