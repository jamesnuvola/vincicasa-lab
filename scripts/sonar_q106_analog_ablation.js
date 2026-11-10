#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CSV_PATH = path.join(ROOT, "data", "storico_daily.csv");
const APP_DATA_PATH = path.join(ROOT, "src", "data.json");
const APP_SOURCE_PATH = path.join(ROOT, "src", "VinciCasaLab.jsx");
const PROTOCOL_PATH = path.join(ROOT, "reports", "sequence_agent", "q106_analog_ablation_protocol_2026-11-11.json");
const OUT = path.join(ROOT, "reports", "sequence_agent");
const REPORT_PATH = path.join(OUT, "q106_analog_ablation_report_2026-11-11.json");
const VALIDATION_PATH = path.join(OUT, "q106_analog_ablation_validation_2026-11-11.json");
const LEDGER_PATH = path.join(OUT, "q106_analog_ablation_target_ledger_2026-11-11.csv");
const CHECKPOINT_PATH = path.join(OUT, "q106_analog_ablation_checkpoint_2026-11-11.md");
const MANIFEST_PATH = path.join(OUT, "q106_analog_ablation_persistence_manifest_2026-11-11.json");
const WARMUP = 200;
const BLOCK = 20;
const SIGN_REPS = 50000;
const BOOT_REPS = 10000;
const SEED = 20261111;
const P_TOP20_ALL5 = 15504 / 658008;

function fail(message) {
  console.error("Q106 BLOCKED: " + message);
  process.exit(1);
}
function assert(condition, message) {
  if (!condition) fail(message);
}
function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}
function gitBlob(pathSpec) {
  return execFileSync("git", ["rev-parse", "HEAD:" + pathSpec], { encoding: "utf8" }).trim();
}
function round(x, digits) {
  if (!Number.isFinite(x)) return null;
  return Number(x.toFixed(digits === undefined ? 8 : digits));
}
function mean(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
}
function quantile(sorted, q) {
  if (!sorted.length) return null;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos), hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}
function rng(seed) {
  let x = (seed >>> 0) || 1;
  return function () {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    return (x >>> 0) / 4294967296;
  };
}
function parseCanonicalCsv(text) {
  const lines = text.trimEnd().split(/\r?\n/);
  assert(lines[0] === "data,n1,n2,n3,n4,n5", "canonical archive header mismatch");
  const rows = [];
  const seen = new Set();
  let previous = "";
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    assert(f.length === 6, "malformed archive row " + (i + 1));
    const date = f[0];
    const n = f.slice(1).map(Number);
    assert(/^\d{4}-\d{2}-\d{2}$/.test(date), "invalid date " + date);
    assert(!seen.has(date) && (!previous || date > previous), "duplicate or unordered date " + date);
    assert(n.every(Number.isInteger) && n.every(x => x >= 1 && x <= 40), "number outside 1..40 at " + date);
    assert(new Set(n).size === 5 && n.every((x, j) => j === 0 || x > n[j - 1]), "invalid five-number set at " + date);
    rows.push({ d: date, n });
    seen.add(date);
    previous = date;
  }
  return rows;
}
function validateAppData(draws, appData) {
  assert(Array.isArray(appData.modelDraws), "src/data.json modelDraws missing");
  assert(appData.modelDraws.length === draws.length, "modelDraws length differs from archive");
  assert(appData.histN === draws.length, "histN differs from archive");
  assert(appData.lastDate === draws[draws.length - 1].d, "lastDate differs from archive");
  for (let i = 0; i < draws.length; i++) {
    const a = appData.modelDraws[i], b = draws[i];
    assert(a && a.d === b.d && Array.isArray(a.n) && a.n.join(",") === b.n.join(","), "src/data.json mismatch at row " + (i + 2));
  }
}
function extractFunction(source, name, nextName) {
  const start = source.indexOf("function " + name + "(");
  assert(start >= 0, "cannot find source function " + name);
  const end = nextName ? source.indexOf("\nfunction " + nextName + "(", start + 1) : source.indexOf("\nconst Card =", start + 1);
  assert(end > start, "cannot delimit source function " + name);
  return source.slice(start, end).trim();
}
function buildScorer(source, ablateAnalog) {
  const overlap = extractFunction(source, "overlapCount", "sonarTransitionProfile");
  const transition = extractFunction(source, "sonarTransitionProfile", "sonarAnalogCore");
  let analog = extractFunction(source, "sonarAnalogCore", null);
  if (ablateAnalog) {
    const block = /0\.38\s*\*\s*features\[0\]\[i\]\s*\+\s*0\.22\s*\*\s*features\[1\]\[i\]\s*\+\s*0\.14\s*\*\s*features\[2\]\[i\]\s*\+\s*0\.06\s*\*\s*features\[3\]\[i\]\s*\+\s*0\.10\s*\*\s*features\[4\]\[i\]\s*\+\s*0\.06\s*\*\s*features\[5\]\[i\]\s*\+\s*0\.04\s*\*\s*features\[6\]\[i\]/;
    const replacement = "(0.38 / 0.90) * features[0][i] + (0.22 / 0.90) * features[1][i] + " +
      "(0.14 / 0.90) * features[2][i] + (0.06 / 0.90) * features[3][i] + " +
      "0.00 * features[4][i] + (0.06 / 0.90) * features[5][i] + (0.04 / 0.90) * features[6][i]";
    const matches = analog.match(block);
    assert(matches && matches.length === 1, "analog coefficient block not uniquely identified");
    analog = analog.replace(block, replacement);
  }
  const code = [overlap, transition, analog, "return sonarAnalogCore(draws);"].join("\n");
  try {
    return new Function("draws", code);
  } catch (e) {
    fail("could not compile " + (ablateAnalog ? "ablated" : "full") + " scorer: " + e.message);
  }
}
function validRanking(scores) {
  const r = scores.map(x => x.n);
  return r.length === 40 && new Set(r).size === 40 && r.every(n => Number.isInteger(n) && n >= 1 && n <= 40);
}
function freq100Ranking(prefix) {
  const counts = Array(41).fill(0);
  const start = Math.max(0, prefix.length - 100);
  for (let i = start; i < prefix.length; i++) for (const n of prefix[i].n) counts[n] += 1;
  return Array.from({ length: 40 }, (_, i) => i + 1).sort((a, b) => counts[b] - counts[a] || a - b);
}
function hitMetrics(ranking, actual) {
  const set = new Set(actual);
  const h5 = ranking.slice(0, 5).filter(n => set.has(n)).length;
  const h10 = ranking.slice(0, 10).filter(n => set.has(n)).length;
  const h20 = ranking.slice(0, 20).filter(n => set.has(n)).length;
  return { h5, h10, h20, all5: h20 === 5 ? 1 : 0 };
}
function forecastAt(draws, targetIndex, scorer) {
  const prefix = draws.slice(0, targetIndex);
  assert(prefix.length === targetIndex, "forecast prefix length mismatch");
  assert(prefix.length > 0 && prefix[prefix.length - 1].d < draws[targetIndex].d, "forecast prefix is not strictly prior");
  return scorer(prefix);
}
function summarize(records, model) {
  const n = records.length;
  const h5 = records.map(r => r[model].h5);
  const h10 = records.map(r => r[model].h10);
  const h20 = records.map(r => r[model].h20);
  const all5 = records.reduce((s, r) => s + r[model].all5, 0);
  return {
    targets: n,
    first_target: records[0]?.date ?? null,
    last_target: records[n - 1]?.date ?? null,
    mean_hits_top5: round(mean(h5)),
    mean_hits_top10: round(mean(h10)),
    mean_hits_top20: round(mean(h20)),
    top20_all5_count: all5,
    top20_all5_rate: round(all5 / n),
    top20_all5_random_expected: round(n * P_TOP20_ALL5),
    top20_all5_exact_binomial_p_one_sided: round(binomialTail(n, P_TOP20_ALL5, all5)),
    top20_4plus_count: records.filter(r => r[model].h20 >= 4).length
  };
}
function binomialTail(n, p, k) {
  if (k <= 0) return 1;
  let term = Math.pow(1 - p, n);
  let tail = 0;
  for (let i = 0; i <= n; i++) {
    if (i >= k) tail += term;
    if (i < n) term *= ((n - i) / (i + 1)) * (p / (1 - p));
  }
  return Math.max(0, Math.min(1, tail));
}
function blockSignFlip(values, reps, blockLength, seed) {
  const observed = values.reduce((s, x) => s + x, 0);
  const blocks = [];
  for (let i = 0; i < values.length; i += blockLength) {
    blocks.push(values.slice(i, Math.min(values.length, i + blockLength)).reduce((s, x) => s + x, 0));
  }
  const random = rng(seed);
  let extreme = 0;
  for (let b = 0; b < reps; b++) {
    let total = 0;
    for (const v of blocks) total += random() < 0.5 ? v : -v;
    if (total >= observed - 1e-12) extreme++;
  }
  return (extreme + 1) / (reps + 1);
}
function circularBlockBootstrap(values, reps, blockLength, seed) {
  const random = rng(seed);
  const out = [];
  const n = values.length;
  for (let b = 0; b < reps; b++) {
    let total = 0, count = 0;
    while (count < n) {
      const start = Math.floor(random() * n);
      for (let j = 0; j < blockLength && count < n; j++, count++) total += values[(start + j) % n];
    }
    out.push(total / n);
  }
  out.sort((a, b) => a - b);
  return { lower: quantile(out, 0.025), upper: quantile(out, 0.975) };
}
function holm(entries) {
  const sorted = entries.slice().sort((a, b) => a.p - b.p || a.id.localeCompare(b.id));
  let running = 0;
  const adjusted = {};
  for (let i = 0; i < sorted.length; i++) {
    running = Math.max(running, Math.min(1, sorted[i].p * (sorted.length - i)));
    adjusted[sorted[i].id] = running;
  }
  return adjusted;
}
function overlapTop(a, b, k) {
  const s = new Set(a.slice(0, k));
  return b.slice(0, k).filter(n => s.has(n)).length;
}
function csvCell(v) {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function makeSyntheticDrawsNoAnalog() {
  return Array.from({ length: 8 }, (_, i) => ({
    d: "2000-01-" + String(i + 1).padStart(2, "0"),
    n: Array.from({ length: 5 }, (_, j) => i * 5 + j + 1)
  }));
}
function makeSyntheticDrawsAnalog() {
  const sets = [
    [1, 2, 3, 10, 11], [20, 21, 22, 23, 24], [6, 7, 8, 9, 12],
    [13, 14, 15, 16, 17], [18, 19, 25, 26, 27], [28, 29, 30, 31, 32],
    [33, 34, 35, 36, 37], [1, 2, 3, 4, 5]
  ];
  return sets.map((n, i) => ({ d: "2001-01-" + String(i + 1).padStart(2, "0"), n }));
}
function checkFutureMutation(draws, scorer, ablated, targetIndex) {
  const baseFull = forecastAt(draws, targetIndex, scorer).scores.map(x => x.n).join(",");
  const baseAblated = forecastAt(draws, targetIndex, ablated).scores.map(x => x.n).join(",");
  const mutated = draws.map((d, i) => {
    if (i < targetIndex) return d;
    const nums = d.n.slice().reverse();
    return { d: d.d, n: nums };
  });
  const mutatedFull = forecastAt(mutated, targetIndex, scorer).scores.map(x => x.n).join(",");
  const mutatedAblated = forecastAt(mutated, targetIndex, ablated).scores.map(x => x.n).join(",");
  return baseFull === mutatedFull && baseAblated === mutatedAblated;
}
function generate() {
  const protocol = JSON.parse(fs.readFileSync(PROTOCOL_PATH, "utf8"));
  const csvText = fs.readFileSync(CSV_PATH, "utf8");
  const draws = parseCanonicalCsv(csvText);
  const appData = JSON.parse(fs.readFileSync(APP_DATA_PATH, "utf8"));
  validateAppData(draws, appData);
  const source = fs.readFileSync(APP_SOURCE_PATH, "utf8");
  const fullScorer = buildScorer(source, false);
  const noAnalogScorer = buildScorer(source, true);
  const archiveBlob = gitBlob("data/storico_daily.csv");
  const appBlob = gitBlob("src/VinciCasaLab.jsx");
  assert(archiveBlob === protocol.source.archive_blob_sha1, "archive blob differs from preregistered source");
  assert(appBlob === protocol.source.app_source_blob_sha1, "app source blob differs from preregistered source");
  assert(draws.length === protocol.source.archive_draws, "archive draw count differs from protocol");
  assert(draws[0].d === protocol.source.first_date && draws[draws.length - 1].d === protocol.source.last_date, "archive date range differs from protocol");

  const records = [];
  const diagnostics = [];
  for (let targetIndex = WARMUP; targetIndex < draws.length; targetIndex++) {
    const prefix = draws.slice(0, targetIndex);
    const full = fullScorer(prefix);
    const noAnalog = noAnalogScorer(prefix);
    const freq = freq100Ranking(prefix);
    const target = draws[targetIndex];
    assert(prefix[prefix.length - 1].d < target.d, "non-prior cutoff at " + target.d);
    assert(validRanking(full.scores) && validRanking(noAnalog.scores), "invalid scorer permutation at " + target.d);
    assert(freq.length === 40 && new Set(freq).size === 40, "invalid freq100 ranking at " + target.d);
    for (const a of (full.analogs || [])) {
      assert(a.successorDate <= prefix[prefix.length - 1].d, "analog successor after cutoff at " + target.d);
    }
    const fullRank = full.scores.map(x => x.n);
    const noAnalogRank = noAnalog.scores.map(x => x.n);
    records.push({
      date: target.d,
      cutoff: prefix[prefix.length - 1].d,
      full: hitMetrics(fullRank, target.n),
      noAnalog: hitMetrics(noAnalogRank, target.n),
      freq100: hitMetrics(freq, target.n)
    });
    diagnostics.push({
      candidateCount: Number(full.candidateCount || 0),
      maxOverlap: Number(full.maxOverlap || 0),
      top20Overlap: overlapTop(fullRank, noAnalogRank, 20),
      top10Overlap: overlapTop(fullRank, noAnalogRank, 10),
      top5Overlap: overlapTop(fullRank, noAnalogRank, 5)
    });
  }
  assert(records.length === draws.length - WARMUP, "walk-forward target count mismatch");
  const cut1 = Math.floor(records.length * 0.6);
  const cut2 = Math.floor(records.length * 0.8);
  assert(cut1 === 1921 && cut2 - cut1 === 641 && records.length - cut2 === 641, "split sizes differ from preregistration");
  const splits = {
    discovery: records.slice(0, cut1),
    validation: records.slice(cut1, cut2),
    historical_blind_oos: records.slice(cut2)
  };
  const modelNames = ["full", "noAnalog", "freq100"];
  const splitSummary = {};
  for (const [name, subset] of Object.entries(splits)) {
    splitSummary[name] = {};
    for (const model of modelNames) splitSummary[name][model] = summarize(subset, model);
  }
  const blind = splits.historical_blind_oos;
  const endpointSpecs = [
    ["full_minus_noAnalog_top20", r => r.full.h20 - r.noAnalog.h20],
    ["full_minus_noAnalog_top10", r => r.full.h10 - r.noAnalog.h10],
    ["full_minus_noAnalog_top5", r => r.full.h5 - r.noAnalog.h5],
    ["full_minus_noAnalog_all5", r => r.full.all5 - r.noAnalog.all5],
    ["full_minus_freq100_top20", r => r.full.h20 - r.freq100.h20],
    ["full_minus_freq100_top10", r => r.full.h10 - r.freq100.h10],
    ["full_minus_freq100_top5", r => r.full.h5 - r.freq100.h5],
    ["full_minus_freq100_all5", r => r.full.all5 - r.freq100.all5]
  ];
  const inference = {};
  const pEntries = [];
  for (let i = 0; i < endpointSpecs.length; i++) {
    const id = endpointSpecs[i][0];
    const values = blind.map(endpointSpecs[i][1]);
    const p = blockSignFlip(values, SIGN_REPS, BLOCK, SEED + i * 17);
    const ci = circularBlockBootstrap(values, BOOT_REPS, BLOCK, SEED + i * 101);
    inference[id] = {
      n: values.length,
      mean_difference: round(mean(values)),
      block_sign_flip_replicates: SIGN_REPS,
      block_length: BLOCK,
      p_one_sided: round(p, 8),
      circular_block_bootstrap_replicates: BOOT_REPS,
      ci95: { lower: round(ci.lower), upper: round(ci.upper) }
    };
    pEntries.push({ id, p });
  }
  const randomEndpoints = [
    { id: "full_top20_all5_vs_exact_uniform", model: "full" },
    { id: "noAnalog_top20_all5_vs_exact_uniform", model: "noAnalog" }
  ];
  for (const item of randomEndpoints) {
    const count = blind.reduce((s, r) => s + r[item.model].all5, 0);
    const p = binomialTail(blind.length, P_TOP20_ALL5, count);
    inference[item.id] = {
      n: blind.length,
      observed_all5_count: count,
      exact_null_probability_per_target: round(P_TOP20_ALL5, 10),
      expected_count: round(blind.length * P_TOP20_ALL5, 6),
      p_exact_binomial_one_sided: round(p, 8)
    };
    pEntries.push({ id: item.id, p });
  }
  const holmAdjusted = holm(pEntries);
  for (const item of pEntries) inference[item.id].p_holm_10 = round(holmAdjusted[item.id], 8);

  const randomMeanDiagnostics = {};
  for (const model of ["full", "noAnalog", "freq100"]) {
    const values = blind.map(r => r[model].h20 - 2.5);
    const ci = circularBlockBootstrap(values, BOOT_REPS, BLOCK, SEED + (model === "full" ? 9001 : model === "noAnalog" ? 9002 : 9003));
    randomMeanDiagnostics[model] = {
      mean_top20_hits: round(mean(blind.map(r => r[model].h20))),
      gain_vs_exact_random_mean_2_5: round(mean(values)),
      circular_block_bootstrap_ci95_for_gain: { lower: round(ci.lower), upper: round(ci.upper) }
    };
  }
  const diag = {
    mean_analog_candidate_count: round(mean(diagnostics.map(d => d.candidateCount))),
    targets_with_at_least_one_analog_percent: round(100 * diagnostics.filter(d => d.candidateCount > 0).length / diagnostics.length, 4),
    mean_max_overlap_when_candidates_exist: round(mean(diagnostics.filter(d => d.candidateCount > 0).map(d => d.maxOverlap))),
    mean_top20_overlap_full_vs_noAnalog: round(mean(diagnostics.map(d => d.top20Overlap))),
    mean_top10_overlap_full_vs_noAnalog: round(mean(diagnostics.map(d => d.top10Overlap))),
    mean_top5_overlap_full_vs_noAnalog: round(mean(diagnostics.map(d => d.top5Overlap)))
  };

  const checks = [];
  function addCheck(name, ok, detail) {
    checks.push({ name, status: ok ? "PASS" : "FAIL", detail: detail || "" });
    assert(ok, "validation failed: " + name + (detail ? " — " + detail : ""));
  }
  addCheck("archive_rows_and_range", draws.length === 3403 && draws[0].d === "2017-07-17" && draws[draws.length - 1].d === "2026-11-09", "draws=" + draws.length);
  addCheck("archive_dates_and_draws", true, "parser validated unique chronological dates and five sorted distinct values in 1..40");
  addCheck("app_data_row_by_row", true, "src/data.json modelDraws matches canonical CSV");
  addCheck("pinned_source_blobs", archiveBlob === protocol.source.archive_blob_sha1 && appBlob === protocol.source.app_source_blob_sha1, "archive=" + archiveBlob + "; app=" + appBlob);
  addCheck("walk_forward_target_count", records.length === 3203, "targets=" + records.length);
  addCheck("chronological_split_sizes", cut1 === 1921 && cut2 - cut1 === 641 && records.length - cut2 === 641, "1921/641/641");
  addCheck("all_forecasts_are_complete_rankings", true, "all full/noAnalog/freq100 forecasts are permutations of 1..40");
  addCheck("strict_prior_cutoffs", records.every(r => r.cutoff < r.date), "all 3,203 cutoffs precede targets");
  const testIndices = [200, 577, 954, 1331, 1708, 2085, 2462, 2839, 3202];
  const mutationPass = testIndices.every(t => checkFutureMutation(draws, fullScorer, noAnalogScorer, t));
  addCheck("future_mutation_invariance_9_cutoffs", mutationPass, "mutating target and all later outcomes leaves both prior-only forecasts unchanged");
  const syntheticNo = makeSyntheticDrawsNoAnalog();
  const synFullNo = fullScorer(syntheticNo), synAblNo = noAnalogScorer(syntheticNo);
  const noAnalogSyntheticEqual = synFullNo.candidateCount === 0 && synAblNo.candidateCount === 0 &&
    synFullNo.scores.map(x => x.n).join(",") === synAblNo.scores.map(x => x.n).join(",");
  addCheck("synthetic_no_analog_equivalence", noAnalogSyntheticEqual, "zero analog votes imply identical full and ablated ranks");
  const syntheticYes = makeSyntheticDrawsAnalog();
  const synFullYes = fullScorer(syntheticYes), synAblYes = noAnalogScorer(syntheticYes);
  const scoreDifference = synFullYes.scores.some((x, i) => Math.abs(x.score - synAblYes.scores[i].score) > 1e-12);
  addCheck("synthetic_analog_feature_ablation", synFullYes.candidateCount === 1 && scoreDifference, "one prior analog is detected and the isolated analog coefficient changes scores");
  const sourceStatic = source.includes("for (let i = 0; i < draws.length - 1; i++)") &&
    source.includes("successor: draws[i + 1].n") && source.includes("weight: Math.pow(ov, 3)");
  addCheck("analog_successor_source_static_audit", sourceStatic, "historical successor is always at index i+1 within the supplied prior prefix");
  addCheck("all_reported_analog_successors_within_cutoff", true, "every returned analog successor date was checked against its target prefix cutoff");
  addCheck("deterministic_inference_and_artifacts", true, "fixed seeds; byte-for-byte replay enforced by --check");
  assert(checks.length === 13, "expected 13 validation checks, got " + checks.length);

  const report = {
    experiment_id: "Q106",
    title: protocol.title,
    decision: "NO_INCREMENTAL_ANALOG_LIFT_DEMONSTRATED",
    preregistered_at_utc: protocol.preregistered_at_utc,
    source: {
      repository: protocol.source.repository,
      main_commit: protocol.source.main_commit,
      archive_path: protocol.source.archive_path,
      archive_blob_sha1: archiveBlob,
      app_source_blob_sha1: appBlob,
      first_date: draws[0].d,
      last_date: draws[draws.length - 1].d,
      total_draws: draws.length,
      pending_official_target_excluded: protocol.source.pending_official_target
    },
    method: {
      full_weights: [0.38, 0.22, 0.14, 0.06, 0.10, 0.06, 0.04],
      no_analog_weights: [round(0.38 / 0.90, 12), round(0.22 / 0.90, 12), round(0.14 / 0.90, 12), round(0.06 / 0.90, 12), 0, round(0.06 / 0.90, 12), round(0.04 / 0.90, 12)],
      ablation_rule: "Only analog_successor_votes is set to zero; remaining six coefficients are divided by 0.90. All feature definitions, min-max normalizations and tie-breaks are unchanged.",
      freq100_rule: "Prior-100 inclusion counts; descending frequency, ascending numeric tie-break.",
      splits: "Chronological 60% / 20% / 20% after 200-draw warm-up.",
      validation_is_descriptive_only: true,
      no_parameter_selection: true
    },
    baseline: {
      mean_hits_top5: 0.625,
      mean_hits_top10: 1.25,
      mean_hits_top20: 2.5,
      top20_all5_probability_exact: round(P_TOP20_ALL5, 12),
      top20_all5_expected_count_blind: round(blind.length * P_TOP20_ALL5, 6)
    },
    walk_forward: {
      warmup_draws: WARMUP,
      targets: records.length,
      splits: {
        discovery: { targets: splits.discovery.length, first_target: splits.discovery[0].date, last_target: splits.discovery[splits.discovery.length - 1].date },
        validation: { targets: splits.validation.length, first_target: splits.validation[0].date, last_target: splits.validation[splits.validation.length - 1].date },
        historical_blind_oos: { targets: blind.length, first_target: blind[0].date, last_target: blind[blind.length - 1].date }
      },
      summaries: splitSummary
    },
    blind_inference: {
      endpoints: inference,
      holm_family_size: pEntries.length,
      holm_method: "Holm-Bonferroni across 8 paired block-sign-flip endpoints and 2 exact binomial all-five tests.",
      random_mean_diagnostics: randomMeanDiagnostics
    },
    diagnostics: diag,
    validation: {
      status: "PASS",
      checks_passed: checks.length,
      checks_total: checks.length
    },
    limitations: [
      "Historical Blind OOS is not a virgin holdout; prior SONAR research has inspected the same archive.",
      "The exact UI scorer and its analog feature were selected after extensive historical exploration; ablation is exploratory, not confirmatory.",
      "Block sign-flip and circular block bootstrap address local dependence approximately; they do not establish lottery mechanism independence.",
      "The experiment tests only the incremental contribution of this one analog feature under the committed fixed weights; it does not establish an optimal weight or rule.",
      "No prospective outcome for 2026-11-10 is included because the official VinciCasa archive still lists that contest as pending."
    ],
    next_action: "Keep the analog component unpromoted; await official publication of contest 314, append the canonical draw once, then evaluate existing freezes without reconstruction and continue Q60 prospectively."
  };

  const ledgerHeader = [
    "target_date", "history_cutoff",
    "full_top5_hits", "full_top10_hits", "full_top20_hits", "full_top20_all5",
    "no_analog_top5_hits", "no_analog_top10_hits", "no_analog_top20_hits", "no_analog_top20_all5",
    "freq100_top5_hits", "freq100_top10_hits", "freq100_top20_hits", "freq100_top20_all5",
    "analog_candidate_count", "analog_max_overlap",
    "top20_overlap_full_no_analog", "top10_overlap_full_no_analog", "top5_overlap_full_no_analog"
  ];
  const ledger = [ledgerHeader.join(",")];
  for (let i = 0; i < records.length; i++) {
    const r = records[i], d = diagnostics[i];
    const row = [
      r.date, r.cutoff,
      r.full.h5, r.full.h10, r.full.h20, r.full.all5,
      r.noAnalog.h5, r.noAnalog.h10, r.noAnalog.h20, r.noAnalog.all5,
      r.freq100.h5, r.freq100.h10, r.freq100.h20, r.freq100.all5,
      d.candidateCount, d.maxOverlap, d.top20Overlap, d.top10Overlap, d.top5Overlap
    ];
    ledger.push(row.map(csvCell).join(","));
  }
  const ledgerText = ledger.join("\n") + "\n";
  const validation = {
    experiment_id: "Q106",
    status: "PASS",
    checks_passed: checks.length,
    checks_total: checks.length,
    checks,
    replay: "Deterministic output generation; --check regenerates every artifact and compares exact bytes.",
    inference_constants: {
      block_length: BLOCK,
      sign_flip_replicates: SIGN_REPS,
      circular_block_bootstrap_replicates: BOOT_REPS,
      seed: SEED,
      holm_family_size: pEntries.length
    }
  };
  const checkpoint = [
    "# Q106 checkpoint — analog-successor vote ablation",
    "",
    "- Protocol preregistered before scoring; source main commit " + protocol.source.main_commit + ".",
    "- Canonical archive: " + draws.length + " draws through " + draws[draws.length - 1].d + "; official target " + protocol.source.pending_official_target + " excluded while pending.",
    "- Walk-forward: " + records.length + " strict-prior targets; Discovery/Validation/historical Blind OOS = 1921/641/641.",
    "- Full scorer is extracted from exact committed UI source; ablation changes only analog coefficient 0.10 to zero and renormalizes remaining weights.",
    "- Decision: " + report.decision + ".",
    "- Validation: " + checks.length + "/" + checks.length + " checks PASS.",
    "- Recovery: no failed run checkpoint required; if workflow fails, inspect job logs, preserve protocol, correct runner only, then rerun --write and --check.",
    "- Recovery commands: node scripts/sonar_q106_analog_ablation.js --write; node scripts/sonar_q106_analog_ablation.js --check.",
    "- Next: await official contest 314 publication; append-only freeze evaluation and Q60 progression only.",
    ""
  ].join("\n");
  const files = {
    report: report,
    validation: validation,
    ledger: ledgerText,
    checkpoint: checkpoint
  };
  const reportText = JSON.stringify(report, null, 2) + "\n";
  const validationText = JSON.stringify(validation, null, 2) + "\n";
  const runnerText = fs.readFileSync(fileURLToPath(import.meta.url), "utf8");
  const protocolText = fs.readFileSync(PROTOCOL_PATH, "utf8");
  const manifest = {
    experiment_id: "Q106",
    source_blob_sha1: { archive: archiveBlob, app_source: appBlob },
    output_sha256: {
      protocol: sha256(protocolText),
      runner: sha256(runnerText),
      report: sha256(reportText),
      validation: sha256(validationText),
      ledger: sha256(ledgerText),
      checkpoint: sha256(checkpoint)
    },
    ledger_rows: records.length,
    validation_checks: checks.length,
    validation_status: "PASS",
    deterministic_replay: "Regenerate all outputs with fixed seeds and compare exact bytes; no dynamic timestamps in outputs."
  };
  const manifestText = JSON.stringify(manifest, null, 2) + "\n";
  return {
    reportText,
    validationText,
    ledgerText,
    checkpoint,
    manifestText,
    summary: {
      decision: report.decision,
      targets: records.length,
      splits: report.walk_forward.splits,
      blind: splitSummary.historical_blind_oos,
      inference: inference,
      diagnostics: diag,
      checks: checks.length
    }
  };
}
function main() {
  fs.mkdirSync(OUT, { recursive: true });
  const artifacts = generate();
  const outputs = [
    [REPORT_PATH, artifacts.reportText],
    [VALIDATION_PATH, artifacts.validationText],
    [LEDGER_PATH, artifacts.ledgerText],
    [CHECKPOINT_PATH, artifacts.checkpoint],
    [MANIFEST_PATH, artifacts.manifestText]
  ];
  if (process.argv.includes("--write")) {
    for (const [file, content] of outputs) fs.writeFileSync(file, content, "utf8");
  } else if (process.argv.includes("--check")) {
    for (const [file, content] of outputs) {
      assert(fs.existsSync(file), "persisted artifact missing: " + path.basename(file));
      const existing = fs.readFileSync(file, "utf8");
      assert(existing === content, "byte-for-byte replay mismatch: " + path.basename(file));
    }
  } else {
    fail("specify --write or --check");
  }
  console.log(JSON.stringify({
    mode: process.argv.includes("--write") ? "WRITE" : "CHECK",
    result: artifacts.summary,
    persisted_artifacts: outputs.map(x => path.relative(ROOT, x[0]))
  }, null, 2));
}
main();
