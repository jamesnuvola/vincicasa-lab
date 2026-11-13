# Q141-A12 — execution and checkpoint recovery

**Status:** recovered; final shared CI and remote persistence succeeded.

## Test recovery
- The first local unit-test run had one failure in the test assertion, not in the scorer.
- The test expected 398 transitions in the current Markov state row. The actual row count was 117; 398 is the total number of prior transitions across all states.
- The scorer was made explicit by exposing prior_transition_count; the test now checks total prior transitions = 398 and current-state row count <= 398.
- The complete local suite then passed 7/7 tests.

## Workflow recovery
- Dedicated workflow run 43404786731 downloaded the pinned A7 artifact, completed the walk-forward and all 7 tests, but failed at the final Git push.
- Root cause: the research branch advanced while that workflow was running; its output commit was rejected as non-fast-forward. No result was lost and no remote file was overwritten.
- The shared CI run 43404906228 then ran against the latest stable branch head. All steps succeeded, including A12 replay/tests, canonical archive audit, generated-data rebuild/audit, prospective-gate test, evolutionary lab, positional/regime/residual/hazard lab, web build, artifact upload and report/ledger push.
- Final workflow conclusion: success. Output artifact ID: 14027131770.

## Remote readback
- Report, 2,956-row ledger, preregistration, cycle report and mechanical-dependence note all match their Git blob SHA values in the manifest.
- Checkpoint status updated to REMOTE_GIT_READBACK_VERIFIED.
- The canonical main archive was not modified. No active engine, shadow freeze or protected PR was modified.
