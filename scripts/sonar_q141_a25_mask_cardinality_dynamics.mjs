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
const EXPECTED_INPUT_MANIFEST_SHA1 = "6822b91f0081d3af45f29334688dd3fea3075b9d";
const EXPECTED_A24_LEDGER_SHA1 = "615e67424bb52beae5fbafbea7e936a9d1ecb685";
const EXPECTED_A24_REPORT_SHA1 = "1d3fee61bd0af6036bfb8e050d144bd417e79f98";
const INPUT_NAMES = {
  r0: "q141_a23_source_snapshot_reference_000_059.csv",
  r1: "q141_a23_source_snapshot_reference_059_118.csv",
  ext: "q141_a23_source_snapshot_extension_020.csv",
  cal: "q141_a23_calibration_first400.json",
  ledger: "q141_a23_multivariate_target_ledger_2026-11-14.csv",
  lineage: "q141_a23_source_lineage_2026-11-14.json",
  inputManifest: "q141_a23_input_manifest_2026-11-14.json",
  parentLedger: "q141_a24_prequential_residual_vector_target_ledger_2026-11-14.csv",
  parentReport: "q141_a24_prequential_residual_vector_report_2026-11-14.json",
};
const OUTPUT_NAMES = [
  "q141_a25_mask_cardinality_dynamics_report_2026-11-14.json",
  "q141_a25_mask_cardinality_dynamics_report_2026-11-14.md",
  "q141_a25_mask_cardinality_dynamics_target_ledger_2026-11-14.csv",
  "q141_a25_mask_cardinality_dynamics_validation_2026-11-14.json",
  "q141_a25_mask_cardinality_dynamics_checkpoint_2026-11-14.json",
  "q141_a25_mask_cardinality_dynamics_manifest_2026-11-14.json",
];

export function round12(x) { return Number(Number(x).toFixed(12)); }
function jsonBytes(x) { return JSON.stringify(x, null, 2) + "\n"; }
function sha256(raw) { return createHash("sha256").update(raw).digest("hex"); }
function blobSha(raw) {
  const body = Buffer.isBuffer(raw) ? raw : Buffer.from(raw, "utf8");
  return createHash("sha1").update(Buffer.concat([Buffer.from("blob " + body.length + "\0"), body])).digest("hex");
}
function quantile(sorted, p) {
  const x = (sorted.length - 1) * p;
  const lo = Math.floor(x);
  const hi = Math.ceil(x);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (x - lo);
}
function popcount(value) {
  let n = 0;
  let x = value;
  while (x) { x &= x - 1; n += 1; }
  return n;
}
export function buildMaskStrata() {
  const groups = { low: [], central: [], high: [] };
  const cardinalityCounts = {};
  for (let mask = 1; mask <= FORMULAS; mask += 1) {
    const k = popcount(mask);
    cardinalityCounts[k] = (cardinalityCounts[k] || 0) + 1;
    const key = k <= 3 ? "low" : k <= 7 ? "central" : "high";
    groups[key].push(mask - 1);
  }
  return { groups, cardinalityCounts };
}
function meanVector(vectors, start, end) {
  const out = new Float64Array(FORMULAS);
  const count = end - start;
  if (count <= 0) throw new Error("A25_BLOCKED: empty prior window");
  for (let i = start; i < end; i += 1) {
    for (let j = 0; j < FORMULAS; j += 1) out[j] += vectors[i][j] / count;
  }
  return out;
}
export function forecastVectors(vectors, targetIndex) {
  if (!Number.isInteger(targetIndex) || targetIndex < WARMUP || targetIndex >= vectors.length) {
    throw new Error("A25_BLOCKED: target lacks required strict-prior history");
  }
  return {
    persistence1: Float64Array.from(vectors[targetIndex - 1]),
    mean20: meanVector(vectors, targetIndex - 20, targetIndex),
    mean40: meanVector(vectors, targetIndex - 40, targetIndex),
  };
}
export function forecastGroupVectors(vectors, targetIndex, groups = buildMaskStrata().groups) {
  const forecasts = forecastVectors(vectors, targetIndex);
  const out = {};
  for (const [key, indices] of Object.entries(groups)) {
    out[key] = {};
    for (const model of ["persistence1", "mean20", "mean40"]) {
      out[key][model] = Float64Array.from(indices, (j) => forecasts[model][j]);
    }
  }
  return out;
}
export function groupMse(prediction, actual, indices) {
  if (indices.length === 0) throw new Error("A25_BLOCKED: empty mask stratum");
  let sum = 0;
  for (const j of indices) {
    const d = prediction[j] - actual[j];
    sum += d * d;
  }
  return sum / indices.length;
}
export function reconstructOverallMse(groupMses, groups) {
  let sum = 0;
  for (const [key, indices] of Object.entries(groups)) sum += groupMses[key] * indices.length;
  return sum / RESIDUAL_DIM;
}
export function buildForecastLedger(vectors, rows, groups = buildMaskStrata().groups) {
  if (vectors.length !== TOTAL_ROWS || rows.length !== TOTAL_ROWS) throw new Error("A25_BLOCKED: expected 138 aligned vectors");
  const out = [];
  const parentReplay = [];
  for (let i = WARMUP; i < vectors.length; i += 1) {
    const row = rows[i];
    if (!(row.cutoff_date < row.target_date)) throw new Error("A25_BLOCKED: non-prior cutoff at " + row.target_date);
    const forecasts = forecastVectors(vectors, i);
    const split = i < DISCOVERY_END ? "discovery" : i < VALIDATION_END ? "validation" : "blind_oos_exposed";
    const groupMses = {};
    for (const [key, indices] of Object.entries(groups)) {
      const mseP = groupMse(forecasts.persistence1, vectors[i], indices);
      const mse20 = groupMse(forecasts.mean20, vectors[i], indices);
      const mse40 = groupMse(forecasts.mean40, vectors[i], indices);
      groupMses[key] = { mseP, mse20, mse40 };
      out.push({
        target_index: row.target_index,
        target_date: row.target_date,
        cutoff_date: row.cutoff_date,
        split,
        group: key,
        formula_count: indices.length,
        mse_persistence1: round12(mseP),
        mse_mean20: round12(mse20),
        mse_mean40: round12(mse40),
        gain_persistence1_vs_mean20: round12(mse20 - mseP),
        gain_persistence1_vs_mean40: round12(mse40 - mseP),
        relative_gain_vs_mean20: round12((mse20 - mseP) / mse20),
      });
    }
    const overall = {
      persistence1: reconstructOverallMse(Object.fromEntries(Object.entries(groupMses).map(([k, v]) => [k, v.mseP])), groups),
      mean20: reconstructOverallMse(Object.fromEntries(Object.entries(groupMses).map(([k, v]) => [k, v.mse20])), groups),
      mean40: reconstructOverallMse(Object.fromEntries(Object.entries(groupMses).map(([k, v]) => [k, v.mse40])), groups),
    };
    parentReplay.push({ target_index: row.target_index, target_date: row.target_date, cutoff_date: row.cutoff_date, split,
      mse_persistence1: overall.persistence1, mse_mean20: overall.mean20, mse_mean40: overall.mean40 });
  }
  return { ledger: out, parentReplay };
}
function summarizeSplit(ledger, split) {
  const rows = ledger.filter((r) => r.split === split);
  const groups = {};
  for (const key of ["low", "central", "high"]) {
    const part = rows.filter((r) => r.group === key);
    const avg = (field) => part.reduce((sum, r) => sum + r[field], 0) / part.length;
    groups[key] = {
      targets: part.length,
      formula_count: part[0].formula_count,
      mse_persistence1: round12(avg("mse_persistence1")),
      mse_mean20: round12(avg("mse_mean20")),
      mse_mean40: round12(avg("mse_mean40")),
      gain_vs_mean20: round12(avg("gain_persistence1_vs_mean20")),
      gain_vs_mean40: round12(avg("gain_persistence1_vs_mean40")),
      relative_gain_vs_mean20: round12(avg("gain_persistence1_vs_mean20") / avg("mse_mean20")),
    };
  }
  return { targets: rows.length / 3, groups };
}
export function blockSignFlip(values, blockLength, seed, replicates = REPLICATES) {
  if (values.length !== HOLDOUT_COUNT || HOLDOUT_COUNT % blockLength !== 0) {
    throw new Error("A25_BLOCKED: sign-flip requires 40 holdout rows divisible by block length");
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
  return { lower95: quantile(sorted, 0.025), median: quantile(sorted, 0.5), upper95: quantile(sorted, 0.975) };
}
function readInputs(root) {
  const base = path.join(root, BASE);
  const read = (name) => readFileSync(path.join(base, name), "utf8");
  const raw = Object.fromEntries(Object.entries(INPUT_NAMES).map(([key, name]) => [key, read(name)]));
  const inputManifest = JSON.parse(raw.inputManifest);
  if (blobSha(raw.inputManifest) !== EXPECTED_INPUT_MANIFEST_SHA1) throw new Error("A25_BLOCKED: A23 input manifest blob mismatch");
  const sourceBlobSha1 = {};
  for (const [key, name] of Object.entries(INPUT_NAMES)) {
    if (key === "inputManifest") continue;
    const actual = blobSha(raw[key]);
    const expected = key === "parentLedger" ? EXPECTED_A24_LEDGER_SHA1
      : key === "parentReport" ? EXPECTED_A24_REPORT_SHA1
      : inputManifest.inputs[name]?.git_blob_sha1;
    if (!expected || actual !== expected) throw new Error("A25_BLOCKED: input Git blob mismatch " + name);
    sourceBlobSha1[name] = actual;
  }
  return { raw, sourceBlobSha1, base };
}
function buildCsv(rows) {
  const header = ["target_index", "target_date", "cutoff_date", "split", "group", "formula_count",
    "mse_persistence1", "mse_mean20", "mse_mean40", "gain_persistence1_vs_mean20",
    "gain_persistence1_vs_mean40", "relative_gain_vs_mean20"];
  return [header.join(","), ...rows.map((r) => header.map((k) => String(r[k])).join(","))].join("\n") + "\n";
}
function reportMarkdown(report) {
  const lines = [
    "# Q141-A25 — Mask-Cardinality Conditional Dynamics",
    "",
    "**Decision:** " + report.decision.result,
    "",
    "**Classification:** exploratory post-hoc decomposition of the exposed A24 panel; not confirmatory preregistration.",
    "",
    "## Design",
    "",
    "- 1,023 Q7 masks partitioned by cardinality: low 1–3 (175), central 4–7 (792), high 8–10 (56).",
    "- 138 Q75-high rows; 40 warm-up; 98 strict-prior forecasts.",
    "- Discovery / Validation / historical Blind OOS exposed: 58 / 20 / 20.",
    "- Persistence-1 compared with Mean-20; Mean-40 is descriptive secondary context.",
    "- 20,000 block-sign-flips and circular moving-block bootstrap replicates; block lengths 5, 10, 20; Holm family 12.",
    "",
    "## Split results",
    "",
    "| Split | Stratum | n formulas | Persistence MSE | Mean-20 MSE | Mean-40 MSE | Gain vs Mean-20 | Relative gain |",
    "|---|---|---:|---:|---:|---:|---:|---:|",
  ];
  for (const split of ["discovery", "validation", "blind_oos_exposed"]) {
    for (const key of ["low", "central", "high"]) {
      const x = report.split_results[split].groups[key];
      lines.push("| " + split + " | " + key + " | " + x.formula_count + " | " + x.mse_persistence1.toFixed(6) +
        " | " + x.mse_mean20.toFixed(6) + " | " + x.mse_mean40.toFixed(6) + " | " + x.gain_vs_mean20.toFixed(6) +
        " | " + (100 * x.relative_gain_vs_mean20).toFixed(2) + "% |");
    }
  }
  lines.push("", "## Inferential checks", "", "| Endpoint | Block | Mean gain | p raw | p Holm | Bootstrap 95% CI |", "|---|---:|---:|---:|---:|---|");
  for (const t of report.tests) {
    const ci = report.bootstrap_intervals.find((x) => x.key === t.key);
    lines.push("| " + t.key + " | " + t.block_length + " | " + t.observed_mean_gain.toFixed(6) + " | " +
      t.p_raw.toFixed(6) + " | " + t.p_holm.toFixed(6) + " | [" + ci.lower95.toFixed(6) + ", " + ci.upper95.toFixed(6) + "] |");
  }
  lines.push("", "## Parent A24 parity", "",
    "Maximum absolute per-target MSE difference after weighted reconstruction: **" +
      report.integrity.parent_a24_replay.max_abs_error.toExponential(3) + "** (required < 1e-9).",
    "",
    "## Interpretation and limits", "",
    ...report.limitations.map((x) => "- " + x),
    "",
    "## Next action", "",
    report.next_action,
    "",
    "No production promotion, merge, archive mutation, Q60 update or freeze change."
  );
  return lines.join("\n") + "\n";
}
export function runAnalysis(root = process.cwd()) {
  const { raw, sourceBlobSha1 } = readInputs(root);
  const reference = [...parseRankCsv(raw.r0), ...parseRankCsv(raw.r1)];
  const extension = parseRankCsv(raw.ext);
  const sourceLedger = parseCsv(raw.ledger);
  validateTemporalRows(reference, extension, sourceLedger);
  const rows = [...reference, ...extension];
  if (rows.length !== TOTAL_ROWS) throw new Error("A25_BLOCKED: source row count mismatch");
  const calibration = JSON.parse(raw.cal);
  if (calibration.calibration_rows !== 400 || calibration.means.length !== FORMULAS ||
      calibration.scales.length !== FORMULAS || calibration.scales.some((x) => !Number.isFinite(x) || x <= 0)) {
    throw new Error("A25_BLOCKED: calibration shape or values invalid");
  }
  const parentLedger = parseCsv(raw.parentLedger);
  const parentReport = JSON.parse(raw.parentReport);
  if (parentLedger.length !== 98 || parentReport.experiment_id !== "Q141-A24" ||
      parentReport.design?.scored_targets !== 98 || parentReport.source?.source_rows !== TOTAL_ROWS) {
    throw new Error("A25_BLOCKED: A24 parent dimensions mismatch");
  }
  const basis = buildMaskBasis();
  const basisError = maskBasisOrthogonalityError(basis);
  if (basisError > 1e-10) throw new Error("A25_BLOCKED: mask basis orthogonality failure");
  const vectors = rows.map((row) => residualizeRow(row, calibration.means, calibration.scales, basis));
  const { groups, cardinalityCounts } = buildMaskStrata();
  const groupCounts = Object.fromEntries(Object.entries(groups).map(([k, v]) => [k, v.length]));
  if (JSON.stringify(groupCounts) !== JSON.stringify({ low: 175, central: 792, high: 56 }) ||
      Object.values(groupCounts).reduce((a, b) => a + b, 0) !== FORMULAS) {
    throw new Error("A25_BLOCKED: mask cardinality partition mismatch");
  }
  const built = buildForecastLedger(vectors, rows, groups);
  const ledger = built.ledger;
  if (ledger.length !== 98 * 3) throw new Error("A25_BLOCKED: group ledger row count mismatch");
  let maxReplayError = 0;
  for (let i = 0; i < built.parentReplay.length; i += 1) {
    const got = built.parentReplay[i];
    const expected = parentLedger[i];
    if (got.target_index !== Number(expected.target_index) || got.target_date !== expected.target_date ||
        got.cutoff_date !== expected.cutoff_date || got.split !== expected.split) {
      throw new Error("A25_BLOCKED: parent A24 ledger alignment mismatch at " + i);
    }
    for (const key of ["persistence1", "mean20", "mean40"]) {
      const field = key === "persistence1" ? "mse_persistence1" : "mse_" + key;
      maxReplayError = Math.max(maxReplayError, Math.abs(got[field] - Number(expected[field])));
    }
  }
  if (maxReplayError >= 1e-9) throw new Error("A25_BLOCKED: weighted A24 replay mismatch " + maxReplayError);
  const splitResults = {
    discovery: summarizeSplit(ledger, "discovery"),
    validation: summarizeSplit(ledger, "validation"),
    blind_oos_exposed: summarizeSplit(ledger, "blind_oos_exposed"),
  };
  for (const [split, expected] of [["discovery", 58], ["validation", 20], ["blind_oos_exposed", 20]]) {
    if (splitResults[split].targets !== expected) throw new Error("A25_BLOCKED: split count mismatch " + split);
  }
  const holdout = ledger.filter((r) => r.split === "validation" || r.split === "blind_oos_exposed");
  const series = {};
  for (const key of ["low", "central", "high"]) series[key] = holdout.filter((r) => r.group === key).map((r) => r.gain_persistence1_vs_mean20);
  const contrast = [];
  for (let i = 0; i < HOLDOUT_COUNT; i += 1) contrast.push(series.high[i] - series.low[i]);
  series.high_minus_low = contrast;
  const tests = [];
  const intervals = [];
  let endpointIndex = 0;
  for (const key of ["low", "central", "high", "high_minus_low"]) {
    for (const blockLength of BLOCKS) {
      const values = series[key];
      const seedBase = 250000 + endpointIndex * 101;
      const test = blockSignFlip(values, blockLength, seedBase + blockLength);
      const ci = circularBlockBootstrap(values, blockLength, seedBase + 100 + blockLength);
      const testKey = key + "_L" + blockLength;
      tests.push({ key: testKey, block_length: blockLength, p_raw: round12(test.p_raw),
        exceedances: test.exceedances, blocks: test.blocks, observed_mean_gain: round12(test.observed_mean_gain) });
      intervals.push({ key: testKey, block_length: blockLength, lower95: round12(ci.lower95),
        median: round12(ci.median), upper95: round12(ci.upper95) });
      endpointIndex += 1;
    }
  }
  const adjusted = holmAdjust(tests.map((t) => t.p_raw));
  tests.forEach((t, i) => { t.p_holm = round12(adjusted[i]); });
  const highValidation = splitResults.validation.groups.high;
  const highBlind = splitResults.blind_oos_exposed.groups.high;
  const highTests = tests.filter((t) => t.key.startsWith("high_L"));
  const contrastTests = tests.filter((t) => t.key.startsWith("high_minus_low_L"));
  const highIntervals = intervals.filter((t) => t.key.startsWith("high_L"));
  const contrastIntervals = intervals.filter((t) => t.key.startsWith("high_minus_low_L"));
  const practicalPass = highValidation.relative_gain_vs_mean20 >= PRACTICAL_RELATIVE_GAIN &&
    highBlind.relative_gain_vs_mean20 >= PRACTICAL_RELATIVE_GAIN;
  const inferentialPass = highTests.every((t) => t.p_holm < 0.05) &&
    contrastTests.every((t) => t.p_holm < 0.05) &&
    highIntervals.every((t) => t.lower95 > 0) &&
    contrastIntervals.every((t) => t.lower95 > 0);
  const accepted = practicalPass && inferentialPass;
  const validation = {
    experiment_id: "Q141-A25",
    status: "VALIDATION_COMPLETE",
    checks: {
      source_blob_hashes_verified: true,
      parent_a24_blob_hashes_verified: true,
      source_rows_138: rows.length === TOTAL_ROWS,
      strict_prior_all_rows: rows.every((r, i) => sourceLedger[i].strict_prior === "true" && r.cutoff_date < r.target_date),
      all_source_rows_q75_high: sourceLedger.every((r) => r.state === "high"),
      mask_strata_disjoint_complete: Object.values(groups).flat().length === FORMULAS &&
        new Set(Object.values(groups).flat()).size === FORMULAS,
      mask_strata_counts_exact: JSON.stringify(groupCounts) === JSON.stringify({ low: 175, central: 792, high: 56 }),
      mask_basis_orthogonality: basisError < 1e-10,
      parent_a24_replay_within_1e_9: maxReplayError < 1e-9,
      chronological_splits_exact: splitResults.discovery.targets === 58 &&
        splitResults.validation.targets === 20 && splitResults.blind_oos_exposed.targets === 20,
      inference_family_size_12: tests.length === 12,
      no_production_or_freeze_mutation: true,
    },
    parent_a24_replay: { max_abs_error: maxReplayError, tolerance: 1e-9, rows_compared: 98 },
    decision: accepted ? "HIGH_ORDER_PERSISTENCE_LIFT_SUPPORTED_EXPLORATORY" : "NO_MASK_CARDINALITY_PERSISTENCE_LIFT_DEMONSTRATED",
  };
  const report = {
    experiment_id: "Q141-A25",
    schema_version: "1.0",
    status: "COMPUTED_EXPLORATORY_POSTHOC_MASK_CARDINALITY_DYNAMICS",
    classification: "EXPLORATORY_POST_HOC_NOT_CONFIRMATORY",
    source: {
      parent_experiment: "Q141-A24",
      formula_count: FORMULAS,
      mask_design_rank: 56,
      residual_dimension: RESIDUAL_DIM,
      calibration_rows: 400,
      source_rows: TOTAL_ROWS,
      scored_targets: ledger.length / 3,
      source_period: { start: rows[0].target_date, end: rows.at(-1).target_date },
      input_git_blob_sha1: sourceBlobSha1,
    },
    mask_strata: {
      definition: "popcount(mask) 1-3 / 4-7 / 8-10",
      cardinality_counts: cardinalityCounts,
      groups: groupCounts,
    },
    design: {
      forecast: "strict-prior Persistence-1, Mean-20, Mean-40 over full residual vectors; losses summarized within fixed mask-cardinality strata",
      loss: "squared error summed within stratum and divided by stratum formula count",
      warmup_rows: WARMUP,
      scored_targets: 98,
      splits: { discovery: 58, validation: 20, blind_oos_exposed: 20 },
      inference_rows: HOLDOUT_COUNT,
      primary_comparator: "Mean-20",
      secondary_comparator: "Mean-40 (descriptive only)",
      practical_relative_gain_required: PRACTICAL_RELATIVE_GAIN,
      block_lengths: BLOCKS,
      signflip_replicates: REPLICATES,
      bootstrap_replicates: REPLICATES,
      holm_family_size: tests.length,
      hypothesis: "high-order mask persistence gains at least 1% relative MSE in both holdouts and exceeds low-order persistence gain",
    },
    split_results: splitResults,
    tests,
    bootstrap_intervals: intervals,
    integrity: {
      parent_a24_replay: { max_abs_error: maxReplayError, tolerance: 1e-9, rows_compared: 98 },
      mask_basis_orthogonality_error: basisError,
      all_rows_q75_high_state: true,
      all_cutoffs_strict_prior: true,
    },
    decision: {
      result: validation.decision,
      accepted,
      high_order_practical_pass: practicalPass,
      high_order_inferential_and_contrast_pass: inferentialPass,
      production_promotion: false,
    },
    limitations: [
      "This is a post-hoc decomposition because the A24 panel and outcomes were already exposed.",
      "All 138 source rows are Q75-high-state; no inference is made about low-state periods.",
      "The 40-row pooled Validation plus exposed Blind OOS panel is small and temporally dependent.",
      "Mask cardinality is a combinatorial complexity stratum, not a semantic AST family or a set of independent formula observations.",
      "The final 20-target historical Blind OOS was visible in A21-A24 and is not virgin confirmation.",
      "The endpoint is formula-rank residual-vector MSE, not winning-number accuracy, exact-ticket probability, or monetary return.",
      "Holm correction covers the 12 registered A25 endpoints only, not the full Q00-Q141 research family.",
    ],
    next_action: "Stop adding persistence variants if no stratum passes. Continue the common-source typed-AST evaluator with identical strict-prior cutoffs and separate per-number and quintet endpoints; keep prospective freezes append-only.",
  };
  const ledgerCsv = buildCsv(ledger);
  const reportMd = reportMarkdown(report);
  const validationJson = jsonBytes(validation);
  const checkpoint = {
    schema_version: "1.0",
    task_id: "Q141-A25",
    status: "COMPUTED_PENDING_REMOTE_READBACK",
    decision: report.decision.result,
    source_rows: TOTAL_ROWS,
    scored_targets: 98,
    split_counts: { discovery: 58, validation: 20, blind_oos_exposed: 20 },
    mask_strata: groupCounts,
    parent_a24_replay_max_abs_error: maxReplayError,
    report_sha256: sha256(reportMd),
    ledger_sha256: sha256(ledgerCsv),
    validation_sha256: sha256(validationJson),
    next_action: report.next_action,
  };
  const checkpointJson = jsonBytes(checkpoint);
  const outputContents = {
    [OUTPUT_NAMES[0]]: jsonBytes(report),
    [OUTPUT_NAMES[1]]: reportMd,
    [OUTPUT_NAMES[2]]: ledgerCsv,
    [OUTPUT_NAMES[3]]: validationJson,
    [OUTPUT_NAMES[4]]: checkpointJson,
  };
  const manifest = {
    experiment_id: "Q141-A25",
    schema_version: "1.0",
    branch: "research/q141-a25-mask-cardinality-dynamics-20261114",
    inputs: Object.fromEntries(Object.entries(sourceBlobSha1).map(([name, git_blob_sha1]) => [name, { git_blob_sha1 }])),
    outputs: Object.fromEntries(Object.entries(outputContents).map(([name, content]) => [name, {
      git_blob_sha1: blobSha(content), sha256: sha256(content), bytes_utf8: Buffer.byteLength(content, "utf8"),
    }])),
    verification_policy: "Workflow commits generated outputs, then reads each path from origin branch and compares Git blob SHA-1; a separate receipt records REMOTE_GIT_READBACK_VERIFIED.",
  };
  outputContents[OUTPUT_NAMES[5]] = jsonBytes(manifest);
  return { outputContents, report, validation, manifest };
}
export function verifyPriorOnly(vectors, targetIndex, groups = buildMaskStrata().groups) {
  const before = forecastGroupVectors(vectors, targetIndex, groups);
  const mutated = vectors.map((v) => Float64Array.from(v));
  for (let i = targetIndex; i < mutated.length; i += 1) mutated[i].fill(999 + i);
  const after = forecastGroupVectors(mutated, targetIndex, groups);
  for (const key of Object.keys(groups)) {
    for (const model of ["persistence1", "mean20", "mean40"]) {
      for (let j = 0; j < before[key][model].length; j += 1) {
        if (before[key][model][j] !== after[key][model][j]) return false;
      }
    }
  }
  return true;
}
function writeOutputs(result, root) {
  const base = path.join(root, BASE);
  for (const [name, content] of Object.entries(result.outputContents)) writeFileSync(path.join(base, name), content, "utf8");
}
function verifyOutputs(result, root) {
  const base = path.join(root, BASE);
  for (const [name, expected] of Object.entries(result.outputContents)) {
    const actual = readFileSync(path.join(base, name), "utf8");
    if (actual !== expected) throw new Error("A25_BLOCKED: deterministic replay mismatch " + name);
  }
  return true;
}
function main() {
  const root = process.cwd();
  const result = runAnalysis(root);
  if (process.argv.includes("--write")) {
    writeOutputs(result, root);
    process.stdout.write("A25_WRITE_OK " + JSON.stringify({ files: Object.keys(result.outputContents), decision: result.report.decision.result }) + "\n");
  } else if (process.argv.includes("--verify")) {
    verifyOutputs(result, root);
    process.stdout.write("A25_REPLAY_BYTE_IDENTICAL " + JSON.stringify({ files: Object.keys(result.outputContents).length }) + "\n");
  } else {
    process.stdout.write(jsonBytes({ report: result.report, validation: result.validation }));
  }
}
if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) main();
