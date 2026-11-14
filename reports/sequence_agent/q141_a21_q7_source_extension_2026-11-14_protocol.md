# Q141-A21 — Q7 Source Extension & Prospective Structural Monitor

Date: 2026-11-14  
Status: preregistered before the dedicated workflow execution  
Research branch: research/q141-a21-q7-source-extension-20261114

## Question

The Q141-A17/A18/A19/A20 panel ends at 2026-10-24, while the canonical archive available at this registration ends at 2026-11-13. Extend the exact Q7 rank grammar by the 20 intervening targets, without changing any formula, smoothing constant, mask definition, projection seed, window, or A20 state threshold. Reproduce the original A20 Discovery/Validation/Blind OOS results and freeze a prior-only structural-capture monitor for 2026-11-14.

## Pinned inputs

- Q7 formula grammar and historical rank source: commit 7a37cab601c5f9386131a00246963f8e4aeabf74 (research/exhaustive-formula-catalog-20261025).
- Canonical archive snapshot: commit 0a376c60dc4c33761d3807d59aebf90d3026980a on main, 3,407 draws through 2026-11-13.
- Historical Q7 prefix: 3,387 draws through 2026-10-24; 3,386 scored formula-profile rows.
- A19 response/drift ledger: 2,186 strict-prior rows, target indices 1201–3386.
- A20 report and q75 transformation: fixed, unchanged, research-only.

## Extension procedure

1. Reconcile the complete 3,387-draw Q7 prefix by parsed date and quintet against the pinned main archive.
2. Recompute only archive target indices 3387–3406 with the original Q7 exhaustive walk-forward engine. Each target is ranked under all 1,023 non-empty subsets of the ten registered feature families over all 658,008 quintets, using only its preceding archive prefix.
3. Append the 20 rank rows in memory to the original 3,386 × 1,023 matrix. Do not rewrite the historical Q7 source or its manifests.
4. Rebuild the unchanged A18 mask residuals and A19 fixed 64-dimensional projection. Require the final pre-extension A19 drift/capture pair to reproduce within 2e-9.
5. For each appended target, compute drift from two 400-target windows ending strictly before that target. Compute the realized structural-capture response only after the target row is available.
6. Before revealing each appended response to the rolling arrays, generate A19 OLS and A20 q75-state forecasts from the preceding 400 drift/capture pairs. Verify that mutating the current response placeholder does not change either forecast.
7. Replay the original A20 Discovery/Validation/Blind OOS metrics against the pinned A19 ledger and require numerical agreement within 1e-10. Keep the original split boundaries unchanged.

## Quantitative hypothesis

The unchanged A20 q75-state transformation retains an MSE gain of at least +0.001 versus the prior-400 capture mean on the 20 appended targets.

This 20-target extension is descriptive only. It is not a confirmatory holdout, no p-value or confidence interval will be used to claim validation, and the old Blind OOS remains historically exposed. The hypothesis cannot authorize model promotion.

## Prospective freeze

Freeze the next-target structural-capture forecasts for 2026-11-14 using cutoff 2026-11-13 and 3,407 prior draws:

- A20 q75-state conditional mean;
- A19 linear drift OLS;
- prior-400 and prior-20 mean baselines.

The freeze contains no candidate numbers, no actual target response, and no probability of winning. It is separate from the 42 candidate shadow forecasts already frozen in main.

Freeze timestamp: 2026-11-14T04:46:04+01:00.

## Registered controls

- Strict target/cutoff/date/quintet alignment for every appended rank row.
- All 1,023 ranks in [1, 658008].
- Reproduction of the final A19 historical drift/capture response.
- Reproduction of A20 historical split MSE gains and inherited Holm results.
- Current-target response-placeholder mutation invariance.
- Deterministic replay of the A21 report, ledgers, and freeze.
- Remote Git readback of all final artifacts.

## Interpretation guardrails

- Formula-profile structural capture is not candidate-number accuracy or exact-ticket probability.
- The Q7 grammar is exhaustive only over the registered 1,023 subsets of ten feature families, not over all mathematical formulas.
- The q75 threshold was selected after A19 inspection; the appended 20 rows are exposed exploratory evidence.
- No canonical archive, latest_metrics.json, shadow forecast, Q60 gate, production engine, or protected PR is modified.
- No automatic merge or engine promotion is permitted.

## Next action

After the official 2026-11-14 result is appended to the canonical archive, compute its Q7 rank row and score the unchanged structural-capture freeze. Do not tune q75, the 400-row window, the projection seed, or the feature grammar on this extension.
