# Q90 Edge-Field Decomposition — recovery checkpoint 3

Date: 2026-11-10

## Follow-up to the second failure

During exact source readback after run 42745247395, I found that the first schema patch had updated the ledger writer and validator but missed the accumulator's tuple comprehension. The same diagnostic key would therefore still have raised KeyError.

## Correction

Added main_effect_sum to the decomposition accumulator key tuple. The first-target neutral diagnostic, ledger column, writer and validator already contain the field. This is a narrow schema alignment correction; the decomposition formula and registered experiment remain unchanged.

## Recovery action

Run the full Q90 workflow again. Confirm that the accumulator contains every diagnostic emitted by decompose_edge_change before trusting any output. Do not reuse partial artifacts from failed runs.

## Guardrails

No model promotion, no merge, no freeze changes. PRs #6, #7 and #8 remain untouched.