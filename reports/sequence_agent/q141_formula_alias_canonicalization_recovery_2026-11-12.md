# Q141-B1 — Recovery amendment 1: floating-point tie sensitivity

**Date:** 2026-11-12  
**Status:** AMENDMENT BEFORE RERUN; original preregistration remains unchanged and preserved.

## Failure evidence

Two CI attempts exposed separate issues:
1. Run 43222532830: the synthetic unit-test matrix assigned independent values to columns that the source feature builder defines as exact aliases. The fixture was corrected to set column 25 equal to column 0 and column 26 equal to column 1. The seven unit tests then passed on run 43222764935.
2. Run 43222764935, head \`d13261bfd593b08f4417af377e605c5466fa35c1\`: the complete 3,354-target walk-forward reached the final acceptance check. It recorded zero alias mismatches and zero score mismatches at tolerance 1e-12, but 2,311 rank mismatches across 402,480 target-formula comparisons (0.57419%).

## Root-cause diagnosis

The initial rank comparison mixed two floating-point evaluation paths:
- legacy raw formula: NumPy mean over raw columns;
- canonical formula: multiplicity-preserving weighted mean using \`math.fsum\`.

The two score vectors remained equal within 1e-12, but exact rank ordering can change when two candidates have nearly equal scores. The ranker uses exact floating-point comparisons and a deterministic number-index tie-break; it does not quantize scores. Thus tiny summation-order differences can change ranks without indicating different mathematical formula functions.

This is a numerical reproducibility issue in the legacy evaluation path. It is not acceptable to hide it or to count it as proof that the formulas are mathematically different.

## Recovery protocol

The next run separates two questions:
1. **Mathematical identity (primary):** evaluate the raw expression and canonical weighted AST with the same order-stable \`math.fsum\` semantics. Require score equality within 1e-12 and identical ranks on all 40 numbers for every sampled formula and target.
2. **Legacy compatibility (diagnostic):** retain the original NumPy-mean path and separately report score deltas, rank mismatch count/rate, maximum rank displacement, and maximum score gap among pairwise order flips. Do not fail mathematical identity solely because the legacy floating implementation resolves near-ties differently.

No production ranker or forecast engine is changed. A separate tie-policy audit is required before a canonical evaluator could replace legacy scoring.

## Statistical interpretation

The alias/canonicalization result is deterministic and algebraic. No p-values or multiple-testing adjustment apply. The 120 formula instances are a fixed implementation sample, not a random inferential sample. Discovery, Validation and historical Blind OOS are reported as chronological diagnostics only; no predictive lift is claimed.

## Recovery acceptance

- Seven synthetic unit tests pass, including future-suffix invariance and a negative control showing naive alias deletion changes weights.
- All 3,354 strict-prior targets and 2/3,354 alias checks per target are processed.
- Stable raw versus canonical score and rank mismatches are both zero.
- Legacy NumPy rank sensitivity is measured and reported, not suppressed.
- All source hashes, target cutoffs, split counts, manifests and exact Git readback are verified.
- No archive edit, freeze reconstruction, shadow insertion, engine promotion, merge or change to PRs #6/#7/#8.
