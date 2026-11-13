# VinciCasa SONAR — cycle 25

**Date:** 2026-11-13  
**Research branch:** `research/q141-d2-family-volatility-standardization-20261113`  
**Draft PR:** #91, targeting the D1 research branch  
**Decision:** Q141-D2 remains historical exploratory; no selector promotion.

## 1. Recovered state and root-cause findings

- Recovered Q141-D1 and its pinned C0 family ledger.
- D1 source ledger: 3,354 target rows, Git blob `4620ac88199256d90bf8e11a852206bfeb817812`.
- D1 source archive prefix: 3,404 eligible draws through 2026-11-10, blob `fcb453ed06c8002314f826dbac79d6935f9ac103`.
- D1 report blob: `069a4ef826201bdc3e6af58414e7913c44778fa0`.
- D1's stored checkpoint still says `ARTIFACTS_WRITTEN_LOCAL_READBACK_PENDING`, while parent workflow run [43412187676](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43412187676) reports a successful remote-readback step. The report and manifest are retrievable and their Git blob hashes match the manifest. Root cause is stale checkpoint metadata; this cycle did not overwrite the D1 checkpoint.
- The current canonical `main` archive has advanced to 3,406 draws through 2026-11-12. The official archive now publishes contests 315 and 316; D2 intentionally remains pinned to its earlier 3,404-draw source to preserve the preregistered historical experiment.
- Q60 promotion gate currently records 25/200 complete paired prospective targets, with promotion prohibited. The earlier 23/200 status is superseded by the official publication of contest 315 and 316.

## 2. New quantitative hypothesis Q141-D2

D1 standardized each family's outcome by cross-family dispersion on each target, then averaged the standardized values. D2 tests whether removing target-wide difficulty first and then standardizing each family's rolling relative advantage by its own trailing volatility improves family selection.

For family (f), target (s):
[
r_{f,s}=h_{f,s}-rac{1}{6}sum_g h_{g,s}
]

For target (t), using only the prior 100 targets:
[
U_{f,t}=
rac{operatorname{mean}(r_{f,t-100:t})}
{sqrt{operatorname{var}(r_{f,t-100:t})+0.25^2}}
]

Window 100 and floor 0.25 were preregistered before D2 computation. Ties use prior mean actual rank, then family ID.

## 3. Walk-forward results

3,354 targets: Discovery 2,013; Validation 671; historical Blind OOS 670. All six families, M0 equal-family, M1 C0 raw rolling-100, M2 D1 target-standardized, M3 D2 volatility-standardized, and the uniform expectation 0.625 Top-5 hits were compared.

| Split | D2 | D1 | C0 | Equal-family | Uniform |
|---|---:|---:|---:|---:|---:|
| Discovery | 0.651764 | 0.627422 | 0.649776 | 0.634873 | 0.625 |
| Validation | 0.621461 | 0.614009 | 0.612519 | 0.579732 | 0.625 |
| Blind OOS | 0.635821 | 0.619403 | 0.626866 | 0.600000 | 0.625 |

### Blind OOS paired inference

20,000 circular block-bootstrap replicates and 20,000 block sign-flips per endpoint, block length 20; Holm correction across three co-primary endpoints.

| Contrast | Mean gain | 95% block CI | Raw p | Holm p |
|---|---:|---:|---:|---:|
| D2 − D1 | +0.016418 | [-0.004478; +0.040299] | 0.12704 | 0.37018 |
| D2 − C0 | +0.008955 | [-0.002985; +0.022388] | 0.13944 | 0.37018 |
| D2 − Equal | +0.035821 | [-0.026866; +0.097015] | 0.12339 | 0.37018 |

The practical threshold is +0.025 hits/target. D2−Equal clears the point-estimate threshold, but its interval includes zero; none of the three comparisons passes the joint decision gate. No lift is demonstrated.

## 4. Leakage, bias and reproducibility

- The D2 selector reads only target rows ([t-100,t)).
- The source ledger is chronological, split counts are exact, and each recorded cutoff precedes its target date.
- Six future-suffix mutation checks leave the earlier selection unchanged.
- D1 replay matches the pinned D1 Blind OOS mean exactly: 0.6194029850746269.
- Local tests: 10/10 passed.
- Two complete local replays produced byte-identical report and ledger.
- The local full replay used `--skip-archive-check` because the canonical archive bytes were not materialized in the local runtime. The ledger, parent report and D1 report are pinned; the parent D1 CI run passed its archive audit. The D2 GitHub Actions workflow is committed in the D2 head branch, but no D2-specific Actions run is claimed in this cycle.
- Historical Blind OOS is already exposed to prior SONAR research; it is not virgin prospective confirmation. Holm covers D2's three endpoints only, not the full Q00-Q141 research family.

## 5. Persisted artifacts

- Preregistration: `q141_d2_family_volatility_standardization_preregistration_2026-11-13.md`
- Executable runner: `scripts/sonar_q141_d2_family_volatility_standardization.py`
- Tests: `tests/test_sonar_q141_d2_family_volatility_standardization.py`
- Report: `q141_d2_family_volatility_standardization_report_2026-11-13.json`
- 3,354-target ledger: `q141_d2_family_volatility_standardization_target_ledger_2026-11-13.csv`
- Manifest/checkpoint and remote readback receipt are saved beside the report.
- Current source/Q60 audit: `q141_current_source_and_q60_status_audit_2026-11-13.md`

The report, ledger, manifest, checkpoint, runner, tests and preregistration were fetched back from GitHub and their blob hashes recorded in the remote-readback receipt.

## 6. Governance and next action

- PR #91 remains draft, targeting the D1 research branch; no merge or rebase.
- PRs #6, #7 and #8 are untouched; #89 and #90 are untouched.
- No canonical archive, Q60 freeze, B11 freeze, shadow forecast or active engine was modified.
- No engine was promoted.

**Next iteration:** complete the common-source typed formula atlas. Reconcile Q80's 25 canonical features, Q90's typed AST registry, Q7's quintet AST registry and Q141's 59-feature matrix on a single immutable 3,406-draw snapshot; preserve the different output semantics (number-level versus quintet-level). Verify all AST shard hashes and semantic equivalence, then measure coverage, redundancy, complementarity and pre-target family/regime changes. Do not select formulas by historical Blind OOS performance. Keep Q60 at 25/200 and continue its append-only prospective protocol.
