# VinciCasa SONAR — Q141 cycle 10 (2026-11-12)

**Status:** Q141-B9 completed; strict-prior rank lineage, 7 unit tests, workflow, and exact remote Git readback passed. No factorial effect met the registered confirmatory gate.  
**Branch:** `research/q141-formula-universe-behaviour-mapping-20261112`  
**PR:** #89, open/draft; no merge.

## 1. Recovered state and diagnosis

Recovered the Q141 cycle-9 checkpoint, Q7 typed AST import, B8 complexity report, and the B9 preregistration. B9 was registered before execution and pins:
- Q7 source commit `7a37cab601c5f9386131a00246963f8e4aeabf74`;
- Q7 archive blob `7dab05ba49ace909fe8783eef729605049c65e50`, 3,387 draws through 2026-10-24;
- Q7 rank manifest blob `aae2c7768c9d37bf633a13939f2b686bcce83a27`;
- Q7 runner blob `ad1c7fa721f316b3af0018f5da4a0a905bb62dcf`;
- Q141 archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103`.

The Q7 archive is verified as an exact prefix of Q141. Contest 315 / 2026-11-11 and all 18 later Q141 suffix rows are excluded. Q7's 34 rank parts and all target dates/cutoffs were hash-checked; the pinned runner source confirms target score/write precedes `add_draw(state, draw)`.

The B8 evidence showed that formula complexity alone had no demonstrated association with future quintet rank. B9 therefore decomposed the fixed ten-family grammar rather than adding more complexity variants.

## 2. Q141-B9 quantitative hypothesis and design

Hypothesis: within the fixed 1,023-mask Q7 grammar, ten individual feature families and 45 pairs may show stable marginal or second-order interaction effects on the normalized rank percentile of the realized quintet.

For target (t), each formula mask has percentile (p=1-(rank-1)/(658008-1)).
- Main effect of family (i): average (p(S\cup\{i\})-p(S)) over all 511 non-empty subsets (S) of the other nine families.
- Pair interaction (i,j): average (p(S\cup\{i,j\})-p(S\cup\{i\})-p(S\cup\{j\})+p(S)) over all 255 non-empty subsets (S) of the other eight families.

This gives 10 main effects + 45 pair interactions = 55 preregistered endpoints. The empty background subset is excluded. The estimands are descriptive factorial rank contrasts, not causal effects and not a deployable forecast.

Walk-forward:
- 3,286 targets, indices 101–3386;
- Discovery 1,972; Validation 657; Blind OOS 657;
- all target rank vectors come from the pinned strict-prior Q7 walk-forward;
- target outcomes are used only to evaluate ranks already frozen before that target;
- no parameter fitting or winner selection on Validation or Blind OOS.

Inference:
- two-sided block sign-flip, block length 20, 20,000 replicates;
- 95% circular moving-block bootstrap intervals, 20,000 replicates;
- Holm-Bonferroni across all 55 Blind OOS endpoints;
- flag only if Holm-adjusted p<0.05 and absolute mean effect >=0.005 percentile units.

## 3. Measured results

The average percentile across all 1,023 Q7 formulas was:
- Discovery: 0.500314 (random-quintet reference 0.5);
- Validation: 0.503292;
- Blind OOS: 0.494254.

The mean fraction of formula rankings placing the realized quintet in Top-20 was 0.0002726 in Discovery and zero in both Validation and Blind OOS. This is descriptive only; it was not a registered confirmatory endpoint in B9.

Blind OOS main effects:
- number_frequency: +0.003321; 95% CI [-0.005731, +0.012372]; raw p=0.45293;
- pair_interaction: +0.004119; CI [-0.003182, +0.011067]; raw p=0.27994;
- triple_interaction: +0.001047; CI [-0.005600, +0.007441]; raw p=0.76501;
- quadruple_interaction: +0.003640; CI [-0.004389, +0.011768]; raw p=0.37463;
- exact_quintet_recurrence: -0.000004; CI [-0.000528, +0.000756]; raw p=0.99285;
- sorted_position_frequency: -0.000674; CI [-0.008077, +0.006634]; raw p=0.86121;
- gap_pattern: -0.005039; CI [-0.011563, +0.002181]; raw p=0.18739;
- sum_distribution: -0.002149; CI [-0.008558, +0.004150]; raw p=0.49068;
- odd_count: -0.009463; CI [-0.020553, +0.001631]; raw p=0.12209;
- decade_profile: -0.001873; CI [-0.011635, +0.008046]; raw p=0.68417.

Largest positive pair estimates were:
- sum_distribution × decade_profile: +0.002972; CI [-0.000749, +0.006818]; raw p=0.10699;
- sorted_position_frequency × sum_distribution: +0.002619; CI [-0.002157, +0.007591]; raw p=0.30728;
- sorted_position_frequency × decade_profile: +0.002518; CI [-0.001835, +0.007104]; raw p=0.25579.

The smallest raw p among all 55 endpoints was for triple_interaction × gap_pattern: +0.001225, CI [+0.000306, +0.002086], raw p=0.02230. Its effect is below the +0.005 practical threshold. Because the minimum raw p exceeds 1/55, all 55 Holm-adjusted p-values equal 1.000. No endpoint is flagged.

**Decision:** `NO_REGISTERED_MAIN_OR_PAIRWISE_EFFECT_DEMONSTRATED`.

## 4. Recovery and validation

The first run (43292912400) passed all seven unit tests and completed the calculation, but failed at the final console summary because a relative output path was passed to `Path.relative_to` against an absolute repository root. The report/ledger had been generated locally, but no output persistence or readback was claimed for that failed run.

Corrected all four summary path resolutions to use resolved absolute paths. The rerun [43293021378](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43293021378) completed successfully:
- 7/7 synthetic tests passed, including exact recovery of additive main effects and pairwise difference-in-differences, empty-background counts, sign-flip symmetry/reproducibility, Holm correction, target-row isolation and invalid-rank rejection;
- all 3,286 target rows computed;
- all 34 source rank parts and strict-prior runner order verified;
- artifact uploaded;
- report and target ledger committed;
- exact remote Git readback verified for both outputs by byte length, SHA-256 and Git blob SHA-1;
- five preregistration/code lineage files verified by Git blob SHA-1;
- remote receipt and checkpoint re-read from the branch.

The dedicated workflow is successful. This does not make the historical Blind OOS a virgin prospective test and does not validate the general application CI.

## 5. Persisted evidence

- Report: `q141_q7_factorial_attribution_report_2026-11-12.json`
- Target ledger: `q141_q7_factorial_attribution_target_ledger_2026-11-12.csv` (3,286 rows)
- Manifest: `q141_q7_factorial_attribution_manifest_2026-11-12.json`
- Checkpoint: `q141_q7_factorial_attribution_checkpoint_2026-11-12.json`
- Exact remote readback receipt: `q141_q7_factorial_attribution_remote_readback_2026-11-12.json`

Report Git blob SHA-1: `e5c20a3f1f02d731e9b4a0b19cadd4eda71bae9c`.  
Ledger Git blob SHA-1: `888e0382ff790a9f1508febc12685326c4244204`.  
Remote receipt records 2 output files and 5 preregistration/code lineage entries verified.

## 6. Next action

Do not promote any Q7 family or pair from B9. Stop adding Q7-only interaction variants unless a future independent question is preregistered. Proceed to the cross-granularity behaviour atlas:
1. retain Q7 as `quintet_score` and Q80/Q90 as per-number score types;
2. reconcile archive windows and feature lineage before any joint statistic;
3. map formula coverage, co-occurrence, redundancy, complementarity and transitions as retrospective descriptors;
4. define pre-target family-state signals only after the descriptive atlas is stable;
5. require a fresh prospective freeze for any predictive claim.

Governance unchanged: no merge, no rebase, no engine promotion, no shadow insertion, no canonical archive mutation. PRs #6, #7 and #8 remain untouched.
