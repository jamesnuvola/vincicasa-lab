# CI failure root-cause — P5 order-statistic prior audit

- Failed workflow: 42470276615 (base checkpoint run) and again on PSR-03 branch workflow 42470653348 at the PSR-03 byte-reproducibility guard before the P5 step was reached.
- The P5 audit's train-date regex was double-escaped in a regex literal: it matched literal backslash+d instead of date digits. The report contains ordinary YYYY-MM-DD text, so the train window could not be parsed.
- Correction in scripts/sonar_p5_orderstat_prior_audit.mjs: use the same single-escaped digit/date regex as the test-window parser. This is a parsing-only correction; it does not alter the P5 ranker or its metrics.
- PSR-03 CI run executed PSR-01, PSR-02 and PSR-03 successfully; its exact-output diff failed because the committed Code Mode report omitted position labels in position_bins and unrounded cross-runtime log-loss doubles differed at ~1e-16. The target ledger also used full-precision values, so its FNV fingerprint varied across runtimes.
- PSR-03 correction: include explicit P1–P5 labels, round report numbers to 12 decimals, compact the selected-target ledger to 48 columns and format score deltas to six decimals. The CI diff guard remains enabled.
- Status: fixes persisted in this branch; CI rerun required to verify both the reproducibility guard and the P5 audit step.
