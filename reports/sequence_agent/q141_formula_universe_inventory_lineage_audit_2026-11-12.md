# Q141-A — Formula universe inventory and lineage audit

**Date:** 2026-11-12  
**Status:** PARTIAL_AUDIT_PERSISTED  
**Repository base:** `main` at `0bf1ef0d39afb671ff83e519489f16b0c24eb15a`  
**Eligible source prefix:** 3,404 draws through 2026-11-10, archive Git blob `fcb453ed06c8002314f826dbac79d6935f9ac103`. The 2026-11-11 / contest 315 row remains excluded pending primary-source verification.

## Executive finding

The repository already contains a large amount of formula-search work, but it is not yet one comparable, canonical formula universe. Catalogs use different feature grammars and different archive versions; some are nested/overlapping, some are stale, and several have different levels of validation and persistence. Their counts must **not** be added together.

The main bottleneck is not a shortage of candidate formulas. It is the lack of one source-pinned, typed formula registry with stable IDs, lineage, semantic deduplication and comparable strict-prior evaluation.

## Inventory of prior work

| Task | Declared universe | Source archive / lineage | Evidence status |
|---|---:|---|---|
| Q80 | 3,303 formulas | Used by Q91 | Finite catalog; canonical cross-branch import pending |
| Q83 | 80,730 | SHA256 `4c79ac53…` | Manifest: 242,190 split-metric rows, 9 parts |
| Q86 | 296,010 | SHA256 `4c79ac53…` | Manifest: 888,030 rows, 30 parts |
| Q87 | 888,030 | SHA256 `3bcffb47…` | Manifest: 2,664,090 rows, 89 parts |
| Q88 | 2,220,075 | Manifest SHA `3bcffb47…`; checkpoint SHA `e8d09197…` | 6,660,225 rows, 223 parts; archive mismatch and current-head CI failure |
| Q89 | 59 features | Input to Q90 | Feature matrix/lineage still needs canonical import |
| Q90 | 330,429 variants | Archive blob `5d2efd70…`, 3,401 draws / 3,351 targets | Formula acceptance passed; artifact SHA verified; Git-object persistence and human integration pending |
| Q91 | 3,303 formulas × 6 meta-policies | Archive blob `dc555356…`, 3,398 draws / 3,348 targets | Walk-forward artifact and Git-object readback independently verified; no predictive lift |
| Q92 | 8,436,285 combinations = C(27,10) | Archive blob `77ca692a…`, main commit `6cca9022…` | Combinadic core/synthetic tests only; no walk-forward results |
| Q141-C0 | 6 coarse families / 25 unique features | Current eligible prefix | 3,354-target family behaviour and selector pilot; no lift |
| Q141-C1 | 15 family pairs | Same prefix | 50,310 target-pair rows / 45 tests; no size-adjusted pair lift |

These are declared grammar sizes, not counts of proven unique mathematical functions. Q83/Q86 share one source archive; Q87/Q88 share another manifest archive; the grammars overlap and are nested. Q88's refreshed checkpoint instead pins a third archive (`e8d09197…`, blob `1c9c3824…`, 3,400 draws through 2026-11-06), while its formula metrics manifest still pins `3bcffb47…`. Q90, Q91, Q92 and Q141 use still different archive versions. A direct cross-task performance ranking is therefore invalid until the source data and feature definitions are reconciled.

## Recovered results and independent checks

### Q90 — 330,429 formula variants

The downloaded Q90 artifact was 69,356,707 bytes and its SHA256 exactly matched the checkpoint: `12df057170bc87e5ea36406d52b4ebf3d749e03d95a36a656e07334f1d049077`.

- Grammar: 262,599 equal-weight linear combinations, 29,070 pairwise interactions and 38,760 conditional gates over a Discovery-selected 20-feature subset of 59.
- The 330,429-formula split metrics contain one Holm-significant Top-5 formula in Discovery, zero in Validation and zero in Blind OOS. Every Blind OOS formula's Holm Top-5 p-value is 1.0.
- The best Blind OOS Top-5 formula's raw hit share is 0.14090, but its adjusted p-value is 1.0. This is a maximum over a huge search family, not evidence of a usable ex-ante formula.
- The separate 59-feature screen has zero Holm-significant features in Discovery, Validation or Blind OOS.
- The per-target oracle-best formula ledger is retrospective by construction and cannot be treated as a forecast.
- Q90's checkpoint still lists repository Git-object persistence, main CI, nested ex-ante anticipation and human review as pending.

### Q91 — nested anticipation of the Q80 catalog

The 16,157,390-byte workflow artifact was downloaded. All 34 score shards matched their manifest SHA256 values and their Git blob SHA1s matched the branch tree. The target ledger, policy metrics, formula catalog, selection report, walk-forward report and score manifest also matched their exact Git objects.

The `holm_p_max_endpoint_family` column in `q91_policy_metrics.csv` is blank for all 18 rows, despite the report declaring 36 tests. I independently recomputed Holm over the 36 persisted raw p-values: minimum adjusted p=1.0; zero significant results. The Discovery-selected `EXPANDING_TOP5` policy is below the uniform baseline in both holdouts:
- Validation Top-5 share 0.11582 vs 0.125 uniform; mean actual rank 20.864 vs 20.5.
- Blind OOS Top-5 share 0.11809 vs 0.125; mean actual rank 20.642 vs 20.5.

Thus the selected meta-policy did not generalize. The blank adjusted-p column is a reporting defect, not evidence of a significant result.

### Q141-C0 — family behaviour and rolling selector

3,354 strict-prior targets: Discovery 2,013 / Validation 671 / Blind OOS 670. The dynamic rolling-100 family selector's Blind Top-5 hit-share gain over equal-family was +0.00537, with 95% block-bootstrap CI [-0.00746, +0.01791], raw paired p=0.4014 and Holm-24 p=1.0. Family Top-5 hit lag-1 autocorrelations were between -0.0187 and +0.0259: almost no persistence for the tested rolling-success signal.

### Q141-C1 — size-adjusted pair-union complementarity

All 15 pairs of the six family Top-5 sets were evaluated on the same 3,354 strict-prior targets. The target × pair ledger has 50,310 rows. The null conditions on the predictable, target-specific union size (U_t): (H_tmidmathcal F_{t-1}simmathrm{Hypergeometric}(40,U_t,5)). A fixed lambda mixture of conditional e-processes and Ville p-values avoids treating adaptive union sizes as an unconditional fixed-parameter convolution. Holm covers all 45 pair × split tests.

- Blind OOS: 4/15 pairs had positive raw excess, but 0/15 passed Holm.
- The smallest raw anytime p was 0.03605 for frequency_level + position_dependence; Holm p=1.0.
- The largest positive excess was +0.02332 hits/target for frequency_level + neighbour_field (799 observed vs 783.375 size-conditioned expected); raw p=0.05032, Holm p=1.0.
- Validation had only 1/15 positive-excess pairs; Discovery had 9/15. The lack of persistence across splits is inconsistent with a stable complementary pair.

The C1 report, manifest and 50,310-row ledger were downloaded from the workflow artifact and their SHA256 values and Git blob IDs matched the committed files exactly. The push workflow run passed the C0/C1 tests, C1 acceptance, archive/data audits and the full project CI.

## Root causes

1. **Archive fragmentation:** Q83/Q86, Q87/Q88, Q90, Q91, Q92 and Q141 use different source hashes. Q88 also has a manifest/checkpoint mismatch.
2. **No canonical formula identity:** formula counts overlap and no shared typed AST/semantic-equivalence registry exists; totals cannot be summed or deduplicated reliably.
3. **Search-induced optimism:** Q90's discovery-only adjusted winner did not replicate; Q91's selected policy underperformed uniform; Q141-C0/C1 show no holdout lift.
4. **Weak temporal persistence:** the C0 rolling family-success signal has near-zero lag-1 autocorrelation.
5. **Candidate-budget confounding:** pair unions can cover more numbers merely because they contain more candidates; C1's size-conditioned test found no significant excess.
6. **Evidence/reporting gaps:** Q90 raw outputs remain external to Git; Q88 archive mismatch blocks acceptance; Q91's adjusted-p column is blank even though raw p-values allow a reproducible Holm recomputation.

## Promotion and governance boundary

The canonical Q60 prospective gate remains `INSUFFICIENT_PROSPECTIVE_CASES`: 24 complete paired dates versus the required 200; 2026-11-11 remains quarantined, leaving 23 source-clean pairs. No engine promotion is allowed. PRs #6, #7 and #8 remain untouched; no merge, archive edit or shadow insertion was made.

## Next action

1. Complete Q141-A by importing the exact Q80/Q89 feature definitions and Q80-Q92 formula definitions with source hashes and lineage.
2. Implement Q141-B's typed AST, deterministic formula IDs, alias graph and proof-based semantic deduplication.
3. Reconcile all candidate features against one canonical, pinned archive before any comparable full-universe walk-forward replay.
4. Only after the registry is stable, build the broader behaviour atlas and test pre-target state signals for family transitions. Do not spend another cycle tuning rolling hit windows or selecting a pair from Blind OOS.


### Q141-C2 — Current-state family margin selector

The C2 preregistration was frozen before execution. Its runner initially failed closed because the preregistration stored `formula_policy.no_tuning` as a descriptive string while the validator required the boolean `true`. This was a schema mismatch, not a statistical failure: the description was preserved as `no_tuning_policy`, and the boolean flag was corrected. The C2 unit tests and walk-forward runner then passed.

- Source: same pinned 3,404-draw prefix through 2026-11-10; contest 315 excluded.
- Targets: 3,354 (Discovery 2,013 / Validation 671 / Blind OOS 670).
- Policy: choose the six-family score with the largest prior-only standardized fifth-minus-sixth score margin; no outcome warm-up or parameter tuning; 2,458 family switches.
- Blind primary Top-5 gain vs equal-family: **+0.002985** (below preregistered +0.005 practical threshold); 95% block-bootstrap CI **[-0.01134, +0.01701]**; raw paired p=**0.7007**, Holm-24 p=**1.0**.
- Blind Top-5 vs uniform: 412 hits vs 418.75 expected; exact p=0.65366, Holm-6 p=1.0. Blind Top-20: 1,740 vs 1,675 expected; raw p=0.00931, Holm-6 p=0.05588 (not significant at 0.05).
- Margin calibration: 18 family × split tests; zero survive Holm. No evidence that a larger current-state margin signals greater family usefulness.
- Decision: `NO_CURRENT_STATE_MARGIN_LIFT_DEMONSTRATED`. No family or engine is promoted.

The C2 report, manifest and 3,354-row target ledger are present on the Q141 branch. The manifest records code SHA256 `539bc37d…`, report SHA256 `fa9b98cc…` and target-ledger SHA256 `24f88e7a…`; Git tree readback confirms the report blob `f8c5f353…`, manifest blob `7900d0f2…` and ledger blob `a7410fd3…` (3,570,421 bytes). The full workflow run `43212004991` completed successfully on head `a925ab62…`, including Q141-C0/C1/C2, append-only output persistence, archive/data audits, prospective-gate checks, positional/regime/residual/hazard lab and application build.

## Updated diagnosis and next action

Across Q141-C0, C1 and C2, three distinct approaches—rolling historical family success, size-conditioned pair unions and current-state margin selection—have not demonstrated a reproducible blind-holdout lift. This does not prove all formula families are useless; the tested universe is only six coarse Q80-derived families and the historical blind tail is exposed. The main actionable bottleneck remains the fragmented formula lineage and absence of a canonical typed registry. Stop adding small variants of these three selectors. Proceed to Q141-B: import the exact Q80/Q89 feature definitions, reconcile Q80-Q92 source hashes and build deterministic typed formula IDs with proof-based deduplication before expanding the behaviour atlas.
