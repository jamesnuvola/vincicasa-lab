# Q141 common-source AST lineage audit — 13 November 2026

## Verified result

The Q90 per-number AST catalog and Q7 quintet-score AST catalog are both present in the research branch's remote Git tree. I independently compared the manifest Git blob SHA-1 and byte size for all listed files against the recursive Git tree at source commit `6bc727a46c65fecceff3410a7a635e42c62b4af5` / tree `75ff2f7d316b8b974d40a9b6fddbb0b89b3c420a`.

- Q90: **8/8** manifest files match (seven AST shards plus import report).
- Q7: **5/5** manifest files match (AST catalog, snapshot, import report, complexity report and target ledger).
- Total: **13/13** exact Git blob IDs and byte sizes match.

This closes the Q90 checkpoint's old "remote readback pending" concern at the Git-tree level without rewriting the original checkpoint. It also resolves the stale Q7 receipt/checkpoint metadata discrepancy: the current tree contains the exact blobs claimed by the manifest.

## Source-window reconciliation

I fetched the canonical `data/storico_daily.csv` at each pinned source commit and compared ordered data rows:

| Namespace | Source commit | Draws | Last draw | Archive Git blob |
|---|---|---:|---|---|
| Q7 | `7a37cab601c5f9386131a00246963f8e4aeabf74` | 3,387 | 24 Oct 2026 | `7dab05ba49ace909fe8783eef729605049c65e50` |
| Q90 | `f552d70eebf060244190889d7156ad739dede613` | 3,401 | 7 Nov 2026 | `5d2efd70684e918b27d8f06386d545647898336d` |
| Current main | current main | 3,406 | 12 Nov 2026 | `6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb` |

The 3,387 Q7 data rows are an exact ordered record prefix of Q90; the 3,401 Q90 rows are an exact ordered record prefix of current main. Q7 is therefore 14 draws behind Q90, and Q90 is five draws behind current main. The source files have different trailing newline lengths, so this is record-prefix equality rather than whole-file byte-prefix equality.

## Semantic separation

- Q90 contains **330,429 unique canonical ASTs**, output type `per_number_score`, Q89 feature namespace. Its grammar has 262,599 linear means, 29,070 pairwise interactions and 38,760 conditional gates. The imported Q90 catalog is based on a 20-feature Discovery selection from a 59-feature source universe.
- Q7 contains **1,023 unique canonical ASTs**, output type `quintet_score`, built from ten quintet-level feature families.

Some concepts are related (frequency, interactions, gaps, sum/regime descriptors), but they are not equivalent. Q90 ranks 40 individual numbers; Q7 scores 658,008 possible five-number subsets. Raw ranks, scores and Top-K metrics must not be pooled.

## Root cause and next action

The earlier blocker was not missing AST data: it was a combination of stale checkpoint/receipt metadata, different source cutoffs, and incompatible output semantics. The next implementation should create a common-source evaluator that recomputes both grammars using identical strict-prior target cutoffs while retaining separate, type-appropriate endpoints and baselines. No cross-type composite score should be created without a separately preregistered calibration.

This is a structural lineage audit, not evidence of predictive value. No engine, forecast, Q60/B11 freeze or canonical archive was changed.
