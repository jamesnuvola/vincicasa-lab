# Q89 preregistration — neighbor-identity counterfactual

**Status:** preregistered; execution not yet performed.

Freeze the Q88 identity-mapped signed transfer formula. Test whether it depends on the true mapping from graph neighbors to their prior six-feature states.

- 39 unique deterministic random neighbor-label permutations (seed 8901, Python random.Random MT19937), plus identity.
- Permute only prior neighbor-feature rows; do not change the edge-delta matrix, so edge weights and row strengths remain unchanged.
- Add a graph-free node-inertia control from cosine between successive node-delta vectors.
- Keep Q88 alpha/window/decay fixed at 0.20/20/0.80. No model selection or tuning.
- 3,202 strict-prior targets; Discovery/Validation/historical Blind OOS = 1,921/640/641.
- Exact-null Holm family 378; paired block-bootstrap Holm family 24; label-randomization Holm family 9.
- Historical Blind OOS is exploratory, not a virgin holdout. Promotion and prospective shadow insertion are prohibited.
