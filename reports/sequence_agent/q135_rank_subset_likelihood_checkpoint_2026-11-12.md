# Q135 checkpoint — 2026-11-12

## Recovery/source
- Main base: 0bf1ef0d39afb671ff83e519489f16b0c24eb15a.
- Upstream Q123 head: 93b494b089abf485b6616f71b90baec79e39c796.
- Immutable Q123 rank-ledger blob: 36d7af1fb3cceda5976eb99a78931f58d1a3d28a.
- Upstream Q123 report/protocol blobs: 3d845ed8b9603fc762446eea38ea126262ff5886 / cf69b9bb1ec738a1fc1f17ff02da3a79d4213252.
- Clean historical prefix: 3,204 targets through 2026-11-10; the disputed 2026-11-11 row is excluded.

## Model
- Fixed-size exponential subset model P_beta(S)=exp(-beta*rank_sum)/Z(beta).
- Beta selected only on Discovery from 21 fixed values in [0, 0.005].
- Validation and Blind OOS use the selected beta without retuning.

## Results
- Selected beta: 0.0005.
- Discovery mean log-likelihood gain: 0.000074584266.
- Validation mean log-likelihood gain: -0.000674973365; Brier delta: 0.000151183361.
- Blind OOS mean log-likelihood gain: 0.000333606979; Brier delta: -0.000075080049.
- Decision: NO_RANK_SUBSET_LIKELIHOOD_LIFT_DEMONSTRATED.

## Validation
- Checks: 22/22.
- Randomization: 10000 per split/endpoint; block bootstrap: 10000 with block 20.
- Holm family size: 4.

## Limits and next action
- Exploratory post-hoc extension of Q123; not independent confirmation.
- Historical Blind OOS is not virgin; uniform independent 5-of-40 null assumed.
- No archive, freeze, Q60 gate or production engine mutation.
- Continue only source-clean prospective collection; human review required before any promotion.
