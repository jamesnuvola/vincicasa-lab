# Q92 selected-candidate split audit and recovery checkpoint
Date: 2026-11-09 17:50 UTC

## Provenance
- Q92 source run: [42648067242](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42648067242), source checkout `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`.
- Shard artifact: `q92-20261108-shard-9-attempt-1`, GitHub artifact ID `13691173789`.
- Artifact ZIP SHA-256 independently computed and matched the GitHub artifact digest: `983644c4743218940f884f0c7214051b3a6a0c425ad9059d260c25d0f5575716`.
- Internal shard report/manifest: source checkout `8f7ac10b1edc7272e8463e61a89fdce8bb80da5c`; canonical archive SHA-256 `5bc4c105c4c34c325eefbbc3441a03c30b732fbe47e5d36b224e9dbcdf10ac1b`; shard 9; 1,687,257 metric rows; 3,352 scored targets; status `SHARD_COMPLETE_NOT_TASK_COMPLETE`.
- Selected Q92 formula: `P10_01_08_11_12_14_15_16_18_19_23`.
- Independently computed combinadic rank: 5,107,361 (zero-based); shard 9; local formula rank 45,590 (zero-based). A streaming scan of the raw shard CSV confirmed the formula ID at the expected row in Discovery, Validation and Blind OOS.

## Selected formula metrics by split
Metrics are hit-share averages over actual winning numbers (uniform expected baselines: Top-5 0.125, Top-10 0.25, Top-20 0.5; mean actual-number rank 20.5).

| Split | Targets | Top-5 share | Top-10 share | Top-20 share | Mean rank | Exact raw p Top-5 | Exact raw p Top-10 | Exact raw p Top-20 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Discovery | 2,012 | 0.1371769384 | 0.2620278330 | 0.5096421471 | 20.2543737575 | 0.0000614801 | 0.0017671326 | 0.0211137588 |
| Validation | 670 | 0.1298507463 | 0.2543283582 | 0.5023880597 | 20.3480597015 | 0.1921720689 | 0.2771029911 | 0.3922081548 |
| Blind OOS | 670 | 0.1116417910 | 0.2397014925 | 0.4853731343 | 20.8510447761 | 0.9942228959 | 0.9302320254 | 0.9645147292 |

All-five rates for selected formula:
- Discovery: Top-5 0; Top-10 0.0009940358; Top-20 0.0273359841.
- Validation: Top-5 0; Top-10 0; Top-20 0.0268656716.
- Blind OOS: Top-5 0; Top-10 0; Top-20 0.0208955224.

The artifact raw metric row field `holm_p_max_endpoint_family` is 1.0 on the three selected rows. Do not substitute this shard-row field for the globally replayed adjusted-p vector or the acceptance validator's global candidate evidence.

## Measured interpretation
- Discovery Top-5 share was 13.7177%, above the uniform 12.5% baseline, but this was the result of selection across a large retrospective catalog and does not stand alone as evidence.
- Validation Top-5 share was 12.9851%, only 0.4851 percentage points above uniform; the exact raw upper-tail p-value was 0.1922.
- Blind OOS Top-5 share fell to 11.1642%, 1.3358 percentage points below uniform; exact raw upper-tail p-value 0.9942. Top-10, Top-20 and mean rank also underperformed their uniform expectations.
- Aggregator log from run 42648067242 separately reports the paired Q92-minus-Q89 Top-5 delta -0.0062686567 on 670 targets, 95% circular block bootstrap CI [-0.0167164179, 0.0041791045], sign-flip p raw 0.26873656, Holm p 0.61976901. The Q89 Top-5 share implied by this delta is 0.1179104478 (11.7910%).
- Global Holm summary from the aggregation log: family size 75,926,565; 0 formula/split rows below adjusted 0.05; raw and adjusted vector hashes recorded in the companion aggregation checkpoint.
- Aggregate primary decision: `NO_SIGNIFICANT_GAIN`. The candidate does not clear the preregistered +0.005 practical Top-5 paired effect and does not show absolute above-uniform Blind OOS value.

## Aggregation acceptance root cause
The aggregator produced a full preliminary summary but the acceptance validator failed:
`Q92_ACCEPTANCE_BLOCKED: Q92 compact metric part exact schema mismatch shard 0`.

Source inspection located the defect in compact gzip CSV generation: CSV writer line terminator was the literal two-character backslash+n, not a real LF. A local Python reproducer showed the compressed decompressed stream became one concatenated record and the DictReader header bled into adjacent fields. The raw shard artifact reconciliation had passed; this is a post-aggregation serialization/acceptance defect.

A recovery commit has been pushed to PR #23:
- Commit `593f259a99ac5cf95dc599e32cbc62ee4f15d15a`.
- Extracted helper `compact_metrics_part`, canonical LF output, deterministic gzip.
- Added synthetic regression checking the exact seven-column header, six rows across three splits, seven LF bytes, no literal backslash+n separators, size and SHA-256.
- Checkpoint source report: `q92_20261108_aggregate_schema_recovery_checkpoint_2026-11-09T1743Z.md`.

Exact-head validation status (verified 2026-11-09 17:49:45 UTC):
- Full project CI on PR #23 exact head `593f259a99ac5cf95dc599e32cbc62ee4f15d15a`: [run 42668028762](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668028762) — **SUCCESS**.
- Q92 runner synthetic acceptance: [run 42668016881](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668016881) — **SUCCESS**.
- Q92 aggregate/Holm/paired-inference synthetic acceptance: [run 42668016909](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668016909) — **SUCCESS**, including the new compact-CSV regression.
- Duplicate push-triggered full CI [run 42668016920](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668016920) — CANCELLED; the exact-head PR CI above completed successfully.
- Fresh exact-source Q92 walk-forward: [run 42668016985](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42668016985) — preflight **SUCCESS**; shards 0, 1, 2, 3 and 4 are **IN PROGRESS**; shards 5–14 are **QUEUED**. Aggregation has not started.

Because aggregator/test sources are in the registered source-hash manifest, the 15 artifacts from checkout `8f7ac10b` are not eligible for exact-head acceptance on `593f259a`; the fresh 15-shard run is the reproducibility path.

## New quantitative hypothesis Q93 (proposal only; not preregistered)
Catalog: `C(27,11)=13,037,895` equal-weight eleven-feature formulas.
Historical Discovery/Validation remain selection-only. Freeze one candidate before any future target.

Primary prospective hypothesis on a new 670-target holdout:
- Uniform Top-5 hit-share null: 0.125.
- Minimum practical alternative: Top-5 share \(\ge 0.130\) (absolute lift \(\ge 0.005\)).
- Gate: one-sided exact discrete null p-value, Holm-adjusted across the four preregistered endpoints <0.05; circular moving-block bootstrap 95% CI lower bound >0 for the primary lift.
- Secondary paired comparisons Q93 vs frozen Q89 and Q92: four endpoints each, Holm over the eight comparison-endpoint tests; block length 7 and fixed seeds to be registered.
- Do not use the historical Q92 Blind OOS for Q93 selection or confirmation. Do not start Q93 before Q92 acceptance and human review.

This is a proposal, not a claim that Q93 is predictive or an instruction to promote it.

## Limits and next action
The selected formula split metrics were independently extracted from a digest-verified artifact, but Q92 as a task remains `PENDING_ACCEPTANCE_VALIDATION`. No globally accepted report, candidate freeze approval, model promotion or prospective confirmation exists. The historical Blind OOS has previous SONAR exposure.

Next: complete exact-head CI and synthetic regression; allow the fresh 15-shard run to complete; verify artifact digests; aggregate and run the exact acceptance replay; persist final report/manifest/shortlist/paired ledger with byte readback; then human review. PR #23 remains draft/open. PR #6, #7 and #8 remain untouched and unmerged.
