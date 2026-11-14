# Q141-B2 — Legacy numerical tie-sensitivity impact audit

**Registration:** 2026-11-12  
**Status before execution:** POST-HOC DIAGNOSTIC REGISTERED; no new model selection or predictive hypothesis  
**Input:** frozen Q141-B1 strict-prior target ledger and manifest  
**Source archive:** Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`, 3,404 eligible draws through 2026-11-10

## Question

The Q141-B1 walk-forward found 2,311 legacy NumPy-vs-stable rank differences among 402,480 sampled formula-target comparisons, despite score deltas no larger than floating-point roundoff. Do those rank changes materially alter Top-5, Top-10 or Top-20 hit coverage?

## Quantitative diagnostic

For the deterministic 120-formula sample (12 formulas per raw feature-subset size k=1..10), compare:
- legacy: NumPy column mean followed by the legacy deterministic rank order (score descending, number index ascending);
- stable: order-stable `math.fsum` raw formula evaluation, followed by the same rank order;
- canonical: multiplicity-preserving weighted-mean AST evaluated with `math.fsum`.

For each strict-prior target, compare the persisted mean actual-number hit shares at Top-5/10/20. Convert share deltas to integer hit counts using 120 formulas × 5 winning numbers per target. Report per-target incidence, split totals and net aggregate differences.

## Walk-forward and controls

Reuse only the already frozen Q141-B1 ledger; do not refit, retune, select formulas or read any outcome to alter a forecast. Re-verify:
- 3,354 chronological targets, split 2,013 / 671 / 670;
- each target index equals its prior-draw count, with cutoff date strictly before target date;
- 120 deterministic formula instances per target;
- exact alias and stable raw-vs-canonical score/rank invariance;
- B1 ledger SHA-256, Git blob SHA-1 and source archive Git blob SHA-1.

Uniform reference shares are 0.125 / 0.25 / 0.5 for Top-5 / Top-10 / Top-20. They contextualize formula coverage but are not used to infer predictive significance in this implementation audit.

## Inference policy

This is a deterministic software/numerical sensitivity audit, not a stochastic prediction test. No p-values or significance claims are appropriate. The three Top-k cutoffs are fixed descriptive endpoints; do not search additional cutoffs. Do not treat the 120 deterministic formula sample as a random sample from the full 16,628,808 raw formula universe.

## Decision and limits

The diagnostic can establish whether floating-point evaluation order changes the persisted sampled Top-k hit counts and by how much. It cannot establish that either arithmetic path predicts future draws, and it does not exhaustively test all formulas. Historical Blind OOS is exposed research history, not virgin prospective evidence. No production ranker or engine may be changed on this basis.

## Acceptance

- Exact input hashes and row/split counts reconcile.
- All target cutoffs remain strict-prior and chronological.
- Stable raw/canonical identities remain exact.
- Per-target Top-k share differences convert to integer hit deltas within numerical tolerance.
- Deterministic report and manifest are generated and persisted with exact Git readback.
- No source archive, historical freeze, prospective shadow, production engine or protected PR is modified.

## Next action

Retain the legacy ranker unchanged for compatibility and use the explicitly documented stable `math.fsum` path for the canonical registry. Next, import Q90 interaction/gate ASTs and Q7 candidate-quintet ASTs as separate typed output families, with source lineage and archive reconciliation before any common-source performance comparison.
