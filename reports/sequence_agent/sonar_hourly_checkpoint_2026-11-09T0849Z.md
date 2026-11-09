# VinciCasa SONAR — hourly checkpoint 2026-11-09 08:49 UTC

## Status
- Q89 refresh on the canonical 2026-11-08 archive: **accepted by automated gates, append-only persisted, exact-byte readback verified; pending human review/integration**.
- Q92: the ten-feature walk-forward runner, global Holm aggregator, acceptance replay and discrete-null calibration amendment are present in draft PR #23. **No Q92 historical shard has been executed.**
- No merge, engine promotion or shadow-stream insertion. PRs #6, #7 and #8 are untouched.

## Q89 refresh — verified archive, selection and Blind OOS replay
Canonical archive:
- 3,402 draws, 2017-07-17 through 2026-11-08.
- Git blob SHA-1: `77ca692a6082809fcc6c471501617433ec7c36cf`.
- SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Canonical main commit: `6cca9022d4311a3f9aba2925fce8c653dc6b63ab`.

Q89 run [42575002631](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42575002631) completed 15/15 delta shards and aggregate/acceptance/persistence. Persisted commit `95e6d7b24f0a92318741b9fdb82fb856becd5436`; verified checkpoint commit `3e8c108dd18a5c09afdd67ed377882998bc26739` records 22 files, 47,651,846 bytes, all exact-commit bytes verified. Report, manifest, selection and paired blind ledger were read back; their Git blob SHAs match the persisted checkpoint.

- Target count: 3,402; scored targets: 3,352.
- Split: Discovery 2,012 / Validation 670 / Blind OOS 670.
- Formula universe: 4,686,825 nine-feature equal-weight formulas.
- Global Holm family: 42,181,425; formula/split rows with Holm < 0.05: 0; minimum maximum-endpoint Holm p: 1.0.
- Candidate frozen before Blind OOS: `P9_06_09_12_14_15_17_18_19_23`.

Independent replay of the persisted 670-row Q89 selected-candidate Blind ledger against the canonical archive:
- Dates: 2025-01-08 through 2026-11-08.
- 670/670 target dates, prior cutoffs, prior-draw counts, actual quintets, candidate IDs, rank vectors, Top-5/10/20 hit counts and rank sums reconciled; **0 mismatches**.
- Recomputed metrics exactly match the report:
  - Top-5 hit-share 11.7910% vs uniform 12.5000% (−0.7090 pp).
  - Top-10 23.5821% vs 25.0000% (−1.4179 pp).
  - Top-20 49.5522% vs 50.0000% (−0.4478 pp).
  - Mean actual-number rank 20.6140 vs uniform 20.5000 (worse).
- This is not evidence of predictive advantage; Q89 remains pending human review.

## Q92-NULL-CALIBRATION-01 — quantitative audit independently reproduced
Preregistered Q92 family: `C(27,10)=8,436,285` formulas; three splits × three endpoints gives 75,926,565 tests. First Holm step threshold `0.05/m = 6.585310424618841e-10`.

The amendment replaces a continuity-corrected normal tail with deterministic float64 convolution of iid `Hypergeometric(40,k,5)` target hit counts. Independent Python reproduction matched the six audit tail/error rows:

| Targets | Top-k | Successes at audited tail | Exact discrete p | Normal approx p | Relative error |
|---:|---:|---:|---:|---:|---:|
| 670 | 5 | 532 | 7.934337625211848e-10 | 2.521639168956081e-10 | 68.2187% |
| 670 | 10 | 984 | 6.961001372301098e-10 | 3.8904433560122223e-10 | 44.1109% |
| 670 | 20 | 1841 | 7.652256487766228e-10 | 7.861991803748541e-10 | 2.7408% |
| 2012 | 5 | 1452 | 6.604344940475981e-10 | 3.3365639511792264e-10 | 49.4793% |
| 2012 | 10 | 2767 | 6.905462882407305e-10 | 4.896431780617303e-10 | 29.0934% |
| 2012 | 20 | 5318 | 7.10786876616995e-10 | 7.172620830304406e-10 | 0.91099% |

At N=670, Top-5 and 532 successes, the normal approximation falls below the first Holm threshold (0.3829×threshold), while the discrete p-value is above it (1.2049×threshold). Thus this audited point **flips the first-step rejection decision** under the approximation. This is a calibration finding, not a Q92 formula result or predictive-skill claim.

Independent checks also reproduced the expected summed-Hypergeometric means for target counts 7, 670 and 2,012 with k=5/10/20 (absolute error ≤ 2.3e-13), monotone upper tails, positive tail support and normalized PMFs. The repository checkpoint records 7/7 local synthetic regressions; the Q92-specific GitHub synthetic CI is still not observed as complete.

## Q92 code / CI state
PR #23 head: `17be52dca22fe5323a9b853509fc29216380820a`.
- Exact discrete-null module blob SHA: `c0aba34111a39d4d6473f35ace082e4f853b59f2`.
- Q92 aggregate-common blob SHA: `b7d54ba4125a9bdec9058f00ada2a7b0d902c76c`.
- Q92 aggregate helper test blob SHA: `f22f0440c7d53097888b0a2c13a188caa3f0d412`.
- Q92 null-calibration test blob SHA: `2a81149eda024ee6e45553931d1a25f06cccc9dc`.
- Aggregator and fail-closed acceptance validator are implemented and include global Holm replay, Discovery top-100 → Validation freeze, strict-prior target/ledger replay, Q89 same-archive control and paired Blind OOS inference.

Full project exact-head CI run [42580473098](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42580473098) is **IN PROGRESS**; Q80–Q86 exhaustive tests are currently running. This full CI does not itself demonstrate Q92-specific synthetic acceptance. PR #23 body still reports synthetic CI pending. No Q92 full shard run is present.

### Reproducibility audit gap to close before execution
The Q92 shard `source_code_sha256` manifest hashes the shard evaluator, Q92 common/null-calibration modules, feature-stack scripts, archive and preregistration. It does not explicitly hash the Q92 aggregator, acceptance validator or aggregate-common module. Exact-head CI pins their Git revision, but the persisted Q92 report/manifest should also record explicit SHA-256 values for these aggregation/acceptance sources before the expensive walk-forward begins.

## Next action
1. Complete and verify Q92-specific synthetic acceptance and exact-head full CI on the current PR #23 head.
2. Add explicit aggregation/validator source hashes to the Q92 report/manifest and replay tests; verify the new head.
3. Reconfirm Q89 same-archive report/manifest/selection/paired-ledger archive SHA and byte/SHA declarations.
4. Only then run the 15 Q92 shards (562,419 formulas each), aggregate the 25,308,855 formula×split rows, apply global Holm over 75,926,565 tests, freeze Discovery→Validation, compute paired Blind OOS inference and pass acceptance/readback.
5. Keep human review mandatory; do not merge or promote.

Checkpoint is research-only.