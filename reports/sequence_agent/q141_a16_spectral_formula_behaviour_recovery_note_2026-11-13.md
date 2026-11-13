# Q141-A16 execution recovery note — 2026-11-13

The first in-memory correlation build failed closed with `Constant formula residual series`. Root cause: JavaScript `TypedArray.prototype.map` returns a typed array and coerced temporary rank-pair objects to numbers, so the average-rank routine produced an all-zero vector. No report, ledger, forecast or repository artifact was written by that failed calculation.

The implementation was corrected to construct sortable rank pairs with `Array.from(values, ...)`, preserving typed-array input while retaining average ranks for ties. The corrected calculation was rerun from the four SHA-pinned A15 panel blocks and the pinned Q7 archive. It produced no constant formula columns and passed eigensolver reconstruction/orthogonality diagnostics. The regression is covered by a dedicated unit test.
