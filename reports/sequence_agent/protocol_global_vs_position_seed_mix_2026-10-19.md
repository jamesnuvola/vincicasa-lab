# SONAR prospective experiment: global Top20 vs position seed mix

- Protocol version: 1.0
- Registered: 2026-10-19
- Repository history source: data/storico_daily.csv
- Baseline cutoff at registration: 2026-10-18 (3,381 draws)
- Candidate A: the existing, unchanged global Top20 generator used by the production walk-forward agent.
- Candidate B: position_seed_mix_top20_v1, unchanged.
- Primary endpoint: indicator that all five winning numbers are contained in Top20.
- Secondary endpoints: Top20 hit count (0-5), Top10 5/5, Top5 5/5; report these separately and do not use them to replace the primary endpoint.
- Design: prospective, paired, target-by-target. Each forecast must be frozen by the real workflow before the target draw, with history_cutoff strictly earlier than target_date. No retrospective reconstruction or backfilling of missing freezes.
- Minimum sample: 200 consecutive eligible target draws. Do not stop early for apparent success or failure.
- Primary comparison: paired difference in Top20 5/5 rates (B minus A), with exact McNemar test on discordant paired outcomes and a 95% confidence interval for the paired rate difference.
- Multiplicity: one preregistered primary endpoint/comparison. Treat all secondary endpoints and any subgroup/regime analyses as exploratory; apply Holm correction within each explicitly reported family of secondary tests.
- Missing/late freeze: mark target ineligible and report it; never reconstruct it. Also report missingness and reasons. If either candidate is absent, do not score the pair.
- Promotion rule: no promotion before 200 eligible pairs and no promotion based only on nominal p-values. Require positive paired effect, two-sided adjusted/primary p < 0.05, and no material degradation in the secondary hit-count distribution. If the sample or workflow is incomplete, status remains INCOMPLETE.
- Baseline context: fixed random Top20 5/5 probability is C(20,5)/C(40,5) = 0.02356202356. This is contextual only; the paired candidate comparison is primary.
- Current state: protocol registered; no new forecast freeze is asserted by this document. The 2026-10-18 pre-existing freeze may be evaluated as a historical diagnostic but is not part of the prospective sample.
