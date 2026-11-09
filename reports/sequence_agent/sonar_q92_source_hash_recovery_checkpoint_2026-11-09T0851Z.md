# SONAR Q92 source-hash replay recovery checkpoint — 2026-11-09 08:51 UTC

**Status:** `Q92_SYNTHETIC_ACCEPTANCE_PASS; EXACT_HEAD_FULL_CI_PENDING`  
**Checkpoint branch:** `research/sonar-hourly-checkpoint-20261109-0949`  
**Source PR head:** `853a8592b0a0024a4a259aecb9ec6b3b923b4747` (PR #23, draft; not merged)

## Verified work in this cycle

### Root cause and regression correction

The Q92 strict-prior synthetic runner test failed at `source_code_hashes(root)` with:

`FileNotFoundError: <temporary-root>/scripts/sonar_per_number_condition_10plus_shard.py`

The hash helper correctly reads declared source paths relative to the supplied root. The synthetic test used a temporary root containing only `archive.csv`, but did not materialize the files declared in `SOURCE_CODE_HASH_PATHS`. This was a test-fixture completeness defect, not a walk-forward scoring defect.

The fixture now creates deterministic placeholder files for every declared hash path before invoking the runner. The updated test and helper were persisted on PR #23 and read back by blob SHA:

- `scripts/sonar_q92_common.py` blob: `11ed9c74bc4e5367f50c02b5f4a77891b2455429`
- `tests/test_sonar_q92_walkforward_shard.py` blob: `fb2b7545e2b09e0965052824a373b4ad2636a3b7`
- PR #23 current head: `853a8592b0a0024a4a259aecb9ec6b3b923b4747`

The source-hash envelope now has 12 entries covering the Q92 runner, Q80/Q81 feature stack modules, null-calibration helper, global aggregator/common helper, acceptance validator, Q92 workflows, preregistration and canonical archive. Archive Git/SHA identities are separately carried in the experiment manifest.

### CI evidence

| Gate | Run | Head | Observed result |
|---|---:|---|---|
| Q92 shard synthetic strict-prior acceptance | [42588940380](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588940380) | `853a8592b0a0024a4a259aecb9ec6b3b923b4747` | **SUCCESS** |
| Q92 global Holm/paired-inference synthetic acceptance | [42588936692](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588936692) | `6a83ec4b2e490f578d480b2dc4117f6a98329b0e` | **SUCCESS** |
| Full project exact-head CI | [42588944269](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42588944269) | `853a8592b0a0024a4a259aecb9ec6b3b923b4747` | **IN PROGRESS** at Q80–Q86 exhaustive grammar test (step 17); no final conclusion observed |

The synthetic runner regression and global aggregate regression are therefore complete and green. The full project exact-head gate is not yet complete.

## Quantitative calibration evidence independently reproduced

Q92 preregistered family size: `75,926,565`; first Holm threshold:

`0.05 / 75,926,565 = 6.585310424618841e-10`

For 670 targets, Top-5 number-hit count (s=532):

| Calibration | p-value |
|---|---:|
| Discrete convolution of iid Hypergeometric(40,5,5) counts | `7.934337625211848e-10` |
| Continuity-corrected normal approximation | `2.521639168956081e-10` |
| Relative tail error of normal approximation | `68.21865556938973%` |

The discrete p-value is above the first Holm threshold (`1.204854...` × threshold); the normal approximation is below it (`0.382918...` × threshold). This numerical case was independently reproduced with a separately coded NumPy convolution and normalized PMF. It supports the preregistered pre-execution null-calibration amendment; it is not evidence of predictive skill.

## Same-archive Q89 control — verified, no predictive gain claim

The accepted refresh report `q89_refresh_20261108_report.json` records `VALIDATED_PENDING_HUMAN_REVIEW`, archive size 3,402 through 2026-11-08, 3,352 scored targets and split counts Discovery/Validation/Blind OOS = 2,012/670/670. The refresh checkpoint records 22 persisted files, 47,651,846 bytes and exact-byte readback verified.

Frozen Q89 control candidate: `P9_06_09_12_14_15_17_18_19_23`.

Blind OOS descriptive metrics:

- Top-5 hit-share: 11.7910% (uniform baseline 12.5000%)
- Top-10: 23.5821% (baseline 25.0000%)
- Top-20: 49.5522% (baseline 50.0000%)
- Mean rank: 20.6140 (baseline 20.5000%)
- Global Holm family: 42,181,425; formula/split rows below 0.05: 0

Q89 remains a same-archive control pending human review, not a promoted engine.

## Q92 state and limits

Q92 catalog remains `C(27,10)=8,436,285` equal-weight formulas over prior-only feature states, 15 contiguous shards of 562,419 formulas each. Registered split sizes are 2,012/670/670; expected compact metric rows are 25,308,855 and formula×split×endpoint Holm family size is 75,926,565.

No full historical Q92 shard has been run in this checkpoint. There are no Q92 Discovery, Validation or Blind OOS formula results to report. Candidate freeze, global Holm acceptance, paired inference, append-only persistence and exact-byte readback remain execution gates.

## Next quantitative hypothesis (candidate only; not preregistered)

After Q92 is completed and reviewed, consider Q93: an exhaustive equal-weight 11-feature extension may improve paired Blind OOS Top-5 hit-share versus the Q92 candidate selected by the same Discovery top-100 → Validation freeze rule on the identical archive.

- Universe: `C(27,11)=13,037,895`
- 15 shards: 869,193 formulas each
- Formula×split metric rows: 39,113,685
- Catalog Holm family (3 splits × Top-5/10/20): 117,341,055
- Same strict-prior cutoff and 2,012/670/670 chronological split
- Paired endpoints: Top-5 primary; Top-10, Top-20 and mean rank secondary

This is only a candidate hypothesis. Before any Q93 execution, preregister the experiment-level multiplicity treatment across model comparisons (including Q92), the paired bootstrap/sign-flip seeds and acceptance criteria. Do not use Blind OOS to select Q93 or alter Q92's frozen candidate.

## Guardrails and next action

- PR #23 remains draft/open; no merge.
- PRs #6, #7 and #8 remain open, unmerged and untouched.
- No automatic merge, engine promotion or shadow-stream insertion.
- Next: finish exact-head full CI for `853a8592`; if green, run the immutable 15-shard Q92 walk-forward, then global Holm, Discovery→Validation freeze, paired Blind OOS replay against the refreshed Q89 control, acceptance validator, append-only persistence and exact-byte readback. Human review remains mandatory.
