#!/usr/bin/env node
/**
 * SONAR Position-Specific Range & Residual Lab (PSR-01)
 * Expanding-window walk-forward; five ordered positions fitted separately.
 * No future leakage: range and frequency profile use only draws before target.
 */
import fs from "node:fs";
import path from "node:path";

const input = process.argv[2] ?? "data/storico_daily.csv";
const outDir = process.argv[3] ?? "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR_WARMUP ?? 250);
const rows = fs.readFileSync(input, "utf8").trim().split(/\r?\n/).slice(1).map((line) => {
  const [date, ...nums] = line.split(",");
  return { date, nums: nums.map(Number) };
}).filter((r) => r.nums.length === 5 && r.nums.every((n) => Number.isInteger(n) && n >= 1 && n <= 40));

if (rows.length <= warmup) throw new Error(`Need > ${warmup} valid rows; got ${rows.length}`);
fs.mkdirSync(outDir, { recursive: true });

const results = [];
for (let t = warmup; t < rows.length; t++) {
  const train = rows.slice(0, t);
  const actual = rows[t];
  const positions = [];
  for (let p = 0; p < 5; p++) {
    const hist = train.map((r) => r.nums[p]);
    const min = Math.min(...hist);
    const max = Math.max(...hist);
    const range = max - min + 1;
    const counts = new Map();
    for (const n of hist) if (n >= min && n <= max) counts.set(n, (counts.get(n) ?? 0) + 1);
    // Deterministic tie-break: smaller number first. This is a transparent
    // frequency-only candidate, not asserted to be a causal forecast.
    const ranked = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0] - b[0]);
    const pick = ranked[0]?.[0] ?? min;
    const y = actual.nums[p];
    positions.push({
      position: p + 1, train_n: t, train_min: min, train_max: max, range_width: range,
      actual: y, within_train_range: y >= min && y <= max,
      frequency_pick: pick, frequency_pick_hit: pick === y,
      frequency_pick_count: counts.get(pick) ?? 0,
      empirical_frequency: (counts.get(pick) ?? 0) / hist.length,
      uniform_within_range_probability: 1 / range
    });
  }
  results.push({ date: actual.date, positions });
}

const summary = [];
for (let p = 1; p <= 5; p++) {
  const rs = results.map((r) => r.positions[p - 1]);
  summary.push({
    position: p, test_n: rs.length,
    historical_range_coverage: rs.filter((r) => r.within_train_range).length / rs.length,
    frequency_top1_hit_rate: rs.filter((r) => r.frequency_pick_hit).length / rs.length,
    mean_range_width: rs.reduce((s, r) => s + r.range_width, 0) / rs.length,
    mean_uniform_within_range_probability: rs.reduce((s, r) => s + r.uniform_within_range_probability, 0) / rs.length,
    max_range_escape_count: rs.filter((r) => !r.within_train_range).length
  });
}

const detailPath = path.join(outDir, "psr01_walkforward_detail.csv");
const fields = ["date","position","train_n","train_min","train_max","range_width","actual","within_train_range","frequency_pick","frequency_pick_hit","frequency_pick_count","empirical_frequency","uniform_within_range_probability"];
const lines = [fields.join(",")];
for (const r of results) for (const p of r.positions) lines.push(fields.map((k) => p[k] === undefined ? r.date : p[k]).join(","));
fs.writeFileSync(detailPath, lines.join("\n") + "\n");
const summaryPath = path.join(outDir, "psr01_walkforward_summary.json");
fs.writeFileSync(summaryPath, JSON.stringify({
  experiment: "PSR-01",
  method: "expanding-window position-specific historical min/max range plus within-range frequency Top-1",
  data_file: input, valid_draws: rows.length, warmup, test_n: results.length,
  first_test_date: results[0]?.date, last_test_date: results.at(-1)?.date,
  summary, caveats: [
    "Historical extrema are estimated from past-only training data and are not guaranteed future bounds.",
    "Five ordered positions are dependent; this run evaluates each marginal position separately.",
    "Frequency Top-1 is a baseline candidate only; no promotion, significance claim, or combined five-number ticket is implied."
  ]
}, null, 2) + "\n");
console.log(JSON.stringify({ summaryPath, detailPath, summary }, null, 2));
