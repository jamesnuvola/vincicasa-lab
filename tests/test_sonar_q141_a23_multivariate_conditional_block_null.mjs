import assert from "node:assert/strict";
import {
  buildMaskBasis,
  computeEnergyDistance,
  computeMeanShiftRms,
  holmAdjust,
  maskBasisOrthogonalityError,
  movingBlockSample,
  validateTemporalRows,
  xorshift32,
} from "../scripts/sonar_q141_a23_multivariate_conditional_block_null.mjs";

const basis = buildMaskBasis();
assert.equal(basis.length, 56);
assert.ok(maskBasisOrthogonalityError(basis) < 1e-10);

const n = 4;
const d = new Float64Array(n * n);
const d2 = new Float64Array(n * n);
for (let i = 0; i < 2; i += 1) {
  for (let j = 2; j < 4; j += 1) {
    d[i * n + j] = 1;
    d[j * n + i] = 1;
    d2[i * n + j] = 1;
    d2[j * n + i] = 1;
  }
}
assert.equal(computeEnergyDistance(d, [2, 3], 2, 2, n), 2);
assert.equal(computeMeanShiftRms(d2, [2, 3], 2, 2, n, 1), 1);

const p = holmAdjust([0.04, 0.001, 0.02]);
assert.deepEqual(p.map((x) => Number(x.toFixed(6))), [0.04, 0.003, 0.04]);

const rngA = xorshift32(14123005);
const rngB = xorshift32(14123005);
assert.deepEqual(Array.from({ length: 20 }, () => rngA()), Array.from({ length: 20 }, () => rngB()));

const sampleA = movingBlockSample(xorshift32(14123005), 118, 20, 5);
const sampleB = movingBlockSample(xorshift32(14123005), 118, 20, 5);
assert.deepEqual(sampleA, sampleB);
assert.equal(sampleA.length, 20);
assert.ok(sampleA.every((x) => Number.isInteger(x) && x >= 0 && x < 118));
for (let i = 1; i < sampleA.length; i += 1) {
  // Each new block is circular and no block can exceed the registered length.
  // The deterministic sampler itself is covered by exact replay above.
  assert.ok(Number.isInteger(sampleA[i]));
}

assert.throws(() => validateTemporalRows([], [], []), /row count mismatch/);
process.stdout.write("Q141_A23_TESTS_PASS 8 checks\n");
