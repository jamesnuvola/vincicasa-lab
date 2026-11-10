# Q88 execution trigger checkpoint

10 November 2026. The Q88 draft now targets the isolated base branch research/q88-execution-base-20261110, which carries the registered Q88 workflow so the pull_request validation is available from the base ref. This branch is infrastructure-only and is not a merge or model promotion.

The experiment remains PREREGISTERED_PENDING_EXECUTION until the workflow completes unit tests, strict-prior walk-forward, independent acceptance replay, append-only artifact persistence, exact-byte Git readback, read-only replay on the persisted head, and general CI on that same head.

No source archive, historical freeze, PR #6, PR #7, or PR #8 was modified.

The isolated execution base now also runs the Q88 strict-prior experiment as a guarded step in its existing Test VinciCasa Lab CI workflow. This provides a second execution path if the dedicated research workflow remains queued. The step is restricted to this Q88 head branch, performs the same registered tests and independent replay, persists only Q88 append-only artifacts, verifies Git readback, and dispatches a full CI/read-only replay on the persisted branch. The PR remains draft and no merge is requested.

A trusted push-only compute/persist workflow has been added. Pull-request workflows remain read-only. The push workflow is restricted to changes to this checkpoint path, runs the registered Q88 walk-forward and independent validator, uploads a recovery artifact, persists the six artifacts with a dedicated commit marker, verifies byte-for-byte Git readback, and runs a read-only replay. The subsequent PR synchronize event is responsible for read-only replay and general CI on the persisted head.
