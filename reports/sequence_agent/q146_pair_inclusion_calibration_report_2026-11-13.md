# Q146 — Pair-inclusion calibration audit

**Decision:** pairwise calibration not established; Q145 remains frozen and unchanged.

## Method
- Pair probability: P(i,j included)=w_i*w_j*e3(w excluding i,j)/e5(w).
- Q145 rank weights unchanged: u(r)=(21-r)/20 for Top20, zero outside; w=exp(u), T=1.
- Uniform pair baseline: 10/C(40,2)=1/78.
- Primary endpoint: target-level mean pairwise Brier gain. Secondary: pairwise Bernoulli composite log-score gain; not a joint subset likelihood.
- The 780 pair events within a target are dependent; inference resamples target-level aggregates only.

## Walk-forward results
| Split | Model | n | Pair Brier gain | Pair composite log gain | Pair mass |
|---|---|---:|---:|---:|---:|
| discovery | borda | 18 | -0.00004203 | -0.00117617 | 10.00000000 |
| discovery | inclusion | 18 | -0.00002338 | -0.00056066 | 10.00000000 |
| discovery | app | 6 | 0.00005534 | 0.00177436 | 10.00000000 |
| validation | borda | 6 | -0.00006857 | -0.00213308 | 10.00000000 |
| validation | inclusion | 6 | -0.00005546 | -0.00157392 | 10.00000000 |
| validation | app | 6 | -0.00004489 | -0.00126393 | 10.00000000 |
| blind_oos | borda | 7 | -0.00002175 | -0.00049495 | 10.00000000 |
| blind_oos | inclusion | 7 | -0.00000430 | 0.00016672 | 10.00000000 |
| blind_oos | app | 7 | -0.00003974 | -0.00131733 | 10.00000000 |

## Historical Blind OOS inference (7 targets)
| Endpoint | Raw p | Holm p | 95% block-bootstrap CI |
|---|---:|---:|---:|
| borda_vs_uniform | 0.50000000 | 1.00000000 | [-0.00007339, 0.00002373] |
| inclusion_vs_uniform | 0.95312500 | 1.00000000 | [-0.00006119, 0.00004640] |
| app_vs_uniform | 0.28125000 | 1.00000000 | [-0.00010483, 0.00001338] |
| borda_vs_inclusion | 0.28125000 | 1.00000000 | [-0.00003335, -0.00000502] |
| borda_vs_app | 0.39062500 | 1.00000000 | [-0.00000590, 0.00003934] |

Historical results are exploratory, not virgin confirmation: Q145's PMF transformation was specified after Q144 outcomes had been inspected. The blind segment contains only seven targets. Sign-flip inference assumes symmetry/exchangeability; Holm covers the five registered Q146 endpoints, not all SONAR experiments.

## Integrity
- 3,406 canonical archive rows; 1,364 shadow rows checked for strict-prior cutoffs and pre-draw timestamps; 43 pending 2026-11-13 rows remain outcome-free.
- 31 Q144 target rows reconciled with the canonical archive; all Top20 hit counts recomputed.
- Every model/target pair inclusion mass sums to 10 within 1e-10; every observed 5-number draw has exactly 10 unordered pairs.
- Q145 upstream source hashes and completed checkpoint verified before Q146 scoring.

## Limits and next action
- Pairwise Brier and composite log score evaluate marginal pair inclusion, not the full dependence structure of a 5-number subset.
- No historical predictive lift or calibrated probability claim is made. No engine promotion.
- Preserve the Q145 2026-11-13 freeze. Reconcile only after official publication and accumulate at least 100 consecutive prospective targets without retuning.
