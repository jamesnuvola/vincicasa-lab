# Q105 checkpoint — weekday-conditioned subset model

- Protocol preregistered before scoring; alpha=200; no tuning.
- Archive: 3,403 draws through 2026-11-09; target 2026-11-10 excluded pending official publication.
- Walk-forward: 3,203 targets; Discovery 1,921 / Validation 641 / historical Blind OOS 641.
- Runner: strict-prior global and weekday counts; fixed-cardinality e5 normalization.
- Blind weekday-minus-global mean gain: -0.009791683281; Holm p=1.
- Blind weekday-minus-uniform mean gain: -0.012825918263; Holm p=1.
- Validation checks: 11/11 structural/replay/leakage checks passed.
- Recovery: run the Q105 Node script with --write, then with --check; no freeze or production file is modified.
- Next: await official contest 314 publication; append-only Q60 evaluation only.
