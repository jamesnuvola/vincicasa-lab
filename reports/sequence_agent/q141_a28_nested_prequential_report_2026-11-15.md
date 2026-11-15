# Q141-A28 — Nested prequential formula-panel selector

**Decision: `NO_PREQUENTIAL_SELECTOR_LIFT_DEMONSTRATED`.** Exploratory historical replay; not a production or prospective claim.

## Sources and exact scope

- Q90 formula artifact: run `42504717670`, artifact `13627507532`, SHA-256 `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`.
- Q141-A7 feature matrix: run `43348144964`, artifact `14003350043`, SHA-256 `9c54699a507e876b7b5b1c0c9e3120ad04c2bcc741dcd5043dc410f81bf6b03a`.
- Feature matrix: 3,356 targets through **2026-11-12**, 40 candidates × 59 prior-only features; archive blob `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`.
- Q90 grammar: **330,429** formulas over 20 Discovery-selected features from the 59-feature matrix; 700 formulas (0.212%) received full per-target ranks in this experiment.
- The first 3,351 matrix rows, target dates, cutoffs and actual quintets match the pinned Q90 source bit-for-bit.

## Candidate panel and selector

- Panel A: 350 deterministic hash-sampled formulas, 50 from each of L4/L5/L6/L7/L8/I4/G4.
- Panel B: 350 Discovery-top formulas, 50 per group, selected by Discovery Top-5 share, then mean rank and formula ID. No overlap with A.
- Eight fixed prequential policies were compared on Discovery after 100 warm-up target rows. The selected policy was **`EXPANDING_RANK`**.
- At each target, `EXPANDING_RANK` selects the formula with the lowest mean rank of the five winning numbers across all earlier targets; ties use prior Top-5 hits and formula ID. The policy was frozen before Validation and Blind OOS.

## Results

| Split | Dynamic A+B Top5 | Static Discovery-best Top5 | Dynamic A+B Top10 | Static Top10 | Dynamic A+B Top20 | Static Top20 | Dynamic mean rank | Static mean rank |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| validation | 11.254% | 12.866% | 23.672% | 23.970% | 48.567% | 49.522% | 20.779 | 20.554 |
| blind_oos | 12.652% | 12.237% | 25.007% | 24.711% | 50.222% | 50.489% | 20.538 | 20.529 |

### Paired inference: dynamic A+B versus static Discovery-best

20,000 circular moving-block bootstrap replicates and 20,000 non-overlapping 20-target block sign-flips; Holm correction across eight endpoints.

| Split | Endpoint | Difference favouring dynamic | 95% block CI | Raw p | Holm p (8 tests) |
|---|---|---:|---:|---:|---:|
| validation | Top5 share | -0.016119 | [-0.025672, -0.006567] | 0.00105 | 0.00840 |
| validation | Top10 share | -0.002985 | [-0.013433, +0.007164] | 0.57217 | 1.00000 |
| validation | Top20 share | -0.009552 | [-0.021493, +0.002687] | 0.16399 | 0.98395 |
| validation | Mean-rank improvement | -0.224478 | [-0.391940, -0.064478] | 0.02875 | 0.20124 |
| blind_oos | Top5 share | +0.004148 | [-0.003556, +0.012148] | 0.28364 | 1.00000 |
| blind_oos | Top10 share | +0.002963 | [-0.008296, +0.014519] | 0.64412 | 1.00000 |
| blind_oos | Top20 share | -0.002667 | [-0.015704, +0.010370] | 0.70646 | 1.00000 |
| blind_oos | Mean-rank improvement | -0.009481 | [-0.201481, +0.186674] | 0.93230 | 1.00000 |

## Interpretation

- In Validation the adaptive selector is materially worse than the fixed Discovery-best formula on Top5: **−1.612 percentage points**, block CI [−2.567, −0.657] pp, Holm p=0.00840. Its mean rank is also worse by 0.224 positions (raw p=0.02875; Holm p=0.20124).
- In historical Blind OOS the Top5 difference is +0.415 pp, but its 95% block interval crosses zero and Holm p=1.0. Top10/Top20 and mean-rank differences are also inconclusive.
- The selected formulas move among three related variants. They share four features: `lag_2`, `lag_10`, `neighbor_balance_pm2_recent`, `regime_sum_affinity`. The two linear variants also share `neighbor_pm2_history`, `rank_consensus_27`, and `transition_profile_affinity`; the gate variant thresholds `neighbor_balance_pm2_recent` at 1.0.
- This recurring motif is a descriptive clue for the next experiment, not evidence of a predictive regime. The fixed expanding-memory selector is too weak to promote.

## Limitations and next work

- This is a 700-formula panel, not the full 330,429 per-target rank cube; the remaining 329,729 formulas have only aggregate split metrics here.
- The Q90 grammar uses 20 features selected from 59 in Discovery; it is not exhaustive over all 59 features or all mathematical formulas.
- The matrix ends 2026-11-12; canonical `main` is through 2026-11-14. The Nov13–14 targets still need the 59-feature matrix refresh.
- Historical Blind OOS has been exposed to earlier SONAR work and is not virgin prospective evidence.
- Next: test a state-conditioned memory/transition selector around the shared four-feature motif, then expand the per-target rank panel to 3,500 and 10,000 formulas with the same deterministic replay and chronological controls.

## Acceptance

- Local replay and source-artifact hash checks: PASS.
- Per-target validation and blind ledgers: generated locally; their local evidence-bundle hashes are in the persistence manifest.
- Report, validation, checkpoint and evidence-manifest: committed and read back on the Q141-A27 research branch.
- Candidate panel and per-target ledgers: generated in the downloadable evidence bundle; repository persistence is PENDING.
- Reproducible analysis code, exact-head CI and human review: PENDING.
- No engine promotion, no shadow insertion, no freeze mutation, no merge.
