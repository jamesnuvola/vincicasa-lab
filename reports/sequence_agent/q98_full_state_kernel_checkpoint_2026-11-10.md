# Q98 — post-run checkpoint (2026-11-10)

## Status
**HISTORICAL_EXPLORATORY_COMPLETE / NO_PREDICTIVE_LIFT_DEMONSTRATED.** Research-only. No production change, merge, or promotion.

## Preregistered hypothesis
A Gaussian kernel over the complete preceding five-number sorted draw geometry, after standardizing each position by its exact 5-of-40 order-statistic mean and standard deviation, might improve next-draw position marginals over the exact order-statistic prior.

- Protocol path: `reports/sequence_agent/q98_full_state_kernel_protocol_2026-11-10.json`
- Protocol commit: `300250c73d6bb822965d450b04e590392e5a4b37`
- Protocol Git blob: `883226aeb8d54dedf8f015d72c2d06e12cae349c`
- Canonical archive: 3,403 draws, 2017-07-17 through 2026-11-09; Git blob `8d3e19f0b417024ba32e576697eac0648d12ab86`
- Fixed bandwidth grid: 0.5, 0.75, 1.0, 1.5; fixed prior strength 200.
- P5-only diagnostic comparator: standardized P5 kernel, fixed h=1.5.
- Walk-forward: 3,103 targets; Discovery 1,400 / Validation 850 / historical Blind OOS 853.

## Measured result
Validation selected h=1.5 by the preregistered mean five-position multiclass Brier criterion. It did not beat the exact prior.

- Discovery h=1.5 Brier gain vs exact prior: **-0.000626617**.
- Validation h=1.5 Brier gain: **-0.000322443**.
- Blind OOS h=1.5 Brier gain: **-0.000228962**.
- Blind OOS h=1.5 Brier-gain 95% circular block-bootstrap CI: **[-0.000430627, -0.000037101]**; block sign-flip p=0.987420251594968; Holm p=1.
- Blind OOS Top-5 positional hit gain vs exact-prior ranking: **-0.022274326 hits/target**; 95% CI [-0.060961313, 0.017584994]; raw p=0.867102657946841; Holm p=1.
- All 8 preregistered bandwidth × endpoint tests have Holm-adjusted p=1.0.
- Full-state vs fixed P5-only P5 Brier diagnostic: 0.00003577; descriptive only, not inferential.

## Integrity and recovery
- 3,103/3,103 strict-prior cutoffs checked; every historical transition outcome index is less than the target index.
- 3,103 ledger rows, 22 columns; each target date, prior cutoff, previous draw and split was independently reconciled to the canonical archive with zero mismatches.
- 65,163 probability normalization checks; maximum sum error 0.
- Five synthetic tests passed: exact-prior normalization, strict-prior boundary, target/future mutation invariance, probability normalization, deterministic prediction replay.
- Deterministic report and ledger replay from the persisted runner core matched the persisted Git files byte-for-byte.
- First execution attempt stopped before scoring because the runner expected split key `blind_oos` while the preregistered protocol used `blind_oos_historical`. The runner was corrected to honor the frozen protocol key, then the complete 3,103-target run was repeated. No hypothesis, split, parameter, source data or result was changed.
- GitHub Actions exact-head CI and independent validator are **pending** a pull-request-triggered run; do not describe them as passed until observed.

## Decision / next action
Stop retrospective tuning of this full-state kernel. It underperformed the exact prior in Discovery, Validation and historical Blind OOS. Continue Q60 append-only prospective collection; do not reconstruct missing freezes. Any future model trial requires a separate pre-target freeze and human review.

Historical Blind OOS is already exposed to prior SONAR research and is not a virgin prospective holdout. Marginal position forecasts do not form a coherent joint quintet distribution. Block sign-flip inference assumes exchangeability of contiguous 20-target block signs.
