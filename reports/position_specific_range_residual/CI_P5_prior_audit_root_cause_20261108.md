# CI failure root-cause — P5 order-statistic prior audit

- Failed workflow: 42470276615 (base checkpoint run) and 42470653348 (PSR-03 branch run). The first failed at the P5 audit parser; the second failed earlier at PSR-03 report reproducibility, so P5 was skipped.
- The P5 audit's train-date regex was double-escaped in a regex literal: it matched literal backslash+d instead of date digits. The report contains ordinary YYYY-MM-DD text, so the train window could not be parsed.
- Correction in scripts/sonar_p5_orderstat_prior_audit.mjs: use the same single-escaped digit/date regex as the test-window parser. This is a parsing-only correction; it does not alter the P5 ranker or its metrics. The corrected regex was locally checked against the report's 2017-09-05 through 2024-12-31 training window.
- PSR-03 itself executed successfully in both CI runs. The first reproducibility diff identified omitted position labels in position_bins and last-bit cross-runtime log-loss float differences (~1e-16); the second diff confirmed the JSON and compact target ledger now match, but Markdown differed in trailing whitespace, the comma in “2,000”, and a terminal blank line.
- PSR-03 corrections: explicit P1–P5 labels, recursive 12-decimal report normalization, 48-column selected-target ledger with six-decimal score deltas, and Markdown formatting aligned with the Node renderer. The byte-for-byte CI diff guard remains enabled.
- Status: code and persisted outputs read back exactly; CI rerun is pending to verify the reproducibility guard and P5 audit step.
