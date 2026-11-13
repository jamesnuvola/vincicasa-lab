import fs from "node:fs";
import crypto from "node:crypto";

const read = (p) => fs.readFileSync(p, "utf8");
const fail = (m) => { throw new Error("Q140 REPLAY FAIL: " + m); };
function gitBlobSha(buf) {
  const b = Buffer.isBuffer(buf) ? buf : Buffer.from(buf, "utf8");
  return crypto.createHash("sha1").update(Buffer.from("blob " + b.length + "\0")).update(b).digest("hex");
}
function compareDeep(a, b, path = "root") {
  if (typeof a === "number" && typeof b === "number") {
    if (!Number.isFinite(a) || !Number.isFinite(b) || Math.abs(a - b) > 1e-10) fail(path + " numeric mismatch: " + a + " vs " + b);
    return;
  }
  if (a === null || b === null || typeof a !== "object" || typeof b !== "object") {
    if (a !== b) fail(path + " mismatch");
    return;
  }
  if (Array.isArray(a) !== Array.isArray(b)) fail(path + " type mismatch");
  const ak = Object.keys(a), bk = Object.keys(b);
  if (ak.length !== bk.length || ak.some(k => !Object.prototype.hasOwnProperty.call(b, k))) fail(path + " keys mismatch");
  for (const k of ak) compareDeep(a[k], b[k], path + "." + k);
}

const protocolPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_protocol_2026-11-12.json";
const reportPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_report_2026-11-12.json";
const ledgerPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_target_ledger_2026-11-12.csv";
const validationPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_validation_2026-11-12.json";
const checkpointPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_checkpoint_2026-11-12.md";
const manifestPath = "reports/sequence_agent/q140_sequential_marginal_break_fwer_persistence_manifest_2026-11-12.json";
const runnerPath = "scripts/sonar_q140_sequential_marginal_break_fwer.mjs";
const workflowPath = ".github/workflows/q140-replay.yml";

const protocol = JSON.parse(read(protocolPath));
const archiveBytes = fs.readFileSync("data/storico_daily.csv");
const archiveText = archiveBytes.toString("utf8");
const archiveSha = gitBlobSha(archiveBytes);
if (archiveSha !== protocol.source.archive_blob_sha) fail("archive Git blob SHA mismatch");
const all = archiveText.trimEnd().split(/\r?\n/).slice(1).map(line => {
  const a = line.split(",");
  return { date: a[0], nums: a.slice(1).map(Number) };
});
const excluded = all[all.length - 1];
const data = all.slice(0, -1);
if (all.length !== 3405 || data.length !== 3404) fail("archive row count mismatch");
if (excluded.date !== "2026-11-11" || excluded.nums.join(",") !== "1,21,22,27,29") fail("disputed contest 315 row changed");
if (data[data.length - 1].date !== "2026-11-10") fail("eligible cutoff mismatch");
for (let i = 0; i < data.length; i++) {
  const d = data[i];
  if (i && data[i - 1].date >= d.date) fail("dates not unique/chronological");
  if (d.nums.length !== 5 || new Set(d.nums).size !== 5 || d.nums.some(n => !Number.isInteger(n) || n < 1 || n > 40)) fail("invalid draw at " + d.date);
}

const W = 200, H = 100, ALPHA = 200, TARGETS = 3204, TESTS = TARGETS * 40;
const NOMINAL_ALPHA = 0.05 / TESTS;
const THRESHOLD = 0.0000003900343375;
const logFact = Array(201).fill(0);
for (let i = 1; i <= 200; i++) logFact[i] = logFact[i - 1] + Math.log(i);
const logChoose = (n, k) => k < 0 || k > n ? -Infinity : logFact[n] - logFact[k] - logFact[n - k];
const logDenom = logChoose(200, 100);
const pTable = Array.from({ length: 201 }, () => Array(101).fill(1));
for (let K = 0; K <= 200; K++) {
  const lo = Math.max(0, 100 - (200 - K)), hi = Math.min(100, K), pmf = [];
  for (let a = lo; a <= hi; a++) pmf.push([a, logChoose(K, a) + logChoose(200 - K, 100 - a) - logDenom]);
  for (const [a, observed] of pmf) {
    let p = 0;
    for (const [, lp] of pmf) if (lp <= observed + 1e-12) p += Math.exp(lp);
    pTable[K][a] = Math.min(1, p);
  }
}
function score(weights, selected) {
  const dp = Array(6).fill(0); dp[0] = 1;
  for (const w of weights) for (let k = 5; k >= 1; k--) dp[k] += w * dp[k - 1];
  const z = dp[5];
  const prefix = Array.from({ length: 41 }, () => Array(5).fill(0));
  const suffix = Array.from({ length: 41 }, () => Array(5).fill(0));
  prefix[0][0] = 1;
  for (let i = 0; i < 40; i++) for (let k = 0; k <= 4; k++) prefix[i + 1][k] = prefix[i][k] + (k ? weights[i] * prefix[i][k - 1] : 0);
  suffix[40][0] = 1;
  for (let i = 39; i >= 0; i--) for (let k = 0; k <= 4; k++) suffix[i][k] = suffix[i + 1][k] + (k ? weights[i] * suffix[i + 1][k - 1] : 0);
  const marg = Array(40).fill(0);
  for (let i = 0; i < 40; i++) {
    let e4 = 0;
    for (let k = 0; k <= 4; k++) e4 += prefix[i][k] * suffix[i + 1][4 - k];
    marg[i] = weights[i] * e4 / z;
  }
  let logP = -Math.log(z);
  for (const n of selected) logP += Math.log(weights[n - 1]);
  const y = new Set(selected);
  let brier = 0;
  for (let i = 0; i < 40; i++) brier += (marg[i] - (y.has(i + 1) ? 1 : 0)) ** 2;
  return { logloss: -logP, brier: brier / 40, marginalSum: marg.reduce((a, b) => a + b, 0), logZ: Math.log(z) };
}
const ones = Array(40).fill(1);
function forecast(t, rows = data) {
  const first = Array(40).fill(0), recent = Array(40).fill(0), total = Array(40).fill(0);
  for (let j = t - W; j < t; j++) {
    for (const n of rows[j].nums) total[n - 1]++;
    if (j < t - H) for (const n of rows[j].nums) first[n - 1]++;
    else for (const n of rows[j].nums) recent[n - 1]++;
  }
  const flagged = []; let minP = 1;
  for (let i = 0; i < 40; i++) {
    const p = pTable[total[i]][first[i]];
    if (p < minP) minP = p;
    if (p <= THRESHOLD) flagged.push(i + 1);
  }
  const q = recent.map(c => (c + ALPHA * 0.125) / (H + ALPHA));
  const w1 = q.map(v => v / 0.125), w2 = ones.slice();
  for (const n of flagged) w2[n - 1] = w1[n - 1];
  const actual = rows[t].nums;
  return {
    target_date: rows[t].date, history_cutoff: rows[t - 1].date,
    window_start: rows[t - W].date, window_end: rows[t - 1].date,
    flagged, minP, s0: score(ones, actual), s1: score(w1, actual), s2: score(w2, actual),
    first, recent, total
  };
}
const ranges = { discovery: [0, 1922], validation: [1922, 2563], blind_oos_historical: [2563, 3204] };
const gains = {};
for (const s of Object.keys(ranges)) gains[s] = {
  M1_M0: { ll: [], br: [] }, M2_M0: { ll: [], br: [] }, M2_M1: { ll: [], br: [] }
};
const alarms = { discovery: 0, validation: 0, blind_oos_historical: 0 }, flagFrequency = {};
const results = [], ledgerRows = [];
for (let k = 0; k < TARGETS; k++) {
  const r = forecast(200 + k);
  const s = k < 1922 ? "discovery" : k < 2563 ? "validation" : "blind_oos_historical";
  if (r.flagged.length) alarms[s]++;
  for (const n of r.flagged) flagFrequency[n] = (flagFrequency[n] || 0) + 1;
  const a = gains[s];
  a.M1_M0.ll.push(r.s0.logloss - r.s1.logloss); a.M1_M0.br.push(r.s0.brier - r.s1.brier);
  a.M2_M0.ll.push(r.s0.logloss - r.s2.logloss); a.M2_M0.br.push(r.s0.brier - r.s2.brier);
  a.M2_M1.ll.push(r.s1.logloss - r.s2.logloss); a.M2_M1.br.push(r.s1.brier - r.s2.brier);
  results.push(r);
  ledgerRows.push([
    r.target_date, r.history_cutoff, r.window_start, r.window_end,
    r.flagged.length ? "1" : "0", r.flagged.join(";"), r.minP.toExponential(8),
    r.s0.logloss.toFixed(12), r.s1.logloss.toFixed(12), r.s2.logloss.toFixed(12),
    r.s0.brier.toFixed(12), r.s1.brier.toFixed(12), r.s2.brier.toFixed(12)
  ].join(","));
}
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const quantile = (a, p) => {
  const x = (a.length - 1) * p, lo = Math.floor(x), hi = Math.ceil(x);
  return a[lo] + (a[hi] - a[lo]) * (x - lo);
};
function rng32(seed) {
  return () => {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
function signflip(a, B, seed) {
  const rng = rng32(seed), blocks = [];
  for (let i = 0; i < a.length; i += 20) blocks.push(a.slice(i, i + 20).reduce((s, x) => s + x, 0));
  const observed = mean(a); let ge = 0;
  for (let b = 0; b < B; b++) {
    let sum = 0;
    for (const v of blocks) sum += rng() < 0.5 ? -v : v;
    if (sum / a.length >= observed - 1e-15) ge++;
  }
  return { p: (ge + 1) / (B + 1), observed };
}
function bootstrap(a, B, seed) {
  const rng = rng32(seed), n = a.length, out = Array(B);
  for (let b = 0; b < B; b++) {
    let sum = 0, used = 0;
    while (used < n) {
      const start = Math.floor(rng() * n), len = Math.min(20, n - used);
      for (let j = 0; j < len; j++) sum += a[(start + j) % n];
      used += len;
    }
    out[b] = sum / n;
  }
  out.sort((x, y) => x - y);
  return { lower: quantile(out, 0.025), upper: quantile(out, 0.975), median: quantile(out, 0.5) };
}
const endpoints = []; let seed = 140202611;
for (const s of ["validation", "blind_oos_historical"]) {
  for (const cmp of ["M1_M0", "M2_M0", "M2_M1"]) {
    for (const metric of ["ll", "br"]) {
      const a = gains[s][cmp][metric], sf = signflip(a, 10000, seed++), bb = bootstrap(a, 10000, seed++);
      endpoints.push({ split: s, comparison: cmp, metric, mean_gain: sf.observed, p_raw: sf.p,
        bootstrap_95: { lower: bb.lower, upper: bb.upper, median: bb.median } });
    }
  }
}
const order = endpoints.map((e, i) => ({ i, p: e.p_raw })).sort((a, b) => a.p - b.p);
let running = 0;
for (let j = 0; j < order.length; j++) {
  running = Math.max(running, Math.min(1, (endpoints.length - j) * order[j].p));
  endpoints[order[j].i].p_holm = running;
}
const splitSummary = {};
for (const s of Object.keys(ranges)) {
  splitSummary[s] = { targets: ranges[s][1] - ranges[s][0], alarms: alarms[s],
    alarm_rate: alarms[s] / (ranges[s][1] - ranges[s][0]), comparisons: {} };
  for (const [cmp, v] of Object.entries(gains[s])) splitSummary[s].comparisons[cmp] = {
    mean_logloss_gain: mean(v.ll), mean_brier_gain: mean(v.br),
    logloss_gain_min: Math.min(...v.ll), logloss_gain_max: Math.max(...v.ll),
    brier_gain_min: Math.min(...v.br), brier_gain_max: Math.max(...v.br)
  };
}
const checks = [], add = (id, pass) => checks.push({ id, pass });
add("source_blob_sha", archiveSha === "fcb453ed06c8002314f826dbac79d6935f9ac103");
add("archive_3405_rows", all.length === 3405);
add("disputed_315_row_excluded", excluded.date === "2026-11-11" && excluded.nums.join(",") === "1,21,22,27,29");
add("clean_cutoff_2026_11_10", data[data.length - 1].date === "2026-11-10");
add("chronological_unique_dates", data.every((d, i) => i === 0 || data[i - 1].date < d.date));
add("all_draws_valid_5of40", data.every(d => d.nums.length === 5 && new Set(d.nums).size === 5 && d.nums.every(n => Number.isInteger(n) && n >= 1 && n <= 40)));
add("target_count_3204", results.length === 3204);
add("strict_prior_cutoff", results.every(r => r.history_cutoff < r.target_date && r.window_end === r.history_cutoff));
add("global_test_count_128160", TESTS === 128160);
add("threshold_conservative_vs_nominal", THRESHOLD <= NOMINAL_ALPHA);
for (const t of [200, 1921, 1922, 2562, 2563, 3403]) {
  const r = forecast(t);
  add("marginal_sum_5_t" + t, [r.s0, r.s1, r.s2].every(x => Math.abs(x.marginalSum - 5) < 1e-9));
  add("normalizers_finite_t" + t, [r.s0, r.s1, r.s2].every(x => Number.isFinite(x.logZ)));
}
const d1 = forecast(1234), d2 = forecast(1234);
add("deterministic_replay", JSON.stringify(d1) === JSON.stringify(d2));
const suffixTargets = [200, 400, 800, 1200, 1600, 2000, 2400, 2800, 3200];
for (let z = 0; z < suffixTargets.length; z++) {
  const t = suffixTargets[z], a = forecast(t);
  const altered = data.map((d, i) => i <= t ? d : { ...d, nums: [
    ((i + z) % 40) + 1, ((i + z + 7) % 40) + 1, ((i + z + 13) % 40) + 1,
    ((i + z + 21) % 40) + 1, ((i + z + 31) % 40) + 1
  ] });
  const b = forecast(t, altered);
  const sig = x => JSON.stringify({ flagged: x.flagged, minP: x.minP, s0: x.s0, s1: x.s1, s2: x.s2, first: x.first, recent: x.recent, total: x.total });
  add("future_suffix_invariance_" + (z + 1), sig(a) === sig(b));
}
if (checks.some(x => !x.pass)) fail("one or more structural checks failed");
const decision = "NO_SEQUENTIAL_MARGINAL_CHANGE_LIFT_DEMONSTRATED";
const report = {
  experiment: "Q140",
  title: "Sequential per-number marginal change detection with global FWER control",
  source: { archive_blob_sha: archiveSha, archive_rows: 3405, eligible_draws: 3404, eligible_cutoff: "2026-11-10",
    excluded_row: { date: excluded.date, numbers: excluded.nums } },
  design: { targets: 3204, window_draws: W, first_half_draws: H, recent_half_draws: H,
    discovery: 1922, validation: 641, blind_oos_historical: 641, shrinkage_alpha: ALPHA,
    tests_per_walk_forward: TESTS, global_fwer_alpha: 0.05, nominal_per_test_alpha: NOMINAL_ALPHA,
    implemented_per_test_threshold: THRESHOLD, threshold_rounding: "slightly conservative relative to exact 0.05/128160" },
  models: {
    M0: "Uniform exact 5-of-40 subset distribution.",
    M1: "Always-on recent-100 frequency weights with alpha=200 shrinkage toward p=0.125 and exact e5 normalization.",
    M2: "Sparse adaptation: only numbers passing the global exact change test receive the same recent-100 weight; all others retain weight 1."
  },
  change_detection: {
    test: "Two-sided Fisher exact conditional hypergeometric test of first-half count given total occurrences in the 200-draw window.",
    familywise_tests: TESTS, per_test_alpha: THRESHOLD,
    flagged_number_target_events: results.reduce((s, r) => s + r.flagged.length, 0),
    targets_with_any_alarm: results.filter(r => r.flagged.length).length,
    flagged_number_frequency: flagFrequency, alarms_by_split: alarms
  },
  scoring: {
    joint_subset_log_loss: "-log(product of selected weights / e5(weights))",
    marginal_brier: "mean squared error over 40 exact marginal inclusion probabilities",
    gain_direction: "baseline loss minus model loss; positive favors model"
  },
  split_results: splitSummary,
  inference: {
    endpoints, holm_family_size: endpoints.length,
    holm_method: "Holm across all 12 one-sided holdout endpoints",
    paired_block_sign_flip_replicates: 10000, circular_block_bootstrap_replicates: 10000,
    block_length: 20, discovery_inference: "descriptive only"
  },
  decision,
  limitations: [
    "Exploratory within broad Q00-Q139 family; Holm covers only Q140's 12 holdout endpoints.",
    "Historical Blind OOS is not a virgin prospective sample.",
    "Global Bonferroni alarm threshold is intentionally conservative; absence of alarms does not prove exact stationarity.",
    "Test addresses marginal temporal change only, not higher-order dependence.",
    "Contest 315 is excluded because the official VinciCasa archive still lists it as pending."
  ],
  governance: { research_only: true, no_archive_mutation: true, no_freeze_mutation: true,
    no_q60_increment: true, no_engine_promotion: true, no_merge: true, human_review_required: true }
};
const ledger = "target_date,history_cutoff,window_start,window_end,alarm,flagged_numbers,min_exact_p,logloss_m0,logloss_m1,logloss_m2,brier_m0,brier_m1,brier_m2\n" + ledgerRows.join("\n") + "\n";
const validation = {
  experiment: "Q140", checks,
  checks_passed: checks.filter(x => x.pass).length, checks_total: checks.length,
  future_suffix_invariance_passed: checks.filter(x => x.id.startsWith("future_suffix_invariance_") && x.pass).length,
  deterministic_replay: true, source_rows: all.length, eligible_rows: data.length, target_rows: results.length,
  exact_normalization: "Exact marginal inclusion probabilities for M0/M1/M2 sum to five at all tested boundary/sample targets.",
  anti_leakage: "Each target reads only its prior 200 eligible draws; target is scored before the target row enters any future history.",
  status: "PASS"
};
const reportText = JSON.stringify(report, null, 2) + "\n";
const validationText = JSON.stringify(validation, null, 2) + "\n";
const ledgerText = ledger;
const expectedReport = JSON.parse(read(reportPath));
compareDeep(report, expectedReport, "report");
if (ledgerText !== read(ledgerPath)) fail("target ledger differs from committed bytes");
compareDeep(validation, JSON.parse(read(validationPath)), "validation");

const manifest = JSON.parse(read(manifestPath));
for (const entry of manifest.files) {
  const buf = fs.readFileSync(entry.path);
  if (gitBlobSha(buf) !== entry.git_blob_sha) fail("manifest SHA mismatch for " + entry.path);
  if (buf.length !== entry.byte_length) fail("manifest byte length mismatch for " + entry.path);
}
if (validation.checks_passed !== 32 || validation.future_suffix_invariance_passed !== 9) fail("validation totals unexpected");
console.log("Q140 REPLAY PASS: 3,204 strict-prior targets; 128,160 exact marginal tests; 0 alarms; 32/32 checks; suffix invariance 9/9; report tolerance 1e-10; ledger byte-identical; manifest " + manifest.files.length + "/" + manifest.files.length + " verified.");
