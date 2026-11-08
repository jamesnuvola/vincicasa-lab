# PSR-05 — CI artifact readback checkpoint

**Run:** GitHub Actions #629 / 42474860950  
**Branch commit with outputs:** 70a5da241356e7bdd4ac90647358868754fbc800  
**Artifact:** sonar-psr05-signed-displacement, ID 13615565117  
**Archive digest:** sha256:69a4d3c6c919dee15d68cec3a84614fe6d2e98e466bdc4701751c0818f7a55c1

## Readback audit

The downloaded workflow artifact was inspected locally. Both ledger row counts and FNV-1a32 fingerprints match the committed report JSON:

- Grid ledger: 46,515 rows × 38 columns; FNV-1a32 `0955f90a`.
- Selected ledger: 15,505 rows × 36 columns; FNV-1a32 `354a98cc`.
- Report JSON Git blob SHA: `6541c8d6ece65834dd98938bf85e4ca78e2a6bd5`.
- Report Markdown Git blob SHA: `55b94c7659f246ade55c2b72fb1d2b20f81e0ed4`.
- Grid ledger Git blob SHA: `50770efcab8a0da7965b7f5b4fd2f0a90025015d`.
- Selected ledger Git blob SHA: `630a8e23e2e9825b5ca67e95b8ed8d6526817b37`.

All four artifact file Git blob SHA values were calculated from downloaded bytes and match the files read back from the repository. The ZIP digest matches GitHub's artifact metadata. PSR-05's two complete internal executions were byte-identical.

## Final report and reproducibility readback

**Subsequent CI:** run #635 / 42475545395, conclusion **success**. Step 27 regenerated all four PSR-05 outputs and passed the committed byte-for-byte `git diff --exit-code` guard. The workflow also passed the tolerance-aware PSR-04 verifier, all existing lab checks, and the application build.

**Run #635 artifact:** ID 13614928050; digest sha256:0a46587c571911ba454a3373610c48c6d39c9048d7c18677789a4b73304b428e. Downloaded ZIP digest matches GitHub metadata. Artifact file Git blob SHA values match repository readback:
- PSR-05 JSON: `7f1d0b6f6f8f39fd3f36b59c054643a5f785c0fd`.
- PSR-05 Markdown: `104b0852f96747fc4b115b0f795f2949c7cb1253`.
- Grid ledger: `50770efcab8a0da7965b7f5b4fd2f0a90025015d` (46,515 × 38).
- Selected ledger: `630a8e23e2e9825b5ca67e95b8ed8d6526817b37` (15,505 × 36).

The final interpretation now explicitly compares PSR-05 with the exact order-statistic prior and quantifies the P2/P3 anomalies. No engine promotion, merge, or change to PR #6/#7/#8 occurred.
