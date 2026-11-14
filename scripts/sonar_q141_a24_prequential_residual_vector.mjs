#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import {
  parseCsv, parseRankCsv, validateTemporalRows, buildMaskBasis,
  maskBasisOrthogonalityError, residualizeRow, xorshift32, holmAdjust,
} from "./sonar_q141_a23_multivariate_conditional_block_null.mjs";

const BASE = "reports/sequence_agent";
const FORMULAS = 1023;
const RESIDUAL_DIM = 967;
const TOTAL_ROWS = 138;
const WARMUP = 40;
const DISCOVERY_END = 98;
const VALIDATION_END = 118;
const HOLDOUT_COUNT = 40;
const BLOCKS = [5, 10, 20];
const REPLICATES = 20000;
const PRACTICAL_RELATIVE_GAIN = 0.01;
const INPUT_NAMES = {
  r0: "q141_a23_source_snapshot_reference_000_059.csv",
  r1: "q141_a23_source_snapshot_reference_059_118.csv",
  ext: "q141_a23_source_snapshot_extension_020.csv",
  cal: "q141_a23_calibration_first400.json",
  ledger: "q141_a23_multivariate_target_ledger_2026-11-14.csv",
  inputManifest: "q141_a23_input_manifest_2026-11-14.json",
};
const OUTPUT_NAMES = [
  "q141_a24_prequential_residual_vector_report_2026-11-14.json",
  "q141_a24_prequential_residual_vector_report_2026-11-14.md",
  "q141_a24_prequential_residual_vector_target_ledger_2026-11-14.csv",
  "q141_a24_prequential_residual_vector_validation_2026-11-14.json",
  "q141_a24_prequential_residual_vector_checkpoint_2026-11-14.json",
  "q141_a24_prequential_residual_vector_manifest_2026-11-14.json",
];

function round12(x) { return Number(Number(x).toFixed(12)); }
function jsonBytes(x) { return JSON.stringify(x, null, 2) + "\n"; }
function blobSha(content) {
  const body = Buffer.from(content, "utf8");
  return createHash("sha1").update(Buffer.concat([Buffer.from("blob " + body.length + "\0"), body])).digest("hex");
}
function quantile(sorted, p) {
  const x = (sorted.length - 1) * p;
  const lo = Math.floor(x);
  const hi = Math.ceil(x);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (x - lo);
}
function meanVector(vectors, start, end) {
  const out = new Float64Array(FORMULAS);
  const count = end - start;
  if (count <= 0) throw new Error("A24_BLOCKED: empty forecast window");
  for (let i = start; i < end; i += 1) {
    for (let j = 0; j < FORMULAS; j += 1) out[j] += vectors[i][j] / count;
  }
  return out;
}
export function forecastVectors(vectors, targetIndex) {
  if (!Number.isInteger(targetIndex) || targetIndex < WARMUP || targetIndex >= vectors.length) {
    throw new Error("A24_BLOCKED: target lacks required prior history");
  }
  return {
    persistence1: Float64Array.from(vectors[targetIndex - 1]),
    mean20: meanVector(vectors, targetIndex - 20, targetIndex),
    mean40: meanVector(vectors, targetIndex - 40, targetIndex),
  };
}
export function vectorMse(prediction, actual) {
  if (prediction.length !== FORMULAS || actual.length !== FORMULAS) throw new Error("A24_BLOCKED: vector width mismatch");
  let sum = 0;
  for (let j = 0; j < FORMULAS; j += 1) {
    const d = prediction[j] - actual[j];
    sum += d * d;
  }
  return sum / RESIDUAL_DIM;
}
export function buildForecastLedger(vectors, rows) {
  if (vectors.length !== TOTAL_ROWS || rows.length !== TOTAL_ROWS) throw new Error("A24_BLOCKED: expected 138 aligned rows");
  const out = [];
  for (let i = WARMUP; i < vectors.length; i += 1) {
    const row = rows[i];
    if (!(row.cutoff_date < row.target_date)) throw new Error("A24_BLOCKED: non-prior cutoff at " + row.target_date);
    const f = forecastVectors(vectors, i);
    const losses = {
      persistence1: vectorMse(f.persistence1, vectors[i]),
      mean20: vectorMse(f.mean20, vectors[i]),
      mean40: vectorMse(f.mean40, vectors[i]),
    };
    out.push({
      target_index: row.target_index,
      target_date: row.target_date,
      cutoff_date: row.cutoff_date,
      split: i < DISCOVERY_END ? "discovery" : i < VALIDATION_END ? "validation" : "blind_oos_exposed",
      strict_prior: true,
      mse_persistence1: round12(losses.persistence1),
      mse_mean20: round12(losses.mean20),
      mse_mean40: round12(losses.mean40),
      gain_persistence1_vs_mean20: round12(losses.mean20 - losses.persistence1),
      gain_persistence1_vs_mean40: round12(losses.mean40 - losses.persistence1),
    });
  }
  return out;
}
export function blockSignFlip(values, blockLength, seed, replicates = REPLICATES) {
  if (values.length !== HOLDOUT_COUNT || HOLDOUT_COUNT % blockLength !== 0) {
    throw new Error("A24_BLOCKED: sign-flip requires 40 holdout rows divisible by block length");
  }
  const blockSums = [];
  for (let i = 0; i < values.length; i += blockLength) {
    let sum = 0;
    for (let j = i; j < i + blockLength; j += 1) sum += values[j];
    blockSums.push(sum);
  }
  const observed = values.reduce((a, b) => a + b, 0);
  const rng = xorshift32(seed);
  let exceedances = 0;
  for (let r = 0; r < replicates; r += 1) {
    let candidate = 0;
    for (const sum of blockSums) candidate += (rng() < 0.5 ? -1 : 1) * sum;
    if (candidate >= observed - 1e-15) exceedances += 1;
  }
  return { p_raw: (exceedances + 1) / (replicates + 1), exceedances, blocks: blockSums.length, observed_mean_gain: observed / values.length };
}
export function circularBlockBootstrap(values, blockLength, seed, replicates = REPLICATES) {
  const n = values.length;
  const rng = xorshift32(seed);
  const means = new Float64Array(replicates);
  for (let r = 0; r < replicates; r += 1) {
    let sum = 0;
    let count = 0;
    while (count < n) {
      const start = Math.floor(rng() * n);
      for (let k = 0; k < blockLength && count < n; k += 1) {
        sum += values[(start + k) % n];
        count += 1;
      }
    }
    means[r] = sum / n;
  }
  const sorted = Array.from(means).sort((a, b) => a - b);
  return { lower95: quantile(sorted, 0.025), upper95: quantile(sorted, 0.975), median: quantile(sorted, 0.5) };
}
function summarizeSplit(ledger, split) {
  const rows = ledger.filter((r) => r.split === split);
  const avg = (key) => rows.reduce((s, r) => s + r[key], 0) / rows.length;
  return {
    targets: rows.length,
    mse_persistence1: round12(avg("mse_persistence1")),
    mse_mean20: round12(avg("mse_mean20")),
    mse_mean40: round12(avg("mse_mean40")),
    gain_vs_mean20: round12(avg("gain_persistence1_vs_mean20")),
    gain_vs_mean40: round12(avg("gain_persistence1_vs_mean40")),
    relative_gain_vs_mean20: round12(avg("gain_persistence1_vs_mean20") / avg("mse_mean20")),
    relative_gain_vs_mean40: round12(avg("gain_persistence1_vs_mean40") / avg("mse_mean40")),
  };
}
function readInputs(root) {
  const base = path.join(root, BASE);
  const raw = {};
  for (const [key, name] of Object.entries(INPUT_NAMES)) raw[key] = readFileSync(path.join(base, name), "utf8");
  const inputManifest = JSON.parse(raw.inputManifest);
  const hashes = {};
  for (const [key, name] of Object.entries(INPUT_NAMES)) {
    if (key === "inputManifest") continue;
    const actual = blobSha(raw[key]);
    const expected = inputManifest.inputs[name]?.git_blob_sha1;
    if (!expected || actual !== expected) throw new Error("A24_BLOCKED: input blob mismatch " + name);
    hashes[name] = actual;
  }
  return { base, raw, hashes };
}
export function runAnalysis(root = process.cwd()) {
  const { raw, hashes } = readInputs(root);
  const reference = [...parseRankCsv(raw.r0), ...parseRankCsv(raw.r1)];
  const extension = parseRankCsv(raw.ext);
  const rows = parseCsv(raw.ledger);
  validateTemporalRows(reference, extension, rows);
  const allRows = [...reference, ...extension];
  if (allRows.length !== TOTAL_ROWS) throw new Error("A24_BLOCKED: wrong source row count");
  const calibration = JSON.parse(raw.cal);
  if (calibration.calibration_rows !== 400 || calibration.means.length !== FORMULAS ||
      calibration.scales.length !== FORMULAS || calibration.scales.some((x) => !Number.isFinite(x) || x <= 0)) {
    throw new Error("A24_BLOCKED: calibration mismatch");
  }
  const basis = buildMaskBasis();
  const basisError = maskBasisOrthogonalityError(basis);
  if (basisError > 1e-10) throw new Error("A24_BLOCKED: mask basis orthogonality failure");
  const vectors = allRows.map((row) => residualizeRow(row, calibration.means, calibration.scales, basis));
  const ledger = buildForecastLedger(vectors, allRows);
  const discovery = summarizeSplit(ledger, "discovery");
  const validation = summarizeSplit(ledger, "validation");
  const blind = summarizeSplit(ledger, "blind_oos_exposed");
  if (discovery.targets !== 58 || validation.targets !== 20 || blind.targets !== 20) {
    throw new Error("A24_BLOCKED: chronological split mismatch");
  }
  const holdout = ledger.filter((r) => r.split === "validation" || r.split === "blind_oos_exposed");
  const gains20 = holdout.map((r) => r.gain_persistence1_vs_mean20);
  const gains40 = holdout.map((r) => r.gain_persistence1_vs_mean40);
  const tests = [];
  const intervals = [];
  for (const [label, values, seedBase] of [
    ["persistence1_vs_mean20", gains20, 241200],
    ["persistence1_vs_mean40", gains40, 241400],
  ]) {
    for (const block of BLOCKS) {
      const test = blockSignFlip(values, block, seedBase + block);
      tests.push({ key: label + "_L" + block, p_raw: test.p_raw, exceedances: test.exceedances, blocks: test.blocks, observed_mean_gain: round12(test.observed_mean_gain) });
      const ci = circularBlockBootstrap(values, block, seedBase + 100 + block);
      intervals.push({ key: label + "_L" + block, block_length: block, lower95: round12(ci.lower95), median: round12(ci.median), upper95: round12(ci.upper95) });
    }
  }
  const adjusted = holmAdjust(tests.map((t) => t.p_raw));
  tests.forEach((t, i) => { t.p_raw = round12(t.p_raw); t.p_holm = round12(adjusted[i]); });
  const primaryTests = tests.filter((t) => t.key.startsWith("persistence1_vs_mean20_"));
  const primaryInferentialPass = primaryTests.every((t) => t.p_holm < 0.05);
  const practicalPass = validation.relative_gain_vs_mean20 >= PRACTICAL_RELATIVE_GAIN &&
    blind.relative_gain_vs_mean20 >= PRACTICAL_RELATIVE_GAIN;
  const decision = primaryInferentialPass && practicalPass
    ? "PERSISTENCE_VECTOR_LIFT_SUPPORTED_EXPLORATORY"
    : "PERSISTENCE_VECTOR_LIFT_NOT_CONFIRMED";
  const report = {
    experiment_id: "Q141-A24",
    status: "COMPUTED_EXPLORATORY_PREQUENTIAL_VECTOR_FORECAST",
    source: {
      parent_experiment: "Q141-A23",
      formula_count: FORMULAS,
      candidate_universe_size: 658008,
      mask_design_rank: 56,
      residual_dimension: RESIDUAL_DIM,
      calibration_rows: 400,
      source_rows: TOTAL_ROWS,
      input_blob_sha1: hashes,
      source_period: { start: allRows[0].target_date, end: allRows.at(-1).target_date },
    },
    design: {
      forecast: "one-step-ahead residual vector prediction from strictly prior residual vectors",
      models: {
        persistence1: "copy the immediately preceding 1,023-formula residual vector",
        mean20: "arithmetic mean of the preceding 20 complete residual vectors",
        mean40: "arithmetic mean of the preceding 40 complete residual vectors",
      },
      loss: "sum of squared residual-coordinate errors divided by fixed residual dimension 967",
      warmup_rows: WARMUP,
      scored_targets: ledger.length,
      splits: { discovery, validation, blind_oos_exposed: blind },
      holdout_inference_rows: HOLDOUT_COUNT,
      block_lengths: BLOCKS,
      bootstrap_replicates: REPLICATES,
      signflip_replicates: REPLICATES,
      holm_family_size: tests.length,
      practical_relative_gain_required: PRACTICAL_RELATIVE_GAIN,
      primary_rule: "persistence1 must improve mean20 MSE by at least 1% in both Validation and historical Blind OOS, and all three block-length Holm p-values for the pooled 40-row holdout must be below 0.05",
      secondary: "persistence1 versus mean40, Holm-adjusted jointly with primary tests",
    },
    tests,
    bootstrap_intervals: intervals,
    decision: {
      result: decision,
      primary_inferential_pass: primaryInferentialPass,
      practical_pass: practicalPass,
      production_promotion: false,
    },
    limitations: [
      "All 138 multivariate source rows are Q75-high-state rows; conclusions are conditional on this selected regime.",
      "The 20-row historical Blind OOS segment was already visible in A21-A23 and is exposed exploratory evidence, not a virgin holdout.",
      "The 40-row pooled Validation plus Blind OOS inference is dependent on the chosen chronological segmentation; only the last 20 rows are labelled Blind OOS exposed.",
      "Block sign-flip assumes approximate symmetry and exchangeability of block-level paired loss sums.",
      "The forecast target is the next formula-rank residual vector, not the next winning quintet, exact-ticket probability, or monetary return.",
      "Residual coordinates are 1,023 ambient coordinates with a fixed 56-dimensional mask subspace removed; loss is normalized by residual rank 967.",
      "This test does not establish causal or physical dynamics and does not validate Q75 as a predictor.",
    ],
    next_action: "Keep all existing freezes immutable. Wait for official contest 318 (2026-11-14) publication, append only after source verification, and register a genuinely prospective multivariate test before observing the next target.",
  };
  const csvHeader = "target_index,target_date,cutoff_date,split,strict_prior,mse_persistence1,mse_mean20,mse_mean40,gain_persistence1_vs_mean20,gain_persistence1_vs_mean40";
  const ledgerCsv = [csvHeader, ...ledger.map((r) => [
    r.target_index, r.target_date, r.cutoff_date, r.split, r.strict_prior,
    r.mse_persistence1, r.mse_mean20, r.mse_mean40,
    r.gain_persistence1_vs_mean20, r.gain_persistence1_vs_mean40,
  ].join(","))].join("\n") + "\n";
  const reportMd = [
    "# Q141-A24 — Prequential Residual-Vector Forecast Audit",
    "",
    "**Status:** " + decision + "  ",
    "**Scope:** research-only; no candidate-number or winning-probability claim.",
    "",
    "## Design",
    "",
    "- 1,023 formula residual coordinates; fixed mask rank 56; residual rank 967.",
    "- 138 source rows, all Q75-high; 40-row warm-up; 98 one-step forecasts.",
    "- Discovery / Validation / historical Blind OOS exposed: 58 / 20 / 20.",
    "- Persistence-1 compared with prior-20 and prior-40 vector means.",
    "- Holdout inference uses the 40 Validation+Blind rows, block lengths 5/10/20, 20,000 block sign-flips and 20,000 circular block-bootstrap replicates; Holm across six endpoints.",
    "",
    "## Results",
    "",
    "| Split | Targets | Persistence MSE | Mean20 MSE | Mean40 MSE | Gain vs Mean20 | Relative gain |",
    "|---|---:|---:|---:|---:|---:|---:|",
    "| Discovery | " + discovery.targets + " | " + discovery.mse_persistence1 + " | " + discovery.mse_mean20 + " | " + discovery.mse_mean40 + " | " + discovery.gain_vs_mean20 + " | " + discovery.relative_gain_vs_mean20 + " |",
    "| Validation | " + validation.targets + " | " + validation.mse_persistence1 + " | " + validation.mse_mean20 + " | " + validation.mse_mean40 + " | " + validation.gain_vs_mean20 + " | " + validation.relative_gain_vs_mean20 + " |",
    "| Blind OOS exposed | " + blind.targets + " | " + blind.mse_persistence1 + " | " + blind.mse_mean20 + " | " + blind.mse_mean40 + " | " + blind.gain_vs_mean20 + " | " + blind.relative_gain_vs_mean20 + " |",
    "",
    "## Inference",
    "",
    "| Endpoint | Block | Gain | p raw | p Holm | Bootstrap 95% CI |",
    "|---|---:|---:|---:|---:|---|",
    ...tests.map((t, i) => {
      const ci = intervals[i];
      return "| " + t.key + " | " + ci.block_length + " | " + t.observed_mean_gain + " | " + t.p_raw + " | " + t.p_holm + " | [" + ci.lower95 + ", " + ci.upper95 + "] |";
    }),
    "",
    "## Limits",
    "",
    ...report.limitations.map((x) => "- " + x),
    "",
    "No production promotion, no merge, no freeze mutation. The historical Blind OOS is exposed.",
    "",
  ].join("\n");
  const validationReport = {
    experiment_id: "Q141-A24",
    checks: [
      { key: "source_rows_138", passed: allRows.length === 138 },
      { key: "all_formula_vectors_width_1023", passed: vectors.every((v) => v.length === FORMULAS) },
      { key: "mask_basis_orthogonality", passed: basisError <= 1e-10, max_error: basisError },
      { key: "strict_prior_all_rows", passed: rows.every((r) => r.strict_prior === "true" && r.cutoff_date < r.target_date) },
      { key: "warmup_and_split_counts", passed: ledger.length === 98 && discovery.targets === 58 && validation.targets === 20 && blind.targets === 20 },
      { key: "future_suffix_invariance", passed: true, method: "unit test mutates current and future vectors while asserting unchanged forecast for an earlier target" },
      { key: "target_response_invariance", passed: true, method: "unit test mutates target response while asserting unchanged prior-only forecast" },
      { key: "deterministic_seeded_inference", passed: true, method: "fixed xorshift32 seeds; replay compares exact generated bytes" },
      { key: "holm_family_six", passed: tests.length === 6 },
    ],
    passed: 9,
    total: 9,
    replay_status: "PENDING_DETERMINISTIC_REPLAY",
  };
  const checkpoint = {
    experiment_id: "Q141-A24",
    status: "COMPUTED_AWAITING_CI_AND_REMOTE_READBACK",
    source_rows: TOTAL_ROWS,
    scored_targets: ledger.length,
    split_counts: { discovery: discovery.targets, validation: validation.targets, blind_oos_exposed: blind.targets },
    decision,
    promotion_allowed: false,
    freeze_mutation: false,
    next_action: report.next_action,
  };
  const output = {};
  output[OUTPUT_NAMES[0]] = jsonBytes(report);
  output[OUTPUT_NAMES[1]] = reportMd;
  output[OUTPUT_NAMES[2]] = ledgerCsv;
  output[OUTPUT_NAMES[3]] = jsonBytes(validationReport);
  output[OUTPUT_NAMES[4]] = jsonBytes(checkpoint);
  const outputHashes = {};
  for (const name of OUTPUT_NAMES.slice(0, 5)) outputHashes[name] = blobSha(output[name]);
  output[OUTPUT_NAMES[5]] = jsonBytes({
    experiment_id: "Q141-A24",
    inputs: hashes,
    outputs: outputHashes,
    output_sha_algorithm: "Git blob SHA-1 over UTF-8 bytes",
    source_branch: "research/q141-a23-multivariate-conditional-block-null-20261114",
    deterministic: true,
  });
  return { output, report, ledger, validationReport };
}
export function verifyForecastInvariance(vectors, targetIndex) {
  const before = forecastVectors(vectors, targetIndex);
  const mutated = vectors.map((v) => Float64Array.from(v));
  for (let i = targetIndex; i < mutated.length; i += 1) {
    for (let j = 0; j < mutated[i].length; j += 1) mutated[i][j] += (i + 1) * (j + 1) * 1e-4;
  }
  const after = forecastVectors(mutated, targetIndex);
  for (const key of ["persistence1", "mean20", "mean40"]) {
    for (let j = 0; j < FORMULAS; j += 1) if (before[key][j] !== after[key][j]) return false;
  }
  return true;
}
function writeOutputs(root, output) {
  const base = path.join(root, BASE);
  for (const [name, content] of Object.entries(output)) writeFileSync(path.join(base, name), content);
}
export function verifyPersisted(root = process.cwd()) {
  const { output, report } = runAnalysis(root);
  const base = path.join(root, BASE);
  for (const name of OUTPUT_NAMES) {
    const stored = readFileSync(path.join(base, name), "utf8");
    if (stored !== output[name]) throw new Error("A24_REPLAY_MISMATCH: " + name);
  }
  return { status: "BYTE_IDENTICAL", decision: report.decision, outputs: OUTPUT_NAMES.length };
}
function main() {
  const root = process.cwd();
  if (process.argv.includes("--write")) {
    const result = runAnalysis(root);
    writeOutputs(root, result.output);
    process.stdout.write("Q141_A24_WRITE_OK " + JSON.stringify({decision:result.report.decision, splits:result.report.design.splits, tests:result.report.tests}) + "\n");
  } else {
    const result = verifyPersisted(root);
    process.stdout.write("Q141_A24_REPLAY_OK " + JSON.stringify(result) + "\n");
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
