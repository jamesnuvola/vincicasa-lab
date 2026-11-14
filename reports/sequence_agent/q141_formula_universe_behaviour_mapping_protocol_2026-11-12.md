# Q141 — Formula Universe & Behaviour Mapping

**Status:** REGISTERED — inventory and protocol only; no predictive result claimed  
**Registration date:** 2026-11-12  
**Base main:** `0bf1ef0d39afb671ff83e519489f16b0c24eb15a`  
**Source archive blob on base main:** `fcb453ed06c8002314f826dbac79d6935f9ac103`  
**Source policy:** 3,404-draw eligible prefix through 2026-11-10. Exclude the 2026-11-11 / contest 315 row until primary-source verification is resolved.

## 1. Research question

Can a broad, reproducible universe of mathematical formulas describe how the five winning numbers relate to information available before each draw, and can pre-draw observable state identify which formula families are becoming useful or losing usefulness?

Q141 is not a claim that the draw is predictable. It is a structured research program to distinguish:
1. **Retrospective description:** which formulas fit or rank the realized five numbers after the outcome is known.
2. **Ex-ante prediction:** which formulas, selected and parameterized only from data available before the target, improve a forecast against registered baselines.

Only the second can support a predictive claim.

## 2. Relationship to prior SONAR work

Q141 must inventory and reconcile existing work before recomputing or extending it. Known starting points from open research branches:
- Q83: 80,730 five-feature equal-weight combinations; existing manifest reports 242,190 split-metric rows, on an older archive.
- Q86: 296,010 six-feature combinations; older archive and branch-specific outputs.
- Q87: 888,030 seven-feature combinations; older archive and branch-specific outputs.
- Q90: 330,429 declared variants built from a discovery-selected 20-feature subset of a 59-feature matrix; checkpoint says formula acceptance passed but repository Git-object persistence, main CI, nested ex-ante anticipation and human review were still pending.
- Q91: nested strict-prior anticipation of the Q80 catalog; PR description says stale upstream evidence and completion gates remain pending.
- Q92: exact combinadic core for C(27,10)=8,436,285 combinations and synthetic regression; its PR explicitly says the walk-forward catalog, metrics, target ledger, refreshed control and output persistence were not yet completed.
- Q140: sequential marginal-break diagnostic; no alarms and no predictive lift demonstrated. It is a separate test, not a substitute for formula behaviour mapping.

These counts are not additive: catalogs overlap, use different feature universes, source archives, formula grammars and completion states. Q141's first deliverable is a source-pinned inventory with exact branch/head/blob references, status, lineage, formula semantics and reproducibility—not a summed headline count.

## 3. Formula universe: typed grammar

Build a deterministic, extensible formula registry. Every formula must declare its input scope, output type, operator tree, parameters, complexity and availability time.

### 3.1 Input families
- Per-number prior-only state: cumulative and rolling frequency, recency/age, overdue measures, lag indicators, trend and acceleration.
- Position/rank state: sorted-position marginals, APP ranks/scores, rank transitions and rank residuals.
- Local geometry: gaps, gap ratios, gap moments, adjacency, neighbourhood counts and modular residues.
- Dependence: pair/triple co-occurrence, conditional counts, residual association and graph/field features.
- Whole-draw descriptors: sum, parity, decades, span, entropy/concentration, order statistics and structural signatures.
- Temporal state: rolling-window contrasts, change statistics, state transitions and pre-target forecast residual summaries.

Each feature must be computed from the strict historical prefix for the target. Features derived from outcomes after the target are forbidden.

### 3.2 Operator families
Enumerate bounded, declared operators in deterministic tiers:
- Linear and affine combinations, signed contrasts and normalized ratios.
- Products and low-order interactions; conditional gates and piecewise rules.
- Polynomial and spline-like transforms with bounded degree/knots.
- Rank, ordinal, monotone and distance transforms.
- Modular/residue and periodic transforms with declared modulus/phase.
- Gap/spacing and order-statistic operators.
- Temporal differences, rolling contrasts, slopes, volatility and change-point/state operators.
- Graph/network operators over prior-only co-occurrence/residual structures.
- Formula ensembles and complementary unions, with weights fixed or learned only on prior targets.

The grammar is intentionally finite per registered batch but extensible across batches. “Largest possible” means broad systematic coverage under declared compute/memory budgets—not an unbounded, un-auditable search.

### 3.3 Output types
1. **Number score/ranking:** one score per number 1..40; evaluate Top-5/10/20 hit share, all-five coverage, mean rank and calibration where available.
2. **Quintet score/ranking:** score or order candidate 5-of-40 subsets; evaluate actual-quintet rank and proper scoring rules only when a normalized probability distribution exists.
3. **Draw descriptor/condition:** explain realized structure or classify a pre-target state; descriptive use must not be confused with a forecast.
4. **Meta-selector:** choose or weight formula families using only pre-target information and earlier target outcomes.

## 4. Canonicalization and deduplication

- Represent every formula as a typed canonical AST with deterministic serialization and stable formula ID/hash.
- Normalize commutative operand order, constants, signs, equivalent affine scalings and declared algebraic identities.
- Separate syntactic duplicates from semantic duplicates. Semantic equivalence requires an explicit proof or equality over a declared finite input domain; correlation alone is not equivalence.
- Record feature dependencies, operator sequence, depth, parameter count, compute cost and family tags.
- Retain lineage to earlier Q80–Q92 formula IDs. Never silently discard an old formula; mark it as alias, equivalent, superseded or invalid with reason.
- Keep a registry of rejected/failed formulas as well as surviving candidates.

## 5. Behaviour mapping

For every formula and each strict-prior target, record:
- Source archive hash, target date/index and exact prior cutoff.
- Formula ID/version, feature snapshot hash, parameter-training cutoff and selection provenance.
- Number-level or quintet-level score vector and target outcome evaluation.
- Top-5/10/20 hits, all-five indicators, mean rank, score/rank margins and calibration/proper-score metrics where meaningful.
- Formula availability, active/inactive state, stability, coverage, failure and missingness.
- Co-occurrence with other formula successes/failures; conditional complementarity and redundancy.
- Transition events: onset, persistence, decay, failure, recovery and regime changes.
- Computational cost and whether the formula was actually eligible at that target.

Aggregate over time, but preserve target-level rows so every summary can be replayed.

## 6. Leakage-safe evaluation

For target t, all features, formula discovery, parameter fitting, formula selection, family selection and meta-policy decisions must use information strictly earlier than t.

Use nested chronological walk-forward:
- Discovery: grammar exploration and candidate construction.
- Validation: choose bounded complexity, hyperparameters and family-selection policy.
- Historical blind tail: evaluate a frozen policy once; label it historical/exposed, not virgin prospective evidence.
- Prospective shadow: freeze forecasts before outcomes and accumulate new paired targets. Do not reconstruct missing freezes.

A retrospective per-target oracle may be reported only as an explicitly post-hoc upper-bound diagnostic. It must never be presented as a deployable forecast or as evidence that the formula was knowable before the target.

## 7. Statistical controls and baselines

- Compare number rankings to uniform random 5-of-40 expectations and registered prior-only SONAR baselines on identical targets.
- Compare subset probabilities to the exact uniform 5-of-40 distribution and normalized fixed-size alternatives.
- Pre-register endpoints and the complete formula × split × endpoint testing family for each batch.
- Use family-wise or false-discovery controls appropriate to the declared confirmatory question; account for the full search universe, not only the final shortlist.
- Use paired chronological inference and block-aware uncertainty where serial dependence is plausible.
- Report effect sizes, confidence intervals, raw and adjusted p-values, null results and computational exclusions.
- No winner selection on historical blind OOS. No repeated peeking followed by selective reporting.

## 8. Formula-family anticipation

The key Q141 hypothesis is not “a formula worked often in the past.” It is:

**Do signals observable before target t predict which formula family will have useful coverage on target t?**

Candidate pre-target signals include recent family success/failure, stability, residual structure, co-occurrence, disagreement, feature drift, state transitions and formula diversity. Their definitions and lookback windows must be registered before scoring. The selector is trained only on earlier target-level outcomes, calibrated, and compared with:
- uniform family allocation;
- fixed family allocation;
- best single family selected on Discovery only;
- recency-only and complexity-matched controls;
- a no-selection baseline using the existing SONAR ranking.

A formula's post-target success cannot be used to select that formula for the same target.

## 9. Compute strategy

Do not launch a naive formula_count × all_targets calculation when the cost is prohibitive. Use deterministic shards, bounded batches, streaming aggregation and exact manifests. Screen only through a pre-registered, leakage-safe hierarchy; retain the full tested denominator and all exclusions. Any sampled or pruned universe must be labelled as such, with inclusion probabilities and a clear distinction from exhaustive enumeration.

## 10. First milestones and gates

**Q141-A — Inventory and lineage audit**
- Reconcile Q80–Q92 catalog definitions, counts, archive hashes, branch heads, output availability and acceptance states.
- Detect overlapping formula grammars and stale/incompatible source matrices.
- Produce a canonical feature dictionary and formula-family ontology.

**Q141-B — Registry and canonical formula IDs**
- Define typed AST schema, canonical serialization, semantic-equivalence policy and deterministic IDs.
- Validate with synthetic equivalence/non-equivalence tests and round-trip serialization.

**Q141-C — Behaviour atlas**
- Generate target-level formula behaviour records on the clean source prefix with strict-prior cutoffs.
- Produce coverage, stability, co-occurrence, complementarity and transition summaries.
- Mark retrospective oracle views as descriptive only.

**Q141-D — Ex-ante family anticipation**
- Register and run nested walk-forward family-selection policies.
- Compare against the baselines above; no promotion without independent prospective evidence.

**Acceptance:** exact source/hash reconciliation; complete catalog accounting; deterministic replay; future-suffix invariance; zero target leakage; baseline and multiplicity controls; exact output persistence/readback; exact-head CI; human review. A valid null result is an acceptable research result. No automatic merge, engine promotion, shadow insertion or changes to the canonical archive.

## 11. Current data/provenance boundary

Base main contains 3,405 CSV rows according to the Q140 checkpoint, but only the 3,404-draw prefix through 2026-11-10 is eligible for Q141 until contest 315 is confirmed by a primary source. The 2026-11-11 row must remain quarantined and must not enter feature construction, formula discovery, fitting, validation or forecasts.

Q140's 3,204-target splits (1,922 / 641 / 641) may be used as a historical comparison frame only after exact input reconciliation. Historical blind OOS has prior SONAR research exposure and is not a virgin test set.

## 12. Governance

- Research-only branch; keep PR draft.
- Do not modify or merge PRs #6, #7 or #8.
- Do not merge any Q141 PR or promote any engine automatically.
- Preserve immutable forecast freezes and all previous research artifacts.
- Persist protocol before computation; persist code, outputs, manifests, hashes and checkpoint after each completed stage.
- Report only work actually run and read back from the repository.


## Execution checkpoint — 2026-11-12: Q141-C0

The branch now contains a completed Q141-C0 pilot, a narrow six-family test built from 25 unique Q80-derived features. It is **not** the full formula universe or the canonical AST registry.

- Source: pinned archive blob `fcb453ed06c8002314f826dbac79d6935f9ac103`; 3,404 eligible draws through 2026-11-10; contest 315 excluded.
- Strict-prior walk-forward: 3,354 targets, Discovery 2,013 / Validation 671 / historical Blind OOS 670. The committed target ledger was independently read back and checked: 3,354 rows, chronological target/cutoff order, `prior_draws == target_index`, valid five-number outcomes, and exact split counts.
- Dynamic rolling-100 family selector vs equal-family in Blind OOS: Top-5 hit-share delta +0.00537; 95% block-bootstrap CI [-0.00746, +0.01791]; raw block-sign-flip p=0.4014; Holm-adjusted p=1.000 across 24 paired tests. No lift demonstrated.
- Against the uniform 5-of-40 null, Blind Top-5 raw p=0.4813 (Holm-6 p=1.000). Blind Top-20 raw p=0.01642 but Holm-6 p=0.09852: not significant at 0.05.
- Family Top-5 hit lag-1 autocorrelations range only from -0.0187 to +0.0259. The simple rolling success signal therefore shows almost no temporal persistence in this pilot.
- The exploratory pair-union summaries are size-confounded: the best full-history pair's observed union coverage exceeded its size-conditioned random expectation by only about +0.0042 winning numbers per target; the worst was about -0.0195. Those aggregate summaries were descriptive, not split-wise inferential tests.

The C0 code, leakage/determinism tests and walk-forward run succeeded on code commit `738d02fedfc41d36921559c8855c3090d1292515` (workflow run [43196930220](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43196930220)); the output bundle was then persisted in commit `c9c7f555b28073783965912896e287432256a024`. The subsequent PR check on the output-persistence head was marked `action_required`; it is not being represented as a separate current-head CI pass.

## Q141-C1 — preregistered size-adjusted pair-union test

The next quantitative hypothesis is that at least one pair of distinct formula families has a Top-5 union that covers more winners than a random candidate set of the **same, target-specific union size**. For each of the 15 family pairs and each chronological split, let `U_t` be the size of the union of their prior-only Top-5 sets and `H_t` the number of winning numbers in that union.

Under the sequential uniform 5-of-40 null, conditional on the history before target `t`, `H_t ~ Hypergeometric(40, U_t, 5)`. Because `U_t` is itself adaptive but fixed before the target, C1 will use a predictable conditional hypergeometric e-process: a preregistered equal mixture over fixed positive lambda values, with Ville's maximum-e-value p-value. Holm correction covers all 45 pair × split tests. This avoids the invalid shortcut of convolving unconditional hypergeometric distributions while the candidate-set size is adaptive.

C1 remains a historical exploratory test of six coarse families. Its Holm family does not control the entire prior Q00-Q141 research program. A null result will be retained as a valid finding; no pair will be selected from Blind OOS or promoted.


## Q141-C1 completed — 2026-11-12

The size-adjusted pair-union experiment completed on 3,354 strict-prior targets (2,013 / 671 / 670) across 15 family pairs and 45 pair × split tests. The target × pair ledger contains 50,310 rows. The conditional hypergeometric e-process handled the adaptive union size; Holm covered all 45 tests.

Blind OOS had four positive-excess pairs but **zero** Holm-significant pairs. The smallest raw anytime p was 0.03605 for frequency_level + position_dependence, but its Holm-adjusted p was 1.0. The largest excess was +0.02332 hits/target for frequency_level + neighbour_field (799 observed vs 783.375 size-conditioned expected), raw p=0.05032 and Holm p=1.0. Discovery had 9/15 positive-excess pairs, Validation 1/15, and Blind OOS 4/15: no stable pairwise complementarity was demonstrated.

The C1 workflow run [43199107862](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/43199107862) passed the C0/C1 tests, C1 acceptance, archive and generated-data audits, prospective gate checks and full project CI. The report, manifest and 50,310-row ledger were independently downloaded from its artifact; their SHA256 and Git blob IDs matched the committed files.

## Q141-A provenance audit — 2026-11-12

The new inventory report is `reports/sequence_agent/q141_formula_universe_inventory_lineage_audit_2026-11-12.md`. It confirms that formula counts from Q83–Q92 cannot be summed: their feature grammars overlap and their source archive hashes differ. Q88's metrics manifest and refreshed checkpoint pin different archives. Q90's artifact is externally verified but not stored as Git objects. Q91's artifact and all 34 score shards now have exact Git-object readback verified; its persisted Holm column was blank, so 36 raw p-values were independently adjusted (minimum Holm p=1.0, zero significant).

The Q60 prospective promotion gate remains insufficient at 24 paired dates (23 source-clean) versus the required 200. No engine promotion is allowed.

## Workflow persistence correction

The first concurrent PR/push validation pair both attempted to persist the same generated outputs. The push run succeeded; the PR run encountered an add/add conflict while rebasing. The workflow now keeps PR runs validation-only and performs append-only persistence only on push events to the dedicated `research/q141-*` branches.
