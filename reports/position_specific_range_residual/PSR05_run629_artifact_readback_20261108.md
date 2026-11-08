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

**Next gate:** a subsequent CI run must regenerate the committed PSR-05 outputs and pass the byte-for-byte `git diff --exit-code` check; the first run only created and persisted them.
