# SONAR Q96 post-persistence and cross-lab reconciliation — 2026-11-10

## Q96 final state

- Research branch: research/q96-delayed-spectral-recurrence-20261110
- Accepted output commit: 6b69556ca77f45eacc9a4d40984445b9d03aa951
- Workflow run: 42764596346 — SUCCESS
- Independent acceptance: PASS
- Persisted-head read-only replay: PASS
- Report status: VALIDATED_PENDING_HUMAN_REVIEW
- Diagnostic gate: NOT_SUPPORTED
- Strict-prior targets: 3,203 (1,921 Discovery / 641 Validation / 641 historical Blind OOS)
- Fixed lags: 2, 3, 5; 999 constrained node-label permutations per lag/target; 2,000 block-bootstrap replicates; block length 20
- Global Holm family: 9 lag-by-split tests; all adjusted p-values 1.000
- Permutation overlap values independently replayed: 9,599,391
- Target outcomes read: false; immutable freezes modified: false; promotion allowed: false

The delayed recurrence hypothesis is not supported. Observed overlap is at or below the constrained node-label null in all nine lag/split summaries. In particular, lag 2 Validation excess is -0.006733 (95% block-bootstrap CI [-0.009328, -0.003955]); lag 3 historical Blind OOS excess is -0.003743 (CI [-0.006218, -0.001125]). This is a geometric diagnostic, not a forecast-performance result. Historical Blind OOS is exploratory.

Ledger: 87,665,922 bytes; SHA-256 977ba55db42b0d6b1c6dda7b3a97fbbda71476be8023dbacb13d841ca58be076.

The original Q96 checkpoint was written before persisted-head replay and therefore still lists replay/persistence as its next action. This addendum supersedes that operational status; the replay completed successfully in run 42764596346.

## Recovery history

1. Protocol guard initially looked for permutation count/seed at the wrong JSON level. They are nested under permutation_null; engine and validator were corrected.
2. Compressed ledger writer lacked the io import; corrected and covered by a regression test.
3. An early accepted run uploaded its artifact but could not push because the branch advanced during execution (non-fast-forward). The run was not treated as persisted. The next run used exact checked-out source SHA 31b5ebc1e708e382e1f5c990f01ffb05f2cfa4b1, accepted, committed the evidence and passed read-only replay.

## Q92 recovery status

The Q92 validator failure in run 42716753270 was a NameError: EXPECTED_BLIND_TARGETS was referenced but not defined. It is now derived from SPLIT_COUNTS["blind_oos"] on the Q92 branch, commit 449d2e9925a9d68385912025b9937c8b5e0851a2.

- Synthetic discrete-null acceptance workflow: PASS.
- Exact-head project CI: PASS.
- Full 15-shard walk-forward rerun: run 42764304973; preflight PASS. At checkpoint time, five shards were running and ten queued. No new Q92 acceptance or final result is claimed yet.

## Q60 prospective reconciliation — pending official refresh

The main-branch gate still reports 21/200 complete paired prospective targets through 2026-11-08. A further pair of already-frozen (not reconstructed) records exists for target 2026-11-09:

- sequence comparator freq_100: frozen 2026-11-09 00:44:13+01:00, history cutoff 2026-11-08, status FROZEN_PENDING;
- position mix position_seed_mix_top20_v1: frozen 2026-11-09 00:45:45+01:00, history cutoff 2026-11-08, status FROZEN_PENDING.

The canonical archive now contains the 2026-11-09 outcome 9, 17, 25, 32, 34. Against those existing Top20 freezes, freq_100 has 3 hits (9, 17, 25) and position mix has 2 hits (17, 25). This pair is eligible for evaluation by the existing sequence-agent refresh but is not yet included in the official Q60 gate; do not report the official count as 22 until that refresh writes and verifies the paired ledger/gate. No freeze was edited or recreated.

## Next action

1. Allow the existing sequence-agent refresh to evaluate the pending 2026-11-09 pair and append the next legitimate prospective freeze; never reconstruct missing historical freezes.
2. Complete Q92's 15 regenerated shards, aggregation, independent validator, append-only persistence and persisted-head replay.
3. Close the spectral-recurrence line after Q96 NOT_SUPPORTED. Do not add further spectral lags or promote a spectral engine without new independent evidence and human review.
4. Keep Q60's 200-pair prospective gate as the promotion blocker.

PR #35 remains draft and open. PR #23 remains draft and open. PR #6, #7 and #8 remain untouched. No merge or engine promotion was performed.
