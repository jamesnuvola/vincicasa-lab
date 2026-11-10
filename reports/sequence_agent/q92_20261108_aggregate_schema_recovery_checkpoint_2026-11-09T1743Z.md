# Q92 aggregation checkpoint — preliminary statistics and compact-CSV recovery
Date: 2026-11-09 17:43 UTC
Task: \`Q92_2026_11_08\`
Source run: [42648067242](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648067242)
Source checkout: \`8f7ac10b1edc7272e8463e61a89fdce8bb80da5c\`
Canonical archive SHA-256: \`5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b\`

## Verified execution and aggregation facts
- Preflight passed; all 15 shard jobs succeeded.
- Aggregator log reports artifact reconciliation PASS: shard coverage 0..14, source checkout SHA matched, receipt file byte counts and SHA-256 values matched, and rerun receipts (where present) were byte-identical.
- Aggregation completed its computation and emitted \`AGGREGATED_PENDING_ACCEPTANCE_VALIDATION\`: 3,402 archived draws, 3,352 scored targets, 8,436,285 formulas, 25,308,855 formula×split metric rows; split counts Discovery 2,012, Validation 670, Blind OOS 670.
- Global Holm family: 75,926,565 formula×split×endpoint tests. Raw p-vector SHA-256 \`9334b5deb519da352ad2097fadd1c9ea37d04e954c730d3d73670cd6bc002ef3\`; adjusted vector SHA-256 \`845dd86f9d68a3e6983bcad9228e3c0ddff22bebfa9b0c784a7338fca1f55ad3\`. The emitted summary reports 0 formula/split rows below adjusted 0.05 and minimum row-wise max-endpoint adjusted p=1.0.
- Discovery selected top-100 count=100; Validation candidates=100; selected formula \`P10_01_08_11_12_14_15_16_18_19_23\`; Q89 control \`P9_06_09_12_14_15_17_18_19_23\`. The aggregate summary explicitly says Blind OOS was not used for selection.

## Preliminary paired Blind OOS evidence (log only; acceptance still blocked)
The paired inference emitted for 670 targets used circular moving-block bootstrap and block sign-flip, 20,000 replicates, block length 7, fixed seeds 920027/920028, and Holm across four endpoints:
- Top-5 delta vs Q89: -0.0062686567; 95% CI [-0.0167164179, 0.0041791045]; raw sign-flip p=0.26873656; Holm p=0.61976901.
- Top-10 delta: +0.0038805970; 95% CI [-0.0086567164, 0.0167164179]; raw p=0.58892055; Holm p=0.61976901.
- Top-20 delta: -0.0101492537; 95% CI [-0.0250746269, 0.0047761194]; raw p=0.20658967; Holm p=0.61976901.
- Mean actual-number rank delta: +0.2370149254; 95% CI [-0.0352313433, 0.5119402985]; raw p=0.09374531; Holm p=0.37498125.
- Primary decision emitted: \`NO_SIGNIFICANT_GAIN\`. Q92 Top-5 relative lift does not meet the registered +0.005 practical threshold and its paired CI includes zero.

These values are read from the workflow aggregate log, not from a persisted, acceptance-validated report. Do not treat them as final or promoted evidence. The absolute-uniform evidence JSON was not exposed in the compact log summary and is not claimed here.

## Acceptance failure and root cause
The aggregate job failed at the acceptance validator:
\`Q92_ACCEPTANCE_BLOCKED: Q92 compact metric part exact schema mismatch shard 0\`.

Source inspection identified the writer in \`scripts/aggregate_sonar_q92_ten_feature.py\` using a two-character literal \`\\\\n\` as CSV line terminator instead of a real LF. A local Python reproducer confirmed that this produces one concatenated decompressed stream and a malformed DictReader header (e.g. fields bleed across records), matching the exact-schema failure. The raw shard CSVs and artifact receipts themselves passed reconciliation.

## Recovery change and regression
- Extracted compact-part writing into \`compact_metrics_part(...)\`, preserving deterministic gzip (mtime=0, filename empty, level 9), exact row count/split order and source SHA metadata.
- Corrected the CSV writer to use a real newline line terminator.
- Added a synthetic regression that writes six compact rows across three splits, then reads gzip back and checks exact seven-field schema, six rows, seven LF bytes, absence of literal backslash-n separators, byte count and SHA-256.
- This modifies the aggregate source and a test included in the Q92 source-hash manifest. Therefore the prior 15 shard artifacts are not eligible for exact-head acceptance on the corrected source hash; a fresh exact-head walk-forward is required.

## Limitations and next action
No acceptance-complete Q92 report or persistent candidate/manifest was produced by run 42648067242. The paired evidence is preliminary log evidence only; the historical Blind OOS had prior SONAR exposure and is not prospective independent confirmation. Q89 remains the control and no motor promotion is justified.

Next: run exact-head full CI and the new compact-CSV synthetic regression; then run all 15 Q92 shards on the corrected source checkout; reconcile artifact digests; aggregate and run acceptance; only after validator success persist/read back the final report and assess the absolute uniform baseline separately. Keep PR #23 draft/open; do not merge or promote. PR #6/#7/#8 remain untouched.
