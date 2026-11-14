# Q141-A19 execution recovery note

Date: 2026-11-14  
Authoritative successful workflow: https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43543318926

## Failed attempts and root causes

1. **Initial checkout failure (run 43542864673).** The workflow source contained an escaped GitHub expression for github.sha, so checkout received a literal leading backslash and could not resolve the ref. The expression was corrected. Checkout was also changed to fetch-depth 1; the workflow separately fetches the pinned Q7 source commit and the research branch, so full repository history was unnecessary.
2. **Future-invariance probe NameError (run 43543003444).** The probe referenced SEED_SKETCH while the registered constant was SKETCH_SEED. The identifier was corrected and a dedicated unit test was added for the future-suffix invariance helper.
3. **Residual dimension contract failure (run 43543066700).** The first implementation reported the 1,023-dimensional embedding width as the residual dimension, although the A18 mask design has rank 56 and therefore a 967-dimensional residual subspace. The implementation now constructs the exact 1,023×967 orthonormal complement by complete QR, expresses residual rows in 967 coordinates, and only then applies the fixed 967×64 sketch. Tests and workflow assertions cover complement orthogonality and reconstruction. The Markdown report was aligned with the JSON dimensions.
4. **Manifest final status.** The readback step now updates the manifest to REMOTE_GIT_READBACK_VERIFIED only after the remote content hashes have been checked, then commits and verifies the final manifest, checkpoint and receipt.

## Authoritative final run

- Dedicated workflow: run 43543318926 — SUCCESS.
- Unit tests: 13/13 passed.
- Source: Q7 commit 7a37cab601c5f9386131a00246963f8e4aeabf74.
- Formula masks: 1,023; target rows: 3,386; evaluated rows: 2,186.
- Full replay: byte-identical across five generated outputs before finalization.
- Strict-prior ledger: 2,186 rows checked.
- Future-suffix invariance: passed at target indices 1,200, 2,293 and 3,385.
- Remote readback: report, Markdown, target ledger, circular-shift null, source lineage, validation and final manifest verified; checkpoint and receipt were then committed and re-read.
- Final manifest, checkpoint and receipt all report REMOTE_GIT_READBACK_VERIFIED.

Earlier failed runs are retained in Actions history for audit and are not treated as validated results. No production engine, canonical archive, freeze, Q60 gate or protected PR #6/#7/#8 was changed.
