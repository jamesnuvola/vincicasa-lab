#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const FORMULAS = 1023;
const CANDIDATES = 658008;
const REF_COUNT = 118;
const EXT_COUNT = 20;
const DIM = 1023;
const RESIDUAL_DIM = 967;
const BLOCKS = [5, 10, 20];
const REPLICATES = 20000;

export function round12(value) {
  return Number(Number(value).toFixed(12));
}

export function parseCsv(raw) {
  const lines = raw.trimEnd().split(/\r?\n/);
  if (lines.length < 2) throw new Error("A23_BLOCKED: empty CSV");
  const header = lines[0].split(",");
  return lines.slice(1).filter(Boolean).map((line) => {
    const cells = line.split(",");
    if (cells.length !== header.length) throw new Error("A23_BLOCKED: CSV width mismatch");
    const row = {};
    for (let i = 0; i < header.length; i += 1) row[header[i]] = cells[i];
    return row;
  });
}

export function parseRankCsv(raw) {
  const lines = raw.trimEnd().split(/\r?\n/);
  const header = lines[0].split(",");
  if (header.length !== 1027 || header[4] !== "rank_mask_0001" || header[1026] !== "rank_mask_1023") {
    throw new Error("A23_BLOCKED: rank snapshot header mismatch");
  }
  return parseCsv(raw).map((row) => {
    const ranks = new Int32Array(FORMULAS);
    for (let j = 0; j < FORMULAS; j += 1) {
      const value = Number(row[header[j + 4]]);
      if (!Number.isInteger(value) || value < 1 || value > CANDIDATES) {
        throw new Error("A23_BLOCKED: invalid formula rank");
      }
      ranks[j] = value;
    }
    return {
      target_index: Number(row.target_index),
      target_date: row.target_date,
      cutoff_date: row.cutoff_date,
      actual_quintet: row.actual_quintet,
      ranks,
    };
  });
}

export function validateTemporalRows(reference, extension, targetLedger) {
  const all = [...reference, ...extension];
  if (reference.length !== REF_COUNT || extension.length !== EXT_COUNT || targetLedger.length !== REF_COUNT + EXT_COUNT) {
    throw new Error("A23_BLOCKED: source row count mismatch");
  }
  for (let i = 0; i < all.length; i += 1) {
    const row = all[i];
    const meta = targetLedger[i];
    const expectedIndex = 3269 + i;
    if (row.target_index !== expectedIndex || Number(meta.target_index) !== expectedIndex) {
      throw new Error("A23_BLOCKED: target index discontinuity at row " + i);
    }
    if (row.target_date !== meta.target_date || row.cutoff_date !== meta.cutoff_date ||
        row.actual_quintet !== meta.actual_quintet || meta.strict_prior !== "true" ||
        !(row.cutoff_date < row.target_date)) {
      throw new Error("A23_BLOCKED: date/outcome/strict-prior mismatch at row " + i);
    }
    const nums = row.actual_quintet.split(/\s+/).map(Number);
    if (nums.length !== 5 || nums.some((v, j) => !Number.isInteger(v) || v < 1 || v > 40 || (j > 0 && nums[j - 1] >= v))) {
      throw new Error("A23_BLOCKED: invalid target quintet at row " + i);
    }
    if (i < REF_COUNT && meta.state !== "high") throw new Error("A23_BLOCKED: reference row is not high-state");
    if (i >= REF_COUNT && meta.state !== "high") throw new Error("A23_BLOCKED: extension row is not high-state");
  }
  return true;
}

export function buildMaskBasis() {
  const basis = [];
  for (let col = 0; col < 56; col += 1) {
    const vector = new Float64Array(FORMULAS);
    for (let mask = 1; mask <= FORMULAS; mask += 1) {
      let value = 0;
      if (col === 0) {
        value = 1;
      } else if (col <= 10) {
        value = (mask >> (col - 1)) & 1;
      } else {
        const pairIndex = col - 11;
        let pairCounter = 0;
        let left = 0;
        let right = 0;
        outer: for (let i = 0; i < 10; i += 1) {
          for (let j = i + 1; j < 10; j += 1) {
            if (pairCounter === pairIndex) {
              left = i;
              right = j;
              break outer;
            }
            pairCounter += 1;
          }
        }
        value = ((mask >> left) & 1) * ((mask >> right) & 1);
      }
      vector[mask - 1] = value;
    }
    for (let pass = 0; pass < 2; pass += 1) {
      for (const q of basis) {
        let dot = 0;
        for (let j = 0; j < FORMULAS; j += 1) dot += vector[j] * q[j];
        for (let j = 0; j < FORMULAS; j += 1) vector[j] -= dot * q[j];
      }
    }
    let norm2 = 0;
    for (let j = 0; j < FORMULAS; j += 1) norm2 += vector[j] * vector[j];
    const norm = Math.sqrt(norm2);
    if (norm < 1e-10) throw new Error("A23_BLOCKED: mask design rank deficient");
    for (let j = 0; j < FORMULAS; j += 1) vector[j] /= norm;
    basis.push(vector);
  }
  return basis;
}

export function maskBasisOrthogonalityError(basis) {
  let maximum = 0;
  for (let i = 0; i < basis.length; i += 1) {
    for (let j = 0; j < basis.length; j += 1) {
      let dot = 0;
      for (let k = 0; k < FORMULAS; k += 1) dot += basis[i][k] * basis[j][k];
      maximum = Math.max(maximum, Math.abs(dot - (i === j ? 1 : 0)));
    }
  }
  return maximum;
}

export function residualizeRow(row, means, scales, basis) {
  const sorted = Array.from(row.ranks, (v) => (v - 1) / (CANDIDATES - 1)).sort((a, b) => a - b);
  const median = sorted[511];
  const residual = new Float64Array(FORMULAS);
  for (let j = 0; j < FORMULAS; j += 1) {
    residual[j] = ((row.ranks[j] - 1) / (CANDIDATES - 1) - median - means[j]) / scales[j];
  }
  for (const q of basis) {
    let dot = 0;
    for (let j = 0; j < FORMULAS; j += 1) dot += residual[j] * q[j];
    for (let j = 0; j < FORMULAS; j += 1) residual[j] -= dot * q[j];
  }
  return residual;
}

export function pairwiseDistances(vectors) {
  const n = vectors.length;
  const distances = new Float64Array(n * n);
  const squared = new Float64Array(n * n);
  for (let i = 0; i < n; i += 1) {
    for (let j = 0; j < i; j += 1) {
      let sum = 0;
      for (let k = 0; k < FORMULAS; k += 1) {
        const delta = vectors[i][k] - vectors[j][k];
        sum += delta * delta;
      }
      squared[i * n + j] = sum;
      squared[j * n + i] = sum;
      distances[i * n + j] = Math.sqrt(sum);
      distances[j * n + i] = distances[i * n + j];
    }
  }
  return { distances, squared };
}

function aggregate(sample, matrix, nTotal, referenceCount) {
  let cross = 0;
  let withinSample = 0;
  let withinReference = 0;
  for (const i of sample) {
    for (let j = 0; j < referenceCount; j += 1) cross += matrix[i * nTotal + j];
  }
  for (const i of sample) {
    for (const j of sample) withinSample += matrix[i * nTotal + j];
  }
  for (let i = 0; i < referenceCount; i += 1) {
    for (let j = 0; j < referenceCount; j += 1) withinReference += matrix[i * nTotal + j];
  }
  return { cross, withinSample, withinReference };
}

export function computeEnergyDistance(matrix, sample, referenceCount, sampleCount, nTotal) {
  const a = aggregate(sample, matrix, nTotal, referenceCount);
  return 2 * a.cross / (sampleCount * referenceCount)
    - a.withinSample / (sampleCount * sampleCount)
    - a.withinReference / (referenceCount * referenceCount);
}

export function computeMeanShiftRms(squaredMatrix, sample, referenceCount, sampleCount, nTotal, dimension) {
  const a = aggregate(sample, squaredMatrix, nTotal, referenceCount);
  const meanDifferenceSquared = a.cross / (sampleCount * referenceCount)
    - 0.5 * a.withinSample / (sampleCount * sampleCount)
    - 0.5 * a.withinReference / (referenceCount * referenceCount);
  return Math.sqrt(Math.max(0, meanDifferenceSquared / dimension));
}

export function xorshift32(seed) {
  let state = seed >>> 0;
  return function next() {
    state ^= state << 13;
    state ^= state >>> 17;
    state ^= state << 5;
    return (state >>> 0) / 4294967296;
  };
}

export function movingBlockSample(rng, referenceCount, sampleCount, blockLength) {
  const sample = [];
  while (sample.length < sampleCount) {
    const start = Math.floor(rng() * referenceCount);
    for (let k = 0; k < blockLength && sample.length < sampleCount; k += 1) {
      sample.push((start + k) % referenceCount);
    }
  }
  return sample;
}

export function holmAdjust(pValues) {
  const ordered = pValues.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p || a.i - b.i);
  const adjusted = new Array(pValues.length);
  let running = 0;
  for (let i = 0; i < ordered.length; i += 1) {
    running = Math.max(running, Math.min(1, (ordered.length - i) * ordered[i].p));
    adjusted[ordered[i].i] = running;
  }
  return adjusted;
}

function readInputFiles(root) {
  const base = path.join(root, "reports/sequence_agent");
  const read = (name) => readFileSync(path.join(base, name), "utf8");
  const names = {
    r0: "q141_a23_source_snapshot_reference_000_059.csv",
    r1: "q141_a23_source_snapshot_reference_059_118.csv",
    ext: "q141_a23_source_snapshot_extension_020.csv",
    cal: "q141_a23_calibration_first400.json",
    ledger: "q141_a23_multivariate_target_ledger_2026-11-14.csv",
    lineage: "q141_a23_source_lineage_2026-11-14.json",
    inputManifest: "q141_a23_input_manifest_2026-11-14.json",
    a22: "q141_a22_conditional_response_shift_2026-11-14_report.json",
    a21: "q141_a21_q7_source_extension_2026-11-14_report.json",
  };
  const raw = Object.fromEntries(Object.entries(names).map(([key, name]) => [key, read(name)]));
  const manifest = JSON.parse(raw.inputManifest);
  for (const [key, name] of Object.entries({
    r0: names.r0, r1: names.r1, ext: names.ext, cal: names.cal, ledger: names.ledger, lineage: names.lineage,
  })) {
    const content = raw[key];
    const body = Buffer.from(content, "utf8");
    const gitSha = createHash("sha1").update(Buffer.concat([Buffer.from("blob " + body.length + "\0"), body])).digest("hex");
    const expected = manifest.inputs[name]?.git_blob_sha1;
    if (!expected || gitSha !== expected) throw new Error("A23_BLOCKED: input Git blob mismatch for " + name);
  }
  return { raw, names, base };
}

export function runAnalysis(root = process.cwd()) {
  const { raw } = readInputFiles(root);
  const reference = [
    ...parseRankCsv(raw.r0),
    ...parseRankCsv(raw.r1),
  ];
  const extension = parseRankCsv(raw.ext);
  const targetLedger = parseCsv(raw.ledger);
  validateTemporalRows(reference, extension, targetLedger);

  const calibration = JSON.parse(raw.cal);
  if (calibration.means.length !== FORMULAS || calibration.scales.length !== FORMULAS ||
      calibration.means.some((x) => !Number.isFinite(x)) ||
      calibration.scales.some((x) => !Number.isFinite(x) || x <= 0) ||
      calibration.calibration_rows !== 400) {
    throw new Error("A23_BLOCKED: calibration shape or values invalid");
  }

  const lineage = JSON.parse(raw.lineage);
  const inputManifest = JSON.parse(raw.inputManifest);
  const a22 = JSON.parse(raw.a22);
  const a21 = JSON.parse(raw.a21);
  const basis = buildMaskBasis();
  const qError = maskBasisOrthogonalityError(basis);
  if (qError > 1e-10) throw new Error("A23_BLOCKED: mask basis orthogonality failure");
  const vectors = [...reference, ...extension].map((row) => residualizeRow(row, calibration.means, calibration.scales, basis));
  const pairwise = pairwiseDistances(vectors);
  const observedSample = Array.from({ length: EXT_COUNT }, (_, i) => REF_COUNT + i);
  const observed = {
    energy_distance: computeEnergyDistance(pairwise.distances, observedSample, REF_COUNT, EXT_COUNT, vectors.length),
    mean_shift_rms: computeMeanShiftRms(pairwise.squared, observedSample, REF_COUNT, EXT_COUNT, vectors.length, RESIDUAL_DIM),
  };

  const tests = [];
  const nullSummaries = [];
  for (const blockLength of BLOCKS) {
    const rng = xorshift32(14123000 + blockLength);
    const energyNull = new Float64Array(REPLICATES);
    const meanNull = new Float64Array(REPLICATES);
    let energyExceedances = 0;
    let meanExceedances = 0;
    for (let b = 0; b < REPLICATES; b += 1) {
      const sample = movingBlockSample(rng, REF_COUNT, EXT_COUNT, blockLength);
      const energy = computeEnergyDistance(pairwise.distances, sample, REF_COUNT, EXT_COUNT, vectors.length);
      const meanShift = computeMeanShiftRms(pairwise.squared, sample, REF_COUNT, EXT_COUNT, vectors.length, RESIDUAL_DIM);
      energyNull[b] = energy;
      meanNull[b] = meanShift;
      if (energy >= observed.energy_distance) energyExceedances += 1;
      if (meanShift >= observed.mean_shift_rms) meanExceedances += 1;
    }
    const sortedEnergy = Array.from(energyNull).sort((a, b) => a - b);
    const sortedMean = Array.from(meanNull).sort((a, b) => a - b);
    const energyP = (energyExceedances + 1) / (REPLICATES + 1);
    const meanP = (meanExceedances + 1) / (REPLICATES + 1);
    tests.push(
      { key: "energy_L" + blockLength, p_raw: energyP },
      { key: "mean_shift_L" + blockLength, p_raw: meanP },
    );
    const medianEnergy = sortedEnergy[Math.floor((REPLICATES - 1) * 0.5)];
    nullSummaries.push({
      block_length: blockLength,
      replicates: REPLICATES,
      energy_null_mean: energyNull.reduce((a, b) => a + b, 0) / REPLICATES,
      energy_null_median: medianEnergy,
      energy_null_q95: sortedEnergy[Math.floor((REPLICATES - 1) * 0.95)],
      energy_exceedances: energyExceedances,
      energy_p_raw: energyP,
      energy_ratio_to_null_median: observed.energy_distance / medianEnergy,
      mean_shift_null_mean: meanNull.reduce((a, b) => a + b, 0) / REPLICATES,
      mean_shift_null_median: sortedMean[Math.floor((REPLICATES - 1) * 0.5)],
      mean_shift_null_q95: sortedMean[Math.floor((REPLICATES - 1) * 0.95)],
      mean_shift_exceedances: meanExceedances,
      mean_shift_p_raw: meanP,
    });
  }

  const adjusted = holmAdjust(tests.map((t) => t.p_raw));
  for (let i = 0; i < tests.length; i += 1) {
    tests[i].p_raw = round12(tests[i].p_raw);
    tests[i].p_holm = round12(adjusted[i]);
  }
  for (const summary of nullSummaries) {
    for (const key of [
      "energy_null_mean", "energy_null_median", "energy_null_q95", "energy_p_raw",
      "energy_ratio_to_null_median", "mean_shift_null_mean", "mean_shift_null_median",
      "mean_shift_null_q95", "mean_shift_p_raw",
    ]) summary[key] = round12(summary[key]);
  }

  const energyAll = tests.filter((t) => t.key.startsWith("energy_")).every((t) => t.p_holm < 0.05);
  const meanCount = tests.filter((t) => t.key.startsWith("mean_shift_") && t.p_holm < 0.05).length;
  const ratioAll = nullSummaries.every((s) => s.energy_ratio_to_null_median >= 1.25);
  const split22 = a22.historical_split_metrics;
  const split21 = a21.historical_a20_reference.split_metrics;
  const registered = a21.historical_a20_reference.registered_tests;
  const holmFor = (key) => {
    const found = registered.find((item) => item.key === key);
    return found ? found.p_holm : null;
  };

  const report = {
    experiment_id: "Q141-A23",
    schema_version: "1.0",
    status: "COMPUTED_EXPLORATORY_MULTIVARIATE_CONDITIONAL_BLOCK_NULL",
    source: {
      q7_branch: lineage.q7_branch,
      q7_commit: lineage.q7_commit,
      upstream_blobs: lineage.source_blobs,
      snapshot_inputs: inputManifest.inputs,
    },
    design: {
      formula_count: FORMULAS,
      candidate_universe_size: CANDIDATES,
      mask_design_rank: 56,
      residual_dimension: RESIDUAL_DIM,
      calibration_rows: 400,
      reference_rows: REF_COUNT,
      extension_rows: EXT_COUNT,
      reference_start: reference[0].target_date,
      reference_end: reference[reference.length - 1].target_date,
      extension_start: extension[0].target_date,
      extension_end: extension[extension.length - 1].target_date,
      strict_prior_all_rows: true,
      bootstrap_replicates_per_block: REPLICATES,
      block_lengths: BLOCKS,
      holm_family_size: 6,
      holm_alpha: 0.05,
      primary: "V-statistic energy distance on full mask-lattice residual vectors",
      secondary: "RMS norm of difference between multivariate mean vectors",
      null: "circular moving-block bootstrap of complete reference formula-rank vectors",
    },
    observed: {
      energy_distance: round12(observed.energy_distance),
      mean_shift_rms: round12(observed.mean_shift_rms),
    },
    null_summaries: nullSummaries,
    tests,
    decision: {
      multivariate_shift_confirmed: energyAll && meanCount >= 2 && ratioAll,
      energy_all_blocks_holm_below_005: energyAll,
      mean_shift_significant_blocks: meanCount,
      energy_ratio_all_blocks_at_least_1_25: ratioAll,
      production_promotion: false,
    },
    historical_context: {
      discovery: {
        targets: split22.discovery.targets,
        mse_gain_vs_mean400: split22.discovery.mean_q75_mse_gain_vs_mean400,
        mse_gain_vs_a19_ols: split21.discovery.mse_gain_vs_a19_ols,
      },
      validation: {
        targets: split22.validation.targets,
        mse_gain_vs_mean400: split22.validation.mean_q75_mse_gain_vs_mean400,
        mse_gain_vs_a19_ols: split21.validation.mse_gain_vs_a19_ols,
      },
      blind_oos: {
        targets: split22.blind_oos.targets,
        mse_gain_vs_mean400: split22.blind_oos.mean_q75_mse_gain_vs_mean400,
        mse_gain_vs_a19_ols: split21.blind_oos.mse_gain_vs_a19_ols,
        p_holm_vs_a19_ols: holmFor("blind_oos_mse_gain_vs_a19_ols"),
      },
      note: "Inherited unchanged from A20/A21/A22; not recomputed by A23.",
    },
    scalar_context: {
      terminal_high_run_mean_capture: a22.conditional_capture_response.terminal_high_run_mean_capture,
      extension_mean_capture: a22.conditional_capture_response.extension_mean_capture,
      extension_minus_terminal_run_capture: a22.conditional_capture_response.extension_minus_terminal_run_capture,
      q75_mse_gain_vs_mean400: a22.extension_forecast_errors.mean_q75_mse_gain_vs_mean400,
    },
    limitations: [
      "A21 outcomes were visible before A23 protocol; retrospective exploratory audit, not virgin prospective evidence.",
      "Only 20 extension targets; inference conditional on the 118-row preceding high-state reference.",
      "Moving-block null preserves complete formula vectors and local temporal dependence, but assumes the preceding high-state run is a reasonable stationary continuation null.",
      "Mask residualization and first-400 scaler are inherited fixed transformations; no predictive accuracy or winning probability is tested.",
      "Historical Discovery/Validation/Blind OOS scores are inherited, not re-estimated on the full multivariate rank matrix.",
    ],
    next_action: "Keep the 2026-11-14 A21 freeze immutable. Do not retune Q75. Extend the prospective source after the official 2026-11-14 result is verified; then repeat the pre-registered monitor on a new target without changing the A23 null or endpoints.",
  };

  const nullCsv = [
    "block_length,endpoint,observed,null_mean,null_median,null_q95,exceedances,p_raw,p_holm,ratio_to_null_median",
    ...nullSummaries.map((s) => [
      s.block_length, "energy_distance", report.observed.energy_distance, s.energy_null_mean,
      s.energy_null_median, s.energy_null_q95, s.energy_exceedances, s.energy_p_raw,
      tests.find((t) => t.key === "energy_L" + s.block_length).p_holm, s.energy_ratio_to_null_median,
    ].join(",")),
    ...nullSummaries.map((s) => [
      s.block_length, "mean_shift_rms", report.observed.mean_shift_rms, s.mean_shift_null_mean,
      s.mean_shift_null_median, s.mean_shift_null_q95, s.mean_shift_exceedances, s.mean_shift_p_raw,
      tests.find((t) => t.key === "mean_shift_L" + s.block_length).p_holm, "",
    ].join(",")),
  ].join("\n") + "\n";

  const observedAggregate = aggregate(observedSample, pairwise.distances, vectors.length, REF_COUNT);
  const firstResidualNorm = Math.sqrt(vectors[0].reduce((sum, value) => sum + value * value, 0));
  const lastResidualNorm = Math.sqrt(vectors[vectors.length - 1].reduce((sum, value) => sum + value * value, 0));
  const debug = {
    qError,
    firstResidualNorm,
    lastResidualNorm,
    cross: observedAggregate.cross,
    withinSample: observedAggregate.withinSample,
    withinReference: observedAggregate.withinReference,
    energyFromSums: 2 * observedAggregate.cross / (EXT_COUNT * REF_COUNT)
      - observedAggregate.withinSample / (EXT_COUNT * EXT_COUNT)
      - observedAggregate.withinReference / (REF_COUNT * REF_COUNT),
  };
  return { report, nullCsv, qError, debug };
}

function assertClose(actual, expected, label, tolerance = 1e-10) {
  if (!Number.isFinite(Number(actual)) || Math.abs(Number(actual) - Number(expected)) > tolerance) {
    throw new Error("A23_REPLAY_MISMATCH: " + label + " actual=" + actual + " expected=" + expected);
  }
}

export function verifyPersisted(root = process.cwd()) {
  const result = runAnalysis(root);
  process.stdout.write("Q141_A23_DEBUG " + JSON.stringify(result.debug) + "\n");
  process.stdout.write("Q141_A23_RECOMPUTED " + JSON.stringify({observed: result.report.observed, null_summaries: result.report.null_summaries, tests: result.report.tests, decision: result.report.decision}) + "\n");
  const base = path.join(root, "reports/sequence_agent");
  const expected = JSON.parse(readFileSync(path.join(base, "q141_a23_multivariate_conditional_block_null_report_2026-11-14.json"), "utf8"));
  const expectedCsv = readFileSync(path.join(base, "q141_a23_multivariate_conditional_block_null_summary_2026-11-14.csv"), "utf8");
  assertClose(result.report.observed.energy_distance, expected.observed.energy_distance, "observed energy");
  assertClose(result.report.observed.mean_shift_rms, expected.observed.mean_shift_rms, "observed mean shift");
  if (result.report.tests.length !== expected.tests.length || result.report.null_summaries.length !== expected.null_summaries.length) {
    throw new Error("A23_REPLAY_MISMATCH: test/summary count");
  }
  for (let i = 0; i < result.report.tests.length; i += 1) {
    if (result.report.tests[i].key !== expected.tests[i].key) throw new Error("A23_REPLAY_MISMATCH: test key");
    assertClose(result.report.tests[i].p_raw, expected.tests[i].p_raw, "p_raw " + result.report.tests[i].key);
    assertClose(result.report.tests[i].p_holm, expected.tests[i].p_holm, "p_holm " + result.report.tests[i].key);
  }
  for (let i = 0; i < result.report.null_summaries.length; i += 1) {
    const actual = result.report.null_summaries[i];
    const stored = expected.null_summaries[i];
    for (const key of Object.keys(actual)) {
      if (typeof actual[key] === "number") assertClose(actual[key], stored[key], key + " block " + actual.block_length);
    }
  }
  if (result.nullCsv !== expectedCsv) throw new Error("A23_REPLAY_MISMATCH: null summary CSV bytes");
  if (JSON.stringify(result.report.decision) !== JSON.stringify(expected.decision)) {
    throw new Error("A23_REPLAY_MISMATCH: decision");
  }
  return {
    status: "BYTE_IDENTICAL_NUMERIC_REPLAY",
    observed: result.report.observed,
    test_count: result.report.tests.length,
    null_summary_rows: 6,
    mask_basis_orthogonality_max: result.qError,
  };
}

function main() {
  const verify = process.argv.includes("--verify");
  if (verify) {
    const result = verifyPersisted(process.cwd());
    process.stdout.write("Q141_A23_REPLAY_OK " + JSON.stringify(result) + "\n");
    return;
  }
  const result = runAnalysis(process.cwd());
  const base = path.join(process.cwd(), "reports/sequence_agent");
  writeFileSync(path.join(base, "q141_a23_multivariate_conditional_block_null_report_2026-11-14.json"), JSON.stringify(result.report, null, 2) + "\n");
  writeFileSync(path.join(base, "q141_a23_multivariate_conditional_block_null_summary_2026-11-14.csv"), result.nullCsv);
  process.stdout.write("Q141_A23_ANALYSIS_COMPLETE " + JSON.stringify(result.report.decision) + "\n");
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
