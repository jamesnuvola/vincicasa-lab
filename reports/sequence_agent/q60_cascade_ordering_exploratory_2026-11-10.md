# Q60 cascade-ordering exploratory analysis — 2026-11-10

## Scope and hypothesis

Using only the 22 registered, pre-target paired freezes from 2026-10-19 through 2026-11-09, test the exploratory hypothesis that `position_seed_mix_top20_v1` ranks the five eventual winning numbers higher inside its frozen Top20 than the registered `freq_100` comparator, particularly at Top5 and Top10.

This is a secondary descriptive analysis of the already frozen Top20/Top10/Top5 lists. It does not alter the registered primary Q60 promotion endpoint (Top20 5-of-5), and it is not a new model-selection exercise.

## Data and leakage controls

- 22 complete paired target dates, 2026-10-19 through 2026-11-09.
- Each candidate list was frozen before its target and used the previous calendar day's archive cutoff.
- The 2026-11-09 outcome was read only after the pre-existing freezes had been verified.
- The 43 other global pending freezes for 2026-11-09 were reconciled for archive completeness but are not part of this registered pairwise comparison.
- No missing freeze was reconstructed; candidate lists and timestamps were unchanged.
- Historical Discovery/Validation/Blind OOS results are not pooled with this prospective sample.

## Paired hit-count results

Mean number of actual winning numbers found in each ranked prefix:

| Prefix | Global freq_100 | Positional mix | Position minus global |
|---|---:|---:|---:|
| Top5 | 0.7273 | 0.9545 | +0.2273 |
| Top10 | 1.2727 | 1.4545 | +0.1818 |
| Top20 | 2.5455 | 2.5455 | 0.0000 |

Paired wins / losses / ties for positional minus global:

- Top5: 6 / 1 / 15.
- Top10: 7 / 4 / 11.
- Top20: 7 / 7 / 8.

## Inference (exploratory)

An exact within-pair label-swap sign-flip test was enumerated over all non-zero paired differences for each endpoint. Holm correction was applied across the three endpoints.

| Prefix | Exact two-sided p | Holm-adjusted p | Circular moving-block bootstrap 95% CI |
|---|---:|---:|---:|
| Top5 | 0.1250 | 0.3750 | [0.0000, 0.4091] |
| Top10 | 0.4316 | 0.8633 | [-0.1364, 0.4545] |
| Top20 | 1.0000 | 1.0000 | [-0.3636, 0.3636] |

Bootstrap: 10,000 circular moving-block replicates, block length 3, fixed seed 20261110. The small prospective sample makes all intervals wide; this is an exploratory estimate, not a confirmation.

## Registered primary gate remains unchanged in meaning

- Complete prospective paired targets: 22/200.
- Position Top20 5-of-5: 0/22.
- Global Top20 5-of-5: 1/22.
- Exact McNemar p-value: 1.000.
- Position-minus-global 5-of-5 rate difference: -0.04545; simultaneous exact interval [-0.25698, +0.18003].
- Promotion remains disallowed; 178 paired targets remain.

## Decision and next action

The positional mix shows descriptively higher average Top5 and Top10 hit counts in this 22-target sample, but none of the three endpoints is significant after Holm correction and every block-bootstrap interval includes zero. Top20 mean coverage is identical.

Do not promote or retune either engine from this sample. Continue append-only prospective collection to 200 paired targets. Preserve the original freezes and keep the registered Top20 5-of-5 promotion gate unchanged.
