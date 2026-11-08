#!/usr/bin/env node
/**
 * SONAR PSR-02: previous-draw odd-count-conditioned positional residual frequencies.
 * Expanding-window walk-forward with a fixed prior-shrinkage alpha; no target leakage.
 * Exploratory only; not an engine replacement.
 */
import fs from "node:fs";
import path from "node:path";
const input = process.argv[2] ?? "data/storico_daily.csv";
const outDir = process.argv[3] ?? "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR02_WARMUP ?? 300);
const alpha = Number(process.env.SONAR_PSR02_ALPHA ?? 100);
const bootstrapReplicates = Number(process.env.SONAR_PSR02_BOOTSTRAP ?? 2000);
const blockLength = Number(process.env.SONAR_PSR02_BLOCK ?? 7);
const seedBase = Number(process.env.SONAR_PSR02_SEED ?? 20261108);
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
      nums.some((n, j) => j > 0 && n <= nums[j - 1])) throw new Error(`Invalid sorted five-number draw at CSV row ${i + 2}: ${line}`);
  return { date, nums };
});
for (let i = 1; i < rows.length; i++) if (rows[i].date <= rows[i - 1].date) throw new Error(`Dates not strictly increasing: ${rows[i - 1].date}, ${rows[i].date}`);
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
const domains = [], priors = [], priorModes = [];
for (let p = 1; p <= 5; p++) {
  const domain = Array.from({ length: 36 }, (_, i) => i + p);
  const prior = domain.map((n) => choose(n - 1, p - 1) * choose(40 - n, 5 - p) / totalComb);
  const sum = prior.reduce((a, b) => a + b, 0);
  if (Math.abs(sum - 1) > 1e-10) throw new Error(`Order-statistic prior P${p} sums to ${sum}`);
  domains.push(domain); priors.push(prior);
  let best = 0;
  for (let i = 1; i < prior.length; i++) if (prior[i] > prior[best] + 1e-15) best = i;
  priorModes.push(domain[best]);
}
const argmax = (values, domain) => {
  let best = 0;
  for (let i = 1; i < values.length; i++) if (values[i] > values[best] + 1e-15) best = i;
  return domain[best];
};
const brier = (prob, idx) => prob.reduce((s, q, i) => s + (q - (i === idx ? 1 : 0)) ** 2, 0);
const logloss = (prob, idx) => -Math.log(Math.max(prob[idx], 1e-15));
const oddCount = (draw) => draw.nums.reduce((s, n) => s + (n % 2), 0);
const stateOfOddCount = (count) => count <= 1 ? 0 : count <= 3 ? 1 : 2;
const stateLabel = ["ODD_0_1", "ODD_2_3", "ODD_4_5"];
const detail = [];
for (let t = warmup; t < rows.length; t++) {
  const globalCounts = Array.from({ length: 5 }, (_, p) => Array(domains[p].length).fill(0));
  const stateCounts = Array.from({ length: 3 }, () => Array.from({ length: 5 }, (_, p) => Array(domains[p].length).fill(0)));
  const stateTotals = [0, 0, 0];
  for (let j = 1; j < t; j++) {
    const st = stateOfOddCount(oddCount(rows[j - 1]));
    stateTotals[st]++;
    for (let p = 0; p < 5; p++) {
      const value = rows[j].nums[p], idx = value - domains[p][0];
      if (idx < 0 || idx >= domains[p].length) throw new Error(`Training value outside position domain P${p + 1}: ${value}`);
      globalCounts[p][idx]++;
      stateCounts[st][p][idx]++;
    }
  }
  const currentOdd = oddCount(rows[t - 1]);
  const currentState = stateOfOddCount(currentOdd);
  const target = rows[t], globalN = t - 1;
  for (let p = 0; p < 5; p++) {
    const domain = domains[p], prior = priors[p], stateN = stateTotals[currentState];
    const globalProb = globalCounts[p].map((c, i) => (c + alpha * prior[i]) / (globalN + alpha));
    const stateProb = stateCounts[currentState][p].map((c, i) => (c + alpha * prior[i]) / (stateN + alpha));
    const actual = target.nums[p], actualIdx = actual - domain[0];
    const globalPick = argmax(globalProb, domain), statePick = argmax(stateProb, domain), priorPick = priorModes[p];
    const brierGlobal = brier(globalProb, actualIdx), brierState = brier(stateProb, actualIdx), brierPrior = brier(prior, actualIdx);
    const logGlobal = logloss(globalProb, actualIdx), logState = logloss(stateProb, actualIdx), logPrior = logloss(prior, actualIdx);
    detail.push({
      date: target.date, target_index: t, train_n: globalN, position: p + 1,
      state_cutoff_date: rows[t - 1].date, previous_draw_odd_count: currentOdd,
      current_state: stateLabel[currentState], state_training_n: stateN, global_training_n: globalN,
      actual, state_top1_pick: statePick, state_top1_hit: statePick === actual,
      global_top1_pick: globalPick, global_top1_hit: globalPick === actual,
      prior_mode_pick: priorPick, prior_mode_hit: priorPick === actual,
      state_top1_hit_delta_vs_global: Number(statePick === actual) - Number(globalPick === actual),
      state_top1_hit_delta_vs_prior: Number(statePick === actual) - Number(priorPick === actual),
      brier_global: brierGlobal, brier_state: brierState, brier_prior: brierPrior,
      brier_improvement_vs_global: brierGlobal - brierState,
      brier_improvement_vs_prior: brierPrior - brierState,
      logloss_global: logGlobal, logloss_state: logState, logloss_prior: logPrior,
      logloss_improvement_vs_global: logGlobal - logState,
      logloss_improvement_vs_prior: logPrior - logState
    });
  }
}
const testN = rows.length - warmup;
const splitEnd = { discovery: Math.floor(testN * 0.5), validation: Math.floor(testN * 0.75), blind_oos: testN };
const splitOf = (targetIndex) => {
  const j = targetIndex - warmup;
  return j < splitEnd.discovery ? "discovery" : j < splitEnd.validation ? "validation" : "blind_oos";
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
  const observed = mean(values), rngCi = mulberry32(seed);
  const ciMeans = Array.from({ length: bootstrapReplicates }, () => circularBlockMean(values, rngCi, blockLength));
  const centered = values.map((v) => v - observed), rngNull = mulberry32(seed ^ 0x9E3779B9);
  const nullMeans = Array.from({ length: bootstrapReplicates }, () => circularBlockMean(centered, rngNull, blockLength));
  const tail = nullMeans.filter((v) => v >= observed).length;
  return { n: values.length, mean_improvement: observed, ci95_low: quantile(ciMeans, 0.025), ci95_high: quantile(ciMeans, 0.975),
    p_one_sided_raw: (tail + 1) / (bootstrapReplicates + 1), bootstrap_replicates: bootstrapReplicates, block_length: blockLength,
    method: "circular moving-block bootstrap; null centered on zero; one-sided benefit test" };
}
const summary = [], inferential = [];
for (let p = 1; p <= 5; p++) for (const split of ["discovery", "validation", "blind_oos"]) {
  const rs = detail.filter((r) => r.position === p && r.split === split);
  const metric = (key) => mean(rs.map((r) => r[key]));
  summary.push({
    position: p, split, n: rs.length, first_target: rs[0]?.date, last_target: rs.at(-1)?.date,
    mean_state_training_n: metric("state_training_n"),
    state_top1_hit_rate: metric("state_top1_hit"), global_top1_hit_rate: metric("global_top1_hit"), prior_mode_hit_rate: metric("prior_mode_hit"),
    state_top1_delta_vs_global: metric("state_top1_hit_delta_vs_global"), state_top1_delta_vs_prior: metric("state_top1_hit_delta_vs_prior"),
    mean_brier_global: metric("brier_global"), mean_brier_state: metric("brier_state"), mean_brier_prior: metric("brier_prior"),
    brier_improvement_vs_global: metric("brier_improvement_vs_global"), brier_improvement_vs_prior: metric("brier_improvement_vs_prior"),
    mean_logloss_global: metric("logloss_global"), mean_logloss_state: metric("logloss_state"), mean_logloss_prior: metric("logloss_prior"),
    logloss_improvement_vs_global: metric("logloss_improvement_vs_global"), logloss_improvement_vs_prior: metric("logloss_improvement_vs_prior")
  });
  if (split === "blind_oos") inferential.push({ position: p, endpoint: "brier_improvement_vs_global",
    endpoint_label: "State-conditioned Brier improvement vs global empirical shrinkage",
    ...bootstrapInference(rs.map((r) => r.brier_improvement_vs_global), seedBase + p * 2027) });
}
const sorted = inferential.filter((x) => Number.isFinite(x.p_one_sided_raw)).sort((a, b) => a.p_one_sided_raw - b.p_one_sided_raw);
let running = 0;
for (let i = 0; i < sorted.length; i++) { running = Math.max(running, Math.min(1, (sorted.length - i) * sorted[i].p_one_sided_raw)); sorted[i].p_holm_family5 = running; }
for (const x of inferential) if (x.p_holm_family5 === undefined) x.p_holm_family5 = null;
fs.mkdirSync(outDir, { recursive: true });
const detailPath = path.join(outDir, "psr02_walkforward_detail.csv"), fields = Object.keys(detail[0]);
fs.writeFileSync(detailPath, [fields.join(","), ...detail.map((r) => fields.map((k) => r[k]).join(","))].join("\n") + "\n");
const summaryPath = path.join(outDir, "psr02_walkforward_summary.json");
const result = {
  experiment: "PSR-02", generated_at_utc: new Date().toISOString(),
  data_file: input, archive_draws: rows.length, archive_first_date: rows[0].date, archive_last_date: rows.at(-1).date,
  warmup, test_n: testN, split_definition: "chronological target sequence: discovery first 50%, validation next 25%, final blind OOS 25%; fixed alpha, no validation tuning",
  model: {
    hypothesis: "previous-draw odd-count state may condition position-wise marginal residual frequencies beyond global shrinkage",
    state_bins: [{state:0,odd_count:[0,1]},{state:1,odd_count:[2,3]},{state:2,odd_count:[4,5]}],
    posterior_formula: "q_i,t(n|s)=[c_i,t,s(n)+alpha*pi_i(n)]/[N_t,s+alpha]",
    alpha, prior: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5); domain i..35+i",
    baseline: "same strict-prior target rows with global position frequency and identical alpha shrinkage",
    primary_endpoint: "blind OOS per-position Brier improvement versus global empirical shrinkage; Holm across five positions",
    secondary: ["Top1 hit-rate deltas vs global and exact prior mode","Brier and log-loss versus exact order-statistic prior","log-loss improvement versus global shrinkage"]
  },
  split_boundaries: splitEnd, summary, blind_oos_inference: inferential,
  multiple_testing: "Holm step-down across 5 blind-OOS position-level primary Brier endpoints; secondary metrics descriptive",
  caveats: [
    "Position marginals are dependent because draws are sorted; no joint five-number ticket is built.",
    "Previous-draw odd-count state is a fixed conditioning hypothesis, not evidence of causal dependence.",
    "Historical blind slice overlaps earlier SONAR exploratory research; this is not independent prospective evidence.",
    "No guarantee or promotion; Q60 prospective frozen gate remains required."
  ]
};
fs.writeFileSync(summaryPath, JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ summaryPath, detailPath, archive_draws: rows.length, test_n: testN, split_boundaries: splitEnd, blind_oos_inference: inferential }, null, 2));
