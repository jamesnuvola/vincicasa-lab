# CI failure root-cause — P5 order-statistic prior audit

## Resolved parser and PSR-03 reproducibility issues

- Workflow 42470276615 failed because the P5 audit train-date regex was double-escaped in a regex literal; it matched literal backslash+d instead of date digits. Corrected to the same single-escaped date regex as the test-window parser.
- Workflow 42470653348 executed PSR-01, PSR-02 and PSR-03, but the PSR-03 byte-diff guard found missing P1–P5 labels and cross-runtime float/ledger formatting differences. Workflow 42471192018 confirmed the JSON and compact ledger matched after normalization; Markdown still differed in trailing whitespace, thousands separator, and terminal blank line. Those renderer details were aligned.
- Workflow 42471485090 completed successfully: all preceding lab checks, PSR-01, PSR-02, PSR-03, the PSR-03 byte-for-byte reproducibility guard, P5 audit step, artifact uploads and application build passed.

## P5 audit artifact inspection and correction

- The successful P5 artifact confirmed the exact order-statistic baseline: pooled 2025-01-01–2026-11-04 (N=673), logistic Top5 42.7935% vs exact prior-ranked Top5 52.0059% on the same dates (−9.2125 pp); Top1 10.4012% vs 12.3328% (−1.9316 pp); mean rank 8.751857 vs 7.062407 (+1.689450, lower is better). Paired inference remains unavailable because the ranker report has aggregate-only metrics.
- A code audit of that artifact found a reporting defect: empirical_frequency_prior_baseline.top10_hit_rate was written as raw hits (516) rather than rate (516/673 = 0.7667161961). The exact-prior top10 rate field is already a rate.
- Corrected scripts/sonar_p5_orderstat_prior_audit.mjs to divide the empirical Top10 count by test.length. This changes only the reported metric scale, not ranker training or rankings.
- Status: the parser and PSR-03 output reproduction are CI-verified; the Top10 metric correction is persisted and awaits a fresh CI run and artifact readback.
