# Q141-D4 — Family Top-5 consensus under disagreement states

**Decision: no conditional family-consensus lift demonstrated.** Historical research only; no engine promotion.

## Design and source integrity

- Seven fixed Q89 families partition all 59 features: baseline legacy 27, EWMA 7, gap 6, co-occurrence 6, rank trajectory 5, residual surprise 2, regime/transition 6.
- Each family independently ranks the 40 candidates by its mean per-target feature z-score. Consensus ranks by number of family Top-5 votes, then equal-family mean score, then number ascending.
- Disagreement is mean pairwise Jaccard of the seven family Top-5 sets. High disagreement means current Jaccard is below the median of the preceding 100 targets.
- Q90 artifact: 3,401 draws through 2026-11-07; 3,351 target rows. Q141-A6 outcome ledger aligns exactly on dates, cutoffs and actual quintets. Five later main-archive rows are excluded.
- Walk-forward: 3,351 rows; 100 state warm-up; Discovery 1,911 evaluated, Validation 670, historical Blind OOS 670.

## Results

Mean Top-5 hits per target (uniform expectation 0.625):

| Split | Consensus | Equal-family mean | Equal-59 mean | Consensus − equal-family |
|---|---:|---:|---:|---:|
| Discovery | 0.63318 | 0.62480 | 0.63265 | +0.00837 |
| Validation | 0.55970 | 0.60149 | 0.60149 | −0.04179 |
| Historical Blind OOS | 0.64925 | 0.64328 | 0.64776 | +0.00597 |

Blind OOS contained 327 high-disagreement and 343 low-disagreement targets; mean family Jaccard was 0.15314.

| Registered endpoint | Effect | 95% block-bootstrap CI | Raw p | Holm p |
|---|---:|---:|---:|---:|
| High-disagreement minus low-disagreement paired delta | +0.06002 hits/target | [−0.01777, +0.14029] | 0.14404 | 0.43213 |
| Unconditional consensus minus equal-family mean | +0.00597 | [−0.03134, +0.04179] | 0.81651 | 0.81651 |
| Consensus minus uniform expectation | +0.02425 | [−0.02649, +0.07351] | 0.19217 exact | 0.43213 |

Inference used 20,000 circular block-bootstrap replicates (block 20), 20,000 circular state shifts, 20,000 block sign-flips and exact convolution of Hypergeometric(40,5,5), with Holm across the three registered endpoints.

The primary point estimate exceeds the +0.025 practical threshold, but its interval includes zero and Holm p=0.43213. The unconditional lift is near zero. Discovery, Validation and Blind OOS change sign, indicating instability. No acceptance criterion is met.

## Integrity, recovery and limits

- 12/12 local unit tests passed after correcting a test that incorrectly treated an unmapped legacy feature as invalid; unmapped features correctly belong to baseline_legacy.
- Two complete local runs produced byte-identical report, ledger, manifest and checkpoint.
- Six future-suffix mutation checks passed.
- Exact source ZIP/member hashes, 3,351 row alignment, strict-prior cutoffs and family partition were verified.
- A first run stopped on incorrect pinned A6/catalog digests; both were corrected against the actual downloaded artifact bytes before the successful replay.
- The full 3,351-row ledger is currently a local artifact (466,760 bytes; SHA-256 5d531c4790e5a1635537810b5a57b778e044237b44cd055ee266c5fdea8652cc). The runner, preregistration, tests and workflow are in the research branch. GitHub Actions execution and remote readback of generated outputs have not been observed; do not mark full repository persistence complete.
- Historical Blind OOS is already exposed, not a virgin holdout. These per-number Top-5 metrics do not establish exact-ticket predictability. Holm covers only D4's three endpoints, not the full SONAR research family.

## Next action

Keep D4 research-only. Resolve the dedicated workflow trigger and remote readback. Then continue the Common-Source AST Behaviour Atlas: reconcile Q7/Q90/Q141 semantic ASTs, evaluate them on the same strict-prior cutoffs, deduplicate semantic equivalents, and measure incremental information rather than selecting another retrospective winner.
