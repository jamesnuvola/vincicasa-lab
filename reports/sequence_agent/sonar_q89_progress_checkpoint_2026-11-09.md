# SONAR Q89 — progress checkpoint

Captured: 2026-11-09T18:06:18.088Z

- Workflow: run `42668855015`.
- Frozen run-request head: `be94053cd5c2a81bf2cca6ec8b74bee765a11d90`.
- Exact-head CI: run `42668854880`, SUCCESS.
- Q89 preflight: SUCCESS; it waited for the exact run-request head CI before starting shards.
- Shard artifacts published: 6/30.
- Shard jobs currently in progress: 15.
- Shard jobs queued: 12.
- Shard job failures: 0.
- No aggregate, Discovery/Validation candidate, Blind OOS result or Holm decision exists yet.

## Published shard artifacts

- `sonar-q89-shard-10`: 14575310 bytes; sha256:82ae51c120bf9909356c943909c2723892e2b73e3a5dd33b9552d6b7371c9555; created 2026-11-09T18:05:28Z; expired=false.
- `sonar-q89-shard-11`: 14700773 bytes; sha256:b9dffe060d51bc1aa93ce7f26922fdd0d8d6112dd7a3733b6a130de32819f1cc; created 2026-11-09T18:05:08Z; expired=false.
- `sonar-q89-shard-14`: 14769062 bytes; sha256:cb7b40964337ef7e81c29c20cbef4cbb81d2a44bca206b9d05d980f1d8dff526; created 2026-11-09T18:05:41Z; expired=false.
- `sonar-q89-shard-3`: 14546045 bytes; sha256:0a2ecfa7c28991b90209b36068fe0bdf1f70bac28bfc8aa720df9baeb54015e0; created 2026-11-09T18:04:54Z; expired=false.
- `sonar-q89-shard-6`: 14669855 bytes; sha256:94c1a258c8cbf9c65e807f37b194c82dfa3310737a57b78a96977bf0f7d98a92; created 2026-11-09T18:05:10Z; expired=false.
- `sonar-q89-shard-9`: 14793815 bytes; sha256:c4e760192bc14fba3616c68b7a81318186a3a284968bea3c4558bdacfac3a6a3; created 2026-11-09T18:04:57Z; expired=false.

These are GitHub artifact archive digests, not yet the internal CSV SHA-256 values. The aggregate job will validate shard schemas, formula coverage, strict-prior ledgers and row counts; the final repository manifest will carry per-part SHA-256, bytes and row ranges.

## Next gate

Wait for all 30 shard artifacts, then aggregate 14,060,475 formula×split rows, apply the global 42,181,425-test Holm correction, validate Discovery top-100 → Validation freeze → selected-candidate-only Blind OOS, reconcile the 3,351-row retrospective ledger, persist via Git Data API, and require exact-head CI plus human review.

No changes were made to the experiment branch during this run; its head remains pinned for reproducibility.
