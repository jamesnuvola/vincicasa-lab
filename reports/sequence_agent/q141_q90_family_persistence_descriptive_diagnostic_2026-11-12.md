# Q141-B7-D1 — descriptive family persistence diagnostic

**Status:** post-hoc descriptive diagnostic; not preregistered and not inferential.

The 700-formula Q90 family ledger shows very weak one-step persistence in family-average Top-5 hit share:

| Split | Mean lag-1 correlation across seven families |
|---|---:|
| Discovery | -0.01158 |
| Validation | +0.01307 |
| Blind OOS | -0.02549 |
| All targets | -0.00767 |

In Blind OOS, all seven family-specific lag-1 correlations are negative (from -0.00881 for pairwise interactions to -0.03376 for linear L5). The rolling selector's chosen family remains the same on 86.7% of adjacent scored targets, yet this label stability does not yield next-target performance lift.

The equal-family mean Top-5 share is 0.128466 in Discovery, 0.121131 in Validation and 0.124715 in Blind OOS, against a uniform reference of 0.125. The Discovery-to-holdout decline is consistent with feature-selection optimism, but cannot distinguish it from regime change or sampling variation.

**Interpretation:** weak or negative short-lag family-outcome persistence is a plausible reason the rolling-100 selector failed. This is descriptive evidence only; no p-values were calculated, no confirmatory claim is made, and it is not part of the preregistered six-test family.

**Next action:** do not tune the selector/window from this diagnostic. Prioritize durable Q90 artifact import and typed AST reconciliation.
