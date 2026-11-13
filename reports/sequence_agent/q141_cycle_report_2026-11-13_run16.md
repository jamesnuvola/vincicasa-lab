# VinciCasa SONAR — Q141 cycle 16 (2026-11-13)

## Decision

The historical A7/B11 result remains negative. The frozen prospective protocol was started correctly: one pre-outcome prediction for 2026-11-13 was generated, hashed and read back from Git. No outcome has been appended and no efficacy analysis has been run.

## Recovered state and source reconciliation

- Recovered A7/B11 checkpoint from branch research/q141-a7-fresh59-behaviour-20261113.
- Canonical archive: 3,406 draws through 2026-11-12; Git blob 6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb.
- Official VinciCasa archive lists contest 316 dated 2026-11-12 with 2, 4, 7, 23, 33: https://www.vincicasa.it/archivio-estrazioni
- Sisal's latest-results page still displayed contest 315 dated 2026-11-11 at the time of checking; it is recorded as a lagging mirror, not used to override the official VinciCasa archive: https://www.sisal.it/vincicasa/ultima-estrazione
- Official schedule states daily draws at 20:00: https://www.sisal.it/vincicasa/faq
- Repository final row matches the official VinciCasa archive exactly.

## Quantitative hypothesis kept frozen

No new retrospective selector was introduced. Changing the model now would contaminate the prospective confirmation protocol.

B11 remains the preregistered hypothesis: over the next 200 consecutive eligible official draws, the fixed stability-weighted M1 should exceed equal-family M0 by at least +0.005 in paired Top-5 per-number hit share, with a 95% block-bootstrap interval lower bound above zero and Holm-adjusted p below 0.05. Top-10 is secondary. Exact block sign-flip and circular block bootstrap use block length 20; Holm covers the two registered endpoints.

## First prospective freeze

- Target: 2026-11-13 at 20:00 Europe/Rome.
- Frozen at: 2026-11-13T02:48:10.854369Z.
- Prior cutoff: 2026-11-12; 3,406 prior draws.
- Five prior target feature rows used for turnover weights: 2026-11-08 through 2026-11-12.
- M0 equal-family Top-5: 25, 1, 7, 27, 36.
- M1 stability-weighted Top-5: 25, 1, 27, 7, 36.
- M0 Top-10: 25, 1, 7, 27, 36, 16, 29, 35, 26, 17.
- M1 Top-10: 25, 1, 27, 7, 36, 16, 35, 29, 26, 38.
- M1 family weights: baseline 0.148849; EWMA 0.176414; gap 0.094041; co-occurrence 0.088044; rank trajectory 0.199296; residual surprise 0.215528; regime transition 0.077830.
- Prediction SHA-256: 009f56ae414852c223a81a7d209e17bc4f94076b72556c87d15273001470a1f3.
- Code commit pinned in the prediction: 1a6f27adc158c47c300c992be3ef38bfa99505ec.

The 40-number M0/M1 score vectors, prior family turnovers, normalized weights, feature-vector hash and rank-history hash are stored in the immutable prediction JSON. The record contains no actual outcome.

## Integrity and persistence

- The extended feature builder reproduced the complete historical A7 matrix prefix bit-for-bit; maximum absolute difference 0.
- The stored historical last-row family weights were independently recomputed and matched exactly (maximum difference 0).
- The next feature row was generated from all 3,406 prior draws; the dummy sentinel is only used to advance the existing score-before-update feature builder and is never read as an outcome.
- Prospective checkpoint status: PREDICTION_FROZEN_REMOTE_VERIFIED.
- Remote Git blob readback verified for prediction JSON, one-row append-only ledger, report and manifest.
- No target outcome, hit count or efficacy statistic has been appended.

## Limitations and governance

- One frozen prediction is not evidence of predictive skill.
- No discovery/validation/blind efficacy comparison is appropriate on a single prospective target.
- No interim efficacy peeking, retuning, threshold changes or family remapping.
- PR #90 remains open for human review; no merge or rebase.
- PRs #6, #7, #8 and #89 untouched.
- No canonical archive mutation, shadow insertion or engine promotion.

## Next action

After the official 2026-11-13 result is published, verify the exact five numbers from the official VinciCasa archive, append the outcome to the prospective ledger without changing the frozen prediction, and continue collecting 200 consecutive eligible draws. Run the single preregistered paired analysis only after all 200 outcomes are locked.
