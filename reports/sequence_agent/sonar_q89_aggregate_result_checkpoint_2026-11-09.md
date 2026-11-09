# SONAR Q89 — aggregated statistical result checkpoint

Captured: 2026-11-09T18:45:07.360Z

## Execution and acceptance

- Q89 workflow run: `42668855015`; frozen execution head `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`.
- Exact-head CI before execution: `42668854880`, SUCCESS.
- All 30/30 shard jobs completed SUCCESS; 30 shard artifacts were published.
- Aggregate job `129352903532`: completed/success.
- Fail-closed Q89 acceptance step: SUCCESS with an empty error list.
- Aggregate artifact: 495303500 bytes; archive digest sha256:82e08396f62e33f469f601a20732688133baa633fbb22ae79a2d67bdb375c88e.
- Persistence job `129359549834`: in_progress; Git Data API persistence/readback and post-persistence exact-head CI are still pending.

## Quantitative scope

- Archive: 3,401 draws, 2017-07-17 through 2026-11-07.
- Strict-prior targets: 3,351 (50 prior draws minimum).
- Chronological splits: Discovery 2,011; Validation 670; Blind OOS 670.
- Nine-feature formulas: 4,686,825.
- Formula×split rows: 14,060,475.
- Global Holm family: 42,181,425 formula×split×endpoint tests.
- Holm-adjusted formula/split rows below 0.05: **0**.
- Minimum max-endpoint Holm-adjusted p-value: **1.0**.

## Frozen Validation candidate

`P9_06_09_12_14_15_17_18_19_23`

Features: `freq_500 + trend_10_vs_100 + gap_mean + overdue_ratio + position_log_frequency + neighbor_pm1_history + neighbor_pm2_history + lag_1 + lag_10`.

| Split | Top-5 hit share | Uniform | Top-10 | Uniform | Top-20 | Uniform | Mean actual-number rank | Uniform |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery | 13.7544% | 12.5% | 25.9672% | 25% | 51.3078% | 50% | 20.1434 | 20.5 |
| Validation | 12.9851% | 12.5% | 24.3284% | 25% | 49.8209% | 50% | 20.6018 | 20.5 |
| Blind OOS | 11.7612% | 12.5% | 23.5821% | 25% | 49.5522% | 50% | 20.6137 | 20.5 |

Blind OOS differences from uniform: Top-5 -0.7388 percentage points; Top-10 -1.4179 pp; Top-20 -0.4478 pp; mean rank is 0.1137 worse (higher). All three Blind OOS conservative p-value bounds and the max endpoint-family Holm value are 1.0.

## Interpretation

The selected formula looks better than uniform in Discovery, is mixed/near-baseline in Validation, and is worse than uniform on all three hit-share endpoints in Blind OOS. No formula/split survived the registered global Holm correction. **Q89 provides no evidence of predictive advantage for the nine-feature equal-weight grammar.** This is a negative research result, not a model promotion.

The Blind OOS was a historical split already exposed to prior SONAR analyses; it is not an untouched prospective confirmation. The per-target best-formula ledger remains retrospective/descriptive, not a forecast.

## Next gates

1. Complete Git Data API persistence of report, metrics manifest, 469 deterministic gzip parts and 3,351-row target ledger.
2. Verify every persisted blob by exact readback and SHA/byte count.
3. Require SUCCESS on the persisted exact-head CI, including the full Q89 acceptance validator.
4. Keep Q89 at `VALIDATED_PENDING_HUMAN_REVIEW`; do not mark COMPLETE or promote.
5. After human review, proceed to a separately preregistered ten-feature/conditional grammar experiment; do not mine the already exposed Blind OOS.
