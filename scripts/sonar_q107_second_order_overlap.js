#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "reports", "sequence_agent");
const CSV_PATH = path.join(ROOT, "data", "storico_daily.csv");
const APP_PATH = path.join(ROOT, "src", "data.json");
const PROTOCOL_PATH = path.join(OUT, "q107_second_order_overlap_protocol_2026-11-11.json");
const REPORT_PATH = path.join(OUT, "q107_second_order_overlap_report_2026-11-11.json");
const VALIDATION_PATH = path.join(OUT, "q107_second_order_overlap_validation_2026-11-11.json");
const LEDGER_PATH = path.join(OUT, "q107_second_order_overlap_target_ledger_2026-11-11.csv");
const CHECKPOINT_PATH = path.join(OUT, "q107_second_order_overlap_checkpoint_2026-11-11.md");
const MANIFEST_PATH = path.join(OUT, "q107_second_order_overlap_persistence_manifest_2026-11-11.json");

const PINNED_MAIN = "161273b72804c2b6e815e41f20b90dabfea4fdfa";
const PINNED_ARCHIVE_BLOB = "40f317e2d0067e061c46ab799d66f777a0e087c0";
const PINNED_PREFIX_BLOB = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const PINNED_APP_BLOB = "25c0b2316662664deff9e2157e60ec56cfa3a640";
const DRAW_COUNT = 3403;
const WARMUP_PAIRS = 300;
const FIRST_TARGET = 303;
const ALPHA = 200;
const BLOCK = 20;
const SIGN_REPS = 50000;
const BOOT_REPS = 10000;
const SEED = 20261111;
const Q0_NUM = [324632, 261800, 65450, 5950, 175, 1];
const Q0_DEN = 658008;
const Q0 = Q0_NUM.map(x => x / Q0_DEN);

function assert(ok, message) {
  if (!ok) throw new Error("Q107 BLOCKED: " + message);
}
function hash(s) {
  return gitBlobSha1(s);
}
function gitBlobSha1(s) {
  const bytes = Buffer.from(s, "utf8");
  return crypto.createHash("sha1").update(Buffer.from("blob " + bytes.length + "\0", "utf8")).update(bytes).digest("hex");
}
function gitBlob(pathSpec) {
  return execFileSync("git", ["rev-parse", "HEAD:" + pathSpec], { encoding: "utf8" }).trim();
}
function round(x) {
  return Number(x.toFixed(12));
}
function mean(xs) {
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
function quantile(sorted, q) {
  const p = (sorted.length - 1) * q;
  const lo = Math.floor(p), hi = Math.ceil(p);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (p - lo);
}
function rng(seed) {
  let x = (seed >>> 0) || 1;
  return () => {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    return (x >>> 0) / 4294967296;
  };
}
function stableJson(x) {
  return JSON.stringify(x, null, 2) + "\n";
}
function parseCsv(text) {
  const lines = text.split(/\r?\n/);
  while (lines.length && lines[lines.length - 1] === "") lines.pop();
  assert(lines[0] === "data,n1,n2,n3,n4,n5", "archive header mismatch");
  const rows = [];
  let prev = "";
  const seen = new Set();
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    assert(f.length === 6, "malformed CSV row " + (i + 1));
    const date = f[0];
    const n = f.slice(1).map(Number);
    assert(/^\d{4}-\d{2}-\d{2}$/.test(date), "invalid date " + date);
    assert(!seen.has(date) && (!prev || date > prev), "duplicate or unordered date " + date);
    assert(n.every(Number.isInteger) && n.every(v => v >= 1 && v <= 40), "number outside 1..40 at " + date);
    assert(n.length === 5 && new Set(n).size === 5 && n.every((v, j) => j === 0 || v > n[j - 1]), "invalid draw at " + date);
    rows.push({ d: date, n });
    seen.add(date);
    prev = date;
  }
  return { rows, lines };
}
function overlap(a, b) {
  let c = 0;
  for (const x of a) if (b.includes(x)) c++;
  return c;
}
function buildK(draws) {
  const k = Array(draws.length).fill(null);
  for (let i = 1; i < draws.length; i++) k[i] = overlap(draws[i - 1].n, draws[i].n);
  return k;
}
function forecastFromK(k, t) {
  const c1 = Array.from({ length: 6 }, () => Array(6).fill(0));
  const n1 = Array(6).fill(0);
  const c2 = Array.from({ length: 6 }, () => Array.from({ length: 6 }, () => Array(6).fill(0)));
  const n2 = Array.from({ length: 6 }, () => Array(6).fill(0));
  for (let j = 3; j < t; j++) {
    const a = k[j - 1], b = k[j - 2], y = k[j];
    assert(Number.isInteger(a) && a >= 0 && a <= 5 && Number.isInteger(b) && b >= 0 && b <= 5 && Number.isInteger(y) && y >= 0 && y <= 5, "invalid training overlap state at j=" + j);
    c1[a][y]++; n1[a]++;
    c2[a][b][y]++; n2[a][b]++;
  }
  const a = k[t - 1], b = k[t - 2];
  assert(Number.isInteger(a) && a >= 0 && a <= 5 && Number.isInteger(b) && b >= 0 && b <= 5, "invalid target lag state at t=" + t);
  const p1 = Q0.map((q, y) => (ALPHA * q + c1[a][y]) / (ALPHA + n1[a]));
  const p2 = Q0.map((_, y) => (ALPHA * p1[y] + c2[a][b][y]) / (ALPHA + n2[a][b]));
  return { p0: Q0.slice(), p1, p2, lag1: a, lag2: b, n1: n1[a], n2: n2[a][b], trainingPairs: t - 3 };
}
function brier(p, y) {
  let s = 0;
  for (let k = 0; k < 6; k++) {
    const e = p[k] - (k === y ? 1 : 0);
    s += e * e;
  }
  return s;
}
function logloss(p, y) {
  return -Math.log(p[y]);
}
function summarize(rows, start, end) {
  const x = rows.slice(start, end);
  const out = {};
  for (const model of ["m0", "m1", "m2"]) {
    out[model] = {
      brier: round(mean(x.map(r => r[model + "_brier"]))),
      logloss: round(mean(x.map(r => r[model + "_logloss"])))
    };
  }
  out.m1_vs_m0 = {
    brier_gain: round(out.m0.brier - out.m1.brier),
    logloss_gain: round(out.m0.logloss - out.m1.logloss)
  };
  out.m2_vs_m1 = {
    brier_gain: round(out.m1.brier - out.m2.brier),
    logloss_gain: round(out.m1.logloss - out.m2.logloss)
  };
  out.m2_vs_m0 = {
    brier_gain: round(out.m0.brier - out.m2.brier),
    logloss_gain: round(out.m0.logloss - out.m2.logloss)
  };
  const counts = Array(6).fill(0);
  for (const r of x) counts[r.actual_overlap]++;
  out.observed_overlap_counts = counts;
  out.observed_mean_overlap = round(mean(x.map(r => r.actual_overlap)));
  return out;
}
function blockSignFlip(values, blockLength, reps, seed) {
  const sums = [];
  for (let i = 0; i < values.length; i += blockLength) sums.push(values.slice(i, i + blockLength).reduce((a, b) => a + b, 0));
  const observed = mean(values);
  const random = rng(seed);
  let ge = 0;
  for (let r = 0; r < reps; r++) {
    let s = 0;
    for (const v of sums) s += (random() < 0.5 ? -1 : 1) * v;
    if (s / values.length >= observed) ge++;
  }
  const p = (ge + 1) / (reps + 1);
  return { observed_mean: round(observed), blocks: sums.length, replicates: reps, p_one_sided: round(p), monte_carlo_se: round(Math.sqrt(p * (1 - p) / (reps + 1))) };
}
function circularBlockBootstrap(values, blockLength, reps, seed) {
  const random = rng(seed);
  const n = values.length;
  const means = [];
  for (let r = 0; r < reps; r++) {
    let sum = 0, used = 0;
    while (used < n) {
      const start = Math.floor(random() * n);
      const take = Math.min(blockLength, n - used);
      for (let j = 0; j < take; j++) sum += values[(start + j) % n];
      used += take;
    }
    means.push(sum / n);
  }
  means.sort((a, b) => a - b);
  return { replicates: reps, block_length: blockLength, ci95: { lower: round(quantile(means, 0.025)), upper: round(quantile(means, 0.975)) } };
}
function holm(entries) {
  const sorted = entries.map((e, i) => ({ ...e, i })).sort((a, b) => a.p_raw - b.p_raw);
  let running = 0;
  const adjusted = Array(entries.length);
  for (let i = 0; i < sorted.length; i++) {
    running = Math.max(running, Math.min(1, (sorted.length - i) * sorted[i].p_raw));
    adjusted[sorted[i].i] = round(running);
  }
  return adjusted;
}
function makeInference(rows) {
  const n = rows.length;
  const definitions = [
    ["m2_vs_m1_brier", "m1_brier", "m2_brier", 101],
    ["m2_vs_m1_logloss", "m1_logloss", "m2_logloss", 202],
    ["m2_vs_m0_brier", "m0_brier", "m2_brier", 303],
    ["m2_vs_m0_logloss", "m0_logloss", "m2_logloss", 404]
  ];
  const endpoints = definitions.map(([name, base, model, seedOffset]) => {
    const gains = rows.map(r => r[base] - r[model]);
    const test = blockSignFlip(gains, BLOCK, SIGN_REPS, SEED + seedOffset);
    const ci = circularBlockBootstrap(gains, BLOCK, BOOT_REPS, SEED + seedOffset + 1000);
    return { name, n, ...test, bootstrap: ci };
  });
  const adj = holm(endpoints.map(e => ({ p_raw: e.p_one_sided })));
  endpoints.forEach((e, i) => e.p_holm_4 = adj[i]);
  return {
    method: "One-sided block sign-flip of contiguous block sums; circular moving-block bootstrap for 95% CI.",
    block_length: BLOCK,
    sign_flip_replicates: SIGN_REPS,
    bootstrap_replicates: BOOT_REPS,
    seed: SEED,
    holm_family_size: 4,
    endpoints
  };
}
function formatCsvValue(v) {
  if (typeof v === "number") return Number.isFinite(v) ? v.toFixed(12) : "";
  return String(v);
}
function buildLedger(rows) {
  const cols = ["target_index","target_date","cutoff_date","training_pairs","lag1_overlap","lag2_overlap","actual_overlap","lag1_support","lag2_pair_support",
    "m0_brier","m1_brier","m2_brier","m0_logloss","m1_logloss","m2_logloss",
    "m2_minus_m1_brier_gain","m2_minus_m1_logloss_gain","m2_minus_m0_brier_gain","m2_minus_m0_logloss_gain"];
  const lines = [cols.join(",")];
  for (const r of rows) {
    const values = [r.target_index,r.target_date,r.cutoff_date,r.training_pairs,r.lag1_overlap,r.lag2_overlap,r.actual_overlap,r.lag1_support,r.lag2_pair_support,
      r.m0_brier,r.m1_brier,r.m2_brier,r.m0_logloss,r.m1_logloss,r.m2_logloss,
      r.m2_minus_m1_brier_gain,r.m2_minus_m1_logloss_gain,r.m2_minus_m0_brier_gain,r.m2_minus_m0_logloss_gain];
    lines.push(values.map(formatCsvValue).join(","));
  }
  return lines.join("\\n") + "\\n";
}
function mutateDraw(draw, shift) {
  return { d: draw.d, n: draw.n.map(v => ((v - 1 + shift) % 40) + 1).sort((a, b) => a - b) };
}
function run() {
  const protocolText = fs.readFileSync(PROTOCOL_PATH, "utf8");
  const protocol = JSON.parse(protocolText);
  assert(protocol.experiment_id === "Q107" && protocol.status === "PREREGISTERED_BEFORE_SCORING", "protocol not preregistered");
  assert(protocol.source.main_commit === PINNED_MAIN, "pinned main commit mismatch");
  const rawCsv = fs.readFileSync(CSV_PATH, "utf8");
  const parsed = parseCsv(rawCsv);
  const allRows = parsed.rows;
  assert(allRows.length === DRAW_COUNT + 1, "expected 3,403 analysis rows plus exactly one excluded appended row; got " + allRows.length);
  const extra = allRows[DRAW_COUNT];
  assert(extra.d === "2026-11-10" && extra.n.join(",") === "1,7,11,22,25", "unexpected appended row; stop and re-audit archive governance");
  const newline = rawCsv.includes("\r\n") ? "\r\n" : "\n";
  const prefixText = [parsed.lines[0], ...parsed.lines.slice(1, DRAW_COUNT + 1)].join(newline) + newline;
  assert(gitBlobSha1(prefixText) === PINNED_PREFIX_BLOB, "3,403-row analysis prefix blob SHA-1 mismatch");
  assert(gitBlob("data/storico_daily.csv") === PINNED_ARCHIVE_BLOB, "current archive blob SHA mismatch");
  assert(gitBlob("src/data.json") === PINNED_APP_BLOB, "current app-data blob SHA mismatch");
  const draws = allRows.slice(0, DRAW_COUNT);
  const app = JSON.parse(fs.readFileSync(APP_PATH, "utf8"));
  assert(Array.isArray(app.modelDraws) && app.modelDraws.length === allRows.length, "app modelDraws length mismatch");
  assert(app.histN === allRows.length && app.lastDate === extra.d, "app archive metadata mismatch");
  for (let i = 0; i < allRows.length; i++) {
    const a = app.modelDraws[i], b = allRows[i];
    assert(a && a.d === b.d && Array.isArray(a.n) && a.n.join(",") === b.n.join(","), "app-data row mismatch at " + i);
  }
  assert(draws.length === DRAW_COUNT && draws[0].d === "2017-07-17" && draws[draws.length - 1].d === "2026-11-09", "analysis prefix date range mismatch");
  const k = buildK(draws);
  const targetCount = draws.length - FIRST_TARGET;
  assert(targetCount === 3100, "target count mismatch");
  const discoveryN = 1860, validationN = 620, blindN = 620;
  assert(discoveryN + validationN + blindN === targetCount, "split totals mismatch");
  const rows = [];
  let maxNormError = 0;
  let minProbability = 1;
  for (let t = FIRST_TARGET; t < draws.length; t++) {
    const f = forecastFromK(k, t);
    const y = k[t];
    const sums = [f.p0, f.p1, f.p2].map(p => p.reduce((a, b) => a + b, 0));
    for (const s of sums) maxNormError = Math.max(maxNormError, Math.abs(s - 1));
    for (const p of [f.p0, f.p1, f.p2]) for (const v of p) minProbability = Math.min(minProbability, v);
    assert(f.trainingPairs === t - 3 && f.trainingPairs >= WARMUP_PAIRS, "training pair cutoff mismatch at " + t);
    assert(draws[t - 1].d < draws[t].d, "cutoff is not strictly before target at " + t);
    rows.push({
      target_index:t,target_date:draws[t].d,cutoff_date:draws[t-1].d,
      training_pairs:f.trainingPairs,lag1_overlap:f.lag1,lag2_overlap:f.lag2,actual_overlap:y,
      lag1_support:f.n1,lag2_pair_support:f.n2,
      m0_brier:brier(f.p0,y),m1_brier:brier(f.p1,y),m2_brier:brier(f.p2,y),
      m0_logloss:logloss(f.p0,y),m1_logloss:logloss(f.p1,y),m2_logloss:logloss(f.p2,y),
      m2_minus_m1_brier_gain:brier(f.p1,y)-brier(f.p2,y),
      m2_minus_m1_logloss_gain:logloss(f.p1,y)-logloss(f.p2,y),
      m2_minus_m0_brier_gain:brier(f.p0,y)-brier(f.p2,y),
      m2_minus_m0_logloss_gain:logloss(f.p0,y)-logloss(f.p2,y),
      p0:f.p0,p1:f.p1,p2:f.p2
    });
  }
  const discovery = summarize(rows, 0, discoveryN);
  const validation = summarize(rows, discoveryN, discoveryN + validationN);
  const blind = summarize(rows, discoveryN + validationN, targetCount);
  const blindRows = rows.slice(discoveryN + validationN);
  const inference = makeInference(blindRows);
  const stateCounts = Array.from({ length: 6 }, () => Array(6).fill(0));
  for (const r of rows) stateCounts[r.lag1_overlap][r.lag2_overlap]++;
  const pairSupport = rows.map(r => r.lag2_pair_support).sort((a,b)=>a-b);
  const actualCounts = Array(6).fill(0);
  for (const r of rows) actualCounts[r.actual_overlap]++;
  const report = {
    experiment_id:"Q107",
    title:"Second-order overlap memory conditional on first-order state",
    decision:"NO_SECOND_ORDER_INCREMENTAL_LIFT_DEMONSTRATED",
    source:{
      pinned_main_commit:PINNED_MAIN,
      current_archive_blob_sha1:PINNED_ARCHIVE_BLOB,
      analysis_prefix_blob_sha1:PINNED_PREFIX_BLOB,
      app_data_blob_sha1:PINNED_APP_BLOB,
      analysis_draws:DRAW_COUNT,
      first_date:draws[0].d,
      last_date:draws[draws.length-1].d,
      excluded_appended_row:extra,
      excluded_reason:"Official VinciCasa archive and official bulletin page still list contest 314 as pending; the row is not used in any Q107 calculation."
    },
    hypothesis:"K[t-2] adds predictive information about K[t] conditional on K[t-1].",
    definition:{
      overlap:"K_t=|D_(t-1)∩D_t|",
      target:"K_t",
      lag1:"K_(t-1)",
      lag2:"K_(t-2)",
      exact_null_numerators:Q0_NUM,
      exact_null_denominator:Q0_DEN,
      exact_null_probabilities:Q0.map(round),
      expected_overlap:0.625
    },
    models:{
      alpha:ALPHA,
      M0:"Exact Hypergeometric(40,5,5) null.",
      M1:"First-order state shrinkage toward M0 with alpha=200.",
      M2:"Second-order pair-state shrinkage toward the corresponding M1 distribution with alpha=200.",
      parameter_selection:"None; no tuning on Validation or Blind OOS."
    },
    walk_forward:{
      warmup_transition_pairs:WARMUP_PAIRS,
      first_target_index:FIRST_TARGET,
      targets:targetCount,
      splits:{
        discovery:{targets:discoveryN,first_target:rows[0].target_date,last_target:rows[discoveryN-1].target_date},
        validation:{targets:validationN,first_target:rows[discoveryN].target_date,last_target:rows[discoveryN+validationN-1].target_date},
        historical_blind_oos:{targets:blindN,first_target:rows[discoveryN+validationN].target_date,last_target:rows[rows.length-1].target_date}
      },
      strict_prior_rule:"For each target draw index t, only draws[0..t-1] are read; training transition targets j=3..t-1, with exactly t-3 prior transition examples."
    },
    metrics:{
      discovery,validation,historical_blind_oos:blind,
      all_target_overlap_counts:actualCounts,
      state_pair_target_counts:stateCounts,
      lag2_pair_support:{min:pairSupport[0],median:pairSupport[Math.floor(pairSupport.length/2)],max:pairSupport[pairSupport.length-1]}
    },
    blind_inference:inference,
    interpretation:{
      primary:"M2 versus M1 tests incremental second-order information after conditioning on the first-order overlap state.",
      secondary:"M2 versus M0 tests whether the second-order model improves over the exact hypergeometric overlap null.",
      caveat:"The historical Blind OOS segment is not virgin: Q102 previously studied lag-1 overlap-state memory on the same archive. Q107 is exploratory and cannot establish prospective predictability."
    },
    integrity:{
      maximum_probability_normalization_error:round(maxNormError),
      minimum_forecast_probability:round(minProbability),
      exact_null_numerator_sum:Q0_NUM.reduce((a,b)=>a+b,0),
      exact_null_denominator:Q0_DEN
    }
  };
  const primary = inference.endpoints.filter(e => e.name.startsWith("m2_vs_m1"));
  const primaryPass = primary.every(e => e.observed_mean > 0 && e.p_holm_4 < 0.05);
  report.decision = primaryPass ? "SECOND_ORDER_INCREMENTAL_LIFT_CANDIDATE_PENDING_HUMAN_REVIEW" : "NO_SECOND_ORDER_INCREMENTAL_LIFT_DEMONSTRATED";

  const mutationCutoffs = [303, 410, 777, 1000, 1400, 1900, 2400, 2900, 3300];
  let mutationPass = true;
  for (const t of mutationCutoffs) {
    const original = forecastFromK(k, t);
    const mutatedDraws = draws.map((d, i) => i >= t ? mutateDraw(d, 7 + (i % 31)) : d);
    const mutatedK = buildK(mutatedDraws);
    const changed = forecastFromK(mutatedK, t);
    if (stableJson({p1:original.p1.map(round),p2:original.p2.map(round),a:original.lag1,b:original.lag2}) !== stableJson({p1:changed.p1.map(round),p2:changed.p2.map(round),a:changed.lag1,b:changed.lag2})) mutationPass = false;
  }
  const synthetic = [null,1,0,4,0,0,0,1,0,4,0,1,0];
  const syntheticForecast = forecastFromK(synthetic, 13);
  const syntheticSensitivity = Math.abs(syntheticForecast.p2[4] - syntheticForecast.p1[4]) > 1e-12;
  const noPair = forecastFromK([null,1,0], 3);
  const noPairEquality = stableJson(noPair.p1.map(round)) === stableJson(noPair.p2.map(round));
  const inferenceReplay = stableJson(makeInference(blindRows)) === stableJson(inference);
  const checks = [
    ["archive_schema_and_chronology",true,"all 3,404 rows are unique chronological valid 5-of-40 draws"],
    ["pinned_archive_and_app_blobs",gitBlob("data/storico_daily.csv")===PINNED_ARCHIVE_BLOB && gitBlob("src/data.json")===PINNED_APP_BLOB,"source blobs match pinned main commit"],
    ["analysis_prefix_blob",gitBlobSha1(prefixText)===PINNED_PREFIX_BLOB,"first 3,403 rows reproduce the pre-append archive blob; appended row excluded"],
    ["app_data_row_by_row",app.modelDraws.length===allRows.length,"all app modelDraws match the archive, including the separately excluded row"],
    ["exact_hypergeometric_null",Q0_NUM.reduce((a,b)=>a+b,0)===Q0_DEN && Math.abs(Q0.reduce((a,b)=>a+b,0)-1)<1e-14,"exact numerators sum to 658008"],
    ["walk_forward_count_and_splits",targetCount===3100 && discoveryN+validationN+blindN===3100,"3,100 targets split 1,860/620/620"],
    ["strict_prior_cutoffs",rows.length===3100 && rows.every(r=>r.cutoff_date<r.target_date && r.training_pairs===r.target_index-3),"all targets have strict prior cutoffs and exact training-pair counts"],
    ["forecast_probability_normalization",maxNormError<1e-12 && minProbability>0,"all M0/M1/M2 probabilities finite, positive and normalized"],
    ["future_mutation_invariance_9_cutoffs",mutationPass,"mutating target and all future draws leaves both prior-only forecasts unchanged at nine cutoffs"],
    ["synthetic_second_order_sensitivity",syntheticSensitivity,"a synthetic lag-2 state with distinct outcomes changes M2 relative to M1"],
    ["synthetic_no_pair_fallback",noPairEquality,"when no pair-state observations exist, M2 equals M1 exactly"],
    ["deterministic_inference_replay",inferenceReplay,"fixed-seed block sign-flip and bootstrap reproduce exactly"]
  ];
  const validation = {
    experiment_id:"Q107",
    status:checks.every(c=>c[1])?"PASS":"FAIL",
    checks_passed:checks.filter(c=>c[1]).length,
    checks_total:checks.length,
    checks:checks.map(([name,ok,detail])=>({name,status:ok?"PASS":"FAIL",detail})),
    replay:"--check regenerates report, validation, ledger, checkpoint and manifest and byte-compares every persisted file.",
    inference_constants:{alpha:ALPHA,block_length:BLOCK,block_sign_flip_replicates:SIGN_REPS,circular_block_bootstrap_replicates:BOOT_REPS,seed:SEED,holm_family_size:4}
  };
  assert(validation.status==="PASS","one or more Q107 integrity checks failed");
  const ledger = buildLedger(rows);
  const checkpoint = [
    "# Q107 — second-order overlap memory checkpoint (2026-11-11)","",
    "- Status: " + report.decision + ".",
    "- Preregistered before scoring; fixed alpha=200; no parameter selection.",
    "- Source main commit: " + PINNED_MAIN + ".",
    "- Analysis uses exactly 3,403 draws through 2026-11-09; the extra 2026-11-10 row present on main is explicitly excluded because the official archive/bulletin still show contest 314 pending.",
    "- Walk-forward: 3,100 targets; Discovery/Validation/historical Blind OOS = 1,860/620/620.",
    "- Primary comparison: second-order M2 versus first-order M1; secondary comparison M2 versus exact Hypergeometric(40,5,5) null.",
    "- Blind OOS selected no parameters; four preregistered endpoints corrected with Holm.",
    "- Validation: " + validation.checks_passed + "/" + validation.checks_total + " PASS.",
    "- Historical Blind OOS is not virgin because Q102 previously examined lag-1 overlap memory on the same archive.",
    "- No engine, freeze, Q60, H101 or H102 record changed.",
    "- Next action: wait for official publication of contest 314; append-only reconcile the existing pending freezes; continue Q60 without reconstructing missing freezes.",
    ""
  ].join("\n");
  const reportText = stableJson(report);
  const validationText = stableJson(validation);
  const ledgerText = ledger;
  const checkpointText = checkpoint;
  const protocolHash = hash(protocolText);
  const runnerText = fs.readFileSync(fileURLToPath(import.meta.url), "utf8");
  const manifest = {
    experiment_id:"Q107",
    source_blob_sha1:{main_commit:PINNED_MAIN,archive:PINNED_ARCHIVE_BLOB,analysis_prefix:PINNED_PREFIX_BLOB,app_data:PINNED_APP_BLOB},
    output_git_blob_sha1:{
      protocol:protocolHash,
      runner:hash(runnerText),
      report:hash(reportText),
      validation:hash(validationText),
      ledger:hash(ledgerText),
      checkpoint:hash(checkpointText)
    },
    ledger_rows:rows.length,
    validation_checks:validation.checks_total,
    validation_status:validation.status,
    deterministic_replay:"Fixed-seed outputs; --check compares exact bytes."
  };
  const manifestText = stableJson(manifest);
  const outputs = [
    [REPORT_PATH,reportText],[VALIDATION_PATH,validationText],[LEDGER_PATH,ledgerText],
    [CHECKPOINT_PATH,checkpointText],[MANIFEST_PATH,manifestText]
  ];
  const mode = process.argv[2];
  assert(mode==="--write" || mode==="--check","use --write or --check");
  if (mode==="--write") {
    fs.mkdirSync(OUT,{recursive:true});
    for (const [p,c] of outputs) fs.writeFileSync(p,c,"utf8");
    console.log("Q107_WRITE_PASS " + JSON.stringify({targets:rows.length,checks:validation.checks_passed,decision:report.decision,blind:blind.m2_vs_m1}));
  } else {
    for (const [p,c] of outputs) {
      assert(fs.existsSync(p),"missing persisted artifact " + path.basename(p));
      const existing=fs.readFileSync(p,"utf8");
      assert(existing===c,"persisted artifact differs on replay: " + path.basename(p));
    }
    console.log("Q107_REPLAY_PASS " + JSON.stringify({targets:rows.length,checks:validation.checks_passed,decision:report.decision,manifest:manifest.output_git_blob_sha1}));
  }
}
try { run(); } catch (error) { console.error(error.stack || error.message); process.exit(1); }
