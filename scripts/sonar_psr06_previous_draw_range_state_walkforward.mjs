#!/usr/bin/env node
/**
 * SONAR PSR-06: condition each next ordered-position marginal on the exact
 * theoretical range-quartile state of the immediately preceding draw.
 * Strict expanding-prefix walk-forward; alpha chosen only on validation.
 * Exploratory research; never promotes or replaces the active engine.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const input = process.argv[2] ?? "data/storico_daily.csv";
const outDir = process.argv[3] ?? "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR06_WARMUP ?? 300);
const alphaGrid = [50, 100, 200, 500];
const B = Number(process.env.SONAR_PSR06_BOOTSTRAP ?? 2000);
const block = Number(process.env.SONAR_PSR06_BLOCK ?? 7);
const seedBase = Number(process.env.SONAR_PSR06_SEED ?? 20261108);
const expectedSha = process.env.SONAR_PSR06_EXPECTED_ARCHIVE_BLOB_SHA ?? "5d2efd70684e918b27d8f06386d545647898336d";
if (!Number.isInteger(warmup) || warmup < 50 || !Number.isInteger(B) || B < 100 ||
    !Number.isInteger(block) || block < 1 || !Number.isInteger(seedBase)) throw new Error("Invalid PSR-06 parameters");

const csv = fs.readFileSync(input, "utf8");
const gitBlobSha = crypto.createHash("sha1").update(Buffer.from("blob " + Buffer.byteLength(csv) + "\0")).update(Buffer.from(csv)).digest("hex");
if (expectedSha && gitBlobSha !== expectedSha) throw new Error("Archive Git blob SHA mismatch: expected " + expectedSha + ", got " + gitBlobSha);
const lines = csv.trim().split(/\r?\n/);
if (lines.length < 2 || lines[0].trim() !== "data,n1,n2,n3,n4,n5") throw new Error("Bad canonical CSV header");
const rows = lines.slice(1).map((line, i) => {
  const c = line.split(","), date = c[0], nums = c.slice(1).map(Number);
  if (c.length !== 6 || !/^\d{4}-\d{2}-\d{2}$/.test(date) || nums.length !== 5 ||
      nums.some(n => !Number.isInteger(n) || n < 1 || n > 40) || new Set(nums).size !== 5 ||
      nums.some((n, j) => j > 0 && n <= nums[j - 1])) throw new Error("Invalid sorted draw at CSV row " + (i + 2));
  return { date, nums, range: nums[4] - nums[0] };
});
for (let i = 1; i < rows.length; i++) if (rows[i].date <= rows[i - 1].date) throw new Error("Dates not strictly increasing");
if (rows.length <= warmup + 20) throw new Error("Insufficient canonical rows");

const choose = (n, k) => {
  if (k < 0 || n < k || n < 0) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let v = 1;
  for (let i = 1; i <= k; i++) v = v * (n - k + i) / i;
  return v;
};
// Exact range distribution of a uniform 5-subset: Pr(R=r)=(40-r)C(r-1,3)/C(40,5).
const totalComb = choose(40, 5), rangeCounts = [];
let rangeTotal = 0;
for (let r = 4; r <= 39; r++) {
  const count = (40 - r) * choose(r - 1, 3);
  rangeCounts.push({ range: r, count }); rangeTotal += count;
}
if (rangeTotal !== totalComb) throw new Error("Exact range-distribution normalization failure");
const cuts = [];
for (const q of [0.25, 0.5, 0.75]) {
  let cumulative = 0, cut = null;
  for (const item of rangeCounts) { cumulative += item.count; if (cumulative >= rangeTotal * q) { cut = item.range; break; } }
  if (cut === null) throw new Error("Range quantile failure");
  cuts.push(cut);
}
if (cuts.join(",") !== "23,28,33") throw new Error("Unexpected theoretical range quartile cutpoints: " + cuts.join(","));
const stateOf = r => r <= cuts[0] ? 0 : r <= cuts[1] ? 1 : r <= cuts[2] ? 2 : 3;
const stateLabels = ["RANGE_Q1_LOW_R<=23", "RANGE_Q2_R=24..28", "RANGE_Q3_R=29..33", "RANGE_Q4_HIGH_R>=34"];
const stateMass = [0, 0, 0, 0];
for (const item of rangeCounts) stateMass[stateOf(item.range)] += item.count / totalComb;

const domains = [], priors = [], priorModes = [];
for (let p = 1; p <= 5; p++) {
  const domain = Array.from({ length: 36 }, (_, i) => i + p);
  const prior = domain.map(n => choose(n - 1, p - 1) * choose(40 - n, 5 - p) / totalComb);
  if (Math.abs(prior.reduce((s, q) => s + q, 0) - 1) > 1e-10) throw new Error("Order-statistic prior normalization failure P" + p);
  let mode = 0;
  for (let i = 1; i < 36; i++) if (prior[i] > prior[mode] + 1e-15) mode = i;
  domains.push(domain); priors.push(prior); priorModes.push(mode);
}
const argmax = a => { let best = 0; for (let i = 1; i < a.length; i++) if (a[i] > a[best] + 1e-15) best = i; return best; };
const score = (prob, actualIndex) => {
  let brier = 0;
  for (let i = 0; i < 36; i++) brier += (prob[i] - (i === actualIndex ? 1 : 0)) ** 2;
  const order = prob.map((q, i) => ({ q, i })).sort((a, b) => b.q - a.q || a.i - b.i);
  const rank = order.findIndex(o => o.i === actualIndex) + 1;
  return { brier, logloss: -Math.log(Math.max(prob[actualIndex], 1e-15)), rank,
    top1: rank <= 1, top5: rank <= 5, top10: rank <= 10, top20: rank <= 20 };
};

const globalCounts = Array.from({ length: 5 }, () => Array(36).fill(0));
const stateCounts = Array.from({ length: 5 }, () => Array.from({ length: 4 }, () => Array(36).fill(0)));
const stateN = Array(4).fill(0);
let trainN = 0;
const addTrainingTarget = j => {
  if (j < 2 || j >= rows.length) throw new Error("Invalid training target index " + j);
  const st = stateOf(rows[j - 1].range); trainN++; stateN[st]++;
  for (let p = 0; p < 5; p++) {
    const yi = rows[j].nums[p] - domains[p][0];
    if (yi < 0 || yi >= 36) throw new Error("Position support failure P" + (p + 1));
    globalCounts[p][yi]++; stateCounts[p][st][yi]++;
  }
};
for (let j = 2; j < warmup; j++) addTrainingTarget(j);

const testN = rows.length - warmup, discoveryEnd = Math.floor(testN * 0.5), validationEnd = Math.floor(testN * 0.75);
const splitOf = t => t - warmup < discoveryEnd ? "discovery" : t - warmup < validationEnd ? "validation" : "blind_oos";
const splitCounts = { discovery: discoveryEnd, validation: validationEnd - discoveryEnd, blind_oos: testN - validationEnd };
const splitDates = {
  discovery: [rows[warmup].date, rows[warmup + discoveryEnd - 1].date],
  validation: [rows[warmup + discoveryEnd].date, rows[warmup + validationEnd - 1].date],
  blind_oos: [rows[warmup + validationEnd].date, rows.at(-1).date]
};
const grid = [];
for (let t = warmup; t < rows.length; t++) {
  if (trainN !== t - 2) throw new Error("Strict-prefix train_n=t-2 failure at target index " + t + ": " + trainN);
  if (rows[t - 1].date >= rows[t].date) throw new Error("Target/cutoff chronology failure at " + t);
  const st = stateOf(rows[t - 1].range), nState = stateN[st], split = splitOf(t);
  if (nState < 0 || nState > trainN) throw new Error("State training size invalid");
  for (let p = 0; p < 5; p++) {
    const domain = domains[p], prior = priors[p], actual = rows[t].nums[p], ai = actual - domain[0];
    for (const alpha of alphaGrid) {
      const gp = globalCounts[p].map((c, i) => (c + alpha * prior[i]) / (trainN + alpha));
      const sp = stateCounts[p][st].map((c, i) => (c + alpha * prior[i]) / (nState + alpha));
      const g = score(gp, ai), s = score(sp, ai), pr = score(prior, ai);
      if (Math.abs(sp.reduce((a, q) => a + q, 0) - 1) > 1e-10) throw new Error("Conditional probability normalization failure");
      grid.push({
        date: rows[t].date, target_index: t, cutoff_date: rows[t - 1].date, split, position: p + 1,
        previous_draw_range: rows[t - 1].range, range_state: stateLabels[st], state_training_n: nState, global_training_n: trainN, alpha, actual,
        state_pick: domain[argmax(sp)], global_pick: domain[argmax(gp)], prior_pick: domain[priorModes[p]],
        state_rank: s.rank, global_rank: g.rank, prior_rank: pr.rank,
        state_top1: Number(s.top1), global_top1: Number(g.top1), prior_top1: Number(pr.top1),
        state_top5: Number(s.top5), global_top5: Number(g.top5), prior_top5: Number(pr.top5),
        state_top10: Number(s.top10), global_top10: Number(g.top10), prior_top10: Number(pr.top10),
        state_top20: Number(s.top20), global_top20: Number(g.top20), prior_top20: Number(pr.top20),
        state_brier: s.brier, global_brier: g.brier, prior_brier: pr.brier,
        brier_improvement_vs_global: g.brier - s.brier, brier_improvement_vs_prior: pr.brier - s.brier,
        state_logloss: s.logloss, global_logloss: g.logloss, prior_logloss: pr.logloss,
        logloss_improvement_vs_global: g.logloss - s.logloss, logloss_improvement_vs_prior: pr.logloss - s.logloss
      });
    }
  }
  addTrainingTarget(t);
}
const expectedGridN = testN * 5 * alphaGrid.length;
if (grid.length !== expectedGridN) throw new Error("Grid row count mismatch");
const gridKeys = new Set();
for (const r of grid) { const key = r.date + "|" + r.position + "|" + r.alpha; if (gridKeys.has(key)) throw new Error("Duplicate grid key " + key); gridKeys.add(key); }
const mean = a => a.reduce((s, x) => s + x, 0), avg = a => mean(a) / a.length, metric = (rs, key) => avg(rs.map(r => r[key]));
const validationGrid = [], selected = [];
for (let p = 1; p <= 5; p++) {
  const candidates = alphaGrid.map(alpha => {
    const rs = grid.filter(r => r.position === p && r.split === "validation" && r.alpha === alpha);
    return { position: p, alpha, n: rs.length,
      brier_improvement_vs_global: metric(rs, "brier_improvement_vs_global"), brier_improvement_vs_prior: metric(rs, "brier_improvement_vs_prior"),
      logloss_improvement_vs_global: metric(rs, "logloss_improvement_vs_global"), logloss_improvement_vs_prior: metric(rs, "logloss_improvement_vs_prior"),
      top1_delta_vs_global: metric(rs, "state_top1") - metric(rs, "global_top1"), top5_delta_vs_global: metric(rs, "state_top5") - metric(rs, "global_top5"),
      mean_rank_improvement_vs_global: metric(rs, "global_rank") - metric(rs, "state_rank") };
  });
  let best = candidates[0];
  for (const c of candidates.slice(1)) if (c.brier_improvement_vs_global > best.brier_improvement_vs_global + 1e-15 ||
      (Math.abs(c.brier_improvement_vs_global - best.brier_improvement_vs_global) <= 1e-15 && c.alpha < best.alpha)) best = c;
  validationGrid.push({ position: p, candidates });
  selected.push({ position: p, selected_alpha: best.alpha, selection_metric: "validation maximum mean Brier improvement vs global shrinkage with same alpha; tie smaller alpha",
    selected_validation_brier_improvement_vs_global: best.brier_improvement_vs_global });
}
const selectedRows = grid.filter(r => r.alpha === selected[r.position - 1].selected_alpha);
if (selectedRows.length !== testN * 5) throw new Error("Selected target ledger row count mismatch");
const splitMetrics = [];
for (let p = 1; p <= 5; p++) for (const split of ["discovery", "validation", "blind_oos"]) {
  const rs = selectedRows.filter(r => r.position === p && r.split === split);
  splitMetrics.push({ position: p, selected_alpha: selected[p - 1].selected_alpha, split, n: rs.length,
    first_target: rs[0]?.date, last_target: rs.at(-1)?.date, mean_state_training_n: metric(rs, "state_training_n"),
    brier_improvement_vs_global: metric(rs, "brier_improvement_vs_global"), brier_improvement_vs_prior: metric(rs, "brier_improvement_vs_prior"),
    logloss_improvement_vs_global: metric(rs, "logloss_improvement_vs_global"), logloss_improvement_vs_prior: metric(rs, "logloss_improvement_vs_prior"),
    top1_delta_vs_global: metric(rs, "state_top1") - metric(rs, "global_top1"), top1_delta_vs_prior: metric(rs, "state_top1") - metric(rs, "prior_top1"),
    top5_delta_vs_global: metric(rs, "state_top5") - metric(rs, "global_top5"), top5_delta_vs_prior: metric(rs, "state_top5") - metric(rs, "prior_top5"),
    top10_delta_vs_global: metric(rs, "state_top10") - metric(rs, "global_top10"), top20_delta_vs_global: metric(rs, "state_top20") - metric(rs, "global_top20"),
    mean_rank_improvement_vs_global: metric(rs, "global_rank") - metric(rs, "state_rank"), mean_rank_improvement_vs_prior: metric(rs, "prior_rank") - metric(rs, "state_rank") });
}
const rng32 = seed => { let a = seed >>> 0; return () => { a += 0x6D2B79F5; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14) >>> 0) >>> 0) / 4294967296; }; };
const quantile = (a, q) => { const s = [...a].sort((x, y) => x - y), h = (s.length - 1) * q, lo = Math.floor(h), hi = Math.ceil(h); return s[lo] + (s[hi] - s[lo]) * (h - lo); };
const blockMean = (sample, rng) => { let sum = 0, count = 0; while (count < sample.length) { const start = Math.floor(rng() * sample.length); for (let j = 0; j < block && count < sample.length; j++, count++) sum += sample[(start + j) % sample.length]; } return sum / sample.length; };
const rawInference = [];
for (let p = 1; p <= 5; p++) {
  const rs = selectedRows.filter(r => r.position === p && r.split === "blind_oos"), diffs = rs.map(r => r.brier_improvement_vs_global), observed = avg(diffs);
  const ciRng = rng32(seedBase + p * 1009), ci = Array.from({ length: B }, () => blockMean(diffs, ciRng));
  const centered = diffs.map(x => x - observed), nullRng = rng32((seedBase + p * 1009) ^ 0x9E3779B9), nullMeans = Array.from({ length: B }, () => blockMean(centered, nullRng));
  const tail = nullMeans.filter(x => x >= observed - 1e-15).length;
  rawInference.push({ position: p, selected_alpha: selected[p - 1].selected_alpha, n: rs.length, mean_brier_improvement_vs_global: observed,
    ci95: [quantile(ci, 0.025), quantile(ci, 0.975)], p_one_sided_raw: (tail + 1) / (B + 1),
    bootstrap: { type: "circular moving-block bootstrap; paired differences for CI, null-centered one-sided benefit p", block_length: block, replicates: B, seed: seedBase + p * 1009 } });
}
const ordered = rawInference.map((r, i) => ({ p: r.p_one_sided_raw, i })).sort((a, b) => a.p - b.p || a.i - b.i);
const holm = Array(5).fill(1); let running = 0;
for (let i = 0; i < 5; i++) { running = Math.max(running, Math.min(1, (5 - i) * ordered[i].p)); holm[ordered[i].i] = running; }
const inference = rawInference.map((r, i) => ({ ...r, p_holm_family5: holm[i], family: "five primary position Brier endpoints" }));

const csvCell = v => { const s = String(v); return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const csvOf = (rs, fields) => [fields.join(","), ...rs.map(r => fields.map(k => csvCell(r[k] ?? "")).join(","))].join("\n") + "\n";
const targetFields = ["date","target_index","cutoff_date","split","position","previous_draw_range","range_state","state_training_n","global_training_n","selected_alpha","actual","state_pick","global_pick","prior_pick","state_rank","global_rank","prior_rank","state_top1","global_top1","prior_top1","state_top5","global_top5","prior_top5","state_top10","global_top10","prior_top10","state_top20","global_top20","prior_top20","state_brier","global_brier","prior_brier","brier_improvement_vs_global","brier_improvement_vs_prior","state_logloss","global_logloss","prior_logloss","logloss_improvement_vs_global","logloss_improvement_vs_prior"];
const targetCsv = csvOf(selectedRows.map(r => ({ ...r, selected_alpha: r.alpha })), targetFields);
const validationRows = validationGrid.flatMap(v => v.candidates);
const validationFields = ["position","alpha","n","brier_improvement_vs_global","brier_improvement_vs_prior","logloss_improvement_vs_global","logloss_improvement_vs_prior","top1_delta_vs_global","top5_delta_vs_global","mean_rank_improvement_vs_global"];
const validationCsv = csvOf(validationRows, validationFields);
const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); } return (h >>> 0).toString(16).padStart(8, "0"); };
const roundDeep = v => { if (Array.isArray(v)) return v.map(roundDeep); if (v && typeof v === "object") { const o = {}; for (const k of Object.keys(v)) o[k] = roundDeep(v[k]); return o; } if (typeof v === "number") { const n = Number(v.toFixed(12)); return Object.is(n, -0) ? 0 : n; } return v; };
const report = roundDeep({
  experiment_id: "SONAR_PSR06_PREVIOUS_DRAW_RANGE_STATE_POSITION_MARGINALS", status: "EXPLORATORY_NULL_NO_PROMOTION",
  archive: { path: "data/storico_daily.csv", git_blob_sha: gitBlobSha, draw_count: rows.length, first_date: rows[0].date, last_date: rows.at(-1).date },
  hypothesis: "The whole range state of the immediately preceding complete draw may condition the next draw's ordered-position marginal distributions.",
  formula: { range_distribution: "Pr(R=r)=(40-r)*C(r-1,3)/C(40,5), r=4..39", exact_theoretical_range_quartile_cutpoints: cuts, states: stateLabels,
    exact_position_prior: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5), n=i..35+i",
    conditional: "qS_i,t(n|s)=[c_i,t,s(n)+alpha*pi_i(n)]/[N_t,s+alpha]", global_comparator: "qG_i,t(n)=[c_i,t(n)+alpha*pi_i(n)]/[N_t+alpha]",
    alpha_grid: alphaGrid, alpha_selection: "per position; validation max mean Brier improvement vs global shrinkage with same alpha; ties smaller alpha" },
  protocol: { warmup, test_targets: testN, split_counts: splitCounts, split_dates: splitDates,
    bootstrap: { type: "circular moving-block", block_length: block, replicates: B, seed_base: seedBase, holm_family: 5, primary_endpoint: "blind OOS paired Brier improvement vs global shrinkage" },
    theoretical_range_state_mass: stateMass },
  validation_selection: selected, validation_grid: validationGrid, selected_model_metrics: splitMetrics, blind_oos_inference: inference,
  integrity: { strict_prefix_checks: testN, expected_train_n_rule: "train_n=t-2; training targets j=2..t-1; predictor state uses draw t-1", strict_prefix_pass: true,
    target_position_rows: selectedRows.length, expected_target_position_rows: testN * 5,
    validation_grid_rows: grid.filter(r => r.split === "validation").length, expected_validation_grid_rows: splitCounts.validation * 5 * alphaGrid.length,
    internal_grid_rows: grid.length, expected_internal_grid_rows: expectedGridN, duplicate_grid_keys: 0,
    order_statistic_prior_normalization_pass: true, conditional_probability_normalization_checks: grid.length, archive_blob_sha_verified_by_runtime: true,
    target_ledger_fnv1a32: fnv(targetCsv), validation_grid_fnv1a32: fnv(validationCsv) },
  limitations: ["The preceding draw range should not affect a new independent draw under the ideal game model.",
    "The historical blind partition overlaps dates inspected in previous PSR studies; this is not lab-wide independent prospective confirmation.",
    "Five marginal position distributions are dependent and do not form a joint ticket.", "Alpha selection is validation-only; no blind parameter tuning.", "No engine promotion or merge is authorized."],
  next_action: "Preserve any positive point estimates as exploratory; continue append-only prospective freezes and seek independent prospective evidence. Audit range-state calibration and dependence null controls next."
});
const fmt = x => Number(x).toFixed(6), pp = x => (x * 100).toFixed(3) + " pp", md = [];
md.push("# SONAR PSR-06 — Previous-Draw Range-State Position Marginals", "", "**Status:** EXPLORATORY / NO PROMOTION  ",
  "**Archive:** " + rows.length + " draws, " + rows[0].date + "–" + rows.at(-1).date + "; blob SHA " + gitBlobSha + "  ",
  "**Targets:** " + testN + "; warmup " + warmup + "; discovery " + splitCounts.discovery + ", validation " + splitCounts.validation + ", blind OOS " + splitCounts.blind_oos, "");
md.push("## Hypothesis and formula", "Condition each next ordered-position marginal on the range of the preceding draw. Exact range distribution Pr(R=r)=(40-r)C(r-1,3)/C(40,5), r=4..39. Theoretical quartile cutpoints: **" + cuts.join(", ") + "**; state masses: " + stateMass.map(x => (100 * x).toFixed(2) + "%").join(", ") + ".",
  "", "For position i, exact prior pi_i(n)=C(n-1,i-1)C(40-n,5-i)/C(40,5). Conditional qS=[c_i,t,s(n)+alpha*pi_i(n)]/[N_t,s+alpha]; global comparator qG=[c_i,t(n)+alpha*pi_i(n)]/[N_t+alpha]. Alpha grid " + alphaGrid.join(", ") + ", selected per position on validation by Brier improvement vs global with same alpha.", "");
md.push("## Validation alpha selection", "| P | Selected alpha | Validation delta Brier vs global | alpha=50 | alpha=100 | alpha=200 | alpha=500 |", "|---|---:|---:|---:|---:|---:|---:|");
for (const v of validationGrid) md.push("| P" + v.position + " | " + selected[v.position - 1].selected_alpha + " | " + fmt(selected[v.position - 1].selected_validation_brier_improvement_vs_global) + " | " + v.candidates.map(c => fmt(c.brier_improvement_vs_global)).join(" | ") + " |");
md.push("", "## Selected model by split", "| P | alpha | Split | N | delta Brier vs global | delta Brier vs prior | delta log-loss vs global | delta log-loss vs prior | Top-1 delta vs global | Top-5 delta vs global | Mean rank improvement vs global |", "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|");
for (const r of splitMetrics) md.push("| P" + r.position + " | " + r.selected_alpha + " | " + r.split + " | " + r.n + " | " + fmt(r.brier_improvement_vs_global) + " | " + fmt(r.brier_improvement_vs_prior) + " | " + fmt(r.logloss_improvement_vs_global) + " | " + fmt(r.logloss_improvement_vs_prior) + " | " + pp(r.top1_delta_vs_global) + " | " + pp(r.top5_delta_vs_global) + " | " + fmt(r.mean_rank_improvement_vs_global) + " |");
md.push("", "## Blind OOS primary inference", "| P | alpha | delta Brier vs global | 95% block CI | Raw one-sided p | Holm p (5) |", "|---|---:|---:|---|---:|---:|");
for (const r of inference) md.push("| P" + r.position + " | " + r.selected_alpha + " | " + fmt(r.mean_brier_improvement_vs_global) + " | [" + fmt(r.ci95[0]) + ", " + fmt(r.ci95[1]) + "] | " + r.p_one_sided_raw.toFixed(6) + " | " + r.p_holm_family5.toFixed(6) + " |");
md.push("", (inference.some(r => r.p_holm_family5 < 0.05) ? "At least one endpoint survives Holm; independent prospective confirmation is still required." : "**Decision:** no primary endpoint survives Holm; no statistically supported lift. Positive point estimates remain exploratory.") + " The historical blind partition overlaps prior PSR research and is not lab-wide independent confirmation.", "");
md.push("## Integrity and reproducibility", "- Strict-prefix checks " + testN + "; train_n=t-2; predictor cutoff is draw t-1; PASS.",
  "- Selected target-position rows " + selectedRows.length + "; expected " + (testN * 5) + "; validation alpha-grid rows " + grid.filter(r => r.split === "validation").length + "; complete internal alpha-grid rows " + grid.length + "; duplicate keys 0.",
  "- Exact order-statistic priors and conditional probabilities normalized.", "- Target ledger FNV-1a32 " + report.integrity.target_ledger_fnv1a32 + "; validation grid FNV-1a32 " + report.integrity.validation_grid_fnv1a32 + ".", "");
md.push("## Root cause and limitations", "PSR-01 extrema barely narrowed the exact positional supports; PSR-05 same-position displacement did not show robust calibrated lift. PSR-06 tests a distinct cross-position shape feature (range of the previous whole draw). Under independent draws this state should have no predictive effect; any lift can reflect noise or historical selection. Four state bins and alpha grid are fixed; Holm is applied to five primary position Brier endpoints. Marginal positions are dependent; no joint ticket or winning guarantee.", "", "## Next action", report.next_action);

fs.mkdirSync(outDir, { recursive: true });
const outputs = [
  ["PSR06_results_20261108.json", JSON.stringify(report, null, 2) + "\n"],
  ["PSR06_results_20261108.md", md.join("\n") + "\n"],
  ["PSR06_target_ledger_20261108.csv", targetCsv],
  ["PSR06_validation_grid_20261108.csv", validationCsv]
];
for (const [name, content] of outputs) fs.writeFileSync(path.join(outDir, name), content);
console.log(JSON.stringify({ experiment: report.experiment_id, status: report.status, archive: report.archive, targets: testN,
  selected_alpha: selected, blind_oos_inference: inference, integrity: report.integrity,
  outputs: outputs.map(([name, content]) => ({ name, bytes: Buffer.byteLength(content) })) }, null, 2));
