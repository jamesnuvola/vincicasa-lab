import assert from "node:assert/strict";
import {
  parseCsv,
  aggregateTarget,
  validateFreezeRow,
  exactSignFlipGreater,
  hypergeometricTop20Pmf,
  exactUniformUpperTail,
  circularBlockBootstrapCI,
  holmAdjust
} from "../scripts/sonar_q144_shadow_rank_ensemble.mjs";

const top20 = Array.from({ length: 20 }, (_, i) => i + 1).join(" ");
const rows = [];
for (const [type, count] of [["family", 24], ["pair", 12], ["chain", 6]]) {
  for (let i = 0; i < count; i++) rows.push({ config_type: type, config_id: type + "_" + i, top20 });
}
rows.push({ config_type: "app_engine", config_id: "APP", top20 });

assert.equal(parseCsv('a,b\n"x,y",z\n')[0].a, "x,y");
const aggregate = aggregateTarget(rows);
assert.deepEqual(aggregate.borda, Array.from({ length: 20 }, (_, i) => i + 1));
assert.deepEqual(aggregate.inclusion, Array.from({ length: 20 }, (_, i) => i + 1));
assert.deepEqual(aggregate.app, Array.from({ length: 20 }, (_, i) => i + 1));
assert.deepEqual(aggregate.counts, { family: 24, pair: 12, chain: 6 });
assert.throws(() => aggregateTarget(rows.slice(1)), /42 non-APP rule rows/);

const archiveDates = new Set(["2026-11-12", "2026-10-25", "2026-10-24"]);
assert.equal(validateFreezeRow({
  frozen_at: "2026-11-13T08:00:00+01:00",
  history_cutoff: "2026-11-12"
}, "2026-11-13", archiveDates), true);
assert.equal(validateFreezeRow({
  frozen_at: "2026-10-25T23:30:00+01:00",
  history_cutoff: "2026-10-25"
}, "2026-10-26", archiveDates), true);
assert.throws(() => validateFreezeRow({
  frozen_at: "2026-10-25T19:00:00+01:00",
  history_cutoff: "2026-10-25"
}, "2026-10-26", archiveDates), /Same-day cutoff/);
assert.throws(() => validateFreezeRow({
  frozen_at: "2026-11-13T21:00:00+01:00",
  history_cutoff: "2026-11-12"
}, "2026-11-13", archiveDates), /after target draw/);
assert.throws(() => validateFreezeRow({
  frozen_at: "2026-11-13T08:00:00+01:00",
  history_cutoff: "2026-11-13"
}, "2026-11-13", archiveDates), /not prior to target/);

assert.equal(exactSignFlipGreater([1, -1]), 0.5);
assert.equal(exactSignFlipGreater([1, 1]), 0.25);
const pmf = hypergeometricTop20Pmf();
assert.ok(Math.abs(pmf.reduce((a, b) => a + b, 0) - 1) < 1e-12);
assert.ok(exactUniformUpperTail(19, 7) > 0 && exactUniformUpperTail(19, 7) < 1);
assert.deepEqual(
  circularBlockBootstrapCI([1, 0, 1, -1, 1, 0, 1], 14401),
  circularBlockBootstrapCI([1, 0, 1, -1, 1, 0, 1], 14401)
);
const adjusted = holmAdjust({ a: 0.01, b: 0.04, c: 0.2 });
assert.equal(adjusted.a, 0.03);
assert.equal(adjusted.b, 0.08);
assert.equal(adjusted.c, 0.2);

process.stdout.write("Q144 unit tests passed: 11 assertions\n");
