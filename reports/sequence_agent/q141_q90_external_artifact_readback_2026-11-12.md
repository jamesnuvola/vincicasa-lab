# Q141-A2 — Q90 external artifact readback

**Status:** external artifact readback verified; repository Git-object persistence, exact-head CI and human review remain pending.  
**Readback date:** 2026-11-12.

## Provenance

- Q90 PR #11 branch: research/q90-expanded-formula-grammar-20261103
- Artifact workflow run: 42504717670
- Artifact ID: 13627507532
- Exact artifact head: 30480c640c1c1f5667e28562f75247cd8661f8ad
- Bundle SHA-256: 12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077
- Bundle size: 69,356,707 bytes; 17 members; 370,206,028 uncompressed bytes.

The internal hashes for all 17 files were recalculated from the downloaded bundle. The Q90 formula catalog, split metrics, target ledger, Q90 manifest and Q89 feature matrix all match the SHA-256 values declared in the saved checkpoints/manifests.

## Archive reconciliation

Q90 archive blob 5d2efd70684e918b27d8f06386d545647898336d contains 3,401 draws through 2026-11-07. Its complete contents match the first 3,401 draws in the Q141 archive blob fcb453ed06c8002314f826dbac79d6935f9ac103, which contains 3,405 rows through 2026-11-11. The four later rows are not used in Q90's original results.

## Recovered Q90 universe

- 59 prior-only features; matrix shape 3,351 × 40 × 59, float32.
- 20 features selected on Discovery only.
- 330,429 declared formulas across linear-mean, pairwise-interaction and conditional-gate types, sizes 4–8.
- 991,287 formula/split metric rows and 3,351 target-ledger rows.
- Split counts: Discovery 2,011; Validation 670; Blind OOS 670.
- Holm-Bonferroni correction across all 330,429 formulas within each split.

This is exhaustive only within the 20-feature Discovery-selected subset and the declared variants; it is not an exhaustive search over all 59 features or all mathematical formulas.

## Recovered performance evidence

The uniform number-ranking baseline is Top-5 hit share 0.125 and mean actual number rank 20.5.

| Split | Mean Top-5 across 330,429 formulas | Mean actual number rank | Formulas surviving Holm Top-5 |
|---|---:|---:|---:|
| Discovery | 0.128680 | 20.33794 | 1 |
| Validation | 0.121003 | 20.71418 | 0 |
| Blind OOS | 0.124408 | 20.47545 | 0 |

One Discovery formula, L8_20_23_18_45_33_50_57_53, has Holm-adjusted Top-5 p = 0.03735. No formula survives Holm in Validation or Blind OOS. This is a Discovery-only result, not predictive evidence. The Blind OOS is historical and already exposed to prior SONAR research.

## Remaining work

The external artifact readback is now verified, but the Q90 checkpoint still correctly has repository Git-object persistence, exact-head CI, human review, nested ex-ante anticipation and grammar expansion pending. The largest files are 238,901,597 bytes (split metrics) and 80,772,093 bytes (formula catalog); plan deterministic chunked persistence rather than assuming a single Contents API write.

Next: build a hash-preserving chunked importer for the Q90 matrix, catalog, split metrics and target ledger, keeping Q90's per-number AST lineage separate from Q7's quintet-scoring grammar.
