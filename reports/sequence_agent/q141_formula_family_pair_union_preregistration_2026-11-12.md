# Q141-C1 — Size-adjusted formula-family pair-union complementarity

**Registered:** 2026-11-12, before C1 computation  
**Status:** PREREGISTERED_EXECUTION_PENDING  
**Parent:** Q141 Formula Universe & Behaviour Mapping  
**Source:** `data/storico_daily.csv`, Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`; 3,404 eligible draws through 2026-11-10. Exclude contest 315 / 2026-11-11.

## Hypothesis

At least one pair among the six Q141-C0 formula families has a union of its two prior-only Top-5 candidate sets that contains more winning numbers than a random candidate set of the same target-specific size. This tests whether apparent family complementarity exceeds the mechanical gain from using more candidates.

## Candidate construction

Reuse, without retuning, the Q141-C0 strict-prior feature definitions and six families derived from 25 unique Q80 features. For each target, independently rank numbers 1..40 within each family using the Q141-C0 equal-mean standardized family score and ascending-number tie-break. Each family contributes exactly five candidates. Evaluate all 15 unordered pairs, with no pair selection or parameter tuning.

For pair `(a,b)` at target `t`:
- `S_a,t` and `S_b,t` are the two prior-only Top-5 sets.
- `U_t = |S_a,t union S_b,t|`, necessarily 5..10.
- `H_t = |Y_t intersect (S_a,t union S_b,t)|`, necessarily 0..5.
- Conditional uniform expectation: `mu_t = 5 U_t / 40`.

## Conditional null and inference

Under independent uniform draws of five distinct numbers from 1..40, conditional on all information available before target `t`, the candidate union and its size are fixed, so:

`H_t | F_(t-1) ~ Hypergeometric(N=40, K=U_t, n=5)`.

Because `U_t` is adaptive and depends on earlier outcomes, do **not** treat the sequence as an unconditional independent convolution with fixed parameters. Use a predictable conditional e-process. For each fixed `lambda` in `{0.05, 0.10, 0.20, 0.40}`, update:

`E_(lambda,t) = E_(lambda,t-1) * exp(lambda*(H_t-mu_t) - log E[exp(lambda*(X_t-mu_t)) | F_(t-1)])`

where `X_t ~ Hypergeometric(40,U_t,5)`; calculate the conditional moment exactly from its finite PMF. The test e-process is the equal-weight mixture of the four lambda-specific processes. The one-sided anytime-valid p-value is `min(1, 1 / max_t E_mix,t)` by Ville's inequality.

Test 15 unordered family pairs × 3 fixed chronological splits = 45 hypotheses. Apply Holm-Bonferroni across all 45 p-values. The primary decision concerns Blind OOS; no pair is chosen using Blind results. Report observed hits, size-conditioned expected hits, excess hits, union size, e-process maximum and adjusted p-value.

## Walk-forward and integrity

- Minimum prior history: 50 draws; expected targets 3,354.
- Discovery / Validation / Blind OOS: 2,013 / 671 / 670 using the fixed Q141-C0 split rule.
- All features and candidate sets use only the strict prefix before each target. Update historical state only after scoring the target.
- Persist a target × pair ledger (50,310 rows) with target/cutoff dates, actual quintet, pair IDs, union mask/size, observed hits and conditional expectation.
- Require exact source blob pin, split counts, 15-pair/45-test denominators, valid masks and hit counts, deterministic replay, future-suffix invariance, exact e-process normalization, Holm adjustment and output hash readback.

## Decision and limitations

A size-adjusted pair-complementarity signal requires positive Blind OOS excess and Holm-adjusted p<0.05 within the registered 45-test family. Otherwise report no demonstrated size-adjusted pair lift. This is a historical exploratory test using six coarse families, not the full formula universe; the archive is heavily exposed, the null assumes independent uniform 5-of-40 draws, and Holm does not control the entire Q00-Q141 project-wide search history. No automatic merge, shadow insertion or engine promotion.

**Next:** use the result to decide whether pair complementarity deserves a larger canonical formula registry; continue Q141-A lineage audit and Q141-B typed formula registry regardless of a null result.
