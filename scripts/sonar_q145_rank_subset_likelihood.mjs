import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

export const Q145 = Object.freeze({
  archivePath: "data/storico_daily.csv",
  shadowPath: "reports/sequence_agent/shadow_forecasts.csv",
  q144LedgerPath: "reports/sequence_agent/q144_shadow_rank_ensemble_ledger_2026-11-13.csv",
  q144FreezePath: "reports/sequence_agent/q144_shadow_rank_ensemble_freeze_2026-11-13.json",
  preregPath: "reports/sequence_agent/q145_rank_subset_likelihood_preregistration_2026-11-13.md",
  archiveSha: "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb",
  shadowSha: "ffc5a4eb0c38e4dfc67032e1ef5737689be5fec1",
  q144LedgerSha: "c14e13b0c8e7f7a8c20ae40c9af56101f5209762",
  q144FreezeSha: "df20af45433ae8693b90e06124d31df0ad345dfe",
  preregSha: "6bb8725ccb57ffad5f803352252ba94c42b29b70",
  targetDate: "2026-11-13",
  cutoff: "2026-11-12",
  frozenAtLocal: "2026-11-13T19:18:07+01:00",
  temperature: 1,
  bootstrapReplicates: 20000,
  bootstrapBlockLength: 2
});
const ROOT = process.cwd();
const OUT = {
  reportJson: "reports/sequence_agent/q145_rank_subset_likelihood_report_2026-11-13.json",
  reportMd: "reports/sequence_agent/q145_rank_subset_likelihood_report_2026-11-13.md",
  ledger: "reports/sequence_agent/q145_rank_subset_likelihood_ledger_2026-11-13.csv",
  freeze: "reports/sequence_agent/q145_rank_subset_likelihood_freeze_2026-11-13.json",
  checkpoint: "reports/sequence_agent/q145_rank_subset_likelihood_checkpoint_2026-11-13.json",
  manifest: "reports/sequence_agent/q145_rank_subset_likelihood_manifest_2026-11-13.json"
};

export function parseCsv(input) {
  const records = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < input.length; i++) {
    const c = input[i];
    if (quoted) {
      if (c === '"' && input[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field.replace(/\r$/, "")); records.push(row); row = []; field = ""; }
    else field += c;
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/, "")); records.push(row); }
  const header = records.shift();
  if (!header || header.length < 2) throw new Error("CSV header missing");
  return records.filter(r => !(r.length === 1 && !r[0])).map(r =>
    Object.fromEntries(header.map((key, i) => [key, r[i] ?? ""]))
  );
}
export function gitBlobSha1(content) {
  const bytes = Buffer.from(content, "utf8");
  return crypto.createHash("sha1").update("blob " + bytes.length + "\0").update(bytes).digest("hex");
}
export function choose(n, k) {
  if (k < 0 || k > n) return 0;
  let value = 1;
  for (let i = 1; i <= k; i++) value = value * (n - i + 1) / i;
  return value;
}
export function elementarySymmetric(weights, order) {
  const e = Array(order + 1).fill(0);
  e[0] = 1;
  for (const w of weights) for (let k = order; k >= 1; k--) e[k] += w * e[k - 1];
  return e[order];
}
export function rankWeights(top20, temperature = 1) {
  if (top20.length !== 20 || new Set(top20).size !== 20 ||
      top20.some(n => !Number.isInteger(n) || n < 1 || n > 40)) throw new Error("Invalid Top20");
  const weights = Array(40).fill(1);
  top20.forEach((n, i) => { weights[n - 1] = Math.exp(((20 - i) / 20) / temperature); });
  return weights;
}
export function marginalInclusionProbabilities(weights) {
  if (weights.length !== 40 || weights.some(w => !(w > 0) || !Number.isFinite(w))) throw new Error("Invalid weights");
  const denominator = elementarySymmetric(weights, 5);
  return weights.map((w, i) => w * elementarySymmetric(weights.filter((_, j) => j !== i), 4) / denominator);
}
export function scoreRankModel(top20, draw, temperature = 1) {
  const weights = rankWeights(top20, temperature);
  const e5 = elementarySymmetric(weights, 5);
  const logNormalizer = Math.log(e5);
  const logProbability = draw.reduce((sum, n) => sum + Math.log(weights[n - 1]), 0) - logNormalizer;
  const logGain = Math.log(choose(40, 5)) + logProbability;
  const marginals = marginalInclusionProbabilities(weights);
  const y = Array.from({ length: 40 }, (_, i) => draw.includes(i + 1) ? 1 : 0);
  const modelBrier = marginals.reduce((sum, p, i) => sum + (p - y[i]) ** 2, 0) / 40;
  const uniformBrier = y.reduce((sum, v) => sum + (0.125 - v) ** 2, 0) / 40;
  return {
    weights, marginals, logNormalizer, logGain, brierGain: uniformBrier - modelBrier,
    modalTop5: top20.slice(0, 5),
    modeProbability: Math.exp(top20.slice(0, 5).reduce((s, n) => s + Math.log(weights[n - 1]), 0) - logNormalizer)
  };
}
function parseNumbers(value) { return !value || !value.trim() ? [] : value.trim().split(/\s+/).map(Number); }
function round(x, digits = 12) { const v = Number(x.toFixed(digits)); return Object.is(v, -0) ? 0 : v; }
function roundArray(xs, digits = 12) { return xs.map(x => round(x, digits)); }
function avg(xs) { return xs.reduce((a, b) => a + b, 0) / xs.length; }
function quantile(xs, p) { const s = [...xs].sort((a, b) => a - b); return s[Math.floor((s.length - 1) * p)]; }
function mulberry32(seed) {
  return function () {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}
export function circularBlockBootstrap(values, seed, reps = 20000, blockLength = 2) {
  const rng = mulberry32(seed), n = values.length, out = [];
  for (let b = 0; b < reps; b++) {
    const sample = [];
    while (sample.length < n) {
      const start = Math.floor(rng() * n);
      for (let j = 0; j < blockLength && sample.length < n; j++) sample.push(values[(start + j) % n]);
    }
    out.push(avg(sample));
  }
  return [round(quantile(out, 0.025)), round(quantile(out, 0.975))];
}
export function exactSignFlipGreater(values) {
  const n = values.length;
  if (!n || n > 20) throw new Error("Exact sign-flip supports 1..20 pairs");
  const observed = avg(values);
  let extreme = 0;
  for (let mask = 0; mask < 2 ** n; mask++) {
    let sum = 0;
    for (let i = 0; i < n; i++) sum += (mask & (1 << i)) ? values[i] : -values[i];
    if (sum / n >= observed - 1e-12) extreme++;
  }
  return extreme / (2 ** n);
}
export function exactSignFlipTwoSided(values) {
  const n = values.length, observed = Math.abs(avg(values));
  let extreme = 0;
  for (let mask = 0; mask < 2 ** n; mask++) {
    let sum = 0;
    for (let i = 0; i < n; i++) sum += (mask & (1 << i)) ? values[i] : -values[i];
    if (Math.abs(sum / n) >= observed - 1e-12) extreme++;
  }
  return extreme / (2 ** n);
}
export function eProcessVille(logGains) {
  let cumulative = 0, maximum = 0;
  for (const gain of logGains) { cumulative += gain; maximum = Math.max(maximum, cumulative); }
  return Math.min(1, Math.exp(-maximum));
}
export function holmAdjust(pValues) {
  const entries = Object.entries(pValues).sort((a, b) => a[1] - b[1]);
  const out = {};
  let previous = 0;
  entries.forEach(([key, p], i) => { previous = Math.max(previous, Math.min(1, (entries.length - i) * p)); out[key] = round(previous); });
  return out;
}
function validateTop20(top20, label) {
  if (top20.length !== 20 || new Set(top20).size !== 20 ||
      top20.some(n => !Number.isInteger(n) || n < 1 || n > 40)) throw new Error(label + " invalid Top20");
}
function drawTimestamp(date, offset) { return Date.parse(date + "T20:00:00" + offset); }
export function validateShadowTemporalRow(row) {
  const freezeMs = Date.parse(row.frozen_at), offset = row.frozen_at.slice(-6), freezeDate = row.frozen_at.slice(0, 10);
  if (!Number.isFinite(freezeMs) || !(row.history_cutoff < row.target_date) ||
      !(row.history_cutoff <= freezeDate) || !(freezeMs < drawTimestamp(row.target_date, offset))) return false;
  if (row.history_cutoff === freezeDate && !(freezeMs > drawTimestamp(row.history_cutoff, offset))) return false;
  return true;
}
function validateShadowRows(shadowRows, archiveMap) {
  if (shadowRows.length !== 1364) throw new Error("Expected 1,364 shadow rows");
  let strictPrior = 0, pending = 0;
  const byDate = new Map();
  for (const row of shadowRows) {
    if (!validateShadowTemporalRow(row)) throw new Error("Shadow temporal guard failed: " + row.target_date);
    strictPrior++;
    if (!byDate.has(row.target_date)) byDate.set(row.target_date, []);
    byDate.get(row.target_date).push(row);
    if (row.target_date === Q145.targetDate) {
      pending++;
      if (row.actual_numbers || row.hit_count || row.hit_numbers || row.history_cutoff !== Q145.cutoff) throw new Error("Pending target invalid");
    } else if (row.status === "EVALUATED") {
      const actual = parseNumbers(row.actual_numbers).sort((a, b) => a - b);
      const canonical = archiveMap.get(row.target_date);
      if (!canonical || actual.join(",") !== canonical.join(",")) throw new Error("Shadow/archive mismatch: " + row.target_date);
    }
  }
  if (pending !== 43) throw new Error("Expected 43 pending outcome-free rows");
  for (const [date, group] of byDate) {
    if (date === Q145.targetDate) { if (group.length !== 43) throw new Error("Pending row count mismatch"); continue; }
    const rules = group.filter(r => ["family", "pair", "chain"].includes(r.config_type));
    if (rules.length !== 42 ||
        rules.filter(r => r.config_type === "family").length !== 24 ||
        rules.filter(r => r.config_type === "pair").length !== 12 ||
        rules.filter(r => r.config_type === "chain").length !== 6) throw new Error("Component count mismatch: " + date);
  }
  return { strictPriorChecks: strictPrior, pendingRows: pending, targetGroups: byDate.size };
}
function summarize(rows, model) {
  const a = rows.filter(r => r.models[model]);
  if (!a.length) return null;
  return { n: a.length, mean_log_gain: round(avg(a.map(r => r.models[model].logGain))),
    total_log_gain: round(a.reduce((s, r) => s + r.models[model].logGain, 0)),
    mean_brier_gain: round(avg(a.map(r => r.models[model].brierGain))),
    mean_mode_probability: round(avg(a.map(r => r.models[model].modeProbability)), 15) };
}
function renderMarkdown(r) {
  const f = x => Number(x).toFixed(6);
  const lines = [
    "# Q145 — Rank-to-subset likelihood calibration",
    "",
    "**Decision:** no historical predictive lift demonstrated; prospective freeze pending.",
    "",
    "## Method",
    "- Fixed utility: u(r)=(21-r)/20 for ranks 1..20; zero outside Top20; temperature T=1.",
    "- Exact unordered 5-of-40 PMF: P(S)=product(w_i)/e5(w), w_i=exp(u_i).",
    "- Primary endpoint: complete-quintet log-likelihood gain versus uniform. Secondary: marginal-inclusion Brier gain versus 0.125.",
    "",
    "## Walk-forward results",
    "| Split | Model | n | Mean log-gain | Mean Brier gain |",
    "|---|---|---:|---:|---:|"
  ];
  for (const split of ["discovery", "validation", "blind_oos"]) for (const model of ["borda", "inclusion", "app"]) {
    const s = r.splits[split][model];
    if (s) lines.push("| " + split + " | " + model + " | " + s.n + " | " + f(s.mean_log_gain) + " | " + f(s.mean_brier_gain) + " |");
  }
  lines.push("", "## Historical Blind OOS diagnostics (7 dates)", "| Diagnostic | Raw p | Holm p |", "|---|---:|---:|");
  for (const [key, p] of Object.entries(r.blind_inference.raw_p_values)) lines.push("| " + key + " | " + f(p) + " | " + f(r.blind_inference.holm_adjusted_p_values[key]) + " |");
  lines.push(
    "",
    "All historical inference is exploratory, not virgin confirmation: this PMF transformation was specified after Q144 historical outcomes had been inspected. Sign-flip tests assume symmetry/exchangeability. Holm covers only the five registered Q145 diagnostics, not all SONAR research.",
    "",
    "## Prospective 2026-11-13 freeze",
    "- Borda modal quintet: **" + r.prospective_freeze.borda_modal_top5.join(" · ") + "**",
    "- Equal-type inclusion modal quintet: **" + r.prospective_freeze.inclusion_modal_top5.join(" · ") + "**",
    "- Cutoff 2026-11-12; frozen 2026-11-13 at 19:18:07 Europe/Rome; outcome null.",
    "- The 2026-11-12 repository row has an unresolved discrepancy between official archive pages; the cutoff is preserved but not treated as independently source-confirmed.",
    "",
    "## Integrity and limits",
    "- 31 historical target rows reconciled against the pinned canonical archive.",
    "- 1,364 shadow rows checked for strict-prior cutoffs and pre-draw timestamps; 43 pending 2026-11-13 rows remain outcome-free.",
    "- 42 component forecasts per completed target (24 family / 12 pair / 6 chain); APP is an external comparator.",
    "- The PMF is normalized mathematically over all 658,008 quintets; this does not establish calibration or predictive power.",
    "- Seven historical Blind OOS dates are insufficient for confirmation. No model promotion.",
    "",
    "## Next action",
    "Keep the two probability forecasts frozen and append-only. Reconcile only after official publication. Accumulate at least 100 consecutive prospective targets without retuning."
  );
  return lines.join("\n") + "\n";
}
function buildArtifacts() {
  const read = p => fs.readFileSync(path.join(ROOT, p), "utf8");
  const archiveText = read(Q145.archivePath), shadowText = read(Q145.shadowPath);
  const q144LedgerText = read(Q145.q144LedgerPath), q144FreezeText = read(Q145.q144FreezePath);
  const preregText = read(Q145.preregPath);
  const sourceHashes = {
    archive: gitBlobSha1(archiveText), shadow: gitBlobSha1(shadowText),
    q144_ledger: gitBlobSha1(q144LedgerText), q144_freeze: gitBlobSha1(q144FreezeText),
    preregistration: gitBlobSha1(preregText)
  };
  const expected = { archive: Q145.archiveSha, shadow: Q145.shadowSha, q144_ledger: Q145.q144LedgerSha,
    q144_freeze: Q145.q144FreezeSha, preregistration: Q145.preregSha };
  for (const key of Object.keys(expected)) if (sourceHashes[key] !== expected[key]) throw new Error("Pinned source SHA mismatch: " + key);
  const archiveRows = parseCsv(archiveText), archiveMap = new Map();
  for (const r of archiveRows) {
    const nums = [r.n1, r.n2, r.n3, r.n4, r.n5].map(Number).sort((a, b) => a - b);
    if (nums.length !== 5 || new Set(nums).size !== 5) throw new Error("Invalid archive row " + r.data);
    archiveMap.set(r.data, nums);
  }
  const shadowRows = parseCsv(shadowText), shadowAudit = validateShadowRows(shadowRows, archiveMap);
  const q144Rows = parseCsv(q144LedgerText), q144Freeze = JSON.parse(q144FreezeText);
  if (q144Rows.length !== 31) throw new Error("Expected 31 Q144 target rows");
  if (q144Freeze.target_date !== Q145.targetDate || q144Freeze.history_cutoff !== Q145.cutoff ||
      q144Freeze.status !== "FROZEN_PENDING" || q144Freeze.outcome !== null) throw new Error("Q144 freeze invalid");
  const q144Ms = Date.parse(q144Freeze.frozen_at_local), q145Ms = Date.parse(Q145.frozenAtLocal);
  if (!(q144Ms < q145Ms && q145Ms < drawTimestamp(Q145.targetDate, "+01:00"))) throw new Error("Q145 freeze not strictly pre-target");
  if (!archiveMap.has(Q145.cutoff)) throw new Error("Cutoff missing from archive");

  const rows = q144Rows.map((r, i) => {
    const draw = parseNumbers(r.actual_numbers).sort((a, b) => a - b);
    const canonical = archiveMap.get(r.target_date);
    if (!canonical || draw.join(",") !== canonical.join(",")) throw new Error("Q144/archive mismatch " + r.target_date);
    if (+r.rule_rows !== 42 || +r.family_rows !== 24 || +r.pair_rows !== 12 || +r.chain_rows !== 6) throw new Error("Q144 counts mismatch " + r.target_date);
    const bordaRank = parseNumbers(r.borda_top20), inclusionRank = parseNumbers(r.inclusion_top20);
    validateTop20(bordaRank, "Borda"); validateTop20(inclusionRank, "Inclusion");
    if (draw.filter(n => bordaRank.includes(n)).length !== +r.borda_hits ||
        draw.filter(n => inclusionRank.includes(n)).length !== +r.inclusion_hits) throw new Error("Q144 hits mismatch " + r.target_date);
    let appRank = null;
    if (r.app_available === "1") {
      appRank = parseNumbers(r.app_top20); validateTop20(appRank, "APP");
      if (draw.filter(n => appRank.includes(n)).length !== +r.app_hits) throw new Error("APP hits mismatch " + r.target_date);
    } else if (r.app_top20 || r.app_hits) throw new Error("APP flag mismatch " + r.target_date);
    const split = i < 18 ? "discovery" : i < 24 ? "validation" : "blind_oos";
    return { date: r.target_date, draw, split, models: {
      borda: scoreRankModel(bordaRank, draw, Q145.temperature),
      inclusion: scoreRankModel(inclusionRank, draw, Q145.temperature),
      app: appRank ? scoreRankModel(appRank, draw, Q145.temperature) : null
    }};
  });
  const splits = { discovery: rows.slice(0, 18), validation: rows.slice(18, 24), blind_oos: rows.slice(24) };
  const splitSummary = {};
  for (const [name, list] of Object.entries(splits)) {
    splitSummary[name] = { n: list.length };
    for (const model of ["borda", "inclusion", "app"]) {
      const s = summarize(list, model);
      if (s) splitSummary[name][model] = s;
    }
  }
  const blind = splits.blind_oos, appBlind = blind.filter(r => r.models.app);
  const diffBI = blind.map(r => r.models.borda.logGain - r.models.inclusion.logGain);
  const diffBA = appBlind.map(r => r.models.borda.logGain - r.models.app.logGain);
  const rawP = {
    borda_vs_uniform_eprocess: eProcessVille(blind.map(r => r.models.borda.logGain)),
    inclusion_vs_uniform_eprocess: eProcessVille(blind.map(r => r.models.inclusion.logGain)),
    app_vs_uniform_eprocess: eProcessVille(appBlind.map(r => r.models.app.logGain)),
    borda_vs_inclusion_signflip: exactSignFlipGreater(diffBI),
    borda_vs_app_signflip: exactSignFlipGreater(diffBA)
  };
  const adjustedP = holmAdjust(rawP);
  const ci = {
    borda_vs_uniform: circularBlockBootstrap(blind.map(r => r.models.borda.logGain), 14501),
    borda_vs_inclusion: circularBlockBootstrap(diffBI, 14502),
    borda_vs_app: circularBlockBootstrap(diffBA, 14503)
  };
  const twoSided = { borda_vs_inclusion: round(exactSignFlipTwoSided(diffBI)), borda_vs_app: round(exactSignFlipTwoSided(diffBA)) };
  const pb = scoreRankModel(q144Freeze.top20_ranked, [], Q145.temperature);
  const pi = scoreRankModel(q144Freeze.alternative_equal_type_inclusion_top20, [], Q145.temperature);
  const freeze = {
    schema_version: "1.0", experiment_id: "Q145", algorithm_id: "rank_to_unordered_subset_pl_v1",
    status: "FROZEN_PENDING", target_date: Q145.targetDate, history_cutoff: Q145.cutoff,
    frozen_at_utc: "2026-11-13T18:18:07Z", frozen_at_local: Q145.frozenAtLocal,
    source_archive_blob_sha: sourceHashes.archive, source_shadow_blob_sha: sourceHashes.shadow,
    q144_ledger_blob_sha: sourceHashes.q144_ledger, q144_freeze_blob_sha: sourceHashes.q144_freeze,
    preregistration_blob_sha: sourceHashes.preregistration, temperature: Q145.temperature,
    utility_definition: "u(r)=(21-r)/20 for ranks 1..20; u=0 outside Top20",
    probability_definition: "P(S)=product(i in S) w_i / e5(w), w_i=exp(u_i), unordered |S|=5",
    uniform_ticket_probability: round(1 / choose(40, 5), 15),
    borda: {
      top20_ranked: q144Freeze.top20_ranked, modal_top5: pb.modalTop5,
      weights: roundArray(pb.weights), marginal_inclusion_probabilities: roundArray(pb.marginals),
      marginal_sum: round(pb.marginals.reduce((a, b) => a + b, 0)),
      log_e5_normalizer: round(pb.logNormalizer), modal_quintet_probability: round(pb.modeProbability, 15),
      modal_probability_ratio_vs_uniform: round(pb.modeProbability * choose(40, 5))
    },
    equal_type_inclusion: {
      top20_ranked: q144Freeze.alternative_equal_type_inclusion_top20, modal_top5: pi.modalTop5,
      weights: roundArray(pi.weights), marginal_inclusion_probabilities: roundArray(pi.marginals),
      marginal_sum: round(pi.marginals.reduce((a, b) => a + b, 0)),
      log_e5_normalizer: round(pi.logNormalizer), modal_quintet_probability: round(pi.modeProbability, 15),
      modal_probability_ratio_vs_uniform: round(pi.modeProbability * choose(40, 5))
    },
    outcome: null,
    note: "Probability forecasts only; modal quintets are not validated betting recommendations. The 2026-11-12 cutoff row is repository-present but official archive pages were inconsistent at registration."
  };
  const report = {
    schema_version: "1.0", experiment_id: "Q145", title: "Rank-to-subset likelihood calibration of Q144 shadow ensembles",
    status: "COMPLETE_RETROSPECTIVE_EXPLORATORY_WITH_PROSPECTIVE_FREEZE",
    temperature: Q145.temperature, utility: "u(r)=(21-r)/20 for ranks 1..20; zero outside Top20",
    pmf: "P(S)=product(w_i for i in S)/e5(w), w_i=exp(u_i), |S|=5",
    uniform_ticket_probability: round(1 / choose(40, 5), 15), source_blob_shas: sourceHashes,
    integrity: { archive_draws: archiveRows.length, q144_targets: rows.length, shadow_rows: shadowRows.length,
      strict_prior_freeze_checks: shadowAudit.strictPriorChecks, pending_2026_11_13_rows: shadowAudit.pendingRows,
      pending_outcomes_empty: true, historical_targets_reconciled: rows.length, q144_rule_count_per_target: 42,
      family_pair_chain_counts: "24/12/6", q144_hit_counts_recomputed: true, future_target_freeze_pre_draw: true },
    sample: { targets: rows.length, discovery: 18, validation: 6, historical_blind_oos: 7,
      app_targets: rows.filter(r => r.models.app).length,
      app_discovery: splits.discovery.filter(r => r.models.app).length,
      app_validation: splits.validation.filter(r => r.models.app).length, app_blind_oos: appBlind.length },
    splits: splitSummary,
    blind_inference: {
      raw_p_values: Object.fromEntries(Object.entries(rawP).map(([k, v]) => [k, round(v)])),
      holm_adjusted_p_values: adjustedP, two_sided_signflip_p_values: twoSided, bootstrap_ci_95: ci,
      bootstrap_replicates: Q145.bootstrapReplicates, circular_block_length: Q145.bootstrapBlockLength,
      signflip_assignments: 128,
      caveat: "Historical Q145 inference is exploratory: the rank-to-PMF transformation was specified after Q144 historical outcomes were inspected. No historical p-value is confirmatory."
    },
    prospective_freeze: { target_date: freeze.target_date, history_cutoff: freeze.history_cutoff,
      frozen_at_local: freeze.frozen_at_local, borda_modal_top5: pb.modalTop5,
      inclusion_modal_top5: pi.modalTop5, outcome: null },
    decision: "NO_HISTORICAL_PREDICTIVE_LIFT_CLAIM; PROSPECTIVE_FROZEN_TEST_PENDING"
  };
  const ledgerHeader = "target_date,actual_numbers,split,borda_log_gain,borda_brier_gain,inclusion_log_gain,inclusion_brier_gain,app_log_gain,app_brier_gain";
  const ledgerText = [ledgerHeader, ...rows.map(r => [
    r.date, r.draw.join(" "), r.split, round(r.models.borda.logGain), round(r.models.borda.brierGain),
    round(r.models.inclusion.logGain), round(r.models.inclusion.brierGain),
    r.models.app ? round(r.models.app.logGain) : "", r.models.app ? round(r.models.app.brierGain) : ""
  ].join(","))].join("\n") + "\n";
  const reportJson = JSON.stringify(report, null, 2) + "\n";
  const reportMd = renderMarkdown(report);
  const freezeJson = JSON.stringify(freeze, null, 2) + "\n";
  const checkpoint = {
    schema_version: "1.0", experiment_id: "Q145", status: "Q145_ARTIFACTS_REPLAYABLE_DEDICATED_CI_PENDING",
    branch: "research/q145-rank-subset-likelihood-20261113", parent_branch: "research/q144-shadow-rank-ensemble-20261113",
    source_blob_shas: sourceHashes, sample: report.sample, split_summary: splitSummary,
    decision: report.decision, prospective_freeze: { target_date: Q145.targetDate, cutoff: Q145.cutoff, status: "FROZEN_PENDING", outcome: null },
    next_action: "Verify Q145 exact-head CI and remote Git readback; reconcile 2026-11-13 only after official publication; accumulate 100 prospective targets without retuning."
  };
  const checkpointJson = JSON.stringify(checkpoint, null, 2) + "\n";
  const artifacts = {
    [Q145.preregPath]: preregText,
    "scripts/sonar_q145_rank_subset_likelihood.mjs": read("scripts/sonar_q145_rank_subset_likelihood.mjs"),
    "tests/test_sonar_q145_rank_subset_likelihood.mjs": read("tests/test_sonar_q145_rank_subset_likelihood.mjs"),
    [OUT.reportJson]: reportJson, [OUT.reportMd]: reportMd, [OUT.ledger]: ledgerText,
    [OUT.freeze]: freezeJson, [OUT.checkpoint]: checkpointJson
  };
  const artifactBlobShas = Object.fromEntries(Object.entries(artifacts).map(([p, content]) => [p, gitBlobSha1(content)]));
  const manifest = {
    schema_version: "1.0", experiment_id: "Q145", branch: "research/q145-rank-subset-likelihood-20261113",
    status: "Q145_DETERMINISTIC_ARTIFACT_MANIFEST", source_blob_shas: sourceHashes,
    artifact_blob_shas: artifactBlobShas,
    target: { date: Q145.targetDate, cutoff: Q145.cutoff, frozen_at_local: Q145.frozenAtLocal },
    no_canonical_archive_or_existing_freeze_modified: true, no_engine_promotion: true
  };
  return { report, reportJson, reportMd, ledgerText, freezeJson, checkpointJson, manifestJson: JSON.stringify(manifest, null, 2) + "\n" };
}
export function verifyArtifacts() {
  const b = buildArtifacts();
  const expected = {
    [OUT.reportJson]: b.reportJson, [OUT.reportMd]: b.reportMd, [OUT.ledger]: b.ledgerText,
    [OUT.freeze]: b.freezeJson, [OUT.checkpoint]: b.checkpointJson, [OUT.manifest]: b.manifestJson
  };
  const mismatches = [];
  for (const [p, content] of Object.entries(expected)) if (fs.readFileSync(path.join(ROOT, p), "utf8") !== content) mismatches.push(p);
  if (mismatches.length) throw new Error("Q145 replay mismatch: " + mismatches.join(", "));
  return { status: "Q145_VERIFY_OK", targets: b.report.sample.targets, blind: b.report.sample.historical_blind_oos,
    strictPriorChecks: b.report.integrity.strict_prior_freeze_checks, artifacts: Object.keys(expected).length };
}
if (path.basename(process.argv[1] || "") === "sonar_q145_rank_subset_likelihood.mjs") {
  process.stdout.write(JSON.stringify(verifyArtifacts()) + "\n");
}
