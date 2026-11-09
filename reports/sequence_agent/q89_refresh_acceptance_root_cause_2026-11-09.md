# SONAR Q89 refresh acceptance root cause — 2026-11-09

## Source run
- Q89 refresh workflow run: [42563200087](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42563200087).
- Head used by the run: `ec48cb87cf9efd4796ae72a7a1d5e08f076c4038`.
- Canonical archive: 3,402 draws through 2026-11-08; Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`; SHA-256 `3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed`.
- All 15 delta shards completed; aggregation completed; acceptance failed; persistence and exact-head CI were correctly skipped.

## Verified root causes
1. The acceptance validator used two `csv.DictReader` instances over the same open file for each CSV: the first read `fieldnames` (consuming the header), then the second treated the first data row as its header. Acceptance logs measured 669 paired-ledger rows with empty `target_date`, and schema/count failures for the 3-row target-delta ledger and 100-row shortlist (each lost its first data row). This explains the observed 684 validation errors and the misleading 669 “target missing/too early” messages. It was a validator I/O defect, not a strict-prefix ranking discrepancy.
2. The aggregate report wrote `metrics_rows=TOTAL` (4,686,825) while its acceptance contract correctly expects the full formula×split ledger dimension `TOTAL*3=14,060,475`. The delta manifest intentionally retains `metrics_rows=TOTAL`, because each shard row contains all three target-offset deltas in columns.

## Corrective changes persisted and read back
- `scripts/validate_q89_refresh_delta.py`: added `read_csv_fields_rows`, materializing fields and rows from one DictReader; all three acceptance CSVs now use it.
- `scripts/aggregate_sonar_q89_refresh_delta.py`: report `metrics_rows` corrected to `TOTAL*3`; manifest dimensions unchanged.
- `tests/test_sonar_q89_refresh_acceptance_io.py`: synthetic three-row CSV regression confirms header preservation and no dropped row.
- `.github/workflows/sonar-q89-refresh-delta.yml`: compiles and runs the regression test with the existing Q89 tests.
- Exact blob readback checks passed for all four changed files.

## Quantitative protocol / guardrails
- Q89 refresh remains 4,686,825 nine-feature formulas; 3,352 strict-prefix targets; Discovery/Validation/Blind OOS = 2,012/670/670; global Holm family = 42,181,425 formula×split×endpoint tests.
- The refresh uses only three preregistered split-transition/new-target deltas (offsets 2011, 2681, 3351) against the accepted 2026-11-07 Q89 base. All outcomes are additive metric deltas; each target feature state uses its strict historical prefix.
- Q92 hypothesis remains preregistered: enumerate all C(27,10)=8,436,285 equal-weight ten-feature formulas and compare a Validation-frozen Q92 candidate paired on Blind OOS against the refreshed Q89 candidate selected with the same Discovery→Validation rule. Q92 is not dispatched until Q89 acceptance, append-only persistence/readback and exact-head CI pass.
- Holm correction remains global within the Q89 refresh catalog; the normal-approximation hypergeometric p-values are exploratory. Blind OOS is historical and not independent prospective confirmation.

## Recovery status at checkpoint
- Fixes are persisted; the regression has been added to the workflow, but the new workflow run has not yet executed.
- Next action: rerun Q89 refresh on the exact archive/head, require all 15 shards, aggregate, acceptance, append-only persistence, byte readback and current-head CI; then proceed to Q92 only if every gate passes.
- No PR merge, engine promotion, shadow insertion, or modification/merge of PR #6, #7, or #8.
