# Q92 result recovery — 2026-11-12

## Recovery source and persistence

The Q92 full walk-forward and fail-closed acceptance validator completed successfully in GitHub Actions run [42764304973](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42764304973), source checkout `449d2e9925a9d68385912025b9937c8b5e0851a2`.

The run failed only in its final append-only Git persistence shell step: an unterminated `<<'PY'` heredoc produced `syntax error: unexpected end of file`. The validator, bundle upload and uploaded-bundle byte readback had already passed. This is a persistence-script failure, not a model or statistical-validation failure.

Recovered and independently checked:
- Accepted bundle artifact ID: `13743351872`, 204,386,240 bytes.
- SHA-256 of downloaded ZIP: `2bc547a399b8017d3e93b34683662ecb3adb96002a26b2bd2835b48384856bc6`, matching the receipt and Actions log.
- Receipt artifact ID: `13742758649`; downloaded receipt ZIP SHA-256: `296b65322547e991895e2692a62ea0b5ac503982b252a99dd808caa8af5cb203`.
- All seven compact output hashes and byte lengths in the receipt were rechecked against files extracted from the accepted bundle.
- This recovery branch persists the paired inference, acceptance summary, receipt and this note. The full 15-shard metrics and target-ledger bundle remains in the Actions artifact (90-day retention); it is not duplicated as repository Git objects in this recovery commit.

## Source and experiment

- Canonical source archive: 3,402 draws through 2026-11-08; SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`; Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`.
- Strict-prior targets: 3,352; Discovery / Validation / historical Blind OOS: 2,012 / 670 / 670.
- Formula universe: 8,436,285 equal-weight 10-feature subsets over the 27 registered prior-only features.
- Metric rows: 25,308,855; global Holm family: 75,926,565 formula × split × endpoint tests.
- Holm-adjusted formula/split rows below 0.05: zero.
- Frozen Q92 candidate: `P10_01_08_11_12_14_15_16_18_19_23`.
- Same-archive Q89 control: `P9_06_09_12_14_15_17_18_19_23`.
- Candidate selection used Discovery then Validation only; Blind OOS was not used for selection.

## Blind OOS results

Paired comparison over 670 targets, circular moving-block bootstrap and block sign-flip, 20,000 replicates, block length 7; Holm across four paired endpoints:

| Endpoint (Q92 minus Q89) | Mean delta | 95% block CI | Holm p |
|---|---:|---:|---:|
| Top-5 hit share | -0.006269 | [-0.016716, 0.004179] | 0.619769 |
| Top-10 hit share | +0.003881 | [-0.008657, 0.016716] | 0.619769 |
| Top-20 hit share | -0.010149 | [-0.025075, 0.004776] | 0.619769 |
| Mean actual-number rank | +0.237015 | [-0.035231, 0.511940] | 0.374981 |

Decision: `NO_SIGNIFICANT_GAIN`. The primary Top-5 delta is negative and fails the preregistered +0.005 practical threshold, adjusted p-value and confidence-bound gates.

The selected Q92 candidate's Blind OOS Top-5 hit share was 0.111642 versus uniform expectation 0.125; absolute lift -0.013358, exact discrete-null raw p 0.994223 and global Holm-adjusted p 1.0. Above-uniform performance was not demonstrated.

## Limitations and next action

- This is historical exploratory evidence, not virgin prospective confirmation; prior SONAR research exposed the historical tail.
- The report JSON retains status `AGGREGATED_PENDING_ACCEPTANCE_VALIDATION` from the aggregation stage, while the separate acceptance summary, validator log and persistence receipt record `ACCEPTANCE_PASS`. This is a status-field mismatch to reconcile in a future replay; the acceptance validator itself passed.
- Human review and result-branch CI remain pending. No merge, engine promotion or shadow insertion is authorized.
- Next: keep Q92 as a valid negative result, fix the workflow's heredoc/persistence implementation in its own research branch before any rerun, and prioritize Q141's formula-family behaviour mapping rather than rerunning this expensive catalog.
