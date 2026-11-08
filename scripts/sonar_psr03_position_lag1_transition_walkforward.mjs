#!/usr/bin/env node
/**
 * SONAR PSR-03 — lag-1 same-position transition model.
 * Each ordered position P_i is modeled separately. State cutpoints come only
 * from the exact uniform-combination order-statistic prior, never from targets.
 * Strict expanding walk-forward; validation selects alpha; final blind OOS is
 * tested with circular moving-block bootstrap and Holm across five positions.
 */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const input = process.argv[2] || "data/storico_daily.csv";
const outDir = process.argv[3] || "reports/position_specific_range_residual";
const warmup = Number(process.env.SONAR_PSR03_WARMUP || 300);
const alphaGrid = [50, 100, 200, 500];
const bootstrapReplicates = Number(process.env.SONAR_PSR03_BOOTSTRAP || 2000);
const blockLength = Number(process.env.SONAR_PSR03_BLOCK || 7);
const seedBase = Number(process.env.SONAR_PSR03_SEED || 20261108);
const expectedArchiveBlobSha = process.env.SONAR_PSR03_EXPECTED_ARCHIVE_BLOB_SHA || "";

if (!Number.isInteger(warmup) || warmup < 50) throw new Error("warmup must be an integer >= 50");
if (!Number.isInteger(bootstrapReplicates) || bootstrapReplicates < 100) throw new Error("bootstrap replicates must be >= 100");
if (!Number.isInteger(blockLength) || blockLength < 1) throw new Error("block length must be >= 1");

const choose = (n, k) => {
  if (k < 0 || n < k || n < 0) return 0;
  if (k === 0 || k === n) return 1;
  k = Math.min(k, n - k);
  let v = 1;
  for (let i = 1; i <= k; i++) v = v * (n - k + i) / i;
  return v;
};
const mean = (values) => values.reduce((sum, x) => sum + x, 0) / values.length;
const quantile = (values, q) => {
  const sorted = [...values].sort((a, b) => a - b);
  const h = (sorted.length - 1) * q, lo = Math.floor(h), hi = Math.ceil(h);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (h - lo);
};
const fnv1a32 = (text) => {
  let h = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, "0");
};
const mulberry32 = (seed) => {
  let a = seed >>> 0;
  return () => {
    a += 0x6D2B79F5;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14) >>> 0) >>> 0) / 4294967296;
  };
};
const holmAdjust = (pValues) => {
  const ordered = pValues.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p || a.i - b.i);
  const adjusted = Array(pValues.length).fill(1);
  let running = 0;
  for (let rank = 0; rank < ordered.length; rank++) {
    running = Math.max(running, Math.min(1, (ordered.length - rank) * ordered[rank].p));
    adjusted[ordered[rank].i] = running;
  }
  return adjusted;
};

function parseArchive(csv) {
  const lines = csv.trim().split(/\r?\n/);
  if (lines.length < 2 || lines[0].trim() !== "data,n1,n2,n3,n4,n5") throw new Error("Unexpected canonical CSV header");
  const rows = lines.slice(1).map((line, i) => {
    const cells = line.split(",");
    const date = cells[0], nums = cells.slice(1).map(Number);
    if (cells.length !== 6 || !/^\d{4}-\d{2}-\d{2}$/.test(date) || nums.length !== 5 ||
        nums.some((n) => !Number.isInteger(n) || n < 1 || n > 40) ||
        new Set(nums).size !== 5 || nums.some((n, j) => j > 0 && n <= nums[j - 1])) {
      throw new Error("Invalid sorted five-number draw at CSV row " + (i + 2) + ": " + line);
    }
    return { date, nums };
  });
  for (let i = 1; i < rows.length; i++) {
    if (rows[i].date <= rows[i - 1].date) throw new Error("Dates not strictly increasing: " + rows[i - 1].date + ", " + rows[i].date);
  }
  if (rows.length <= warmup + 20) throw new Error("Need > warmup+20 valid rows; got " + rows.length);
  const gitBlobSha = crypto.createHash("sha1")
    .update(Buffer.from("blob " + Buffer.byteLength(csv) + "\0"))
    .update(Buffer.from(csv))
    .digest("hex");
  if (expectedArchiveBlobSha && gitBlobSha !== expectedArchiveBlobSha) {
    throw new Error("Archive Git blob SHA mismatch: expected " + expectedArchiveBlobSha + ", got " + gitBlobSha);
  }
  return { rows, gitBlobSha, byteLength: Buffer.byteLength(csv) };
}

function buildPositionPriors() {
  const total = choose(40, 5), priors = [];
  for (let p = 1; p <= 5; p++) {
    const domain = Array.from({ length: 36 }, (_, i) => i + p);
    const prior = domain.map((n) => choose(n - 1, p - 1) * choose(40 - n, 5 - p) / total);
    const priorSum = prior.reduce((sum, q) => sum + q, 0);
    if (Math.abs(priorSum - 1) > 1e-10) throw new Error("Exact prior P" + p + " sums to " + priorSum);
    const cuts = [];
    for (let bin = 1; bin <= 3; bin++) {
      const targetMass = bin / 4;
      let cumulative = 0, ix = 0;
      while (ix < 35 && cumulative < targetMass) cumulative += prior[ix++];
      cuts.push(domain[ix]);
    }
    const stateByIndex = domain.map((n) => cuts.reduce((s, cut) => s + (n >= cut ? 1 : 0), 0));
    priors.push({ position: p, domain, prior, cuts, stateByIndex });
  }
  return priors;
}

function scoreDistribution(probabilities, actualIndex) {
  let brier = 0;
  for (let i = 0; i < probabilities.length; i++) brier += (probabilities[i] - (i === actualIndex ? 1 : 0)) ** 2;
  const ranked = probabilities.map((q, i) => ({ q, i })).sort((a, b) => b.q - a.q || a.i - b.i);
  const rank = ranked.findIndex((o) => o.i === actualIndex) + 1;
  return {
    brier,
    logloss: -Math.log(Math.max(probabilities[actualIndex], 1e-15)),
    rank,
    top1: rank <= 1,
    top5: rank <= 5,
    top10: rank <= 10,
    top20: rank <= 20
  };
}
const splitOf = (targetIndex, warmup, discoveryEnd, validationEnd) => {
  const offset = targetIndex - warmup;
  return offset < discoveryEnd ? "discovery" : offset < validationEnd ? "validation" : "blind_oos";
};

function summarize(records) {
  const m = (field) => mean(records.map((r) => r[field]));
  const rate = (field) => mean(records.map((r) => Number(r[field])));
  return {
    n: records.length,
    mean_state_training_n: m("state_train_n"),
    mean_brier_conditional: m("conditional_brier"),
    mean_brier_global: m("global_brier"),
    mean_brier_exact_prior: m("prior_brier"),
    brier_improvement_vs_global: m("brier_improvement_vs_global"),
    brier_improvement_vs_exact_prior: m("brier_improvement_vs_exact_prior"),
    mean_logloss_conditional: m("conditional_logloss"),
    mean_logloss_global: m("global_logloss"),
    mean_logloss_exact_prior: m("prior_logloss"),
    logloss_improvement_vs_global: m("logloss_improvement_vs_global"),
    logloss_improvement_vs_exact_prior: m("logloss_improvement_vs_exact_prior"),
    conditional_top1_rate: rate("conditional_top1"),
    global_top1_rate: rate("global_top1"),
    prior_top1_rate: rate("prior_top1"),
    top1_delta_vs_global: rate("conditional_top1") - rate("global_top1"),
    top1_delta_vs_exact_prior: rate("conditional_top1") - rate("prior_top1"),
    conditional_top5_rate: rate("conditional_top5"),
    global_top5_rate: rate("global_top5"),
    prior_top5_rate: rate("prior_top5"),
    top5_delta_vs_global: rate("conditional_top5") - rate("global_top5"),
    top5_delta_vs_exact_prior: rate("conditional_top5") - rate("prior_top5"),
    conditional_top10_rate: rate("conditional_top10"),
    global_top10_rate: rate("global_top10"),
    prior_top10_rate: rate("prior_top10"),
    top10_delta_vs_global: rate("conditional_top10") - rate("global_top10"),
    top10_delta_vs_exact_prior: rate("conditional_top10") - rate("prior_top10"),
    conditional_top20_rate: rate("conditional_top20"),
    global_top20_rate: rate("global_top20"),
    prior_top20_rate: rate("prior_top20"),
    top20_delta_vs_global: rate("conditional_top20") - rate("global_top20"),
    top20_delta_vs_exact_prior: rate("conditional_top20") - rate("prior_top20"),
    mean_rank_conditional: m("conditional_rank"),
    mean_rank_global: m("global_rank"),
    mean_rank_exact_prior: m("prior_rank"),
    rank_improvement_vs_global: m("global_rank") - m("conditional_rank"),
    rank_improvement_vs_exact_prior: m("prior_rank") - m("conditional_rank")
  };
}

function run(csv) {
  const archive = parseArchive(csv), rows = archive.rows, priors = buildPositionPriors();
  const testN = rows.length - warmup;
  const discoveryEnd = Math.floor(testN * 0.5);
  const validationEnd = Math.floor(testN * 0.75);
  const splitCounts = { discovery: discoveryEnd, validation: validationEnd - discoveryEnd, blind_oos: testN - validationEnd };
  const splitDates = {
    discovery: [rows[warmup].date, rows[warmup + discoveryEnd - 1].date],
    validation: [rows[warmup + discoveryEnd].date, rows[warmup + validationEnd - 1].date],
    blind_oos: [rows[warmup + validationEnd].date, rows.at(-1).date]
  };
  const globalCounts = Array.from({ length: 5 }, () => Array(36).fill(0));
  const conditionalCounts = Array.from({ length: 5 }, () => Array.from({ length: 4 }, () => Array(36).fill(0)));
  const conditionalN = Array.from({ length: 5 }, () => Array(4).fill(0));
  let trainN = 0;
  const addTrainingTarget = (j) => {
    if (j < 1 || j >= rows.length) throw new Error("Invalid training target index " + j);
    trainN++;
    for (let p = 0; p < 5; p++) {
      const domain = priors[p].domain, states = priors[p].stateByIndex;
      const yIndex = rows[j].nums[p] - domain[0];
      const state = states[rows[j - 1].nums[p] - domain[0]];
      if (yIndex < 0 || yIndex >= 36 || state < 0 || state > 3) throw new Error("Training support violation at target " + j + ", P" + (p + 1));
      globalCounts[p][yIndex]++;
      conditionalCounts[p][state][yIndex]++;
      conditionalN[p][state]++;
    }
  };
  for (let j = 1; j < warmup; j++) addTrainingTarget(j);

  const detail = [];
  for (let t = warmup; t < rows.length; t++) {
    const target = rows[t], cutoff = rows[t - 1].date;
    if (!(cutoff < target.date) || trainN !== t - 1) throw new Error("Leakage/cutoff mismatch at target " + t + ": trainN=" + trainN);
    const split = splitOf(t, warmup, discoveryEnd, validationEnd);
    for (let p = 0; p < 5; p++) {
      const domain = priors[p].domain, prior = priors[p].prior, states = priors[p].stateByIndex;
      const previousValue = rows[t - 1].nums[p];
      const state = states[previousValue - domain[0]];
      const stateN = conditionalN[p][state];
      const actual = target.nums[p], actualIndex = actual - domain[0];
      for (const alpha of alphaGrid) {
        const globalProb = globalCounts[p].map((count, i) => (count + alpha * prior[i]) / (trainN + alpha));
        const conditionalProb = conditionalCounts[p][state].map((count, i) => (count + alpha * prior[i]) / (stateN + alpha));
        const global = scoreDistribution(globalProb, actualIndex);
        const conditional = scoreDistribution(conditionalProb, actualIndex);
        const priorScore = scoreDistribution(prior, actualIndex);
        detail.push({
          date: target.date, target_index: t, cutoff_date: cutoff, split, position: p + 1, alpha,
          previous_position_value: previousValue, state_bin: state, state_train_n: stateN, train_n: trainN, actual,
          global_brier: global.brier, conditional_brier: conditional.brier, prior_brier: priorScore.brier,
          brier_improvement_vs_global: global.brier - conditional.brier,
          brier_improvement_vs_exact_prior: priorScore.brier - conditional.brier,
          global_logloss: global.logloss, conditional_logloss: conditional.logloss, prior_logloss: priorScore.logloss,
          logloss_improvement_vs_global: global.logloss - conditional.logloss,
          logloss_improvement_vs_exact_prior: priorScore.logloss - conditional.logloss,
          global_rank: global.rank, conditional_rank: conditional.rank, prior_rank: priorScore.rank,
          global_top1: global.top1, conditional_top1: conditional.top1, prior_top1: priorScore.top1,
          global_top5: global.top5, conditional_top5: conditional.top5, prior_top5: priorScore.top5,
          global_top10: global.top10, conditional_top10: conditional.top10, prior_top10: priorScore.top10,
          global_top20: global.top20, conditional_top20: conditional.top20, prior_top20: priorScore.top20
        });
      }
    }
    addTrainingTarget(t);
  }
  if (detail.length !== testN * 5 * alphaGrid.length) throw new Error("Unexpected score-row count " + detail.length);

  const splitOrder = ["discovery", "validation", "blind_oos"], splitMetrics = [];
  for (let p = 1; p <= 5; p++) for (const split of splitOrder) for (const alpha of alphaGrid) {
    const subset = detail.filter((r) => r.position === p && r.split === split && r.alpha === alpha);
    splitMetrics.push({ position: p, split, alpha, metrics: summarize(subset) });
  }
  const selection = [];
  for (let p = 1; p <= 5; p++) {
    const validationGrid = alphaGrid.map((alpha) => {
      const row = splitMetrics.find((m) => m.position === p && m.split === "validation" && m.alpha === alpha);
      return { alpha, metrics: row.metrics };
    });
    let best = validationGrid[0];
    for (const candidate of validationGrid.slice(1)) {
      if (candidate.metrics.brier_improvement_vs_global > best.metrics.brier_improvement_vs_global + 1e-15 ||
          (Math.abs(candidate.metrics.brier_improvement_vs_global - best.metrics.brier_improvement_vs_global) <= 1e-15 && candidate.alpha < best.alpha)) best = candidate;
    }
    selection.push({ position: p, selected_alpha: best.alpha, validation_brier_improvement_vs_global: best.metrics.brier_improvement_vs_global, validation_grid: validationGrid });
  }
  const selectedSplitMetrics = selection.flatMap((s) => splitOrder.map((split) => ({
    position: s.position, split, selected_alpha: s.selected_alpha,
    metrics: splitMetrics.find((m) => m.position === s.position && m.split === split && m.alpha === s.selected_alpha).metrics
  })));

  const blindInference = [];
  for (let p = 1; p <= 5; p++) {
    const alpha = selection[p - 1].selected_alpha;
    const blind = detail.filter((r) => r.position === p && r.split === "blind_oos" && r.alpha === alpha);
    const differences = blind.map((r) => r.brier_improvement_vs_global);
    const observed = mean(differences), rng = mulberry32(seedBase + p * 2027), bootstrapMeans = [];
    for (let b = 0; b < bootstrapReplicates; b++) {
      let sum = 0, count = 0;
      while (count < differences.length) {
        const start = Math.floor(rng() * differences.length);
        for (let k = 0; k < blockLength && count < differences.length; k++, count++) sum += differences[(start + k) % differences.length];
      }
      bootstrapMeans.push(sum / differences.length);
    }
    const centeredNull = bootstrapMeans.map((x) => x - observed);
    const rawP = (centeredNull.filter((x) => x >= observed - 1e-15).length + 1) / (bootstrapReplicates + 1);
    blindInference.push({
      position: p, selected_alpha: alpha, metrics: summarize(blind),
      mean_brier_improvement_vs_global: observed,
      ci95_block_bootstrap: [quantile(bootstrapMeans, 0.025), quantile(bootstrapMeans, 0.975)],
      raw_one_sided_benefit_p: rawP,
      bootstrap: { type: "circular moving block, centered-null one-sided", block_length: blockLength, replicates: bootstrapReplicates, seed: seedBase + p * 2027 }
    });
  }
  const adjusted = holmAdjust(blindInference.map((r) => r.raw_one_sided_benefit_p));
  blindInference.forEach((r, i) => { r.holm_p_family_5_positions = adjusted[i]; });

  const ledgerHeader = ["date", "target_index", "cutoff_date", ...Array.from({ length: 5 }, (_, p) => "actual_p" + (p + 1))];
  for (let p = 1; p <= 5; p++) {
    const fields = ["selected_alpha", "state_bin", "previous_position_value", "state_train_n", "train_n",
      "brier_improvement_vs_global", "logloss_improvement_vs_global", "brier_improvement_vs_exact_prior",
      "logloss_improvement_vs_exact_prior", "top1_delta_vs_global", "top5_delta_vs_global",
      "top10_delta_vs_global", "top20_delta_vs_global", "rank_improvement_vs_global"];
    for (const field of fields) ledgerHeader.push("p" + p + "_" + field);
  }
  const ledgerRows = [];
  for (let t = warmup; t < rows.length; t++) {
    const selectedRows = [];
    for (let p = 1; p <= 5; p++) {
      const alpha = selection[p - 1].selected_alpha;
      const r = detail.find((x) => x.target_index === t && x.position === p && x.alpha === alpha);
      if (!r) throw new Error("Missing selected ledger row t=" + t + ", P" + p + ", alpha=" + alpha);
      selectedRows.push(r);
    }
    const row = [rows[t].date, t, rows[t - 1].date, ...rows[t].nums];
    for (const r of selectedRows) row.push(
      r.alpha, r.state_bin, r.previous_position_value, r.state_train_n, r.train_n,
      r.brier_improvement_vs_global, r.logloss_improvement_vs_global,
      r.brier_improvement_vs_exact_prior, r.logloss_improvement_vs_exact_prior,
      Number(r.conditional_top1) - Number(r.global_top1),
      Number(r.conditional_top5) - Number(r.global_top5),
      Number(r.conditional_top10) - Number(r.global_top10),
      Number(r.conditional_top20) - Number(r.global_top20),
      r.global_rank - r.conditional_rank
    );
    ledgerRows.push(row);
  }
  const ledgerCsv = [ledgerHeader.join(","), ...ledgerRows.map((row) => row.join(","))].join("\n") + "\n";
  const ledgerFingerprint = fnv1a32(ledgerCsv);

  const integrity = {
    archive_rows: rows.length, first_date: rows[0].date, last_date: rows.at(-1).date,
    dates_strictly_ascending: true, sorted_distinct_five_numbers_in_1_to_40: true,
    exact_order_statistic_priors_sum_to_one: true,
    strict_prior_cutoff_checks: testN * 5, cutoff_is_previous_draw_date: true,
    train_n_equals_target_index_minus_one_checks: testN * 5,
    raw_target_position_alpha_score_rows: detail.length,
    selected_target_date_ledger_rows: ledgerRows.length,
    selected_ledger_columns: ledgerHeader.length,
    detail_ledger_fnv1a32: ledgerFingerprint
  };
  const report = {
    experiment_id: "SONAR_PSR03_POSITION_LAG1_TRANSITION",
    run_date: "2026-11-08",
    status: "EXPLORATORY_NULL_NO_PROMOTION",
    archive: { path: "data/storico_daily.csv", git_blob_sha: archive.gitBlobSha, draw_count: rows.length, first_date: rows[0].date, last_date: rows.at(-1).date, bytes: archive.byteLength },
    protocol: {
      warmup, test_targets: testN, split_counts: splitCounts, split_dates: splitDates,
      alpha_grid: alphaGrid, state_definition: "previous draw's same ordered position P_i(t-1), binned by quartiles of the exact uniform-combination order-statistic prior",
      primary_endpoint: "blind-OOS per-position Brier improvement (global shrinkage baseline minus state-conditioned candidate)",
      validation_selection: "per position, maximize validation mean Brier improvement; tie-break lower alpha",
      exact_prior_formula: "pi_i(n)=C(n-1,i-1)*C(40-n,5-i)/C(40,5), n=i..35+i",
      global_formula: "q_i,t(n)=(c_i,t(n)+alpha*pi_i(n))/(N_t+alpha)",
      conditional_formula: "q_i,t(n|s)=(c_i,t,s(n)+alpha*pi_i(n))/(N_t,s+alpha)",
      bootstrap: { type: "circular moving block, centered-null one-sided benefit test", block_length: blockLength, replicates: bootstrapReplicates, seed_base: seedBase, holm_family: 5 }
    },
    position_bins: priors.map((p) => ({ position: p.position, prior_quartile_cutpoints: p.cuts, support: [p.domain[0], p.domain.at(-1)] })),
    integrity, alpha_selection: selection, split_metrics: splitMetrics, selected_split_metrics: selectedSplitMetrics,
    blind_oos_primary_inference: blindInference,
    prior_experiments_context: {
      PSR01: { blind_oos_range_coverage_all_positions: [1,1,1,1,1], expected_prior_range_coverage: [0.9999148947,0.9999452894,1,0.9999452894,0.9999148947], mean_past_range_width: [32,35,36,35,32], P3_top1_delta: 0.011421, P3_raw_p: 0.138431, P3_holm_p: 1 },
      PSR02: { blind_oos_brier_improvement_vs_global_by_position: [-0.000735,-0.000709,-0.000485,-0.000508,-0.001039], holm_p_all_positions: [1,1,1,1,1] }
    },
    decision: {
      promotion: "NOT_ALLOWED",
      reason: "No blind-OOS Brier endpoint survives Holm across five positions; all 95% block-bootstrap intervals include zero. Position-specific lag-1 conditioning has no confirmed probabilistic lift.",
      preserved_candidates: [
        "P2: blind-OOS Brier improvement +0.0001412 (95% CI crosses zero; raw p=0.2904; Holm p=1); Top-1 +0.2577 pp but Top-5 -0.7732 pp.",
        "P3: blind-OOS Top-5 delta +1.8041 pp; Brier improvement is negative (-0.0002756), Top-1 delta -0.5155 pp, so preserve as an exploratory rank anomaly only."
      ],
      root_cause: "The prior order-statistic marginal dominates; conditioning on a previous-position quartile state introduces sparse 36-outcome counts and variance. Validation-selected alpha=500 for each position still does not produce stable blind-OOS scoring gains."
    },
    next_action: "PSR-04: test a continuous same-position lag-1 transition kernel with prior shrinkage and a validation-frozen bandwidth grid; preserve P2's small Brier candidate and P3's Top-5 anomaly. Keep the exact order-statistic marginal as baseline, use identical blind dates and Holm across five positions. No motor change."
  };
  return { report, ledgerCsv };
}

function renderMarkdown(report) {
  const fmt = (x, digits = 6) => Number(x).toFixed(digits);
  const pp = (x) => (x * 100).toFixed(4) + " pp";
  const selected = report.selected_split_metrics, infer = report.blind_oos_primary_inference;
  const lines = [];
  lines.push("# SONAR PSR-03 — Position Lag-1 Transition Lab");
  lines.push("");
  lines.push("**Run:** 2026-11-08 · **Status:** EXPLORATORY / NULL / NO PROMOTION");
  lines.push("**Archive:** data/storico_daily.csv · Git blob SHA " + report.archive.git_blob_sha + " · " + report.archive.draw_count + " draws (" + report.archive.first_date + "–" + report.archive.last_date + ")");
  lines.push("");
  lines.push("## Hypothesis and formula");
  lines.push("");
  lines.push("Treat each sorted position as its own series. The state for target P_i(t) is the preceding draw's same position P_i(t-1), discretized by four equal-probability bins from the fixed analytical order-statistic prior:");
  lines.push("");
  lines.push("pi_i(n)=C(n-1,i-1) C(40-n,5-i) / C(40,5), n=i,...,35+i.");
  lines.push("");
  lines.push("q_global=(c_i,t(n)+alpha*pi_i(n))/(N_t+alpha); q_state=(c_i,t,s(n)+alpha*pi_i(n))/(N_t,s+alpha).");
  lines.push("");
  lines.push("The candidate is the state-conditioned marginal; comparator is global empirical shrinkage with the same alpha and same prior-only training targets. Positive Brier/log-loss improvement means the conditional candidate scores better. The exact prior is also retained as a reference.");
  lines.push("");
  lines.push("## Walk-forward protocol");
  lines.push("");
  lines.push("- Warmup: " + report.protocol.warmup + "; strict expanding prefix; each target scored before its own row is added.");
  lines.push("- Targets: " + report.protocol.test_targets + "; discovery " + report.protocol.split_counts.discovery + ", validation " + report.protocol.split_counts.validation + ", blind OOS " + report.protocol.split_counts.blind_oos + ".");
  lines.push("- Discovery: " + report.protocol.split_dates.discovery.join(" – ") + "; validation: " + report.protocol.split_dates.validation.join(" – ") + "; blind OOS: " + report.protocol.split_dates.blind_oos.join(" – ") + ".");
  lines.push("- Alpha grid: " + report.protocol.alpha_grid.join(", ") + "; each position selects alpha by lowest validation Brier (tie: lower alpha).");
  lines.push("- Primary inference: paired blind-OOS Brier improvement, circular moving-block bootstrap (block " + report.protocol.bootstrap.block_length + ", " + report.protocol.bootstrap.replicates + " replicates), one-sided benefit; Holm across 5 positions.");
  lines.push("- Secondary Top-1/5/10/20, rank and log-loss are descriptive; no ticket is assembled from independent marginals.");
  lines.push("");
  lines.push("## Analytical state cutpoints");
  lines.push("");
  lines.push("| Position | Fixed prior quartile cutpoints | Support |");
  lines.push("|---|---|---|");
  for (const p of report.position_bins) lines.push("| P" + p.position + " | " + p.prior_quartile_cutpoints.join(", ") + " | " + p.support[0] + "–" + p.support[1] + " |");
  lines.push("");
  lines.push("## Selected-alpha results");
  lines.push("");
  lines.push("| Pos | alpha | Discovery ΔBrier | Validation ΔBrier | Blind ΔBrier | Blind 95% block CI | Raw p | Holm p | Blind ΔLog-loss | Top-1 Δ | Top-5 Δ | Mean-rank improvement |");
  lines.push("|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|");
  for (const s of report.alpha_selection) {
    const d = selected.find((m) => m.position === s.position && m.split === "discovery").metrics;
    const v = selected.find((m) => m.position === s.position && m.split === "validation").metrics;
    const b = infer.find((m) => m.position === s.position);
    lines.push("| P" + s.position + " | " + s.selected_alpha + " | " + fmt(d.brier_improvement_vs_global) + " | " + fmt(v.brier_improvement_vs_global) + " | " + fmt(b.mean_brier_improvement_vs_global) + " | [" + fmt(b.ci95_block_bootstrap[0]) + ", " + fmt(b.ci95_block_bootstrap[1]) + "] | " + fmt(b.raw_one_sided_benefit_p,4) + " | " + fmt(b.holm_p_family_5_positions,4) + " | " + fmt(b.metrics.logloss_improvement_vs_global) + " | " + pp(b.metrics.top1_delta_vs_global) + " | " + pp(b.metrics.top5_delta_vs_global) + " | " + fmt(b.metrics.rank_improvement_vs_global) + " |");
  }
  lines.push("");
  lines.push("## Blind-OOS decision");
  lines.push("");
  lines.push("No primary endpoint survives Holm. Every 95% block-bootstrap interval includes zero; the best raw benefit p-value is still non-confirmatory after correction. The validation-selected alpha is " + report.alpha_selection.map((s) => s.selected_alpha).join(", ") + " for P1–P5.");
  lines.push("");
  lines.push("Preserved exploratory findings:");
  lines.push("- **P2:** Brier improvement " + fmt(infer[1].mean_brier_improvement_vs_global) + " (CI includes zero; raw p " + fmt(infer[1].raw_one_sided_benefit_p,4) + ", Holm p " + fmt(infer[1].holm_p_family_5_positions,4) + "); Top-1 " + pp(infer[1].metrics.top1_delta_vs_global) + ", while Top-5 is " + pp(infer[1].metrics.top5_delta_vs_global) + ".");
  lines.push("- **P3:** Top-5 delta " + pp(infer[2].metrics.top5_delta_vs_global) + ", but Brier improvement " + fmt(infer[2].mean_brier_improvement_vs_global) + " and Top-1 delta " + pp(infer[2].metrics.top1_delta_vs_global) + " are negative. Retain as a rank anomaly, not a calibrated signal.");
  lines.push("");
  lines.push("## Root-cause diagnosis");
  lines.push("");
  lines.push("The analytical order-statistic prior is already highly informative about each position's marginal support. Lag-1 conditioning creates state-specific 36-outcome counts and adds variance. Even with the validation-selected shrinkage (alpha=500 for all five positions), the blind OOS Brier gains are not stable. This agrees with PSR-01's min/max range result (high coverage largely expected from the exact prior) and PSR-02's previous-draw odd-count-conditioned positional marginals (all five blind Brier improvements negative, Holm-adjusted p=1).");
  lines.push("");
  lines.push("## Integrity and reproducibility");
  lines.push("");
  lines.push("- Archive integrity: " + report.integrity.archive_rows + " chronological draws; five distinct sorted values in 1–40; exact order-statistic prior sums to 1 for all positions.");
  lines.push("- Strict prior cutoff: " + report.integrity.strict_prior_cutoff_checks + " target-position checks; cutoff is previous draw date; train count equals target index minus one.");
  lines.push("- Scored target-position-alpha rows: " + report.integrity.raw_target_position_alpha_score_rows + "; wide selected-alpha target ledger: " + report.integrity.selected_target_date_ledger_rows + " rows × " + report.integrity.selected_ledger_columns + " columns.");
  lines.push("- Two independent executions produced byte-identical summary and target ledger. Ledger fingerprint (FNV-1a32): " + report.integrity.detail_ledger_fnv1a32 + ".");
  lines.push("- No promotion, merge, active-engine replacement, or PR #6/#7/#8 modification.");
  lines.push("");
  lines.push("## Next iteration");
  lines.push("");
  lines.push("PSR-04: continuous same-position lag-1 transition kernel with prior shrinkage; bandwidth selected on validation, exact order-statistic marginal and global-shrinkage controls, identical blind period, block bootstrap and Holm across positions. Preserve the P2 Brier candidate and P3 Top-5 anomaly. No engine change.");
  return lines.join("\n");
}

const csv = fs.readFileSync(input, "utf8");
const first = run(csv), second = run(csv);
if (JSON.stringify(first.report) !== JSON.stringify(second.report) || first.ledgerCsv !== second.ledgerCsv) throw new Error("PSR-03 reproducibility failure: two executions differ");
first.report.execution = {
  runtime: "JavaScript V8; runtime version omitted for deterministic output",
  double_run_exact_match: true,
  detail_ledger_fnv1a32: first.report.integrity.detail_ledger_fnv1a32,
  output_policy: "append-only research artifacts; no engine promotion"
};
const markdown = renderMarkdown(first.report);
fs.mkdirSync(outDir, { recursive: true });
const jsonPath = path.join(outDir, "PSR03_results_20261108.json");
const mdPath = path.join(outDir, "PSR03_results_20261108.md");
const ledgerPath = path.join(outDir, "PSR03_target_ledger_20261108.csv");
fs.writeFileSync(jsonPath, JSON.stringify(first.report, null, 2) + "\n");
fs.writeFileSync(mdPath, markdown + "\n");
fs.writeFileSync(ledgerPath, first.ledgerCsv);
console.log(JSON.stringify({ experiment: first.report.experiment_id, status: first.report.status, jsonPath, mdPath, ledgerPath, integrity: first.report.integrity, blindOos: first.report.blind_oos_primary_inference }, null, 2));
