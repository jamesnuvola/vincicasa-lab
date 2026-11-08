#!/usr/bin/env node
/**
 * PSR-05: signed same-position lag-1 displacement residual conditioning.
 * Each target is scored from the strict past prefix. Research-only; no promotion.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const input = process.argv[2] || "data/storico_daily.csv";
const outDir = process.argv[3] || "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR05_WARMUP || 300);
const alphaGrid = [100, 300, 1000];
const B = Number(process.env.SONAR_PSR05_BOOTSTRAP || 2000);
const blockLength = Number(process.env.SONAR_PSR05_BLOCK || 7);
const seedBase = Number(process.env.SONAR_PSR05_SEED || 20261108);
const expectedSha = process.env.SONAR_PSR05_EXPECTED_ARCHIVE_BLOB_SHA || "5d2efd70684e918b27d8f06386d545647898336d";
if (!Number.isInteger(warmup) || warmup < 50 || !Number.isInteger(B) || B < 100 ||
    !Number.isInteger(blockLength) || blockLength < 1 || !Number.isInteger(seedBase)) {
  throw new Error("Invalid PSR-05 parameters");
}

const choose = (n, k) => {
  if (k < 0 || n < k || n < 0) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let v = 1;
  for (let i = 1; i <= k; i++) v = v * (n - k + i) / i;
  return v;
};
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const quantile = (a, q) => {
  const s = [...a].sort((x, y) => x - y), h = (s.length - 1) * q, lo = Math.floor(h), hi = Math.ceil(h);
  return s[lo] + (s[hi] - s[lo]) * (h - lo);
};
const mulberry32 = seed => {
  let a = seed >>> 0;
  return () => {
    a += 0x6D2B79F5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14) >>> 0) >>> 0) / 4294967296;
  };
};
const holm = ps => {
  const order = ps.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p || a.i - b.i), out = Array(ps.length).fill(1);
  let running = 0;
  for (let r = 0; r < order.length; r++) {
    running = Math.max(running, Math.min(1, (order.length - r) * order[r].p));
    out[order[r].i] = running;
  }
  return out;
};
const roundDeep = v => {
  if (Array.isArray(v)) return v.map(roundDeep);
  if (v && typeof v === "object") { const o = {}; for (const k of Object.keys(v)) o[k] = roundDeep(v[k]); return o; }
  if (typeof v === "number") { const x = Number(v.toFixed(12)); return Object.is(x, -0) ? 0 : x; }
  return v;
};
const fnv1a32 = s => {
  let h = 0x811c9dc5;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193); }
  return (h >>> 0).toString(16).padStart(8, "0");
};
const csvCell = v => {
  const s = String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
};
const csvRow = values => values.map(csvCell).join(",");
const fmt9 = x => Number(x).toFixed(9);
function parseArchive(csv) {
  const lines = csv.trim().split(/\r?\n/);
  if (lines.length < 2 || lines[0].trim() !== "data,n1,n2,n3,n4,n5") throw new Error("Bad canonical CSV header");
  const rows = lines.slice(1).map((line, i) => {
    const c = line.split(","), date = c[0], nums = c.slice(1).map(Number);
    if (c.length !== 6 || !/^\d{4}-\d{2}-\d{2}$/.test(date) || nums.length !== 5 ||
        nums.some(n => !Number.isInteger(n) || n < 1 || n > 40) || new Set(nums).size !== 5 ||
        nums.some((n, j) => j > 0 && n <= nums[j - 1])) throw new Error("Invalid draw row " + (i + 2));
    return { date, nums };
  });
  for (let i = 1; i < rows.length; i++) if (rows[i].date <= rows[i - 1].date) throw new Error("Nonascending dates");
  const sha = crypto.createHash("sha1").update(Buffer.from("blob " + Buffer.byteLength(csv) + "\0")).update(Buffer.from(csv)).digest("hex");
  if (expectedSha && sha !== expectedSha) throw new Error("Archive Git blob SHA mismatch: " + sha);
  if (rows.length <= warmup + 20) throw new Error("Insufficient archive rows");
  return { rows, sha, bytes: Buffer.byteLength(csv) };
}
const stateOf = d => d <= -3 ? 0 : d === -2 ? 1 : d === -1 ? 2 : d === 0 ? 3 : d === 1 ? 4 : d === 2 ? 5 : 6;
const stateLabels = ["d<=-3", "d=-2", "d=-1", "d=0", "d=1", "d=2", "d>=3"];
function score(prob, actualIndex) {
  let brier = 0;
  for (let i = 0; i < prob.length; i++) brier += (prob[i] - (i === actualIndex ? 1 : 0)) ** 2;
  const ranked = prob.map((q, i) => ({ q, i })).sort((a, b) => b.q - a.q || a.i - b.i);
  const rank = ranked.findIndex(o => o.i === actualIndex) + 1;
  return { brier, logloss: -Math.log(Math.max(prob[actualIndex], 1e-15)), rank, top1: rank <= 1, top5: rank <= 5, top10: rank <= 10, top20: rank <= 20 };
}
function summarize(rs) {
  const m = f => mean(rs.map(f));
  return {
    n: rs.length, mean_state_train_n: m(r => r.state_train_n),
    global_brier: m(r => r.global_brier), state_brier: m(r => r.state_brier), prior_brier: m(r => r.prior_brier),
    brier_improvement_vs_global: m(r => r.brier_improvement_vs_global),
    brier_improvement_vs_prior: m(r => r.brier_improvement_vs_prior),
    global_brier_improvement_vs_prior: m(r => r.global_brier_improvement_vs_prior),
    global_logloss: m(r => r.global_logloss), state_logloss: m(r => r.state_logloss), prior_logloss: m(r => r.prior_logloss),
    logloss_improvement_vs_global: m(r => r.logloss_improvement_vs_global),
    logloss_improvement_vs_prior: m(r => r.logloss_improvement_vs_prior),
    global_logloss_improvement_vs_prior: m(r => r.global_logloss_improvement_vs_prior),
    top1_delta: m(r => r.top1_delta), top5_delta: m(r => r.top5_delta), top10_delta: m(r => r.top10_delta), top20_delta: m(r => r.top20_delta),
    rank_improvement: m(r => r.rank_improvement)
  };
}
function circularBlockMean(sample, rng) {
  let sum = 0, count = 0;
  while (count < sample.length) {
    const start = Math.floor(rng() * sample.length);
    for (let k = 0; k < blockLength && count < sample.length; k++, count++) sum += sample[(start + k) % sample.length];
  }
  return sum / sample.length;
}
function bootstrapInference(differences, seed) {
  const observed = mean(differences), rngCi = mulberry32(seed), ciMeans = [];
  const rngNull = mulberry32(seed ^ 0x9E3779B9), centered = differences.map(x => x - observed), nullMeans = [];
  for (let b = 0; b < B; b++) {
    ciMeans.push(circularBlockMean(differences, rngCi));
    nullMeans.push(circularBlockMean(centered, rngNull));
  }
  const rawP = (nullMeans.filter(x => x >= observed - 1e-15).length + 1) / (B + 1);
  return { mean_improvement: observed, ci95: [quantile(ciMeans, 0.025), quantile(ciMeans, 0.975)], raw_one_sided_benefit_p: rawP,
    bootstrap: { type: "circular moving-block bootstrap; raw paired differences for CI, null-centered differences for one-sided p", block_length: blockLength, replicates: B, seed } };
}
function run(csv) {
  const archive = parseArchive(csv), rows = archive.rows, priors = [];
  for (let p = 1; p <= 5; p++) {
    const domain = Array.from({ length: 36 }, (_, i) => i + p);
    const prior = domain.map(n => choose(n - 1, p - 1) * choose(40 - n, 5 - p) / choose(40, 5));
    if (Math.abs(prior.reduce((s, q) => s + q, 0) - 1) > 1e-10) throw new Error("Prior normalization failure P" + p);
    priors.push({ domain, prior });
  }
  const testN = rows.length - warmup, discoveryEnd = Math.floor(testN * 0.5), validationEnd = Math.floor(testN * 0.75);
  const splitOf = t => t - warmup < discoveryEnd ? "discovery" : t - warmup < validationEnd ? "validation" : "blind_oos";
  const splitCounts = { discovery: discoveryEnd, validation: validationEnd - discoveryEnd, blind_oos: testN - validationEnd };
  const splitDates = {
    discovery: [rows[warmup].date, rows[warmup + discoveryEnd - 1].date],
    validation: [rows[warmup + discoveryEnd].date, rows[warmup + validationEnd - 1].date],
    blind_oos: [rows[warmup + validationEnd].date, rows.at(-1).date]
  };
  const globalCounts = Array.from({ length: 5 }, () => Array(36).fill(0));
  const stateCounts = Array.from({ length: 5 }, () => Array.from({ length: 7 }, () => Array(36).fill(0)));
  const stateN = Array.from({ length: 5 }, () => Array(7).fill(0));
  let trainN = 0;
  const addTrainingTarget = j => {
    if (j < 2 || j >= rows.length) throw new Error("Invalid training target index " + j);
    trainN++;
    for (let p = 0; p < 5; p++) {
      const domain = priors[p].domain, yi = rows[j].nums[p] - domain[0];
      const d = rows[j - 1].nums[p] - rows[j - 2].nums[p], s = stateOf(d);
      if (yi < 0 || yi >= 36 || s < 0 || s > 6) throw new Error("Training support/state violation");
      globalCounts[p][yi]++; stateCounts[p][s][yi]++; stateN[p][s]++;
    }
  };
  for (let j = 2; j < warmup; j++) addTrainingTarget(j);
  const detail = [];
  for (let t = warmup; t < rows.length; t++) {
    if (trainN !== t - 2 || rows[t - 1].date >= rows[t].date) throw new Error("Strict-prefix/cutoff failure at t=" + t + " trainN=" + trainN);
    const split = splitOf(t), cutoff = rows[t - 1].date;
    for (let p = 0; p < 5; p++) {
      const domain = priors[p].domain, prior = priors[p].prior;
      const displacement = rows[t - 1].nums[p] - rows[t - 2].nums[p], state = stateOf(displacement);
      const nState = stateN[p][state], actual = rows[t].nums[p], actualIndex = actual - domain[0];
      const globalScores = [], stateScores = [];
      for (const alpha of alphaGrid) {
        const globalProb = globalCounts[p].map((c, i) => (c + alpha * prior[i]) / (trainN + alpha));
        const stateProb = stateCounts[p][state].map((c, i) => (c + alpha * prior[i]) / (nState + alpha));
        const g = score(globalProb, actualIndex), s = score(stateProb, actualIndex), b = score(prior, actualIndex);
        const row = {
          date: rows[t].date, target_index: t, cutoff_date: cutoff, split, position: p + 1, alpha,
          displacement, state_bin: state, state_label: stateLabels[state], state_train_n: nState, train_n: trainN, actual,
          global_brier: g.brier, state_brier: s.brier, prior_brier: b.brier,
          brier_improvement_vs_global: g.brier - s.brier, brier_improvement_vs_prior: b.brier - s.brier,
          global_brier_improvement_vs_prior: b.brier - g.brier,
          global_logloss: g.logloss, state_logloss: s.logloss, prior_logloss: b.logloss,
          logloss_improvement_vs_global: g.logloss - s.logloss, logloss_improvement_vs_prior: b.logloss - s.logloss,
          global_logloss_improvement_vs_prior: b.logloss - g.logloss,
          global_rank: g.rank, state_rank: s.rank, rank_improvement: g.rank - s.rank,
          global_top1: Number(g.top1), state_top1: Number(s.top1), top1_delta: Number(s.top1) - Number(g.top1),
          global_top5: Number(g.top5), state_top5: Number(s.top5), top5_delta: Number(s.top5) - Number(g.top5),
          global_top10: Number(g.top10), state_top10: Number(s.top10), top10_delta: Number(s.top10) - Number(g.top10),
          global_top20: Number(g.top20), state_top20: Number(s.top20), top20_delta: Number(s.top20) - Number(g.top20)
        };
        detail.push(row);
      }
    }
    addTrainingTarget(t);
  }
  const expectedGridRows = testN * 5 * alphaGrid.length;
  if (detail.length !== expectedGridRows) throw new Error("Grid detail count mismatch " + detail.length);
  const keys = new Set();
  for (const r of detail) {
    const key = r.date + "|" + r.position + "|" + r.alpha;
    if (keys.has(key)) throw new Error("Duplicate grid key " + key);
    keys.add(key);
  }
  const validationSelection = [];
  for (let p = 1; p <= 5; p++) {
    const validationGrid = alphaGrid.map(alpha => {
      const m = summarize(detail.filter(r => r.position === p && r.split === "validation" && r.alpha === alpha));
      return { alpha, metrics: m };
    });
    let best = validationGrid[0];
    for (const candidate of validationGrid.slice(1)) {
      const a = candidate.metrics.brier_improvement_vs_global, b = best.metrics.brier_improvement_vs_global;
      if (a > b + 1e-15 || (Math.abs(a - b) <= 1e-15 && candidate.alpha < best.alpha)) best = candidate;
    }
    validationSelection.push({ position: p, selected_alpha: best.alpha, validation_brier_improvement_vs_global: best.metrics.brier_improvement_vs_global, validation_grid: validationGrid });
  }
  const selectedSplitMetrics = [];
  for (const sel of validationSelection) for (const split of ["discovery", "validation", "blind_oos"]) {
    const m = summarize(detail.filter(r => r.position === sel.position && r.split === split && r.alpha === sel.selected_alpha));
    selectedSplitMetrics.push({ position: sel.position, selected_alpha: sel.selected_alpha, split, metrics: m });
  }
  const blindInference = [];
  for (let p = 1; p <= 5; p++) {
    const alpha = validationSelection[p - 1].selected_alpha;
    const blind = detail.filter(r => r.position === p && r.split === "blind_oos" && r.alpha === alpha);
    const infer = bootstrapInference(blind.map(r => r.brier_improvement_vs_global), seedBase + p * 2027);
    blindInference.push({ position: p, selected_alpha: alpha, metrics: summarize(blind), ...infer });
  }
  const adjusted = holm(blindInference.map(r => r.raw_one_sided_benefit_p));
  blindInference.forEach((r, i) => { r.holm_p_family_5_positions = adjusted[i]; });

  const gridFields = ["date","target_index","cutoff_date","position","alpha","displacement","state_bin","state_label","state_train_n","train_n","actual",
    "global_brier","state_brier","prior_brier","brier_improvement_vs_global","brier_improvement_vs_prior","global_brier_improvement_vs_prior",
    "global_logloss","state_logloss","prior_logloss","logloss_improvement_vs_global","logloss_improvement_vs_prior","global_logloss_improvement_vs_prior",
    "global_rank","state_rank","rank_improvement","global_top1","state_top1","top1_delta","global_top5","state_top5","top5_delta",
    "global_top10","state_top10","top10_delta","global_top20","state_top20","top20_delta"];
  const gridCsv = [csvRow(gridFields), ...detail.map(r => csvRow(gridFields.map(k => typeof r[k] === "number" && !Number.isInteger(r[k]) ? fmt9(r[k]) : r[k])))].join("\n") + "\n";
  const selectedFields = ["date","target_index","cutoff_date","actual","position","selected_alpha","displacement","state_bin","state_label","state_train_n","train_n",
    "global_brier","state_brier","brier_improvement_vs_global","prior_brier","brier_improvement_vs_prior",
    "global_logloss","state_logloss","logloss_improvement_vs_global","prior_logloss","logloss_improvement_vs_prior",
    "global_rank","state_rank","rank_improvement","global_top1","state_top1","top1_delta","global_top5","state_top5","top5_delta",
    "global_top10","state_top10","top10_delta","global_top20","state_top20","top20_delta"];
  const selectedRows = [];
  for (let t = warmup; t < rows.length; t++) for (let p = 1; p <= 5; p++) {
    const sel = validationSelection[p - 1], r = detail.find(x => x.target_index === t && x.position === p && x.alpha === sel.selected_alpha);
    if (!r) throw new Error("Missing selected target ledger row t=" + t + " p=" + p);
    selectedRows.push({
      date: r.date, target_index: r.target_index, cutoff_date: r.cutoff_date,
      actual: r.actual, position: p, selected_alpha: r.alpha, displacement: r.displacement, state_bin: r.state_bin, state_label: r.state_label,
      state_train_n: r.state_train_n, train_n: r.train_n, global_brier: r.global_brier, state_brier: r.state_brier,
      brier_improvement_vs_global: r.brier_improvement_vs_global, prior_brier: r.prior_brier, brier_improvement_vs_prior: r.brier_improvement_vs_prior,
      global_logloss: r.global_logloss, state_logloss: r.state_logloss, logloss_improvement_vs_global: r.logloss_improvement_vs_global,
      prior_logloss: r.prior_logloss, logloss_improvement_vs_prior: r.logloss_improvement_vs_prior,
      global_rank: r.global_rank, state_rank: r.state_rank, rank_improvement: r.rank_improvement,
      global_top1: r.global_top1, state_top1: r.state_top1, top1_delta: r.top1_delta,
      global_top5: r.global_top5, state_top5: r.state_top5, top5_delta: r.top5_delta,
      global_top10: r.global_top10, state_top10: r.state_top10, top10_delta: r.top10_delta,
      global_top20: r.global_top20, state_top20: r.state_top20, top20_delta: r.top20_delta
    });
  }
  const selectedCsv = [csvRow(selectedFields), ...selectedRows.map(r => csvRow(selectedFields.map(k => typeof r[k] === "number" && !Number.isInteger(r[k]) ? fmt9(r[k]) : r[k])))].join("\n") + "\n";
  const gridFingerprint = fnv1a32(gridCsv), selectedFingerprint = fnv1a32(selectedCsv);
  const primaryBenefitCount = blindInference.filter(r => r.holm_p_family_5_positions < 0.05).length;
  const positiveUnconfirmed = blindInference.filter(r => r.mean_improvement > 0 && r.ci95[0] <= 0 && r.ci95[1] >= 0).map(r => ({
    position: r.position, mean_brier_improvement: r.mean_improvement, ci95: r.ci95, raw_p: r.raw_one_sided_benefit_p, holm_p: r.holm_p_family_5_positions
  }));
  const report = {
    experiment_id: "SONAR_PSR05_SIGNED_SAME_POSITION_DISPLACEMENT",
    run_date: rows.at(-1).date,
    status: primaryBenefitCount ? "EXPLORATORY_CANDIDATE_NOT_PROMOTABLE" : "EXPLORATORY_NULL_NO_PROMOTION",
    archive: { path: "data/storico_daily.csv", git_blob_sha: archive.sha, draw_count: rows.length, first_date: rows[0].date, last_date: rows.at(-1).date, bytes: archive.bytes },
    protocol: {
      warmup, test_targets: testN, split_counts: splitCounts, split_dates: splitDates, alpha_grid: alphaGrid,
      state_feature: "d_i(t)=P_i(t-1)-P_i(t-2), prior-only known signed displacement for sorted position i",
      state_bins: stateLabels,
      state_condition: "s(d): <=-3, -2, -1, 0, +1, +2, >=+3",
      global_model: "qG_i,t(n)=(c_i,t(n)+alpha*pi_i(n))/(N_t+alpha)",
      conditional_model: "qS_i,t(n|s)=(c_i,t,s(n)+alpha*pi_i(n))/(N_t,s+alpha)",
      prior: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5), n=i..35+i",
      selection: "alpha per position selected only on validation by mean Brier improvement vs global shrinkage; tie lower alpha",
      bootstrap: { type: "circular moving-block bootstrap; raw paired differences for CI, null-centered differences for one-sided p", block_length: blockLength, replicates: B, seed_base: seedBase, holm_family: 5 },
      caveat: "Historical blind OOS dates overlap earlier PSR-01..04 exploration; not independent prospective evidence. Marginal positions are dependent; no ticket is assembled."
    },
    validation_selection: validationSelection,
    selected_split_metrics: selectedSplitMetrics,
    blind_oos_primary_inference: blindInference,
    multiple_testing: "Holm step-down across the five preregistered per-position blind-OOS Brier benefit endpoints; broader lab-family selection remains exploratory.",
    integrity: {
      archive_rows: rows.length, dates_strictly_ascending: true, sorted_distinct_five_numbers_in_1_to_40: true,
      exact_priors_sum_to_one: true, strict_prefix_checks: testN * 5, cutoff_before_target_checks: testN * 5,
      train_n_equals_target_index_minus_two_checks: testN * 5, state_feature_known_before_target_checks: testN * 5,
      grid_rows: detail.length, grid_columns: gridFields.length, duplicate_grid_keys: 0,
      selected_ledger_rows: selectedRows.length, selected_ledger_columns: selectedFields.length,
      grid_ledger_fingerprint_fnv1a32: gridFingerprint, selected_ledger_fingerprint_fnv1a32: selectedFingerprint,
      score_csv_precision_decimal_places: 9
    },
    decision: {
      promotion: "NOT_ALLOWED",
      primary_holm_benefit_endpoints: primaryBenefitCount,
      preserve_unconfirmed_positive_brier_candidates: positiveUnconfirmed,
      root_cause_reading: primaryBenefitCount ? "At least one position endpoint is Holm-significant within PSR-05, but the repeated historical blind partition and no independent prospective evidence still prohibit promotion." :
        "Signed displacement-state conditioning did not establish a calibrated blind-OOS Brier benefit after validation-only alpha selection and Holm correction; conditional state counts add estimation variance over the exact order-statistic prior/global shrinkage.",
      next_action: "Retain all positive point-estimate candidates as exploratory. Continue prospective append-only shadow freezes; consider a joint dependence-aware model only after independent prospective evidence, and do not replace SONAR."
    },
    execution: { double_run_exact_match: true, grid_ledger_fingerprint_fnv1a32: gridFingerprint, selected_ledger_fingerprint_fnv1a32: selectedFingerprint, runtime: "Node.js; version omitted for deterministic output" }
  };
  return { report: roundDeep(report), gridCsv, selectedCsv };
}
function renderMarkdown(report) {
  const f = (x, d = 6) => Number(x).toFixed(d), pp = x => (x * 100).toFixed(3) + " pp", lines = [];
  lines.push("# SONAR PSR-05 — Signed Same-Position Displacement Residual Lab", "");
  lines.push("**Status:** " + report.status + " · **Promotion:** NOT ALLOWED");
  lines.push("**Archive:** " + report.archive.draw_count + " draws, " + report.archive.first_date + "–" + report.archive.last_date + "; Git blob SHA " + report.archive.git_blob_sha, "");
  lines.push("## Hypothesis and formula", "");
  lines.push("For each sorted position i, condition the next marginal on its preceding signed displacement d_i(t)=P_i(t−1)−P_i(t−2). The seven fixed states are " + report.protocol.state_bins.join(", ") + ".");
  lines.push("Exact order-statistic prior pi_i(n)=C(n−1,i−1)C(40−n,5−i)/C(40,5), n=i..35+i.");
  lines.push("Global comparator qG=(c_i,t(n)+alpha*pi_i(n))/(N_t+alpha); conditional candidate qS=(c_i,t,s(n)+alpha*pi_i(n))/(N_t,s+alpha). Alpha is selected per position only on validation.", "");
  lines.push("## Walk-forward and split", "");
  lines.push("Warmup " + report.protocol.warmup + "; targets " + report.protocol.test_targets + "; discovery " + report.protocol.split_counts.discovery + " (" + report.protocol.split_dates.discovery.join(" – ") + "); validation " + report.protocol.split_counts.validation + " (" + report.protocol.split_dates.validation.join(" – ") + "); blind OOS " + report.protocol.split_counts.blind_oos + " (" + report.protocol.split_dates.blind_oos.join(" – ") + ").");
  lines.push("Alpha grid " + report.protocol.alpha_grid.join(", ") + "; circular block bootstrap block=" + report.protocol.bootstrap.block_length + ", B=" + report.protocol.bootstrap.replicates + "; Holm family=5 primary Brier endpoints.", "");
  lines.push("## Validation selection", "");
  lines.push("| P | Selected alpha | Validation ΔBrier vs global | α=100 | α=300 | α=1000 |");
  lines.push("|---|---:|---:|---:|---:|---:|");
  for (const s of report.validation_selection) lines.push("| P" + s.position + " | " + s.selected_alpha + " | " + f(s.validation_brier_improvement_vs_global) + " | " + f(s.validation_grid[0].metrics.brier_improvement_vs_global) + " | " + f(s.validation_grid[1].metrics.brier_improvement_vs_global) + " | " + f(s.validation_grid[2].metrics.brier_improvement_vs_global) + " |");
  lines.push("", "## Selected model by split", "");
  lines.push("| P | α | Split | N | ΔBrier vs global | ΔLog-loss vs global | Top-1 Δ | Top-5 Δ | Mean rank improvement |");
  lines.push("|---|---:|---|---:|---:|---:|---:|---:|---:|");
  for (const s of report.selected_split_metrics) { const m = s.metrics; lines.push("| P" + s.position + " | " + s.selected_alpha + " | " + s.split + " | " + m.n + " | " + f(m.brier_improvement_vs_global) + " | " + f(m.logloss_improvement_vs_global) + " | " + pp(m.top1_delta) + " | " + pp(m.top5_delta) + " | " + f(m.rank_improvement) + " |"); }
  lines.push("", "## Blind OOS primary inference", "");
  lines.push("| P | α | ΔBrier | 95% block CI | Raw one-sided p | Holm p (5) | Top-1 Δ | Top-5 Δ |");
  lines.push("|---|---:|---:|---|---:|---:|---:|---:|");
  for (const s of report.blind_oos_primary_inference) lines.push("| P" + s.position + " | " + s.selected_alpha + " | " + f(s.mean_improvement) + " | [" + f(s.ci95[0]) + ", " + f(s.ci95[1]) + "] | " + f(s.raw_one_sided_benefit_p, 4) + " | " + f(s.holm_p_family_5_positions, 4) + " | " + pp(s.metrics.top1_delta) + " | " + pp(s.metrics.top5_delta) + " |");
  lines.push("", "## Decision and retained candidates", "");
  lines.push(report.decision.root_cause_reading, "");
  if (report.decision.preserve_unconfirmed_positive_brier_candidates.length) {
    lines.push("Positive Brier point estimates with CI crossing zero (retained, not promoted):");
    for (const c of report.decision.preserve_unconfirmed_positive_brier_candidates) lines.push("- P" + c.position + ": ΔBrier " + f(c.mean_brier_improvement) + ", CI [" + f(c.ci95[0]) + ", " + f(c.ci95[1]) + "], raw p " + f(c.raw_p, 4) + ", Holm p " + f(c.holm_p, 4) + ".");
  } else lines.push("No positive Brier point-estimate candidate with a CI crossing zero was recorded.");
  lines.push("", "## Integrity / reproducibility", "");
  lines.push("Strict-prefix/cutoff checks " + report.integrity.strict_prefix_checks + "; train_n=t−2 checks " + report.integrity.train_n_equals_target_index_minus_two_checks + "; grid rows " + report.integrity.grid_rows + " (duplicate keys " + report.integrity.duplicate_grid_keys + "); selected ledger " + report.integrity.selected_ledger_rows + " rows.");
  lines.push("Two independent complete executions byte-identical: " + report.execution.double_run_exact_match + ". Grid FNV-1a32 " + report.integrity.grid_ledger_fingerprint_fnv1a32 + "; selected ledger FNV-1a32 " + report.integrity.selected_ledger_fingerprint_fnv1a32 + ".", "");
  lines.push("## Limits and next action", "");
  lines.push("Primary correction is Holm across five positions only; PSR-01..04 also explored the same historical blind partition, so this is not independent confirmation. Marginal positions are dependent; no ticket is constructed. Historical draws remain random and no forecast is guaranteed.");
  lines.push(report.decision.next_action);
  return lines.join("\n") + "\n";
}
const csv = fs.readFileSync(input, "utf8");
const first = run(csv), second = run(csv);
if (JSON.stringify(first.report) !== JSON.stringify(second.report) || first.gridCsv !== second.gridCsv || first.selectedCsv !== second.selectedCsv) {
  throw new Error("PSR-05 reproducibility failure: two full executions differ");
}
const markdown = renderMarkdown(first.report);
fs.mkdirSync(outDir, { recursive: true });
fs.writeFileSync(path.join(outDir, "PSR05_results_20261108.json"), JSON.stringify(first.report, null, 2) + "\n");
fs.writeFileSync(path.join(outDir, "PSR05_results_20261108.md"), markdown);
fs.writeFileSync(path.join(outDir, "PSR05_grid_ledger_20261108.csv"), first.gridCsv);
fs.writeFileSync(path.join(outDir, "PSR05_target_ledger_20261108.csv"), first.selectedCsv);
console.log(JSON.stringify({ experiment: first.report.experiment_id, status: first.report.status, archive: first.report.archive,
  validation_selection: first.report.validation_selection.map(s => ({ position: s.position, selected_alpha: s.selected_alpha, validation_delta_brier: s.validation_brier_improvement_vs_global })),
  blind_oos_primary_inference: first.report.blind_oos_primary_inference.map(s => ({ position: s.position, selected_alpha: s.selected_alpha, mean_improvement: s.mean_improvement, ci95: s.ci95, raw_p: s.raw_one_sided_benefit_p, holm_p: s.holm_p_family_5_positions })),
  integrity: first.report.integrity, execution: first.report.execution }, null, 2));
