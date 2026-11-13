# Q133 — family-wise maximum-hit distribution calibration

Date: 2026-11-12  
Status: EXPLORATORY_POST_HOC; historical walk-forward only  
Source commit: 50078e442509564bbc1d150ac6aea82421e22979

## Hypothesis

For each target, 42 fixed SONAR configurations produce prior-only Top20 sets. Define
\[
M_t=\max_{j=1,\ldots,42}|D_t\cap T_{20,j,t}|.
\]
Test whether the *full distribution* of \(M_t\) is calibrated to a conditional uniform 5-of-40 null that preserves the exact 42 candidate sets for each target.

H0: observed mean and upper-tail frequencies of M are not greater than the target-wise conditional randomization distribution. Directional alternatives: excess mean M, excess rate M>=4, or excess rate M=5.

This is a calibration diagnostic of an already explored family, not a new prediction engine.

## Data and temporal design

- Source: `reports/sequence_agent/historical_rule_ledger.csv`.
- Git blob SHA: `553e08a3c7a0aabd092d3977b75bf959e90b8b3b`.
- 3,204 targets; 134,568 rows; exactly 42 configurations per target.
- First target 2018-02-02; last target 2026-11-10.
- Every `history_cutoff` must equal the previous calendar date; all Top20 hit counts are recomputed from the five target numbers.
- Splits: Discovery 1,922; Validation 641; historical Blind OOS 641.

The ledger labels these rows `RETROSPECTIVE_WALK_FORWARD_RULE_FIXED_NOW`: target features are prior-only, but the rule family was fixed after historical exploration. Blind OOS is historical, not a virgin holdout.

## Conditional null and inference

For each target, draw 1,000 uniform 5-subsets from 1..40 using a 32-bit Mulberry32 stream and rejection sampling (accepting the largest multiple of 40 below 2^32); sample without replacement. For each simulated subset, calculate maximum hits across the same 42 Top20 sets.

Three upper-tail endpoints are evaluated in each chronological split: mean M, rate M>=4, rate M=5. Holm correction covers all nine endpoints. Paired circular block bootstrap: 10,000 replicates, block length 20, on observed-minus-target-null differences.

## Separate prospective observation: contest 315

Main now contains 2026-11-11 = 1,21,22,27,29. GitHub Actions run 43136027472 appended it with the legacy proximity parser at 2026-11-12 01:39:53 UTC. Official Sisal confirms contest 315 and its prize profile, but retrieved official text does not expose the five numbers; the official VinciCasa November archive still marks 315 pending. Two secondary sources agree on the numbers. Primary-number provenance therefore remains unresolved.

The 43 global freezes and one positional freeze remain pending. Provisional scores are reported separately and do not update Q60. Exact enumeration over all 658,008 5-subsets is conditional on the 42 frozen rule Top-k sets and is descriptive for this one target.

## Decision and limits

A nominal Discovery tail result is not confirmatory. Holm covers only these nine Q133 endpoints, not Q00-Q133. No promotion is permitted. Q60 remains 23/200 until contest-315 provenance is resolved and the existing global/positional pair is evaluated under the registered rules.

## Next action

1. Obtain an official primary source exposing all five contest-315 numbers.
2. Reconcile the already-appended row without rewriting frozen forecasts.
3. Refresh sequence-agent metrics after the archive update.
4. Score the existing 2026-11-11 freezes append-only and update Q60 only if eligible.
