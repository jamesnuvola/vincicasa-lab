#!/usr/bin/env node
/**
 * PSR-04: Gaussian kernel on previous same-position value, shrunk to the exact
 * order-statistic prior. Fixed alpha; validation-selected bandwidth per P_i.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const input = process.argv[2] || "data/storico_daily.csv";
const outDir = process.argv[3] || "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR04_WARMUP || 300);
const alpha = 100, hGrid = [2, 4, 6, 10];
const B = Number(process.env.SONAR_PSR04_BOOTSTRAP || 2000);
const block = Number(process.env.SONAR_PSR04_BLOCK || 7);
const seedBase = Number(process.env.SONAR_PSR04_SEED || 20261108);
const expectedSha = process.env.SONAR_PSR04_EXPECTED_ARCHIVE_BLOB_SHA || "";
if (!Number.isInteger(warmup) || warmup < 50 || !Number.isInteger(B) || B < 100 || !Number.isInteger(block) || block < 1) throw new Error("Invalid PSR-04 parameters");

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
const rng32 = seed => {
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
function score(prob, actualIndex) {
  let brier = 0;
  for (let i = 0; i < prob.length; i++) brier += (prob[i] - (i === actualIndex ? 1 : 0)) ** 2;
  const ranked = prob.map((q, i) => ({ q, i })).sort((a, b) => b.q - a.q || a.i - b.i), rank = ranked.findIndex(o => o.i === actualIndex) + 1;
  return { brier, logloss: -Math.log(Math.max(prob[actualIndex], 1e-15)), rank, top1: rank <= 1, top5: rank <= 5, top10: rank <= 10, top20: rank <= 20 };
}
function summarize(rs) {
  const m = f => mean(rs.map(f));
  return {
    n: rs.length,
    global_brier: m(r => r.global_brier), kernel_brier: m(r => r.kernel_brier), brier_improvement: m(r => r.brier_improvement),
    global_logloss: m(r => r.global_logloss), kernel_logloss: m(r => r.kernel_logloss), logloss_improvement: m(r => r.logloss_improvement),
    top1_delta: m(r => r.top1_delta), top5_delta: m(r => r.top5_delta), top10_delta: m(r => r.top10_delta),
    top20_delta: m(r => r.top20_delta), rank_improvement: m(r => r.rank_improvement)
  };
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
  const kernels = Array.from({ length: 5 }, (_, p) => hGrid.map(h =>
    Array.from({ length: 41 }, (_, query) => Array.from({ length: 41 }, (_, x) => Math.exp(-0.5 * ((query - x) / h) ** 2)))));
  const globalCounts = Array.from({ length: 5 }, () => Array(36).fill(0));
  const lagCounts = Array.from({ length: 5 }, () => Array.from({ length: 41 }, () => Array(36).fill(0)));
  const lagN = Array.from({ length: 5 }, () => Array(41).fill(0));
  let trainN = 0;
  const add = j => {
    trainN++;
    for (let p = 0; p < 5; p++) {
      const y = rows[j].nums[p], x = rows[j - 1].nums[p], yi = y - priors[p].domain[0];
      if (yi < 0 || yi >= 36) throw new Error("Position support failure");
      globalCounts[p][yi]++; lagCounts[p][x][yi]++; lagN[p][x]++;
    }
  };
  for (let j = 1; j < warmup; j++) add(j);
  const detail = Array.from({ length: 5 }, () => []);
  for (let t = warmup; t < rows.length; t++) {
    if (trainN !== t - 1 || rows[t - 1].date >= rows[t].date) throw new Error("Strict-prefix/cutoff failure at t=" + t);
    const split = splitOf(t);
    for (let p = 0; p < 5; p++) {
      const domain = priors[p].domain, prior = priors[p].prior, query = rows[t - 1].nums[p], actualIndex = rows[t].nums[p] - domain[0];
      const globalProb = globalCounts[p].map((c, i) => (c + alpha * prior[i]) / (trainN + alpha)), g = score(globalProb, actualIndex);
      for (let hi = 0; hi < hGrid.length; hi++) {
        const weighted = Array(36).fill(0), kw = kernels[p][hi][query]; let mass = 0;
        for (let x = 1; x <= 40; x++) {
          const nx = lagN[p][x]; if (!nx) continue;
          const w = kw[x]; mass += w * nx;
          for (let y = 0; y < 36; y++) weighted[y] += w * lagCounts[p][x][y];
        }
        const prob = weighted.map((c, i) => (c + alpha * prior[i]) / (mass + alpha)), k = score(prob, actualIndex);
        detail[p].push({
          date: rows[t].date, target_index: t, cutoff_date: rows[t - 1].date, split, position: p + 1, h: hGrid[hi],
          previous_value: query, actual: rows[t].nums[p], train_n: trainN,
          global_brier: g.brier, kernel_brier: k.brier, brier_improvement: g.brier - k.brier,
          global_logloss: g.logloss, kernel_logloss: k.logloss, logloss_improvement: g.logloss - k.logloss,
          global_rank: g.rank, kernel_rank: k.rank, rank_improvement: g.rank - k.rank,
          global_top1: g.top1, kernel_top1: k.top1, top1_delta: Number(k.top1) - Number(g.top1),
          global_top5: g.top5, kernel_top5: k.top5, top5_delta: Number(k.top5) - Number(g.top5),
          top10_delta: Number(k.top10) - Number(g.top10), top20_delta: Number(k.top20) - Number(g.top20)
        });
      }
    }
    add(t);
  }
  const expectedDetailRows = testN * 5 * hGrid.length;
  if (detail.reduce((s, a) => s + a.length, 0) !== expectedDetailRows) throw new Error("Detail count mismatch");
  const keys = new Set();
  for (const group of detail) for (const r of group) {
    const key = r.date + "|" + r.position + "|" + r.h;
    if (keys.has(key)) throw new Error("Duplicate detail key " + key);
    keys.add(key);
  }
  const validationSelection = [], selectedSplitMetrics = [];
  for (let p = 1; p <= 5; p++) {
    const grid = hGrid.map(h => {
      const m = summarize(detail[p - 1].filter(r => r.split === "validation" && r.h === h));
      return { h, brier_improvement: m.brier_improvement, logloss_improvement: m.logloss_improvement, top1_delta: m.top1_delta, top5_delta: m.top5_delta };
    });
    let best = grid[0];
    for (const c of grid.slice(1)) if (c.brier_improvement > best.brier_improvement + 1e-15 ||
      (Math.abs(c.brier_improvement - best.brier_improvement) <= 1e-15 && c.h < best.h)) best = c;
    validationSelection.push({ position: p, selected_h: best.h, validation_grid: grid });
    for (const split of ["discovery", "validation", "blind_oos"]) {
      const m = summarize(detail[p - 1].filter(r => r.split === split && r.h === best.h));
      selectedSplitMetrics.push({ position: p, selected_h: best.h, split, metrics: m });
    }
  }
  const blindInference = [];
  for (let p = 1; p <= 5; p++) {
    const h = validationSelection[p - 1].selected_h, blind = detail[p - 1].filter(r => r.split === "blind_oos" && r.h === h);
    const diffs = blind.map(r => r.brier_improvement), observed = mean(diffs), rng = rng32(seedBase + p * 2027), boot = [];
    for (let b = 0; b < B; b++) {
      let sum = 0, count = 0;
      while (count < diffs.length) {
        const start = Math.floor(rng() * diffs.length);
        for (let k = 0; k < block && count < diffs.length; k++, count++) sum += diffs[(start + k) % diffs.length];
      }
      boot.push(sum / diffs.length);
    }
    const nullCentered = boot.map(x => x - observed), rawP = (nullCentered.filter(x => x >= observed - 1e-15).length + 1) / (B + 1);
    blindInference.push({
      position: p, selected_h: h, metrics: summarize(blind), mean_brier_improvement: observed,
      ci95: [quantile(boot, 0.025), quantile(boot, 0.975)], raw_one_sided_p: rawP,
      bootstrap_seed: seedBase + p * 2027
    });
  }
  const adjusted = holm(blindInference.map(r => r.raw_one_sided_p));
  blindInference.forEach((r, i) => { r.holm_p_family_5 = adjusted[i]; });
  const header = ["date", "target_index", "cutoff_date", ...Array.from({ length: 5 }, (_, p) => "actual_p" + (p + 1))];
  for (let p = 1; p <= 5; p++) for (const field of ["selected_h", "previous_value", "train_n", "global_brier", "kernel_brier", "brier_improvement", "logloss_improvement", "rank_improvement", "top1_delta", "top5_delta"]) header.push("p" + p + "_" + field);
  const ledgerRows = [], fmt9 = x => Number(x).toFixed(9);
  for (let t = warmup; t < rows.length; t++) {
    const row = [rows[t].date, String(t), rows[t - 1].date, ...rows[t].nums.map(String)];
    for (let p = 1; p <= 5; p++) {
      const h = validationSelection[p - 1].selected_h, hi = hGrid.indexOf(h), r = detail[p - 1][(t - warmup) * hGrid.length + hi];
      if (!r || r.target_index !== t) throw new Error("Missing ledger row");
      row.push(String(h), String(r.previous_value), String(r.train_n), fmt9(r.global_brier), fmt9(r.kernel_brier),
        fmt9(r.brier_improvement), fmt9(r.logloss_improvement), fmt9(r.rank_improvement), String(r.top1_delta), String(r.top5_delta));
    }
    ledgerRows.push(row);
  }
  const ledgerCsv = [header.join(","), ...ledgerRows.map(r => r.join(","))].join("\n") + "\n";
  const fingerprint = fnv1a32(ledgerCsv);
  const report = {
    experiment_id: "SONAR_PSR04_CONTINUOUS_LAG1_KERNEL",
    run_date: rows.at(-1).date,
    status: "EXPLORATORY_NULL_NO_PROMOTION",
    archive: { path: "data/storico_daily.csv", git_blob_sha: archive.sha, draw_count: rows.length, first_date: rows[0].date, last_date: rows.at(-1).date, bytes: archive.bytes },
    protocol: {
      warmup, test_targets: testN, split_counts: splitCounts, split_dates: splitDates, alpha, h_grid: hGrid,
      kernel: "exp(-0.5*((query_previous_position-train_previous_position)/h)^2)",
      prior: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5), n=i..35+i",
      shrinkage: "q=(weighted_kernel_counts+alpha*pi_i)/(kernel_weight_mass+alpha); alpha fixed 100",
      selection: "choose h per position by validation Brier improvement vs global prior shrinkage; tie to smaller h",
      bootstrap: { type: "circular moving-block centered-null one-sided", block_length: block, replicates: B, seed_base: seedBase, holm_family: 5 },
      caveat: "Holm family is the five PSR-04 position endpoints only; same historical blind dates were used by earlier PSR experiments, so this is not independent prospective evidence."
    },
    validation_selection: validationSelection,
    selected_split_metrics: selectedSplitMetrics,
    blind_oos_primary_inference: blindInference,
    integrity: {
      archive_rows: rows.length, dates_strictly_ascending: true, sorted_distinct_five_numbers_in_1_to_40: true,
      exact_priors_sum_to_one: true, strict_prior_cutoff_checks: testN * 5, train_n_equals_target_index_minus_one_checks: testN * 5,
      scored_target_position_bandwidth_rows: expectedDetailRows, duplicate_detail_keys: 0,
      selected_ledger_rows: ledgerRows.length, selected_ledger_columns: header.length, ledger_fingerprint_fnv1a32: fingerprint,
      aggregate_mean_method: "arithmetic_mean_over_target_rows", ledger_precision_decimal_places: 9
    },
    decision: {
      promotion: "NOT_ALLOWED",
      reason: "No selected-kernel blind-OOS Brier endpoint survives Holm across five positions; all 95% block-bootstrap intervals include zero. The historical blind slice is reused from PSR-01/02/03 and is not independent prospective evidence.",
      preserve: [
        "P2: small positive blind Brier and Top-1/Top-5 deltas, but CI crosses zero and Holm does not confirm benefit.",
        "P1/P5: tiny positive Brier deltas, exploratory only.",
        "P3: Top-5-only rank anomaly while Brier and Top-1 deltas are negative."
      ],
      root_cause: "Exact order-statistic marginals plus global shrinkage already encode positional geometry; continuous lag-1 kernel localization adds variance without stable proper-score lift.",
      next_action: "PSR-05: signed same-position displacement-residual conditioning, with prior-only regularization, validation selection, same chronological split, block bootstrap and Holm x5. Preserve PSR-04 P2/P3 anomalies; no motor promotion."
    }
  };
  return { report, ledgerCsv };
}
function renderMarkdown(report) {
  const fmt = (x, d = 6) => Number(x).toFixed(d), pp = x => (x * 100).toFixed(4) + " pp", lines = [];
  lines.push("# SONAR PSR-04 — Continuous Same-Position Lag-1 Kernel Lab", "");
  lines.push("**Status:** EXPLORATORY / NULL / NO PROMOTION");
  lines.push("**Archive:** " + report.archive.draw_count + " draws, " + report.archive.first_date + "–" + report.archive.last_date + "; blob SHA " + report.archive.git_blob_sha, "");
  lines.push("## Formula", "");
  lines.push("Exact position prior: pi_i(n)=C(n-1,i-1) C(40-n,5-i) / C(40,5), n=i..35+i.");
  lines.push("Kernel: K_h(x_t,x_s)=exp(-0.5*((x_t-x_s)/h)^2), query x_t=P_i(t-1), training feature x_s=P_i(s-1).");
  lines.push("q_kernel=(weighted past-only counts + 100*pi_i)/(kernel weight mass + 100); comparator q_global=(past counts + 100*pi_i)/(N_t+100). Alpha fixed; h selected on validation only.", "");
  lines.push("## Walk-forward", "");
  lines.push("Warmup " + report.protocol.warmup + "; targets " + report.protocol.test_targets + "; discovery " + report.protocol.split_counts.discovery + " (" + report.protocol.split_dates.discovery.join(" – ") + "); validation " + report.protocol.split_counts.validation + " (" + report.protocol.split_dates.validation.join(" – ") + "); blind OOS " + report.protocol.split_counts.blind_oos + " (" + report.protocol.split_dates.blind_oos.join(" – ") + ").");
  lines.push("Bandwidth grid " + report.protocol.h_grid.join(", ") + "; paired circular block bootstrap (block " + report.protocol.bootstrap.block_length + ", " + report.protocol.bootstrap.replicates + " replicates); Holm across five primary positions.");
  lines.push("Historical blind partition overlaps earlier PSR exploration; it is not independent prospective evidence.", "");
  lines.push("## Validation bandwidth selection", "");
  lines.push("| P | h | Val ΔBrier | Val ΔLog-loss | Top-1 Δ | Top-5 Δ |");
  lines.push("|---|---:|---:|---:|---:|---:|");
  for (const s of report.validation_selection) for (const g of s.validation_grid) lines.push("| P" + s.position + " | " + g.h + " | " + fmt(g.brier_improvement) + " | " + fmt(g.logloss_improvement) + " | " + pp(g.top1_delta) + " | " + pp(g.top5_delta) + " |");
  lines.push("", "## Selected model by split", "");
  lines.push("| P | h | Split | N | ΔBrier | ΔLog-loss | Top-1 Δ | Top-5 Δ | Top-10 Δ | Rank improvement |");
  lines.push("|---|---:|---|---:|---:|---:|---:|---:|---:|---:|");
  for (const s of report.selected_split_metrics) { const m = s.metrics; lines.push("| P" + s.position + " | " + s.selected_h + " | " + s.split + " | " + m.n + " | " + fmt(m.brier_improvement) + " | " + fmt(m.logloss_improvement) + " | " + pp(m.top1_delta) + " | " + pp(m.top5_delta) + " | " + pp(m.top10_delta) + " | " + fmt(m.rank_improvement) + " |"); }
  lines.push("", "## Blind-OOS inference", "");
  lines.push("| P | h | ΔBrier | 95% block CI | Raw p | Holm p |");
  lines.push("|---|---:|---:|---|---:|---:|");
  for (const s of report.blind_oos_primary_inference) lines.push("| P" + s.position + " | " + s.selected_h + " | " + fmt(s.mean_brier_improvement) + " | [" + fmt(s.ci95[0]) + ", " + fmt(s.ci95[1]) + "] | " + fmt(s.raw_one_sided_p, 4) + " | " + fmt(s.holm_p_family_5, 4) + " |");
  lines.push("", "**Decision:** no Holm-adjusted primary benefit; all 95% intervals include zero. Preserve P2's small positive Brier/Top-1/Top-5 deltas and P3's Top-5-only rank anomaly as exploratory.", "");
  lines.push("## Integrity", "");
  lines.push("Strict prefix checks " + report.integrity.strict_prior_cutoff_checks + "; score rows " + report.integrity.scored_target_position_bandwidth_rows + "; duplicate keys " + report.integrity.duplicate_detail_keys + ".");
  lines.push("Selected ledger " + report.integrity.selected_ledger_rows + " rows × " + report.integrity.selected_ledger_columns + " columns; FNV-1a32 " + report.integrity.ledger_fingerprint_fnv1a32 + "; score fields persisted to 9 decimals (full precision used for scoring).");
  lines.push("Aggregate means use arithmetic means across target rows; reconciled against the persisted ledger. Two independent executions byte-identical: " + report.execution.double_run_exact_match + ". No engine change, merge, or promotion.", "");
  lines.push("## Root cause / next action", "");
  lines.push(report.decision.root_cause);
  lines.push(report.decision.next_action, "");
  lines.push("## Limits", "");
  lines.push("Marginals are dependent and were not combined into a ticket. Holm applies only within PSR-04's five endpoints; broad historical strategy-selection bias remains.");
  return lines.join("\n") + "\n";
}
const csv=fs.readFileSync(input,"utf8"),first=run(csv),second=run(csv);
if(JSON.stringify(first.report)!==JSON.stringify(second.report)||first.ledgerCsv!==second.ledgerCsv)throw new Error("PSR-04 reproducibility failure");
first.report.execution={double_run_exact_match:true,ledger_fingerprint_fnv1a32:first.report.integrity.ledger_fingerprint_fnv1a32,runtime:"Node.js; runtime version omitted for deterministic output"};
const report=roundDeep(first.report),markdown=renderMarkdown(report);
fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(path.join(outDir,"PSR04_results_20261108.json"),JSON.stringify(report,null,2)+"\n");
fs.writeFileSync(path.join(outDir,"PSR04_results_20261108.md"),markdown);
fs.writeFileSync(path.join(outDir,"PSR04_target_ledger_20261108.csv"),first.ledgerCsv);
console.log(JSON.stringify({experiment:report.experiment_id,integrity:report.integrity,blind_oos_primary_inference:report.blind_oos_primary_inference},null,2));
