import assert from "node:assert/strict";
import {
  forecastVectors,
  vectorMse,
  buildForecastLedger,
  blockSignFlip,
  circularBlockBootstrap,
  verifyForecastInvariance,
} from "../scripts/sonar_q141_a24_prequential_residual_vector.mjs";

const width = 1023;
const vectors = Array.from({ length: 50 }, (_, i) => {
  const row = new Float64Array(width);
  for (let j = 0; j < width; j += 1) row[j] = Math.sin((i + 1) * (j + 1) / 1000);
  return row;
});

const forecast = forecastVectors(vectors, 40);
assert.equal(forecast.persistence1.length, width);
assert.equal(forecast.mean20.length, width);
assert.equal(forecast.mean40.length, width);
assert.deepEqual(Array.from(forecast.persistence1), Array.from(vectors[39]));
assert.equal(verifyForecastInvariance(vectors, 40), true);

const zeros = new Float64Array(width);
const ones = new Float64Array(width).fill(1);
assert.ok(Math.abs(vectorMse(zeros, ones) - width / 967) < 1e-12);
assert.throws(() => forecastVectors(vectors, 39), /prior history/);

const rows = Array.from({ length: 138 }, (_, i) => {
  const d = new Date(Date.UTC(2026, 0, 1 + i));
  const t = d.toISOString().slice(0, 10);
  const p = new Date(Date.UTC(2026, 0, i));
  return {
    target_index: 3269 + i,
    target_date: t,
    cutoff_date: p.toISOString().slice(0, 10),
  };
});
const longVectors = Array.from({ length: 138 }, (_, i) => {
  const row = new Float64Array(width);
  row.fill(i / 100);
  return row;
});
const ledger = buildForecastLedger(longVectors, rows);
assert.equal(ledger.length, 98);
assert.equal(ledger.filter((r) => r.split === "discovery").length, 58);
assert.equal(ledger.filter((r) => r.split === "validation").length, 20);
assert.equal(ledger.filter((r) => r.split === "blind_oos_exposed").length, 20);
assert.ok(ledger.every((r) => r.strict_prior && r.cutoff_date < r.target_date));

const gains = Array.from({ length: 40 }, (_, i) => Math.cos(i / 3) / 100);
const flipA = blockSignFlip(gains, 5, 12345, 2000);
const flipB = blockSignFlip(gains, 5, 12345, 2000);
assert.deepEqual(flipA, flipB);
assert.ok(flipA.p_raw > 0 && flipA.p_raw <= 1);
assert.equal(flipA.blocks, 8);

const bootA = circularBlockBootstrap(gains, 10, 98765, 2000);
const bootB = circularBlockBootstrap(gains, 10, 98765, 2000);
assert.deepEqual(bootA, bootB);
assert.ok(bootA.lower95 <= bootA.median && bootA.median <= bootA.upper95);

process.stdout.write("Q141_A24_TESTS_OK 13/13 assertions\n");
