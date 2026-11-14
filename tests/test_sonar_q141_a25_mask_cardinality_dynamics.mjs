#!/usr/bin/env node
import assert from "node:assert/strict";
import {
  buildMaskStrata, forecastVectors, forecastGroupVectors, groupMse,
  reconstructOverallMse, blockSignFlip, circularBlockBootstrap,
  verifyPriorOnly,
} from "../scripts/sonar_q141_a25_mask_cardinality_dynamics.mjs";
import { holmAdjust } from "../scripts/sonar_q141_a23_multivariate_conditional_block_null.mjs";

let passed = 0;
function test(name, fn) {
  fn();
  passed += 1;
  process.stdout.write("PASS " + name + "\n");
}

test("mask lattice partitions all 1,023 masks into fixed cardinality strata", () => {
  const { groups, cardinalityCounts } = buildMaskStrata();
  assert.deepEqual(Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.length])),
    { low: 175, central: 792, high: 56 });
  assert.equal(Object.values(groups).flat().length, 1023);
  assert.equal(new Set(Object.values(groups).flat()).size, 1023);
  assert.deepEqual(cardinalityCounts, { 1: 10, 2: 45, 3: 120, 4: 210, 5: 252, 6: 210, 7: 120, 8: 45, 9: 10, 10: 1 });
});

test("mask strata use only mask cardinality, not observed outcomes", () => {
  const { groups } = buildMaskStrata();
  assert.ok(groups.low.includes(0));
  assert.ok(groups.high.includes(1022));
  assert.ok(!groups.low.includes(1022));
  assert.ok(!groups.high.includes(0));
});

test("forecast requires forty strictly prior vectors", () => {
  const vectors = Array.from({ length: 45 }, (_, i) => Float64Array.from({ length: 1023 }, (_, j) => i + j / 1000));
  assert.throws(() => forecastVectors(vectors, 39), /strict-prior history/);
  assert.equal(forecastVectors(vectors, 40).persistence1[0], 39);
});

test("target and future suffix mutation cannot change earlier group forecasts", () => {
  const vectors = Array.from({ length: 45 }, (_, i) => Float64Array.from({ length: 1023 }, (_, j) => Math.sin(i / 7 + j / 31)));
  assert.equal(verifyPriorOnly(vectors, 40), true);
  const groups = buildMaskStrata().groups;
  const before = forecastGroupVectors(vectors, 40, groups);
  const changed = vectors.map((v) => Float64Array.from(v));
  changed[40].fill(12345);
  changed[41].fill(-9876);
  const after = forecastGroupVectors(changed, 40, groups);
  for (const group of Object.keys(groups)) {
    for (const model of ["persistence1", "mean20", "mean40"]) {
      assert.deepEqual(Array.from(after[group][model]), Array.from(before[group][model]));
    }
  }
});

test("group MSE is normalized by the stratum coordinate count", () => {
  const prediction = Float64Array.from([1, 2, 3, 4]);
  const actual = Float64Array.from([0, 0, 1, 2]);
  assert.equal(groupMse(prediction, actual, [0, 1]), 2.5);
  assert.equal(groupMse(prediction, actual, [2, 3]), 4);
});

test("weighted stratum reconstruction uses the fixed residual rank", () => {
  const groups = { low: Array(175).fill(0), central: Array(792).fill(0), high: Array(56).fill(0) };
  const value = reconstructOverallMse({ low: 1, central: 2, high: 3 }, groups);
  assert.ok(Number.isFinite(value));
  assert.ok(Math.abs(value - (175 + 2 * 792 + 3 * 56) / 967) < 1e-15);
});

test("block sign-flip is deterministic and one-sided for positive lift", () => {
  const negative = Array(40).fill(-0.1);
  const a = blockSignFlip(negative, 10, 250110, 2000);
  const b = blockSignFlip(negative, 10, 250110, 2000);
  assert.deepEqual(a, b);
  assert.equal(a.p_raw, 1);
  const positive = Array(40).fill(0.1);
  assert.ok(blockSignFlip(positive, 5, 250110, 2000).p_raw < 0.05);
});

test("circular block bootstrap is deterministic and preserves constant means", () => {
  const constant = Array(40).fill(0.25);
  const a = circularBlockBootstrap(constant, 20, 260120, 2000);
  const b = circularBlockBootstrap(constant, 20, 260120, 2000);
  assert.deepEqual(a, b);
  assert.equal(a.lower95, 0.25);
  assert.equal(a.median, 0.25);
  assert.equal(a.upper95, 0.25);
});

test("Holm adjustment is monotone in sorted p-value order", () => {
  const adjusted = holmAdjust([0.01, 0.04, 0.03]);
  assert.deepEqual(adjusted, [0.03, 0.06, 0.06]);
});

process.stdout.write("A25_TESTS_OK " + passed + "/9\n");
