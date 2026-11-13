# Q141-A17 — Full-Universe Prequential Spectral Mapping

**Status:** COMPLETED_HISTORICAL_PREQUENTIAL_STRUCTURAL_TEST
**Decision:** FULL_UNIVERSE_SIX_DIMENSIONAL_PREQUENTIAL_STRUCTURE_NOT_CONFIRMED

## Design

- Full Q7 panel: 3,386 target rows × 1,023 formula masks.
- Initial training prefix: 400; fixed basis dimension: 6.
- Evaluated targets: 2,986; Discovery / Validation / historical Blind OOS: 1792 / 597 / 597.
- The basis and scaler are fitted only on the first 400 target rows and then frozen.

## Results

| Split | Mean captured energy | 95% block-bootstrap CI | Circular-shift null mean | Null q99 |
|---|---:|---:|---:|---:|
| discovery | 0.733447 | [0.723110, 0.743768] | 0.006425 | 0.006692 |
| validation | 0.712218 | [0.695421, 0.727714] | 0.006398 | 0.006775 |
| blind_oos | 0.712131 | [0.694123, 0.729520] | 0.006470 | 0.006869 |

## Primary holdout tests

| Holdout | Raw p | Holm p | Practical threshold |
|---|---:|---:|---:|
| validation | 0.005000 | 0.010000 | mean capture >= 0.75 |
| blind_oos | 0.005000 | 0.010000 | mean capture >= 0.75 |

Training spectrum: participation ratio 6.8794; entropy effective rank 9.2332; k80=6; k90=7; top-six variance share 0.848252.

## Limits

This tests whether the realized formula-rank profile lies in a subspace learned before each evaluated target. It does not predict the actual numbers or a ticket. The historical Blind OOS is exposed to previous SONAR research, and the circular-shift null is only one temporal dependence control.
