# SONAR PSR-01 — Position-Specific Range & Residual Lab

**Status:** isolated research candidate; execution is delegated to CI for reproducible measurement.  
**Branch:** research/sonar-psr01-isolated-20261108  
**Motor status:** unchanged. No merge or promotion.

## Quantitative hypothesis
For sorted VinciCasa draw X(1)<…<X(5), each marginal position i has exact null distribution under uniformly sampled 5-subsets of {1,…,40}:
\[
\pi_i(n)=\frac{\binom{n-1}{i-1}\binom{40-n}{5-i}}{\binom{40}{5}},\quad n=i,\dots,35+i.
\]
The experimental estimate shrinks past-only empirical counts c(i,t,n) toward this exact combinatorial baseline:
\[
q_{i,t}(n)=\frac{c_{i,t}(n)+\alpha\pi_i(n)}{N_t+\alpha},\quad \alpha=20.
\]
Fixed alpha is preregistered for PSR-01; no blind OOS tuning. In addition, record past-only empirical min/max L_i(t), U_i(t) and test range coverage.

## Walk-forward and splits
- Canonical data/storico_daily.csv; strict ascending, distinct five-number draws; date validation.
- Expanding window, default warmup 250 draws; each target uses exactly rows before it.
- Target chronology split 50% discovery / 25% validation / final 25% blind OOS. Discovery and validation are descriptive; they are not used to tune alpha.
- Compare empirical-frequency mode and prior-shrunk posterior mode to exact order-statistic prior mode.
- Proper scores: Brier and log loss for posterior versus prior distribution.
- Blind-OOS inference: circular moving-block bootstrap (block length 7, 2,000 replicates, deterministic seed) for mean paired improvements and 95% intervals; one-sided benefit p-values; Holm correction across 20 blind endpoints (five positions × four metrics).

## Leakage / bias / reproducibility controls
- All counts/extrema recalculated from target prefix only. Target and future rows excluded.
- The theoretical baseline is derived from the uniform 5-combination mechanism; no fitted parameters.
- Same targets and date splits for every position and candidate.
- Script validates CSV header, row format, distinct increasing numbers, range, and chronological unique dates.
- Fixed bootstrap seed; output includes data cutoff, split dates, alpha, block size, replicate count and model formula.
- Preserve every per-target score in a detail CSV. Report weak, null, and favorable positions; no selection based solely on discovery.
- Positions are dependent; marginal predictions cannot be naively combined into a five-number ticket.
- Historical extrema are not future bounds. A range-escape is recorded rather than clipped.

## Artifacts
- scripts/sonar_psr01_position_specific_range_walkforward.mjs
- reports/position_specific_range_residual/PSR01_protocol_20261108.md
- CI-generated psr01_walkforward_summary.json and psr01_walkforward_detail.csv under reports/position_specific_range_residual/ (to be persisted after run review).

## Promotion gate
PSR-01 remains research-only. Any candidate needs independent prospective frozen forecasts and the repository's registered prospective minimum (200 complete paired targets preferred/required by Q60), statistical review and human approval. Do not alter active engine or PR #6/#7/#8.
