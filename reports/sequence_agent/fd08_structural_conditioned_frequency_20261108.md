# VinciCasa SONAR — FD-08 Structural-Conditioned Frequency
**Data cutoff:** 2026-11-07 · **Run date:** 2026-11-08 · **Status:** EXPLORATORY_NULL_NO_PROMOTION

## Hypothesis
The previous draw's sum, categorized into a fixed 2- or 4-state quantile partition estimated from the first 200 historical draws, may condition next-draw per-number inclusion frequencies. Conditional counts are shrunk toward the unconditional all-prior frequency with pseudo-draw strength alpha.

## Archive and strict-prior validation
- Canonical archive: `data/storico_daily.csv`, 3,401 draws (2017-07-17 through 2026-11-07).
- Git blob SHA from repository: `5d2efd70684e918b27d8f06386d545647898336d`.
- Structural validation: 3,402 CSV lines including header; unique increasing dates; each row has five distinct integers in 1..40.
- Scored targets: 3,101, starting at index 300. Discovery 1,400 (300–1699), validation 850 (1700–2549), blind OOS 851 (2550–3400).
- Cutpoints frozen from initial 200 draw sums: K=2 `105`; K=4 `85,105,122`.
- For each target t, the score is computed before adding draw t to the running counts. All conditional training rows j satisfy j<t and their state is bin(sum(draw[j-1])). No target/future outcomes enter its score.
- The persisted JS core was re-parsed and executed in CodeMode against the retrieved archive. Report output and target ledger were byte-identical to the persisted results. Native Node execution and GitHub CI were not run in this cycle.

## Formula
`score(n,t) = (count(n | state_{t-1}) + alpha * freq_prior(n,t)) / (state_exposure(state_{t-1}) + alpha)`
Grid: state count K in {2,4}; alpha in {0,50,200,500,1000}; 10 configurations. Validation selects maximum Top5 hit-share, tie-break lower Brier, larger alpha, then smaller K. Selection: **K4_A0**.

## Discovery / validation / blind OOS
| Segmento | Target | Top5 baseline freq. | Top5 FD-08 selezionato | Top10 FD-08 | Top20 FD-08 | Rank medio FD-08 | Brier FD-08 | Log loss FD-08 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| discovery | 1400 | 12.4286% (870) | 12.5000% (875) | 25.1571% | 50.6000% | 20.3203 | 0.110839 | 0.384056 |
| validation | 850 | 12.1647% (517) | 13.8588% (589) | 25.6235% | 50.4235% | 20.3240 | 0.111166 | 0.386238 |
| blind_oos | 851 | 11.5864% (493) | 12.6439% (538) | 25.2644% | 49.4242% | 20.5694 | 0.111640 | 0.388697 |

Uniform per-number Top5 hit-share reference = 12.50%; Top10 = 25.00%; Top20 = 50.00%; mean rank = 20.5.

## Statistical controls
- Blind selected FD-08: 538 Top5 hits / 851 targets (12.6439%), expected under uniform 531.875 hits; exact one-sided hypergeometric-convolution p = 0.38986, Holm across 10 configurations = 1.00000.
- Selected vs unconditional frequency baseline: 45 net hits (1.0576 percentage points); 7-target block sign-flip p=0.10079, Holm across 10 paired configurations=0.90715.
- Circular 7-target block bootstrap (10,000 replicates) 95% CI for selected paired hit-share delta: [-0.1880, 2.2797] percentage points; includes zero.
- Selected Brier delta vs unconditional frequency = 0.002243 (worse); log-loss delta = 0.011828 (worse).
- Best blind Top5 config, **K4_A1000**, is retrospective descriptive only: 543 hits (12.7615%), raw p=0.30034, Holm=1.00000. It is not used for model selection.
- All 10 exact-uniform p-values have Holm-adjusted value 1.00000. The smallest raw p in this family is 0.30034. The smallest paired Holm p across configs is 0.68897.
- These corrections cover FD-08's registered grid only, not all prior SONAR hypothesis selection. OOS is retrospective, not independent prospective evidence.

## Decision and diagnosis
The four-state conditional frequency model selected by validation has a small Top5 uplift over the unconditional frequency baseline, but it does not reject the uniform-random Top5 null; paired tests and bootstrap include zero after the declared correction family. Its Brier and log-loss are worse than the unconditional baseline, and Top20/rank are not improved. The validation uplift does not establish predictive utility. **FD-08 remains exploratory; no engine promotion.**

## Persistence and gates
- Target ledger: `reports/sequence_agent/fd08_structural_conditioned_target_ledger_20261108.csv` — 3101 strict-prior target rows, all splits, actual quintets, cutoffs, selected/baseline Top5 and all 10 model hit counts.
- Results JSON: `reports/sequence_agent/fd08_structural_conditioned_frequency_20261108.json`.
- Reproducible script: `scripts/sonar_fd08_structural_conditioned_frequency.mjs`.
- Exact GitHub readback verified for ledger, script, and JSON. Blob SHAs: ledger `548b8207f9e5b6b66af958e3700d642aa02568ee`; script `0223b002109580c4c945d45cf5854805c77e421e`; JSON `578e25feb39d377e84f3d6248b953697bc86acc7`.
- Branch: `research/fd08-structural-conditioned-frequency-20261108`. No PR created, no merge, no change to PR #6/#7/#8, no engine promotion. Q60 prospective gate not incremented.

## Next action
Freeze FD-08 parameters. Do not retune on this blind OOS. If prospectively used, append forecasts/results to a new immutable ledger and evaluate only after the outcome is officially verified. Await native Node/CI validation and human review before any integration.
