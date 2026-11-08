# SONAR PSR-05 — Signed Same-Position Displacement Residual Protocol

**Registration date:** 2026-11-08  
**Branch:** `research/sonar-psr05-signed-displacement-20261108`  
**Status:** preregistered exploratory test; no engine promotion.

## Hypothesis

For the sorted five-number draw (P_1(t)<\cdots<P_5(t)), test whether the signed displacement of the same position over the immediately preceding draw pair carries incremental marginal information about the next target position:

\[
d_i(t)=P_i(t-1)-P_i(t-2).
\]

This feature is observable strictly before target (t). It does not assume five independent draws; only the five position-specific marginal forecasts are scored.

## Fixed state bins

The displacement is mapped into seven fixed states, without data-dependent cutpoints:
`d ≤ −3`, `d = −2`, `d = −1`, `d = 0`, `d = +1`, `d = +2`, `d ≥ +3`.

## Exact order-statistic prior

For position (i), value (n\in\{i,\ldots,35+i\}):
\[
\pi_i(n)=\frac{\binom{n-1}{i-1}\binom{40-n}{5-i}}{\binom{40}{5}}.
\]

Global comparator and state-conditioned candidate use the same prior and alpha:
\[
q^G_{i,t}(n)=\frac{c_{i,t}(n)+\alpha\pi_i(n)}{N_t+\alpha},\qquad
q^S_{i,t}(n\mid s)=\frac{c_{i,t,s}(n)+\alpha\pi_i(n)}{N_{t,s}+\alpha}.
\]

## Frozen walk-forward plan

- Canonical archive SHA-1 Git blob: `5d2efd70684e918b27d8f06386d545647898336d`; 3,401 draws through 2026-11-07.
- Warmup: 300 targets; the first train target is index 2, requiring two prior draws to define displacement.
- For each target (t), train targets are (j=2,\ldots,t-1); assert `train_n = t−2` and cutoff `date[t−1] < date[t]`.
- Chronological test split: discovery 50%, validation 25%, blind OOS final 25%; no random split.
- Alpha grid fixed at `[100, 300, 1000]`; one alpha selected per position by validation mean Brier improvement vs global shrinkage, tie toward smaller alpha.
- Primary blind-OOS endpoint: paired mean Brier improvement vs global comparator, tested one-sided by null-centered circular moving-block bootstrap, block length 7, 2,000 replicates, deterministic position-specific seeds; Holm across the five position endpoints.
- Secondary Top-1/5/10/20, rank, log loss and exact-prior score differences are descriptive.

## Integrity and interpretation

The script audits archive schema, chronology, sorted distinct five-number rows, prior normalization, strict target cutoffs, state feature availability, training counts, duplicate target-position-alpha keys and ledger fingerprints. It performs two full executions and requires byte-identical report and ledgers.

The historical blind partition overlaps earlier PSR-01 through PSR-04 exploration. It is therefore a reused retrospective OOS slice, not independent prospective confirmation. Holm applies to this experiment's five preregistered primary endpoints only; wider experiment-family selection remains exploratory. Position marginals are dependent and are not assembled into a ticket.

**Promotion is prohibited** absent independent prospective evidence and human review. Preserve positive point estimates even when intervals cross zero; do not change the active SONAR engine.
