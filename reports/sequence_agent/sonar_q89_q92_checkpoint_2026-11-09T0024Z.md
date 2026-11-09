# SONAR Q89/Q92 checkpoint — 2026-11-09 00:24Z

**Q89 recovery remains in progress; Q92 is preregistered but not implemented or executed.**

## Q89 status
- Recovery aggregate run [42538247699](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42538247699), head `d062bf9ea5068235a136c8adf011108c89440274`: still in aggregate step; acceptance, persistence and exact-head CI pending.
- Full CI [42538247764](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42538247764): in progress.
- Prior aggregate run [42534331468](https://github.com/jamesnuvola/vincicasa-lab/actions/runs/42534331468) measured 4,686,825 formulas, 3,351 targets, 14,060,475 metrics, Holm family 42,181,425 and zero formula/split rows below adjusted p=0.05. Candidate IDs were Q89 `P9_06_09_12_14_15_17_18_19_23` and Q88 control `P8_00_08_11_12_15_16_19_23`. Acceptance failed with eight paired metric replay mismatches. These are provisional run-log results only; no outputs accepted or persisted.
- The Q89 branch archive ends 2026-11-07, while canonical main includes 2026-11-08 (blob `77ca692a6082809fcc6c471501617433ec7c36cf`). A current-canonical Q89 refresh is required.

## Q92 preregistration verified
- Branch: `research/sonar-q92-ten-feature-prereg-20261109`
- Commit: `758cf9ed15b7e2073358ed139b4e34dd75c9365f`
- Protocol JSON blob: `e7cc679a5df83def6be0b0aa771ceca8e688695d`; Markdown blob: `df97d139dab50aa23490310a480854a902aad7d6` (readback hashes match).
- Catalog: C(27,10)=8,436,285 formulas; 15 shards × 562,419; 3,352 targets; splits 2,012/670/670; 25,308,855 formula-split metric rows; Holm family 75,926,565.
- Hypothesis: a Discovery→Validation-selected ten-feature equal-weight formula may improve paired Blind OOS Top-5 hit-share over a Q89 candidate selected with the same rule on the same archive/splits. Q89 must be refreshed on the 2026-11-08 archive before it can serve as comparator.
- Q92 implementation and execution are not started.

## Next action and guardrails
Wait for Q89 recovery. If acceptance fails, diagnose the replay mismatches with stable Git-object evidence and fix only confirmed defects. Then refresh Q89 through 2026-11-08. Implement Q92 combinadic runner, acceptance validator and synthetic tests, but do not execute Q92 until the same-archive Q89 control is ready. No automatic merge, promotion or shadow insertion; PRs #6, #7 and #8 remain untouched, and the 2026-10-25 freeze remains immutable.
