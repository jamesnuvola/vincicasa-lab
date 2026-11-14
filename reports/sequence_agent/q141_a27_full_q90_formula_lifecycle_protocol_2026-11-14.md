# Q141-A27 — Full-Q90 formula lifecycle and rank-stability audit

**Status:** post-hoc descriptive audit specification, not a preregistration.

The Q90 artifact was already available and its summary had been inspected before this audit was specified. The analysis is therefore exploratory and must not be represented as confirmatory.

## Objective

Describe whether the 330,429 Q90 formula rankings retain their relative ordering across Discovery, Validation and historical Blind OOS, and map how the retrospective best formula and best operator family vary from target to target.

## Fixed source

- Workflow run: `42504717670`
- Artifact: `13627507532` (`q90-expanded-formula-grammar-bundle`)
- Artifact SHA-256: `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`
- Archive: 3,401 draws through 2026-11-07
- Strict-prior targets: 3,351
- Formula catalog: 330,429

## Analyses

1. Formula-rank Spearman/Pearson correlations across chronological splits.
2. Retention of the top 0.1%, 0.5%, 1%, 5% and 10% of formulas.
3. Holm-significant formula counts by split and endpoint.
4. Retrospective oracle-best formula identity recurrence.
5. Per-target best formula within each of the seven Q90 operator/size families.
6. Family-winner transitions, run lengths and a 20,000-shuffle count-preserving reference.

## Interpretation rules

- The oracle-best formula is selected after seeing the target outcome. It is a descriptive upper envelope, not a forecast.
- Formula-level correlations and overlap are descriptive because the formula catalogue contains highly dependent, overlapping expressions.
- The family-winner shuffle reference tests only whether the retrospective family labels are more serially structured than a random ordering with the same counts. It is not a predictive test.
- No model promotion, forecast insertion or freeze modification is permitted.
