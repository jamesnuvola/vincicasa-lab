#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ARCHIVE = path.join(ROOT, "data", "storico_daily.csv");
const PROTOCOL = path.join(ROOT, "reports", "sequence_agent", "q105_weekday_conditioned_subset_protocol_2026-11-10.json");
const OUT = path.join(ROOT, "reports", "sequence_agent");
const FILES = {
  report: path.join(OUT, "q105_weekday_conditioned_subset_report_2026-11-10.json"),
  validation: path.join(OUT, "q105_weekday_conditioned_subset_validation_2026-11-10.json"),
  ledger: path.join(OUT, "q105_weekday_conditioned_subset_target_ledger_2026-11-10.csv"),
  checkpoint: path.join(OUT, "q105_weekday_conditioned_subset_checkpoint_2026-11-10.md"),
  manifest: path.join(OUT, "q105_weekday_conditioned_subset_persistence_manifest_2026-11-10.json")
};
const ALPHA = 200, PRIOR_HITS = 25, WARMUP = 200;
const DISCOVERY = 1921, VALIDATION = 641, BLIND = 641;
const BLOCK = 20, SIGN_REPS = 50000, BOOT_REPS = 10000, SEED = 20261110;
const SUBSETS = 658008;
const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

function fail(message) { throw new Error("Q105: " + message); }
function round12(x) {
  if (!Number.isFinite(x)) fail("non-finite numeric result");
  const y = Number(x.toFixed(12));
  return Object.is(y, -0) ? 0 : y;
}
function ceil12(x) {
  if (!Number.isFinite(x) || x < 0) fail("invalid p-value");
  return Math.min(1, Math.ceil(x * 1e12) / 1e12);
}
function stableJson(x) { return JSON.stringify(x, null, 2) + "\n"; }
function sha256(s) { return crypto.createHash("sha256").update(s, "utf8").digest("hex"); }
function gitBlobSha(p) { return execFileSync("git", ["rev-parse", "HEAD:" + path.relative(ROOT, p)], { encoding: "utf8" }).trim(); }

function parseArchive(text) {
  const lines = text.trimEnd().split(/\r?\n/);
  if (lines[0] !== "data,n1,n2,n3,n4,n5") fail("archive header mismatch");
  const rows = [];
  let prev = "";
  const seen = new Set();
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    if (f.length !== 6) fail("archive row width at line " + (i + 1));
    const date = f[0], n = f.slice(1).map(Number);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date + "T00:00:00Z"))) fail("invalid date at line " + (i + 1));
    if (seen.has(date) || (prev && date <= prev)) fail("duplicate or unordered date " + date);
    if (n.some((v, j) => !Number.isInteger(v) || v < 1 || v > 40 || (j > 0 && n[j - 1] >= v))) fail("invalid sorted 5-of-40 draw at line " + (i + 1));
    rows.push({ date, n, weekday: new Date(date + "T00:00:00Z").getUTCDay() });
    seen.add(date); prev = date;
  }
  if (rows.length !== 3403 || rows[0].date !== "2017-07-17" || rows[rows.length - 1].date !== "2026-11-09") fail("archive pin/cutoff mismatch");
  return rows;
}
function e5(weights) {
  const d = [1, 0, 0, 0, 0, 0];
  for (const w of weights) for (let j = 5; j >= 1; j--) d[j] += d[j - 1] * w;
  return d[5];
}
function bruteE5(weights) {
  let z = 0;
  for (let a = 0; a < weights.length - 4; a++)
    for (let b = a + 1; b < weights.length - 3; b++)
      for (let c = b + 1; c < weights.length - 2; c++)
        for (let d = c + 1; d < weights.length - 1; d++)
          for (let e = d + 1; e < weights.length; e++)
            z += weights[a] * weights[b] * weights[c] * weights[d] * weights[e];
  return z;
}
function buildWeights(counts, nDraws) {
  const p = counts.map(c => (PRIOR_HITS + c) / (ALPHA + nDraws));
  const odds = p.map(v => v / (1 - v));
  const z = e5(odds);
  if (!(z > 0) || !Number.isFinite(z)) fail("invalid e5 normalizer");
  return { p, odds, logZ: Math.log(z), z };
}
function scoreSubset(model, actual) {
  let lp = -model.logZ;
  for (const n of actual) lp += Math.log(model.odds[n - 1]);
  return lp;
}
function ranking(odds) {
  return odds.map((w, i) => ({ n: i + 1, w })).sort((a, b) => b.w - a.w || a.n - b.n).map(x => x.n);
}
function forecastAt(draws, t) {
  if (t < WARMUP || t >= draws.length) fail("forecast index out of range");
  const gc = Array(40).fill(0), wc = Array.from({ length: 7 }, () => Array(40).fill(0)), wn = Array(7).fill(0);
  for (let i = 0; i < t; i++) {
    const d = draws[i];
    for (const n of d.n) { gc[n - 1]++; wc[d.weekday][n - 1]++; }
    wn[d.weekday]++;
  }
  const g = buildWeights(gc, t), w = buildWeights(wc[draws[t].weekday], wn[draws[t].weekday]);
  return { global: g, weekday: w, globalRank: ranking(g.odds), weekdayRank: ranking(w.odds), globalPriorDraws: t, weekdayPriorDraws: wn[draws[t].weekday] };
}
function prng(seed) {
  let x = seed >>> 0;
  return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return (x >>> 0) / 4294967296; };
}
function blockSums(values) {
  const out = [];
  for (let i = 0; i < values.length; i += BLOCK) out.push(values.slice(i, Math.min(i + BLOCK, values.length)).reduce((a, b) => a + b, 0));
  return out;
}
function signFlip(values, seed) {
  const bs = blockSums(values), observed = bs.reduce((a, b) => a + b, 0), random = prng(seed);
  let extreme = 0;
  for (let r = 0; r < SIGN_REPS; r++) {
    let s = 0;
    for (const b of bs) s += (random() < 0.5 ? -1 : 1) * b;
    if (s >= observed - 1e-14) extreme++;
  }
  const p = (extreme + 1) / (SIGN_REPS + 1);
  return { observed_sum: round12(observed), observed_mean: round12(observed / values.length), blocks: bs.length, block_length: BLOCK, replicates: SIGN_REPS, extreme, p_one_sided: ceil12(p), monte_carlo_se: round12(Math.sqrt(p * (1 - p) / (SIGN_REPS + 1))) };
}
function bootstrapCI(values, seed) {
  const n = values.length, random = prng(seed), sims = new Array(BOOT_REPS);
  for (let r = 0; r < BOOT_REPS; r++) {
    let sum = 0, used = 0;
    while (used < n) {
      const start = Math.floor(random() * n);
      for (let j = 0; j < BLOCK && used < n; j++, used++) sum += values[(start + j) % n];
    }
    sims[r] = sum / n;
  }
  sims.sort((a, b) => a - b);
  return { replicates: BOOT_REPS, block_length: BLOCK, ci95: [round12(sims[Math.floor(0.025 * (BOOT_REPS - 1))]), round12(sims[Math.floor(0.975 * (BOOT_REPS - 1))])] };
}
function holm(items) {
  const sorted = items.map((x, i) => ({ ...x, i })).sort((a, b) => a.p - b.p);
  let running = 0;
  const out = new Array(items.length);
  for (let i = 0; i < sorted.length; i++) {
    running = Math.max(running, Math.min(1, (sorted.length - i) * sorted[i].p));
    out[sorted[i].i] = { ...items[sorted[i].i], p_holm: ceil12(running) };
  }
  return out;
}
function splitOf(offset) {
  if (offset < DISCOVERY) return "discovery";
  if (offset < DISCOVERY + VALIDATION) return "validation";
  return "historical_blind_oos";
}
function mean(a) { return a.reduce((s, x) => s + x, 0) / a.length; }
function summarize(rows) {
  const n = rows.length;
  return {
    targets: n, first_target: rows[0].target_date, last_target: rows[n - 1].target_date,
    mean_log_gain_global_vs_uniform: round12(mean(rows.map(r => r.global_log_gain))),
    mean_log_gain_weekday_vs_uniform: round12(mean(rows.map(r => r.weekday_log_gain))),
    mean_log_gain_weekday_minus_global: round12(mean(rows.map(r => r.weekday_minus_global))),
    mean_top5_hits_global: round12(mean(rows.map(r => r.global_top5_hits))),
    mean_top5_hits_weekday: round12(mean(rows.map(r => r.weekday_top5_hits))),
    mean_top20_hits_global: round12(mean(rows.map(r => r.global_top20_hits))),
    mean_top20_hits_weekday: round12(mean(rows.map(r => r.weekday_top20_hits))),
    top5_uniform_expected_mean_hits: 0.625, top20_uniform_expected_mean_hits: 2.5
  };
}
function csvEscape(s) {
  const v = String(s);
  return /[",\r\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
}

function run() {
  const archiveText = fs.readFileSync(ARCHIVE, "utf8"), protocolText = fs.readFileSync(PROTOCOL, "utf8");
  const protocol = JSON.parse(protocolText);
  if (protocol.experiment_id !== "Q105" || protocol.status !== "PREREGISTERED_NOT_RUN") fail("protocol identity/status mismatch");
  if (protocol.source.archive_blob_sha1 !== gitBlobSha(ARCHIVE)) fail("archive blob SHA differs from preregistration");
  if (protocol.forecast.prior_equivalent_draws !== ALPHA || protocol.forecast.warmup_draws !== WARMUP) fail("protocol constants mismatch");
  if (protocol.inference.block_length !== BLOCK || protocol.inference.block_sign_flip_replicates !== SIGN_REPS || protocol.inference.circular_block_bootstrap_replicates !== BOOT_REPS || protocol.inference.seed !== SEED) fail("inference constants differ from preregistration");
  const draws = parseArchive(archiveText), rows = [];
  const gc = Array(40).fill(0), wc = Array.from({ length: 7 }, () => Array(40).fill(0)), wn = Array(7).fill(0);
  for (let i = 0; i < WARMUP; i++) {
    for (const n of draws[i].n) { gc[n - 1]++; wc[draws[i].weekday][n - 1]++; }
    wn[draws[i].weekday]++;
  }
  for (let t = WARMUP; t < draws.length; t++) {
    const d = draws[t], g = buildWeights(gc, t), w = buildWeights(wc[d.weekday], wn[d.weekday]);
    const glp = scoreSubset(g, d.n), wlp = scoreSubset(w, d.n);
    const gr = ranking(g.odds), wr = ranking(w.odds), actual = new Set(d.n), offset = t - WARMUP;
    rows.push({
      target_index: t, target_date: d.date, weekday: WEEKDAYS[d.weekday], cutoff_date: draws[t - 1].date,
      max_training_index: t - 1, global_prior_draws: t, weekday_prior_draws: wn[d.weekday], split: splitOf(offset),
      actual_numbers: d.n.join(" "), global_log_gain: round12(glp + Math.log(SUBSETS)),
      weekday_log_gain: round12(wlp + Math.log(SUBSETS)), weekday_minus_global: round12(wlp - glp),
      global_top5_hits: gr.slice(0, 5).filter(n => actual.has(n)).length,
      weekday_top5_hits: wr.slice(0, 5).filter(n => actual.has(n)).length,
      global_top20_hits: gr.slice(0, 20).filter(n => actual.has(n)).length,
      weekday_top20_hits: wr.slice(0, 20).filter(n => actual.has(n)).length
    });
    for (const n of d.n) { gc[n - 1]++; wc[d.weekday][n - 1]++; }
    wn[d.weekday]++;
  }
  if (rows.length !== 3203) fail("walk-forward target count");
  const disc = rows.filter(r => r.split === "discovery"), val = rows.filter(r => r.split === "validation"), blind = rows.filter(r => r.split === "historical_blind_oos");
  if (disc.length !== DISCOVERY || val.length !== VALIDATION || blind.length !== BLIND) fail("chronological split mismatch");
  if (rows.some(r => !(r.cutoff_date < r.target_date) || r.max_training_index !== r.target_index - 1)) fail("strict-prior cutoff failure");

  const weekdayDiagnostics = WEEKDAYS.map((day, i) => {
    const a = blind.filter(r => r.weekday === day);
    return { weekday: day, blind_targets: a.length, mean_weekday_log_gain: round12(mean(a.map(r => r.weekday_log_gain))), mean_weekday_minus_global: round12(mean(a.map(r => r.weekday_minus_global))) };
  });
  const d1 = blind.map(r => r.weekday_minus_global), d2 = blind.map(r => r.weekday_log_gain);
  const p1 = signFlip(d1, SEED + 1), p2 = signFlip(d2, SEED + 2);
  const ci1 = bootstrapCI(d1, SEED + 11), ci2 = bootstrapCI(d2, SEED + 12);
  const adjusted = holm([{ endpoint: "weekday_minus_global", p: p1.p_one_sided }, { endpoint: "weekday_minus_uniform", p: p2.p_one_sided }]);
  const inference = {
    endpoint_weekday_minus_global: { ...p1, bootstrap: ci1, p_holm_two_endpoint_family: adjusted.find(x => x.endpoint === "weekday_minus_global").p_holm },
    endpoint_weekday_minus_uniform: { ...p2, bootstrap: ci2, p_holm_two_endpoint_family: adjusted.find(x => x.endpoint === "weekday_minus_uniform").p_holm },
    family_size: 2, correction: "Holm step-down across the two preregistered Blind OOS inferential endpoints."
  };

  const small = [0.7, 1.2, 0.4, 1.7, 0.9, 1.3, 0.8, 1.1];
  if (Math.abs(e5(small) - bruteE5(small)) > 1e-12) fail("small-n DP/brute-force mismatch");
  const rep = forecastAt(draws, 200), normG = Math.abs(bruteE5(rep.global.odds) / rep.global.z - 1), normW = Math.abs(bruteE5(rep.weekday.odds) / rep.weekday.z - 1);
  if (normG > 1e-10 || normW > 1e-10) fail("representative exhaustive subset normalizer mismatch");

  let futurePass = 0;
  for (const t of [200, 201, 641, 1280, 1921, 2121, 2762, 3000, 3402]) {
    const before = forecastAt(draws, t);
    const mutated = draws.map((d, i) => i < t ? d : { ...d, n: [((i * 7) % 40) + 1, ((i * 7 + 5) % 40) + 1, ((i * 7 + 11) % 40) + 1, ((i * 7 + 19) % 40) + 1, ((i * 7 + 27) % 40) + 1].sort((a, b) => a - b) });
    const after = forecastAt(mutated, t);
    if (JSON.stringify(before.global.odds) !== JSON.stringify(after.global.odds) || JSON.stringify(before.weekday.odds) !== JSON.stringify(after.weekday.odds)) fail("future mutation changed forecast at cutoff " + t);
    futurePass++;
  }
  let replayPass = 0;
  for (const t of [200, 201, 641, 1280, 1921, 2562, 3000, 3402]) {
    if (JSON.stringify(forecastAt(draws, t)) !== JSON.stringify(forecastAt(draws, t))) fail("deterministic replay mismatch at cutoff " + t);
    replayPass++;
  }
  const checks = [
    { id: "protocol_and_archive_pin", status: "PASS", detail: "Q105 protocol constants and canonical archive blob SHA match preregistration." },
    { id: "archive_integrity", status: "PASS", detail: "3403 unique chronological rows; each outcome is a sorted five-number subset of 1..40." },
    { id: "strict_prior_cutoffs", status: "PASS", detail: "3203/3203 forecasts use only rows with index less than the target; previous-day cutoff verified." },
    { id: "weekday_prior_filter", status: "PASS", detail: "Weekday counts use only prior rows matching the target weekday; target row is added after scoring." },
    { id: "fixed_cardinality_normalizer", status: "PASS", detail: "e5 dynamic program agrees with brute-force enumeration on an eight-weight synthetic fixture." },
    { id: "exhaustive_subset_normalization", status: "PASS", detail: "Representative global and weekday normalizers match exhaustive enumeration of all 658008 subsets; max relative error " + Math.max(normG, normW).toExponential(3) + "." },
    { id: "future_mutation_invariance", status: "PASS", detail: futurePass + "/9 fixed-cutoff forecasts unchanged after mutating all later outcomes." },
    { id: "deterministic_replay", status: "PASS", detail: replayPass + "/8 forecast replays identical in memory." },
    { id: "chronological_split_reconciliation", status: "PASS", detail: "1921 discovery + 641 validation + 641 historical blind OOS = 3203." },
    { id: "finite_probability_checks", status: "PASS", detail: "All global and weekday models have finite positive weights and normalizers." },
    { id: "inference_preregistration_match", status: "PASS", detail: "Block length, sign-flip replicates, bootstrap replicates and seed match the preregistered protocol exactly." },
    { id: "multiplicity_family", status: "PASS", detail: "Exactly two preregistered Blind OOS endpoints receive Holm correction; weekday subgroup summaries are descriptive only." }
  ];
  const primaryMean = mean(d1);
  const decision = primaryMean > 0 && inference.endpoint_weekday_minus_global.p_holm_two_endpoint_family < 0.05
    ? "HISTORICAL_WEEKDAY_INCREMENTAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION"
    : "NO_WEEKDAY_INCREMENTAL_LIFT_DEMONSTRATED";
  const report = {
    experiment_id: "Q105",
    title: "Weekday-conditioned number inclusion model versus global-frequency and exact-uniform subset baselines",
    generated_date: "2026-11-10",
    decision,
    source: { main_commit: protocol.source.main_commit, archive_blob_sha1: gitBlobSha(ARCHIVE), protocol_blob_sha1: gitBlobSha(PROTOCOL), archive_draws: draws.length, first_date: draws[0].date, last_date: draws[draws.length - 1].date },
    model: {
      prior_equivalent_draws: ALPHA, prior_expected_hits_per_number: PRIOR_HITS, baseline_per_number_inclusion_probability: 0.125,
      weekday_definition: protocol.forecast.weekday_definition,
      probability_model: "p=(25+prior_count)/(200+prior_draws); odds=p/(1-p); P(D)=product odds(D)/e5(odds), fixed cardinality 5.",
      exact_subset_count: SUBSETS, no_tuning: true
    },
    walk_forward: {
      warmup_draws: WARMUP, target_count: rows.length,
      splits: { discovery: summarize(disc), validation: summarize(val), historical_blind_oos: summarize(blind) },
      selection: "No hyperparameter or model selection; alpha=200 fixed by preregistration."
    },
    blind_inference: inference, weekday_diagnostics: weekdayDiagnostics,
    validation: { status: "PASS", checks },
    recovery: {
      initial_attempt_issue: "The first runner draft used 21-target inference blocks while the preregistered protocol specified 20. That first run is invalidated and its inferential outputs are superseded.",
      correction: "The runner was changed to block length 20 before the final successful run; the final runner now fails closed if any inference constant differs from the protocol.",
      final_run: "The final dedicated workflow run uses 20-target blocks, 50000 sign-flips, 10000 bootstrap replicates and the preregistered seed."
    },
    limitations: [
      "Historical blind OOS has been exposed to prior SONAR research and is not a virgin holdout.",
      "Calendar weekday is an ex-ante covariate but no physical draw mechanism is established.",
      "A positive historical result would remain exploratory until prospective frozen confirmation under Q60."
    ],
    next_action: "Do not tune alpha or weekday subgroups. Preserve Q60/H101/H102 freezes; wait for official contest 314 result before any append-only reconciliation."
  };
  const header = ["target_index","target_date","weekday","cutoff_date","max_training_index","global_prior_draws","weekday_prior_draws","split","actual_numbers","global_log_gain","weekday_log_gain","weekday_minus_global","global_top5_hits","weekday_top5_hits","global_top20_hits","weekday_top20_hits"];
  const ledger = [header.join(",")].concat(rows.map(r => header.map(k => csvEscape(r[k])).join(","))).join("\n") + "\n";
  const checkpoint = [
    "# Q105 checkpoint — weekday-conditioned subset model", "",
    "- Protocol preregistered before scoring; alpha=200; no tuning.",
    "- Archive: 3,403 draws through 2026-11-09; target 2026-11-10 excluded pending official publication.",
    "- Walk-forward: 3,203 targets; Discovery 1,921 / Validation 641 / historical Blind OOS 641.",
    "- Runner: strict-prior global and weekday counts; fixed-cardinality e5 normalization.",
    "- Blind weekday-minus-global mean gain: " + inference.endpoint_weekday_minus_global.observed_mean + "; Holm p=" + inference.endpoint_weekday_minus_global.p_holm_two_endpoint_family + ".",
    "- Blind weekday-minus-uniform mean gain: " + inference.endpoint_weekday_minus_uniform.observed_mean + "; Holm p=" + inference.endpoint_weekday_minus_uniform.p_holm_two_endpoint_family + ".",
    "- Validation checks: " + checks.length + "/" + checks.length + " structural/replay/leakage/preregistration checks passed.",
    "- Recovery: an initial draft used 21-day blocks against the preregistered 20; that run was invalidated. Final runner enforces protocol equality and uses 20-day blocks.",
    "- Recovery command: run the Q105 Node script with --write, then with --check; no freeze or production file is modified.",
    "- Next: await official contest 314 publication; append-only Q60 evaluation only."
  ].join("\n") + "\n";
  const validation = { experiment_id: "Q105", status: "PASS", check_count: checks.length, passed: checks.filter(x => x.status === "PASS").length, failed: checks.filter(x => x.status !== "PASS").length, checks, inference_family_size: 2, selected_model_or_parameter: "none", no_engine_promotion: true, no_freeze_mutation: true };
  const files = { report: stableJson(report), validation: stableJson(validation), ledger, checkpoint, manifest: "" };
  const runnerText = fs.readFileSync(fileURLToPath(import.meta.url), "utf8");
  files.manifest = stableJson({
    experiment_id: "Q105", generated_date: "2026-11-10",
    source_blob_sha1: { archive: gitBlobSha(ARCHIVE), protocol: gitBlobSha(PROTOCOL) },
    output_sha256: { report: sha256(files.report), validation: sha256(files.validation), ledger: sha256(files.ledger), checkpoint: sha256(files.checkpoint), runner: sha256(runnerText) },
    ledger_rows: rows.length, validation_checks: checks.length, validation_status: "PASS",
    replay_policy: "Regenerate outputs and compare exact bytes; fixed random seeds and no dynamic timestamps."
  });
  return { report, validation, files };
}
function main() {
  const mode = process.argv[2];
  if (mode !== "--write" && mode !== "--check") fail("usage: --write or --check");
  const result = run();
  if (mode === "--write") {
    for (const [key, p] of Object.entries(FILES)) fs.writeFileSync(p, result.files[key], "utf8");
    console.log("Q105_WRITE_PASS targets=3203 checks=" + result.validation.passed + "/" + result.validation.check_count);
  } else {
    for (const [key, p] of Object.entries(FILES)) {
      if (!fs.existsSync(p)) fail("missing persisted " + key);
      if (fs.readFileSync(p, "utf8") !== result.files[key]) fail("persisted byte mismatch: " + key);
    }
    console.log("Q105_BYTE_REPLAY_PASS targets=3203 checks=" + result.validation.passed + "/" + result.validation.check_count);
  }
  console.log(JSON.stringify({ discovery: result.report.walk_forward.splits.discovery, validation: result.report.walk_forward.splits.validation, blind_oos: result.report.walk_forward.splits.historical_blind_oos, blind_inference: result.report.blind_inference }, null, 2));
}
main();
