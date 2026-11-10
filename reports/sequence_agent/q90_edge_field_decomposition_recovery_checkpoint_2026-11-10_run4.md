# Q90 Edge-Field Decomposition — recovery checkpoint 4

Date: 2026-11-10

## Third execution attempt

- Workflow run: 42745376319.
- Regression tests: 11/11 PASS.
- Strict-prior walk-forward: completed for 3,203 targets.
- Independent validator: PASS; all replay counts and manifest hashes matched.
- Artifact upload: PASS; bundle ID 13730508847, 9,634,412 bytes.
- Repository persistence: failed before creating a commit.

## Root cause

The persistence script read the reserved GitHub Actions variable GITHUB_REF_NAME. On pull_request events that value is 31/merge; a workflow-level env assignment cannot override the reserved GITHUB_* variable. The Git Data API therefore queried a non-existent branch ref.

## Correction

Changed the persistence script to read SONAR_BRANCH and changed the workflow to pass the explicit research branch through SONAR_BRANCH. No statistical code, archive, protocol, or computed outputs changed.

## Recovery action

Repeat the workflow, then verify append-only Git Data API persistence, exact-byte readback, and read-only replay on the persisted branch head.

## Measured result from the accepted evaluation job

- Pair-interaction Top20: 2.5319812793 per target.
- Degree/main Top20: 2.5600624025; pair-interaction delta: -0.0280811232.
- Equal42 Top20: 2.5460218409; pair-interaction delta: -0.0140405616.
- Paired 95% CI vs degree/main: [-0.0592823713, 0.0046801872].
- Paired Holm p vs degree/main: 1.0; exact-null Holm p: 1.0.
- Primary gate: NOT_MET.

## Guardrails

No model promotion, no merge, no freeze changes. PRs #6, #7 and #8 remain untouched.