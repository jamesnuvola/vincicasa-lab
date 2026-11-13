# Q130 checkpoint — family-wise Top-k depth profile

- Protocol committed before calculation: `7e674a5ac6e90ba2383bb6c282631a3aef3ca874`; protocol blob `99520c283327d8e8f069d0040f1c32be53b6ac0e`.
- Base main: `06e9e470054a86a0b710657db35e0c2259ef6b0a`.
- Source ledger blob: `553e08a3c7a0aabd092d3977b75bf959e90b8b3b`; 134,568 rows; 3,204 targets; 42 fixed rule configurations per target.
- Statistic: maximum overlap across the 42 rule Top5, Top10 and Top20 lists for each target.
- Conditional null: 1,000 uniform 5-of-40 draws per target; unbiased rejection sampler; seed `0x01302026`; same draw reused across all three depths.
- Discovery / Validation / historical Blind OOS: 1,922 / 641 / 641 targets.
- Blind OOS Top5: observed 2.04680187; null 2.06238222; gain -0.01558035; raw p 0.75025; Holm 1; block-bootstrap 95% CI [-0.06338066, 0.03304056] .
- Blind OOS Top10: observed 3.00624025; null 2.99505304; gain 0.01118721; raw p 0.352647; Holm 1; block-bootstrap 95% CI [-0.0434571, 0.06375819] .
- Blind OOS Top20: observed 4.24804992; null 4.26762715; gain -0.01957723; raw p 0.789211; Holm 1; block-bootstrap 95% CI [-0.06333385, 0.02237598] .
- Decision: `NO_FAMILYWISE_TOPK_DEPTH_LIFT_DEMONSTRATED`.
- Contest 315 (11/11/2026) remains `PROVISIONAL_SECONDARY_SOURCE_CORROBORATED`: 1, 21, 22, 27, 29. Exact family-wise tails from all 658,008 outcomes: Top5 0.83903083; Top10 0.81251596; Top20 0.35916737. This is descriptive only and excluded from historical scoring and canonical history.
- Validation: 20/20 checks; strict-prior source rows; 10,000 block-bootstrap replicates; Holm family size 3.
- Limitations: 42-rule family selected after archive; historical Blind OOS not virgin; Q00-Q129 global multiplicity not corrected; uniform independent-draw null assumed.
- No canonical archive update, freeze rewrite, Q60 increment, scorer change, engine promotion or automatic merge. PRs #6, #7 and #8 untouched.
- Next: await official publication of contest 315, then append-only score immutable freezes; continue Q60 paired collection; prioritize genuinely prospective evidence over further retrospective feature variants.
