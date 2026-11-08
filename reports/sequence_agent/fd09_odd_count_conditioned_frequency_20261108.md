# VinciCasa SONAR — FD-09 odd-count-conditioned frequency

**Run date:** 2026-11-08 · **Archive cutoff:** 2026-11-07 · **Status:** EXPLORATORY / NO LIFT CONFIRMED / NO PROMOTION  
**Branch:** `research/fd09-odd-count-conditioned-frequency-20261108`  
**Preregistration:** `reports/sequence_agent/fd09_odd_count_conditioned_frequency_preregister_20261108.md`

## Hypothesis and quantitative formula

The odd-number count of the preceding draw, grouped into fixed bins 0–1, 2–3, and 4–5, may condition the next draw's per-number inclusion frequencies. This differs from FD-08 sum-state conditioning and FD-07 individual lag-1 recurrence.

For target t and candidate n:

`S(n,t,alpha) = [C(n | state(t-1)) + alpha * F(n,t)] / [E(state(t-1)) + alpha]`

C and E use only historical target rows j<t, where state for row j is derived from draw j-1. F is the unconditional strict-prior per-draw frequency. Candidate ties are resolved by ascending number. Alpha grid: {0,25,50,100,200,500,1000}, 21 models.

## Walk-forward protocol and measured results

Archive audit: 3,401 draws (2017-07-17 through 2026-11-07), CSV 3,402 lines including header, dates strictly increasing, five distinct integers 1..40 per draw; source blob SHA `5d2efd70684e918b27d8f06386d545647898336d`.

Targets are scored before target outcomes are added. Fixed index splits: discovery 1,400 (300–1699), validation 850 (1700–2549), blind OOS 851 (2550–3400). Model selection uses validation Top5 hit count only; tie-break lower Brier, then higher alpha. Selected: **ODD3_A100 (alpha=100)**.

| Segment | Targets | FD-09 Top5 hits / hit-share | Unconditional frequency Top5 hits / hit-share | Delta hits |
|---|---:|---:|---:|---:|
| Discovery | 1400 | 860 / 12.2857% | 870 / 12.4286% | -10 |
| Validation | 850 | 554 / 13.0353% | 517 / 12.1647% | 37 |
| Blind OOS | 851 | 514 / 12.0799% | 493 / 11.5864% | 21 |

Blind selected model is +0.4935 percentage points versus unconditional frequency, but remains below the uniform Top5 reference 12.50% (531.875 expected hits; observed 514). This is descriptive only.

## Secondary blind diagnostics

| Metric | FD-09 selected | Unconditional frequency | Uniform reference |
|---|---:|---:|---:|
| Top10 coverage of the five actual numbers | 24.9119% (1060 hits) | 24.3478% (1036) | 25.00% |
| Top20 coverage of the five actual numbers | 50.0118% (2128 hits) | 50.3643% (2143) | 50.00% |
| Mean rank of actual numbers (lower is better) | 20.4496 | 20.4982 | 20.50 |
| Brier (lower is better) | 0.10944323 | 0.10939761 | — |
| Log loss (lower is better) | 0.37707538 | 0.37686935 | — |

FD-09 Brier delta model minus baseline = 0.00004562 (worse); log-loss delta = 0.00020603 (worse).

## Statistical controls

- Exact one-sided uniform Top5 null: aggregate overlap distribution from 851 convolutions of Hypergeometric(40,5,5).
- Selected model exact raw p = **0.81546552**; Holm-adjusted p across 21 conditional models + unconditional-frequency reference (22) = **1.000000**.
- Paired non-overlapping 7-target block sign-flip (121 complete blocks, 4 tail targets omitted; 20,000 deterministic replicates): raw p = **0.40822959**; Holm-adjusted across 22 paired comparisons = **1.000000**.
- Circular moving-block bootstrap, block length 7, 10,000 deterministic replicates: 95% CI for paired Top5 hit-share delta = **[-0.6110, 1.5981] pp**, including zero.
- Best raw blind configuration (post-hoc descriptive, not selected): ODD3_A25, 518 hits (12.1739%), raw exact p=0.75833373, Holm p=1.000000. No model survives correction.

Correction scope is the preregistered FD-09 family only. The same historical blind period was examined by earlier SONAR hypotheses, so this is not independent prospective evidence; no global correction across the full evolving hypothesis history is claimed.

## Leakage, bias and reproducibility

- Strict-prior invariant: each target t uses unconditional counts from draws 0..t-1 and conditional training rows j=1..t-1 with state from draw j-1; target t enters only after its forecasts are frozen.
- Fixed index splits and state bins; no blind-driven selection. The 21-alpha grid is corrected with Holm.
- Two independent CodeMode executions produced byte-identical JSON and target ledger.
- Metric audit: Top10/Top20 coverage is defined as actual numbers captured divided by 5×targets (not k×targets); a preliminary diagnostic denominator was corrected before persisting any result.
- Native Node execution: **not run**. GitHub Actions CI: **not run**. These are not counted as passed.
- Repository readback verification is required for every persisted artifact. No PR, merge, engine promotion, or changes to PR #6/#7/#8. Q60 remains a separate prospective gate.

## Decision and next action

**FD-09 is NULL / no predictive lift confirmed.** The validation-selected model gives +21 blind Top5 hits versus frequency, but exact-uniform and paired block tests are non-significant after correction, bootstrap CI includes zero, and Brier/log-loss slightly worsen. Keep the official engine unchanged. Freeze FD-09; do not retune on this blind segment. Continue append-only Q60 prospective forecasts and only register a fresh hypothesis with a new primary endpoint before examining outcomes.
