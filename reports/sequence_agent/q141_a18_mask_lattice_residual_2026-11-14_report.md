# Q141-A18 — Mask-Lattice Residual Spectral Mapping

**Status:** COMPLETED_HISTORICAL_PREQUENTIAL_MASK_RESIDUAL_TEST
**Decision:** MASK_LATTICE_RESIDUAL_STRUCTURE_NOT_CONFIRMED

## Frozen hypothesis

After removing the intercept, 10 family main effects and 45 pair interactions, the six-dimensional residual subspace must capture at least 0.50 in both holdouts, beat the conditional null after Holm correction, and retain adjacent subspace overlap >= 0.75.

## Mask-lattice design

- Formula masks: 1,023; design columns/rank: 56/56; residual dimensions: 967.
- Design: intercept + 10 family indicators + 45 pairwise products.
- Each split basis is fitted on exactly the 400 targets immediately preceding that split.

## Results

| Split | Targets | Residual capture k6 | 95% block CI | Conditional null mean | Null q99 | k80 |
|---|---:|---:|---:|---:|---:|---:|
| discovery | 1792 | 0.534334 | [0.523262, 0.545429] | 0.061340 | 0.071780 | 11 |
| validation | 597 | 0.600535 | [0.582687, 0.617391] | 0.062993 | 0.077000 | 11 |
| blind_oos | 597 | 0.624041 | [0.605255, 0.642844] | 0.062620 | 0.076150 | 11 |

## Primary holdout tests

| Holdout | Raw p | Holm p |
|---|---:|---:|
| validation | 0.005000 | 0.010000 |
| blind_oos | 0.005000 | 0.010000 |

## Subspace stability

- Discovery → Validation: 0.643390
- Validation → Blind OOS: 0.907737
- Discovery → Blind OOS: 0.635329

## Limits

This is a structural decomposition of realized rank profiles, not a forecast. The historical Blind OOS is not virgin prospective evidence. The conditional shift null preserves each residual column's circular sequence before row-wise re-projection, so it is a defined surrogate rather than a universal null.


Full deterministic replay: byte-identical (verified by the dedicated workflow).
