# VinciCasa SONAR — Q92 tuple-guard recovery checkpoint

Recorded: 2026-11-09 after source commit `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.

## Verified persisted baseline

- Canonical archive: 3,402 draws through 2026-11-08; Git blob SHA-1 `77ca692a6082809fcc6c471501617433ec7c36cf`; archive SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Q89 refresh report/manifest are `VALIDATED_PENDING_HUMAN_REVIEW`, same archive and split 2,012/670/670.
- Frozen Q89 candidate `P9_06_09_12_14_15_17_18_19_23`: Blind Top-5 11.7910% vs uniform 12.5000%; Top-10 23.5821% vs 25.0000%; Top-20 49.5522% vs 50.0000%; mean actual-number rank 20.6140 vs uniform 20.5. No formula/split Holm row <0.05. Conclusion: no verified predictive gain; no promotion.

## Q92 registered study

- `C(27,10)=8,436,285` equal-weight prior-only formulas; 15 contiguous immutable shards × 562,419 formulas.
- 3,352 strict-prior targets; Discovery 2,012 / Validation 670 / Blind OOS 670; 25,308,855 formula×split metric rows; global catalog Holm family 75,926,565.
- Candidate selection: Discovery top-100 then Validation freeze. Blind OOS cannot select.
- Primary paired Blind OOS endpoint Q92 minus same-archive Q89 Top-5. Registered decision gate: mean lift ≥0.005 absolute; circular moving-block bootstrap 20,000 replicates, block length 7, 95% lower bound >0; block sign-flip 20,000 replicates and Holm-adjusted p<0.05 over four endpoints (Top-5/10/20/mean rank).
- Discrete Hypergeometric convolution replaced the normal approximation before execution after the calibration audit showed relative tail errors as large as 68.2187% near the first Holm threshold. This calibration is under an iid uniform 5-of-40 null and is not predictive evidence.

## Root cause and correction

- Q92 full walk-forward run [42612668612](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42612668612) passed its exact-head full CI wait, then preflight failed with `Q92_PREFLIGHT_BLOCKED: canonical final quintet mismatch`.
- Archive readback shows the final row is `2026-11-08,3,7,10,16,27`. The canonical Q80 loader stores each draw as a sorted tuple, but the workflow compared `draws[-1]` to a list `[3,7,10,16,27]`. Values matched; Python container types did not.
- Fixed the guard to compare against tuple `(3,7,10,16,27)`.
- Added regression `test_canonical_archive_last_draw_matches_registered_quintet` to check archive count/date and the tuple returned by the loader.
- Source commit: `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.
- Workflow blob SHA readback: `9c3b390161849b36c08995ea031bbe46e6296444`.
- Test blob SHA readback: `13728b02365b6427ca338e5e5ac2e23426067aec`.
- Git commit and branch ref were read back after update; no merge performed.

## Live gates at checkpoint

- Exact-head PR CI run [42615360700](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615360700): IN PROGRESS.
- Push-triggered full CI run [42615347344](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347344): CANCELLED by branch concurrency; PR event run is the exact-head CI candidate.
- Q92 artifact-backed run [42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368): IN PROGRESS in preflight; no historical shard was observed started at checkpoint time.
- Q92 runner synthetic acceptance [42615347316](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347316): IN PROGRESS.
- Earlier runner/aggregate synthetic acceptance on prior heads passed, but those are not historical Q92 outputs.
- PR #23 remains draft/open. PR #6/#7/#8 remain open/unmerged and untouched.

## Next action and recovery

1. Observe exact-head CI and the tuple regression result.
2. Re-read Q92 preflight logs; require archive SHA/dimensions, tuple/date, same-archive Q89 freeze and 670-row strict-prior ledger, preregistered batch evidence, and all synthetic regressions to pass.
3. Only then allow 15 immutable shards; preserve artifacts and rerun failed shards only.
4. Aggregate all formula×split metrics, apply the registered global Holm family, freeze Discovery→Validation selection, and compute paired Blind OOS inference.
5. Validate acceptance, append-only persistence, artifact digest and Git blob readback byte-for-byte. Human review remains mandatory.

## Next quantitative hypothesis (exploratory, not preregistered)

After Q92 is fully accepted and reviewed, a possible Q93 study would enumerate `C(27,11)=13,037,895` equal-weight 11-feature formulas. Selection remains Discovery top-100 → Validation freeze. Its confirmatory comparison must use a new prospective 670-target holdout after the 2026-11-08 cutoff, not reuse Q92 historical Blind OOS. Proposed gate: paired Top-5 lift ≥0.005, bootstrap 95% lower bound >0, and Holm-adjusted sign-flip p<0.05 across Top-5/10/20/mean-rank. Q93 is not preregistered, implemented, or executed; do not start it before Q92 completion/review.

## Guardrails

No automatic merge, engine promotion, shadow insertion, or modification/merge of PR #6, #7, or #8.
