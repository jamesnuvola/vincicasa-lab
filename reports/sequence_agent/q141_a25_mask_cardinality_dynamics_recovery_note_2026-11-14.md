# Q141-A25 execution recovery note — 2026-11-14

## Failed attempt

Dedicated workflow run 43572714974 completed:
- deterministic report/ledger generation: success;
- focused tests: 9/9 passed;
- deterministic replay: byte-identical;
- persistence step: failed before commit.

Root cause: the workflow staged `q141_a25_mask_cardinality_dynamics_2026-11-14_*`, but the actual generated filenames include an intervening output-kind token (for example `q141_a25_mask_cardinality_dynamics_report_2026-11-14.json`). Git therefore returned a pathspec-not-found error. No generated A25 result was pushed by this failed run.

## Recovery

The workflow staging pattern was corrected to `q141_a25_mask_cardinality_dynamics_*_2026-11-14.*`. The next run recomputes from the pinned A23 source snapshots and A24 parent ledger/report, reruns all tests and replay, then performs remote Git blob readback. No force push, merge, source mutation, or freeze change was used.

The computed checkpoint remains deterministic and recoverable from the pinned inputs. The failure was a persistence-glob defect, not an analytical or statistical test failure.
