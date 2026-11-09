# VinciCasa SONAR — Q92 checkpoint, runner synthetic CI in progress

Recorded: 2026-11-09, latest live status readback.

- Q89 same-archive control remains accepted/persisted on the 3,402-draw archive through 2026-11-08; candidate `P9_06_09_12_14_15_17_18_19_23` Blind Top-5 11.7910% vs uniform 12.5%, no formula/split Holm row below 0.05. No predictive gain, no promotion.
- Q92 preregistration: `C(27,10)=8,436,285`; 15 shards; Discovery 2,012 / Validation 670 / Blind OOS 670; global Holm family 75,926,565. Discrete Hypergeometric convolution amendment is pre-execution. No historical Q92 shard or catalog aggregate has run.
- Synthetic compute benchmark Q92 rank-kernel batch 2,048 measured 8.0883x speedup vs stable argsort baseline with exact rank parity; batch 4,096 was slightly slower. Synthetic throughput only.
- Q92 append-only persister synthetic acceptance [42600172269](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600172269) completed SUCCESS on exact commit `8782534e200ea9c0b54e8782ee38bbe837a33ce1`: aggregate common 9/9, null calibration 8/8, persister 3/3 PASS.
- Q92 runner/rank-kernel synthetic acceptance [42600283544](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42600283544) is IN PROGRESS on exact workflow commit `29132867bc96ddf212ae4dfb465de01c3163960a`; at last readback dependency installation was in progress, compile/test steps pending.
- Full project exact-head CI [42598985535](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42598985535) on preflight source commit `72f0d7b9dc23b9e0c2d979f49382768b722ce071` is still IN PROGRESS at exhaustive Q80-Q86 catalog tests; no success yet.
- Checkpoint `sonar_q92_full_walkforward_checkpoint_2026-11-09T1021Z_synthetic-pass.md` was persisted and byte-readback verified (blob SHA `567f076e8ccff9d65d1e0d37ba3fea46a6d72ae9`). Workflow branch/path trigger repairs and three fixture corrections are also persisted.
- PR #6, #7 and #8 were fetched again: all OPEN, not merged, and not changed in this cycle.

Next: finish runner synthetic acceptance; finish exact-head full CI; then validate artifact-backed immutable 15-shard execution/recovery, source hashes, strict-prior ledger, global Holm, Discovery→Validation freeze, paired Blind OOS vs same-archive Q89, acceptance and byte-readback. Human review remains mandatory. No merge, promotion or shadow insertion.
