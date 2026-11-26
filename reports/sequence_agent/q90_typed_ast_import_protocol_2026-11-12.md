# Q141-A3 — Q90 Typed AST Import

**Registration:** 2026-11-12  
**Purpose:** deterministic structural import; no new predictive claim  
**Source artifact:** Q90 workflow run 42504717670, artifact 13627507532  
**Artifact SHA-256:** `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`

## Scope and lineage

Import the 330,429 Q90 formula definitions into a typed, canonical AST registry while preserving the original Q90 formula ID and source lineage. Q90 is a per-number score grammar built from a 59-feature Q89 matrix, but the catalog uses only 20 features selected on Discovery. It is not the full 59-feature combinatorial universe.

Q90 source archive: Git blob `5d2efd70684e918b27d8f06386d545647898336d`, 3,401 draws through 2026-11-07. It is an exact prefix of the Q141 archive, but the Q90 formula metrics remain tied to their own archive and splits. Do not pool Q90 performance rows with Q141 or Q7.

## Typed output

All imported formulas produce a **per-number score** over the 40 candidate numbers. Q7 quintet-scoring formulas are a separate output type and must not be coerced into this AST.

- **LinearMean:** arithmetic mean of 4–8 selected Q89 feature columns, each already z-scored across the 40 candidates for the target.
- **PairwiseInteraction:** 4-feature mean plus (1/4) times the across-candidate z-score of the product of one selected feature pair.
- **ConditionalGate:** 4-feature mean plus (1/4) times an indicator that one selected feature is greater than or equal to threshold (1/2) or (1).

Feature references use namespace `Q89`, preserving the original 0-based matrix index, name and selected feature family.

## Canonicalization

- Sort the terms of a commutative mean by source feature index.
- Sort the two factors of a commutative product by source feature index.
- Encode coefficients and thresholds as reduced rational numerator/denominator pairs.
- Keep the operator order explicit: mean, product, candidate z-score, scale, indicator and comparison are distinct typed nodes.
- Build `ast_id = Q90AST1-` + SHA-256 of canonical compact JSON.
- Preserve `source_formula_id` separately; never replace or rewrite the source ID.
- Exact duplicate ASTs are counted and fail acceptance rather than being silently dropped.

## Acceptance

1. Verify the Q90 ZIP SHA-256 and all 17 member byte lengths and SHA-256 hashes against the persisted Q141-A2 readback manifest.
2. Verify the Q90 formula catalog hash, 59-feature catalog, Discovery-selected 20-feature list and Q90 source archive hash.
3. Import exactly 330,429 formulas with type counts 262,599 linear means, 29,070 pairwise interactions and 38,760 conditional gates.
4. Verify every feature index/name pair, every interaction pair and every gate reference/threshold.
5. Verify unique source formula IDs and unique canonical AST IDs; no semantic simplification beyond the declared commutative normalizations.
6. Write deterministic gzip JSONL shards (50,000 rows each), with SHA-256 and Git blob SHA-1.
7. Re-read every shard, parse every record, recompute AST IDs and reconcile row/type totals.
8. Verify exact remote Git readback of all shards and report artifacts.

## Limits and next action

This import catalogs formula structure only. It does not replay formula scores, recompute Q90 metrics, or prove predictive value. The 330,429 formulas remain confined to the Discovery-selected 20-feature subset and the Q90 archive through 2026-11-07.

Next: import Q7's 1,023 quintet-ranking formulas as a distinct AST/output type, then design a common-source behaviour atlas only after source dates, target cutoffs and scoring semantics are reconciled.
