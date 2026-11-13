# Q142 — Fixed 42-rule family exact FWER audit

Decision: NO_FWER_CONTROLLED_EXCESS_DEMONSTRATED. Holm-significant tests: 0/252.

Retrospective audit only. The 42-rule family was developed after historical outcomes were available; this is not a virgin holdout or a new forecast.

| Split | N | First | Last | Mean Top20 hits across 42 rules |
|---|---:|---|---|---:|
| discovery | 1923 | 2018-02-02 | 2023-05-09 | 2.513681 |
| validation | 641 | 2023-05-10 | 2025-02-08 | 2.486851 |
| blind_oos_historical | 642 | 2025-02-09 | 2026-11-12 | 2.496699 |

Exact nulls: P(5/5)=0.023562024; P(4+/5)=0.170824671; E[hits]=2.5.
Best 5/5 raw test: momentum_20_100 / discovery, 68/1923, p=0.000856913, Holm=0.215942.
Best 4+/5 raw test: complement_1 / discovery, 362/1923, p=0.023805, Holm=1.
Discovery winner: momentum_20_100; rates: discovery 68/1923 (3.5361%); validation 12/641 (1.8721%); blind_oos_historical 22/642 (3.4268%).
Spearman rank correlations: discovery_vs_validation=-0.1756; discovery_vs_blind_oos_historical=0.0161; validation_vs_blind_oos_historical=0.0492.
At least one rule hit 5/5 on 1096/3206 targets (34.19%); descriptive only.

Cutoffs and actuals were checked against the canonical archive. Holm covers 252 tests only; global Q00-Q141 multiplicity and post-hoc rule selection remain uncorrected.

Next action: preserve pending prospective forecasts unchanged and reconcile only after official publication.
