# Q141-A8 — Top-5 divergence as an information gate (DRAFT ONLY)

**Status:** proposal only; not active, not part of B11, and not to be evaluated on the B11 200-draw sample.

## Motivation

The first frozen B11 target has identical unordered M0 and M1 Top-5 sets even though the score ordering differs. Consequently, that target contributes exactly zero to the paired primary Top-5 difference. This suggests that the adaptive rule can affect the registered Top-5 endpoint only when its membership differs from M0.

## Quantitative hypothesis

On a **new, independent prospective sample collected only after B11 is fully closed**, define before each target:

`D_t = 1 - |Top5(M0_t) intersection Top5(M1_t)| / 5`.

A target is divergence-active when `D_t > 0`.

Hypothesis A8:
1. Divergence prevalence is at least 25% of eligible targets.
2. On divergence-active targets, mean paired M1-minus-M0 Top-5 per-number hit share is at least +0.020.
3. Across all targets, the unconditional paired improvement is at least +0.005, with a 95% block-bootstrap lower bound above zero and Holm-adjusted p < 0.05.

Use one new 200-target consecutive sample, fixed block length 20, exact block sign-flip test and 20,000-replicate circular moving-block bootstrap. Holm correction covers the registered unconditional primary endpoint and the conditional divergence-active endpoint. Require at least 50 divergence-active targets; otherwise report the conditional endpoint as underpowered/inconclusive without changing the threshold.

## Controls

- `D_t` is computed exclusively from frozen pre-outcome M0/M1 rankings.
- Freeze and hash both rankings, `D_t`, prior cutoff, source archive hash and code commit before each outcome.
- No interim efficacy peeking or threshold changes.
- Do not reuse any B11 target in A8.
- If B11 fails, A8 remains a separate future hypothesis; do not retune A8 using B11 outcomes.
- Research only; no engine promotion or merge authorization.

## Why deferred

B11 is an active confirmatory protocol. Using its outcomes to select, tune, or validate A8 would reuse the same prospective sample and invalidate an independent confirmation. A8 must remain inactive until B11's 200 eligible outcomes have been reconciled and its single registered analysis completed.
