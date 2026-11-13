# Q145 — Rank-to-subset likelihood calibration

**Decision:** no historical predictive lift demonstrated; prospective freeze pending.

## Method
- Fixed utility: u(r)=(21-r)/20 for ranks 1..20; zero outside Top20; temperature T=1.
- Exact unordered 5-of-40 PMF: P(S)=product(w_i)/e5(w), w_i=exp(u_i).
- Primary endpoint: complete-quintet log-likelihood gain versus uniform. Secondary: marginal-inclusion Brier gain versus 0.125.

## Walk-forward results
| Split | Model | n | Mean log-gain | Mean Brier gain |
|---|---|---:|---:|---:|
| discovery | borda | 18 | -0.249365 | -0.001626 |
| discovery | inclusion | 18 | -0.118809 | -0.000785 |
| discovery | app | 6 | 0.372857 | 0.002224 |
| validation | borda | 6 | -0.452143 | -0.002904 |
| validation | inclusion | 6 | -0.335476 | -0.002269 |
| validation | app | 6 | -0.268809 | -0.001796 |
| blind_oos | borda | 7 | -0.105714 | -0.000744 |
| blind_oos | inclusion | 7 | 0.030000 | -0.000102 |
| blind_oos | app | 7 | -0.277143 | -0.001676 |

## Historical Blind OOS diagnostics (7 dates)
| Diagnostic | Raw p | Holm p |
|---|---:|---:|
| borda_vs_uniform_eprocess | 0.807117 | 1.000000 |
| inclusion_vs_uniform_eprocess | 0.354466 | 1.000000 |
| app_vs_uniform_eprocess | 1.000000 | 1.000000 |
| borda_vs_inclusion_signflip | 0.890625 | 1.000000 |
| borda_vs_app_signflip | 0.203125 | 1.000000 |

All historical inference is exploratory, not virgin confirmation: this PMF transformation was specified after Q144 historical outcomes had been inspected. Sign-flip tests assume symmetry/exchangeability. Holm covers only the five registered Q145 diagnostics, not all SONAR research.

## Prospective 2026-11-13 freeze
- Borda modal quintet: **1 · 7 · 25 · 16 · 21**
- Equal-type inclusion modal quintet: **1 · 25 · 21 · 16 · 9**
- Cutoff 2026-11-12; frozen 2026-11-13 at 19:18:07 Europe/Rome; outcome null.
- The 2026-11-12 repository row has an unresolved discrepancy between official archive pages; the cutoff is preserved but not independently source-confirmed.

## Integrity and limits
- 31 historical target rows reconciled against the pinned canonical archive.
- 1,364 shadow rows checked for strict-prior cutoffs and pre-draw timestamps; 43 pending rows remain outcome-free.
- 42 component forecasts per completed target (24 family / 12 pair / 6 chain); APP is an external comparator.
- The PMF is normalized over all 658,008 quintets; this does not establish calibration or predictive power.
- Seven historical Blind OOS dates are insufficient for confirmation. No model promotion.

## Next action
Keep both probability forecasts frozen and append-only. Reconcile only after official publication. Accumulate at least 100 consecutive prospective targets without retuning.
