# Q60 H102 — current checkpoint (2026-11-10 13:44 Europe/Rome)

## Recovered state
- Canonical archive on the H101 branch ends at 2026-11-09 (3,403 rows from 2017-07-17 through 2026-11-09).
- Q60 main gate is 22/200 complete paired global/positional targets; 178 remain. Promotion is false.
- H101 is a separate 200-target RRF prospective cohort with 100/50/50 chronological reporting splits.
- H101 target 2026-11-10 is frozen at 12:49:51 Europe/Rome from parent freezes at 10:53:16 and 10:55:31, both using cutoff 2026-11-09. Its Top20 is unchanged and remains FROZEN_PENDING.
- No 2026-11-10 outcome exists in the canonical archive at registration time; no result has been read or inferred.

## Verified CI and Q92 recovery
- H101 exact-head repository CI run 42811595218: success; its H101 freeze regeneration and byte-for-byte comparison step passed.
- Q92 full run 42777967290: 15/15 shards, aggregation and fail-closed acceptance passed, artifact bundle uploaded and byte-readback verified. The original final Git-tree/blob readback step failed because it used the wrong branch reference.
- Later main CI run 42811500657 executed the corrected read-only Q92 result-branch check: 8 result outputs plus receipt verified; status PASS_WITH_METADATA_WARNING.
- Q92 metadata remains deliberately unrevised: report/manifest say AGGREGATED_PENDING_ACCEPTANCE_VALIDATION, summary says ACCEPTANCE_PASS_PENDING_ARTIFACT_PERSISTENCE, receipt says artifact persisted pending result-branch CI/human review. Preserve this discrepancy for human review; do not rewrite accepted outputs.
- Q92 predictive conclusion remains NO_SIGNIFICANT_GAIN; historical blind OOS is not prospective confirmation.

## H102 hypothesis
When the two parent Top20 lists disagree more, fixed H101 RRF may gain more Top20 hits relative to the global parent.

For target t:
- d_t = 20 - |G_t intersect P_t| (available before the target).
- y_t = hits(H101_RRF_t) - hits(freq_100_t) (scored only after canonical outcome publication).
- Primary estimand beta5 = 5 * Cov(d,y) / Var(d), in Top20 hits per target per five additional disagreement slots.
- Practical threshold: beta5 >= +0.10.

The complete 200-target cohort is reported chronologically as Discovery 100, Validation 50, Blind OOS 50. No interim inferential looks or retuning. Final inference uses one block-permutation slope test and a circular block-20 bootstrap CI; three H101 endpoints plus H102 slope are corrected together with Holm. The blind 50 slope is a directional consistency check, not a separately tested p-value.

## Current execution status
- H102 evaluator, protocol, tests, current status report, empty append-only ledger and workflow are committed on this stacked research branch.
- Current canonical evidence yields 0 scored H101 outcomes and one pending target (2026-11-10). Therefore no Discovery, Validation or Blind OOS outcome metrics and no inferential test have been run.
- The workflow must pass exact source regeneration and byte-for-byte status/ledger comparison before the branch is considered validated.

## Next action
Wait for the official 2026-11-10 outcome to enter the canonical archive. Score only the existing frozen row; never reconstruct it. Continue the H101 cohort unchanged to 200 complete targets, then run the final preregistered analysis.


## Hourly repository audit — 2026-11-10 14:38 Europe/Rome

### Source and freeze replay
- Re-read the canonical archive, global shadow, positional shadow, H101 shadow, H102 protocol/status/ledger from GitHub.
- Blob SHAs at this audit still match the preregistered H102 source SHAs:
  - H101 protocol: `b3e9f38537f15dbd8a465a97d4450bed77c657f7`
  - H101 shadow: `ced52ac9fd1850f3812c553ab83d7bd8e27dc3f6`
  - global shadow: `afe538cb835dbe561983eaa6972899ce8bd97df7`
  - positional shadow: `e63f35394e916ca7688fc7b41457c1032b9b7be0`
  - canonical archive: `8d3e19f0b417024ba32e576697eac0648d12ab86`
  - Q60 gate: `bce911528ccecb93d2efaccbf76c45cd22c07ae7`
- Independently recomputed H101 from the frozen parent lists using `1/(20+rank_global) + 1/(20+rank_positional)`, absent rank = 0, descending score then ascending number. The generated Top20 matches the stored H101 Top20 exactly.
- For target 2026-11-10: parent Top20 overlap = 17; disagreement slots `d_t=3`. This is a prior-only predictor, not a scored outcome.
- Canonical archive contains 3,403 draws through 2026-11-09. The official-facing archive page still lists contest 313 dated 2026-11-09 as latest at this audit; the 2026-11-10 draw is scheduled for 20:00 and is not yet available at 14:38. Do not score the pending freeze before canonical publication.
- H102 ledger remains header-only (zero scored rows); status remains 0/200 complete, one pending (2026-11-10), `inference_executed=false`.

### CI verification
- H102 dedicated run 42819781596: SUCCESS; compile, test, source regeneration and exact pending-status/empty-ledger comparison all passed.
- H102 general repository CI run 42819781643: SUCCESS; archive audit, Q60 gate/H101 freeze checks, labs and web build passed.
- H102 dedicated rerun 42820246332: SUCCESS; all steps passed again.
- General repository CI rerun 42820252564: SUCCESS; all steps passed.
- These runs validate the current H102 implementation and empty-state replay only. They do not represent a 200-target predictive experiment or any Discovery/Validation/Blind OOS result.

### Statistical limitation to retain for human review
- The preregistered primary permutation test reorders ten contiguous response blocks of length 20 while holding the disagreement predictor fixed. This preserves within-block response order but assumes exchangeability of those 20-target blocks under the null; strong nonstationarity or regime changes could invalidate that assumption. Keep the registered analysis unchanged unless a timestamped amendment is made before any target outcomes are scored. The paired circular block bootstrap resamples predictor/response pairs and has a different dependence assumption.
- Any final slope is associational, not causal. The final 50-target blind split is a directional consistency check only, as preregistered.

### Deferred quantitative candidate H103 — not registered, not implemented, not tested
- Candidate predictor: rank-weighted disagreement intensity
  `w_t = sum_{n in G_t \\ P_t} 1/(20+r_G(n)) + sum_{n in P_t \\ G_t} 1/(20+r_P(n))`.
- Candidate response remains `y_t = hits(H101_RRF_t)-hits(freq_100_t)`; candidate estimand is the OLS slope of y on w.
- Rationale: distinguish the number of disagreement slots (H102) from whether exclusive candidates occur high or low in their parent rankings.
- Do not add this endpoint to the active H102 cohort or inspect it against H102 outcomes. If pursued, register it before outcomes in a separate future cohort and define its own multiplicity family. H102 remains the sole active confirmatory mechanism test.

### Next action
Wait for the official 2026-11-10 result to enter the canonical archive. Append-only score the existing H101 freeze and rerun the exact H102 source-rebuild/readback workflow. Continue the fixed 200-target cohort with no interim inferential looks or retuning.
