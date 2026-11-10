# SONAR FD-10 — post-run checkpoint (2026-11-10)

## Registration and scope
- Experiment: `SONAR-FD10-P5-CONTINUOUS-MARKOV-KERNEL-2026-11-10`.
- Protocol was committed before evaluating the archive.
- Hypothesis: a fixed Gaussian kernel over historical one-step transitions `P5[j-1] -> P5[j]`, conditioned on the immediately previous maximum `P5[t-1]`, can improve the next P5 probability ranking over the exact order-statistic null.
- Fixed bandwidths: 1.5, 3, 6, 12; fixed Dirichlet shrinkage ESS 200.
- Exact null: `p0(n)=C(n-1,4)/C(40,5)`, n=5..40.
- Model selection: minimum Validation multiclass Brier; ties go to the larger bandwidth.
- Primary Blind OOS endpoint: paired Brier improvement (exact null minus model). Secondary: paired Top-5 hit indicator improvement.
- Inference: block sign-flip, block length 7, 50,000 replicates; circular block bootstrap, block length 7, 10,000 replicates; one Holm family across 8 fixed bandwidth/endpoint tests.

## Source and walk-forward
- Canonical source: `data/storico_daily.csv`.
- Git blob SHA: `8d3e19f0b417024ba32e576697eac0648d12ab86`.
- 3,403 draws, 2017-07-17 through 2026-11-09.
- 3,103 targets after a 300-draw warm-up.
- Chronological splits: Discovery 1,400 (index 300–1699); Validation 850 (1700–2549); historical Blind OOS 853 (2550–3402).
- The target was scored before its own transition was added to the state. The only state input was the previous P5; all historical transitions ended strictly before the target.
- No missing forecast was reconstructed and no production engine or freeze was modified.

## Measured result
Validation selected bandwidth **h=1.5**, but it did not beat the exact null even on Validation:
- Validation Brier: model 0.9245638184 vs exact null 0.9244720200.
- Validation Top-5: model 50.8235% vs exact null 51.0588%.

Blind OOS (n=853):
- Exact null: Top-5 447/853 = 52.4033%; Top-10 655/853 = 76.7878%; Top-20 827/853 = 96.9519%; Brier 0.9275551633; log loss 2.8654807033.
- Selected h=1.5: Top-5 445/853 = 52.1688%; Top-10 652/853 = 76.4361%; Top-20 824/853 = 96.6002%; Brier 0.9278270908; log loss 2.8777501640.
- Brier improvement (null minus model): **-0.0002719275**; 95% circular block-bootstrap CI **[-0.0011178095, +0.0005703490]**.
- Top-5 hit-rate difference: **-0.2345 percentage points**; 95% block-bootstrap CI **[-0.9379, +0.3517] percentage points**.
- Selected Brier and Top-5 Holm-adjusted p-values: **1.000**. All 8 fixed-family Holm-adjusted p-values are 1.000.
- Decision: **NO_PREDICTIVE_LIFT_DEMONSTRATED**.

The other bandwidths also failed to beat the exact null on Blind OOS Brier. h=3, 6 and 12 had the same Top-5 hit rate as the exact null; none generated a corrected signal.

## Root-cause diagnosis
- The continuous kernel did not uncover stable one-step dependence of P5 on the previous P5.
- The narrow h=1.5 validation winner was the least-bad validation Brier in the fixed grid, not a model that beat the analytical null; its OOS Brier and Top-5 were worse.
- This is consistent with the earlier FD-05 coarse-bin Markov P5 null result. The experiment therefore does not justify expanding the bandwidth grid or adding more P5 state features against this already-exposed historical period.
- The exact order-statistic null remains the correct baseline; uniform 1/40 rank assumptions are inappropriate for P5.

## Persistence and current validation state
- Protocol, Python implementation, regression tests, readback validator, isolated workflow, JSON report and full target ledger are committed on `research/fd10-p5-continuous-kernel-20261110`.
- Report blob SHA: `d84f4617f8eccf858614240f98f7e4927eabace9`.
- Target-ledger blob SHA: `7b7d0a3d46eb5094397a377b0b1a79139c64643a`; read back through Git blob API as 1,074,564 characters, 3,104 lines (header + 3,103 targets), 41 columns.
- Code blob SHA: `553dbcb5b18cfeccaadcc022c0f07e1a0210467d`.
- Protocol blob SHA: `5d315321f69cc5e3493ace98d61df49414c57229`.
- GitHub readback confirmed all paths and blob identifiers.
- Initial dedicated workflow run 42839132477 failed in the full replay because the bootstrap still referenced `random.Random` after the PRNG was replaced; the nine unit tests had passed. Replaced the remaining RNG call with the registered XorShift32 generator and added a deterministic-bootstrap regression test.
- The next replay (run 42839311224) completed the full walk-forward but failed the independent readback because Python serialized bandwidth keys as `3.0/6.0/12.0` while the V8-generated report used `3/6/12`. Normalized the Python report keys to `{h:g}`; the registered hypothesis, data, parameters and scored results were unchanged.
- Exact-head dedicated workflow run **42839425666: SUCCESS** on commit `96569fd76495734f860c4eb5baabd7d69663569b`. Verified: compilation, **10/10 regression tests**, full 3,103-target replay with 50,000 block-sign flips and 10,000 bootstraps, and report/ledger readback validator (`FD10_PERSISTED_REPORT_LEDGER_REPLAY_PASS`).
- General repository CI run 42839426185 was still in progress at the last check; do not claim it passed until its conclusion is read.

## Guardrails and next action
- Historical Blind OOS is already exposed to prior SONAR work; this remains exploratory, not prospective confirmation.
- The block sign-flip assumes exchangeable seven-target block signs; strong nonstationarity can invalidate it.
- No merge, no model promotion, no new prospective freeze, and no change to PR #6, #7 or #8.
- Next: complete the dedicated CI replay, recover any failure from this checkpoint without changing the registered hypothesis, then stop retrospective P5 kernel tuning. Keep effort on the separate prospective Q60/H101 cohort and wait for official canonical outcomes before append-only scoring.
