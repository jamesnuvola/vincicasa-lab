# Q118 final replay recovery

The second Node 20 run reached the Q118 replay after all earlier repository checks passed, then found cross-runtime differences in 12-decimal ledger formatting. The persisted 3,204-target ledger and runner were canonicalized to 10 decimal places. The corrected runner then passed a V8 replay harness: selected alpha=3200, four inference comparisons, exact byte-identical 3,205-line ledger, matching freeze, and 9/9 future-suffix checks. A fresh Node 20 CI run on this final branch is still required; no CI success is claimed here.
