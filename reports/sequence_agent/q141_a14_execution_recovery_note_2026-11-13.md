# Q141-A14 execution recovery note — 13 November 2026

The first dedicated workflow run, [43505419192](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43505419192), completed unit tests and the full strict-prior walk-forward successfully, but failed at the deterministic replay comparison.

Root cause: the workflow compared the entire shared `reports/sequence_agent` directory with a temporary directory containing only Q141-A14 outputs. Unrelated existing reports made `diff -ru` fail; the experiment outputs themselves were not shown to differ.

Correction: compare each generated `q141_a14_*` file byte-for-byte with its committed counterpart using `cmp`, leaving unrelated report files outside the comparison.

Recovery state: code and tests passed in the failed run; deterministic parity, output persistence, remote readback and exact-head CI must be re-run after this workflow correction. No engine, archive, freeze, Q60 gate or protected PR #6/#7/#8 was modified.
