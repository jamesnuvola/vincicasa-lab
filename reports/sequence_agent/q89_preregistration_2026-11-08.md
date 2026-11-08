# Q89 preregistration — nine-feature equal-weight formula catalog

**Status:** PREREGISTERED; waiting for Q88 refreshed acceptance and exact-head CI.  
**Archive:** 3,401 draws through 2026-11-07; canonical main blob 5d2efd70684e918b27d8f06386d545647898336d.  
**Formula universe:** C(27,9) = 4,686,825 combinations, 15 deterministic shards × 312,455 formulas.  
**Walk-forward:** 3,351 targets (Discovery 2,011 / Validation 670 / Blind OOS 670).  
**Metrics:** 14,060,475 formula×split rows; global Holm family 42,181,425 primary tests.

## Quantitative hypothesis
Extend the finite equal-weight formula grammar from eight to nine prior-only features and test whether the extra feature produces a stable rank-hit gain against an eight-feature control selected by the same Discovery→Validation rule. No new feature or tuning is introduced.

## Frozen candidate rule
Top 100 formulas by Discovery Top-5 number-hit share, tie-break by lower mean actual-number rank and formula ID. Select one candidate among those 100 using Validation with the same tie-break. Apply the identical rule to Q88 to select the eight-feature control. Blind OOS is never used to choose either ID.

The single primary blind endpoint is the paired Top-5 hit-share difference. Top-10 and Top-20 are secondary. Use 20,000 circular moving-block bootstrap replicates (L=7, seed 890027) for 95% CIs, 20,000 block sign-flip replicates (L=7, seed 890028) for p-values, and Holm across the three endpoint comparisons. The exhaustive formula family also receives global Holm-Bonferroni; its finite-population hypergeometric null uses a continuity-corrected normal approximation and is explicitly exploratory.

## Gate and guardrails
Q88 must first finish its refreshed run, pass aggregate acceptance, exact-byte persistence, and exact-head CI. Q89 must reconcile all shard/formula IDs, split rows, prior-only target cutoffs, actual quintets, the selected-candidate blind ledger, and the 42,181,425-test family. Persist outputs append-only and verify exact bytes. No automatic merge or promotion; human review/integration is required before Q89 can be marked COMPLETE.

See the JSON protocol for complete acceptance criteria, output paths, seeds, cutoffs, limitations and next action.
