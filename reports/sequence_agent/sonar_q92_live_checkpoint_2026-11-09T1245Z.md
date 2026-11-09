# VinciCasa SONAR — Q92 live progress and CI root-cause checkpoint
Captured: 2026-11-09T12:45Z

## Q92 immutable experiment identity

- Source commit: `45aab4d40c90d2cee976f6fad89156bdf0b6a089`.
- Canonical archive: 3,402 draws, 2017-07-17 through 2026-11-08.
- Archive SHA-256: `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.
- Formula universe: `C(27,10)=8,436,285`; 15 contiguous shards × 562,419 formulas.
- Walk-forward targets: 3,352; Discovery 2,012 / Validation 670 / Blind OOS 670.
- Expected formula×split metrics: 25,308,855; global catalog Holm family: 75,926,565 tests.

## Q92 run state at capture

Run [42615347368](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42615347368):
- Preflight SUCCESS, 11/11 steps.
- Six shards complete: 0, 1, 2, 3, 4, 7 (40% of formula ranks).
- Five shards in progress: 5, 6, 8, 9, 10.
- Four shards queued: 11, 12, 13, 14.
- Artifact list still contains exactly the six completed shard uploads. No global aggregation or candidate freeze has started.

Completed shards each report 1,687,257 formula×split rows and 3,352 target-ledger rows, giving 10,123,542 completed metric rows total. All six artifact ZIP SHA-256 values were independently checked after download and matched the GitHub upload-log digests. Artifact manifests match source checkout `45aab4d...` and archive SHA `5bc4...`.

The common target-ledger fields across the six artifacts are byte-independent but value-identical: target date, cutoff date, prior draw count, actual quintet and status. Each has 3,352 unique ascending dates; first target 2017-09-05 / cutoff 2017-09-04 / 50 prior draws; final target 2026-11-08 / cutoff 2026-11-07 / 3,401 prior draws. Source inspection of Q81 confirms feature matrix construction at index `i` uses `prefix[i]` (strict `draws[:i]`) and updates occurrence/pair/gap state only after scoring. This is a partial leakage/reproducibility audit, not the full Q92 acceptance replay.

## New CI failure — root cause verified

Checkpoint-only commit `f86176ef108596eb7a416e1cd6f6f955e961cdf7` used the `[q80-validate-persisted]` CI marker. Its run [42619429392](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42619429392) failed at the step “Validate persisted Q80/Q81/Q82/Q83/Q86 outputs on exact head”; all earlier archive audit, generated-data audit, prospective-gate and syntax steps passed.

The validator rejected the persisted Q80–Q86 evidence because it is stale relative to the newer canonical archive:
- Q80–Q86 reports were produced for 3,401 draws ending 2026-11-07, with 3,351 scored targets and split counts 2,011/670/670.
- Their recorded archive SHA-256 (Q81/Q82/Q83/Q86) is `3bcffb4757febbdf153ed3aa5ce278a77c241dce73294577100bf1a0de197fed`.
- Current canonical archive has 3,402 draws ending 2026-11-08, 3,352 scored targets and split counts 2,012/670/670, SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`.

The log enumerates count/date/split/archive-SHA/ledger-coverage mismatches across Q80, Q81, Q82, Q83 and Q86. **Root cause: stale prior-cutoff Q80–Q86 artifacts were asked to validate against the refreshed canonical archive; this is not a Q92 shard failure and does not invalidate Q92 exact-head CI or its successful preflight.** The Q80–Q86 outputs require their own archive refresh/revalidation before that marker can pass. No refresh was performed in this cycle.

The report-only checkpoint commit uses `[q80-reuse-artifact]` to skip the unrelated Q80 validation job; this is an explicit CI skip, not a CI pass. Repository readback is still verified.

## Q89 same-archive control — recovered from repository

Q89 report and selection are `VALIDATED_PENDING_HUMAN_REVIEW` / `CANDIDATE_FROZEN_BEFORE_BLIND_OOS` on the same archive SHA. Candidate: `P9_06_09_12_14_15_17_18_19_23`. Blind Top-5 hit share 0.1179104478 (11.7910%) vs uniform 0.125 (12.5000%); Top-10 23.5821%, Top-20 49.5522%, mean actual-number rank 20.6140. No formula/split row passed its 42,181,425-test Holm family. Q89 used a continuity-corrected normal null approximation labelled exploratory; Q92 preregistered the discrete hypergeometric convolution amendment. No predictive advantage is established by Q89.

## Next quantitative hypothesis — proposal only

After Q92 acceptance and human review, propose Q93 with `C(27,11)=13,037,895` equal-weight 11-feature formulas. Select Discovery top-100 → Validation freeze; never use Blind OOS for selection. Compare frozen Q93 vs Q92 on a new prospective 670-target holdout after 2026-11-08. Proposed gate: paired Top-5 lift ≥0.005 absolute, 95% circular block-bootstrap lower bound >0, and Holm-adjusted block sign-flip p<0.05 across Top-5/10/20 and mean-rank endpoints. This is not preregistered, implemented or executed.

## Next actions

1. Continue monitoring Q92 shards; retain immutable artifact receipts and retry only failed shards.
2. After all 15 complete, aggregate/replay all 25,308,855 metrics, global Holm, Discovery top-100 → Validation freeze, and paired Blind OOS inference against same-archive Q89.
3. Verify append-only persistence, artifact/result SHA receipts, exact Git blob/tree readback and result-branch CI before human review.
4. Separately refresh Q80–Q86 outputs against the 2026-11-08 canonical archive only if that work is explicitly resumed; do not treat stale artifacts as accepted.

PR #23 remains draft/open. PR #6, #7 and #8 remain open/unmerged and untouched. No merge, engine promotion or shadow insertion.
