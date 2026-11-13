# VinciCasa SONAR — cycle 21 (2026-11-13)

## Recovery and source integrity

- Recovered Q141-A10 checkpoint: `REMOTE_GIT_READBACK_VERIFIED`.
- Pinned source: Q141-A7 artifact run 43348144964, artifact 14003350043.
- Canonical archive blob: `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb`, 3,406 draws through 2026-11-12.
- Feature matrix: 3,356 × 40 × 59; SHA-256 `81479d7cff00ddcbc6046bcb390efb2ef1b08de6a6f1f2cdb2f89a77c76c6047`.
- B11 remains one frozen prediction and zero reconciled outcomes. The official November archive still lists contest 317 (2026-11-13) as “In programmazione / In attesa”; no outcome was read or appended.

## Diagnosis and new hypothesis

A10 tested pairwise co-occurrence residuals after removing additive single-number effects. A11 extends the decomposition to third-order co-occurrences and removes all lower-order single and pair effects.

For each target, only the preceding 200 draws form the recent triple counts; a disjoint preceding 200-draw window is the stale control. The triple residual tensor satisfies zero pair marginals. The exact uniform 5-of-40 conditional variance is checked by exhaustive enumeration on a smaller n=8 problem.

Primary endpoint: mean standardized recent triple-residual score, practical threshold +0.10.  
Secondary endpoint: exact-variance-standardized recent-versus-stale residual contrast, practical threshold +0.05.  
Inference: martingale score approximation under the independent uniform 5-of-40 null, with predictable variance n; HAC/ACF sensitivity; Holm across the two registered endpoints. No parameter tuning.

## Walk-forward results

- Targets: 2,956; Discovery 1,774; Validation 591; historical Blind OOS 591.
- Discovery mean Z3 recent: +0.01314; recent/stale contrast: +0.00082.
- Validation mean Z3 recent: -0.00346; contrast: -0.03424.
- Blind OOS mean Z3 recent: -0.02250; contrast: -0.05259.
- Blind primary one-sided martingale-normal p: 0.70776; Holm p: 1.000.
- Blind secondary p: 0.89948; Holm p: 1.000.
- Primary 95% IID-sensitivity interval: [-0.09910, +0.05411].
- Secondary 95% IID-sensitivity interval: [-0.13044, +0.02525].
- Sample SDs: 0.9502 (primary), 0.9656 (contrast).
- HAC standard errors and ACF at lags 1, 5, 20, 50, 100 are in the machine-readable report.

Decision: no third-order triple-residual lift demonstrated. The historical Blind OOS is exploratory, not virgin confirmation. Holm covers only the two A11 endpoints, not the full Q00–Q141 research family.

## Validation and persistence

- 8 deterministic, decomposition, exact-variance, cutoff and future-suffix tests passed.
- Dedicated workflow 43396887184 completed successfully, including source-artifact download, full walk-forward, fail-closed ledger validation, Git persistence, remote readback and artifact upload.
- 2,956 ledger rows; all cutoffs precede targets; maximum pair-marginal residual below (8\times10^{-15}).
- Checkpoint status: `REMOTE_GIT_READBACK_VERIFIED`.
- General repository CI 43396887110 was still running at the time of this report; it is not claimed as passed.

## Governance and next action

- B11 freeze unchanged; canonical archive unchanged; no shadow insertion or engine promotion.
- PR #90 remains open and draft; no merge or rebase.
- PRs #6, #7 and #8 remain untouched.
- Next: preserve B11 until the official 2026-11-13 result is published, then append-only reconcile it. For research, prioritize Q141 formula-family behaviour/coverage and pre-target regime observability; do not blindly escalate to fourth-order counts, which would be extremely sparse (91,390 quadruples versus five per draw).
