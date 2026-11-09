# SONAR state reconciliation — Q84 already executed; Q92 recovery active

Captured: 2026-11-09 19:55 UTC

This addendum supersedes the earlier checkpoint's statement that Q84 was only a future task. The repository already contained a completed Q84 flow-state experiment; this was discovered during the current recovery cycle.

## Q84 original flow-state atlas — verified

Branch: `research/q84-flow-state-atlas-20261109`  
Execution source commit: `33c7de6fd4395b06ca9ffcd33f3662a25282c921`  
Persisted output head: `73059c3fbcb3821ceefd10a1b323fbeb4fd1e577`

- Full walk-forward run 42683512306: SUCCESS.
- Exact persisted-head validation run 42683964783: SUCCESS; the execution step was skipped because the persisted outputs already existed, and the exact-head validation/replay passed.
- 3,402 canonical draws through 2026-11-08; 3,202 eligible targets; Discovery/Validation/Blind OOS = 1,921/640/641.
- 129 atlas entries: 42 fixed strategies, 2 ensembles, 84 conditional strategies and 1 retrospective oracle.
- Global family: 1,152 strategy × split × endpoint tests; zero Holm-adjusted results below 0.05.
- Validation status: `EXPLORATORY_NOT_PROMOTABLE`; no model promotion.

The original dynamic ensemble `ENSEMBLE::FLOW_STATE_ADAPTIVE` used a 13-feature causal state, 250-target analogue lookback, K=50, shrinkage 30 and temperature 0.35. Blind OOS mean hits were Top-5 0.5913 (uniform 0.625), Top-10 1.2621 (uniform 1.25), Top-20 2.5304 (uniform 2.5), mean actual rank 20.4933 (uniform 20.5). Its Top-5 result was below the uniform baseline and no Holm-adjusted test was significant.

The state kernel was diffuse: mean effective analogue count 48.72/50, mean weight CV 0.223. This motivated the K sensitivity below.

## Q84 K-neighborhood sensitivity — verified and persisted

Branch: `research/q84-flow-state-k-sensitivity-20261109`  
Code source commit: `9e9b70b023050d3d4826a66609237a6f63bd6fed`  
Persisted output head: `597dd203369cc88462ef8a61a335593fc5275684`

- Workflow run 42687283584: SUCCESS, including regression tests, full walk-forward, fail-closed validator, append-only persistence and Git-object byte readback.
- Full project CI run 42687283494: SUCCESS on source-code commit `9e9b70b...`. It ran before the output-only persistence commit; the persistence workflow itself verified exact bytes after the commit.
- Acceptance validation: PASS.
- 3,202 targets and 3,202 strict prior cutoffs.
- 16,010 complete 40-number rank vectors reconciled (five methods × 3,202 targets).
- Global Holm family: 36 tests; zero adjusted p-values below 0.05.
- K=50 reproduction matched the parent Q84 equal-weight, flow-state and fixed-comparator metrics within 1e-12.

### Measured sensitivity result

K was selected on Discovery only by Top-20 mean hits; the selected value remained **K=50**. K=10 and K=20 did not beat it on the registered Discovery selection criterion.

Blind OOS:

| Method | Mean Top-5 hits | Mean Top-10 hits | Mean Top-20 hits | Mean actual rank |
|---|---:|---:|---:|---:|
| Equal-weight 42 | 0.6084 | 1.2449 | 2.5460 | 20.4817 |
| Flow K=10 | 0.5975 | 1.2543 | 2.5242 | 20.5214 |
| Flow K=20 | 0.5928 | 1.2496 | 2.5257 | 20.5045 |
| Flow K=50 | 0.5913 | 1.2621 | 2.5304 | 20.4933 |

Selected K=50 versus equal-weight on Blind OOS:

- Top-20 paired delta: −0.01560 hits/target.
- 95% block-bootstrap CI: [−0.04368, +0.01092].
- Global Holm-adjusted Top-20 p: 1.0.
- Top-5 paired delta: −0.01716 hits/target (−0.3432 percentage points of the five actual numbers).

The primary gate failed: `NO_DEMONSTRATED_GAIN`. Narrowing K alone did not make the current flow state more predictive. Effective analogue counts were 9.75/10, 19.52/20 and 48.72/50; average analogue ages were about 98, 108 and 116 draws respectively. The kernel still produces modestly differentiated weights and the narrower neighborhoods did not improve the held-out ranking.

## Supersession of the earlier speculative Q84 proposal

The file `q84_dynamic_field_hypothesis_2026-11-09.md` on this checkpoint branch was drafted before the existing Q84 branch was discovered. It describes a different 240-dimensional per-number field and was never executed. It is **superseded as the immediate Q84 plan**; do not run it as if it were the repository's registered Q84 protocol. It may be reconsidered only as a new, separately preregistered experiment after human review of the actual Q84 and K-sensitivity evidence.

## Q92 status at this checkpoint

- Corrected Q92 branch head: `739f4134a2dc93c756669bf2f206170d773e1a2f`.
- Regression fix: validator now calls `q92.metric_summary_from_compact_counts`; a regression test rejects the old `q92a` module binding.
- Exact-head general CI run 42683289035: SUCCESS.
- Q92 synthetic shard and paired/Holm acceptance runs 42683276024 and 42683276617: SUCCESS.
- Fresh full walk-forward run 42683275995: preflight SUCCESS; at this checkpoint 5/15 shards completed, 4 in progress and 5 queued. Aggregation/acceptance has not yet completed. The previous run 42668016985 on old source head `593f259...` failed only at acceptance replay due to the module-binding defect; its preliminary metrics remain unaccepted.

## Next action

1. Allow Q92 run 42683275995 to finish all 15 exact-source shards, aggregate, and pass fail-closed acceptance.
2. Persist and reread Q92 outputs, then verify exact-head CI and human review.
3. Review the already validated Q84 and K-sensitivity negative evidence. The next useful hypothesis is not simply another K value: it should test a richer, identity-preserving state representation or different field observables, preregistered before evaluation. Do not tune it against the historical Blind OOS.
4. No automatic promotion or merge.

PR #23 and PR #25 remain open/draft. PR #6, #7 and #8 remain untouched and unmerged.
