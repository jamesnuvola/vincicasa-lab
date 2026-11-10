# Q88 post-run checkpoint — 10 November 2026

## Execution result

The preregistered Q88 signed node-to-graph transfer walk-forward completed on workflow run 42731530270. The independent validator returned PASS.

- Canonical archive: 3,402 draws, 2017-07-17 to 2026-11-08; SHA-256 5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b.
- 3,202 strict-prior targets: Discovery 1,921; Validation 640; historical Blind OOS 641.
- 15 models: 12 frozen Q87 comparators plus 3 preregistered Q88 operators.
- 48,030 complete 40-number rank vectors independently replayed.
- 256,160 signed-transfer values independently replayed.
- 135 exact-null Holm tests and 96 paired block-bootstrap Holm tests.
- Unit tests: 10/10 passed.
- Acceptance: PASS.

## Measured outcome

The candidate selected on Discovery only was DYN::TRANSFER_BLEND.

Blind OOS Top20: 2.531981 versus Equal42 2.546022; delta −0.014041. Paired block-bootstrap 95% CI [−0.035920, +0.007800], raw p=0.213, Holm p=1.000. Exact-null Holm p=1.000. Validation Top20 delta was −0.009375.

The historical primary gate is NOT_MET. Q88 is not promoted.

## Diagnosis

The signed projection signal is mostly weak/near-zero at the instantaneous transition level: 68.9% of Blind OOS number-transition values have absolute magnitude below 0.05. The rolling signal has about 42.8% near zero. Discovery's selected blend did not carry forward to Validation or Blind OOS. The current projection does not show measurable incremental ranking value against Equal42.

## Persistence and evidence

The full six-file Q88 bundle was uploaded and verified as artifact 13725366402 (3,069,825 bytes; SHA-256 67c3130b42429b49441d1be01449d86c58a191e6be06303c3a21f1787f65ee36; expires 2026-11-17). The compact summary, validation result and artifact manifest are persisted separately in the repository.

The complete 3.05 MB target ledger is not yet committed to the repository. Do not mark repository persistence complete until that ledger/full report are committed and read back. The current read-only PR workflow and general CI still need to pass on the persisted exact head.

## Next iteration

Do not retune Q88 from its historical Blind OOS. The next research question should be whether graph-to-node transfer is distinguishable from a node-only autoregressive null and from a degree-preserving edge randomization control. Preregister those controls before running another formula family. Require prospective confirmation for any apparent gain.

No immutable freeze was modified. No engine promotion or automatic merge. PR #6, #7 and #8 remain untouched.
