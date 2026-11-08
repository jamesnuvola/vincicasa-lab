#!/usr/bin/env node
/**
 * SONAR PSR-01: position-specific historical range + prior-shrunk residual frequency.
 * Expanding-window walk-forward. All target features use only rows strictly before target.
 * Candidate is research-only; no motor replacement or promotion.
 */
import fs from "node:fs";
import path from "node:path";

const input = process.argv[2] ?? "data/storico_daily.csv";
const outDir = process.argv[3] ?? "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR_WARMUP ?? 250);
const alpha = Number(process.env.SONAR_PSR_ALPHA ?? 20);
const bootstrapReplicates = Number(process.env.SONAR_PSR_BOOTSTRAP ?? 2000);
const blockLength = Number(process.env.SONAR_PSR_BLOCK ?? 7);
const seedBase = Number(process.env.SONAR_PSR_SEED ?? 20261108);

if (!Number.isInteger(warmup) || warmup < 50) throw new Error("warmup must be an integer >= 50");
if (!(alpha > 0) || !Number.isFinite(alpha)) throw new Error("alpha must be finite and > 0");
if (!Number.isInteger(bootstrapReplicates) || bootstrapReplicates < 100) throw new Error("bootstrap replicates must be >= 100");
if (!Number.isInteger(blockLength) || blockLength < 1) throw new Error("block length must be >= 1");

const raw = fs.readFileSync(input, "utf8").trim().split(/\r?\n/);
if (raw.length < 2 || raw[0].trim() !== "data,n1,n2,n3,n4,n5") throw new Error("Unexpected canonical CSV header");
const rows = raw.slice(1).map((line, i) => {
  const [date, ...cells] = line.split(",");
  const nums = cells.map(Number);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || nums.length !== 5 ||
      nums.some((n) => !Number.isInteger(n) || n < 1 || n > 40) ||
      nums.some((n, j) => j > 0 && n <= nums[j - 1])) {
    throw new Error(`Invalid sorted five-number draw at CSV row ${i + 2}: ${line}`);
  }
  return { date, nums };
});
for (let i = 1; i < rows.length; i++) {
  if (rows[i].date <= rows[i - 1].date) throw new Error(`Dates not strictly increasing: ${rows[i - 1].date}, ${rows[i].date}`);
}
if (rows.length <= warmup + 20) throw new Error(`Need > warmup+20 valid rows; got ${rows.length}`);

const choose = (n, k) => {
  if (k < 0 || n < k || n < 0) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let v = 1;
  for (let i = 1; i <= k; i++) v = v * (n - k + i) / i;
  return v;
};
const totalComb = choose(40, 5);
const priorByPosition = [];
const domainByPosition = [];
const priorModeByPosition = [];
for (let p = 1; p <= 5; p++) {
  const domain = Array.from({ length: 36 }, (_, i) => i + p); // README: Pp range p..35+p
  const prior = domain.map((n) => choose(n - 1, p - 1) * choose(40 - n, 5 - p) / totalComb);
  const sum = prior.reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1) > 1e-10) throw new Error(`Order-statistic prior P${p} sums to ${sum}`);
  domainByPosition.push(domain);
  priorByPosition.push(prior);
  let modeIdx = 0;
  for (let i = 1; i < prior.length; i++) if (prior[i] > prior[modeIdx] + 1e-15) modeIdx = i;
  priorModeByPosition.push(domain[modeIdx]);
}

const argmaxLowerTie = (values, domain) => {
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] > values[best] + 1e-15) best = i;
  return domain[best];
};
const brier = (prob, actualIdx) => prob.reduce((s, q, i) => s + (q - (i === actualIdx ? 1 : 0)) ** 2, 0);
const logloss = (prob, actualIdx) => -Math.log(Math.max(prob[actualIdx], 1e-15));

const detail = [];
for (let t = warmup; t < rows.length; t++) {
  const train = rows.slice(0, t); // strict prefix; excludes target and all future
  const target = rows[t];
  for (let p = 0; p < 5; p++) {
    const domain = domainByPosition[p];
    const prior = priorByPosition[p];
    const counts = Array(domain.length).fill(0);
    let trainMin = 40, trainMax = 1;
    for (const draw of train) {
      const value = draw.nums[p];
      trainMin = Math.min(trainMin, value);
      trainMax = Math.max(trainMax, value);
      const idx = value - domain[0];
      if (idx < 0 || idx >= domain.length) throw new Error(`Training value outside valid position domain P${p + 1}: ${value}`);
      counts[idx]++;
    }
    const posterior = counts.map((c, i) => (c + alpha * prior[i]) / (train.length + alpha));
    const actual = target.nums[p];
    const actualIdx = actual - domain[0];
    const empiricalPick = argmaxLowerTie(counts, domain);
    const posteriorPick = argmaxLowerTie(posterior, domain);
    const priorPick = priorModeByPosition[p];
    const baseBrier = brier(prior, actualIdx);
    const modelBrier = brier(posterior, actualIdx);
    const baseLogloss = logloss(prior, actualIdx);
    const modelLogloss = logloss(posterior, actualIdx);
    const expectedRangeCoverage = prior.reduce((sum, q, i) => {
      const n = domain[i];
      return sum + (n >= trainMin && n <= trainMax ? q : 0);
    }, 0);
    detail.push({
      date: target.date, target_index: t, position: p + 1, train_n: train.length,
      train_min: trainMin, train_max: trainMax, train_range_width: trainMax - trainMin + 1,
      actual, within_past_minmax: actual >= trainMin && actual <= trainMax,
      expected_past_minmax_coverage: expectedRangeCoverage,
      expected_range_escape_probability: 1 - expectedRangeCoverage,
      range_coverage_residual: Number(actual >= trainMin && actual <= trainMax) - expectedRangeCoverage,
      empirical_mode_pick: empiricalPick, empirical_mode_hit: empiricalPick === actual,
      posterior_mode_pick: posteriorPick, posterior_mode_hit: posteriorPick === actual,
      theoretical_mode_pick: priorPick, theoretical_mode_hit: priorPick === actual,
      empirical_mode_hit_delta: Number(empiricalPick === actual) - Number(priorPick === actual),
      posterior_mode_hit_delta: Number(posteriorPick === actual) - Number(priorPick === actual),
      brier_baseline: baseBrier, brier_posterior: modelBrier, brier_improvement: baseBrier - modelBrier,
      logloss_baseline: baseLogloss, logloss_posterior: modelLogloss, logloss_improvement: baseLogloss - modelLogloss
    });
  }
}
const testN = rows.length - warmup;
const splitEnd = { discovery: Math.floor(testN * 0.5), validation: Math.floor(testN * 0.75), blind_oos: testN };
const splitOf = (targetIndex) => {
  const j = targetIndex - warmup;
  if (j < splitEnd.discovery) return "discovery";
  if (j < splitEnd.validation) return "validation";
  return "blind_oos";
};
for (const r of detail) r.split = splitOf(r.target_index);

function mulberry32(seed) {
  let a = seed >>> 0;
  return function() {
    a += 0x6D2B79F5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14) >>> 0) >>> 0) / 4294967296;
  };
}
const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length;
const quantile = (a, q) => {
  const sorted = [...a].sort((x, y) => x - y);
  const h = (sorted.length - 1) * q, lo = Math.floor(h), hi = Math.ceil(h);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (h - lo);
};
function circularBlockMean(sample, rng, block) {
  let sum = 0, count = 0;
  while (count < sample.length) {
    const start = Math.floor(rng() * sample.length);
    for (let j = 0; j < block && count < sample.length; j++, count++) sum += sample[(start + j) % sample.length];
  }
  return sum / sample.length;
}
function bootstrapInference(values, seed) {
  if (values.length < 30) return { n: values.length, mean_improvement: mean(values), ci95_low: null, ci95_high: null, p_one_sided_raw: null, note: "blind OOS n<30; inference withheld" };
  const observed = mean(values);
  const rngCi = mulberry32(seed);
  const ciMeans = Array.from({ length: bootstrapReplicates }, () => circularBlockMean(values, rngCi, blockLength));
  const centered = values.map((v) => v - observed);
  const rngNull = mulberry32(seed ^ 0x9E3779B9);
  const nullMeans = Array.from({ length: bootstrapReplicates }, () => circularBlockMean(centered, rngNull, blockLength));
  const tail = nullMeans.filter((v) => v >= observed).length;
  return {
    n: values.length, mean_improvement: observed,
    ci95_low: quantile(ciMeans, 0.025), ci95_high: quantile(ciMeans, 0.975),
    p_one_sided_raw: (tail + 1) / (bootstrapReplicates + 1),
    bootstrap_replicates: bootstrapReplicates, block_length: blockLength,
    method: "circular moving-block bootstrap; null centered on zero; one-sided benefit test"
  };
}
const endpointDefs = [
  ["empirical_mode_hit_delta", "Empirical-frequency Top1 hit-rate delta vs order-statistic mode"],
  ["posterior_mode_hit_delta", "Prior-shrunk posterior Top1 hit-rate delta vs order-statistic mode"],
  ["brier_improvement", "Brier score improvement vs theoretical order-statistic prior"],
  ["logloss_improvement", "Log loss improvement vs theoretical order-statistic prior"]
];
const summary = [];
const inferential = [];
for (let p = 1; p <= 5; p++) {
  for (const split of ["discovery", "validation", "blind_oos"]) {
    const rs = detail.filter((r) => r.position === p && r.split === split);
    const n = rs.length;
    const metric = (key) => mean(rs.map((r) => r[key]));
    summary.push({
      position: p, split, n, first_target: rs[0]?.date, last_target: rs.at(-1)?.date,
      past_minmax_coverage: metric("within_past_minmax"),
      mean_expected_past_minmax_coverage: metric("expected_past_minmax_coverage"),
      mean_expected_range_escape_probability: metric("expected_range_escape_probability"),
      mean_range_coverage_residual: metric("range_coverage_residual"),
      mean_past_range_width: metric("train_range_width"),
      empirical_mode_hit_rate: metric("empirical_mode_hit"),
      posterior_mode_hit_rate: metric("posterior_mode_hit"),
      theoretical_mode_hit_rate: metric("theoretical_mode_hit"),
      empirical_mode_hit_delta: metric("empirical_mode_hit_delta"),
      posterior_mode_hit_delta: metric("posterior_mode_hit_delta"),
      mean_brier_baseline: metric("brier_baseline"), mean_brier_posterior: metric("brier_posterior"),
      mean_brier_improvement: metric("brier_improvement"),
      mean_logloss_baseline: metric("logloss_baseline"), mean_logloss_posterior: metric("logloss_posterior"),
      mean_logloss_improvement: metric("logloss_improvement")
    });
    if (split === "blind_oos") for (let m = 0; m < endpointDefs.length; m++) {
      const [key, label] = endpointDefs[m];
      const values = rs.map((r) => r[key]);
      inferential.push({ position: p, endpoint: key, endpoint_label: label,
        ...bootstrapInference(values, seedBase + p * 1009 + m * 9176) });
    }
  }
}
function holmAdjust(items) {
  const valid = items.filter((x) => Number.isFinite(x.p_one_sided_raw)).sort((a, b) => a.p_one_sided_raw - b.p_one_sided_raw);
  let running = 0;
  for (let i = 0; i < valid.length; i++) {
    const adj = Math.min(1, (valid.length - i) * valid[i].p_one_sided_raw);
    running = Math.max(running, adj);
    valid[i].p_holm_family20 = running;
  }
  for (const x of items) if (x.p_holm_family20 === undefined) x.p_holm_family20 = null;
}
holmAdjust(inferential);

fs.mkdirSync(outDir, { recursive: true });
const detailPath = path.join(outDir, "psr01_walkforward_detail.csv");
const fields = Object.keys(detail[0]);
fs.writeFileSync(detailPath, [fields.join(","), ...detail.map((r) => fields.map((k) => r[k]).join(","))].join("\n") + "\n");
const summaryPath = path.join(outDir, "psr01_walkforward_summary.json");
const result = {
  experiment: "PSR-01",
  generated_at_utc: new Date().toISOString(),
  data_file: input, archive_draws: rows.length, archive_first_date: rows[0].date, archive_last_date: rows.at(-1).date,
  warmup, test_n: testN, split_definition: "chronological target sequence: discovery first 50%, validation next 25%, final blind OOS 25%; no split tuning",
  model: {
    hypothesis: "past-only position-specific extrema plus historical marginal frequency may improve ordered-position prediction over exact combinatorial order-statistic prior",
    posterior_formula: "q_i(n|t) = [c_i,t(n) + alpha*pi_i(n)] / [N_t + alpha]",
    alpha, prior: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5); domain i..35+i",
    candidates: ["empirical-frequency mode", "prior-shrunk posterior mode", "posterior probability distribution scored by Brier and log loss"],
    range: "L_i(t)=min P_i(s), U_i(t)=max P_i(s), s<t; range is diagnostic coverage only, not treated as a guaranteed future bound"
  },
  split_boundaries: splitEnd,
  summary,
  blind_oos_inference: inferential,
  multiple_testing: "Holm step-down correction over 20 blind-OOS endpoints (5 positions × 4 candidate metrics); discovery/validation are descriptive and not used for significance or tuning",
  caveats: [
    "Position marginals are dependent because each draw is sorted; this experiment scores marginal positions only and does not construct a valid joint five-number ticket.",
    "Historical min/max are empirical and may be escaped by future draws.",
    "Theoretical order-statistic prior is the exact uniform-combination marginal, not an empirically fitted baseline.",
    "Results do not establish predictability or guarantee any lottery outcome; candidate is exploratory and not eligible for motor promotion absent independent prospective evidence."
  ]
};
fs.writeFileSync(summaryPath, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ summaryPath, detailPath, archive_draws: rows.length, test_n: testN, split_boundaries: splitEnd, blind_oos_inference: inferential }, null, 2));
