# Q123 checkpoint — APP full-ranking ordinal skill

- Preregistration commit: f5c8e99a050b830683b454604ff5c3a52e741c02.
- Canonical archive: 3404 draws through 2026-11-10; blob 40f317e2d0067e061c46ab799d66f777a0e087c0.
- Exact APP scorer and APP data blobs pinned; APP modelDraws reconciles row-by-row.
- 3,204 strict-prior targets; Discovery/Validation/Blind OOS = 1,922/641/641.
- Primary Blind OOS mean rank: 20.336661466459 vs null 20.5; p=0.20077598448; Holm=0.60232795344.
- Decision: NO_APP_ORDINAL_RANK_SKILL_DEMONSTRATED.
- Q60 unchanged; no historical freeze reconstructed.
- PRs #6, #7, #8 untouched; no merge or production promotion.

## Blind OOS metrics

| Metric | Observed | Uniform null |
|---|---:|---:|
| Mean drawn rank | 20.336661466459 | 20.5 |
| Top5 mean hits | 0.622464898596 | 0.625 |
| Top10 mean hits | 1.316692667707 | 1.25 |
| Top20 mean hits | 2.525741029641 | 2.5 |

## Next action

Verify contest 315 after official publication; score Q123 freeze without retuning and continue Q60 append-only paired collection.
