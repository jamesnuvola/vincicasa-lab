# Q141-A27 — Full-Q90 formula rank stability and lifecycle atlas

**Status:** COMPUTED_REPLAY_VERIFIED — POST_HOC_DESCRIPTIVE_AUDIT_NOT_CONFIRMATORY

## Source and scope

- Q90 artifact: `13627507532` / run `42504717670`.
- Archive: 3,401 draws through 2026-11-07.
- Strict-prior targets: 3,351; formula catalog: 330,429.
- Feature scope: 20 Discovery-selected features from 59 available features.

## Formula-rank stability

| Endpoint | Discovery → Validation Spearman | Discovery → Blind OOS Spearman |
|---|---:|---:|
| Top-5 share | -0.1699 | -0.0267 |
| Mean actual rank | -0.0528 | -0.0354 |
| Top-10 share | -0.0000 | +0.0267 |
| Top-20 share | -0.1024 | -0.0376 |

Top-5-share formula retention:

| Discovery top set | Validation overlap | Blind OOS overlap |
|---:|---:|---:|
| Top 1% (3,305) | 22 | 20 |
| Top 5% (16,522) | 550 | 749 |
| Top 10% (33,043) | 2,144 | 3,073 |

The formula IDs share features and are not independent. Correlations and overlap are descriptive, not independent-sample significance tests.

## Multiple-testing result

| Split | Holm Top-5 significant formulas | Holm rank significant formulas | Mean Top-5 share |
|---|---:|---:|---:|
| discovery | 1 | 0 | 12.8680% |
| validation | 0 | 0 | 12.1003% |
| blind_oos | 0 | 0 | 12.4408% |

The Discovery-selected formula `L8_20_23_18_45_33_50_57_53` has Top-5 shares of 14.1223% / 12.8657% / 12.2687% across Discovery / Validation / Blind OOS. Its later adjusted p-values are 1.0.

## Retrospective oracle lifecycle

- 3,054 distinct oracle-best formula IDs across 3,351 targets.
- 260 IDs recur; maximum recurrence 5; 0 adjacent same-formula repeats.
- Oracle upper envelope: 2.436/5 winners in Top-5, 3.923/5 in Top-10, 4.845/5 in Top-20.

These oracle values choose the best formula after each target is known. They describe retrospective formula capacity and are not forecasts.

Oracle-best operator mix (target share versus formula-universe share):

| Operator type | Oracle-best target share | Catalog share |
|---|---:|---:|
| pairwise_interaction | 72.58% | 8.80% |
| conditional_gate | 15.43% | 11.73% |
| linear_mean | 12.00% | 79.47% |

Family-specific retrospective Top-5 oracle shares:

| Family | Mean winning numbers in Top-5 | Share of five winners |
|---|---:|---:|
| L4 | 1.950/5 | 39.01% |
| L5 | 2.007/5 | 40.14% |
| L6 | 1.996/5 | 39.92% |
| L7 | 1.965/5 | 39.30% |
| L8 | 1.863/5 | 37.27% |
| I4 | 2.384/5 | 47.69% |
| G4 | 2.169/5 | 43.37% |

The interaction family is disproportionately selected by the hindsight oracle. This is a measure of retrospective flexibility, not evidence that interactions can be chosen before a target.

## Family sequence

- Family-winner switch rate: 65.73%; median run length 1.0 targets.
- Count-preserving shuffle reference: observed 2,202 switches; null mean 2184.9; p(lower switches)=0.789; p(transition MI)=0.602.

No excess temporal clustering or transition dependence was detected in this retrospective family-winner sequence. This is not a test of pre-target number prediction.

## Conclusion and next step

The 330,429-formula ranking is highly unstable across chronological splits. One Discovery formula survives its own Holm family, but none does so in Validation or Blind OOS. The retrospective oracle can explain many winners after the fact, while its formula identity changes almost every target.

Next: construct a nested prequential evaluator that scores a deterministic formula universe at each target and chooses formulas only from earlier outcomes; then expand the grammar beyond the current 20-feature and four-feature nonlinear slices.

Historical Blind OOS is already exposed; no predictive or production claim is made.
