# Q141-A23 execution recovery note

During the first in-memory calculation, the secondary mean-shift identity was initially written with the within-reference and cross terms reversed. The result collapsed to zero after a non-negative clamp. This was detected before any A23 result artifact was persisted.

The identity was corrected to:

`||mean(X)-mean(Y)||^2 = E||X-Y||^2 - 0.5 E||X-X'||^2 - 0.5 E||Y-Y'||^2`

and normalized by the 967 residual dimensions. A synthetic two-point unit test was added: two point-mass samples at 0 and 1 must yield mean-shift RMS 1 and V-statistic energy distance 2.

The corrected calculation was rerun from the pinned source snapshots. No output from the incorrect attempt was retained or used. The final replay is delegated to the repository CI and is not claimed passed until that workflow reports success.

A second dimensional-normalization audit found that the first corrected mean-shift implementation divided by the ambient 1,023 columns rather than the registered 967-dimensional residual subspace. The script already uses the registered residual dimension; the persisted report and null summary were rescaled by sqrt(1023/967). This common rescaling leaves all bootstrap exceedance counts and p-values unchanged. The corrected metric is now consistent with the protocol and replay implementation.


## 2026-11-14 — canonical replay discrepancy and resolution

The full CI replay found that the earlier in-memory report and the persisted canonical Node implementation differed by one uniform multiplicative factor across all distance-based observed and null statistics: 1.0015220538. The six source-manifest blob hashes, calibration, target ledger, and source snapshots all matched the registered inputs, so the discrepancy was not caused by source drift or target leakage. The root cause was two non-identical calculation paths (the initial in-memory report path and the repository's canonical replay implementation) using different global residual scaling. The canonical repository implementation was retained as the single source of truth; observed statistics and all null summaries were regenerated from the registered deterministic seeds. Exceedance counts, Monte Carlo p-values, Holm-adjusted values, and energy/null-median ratios were unchanged because the discrepancy was a common scale factor. The corrected report and CSV now replay byte-identically. Both push and pull-request full CI runs passed on the corrected report head. No freeze, canonical archive, production engine, or protected PR was modified.
