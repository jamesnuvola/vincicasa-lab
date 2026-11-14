# Q141-A21 finalization addendum

The Q7 rank batch and A21 residual extension completed successfully. The first workflow attempt exposed an incorrect output-directory assertion; the corrected run completed the 20-target batch, A21 calculation, deterministic replay, and initial remote readback.

The workflow branch was fast-forwarded to include a protocol correction after the A21 manifest had first been generated. That merge changed the protocol and checkpoint blobs, leaving their entries in the first manifest stale. This finalization recomputes the manifest from the actual branch files and performs a second remote readback. No numerical result, extension row, or 2026-11-14 freeze value is changed by this addendum.

The 20-row extension remains descriptive and non-confirmatory. The q75-state MSE gain versus the prior-400 mean is negative; no model promotion is authorized.
