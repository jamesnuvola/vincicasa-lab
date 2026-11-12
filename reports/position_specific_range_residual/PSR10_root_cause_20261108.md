# PSR-10 Root-cause note — 2026-11-08

## Diagnostic question
Does conditioning the next ordered-position marginal on the previous draw's total-sum quartile add information beyond the global transition marginal?

## Measured diagnostic
The validation-selected alpha values are P1=1000, P2=3000, P3=3000, P4=3000, P5=1000. The largest validation point gain is P5 (+0.000190239 Brier) and P4 (+0.000060023); P2 and P3 validation gains are negative at selected alpha. In blind OOS, gains vs global same-alpha are P1 +0.000073454, P2 +0.000148229, P3 −0.000110149, P4 −0.000339750, P5 −0.000167685. None survives Holm correction across the ten endpoints; P2's raw centered bootstrap p=0.065467 becomes Holm p=0.654673.

## Root-cause interpretation
The four previous-sum bins divide prior transition data into smaller conditional samples. Strong shrinkage (alpha 1000 or 3000) dominates, and validation gains are not concordant across positions or retained on the blind tail. The evidence is consistent with sparse conditional counts and non-persistent sample associations; it does not identify a physical cause and does not establish that the lottery is predictable.

## Reproducibility
Canonical archive SHA pinned; full run repeated in the same execution environment and JSON, Markdown and all five CSV ledger strings were byte-identical. Synthetic replay test (first 700 archive rows, 500 targets, alpha grid 300/1000, 50 bootstrap replicates) passed strict cutoff and train-count assertions. GitHub Actions exact replay is pending on the draft PR at persistence time.

## Next
Do not promote PSR-10 or add it to the shadow gate. Continue the pre-existing Q60 append-only paired prospective gate. Revisit only with new prospective outcomes or human-approved independent preregistration.
