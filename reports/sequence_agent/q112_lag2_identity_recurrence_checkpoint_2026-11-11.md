# Q112 — lag-2 identity rebound checkpoint (2026-11-11)

- Source main commit: 161273b72804c2b6e815e41f20b90dabfea4fdfa.
- Canonical archive: 3,404 draws through 2026-11-10; blob SHA-1 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Protocol status: exploratory; initial scoring preceded protocol persistence.
- Walk-forward: 3,103 targets; Discovery/Validation/historical Blind OOS = 1,861/620/622; first target index 301.
- State: lag-1 overlap x1 and lag-2-only identity rebound x2; exact partition over all 658,008 subsets.
- Validation selected beta1=0, beta2=0 (uniform); every nonzero candidate had negative Validation mean log gain.
- Blind OOS: selected model is uniform; all 14 nonzero candidates had negative mean log gain; Holm-adjusted p-values all 1.000.
- Validation checks: 16/16 passed; future-mutation invariance 9/9; deterministic replay passed.
- Historical Blind OOS is not virgin; no confirmatory claim or model promotion.
- No production scorer, Q60 gate, shadow freezes, H101/H102 or PRs #6/#7/#8 changed.
- Next: prioritize Q60 registry refresh and the next pre-draw freeze.
