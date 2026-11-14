# Q141-A23 execution recovery note

During the first in-memory calculation, the secondary mean-shift identity was initially written with the within-reference and cross terms reversed. The result collapsed to zero after a non-negative clamp. This was detected before any A23 result artifact was persisted.

The identity was corrected to:

`||mean(X)-mean(Y)||^2 = E||X-Y||^2 - 0.5 E||X-X'||^2 - 0.5 E||Y-Y'||^2`

and normalized by the 967 residual dimensions. A synthetic two-point unit test was added: two point-mass samples at 0 and 1 must yield mean-shift RMS 1 and V-statistic energy distance 2.

The corrected calculation was rerun from the pinned source snapshots. No output from the incorrect attempt was retained or used. The final replay is delegated to the repository CI and is not claimed passed until that workflow reports success.

A second dimensional-normalization audit found that the first corrected mean-shift implementation divided by the ambient 1,023 columns rather than the registered 967-dimensional residual subspace. The script already uses the registered residual dimension; the persisted report and null summary were rescaled by sqrt(1023/967). This common rescaling leaves all bootstrap exceedance counts and p-values unchanged. The corrected metric is now consistent with the protocol and replay implementation.
