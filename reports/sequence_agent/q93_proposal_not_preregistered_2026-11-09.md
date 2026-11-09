# Q93 — proposal only, not preregistered

**Recorded:** 2026-11-09  
**Status:** PROPOSAL_ONLY_NOT_PREREGISTERED_NOT_EXECUTED  
**Dependency:** Q92 historical walk-forward, aggregation, acceptance and human review must finish first.

## Quantitative hypothesis

A frozen equal-weight eleven-feature formula, selected only through the historical Discovery → Validation path, may improve prospective Top-5 number-hit share by at least **0.005 absolute** (0.5 percentage points) over the frozen Q92 ten-feature candidate during a new, untouched holdout of **670 future target draws** after the canonical archive cutoff 2026-11-08.

A separate absolute-evidence condition requires the Q93 candidate's prospective Top-5 hit share to exceed the uniform-rank expectation of **0.125**, with its exact one-sided null p-value below the multiplicity-adjusted threshold.

## Historical candidate-development universe

- Feature columns: 27, identical registered prior-only feature stack as Q92.
- Formula size: 11, equal weights of 1/11 over the selected standardized feature columns.
- Formula count: C(27,11) = 13,037,895.
- Proposed deterministic partition: 15 contiguous lexicographic shards × 869,193 formulas.
- Historical scored targets: 3,352; Discovery/Validation/old Blind OOS = 2,012/670/670.
- Historical catalog metric rows, if retained for catalog-level inference: 13,037,895 × 3 = 39,113,685.
- Historical formula × split × three-endpoint Holm family: 117,341,055.
- Candidate selection: Discovery top-100 by mean Top-5 number-hit share, tie-break lower mean rank then lexicographic formula ID; select one on Validation using the same deterministic rule; freeze before the first prospective holdout target.
- The historical Blind OOS must not be used for candidate selection and remains exposed/exploratory because of prior SONAR activity.

## Prospective confirmatory protocol proposal

1. Freeze Q92 candidate and Q93 candidate IDs, feature definition, score, tie-break, archive SHA and code hashes before observing any of the 670 prospective outcomes.
2. For every prospective target index i, compute features only from draws with index < i; rank all 40 numbers before scoring the target; update state only after scoring.
3. Evaluate both frozen candidates on exactly the same 670 consecutive new targets. Also record the uniform baseline expectation.
4. Primary paired endpoint: Q93 Top-5 number-hit share minus Q92 Top-5 number-hit share.
5. Practical effect gate: mean paired Top-5 delta ≥ 0.005.
6. Paired inference proposal: circular moving-block bootstrap, 20,000 replicates, block length 7, fixed seed; require 95% lower confidence bound > 0. Block sign-flip, 20,000 replicates, two-sided.
7. Absolute Q93 endpoint: exact one-sided discrete convolution of iid Hypergeometric(40,5,5) counts over 670 targets; require observed Q93 Top-5 share > 0.125.
8. Joint confirmatory multiplicity family proposal: Holm across five predeclared p-values — paired Top-5, Top-10, Top-20, mean-rank comparison, and absolute Q93 Top-5 vs uniform. The Top-5 paired test remains the sole primary practical-effect endpoint; secondary endpoints cannot substitute for it.
9. No interim significance looks, no candidate reselection, no holdout extension based on interim results, and no use of these 670 outcomes for tuning.
10. If 670 future targets are not yet available, remain pending; do not shorten the holdout or inspect partial results for promotion.

## Controls and limitations

- The historical Q92 Blind OOS is not an independent confirmation set; the new prospective holdout is required.
- The exact Hypergeometric null assumes independent uniform 5-of-40 outcomes under the lottery mechanism.
- Holm controls family-wise error only if component p-values are valid under their stated nulls.
- The 0.005 threshold is a predeclared practical-effect requirement, not a forecast of expected gain.
- Equal-weight eleven-feature subsets are a finite grammar, not the full mathematical model space.
- Q93 does not establish that a lottery is predictable and must not be presented as a betting edge absent prospective evidence.
- This proposal is not an execution instruction. No Q93 code, shards, outputs or promotion are authorized by this document.

## Next action

Complete Q92 on its exact source commit, reconcile all 15 artifacts, run global Holm and acceptance, persist outputs append-only, then request human review. Only after that review may a human decide whether to preregister Q93 with the exact protocol above.
