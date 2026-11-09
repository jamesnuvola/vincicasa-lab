# SONAR Q89 — persistence recovery attempt 2 checkpoint

Captured: 2026-11-09T19:28:10.175Z

- Original full Q89 run: `42668855015`; all 30 shards SUCCESS; aggregate job SUCCESS; fail-closed Q89 acceptance passed.
- Original aggregate artifact: `sonar-q89-aggregate`, 495303500 bytes, sha256:82e08396f62e33f469f601a20732688133baa633fbb22ae79a2d67bdb375c88e; it remains available and was successfully downloaded by recovery attempt 2.
- Original persistence job failed with HTTP 502 after retries; no branch ref update occurred.
- Recovery attempt 1 failed closed because the CI exact-output validator was accidentally conditioned on the recovery marker and ran before outputs were restored. The condition was corrected.
- Recovery commit: `6187e2782663d64ba0f680d7fb4afdbaa5bec016`.
- Exact-head CI run `42682696950`: SUCCESS; Q89 protocol tests and compile gate succeeded; persisted-output validator correctly skipped because outputs are not yet on the branch.
- Recovery workflow run `42682696879`: in_progress; exact-head wait job SUCCESS; aggregate artifact download SUCCESS; restore SUCCESS; persistence/readback step is IN PROGRESS.
- The recovery path reuses the original aggregate artifact and does not rerun any historical shards.
- Persistence script was hardened with method/path diagnostics, 10 bounded retries for transient 5xx/429, slight write throttling, and a single queue-driven fail-closed acceptance pass. The Q89 queue validator uses precomputed combinadic rank prefixes to avoid repeated `math.comb` loops.
- No final repository persistence, persisted exact-head CI, human review, COMPLETE status or promotion has been verified yet.

Next: allow Git Data API persistence and per-blob byte/SHA readback to finish; then inspect the persisted commit, exact-head CI, queue status and report readback. Keep Q89 pending human review.
