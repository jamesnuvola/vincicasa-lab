# Q141-B1 — Exact alias canonicalization of the 27-feature formula grammar

**Registration:** 2026-11-12  
**Status before execution:** PREREGISTERED_EXECUTION_PENDING  
**Research branch:** \`research/q141-formula-universe-behaviour-mapping-20261112\`  
**Current main commit at registration:** \`70dcf8cc128884d9739959406d5662ef76daa253\`  
**Eligible archive:** \`data/storico_daily.csv\`, Git blob \`fcb453ed06c8002314f826dbac79d6935f9ac103\`, 3,404 draws through 2026-11-10. Contest 315 / 2026-11-11 remains excluded.

## Quantitative hypothesis

The 27-column Q80 feature schema contains two exact aliases:
- \`recent_5\` is exactly \`freq_5\`.
- \`recent_10\` is exactly \`freq_10\`.

The formula grammar uses equal-weight means of subsets of distinct raw feature columns. Exact aliases therefore create repeated mathematical signals with different multiplicities. A correct canonical AST must preserve those multiplicities as rational weights; simply dropping duplicate columns would change the formula.

For all raw combinations of sizes 1 through 10:
- nominal count: sum of C(27,k) = 16,628,808;
- predicted exact canonical weighted-mean count: 9,808,263;
- predicted collapse: 6,820,545 formulas (41.0164%).

**Primary hypothesis:** the exact canonical count is 9,808,263 and the raw-to-canonical score/rank mapping is invariant on every eligible strict-prior target.

This is an algebraic/structural hypothesis, not a claim of predictive lift.

## Canonicalization rule

Map the two aliases to their canonical base feature IDs. For a raw formula, count the multiplicity of each canonical feature, then divide all integer weights by their greatest common divisor. The resulting primitive rational-weight vector is the canonical AST.

Examples:
- mean(freq_5) and mean(freq_5, recent_5) are equivalent.
- mean(freq_5, recent_5, freq_10) has weights freq_5:2, freq_10:1 and is **not** equivalent to mean(freq_5, freq_10).
- mean(freq_5, recent_5, freq_10, recent_10) is equivalent to mean(freq_5, freq_10).

No correlation-based, rank-based or approximate semantic deduplication is allowed. The 32 Q89 extension features remain distinct until exact functional equivalence is proved.

## Walk-forward verification

- Use the pinned 3,404-draw source prefix; minimum history 50.
- Score all 3,354 targets in chronological order, split 2,013 / 671 / 670.
- At each target, compute Q80 features from draws strictly before that target; append the target only after scoring.
- Verify both exact alias pairs at every target.
- Verify a deterministic sample of 12 raw formulas at each size k=1..10 (120 formula instances) by comparing legacy mean scores/ranks with canonical weighted-mean scores/ranks on all 40 numbers.
- Report score tolerance, rank mismatches, Top-5/10/20 hit metrics by Discovery, Validation and historical Blind OOS for raw and canonical evaluators. These paired outputs must be identical within the registered numerical tolerance.
- Test future-suffix invariance with synthetic fixtures.

## Baselines and controls

- Baseline: raw index-subset formula IDs.
- Candidate: canonical typed weighted-mean AST IDs.
- Negative control: naive alias deletion without multiplicity preservation; unit tests must demonstrate that it changes at least one constructed formula score.
- Reference only: uniform 5-of-40 expected number-hit shares of 0.125 / 0.25 / 0.5 for Top-5 / Top-10 / Top-20.

No inferential p-values or multiple-testing adjustment are appropriate for an exact deterministic identity check. Any predictive-performance claim is explicitly out of scope.

## Acceptance and limits

- Exact combinatorial counts and formula-size denominators reconcile.
- 3,354 strict-prior targets and all split counts reconcile to the pinned archive.
- Both aliases are exactly equal on every target.
- All sampled formula scores are equal within 1e-12 and all sampled ranks are identical.
- Future-suffix invariance and deterministic replay pass.
- Registry, report, target ledger and manifest are persisted and read back by exact Git blob/hash.
- This validates only exact alias canonicalization of the 27-feature equal-weight grammar. It does not establish semantic uniqueness of the 59-feature Q89 extension, Q90 interactions/gates, graph/field formulas, or all mathematical functions.
- Historical Blind OOS is exposed research history, not virgin prospective evidence. No engine promotion, shadow insertion, archive mutation, auto-merge or changes to PRs #6/#7/#8.
