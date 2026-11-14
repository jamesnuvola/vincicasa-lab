# Q141-A22 — Conditional response-shift audit

**Decision:** state persistence shift not confirmed; conditional capture response drop suggestive but not confirmed after Holm; Q75 predictive skill not confirmed.

## Observed structure

- A20 historical terminal high-state run: 118 targets, 2026-06-29 to 2026-10-24.
- A21 extension: 20/20 high-state targets; combined uninterrupted high run: 138.
- State ACF(1): 0.902740; ACF(20): 0.555641.

## Conditional capture response

- Previous terminal high-run mean: 0.657112.
- A21 extension mean: 0.566665.
- Difference versus preceding 20 targets: -0.038799.
- Mean Q75 MSE gain versus prior-400 baseline: -0.004329.
- Circular block-5 bootstrap 95% interval for the 20-target MSE gain: [-0.00769998367485, -0.001333325824527506].

## Dependence-preserving null

Twelve stationary-bootstrap diagnostics were run (20,000 replicates each): eight state-persistence tests using the full A20 history and Blind OOS subset, plus four lower-tail capture-response tests conditional on the terminal high-state run. Holm correction was applied jointly across all 12 tests.

| Test | Block length | Raw p | Holm p |
|---|---:|---:|---:|
| state_observed_high_count::full_a20_history::L20 | 20 | 0.054397 | 0.435178 |
| state_observed_high_count::full_a20_history::L50 | 50 | 0.083196 | 0.582371 |
| state_observed_high_count::full_a20_history::L100 | 100 | 0.099945 | 0.599670 |
| state_observed_high_count::full_a20_history::L200 | 200 | 0.103645 | 0.599670 |
| state_observed_high_count::blind_oos_a20::L20 | 20 | 0.114244 | 0.599670 |
| state_observed_high_count::blind_oos_a20::L50 | 50 | 0.175791 | 0.599670 |
| state_observed_high_count::blind_oos_a20::L100 | 100 | 0.191540 | 0.599670 |
| state_observed_high_count::blind_oos_a20::L200 | 200 | 0.213989 | 0.599670 |
| capture_mean_lower_tail::terminal_high_run::L5 | 5 | 0.014799 | 0.134493 |
| capture_mean_lower_tail::terminal_high_run::L10 | 10 | 0.013449 | 0.134493 |
| capture_mean_lower_tail::terminal_high_run::L20 | 20 | 0.011899 | 0.130893 |
| capture_mean_lower_tail::terminal_high_run::L40 | 40 | 0.009500 | 0.113994 |

## Chronological splits

| Split | Targets | High-state rate | Longest high run | Mean Q75 MSE gain vs mean400 |
|---|---:|---:|---:|---:|
| discovery | 911 | 0.0670 | 16 | -0.000081 |
| validation | 437 | 0.4096 | 125 | -0.000336 |
| blind_oos | 438 | 0.2694 | 118 | -0.000034 |

## Interpretation and limits

The 20/20 high-state extension is a continuation of the prior terminal high-state run, not a newly observed state transition. The state indicator is strongly autocorrelated. The lower capture response in the extension is descriptively notable, but the joint 12-test Holm family does not confirm a shift. A20/A21 historical Blind OOS is exposed evidence; this analysis was formulated after the A21 extension was visible and is exploratory.

The response is structural capture, not candidate-number or exact-quintet accuracy. The stationary bootstrap preserves temporal dependence in scalar summaries but not the complete multivariate formula-rank panel. No engine is promoted and no freeze is changed.

Next action: Keep the 2026-11-14 A21 freeze immutable. After the official result is ingested, append-only evaluate it; continue prospective monitoring without retuning q75 or the 400-target window.
