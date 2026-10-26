#!/usr/bin/env node
/**
 * Recompute the active VinciCasa SONAR engine diagnostics by executing the
 * exact helper functions currently committed in src/VinciCasaLab.jsx.
 *
 * The historical target is never passed into its own forecast prefix.
 * Existing shadow rows are append-only: missing historical freezes are never
 * reconstructed and an existing forecast is never rewritten.
 */
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CSV_PATH = path.join(ROOT, "data", "storico_daily.csv");
const APP_DATA_PATH = path.join(ROOT, "src", "data.json");
const APP_SOURCE_PATH = path.join(ROOT, "src", "VinciCasaLab.jsx");
const SHADOW_PATH = path.join(ROOT, "reports", "sequence_agent", "shadow_forecasts.csv");
const REPORT_PATH = path.join(ROOT, "reports", "sequence_agent", "active_engine_walkforward.json");
const CONFIG_ID = "APP::SONAR_HYBRID_RECENCY_ANALOG_FULL_HISTORY";
const CONFIG_TYPE = "app_engine";
const RULE_SEQUENCE = "freq20>freq100>freq500>global>analog_overlap3>persistence>recent5";
const MODEL_VERSION = "hybrid-recency-analog-full-history-v2";
const TZ = "Europe/Rome";
const WARMUP = 200;
const DRAW_HOUR = 20;
const DRAW_MINUTE = 0;
const FAMILY_SIZE = 43;

function fail(message) {
  console.error("ACTIVE ENGINE PIPELINE BLOCKED: " + message);
  process.exit(1);
}

function parseCanonicalCsv(text) {
  const lines = text.trimEnd().split(/\r?\n/);
  const expected = "data,n1,n2,n3,n4,n5";
  if (lines[0] !== expected) fail("canonical CSV header mismatch");
  const rows = [];
  const seen = new Set();
  let previous = "";
  for (let i = 1; i < lines.length; i++) {
    const fields = lines[i].split(",");
    if (fields.length !== 6) fail("malformed canonical CSV line " + (i + 1));
    const date = fields[0];
    const numbers = fields.slice(1).map(Number);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(date + "T00:00:00Z"))) {
      fail("invalid ISO date on line " + (i + 1));
    }
    if (seen.has(date) || (previous && date <= previous)) fail("duplicate or unordered date " + date);
    if (numbers.some(n => !Number.isInteger(n) || n < 1 || n > 40) ||
        new Set(numbers).size !== 5 || numbers.some((n, j) => j > 0 && n < numbers[j - 1])) {
      fail("invalid five-number draw on line " + (i + 1) + ": " + numbers.join(" "));
    }
    rows.push({ d: date, n: numbers });
    seen.add(date);
    previous = date;
  }
  if (rows.length < 1000) fail("canonical history unexpectedly short: " + rows.length);
  return rows;
}

function validateAppData(csvDraws, appData) {
  if (!Array.isArray(appData.modelDraws) || appData.modelDraws.length !== csvDraws.length) {
    fail("src/data.json modelDraws length does not match canonical CSV");
  }
  if (appData.histN !== csvDraws.length || appData.lastDate !== csvDraws[csvDraws.length - 1].d) {
    fail("src/data.json histN/lastDate does not match canonical CSV");
  }
  for (let i = 0; i < csvDraws.length; i++) {
    const a = appData.modelDraws[i];
    const b = csvDraws[i];
    if (!a || a.d !== b.d || !Array.isArray(a.n) || a.n.join(",") !== b.n.join(",")) {
      fail("src/data.json modelDraws differs from canonical CSV at row " + (i + 2));
    }
  }
}

function extractFunction(source, name, nextName) {
  const start = source.indexOf("function " + name + "(");
  if (start < 0) fail("cannot find function " + name + " in committed app source");
  const end = nextName
    ? source.indexOf("\nfunction " + nextName + "(", start + 1)
    : source.indexOf("\nconst Card =", start + 1);
  if (end < 0) fail("cannot delimit function " + name + " in committed app source");
  return source.slice(start, end).trim();
}

function buildExactAppScorer(source) {
  const code = [
    extractFunction(source, "overlapCount", "sonarTransitionProfile"),
    extractFunction(source, "sonarTransitionProfile", "sonarAnalogCore"),
    extractFunction(source, "sonarAnalogCore", null),
    "return sonarAnalogCore(draws);"
  ].join("\n");
  try {
    return new Function("draws", code);
  } catch (error) {
    fail("could not compile the exact app engine functions: " + error.message);
  }
}

function choose(n, k) {
  if (k < 0 || k > n) return 0;
  let value = 1;
  for (let i = 1; i <= k; i++) value = value * (n - i + 1) / i;
  return value;
}

const DENOM = choose(40, 5);
const BASE_TOP20 = choose(20, 5) / DENOM;
const BASE_TOP10 = choose(10, 5) / DENOM;
const BASE_TOP5 = choose(5, 5) / DENOM;

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

function round(value, digits = 6) {
  if (value === null || value === undefined || !Number.isFinite(value)) return null;
  return Number(value.toFixed(digits));
}

function nextDate(isoDate) {
  const d = new Date(isoDate + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + 1);
  return d.toISOString().slice(0, 10);
}

function localParts(date) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"
  }).formatToParts(date);
  const out = {};
  for (const p of parts) if (p.type !== "literal") out[p.type] = Number(p.value);
  out.date = String(out.year).padStart(4, "0") + "-" +
    String(out.month).padStart(2, "0") + "-" + String(out.day).padStart(2, "0");
  return out;
}

function offsetMinutesAt(date) {
  const p = localParts(date);
  const localAsUtc = Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second);
  return Math.round((localAsUtc - date.getTime()) / 60000);
}

function localIso(date) {
  const p = localParts(date);
  const offset = offsetMinutesAt(date);
  const sign = offset >= 0 ? "+" : "-";
  const abs = Math.abs(offset);
  return p.date + "T" + String(p.hour).padStart(2, "0") + ":" +
    String(p.minute).padStart(2, "0") + ":" + String(p.second).padStart(2, "0") +
    sign + String(Math.floor(abs / 60)).padStart(2, "0") + ":" +
    String(abs % 60).padStart(2, "0");
}

function nominalTargetInstant(targetDate) {
  const [year, month, day] = targetDate.split("-").map(Number);
  const noonUtc = new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
  const offset = offsetMinutesAt(noonUtc);
  return new Date(Date.UTC(year, month - 1, day, DRAW_HOUR, DRAW_MINUTE, 0) - offset * 60000);
}

function parseNumbers(value) {
  if (value === null || value === undefined || !String(value).trim()) return [];
  return String(value).trim().split(/\s+/).map(Number);
}

function parseSimpleCsv(text) {
  const lines = text.trimEnd().split(/\r?\n/);
  const header = lines.shift().split(",");
  const rows = lines.filter(Boolean).map((line, index) => {
    const values = line.split(",");
    if (values.length !== header.length) fail("malformed shadow CSV row " + (index + 2));
    return Object.fromEntries(header.map((key, i) => [key, values[i] ?? ""]));
  });
  return { header, rows };
}

function csvCell(value) {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function appendFreezeIfEligible(draws, score, now) {
  const expectedHeader = [
    "target_date", "frozen_at", "history_cutoff", "config_id", "config_type",
    "rule_sequence", "top20", "top10", "top5", "status", "actual_numbers",
    "hit_numbers", "hit_count", "all5_top20", "evaluated_at_data_through", "timeliness_note"
  ];
  let raw = fs.existsSync(SHADOW_PATH) ? fs.readFileSync(SHADOW_PATH, "utf8") : "";
  let parsed;
  if (!raw.trim()) {
    parsed = { header: expectedHeader, rows: [] };
    raw = expectedHeader.join(",") + "\n";
  } else {
    parsed = parseSimpleCsv(raw);
    if (parsed.header.join(",") !== expectedHeader.join(",")) {
      fail("shadow_forecasts.csv schema mismatch");
    }
  }
  const p = localParts(now);
  const targetDate = p.date;
  const latestDate = draws[draws.length - 1].d;
  const exists = parsed.rows.some(r => r.config_id === CONFIG_ID && r.target_date === targetDate);
  const beforeDraw = p.hour * 60 + p.minute < DRAW_HOUR * 60 + DRAW_MINUTE;
  const archiveCutoffIsYesterday = nextDate(latestDate) === targetDate;
  let created = false;
  if (!exists && beforeDraw && archiveCutoffIsYesterday) {
    const row = {
      target_date: targetDate,
      frozen_at: localIso(now),
      history_cutoff: latestDate,
      config_id: CONFIG_ID,
      config_type: CONFIG_TYPE,
      rule_sequence: RULE_SEQUENCE,
      top20: score.slice(0, 20).map(x => x.n).join(" "),
      top10: score.slice(0, 10).map(x => x.n).join(" "),
      top5: score.slice(0, 5).map(x => x.n).join(" "),
      status: "FROZEN_PENDING",
      actual_numbers: "",
      hit_numbers: "",
      hit_count: "",
      all5_top20: "",
      evaluated_at_data_through: "",
      timeliness_note: "Exact committed UI scorer; append-only pre-target freeze; cutoff matches canonical latest date."
    };
    const line = expectedHeader.map(k => csvCell(row[k])).join(",") + "\n";
    if (!raw.endsWith("\n")) raw += "\n";
    fs.appendFileSync(SHADOW_PATH, line, "utf8");
    parsed.rows.push(row);
    created = true;
  }
  return { rows: parsed.rows, created, targetDate, latestDate, schema: expectedHeader };
}

function historyForFreeze(row, draws) {
  const targetIndex = draws.findIndex(d => d.d === row.target_date);
  if (targetIndex >= 0) return draws.slice(0, targetIndex);
  const cutoffIndex = draws.findIndex(d => d.d === row.history_cutoff);
  if (cutoffIndex >= 0) return draws.slice(0, cutoffIndex + 1);
  return null;
}

function reconcileFreezes(rows, draws, scoreFunction) {
  const appRows = rows.filter(r => r.config_id === CONFIG_ID).sort((a, b) =>
    a.target_date.localeCompare(b.target_date) || a.frozen_at.localeCompare(b.frozen_at));
  const checked = [];
  for (const row of appRows) {
    const history = historyForFreeze(row, draws);
    const ranking = history && history.length >= 8 ? scoreFunction(history).scores.map(x => x.n) : [];
    const stored20 = parseNumbers(row.top20);
    const stored10 = parseNumbers(row.top10);
    const stored5 = parseNumbers(row.top5);
    const actual = parseNumbers(row.actual_numbers);
    const frozenAt = new Date(row.frozen_at);
    const beforeTarget = Number.isFinite(frozenAt.getTime()) &&
      frozenAt.getTime() < nominalTargetInstant(row.target_date).getTime();
    const cutoffMatches = nextDate(row.history_cutoff) === row.target_date;
    const exactTop20 = ranking.length === 40 && stored20.join(",") === ranking.slice(0, 20).join(",");
    const sameTop5Set = ranking.length === 40 &&
      stored5.slice().sort((a, b) => a - b).join(",") === ranking.slice(0, 5).slice().sort((a, b) => a - b).join(",");
    checked.push({
      target_date: row.target_date,
      frozen_at: row.frozen_at,
      history_cutoff: row.history_cutoff,
      status: row.status,
      frozen_before_nominal_target: beforeTarget,
      cutoff_matches_previous_day: cutoffMatches,
      exact_top20_matches_committed_ui: exactTop20,
      top5_set_matches_committed_ui: sameTop5Set,
      stored_actual_numbers: actual,
      eligible_for_exact_engine_prospective_primary: beforeTarget && cutoffMatches && exactTop20 &&
        (row.status === "FROZEN_PENDING" || row.status === "EVALUATED"),
      preserved_without_rewrite: true
    });
  }
  return {
    rows_checked: checked.length,
    exact_top20_matches: checked.filter(r => r.exact_top20_matches_committed_ui).length,
    exact_top20_mismatches: checked.filter(r => !r.exact_top20_matches_committed_ui).length,
    missing_freezes_reconstructed: 0,
    rows: checked,
    policy: "Append-only. Existing freezes are never changed or reconstructed; a ranking that does not reproduce under the committed UI source is excluded from exact-engine prospective primary evaluation."
  };
}

function summarize(records) {
  const n = records.length;
  const count20 = records.filter(r => r.h20 === 5).length;
  const count10 = records.filter(r => r.h10 === 5).length;
  const count5 = records.filter(r => r.h5 === 5).length;
  const p = binomialTail(n, BASE_TOP20, count20);
  return {
    targets: n,
    first_target: records[0]?.date ?? null,
    last_target: records[n - 1]?.date ?? null,
    mean_hits_top5: round(records.reduce((s, r) => s + r.h5, 0) / n),
    mean_hits_top10: round(records.reduce((s, r) => s + r.h10, 0) / n),
    mean_hits_top20: round(records.reduce((s, r) => s + r.h20, 0) / n),
    top20_5of5: count20,
    top10_5of5: count10,
    top5_5of5: count5,
    top20_4plus: records.filter(r => r.h20 >= 4).length,
    top20_5of5_random_expected: round(n * BASE_TOP20),
    top20_5of5_binomial_p_unadjusted_one_sided: round(p, 8),
    top20_5of5_bonferroni_family_43: round(Math.min(1, p * FAMILY_SIZE), 8)
  };
}

function main() {
  const now = new Date();
  const csvDraws = parseCanonicalCsv(fs.readFileSync(CSV_PATH, "utf8"));
  const appData = JSON.parse(fs.readFileSync(APP_DATA_PATH, "utf8"));
  validateAppData(csvDraws, appData);
  const draws = appData.modelDraws;
  const source = fs.readFileSync(APP_SOURCE_PATH, "utf8");
  const scoreFunction = buildExactAppScorer(source);

  const records = [];
  for (let targetIndex = WARMUP; targetIndex < draws.length; targetIndex++) {
    const prefix = draws.slice(0, targetIndex);
    const ranked = scoreFunction(prefix).scores.map(x => x.n);
    if (ranked.length !== 40 || new Set(ranked).size !== 40) {
      fail("scorer returned an invalid ranking before target " + draws[targetIndex].d);
    }
    const actual = new Set(draws[targetIndex].n);
    const hitCount = k => ranked.slice(0, k).filter(n => actual.has(n)).length;
    records.push({
      date: draws[targetIndex].d,
      h5: hitCount(5),
      h10: hitCount(10),
      h20: hitCount(20)
    });
  }
  if (records.length !== draws.length - WARMUP) fail("walk-forward target count mismatch");

  const cut1 = Math.floor(records.length * 0.6);
  const cut2 = Math.floor(records.length * 0.8);
  const splits = {
    discovery: summarize(records.slice(0, cut1)),
    validation: summarize(records.slice(cut1, cut2)),
    oos: summarize(records.slice(cut2))
  };

  const currentRanking = scoreFunction(draws).scores;
  const shadow = appendFreezeIfEligible(draws, currentRanking, now);
  const reconciliation = reconcileFreezes(shadow.rows, draws, scoreFunction);
  const appRows = shadow.rows.filter(r => r.config_id === CONFIG_ID).sort((a, b) =>
    a.target_date.localeCompare(b.target_date) || a.frozen_at.localeCompare(b.frozen_at));
  const currentRow = appRows[appRows.length - 1] || null;
  const currentReconciliation = currentRow
    ? reconciliation.rows.find(r => r.target_date === currentRow.target_date && r.frozen_at === currentRow.frozen_at)
    : null;

  let dataBlobSha = "";
  let appBlobSha = "";
  let currentCommit = "";
  try {
    dataBlobSha = execFileSync("git", ["rev-parse", "HEAD:data/storico_daily.csv"], { encoding: "utf8" }).trim();
    appBlobSha = execFileSync("git", ["rev-parse", "HEAD:src/VinciCasaLab.jsx"], { encoding: "utf8" }).trim();
    currentCommit = execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
  } catch (error) {
    fail("could not resolve source git identifiers: " + error.message);
  }

  const report = {
    status: "COMPLETE_RETROSPECTIVE_EXPLORATORY",
    validation_status: "EXPLORATORY_NOT_PROMOTABLE",
    model_id: CONFIG_ID,
    model_version: MODEL_VERSION,
    implementation_commit: currentCommit,
    implementation_source_blob_sha: appBlobSha,
    source: "data/storico_daily.csv",
    source_git_blob_sha: dataBlobSha,
    generated_at_utc: now.toISOString(),
    data: {
      first_date: draws[0].d,
      last_date: draws[draws.length - 1].d,
      total_draws: draws.length,
      min_history_before_target: WARMUP,
      walk_forward_targets: records.length
    },
    method: {
      weights: {
        frequency_last20: 0.38,
        frequency_last100: 0.22,
        frequency_last500: 0.14,
        frequency_full_history: 0.06,
        analog_successor_votes: 0.10,
        persistence: 0.06,
        recent_presence_last5: 0.04
      },
      normalization: "Exact committed src/VinciCasaLab.jsx sonarAnalogCore implementation; each feature min-max normalized across numbers 1..40 per target; score ties resolve by smaller number.",
      analog_rule: "Historical draw overlaps the last known draw by at least 3 numbers; each successor number receives overlap^3 votes.",
      leakage_control: "For each target, the exact committed UI scorer receives only draws strictly before that target; the target draw is never included in its feature prefix.",
      split_rule: "Chronological 60% discovery / 20% validation / 20% OOS after the 200-draw warm-up.",
      execution: "The helper functions overlapCount, sonarTransitionProfile and sonarAnalogCore are extracted from the committed UI source and executed directly; canonical CSV and src/data.json modelDraws are checked for exact row-by-row equality.",
      multiple_testing: "Exploratory p-values are reported unadjusted and with a conservative Bonferroni screen over 43 configurations (42 fixed-rule configurations plus this app engine); no confirmatory claim or automatic promotion."
    },
    baseline: {
      top5_mean_hits: 0.625,
      top10_mean_hits: 1.25,
      top20_mean_hits: 2.5,
      top20_5of5_probability: BASE_TOP20,
      top10_5of5_probability: BASE_TOP10,
      top5_5of5_probability: BASE_TOP5
    },
    splits,
    overall: summarize(records),
    current_frozen_forecast: currentRow ? {
      target_date: currentRow.target_date,
      frozen_at: currentRow.frozen_at,
      history_cutoff: currentRow.history_cutoff,
      top20_ranked: parseNumbers(currentRow.top20),
      top10_ranked: parseNumbers(currentRow.top10),
      top5_ranked: parseNumbers(currentRow.top5),
      visible_ticket_sorted: parseNumbers(currentRow.top5).slice().sort((a, b) => a - b),
      status: currentRow.status,
      exact_top20_matches_committed_ui: currentReconciliation?.exact_top20_matches_committed_ui ?? false,
      top5_set_matches_committed_ui: currentReconciliation?.top5_set_matches_committed_ui ?? false,
      freeze_created_this_run: shadow.created
    } : {
      target_date: null,
      status: "NO_VERIFIED_FREEZE",
      freeze_created_this_run: false
    },
    freeze_reconciliation: reconciliation,
    interpretation: {
      positive_signal: "The exact app scorer is evaluated on a strict past-only walk-forward; report any OOS excess as a descriptive signal only, not as evidence of predictive advantage.",
      limitation: "No adjusted statistical evidence authorizes promotion; Top10/Top5 cascade remains sparse and the model was selected after prior exploration.",
      multiple_testing: "All reported p-values are screening values. Bonferroni correction across 43 configurations is included, but this does not erase broader strategy-selection bias.",
      freeze_integrity: "Existing historical freezes are preserved unchanged. The prior 2026-10-25 APP freeze has a Top20 ranking that does not reproduce exactly under the committed UI source; it is not reconstructed or counted as an exact-engine prospective primary case.",
      caveat: "Lottery draws may be independent and uniform; historical patterns do not guarantee future predictive advantage."
    }
  };

  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2) + "\n", "utf8");
  console.log(JSON.stringify({
    status: report.status,
    data: report.data,
    overall: report.overall,
    splits: report.splits,
    current_frozen_forecast: report.current_frozen_forecast,
    freeze_reconciliation: {
      rows_checked: reconciliation.rows_checked,
      exact_top20_matches: reconciliation.exact_top20_matches,
      exact_top20_mismatches: reconciliation.exact_top20_mismatches,
      missing_freezes_reconstructed: reconciliation.missing_freezes_reconstructed
    }
  }, null, 2));
}

if (process.argv.includes("--no-freeze")) {
  const originalAppend = appendFreezeIfEligible;
  // Keep the shadow file read-only for syntax/diagnostic runs.
  appendFreezeIfEligible = function (draws, score, now) {
    const raw = fs.existsSync(SHADOW_PATH) ? fs.readFileSync(SHADOW_PATH, "utf8") : "";
    const parsed = raw.trim() ? parseSimpleCsv(raw) : { header: [], rows: [] };
    return { rows: parsed.rows, created: false, targetDate: localParts(now).date,
      latestDate: draws[draws.length - 1].d, schema: parsed.header };
  };
  main();
  appendFreezeIfEligible = originalAppend;
} else {
  main();
}
