import fs from "node:fs";
import crypto from "node:crypto";

const ROOT = process.cwd();
const ARCHIVE_PATH = "data/storico_daily.csv";
const SOURCE_PATH = "src/VinciCasaLab.jsx";
const ACTIVE_PATH = "reports/sequence_agent/active_engine_walkforward.json";
const PROTOCOL_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_protocol_2026-11-10.json";
const REPORT_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_report_2026-11-10.json";
const VALIDATION_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_validation_2026-11-10.json";
const LEDGER_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_target_ledger_2026-11-10.csv";
const CHECKPOINT_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_checkpoint_2026-11-10.md";
const MANIFEST_PATH = "reports/sequence_agent/q103_score_magnitude_subset_likelihood_persistence_manifest_2026-11-10.json";

const EXPECTED_ARCHIVE_BLOB = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const EXPECTED_SCORER_BLOB = "7ccb9a2abfe452ec535913b70225bc109f692304";
const EXPECTED_ACTIVE_REPORT_BLOB = "ff07b6da4948bb89467067c2552d9b1f78bc9549";
const EXPECTED_PROTOCOL_BLOB = "34e0aca868daf9e1f65113c89a131c63c3ff3b01";

const WARMUP = 200;
const DISCOVERY_N = 1921;
const VALIDATION_N = 641;
const BLIND_N = 641;
const TEMPERATURES = [0.1, 0.2, 0.35, 0.5, 0.75, 1, 1.5, 2, 4];
const COMBINATIONS = 658008;
const LOG_COMBINATIONS = Math.log(COMBINATIONs_SAFE());
const BOOT_REPS = 10000;
const BLOCK_LENGTH = 20;
const BOOT_SEED = 20261110;

function COMBINATIONs_SAFE() { return 658008; }
function fail(message) { throw new Error("Q103: " + message); }
function gitBlobSha1(text) {
  const body = Buffer.from(text, "utf8");
  return crypto.createHash("sha1")
    .update(Buffer.from("blob " + body.length + "\0", "utf8"))
    .update(body)
    .digest("hex");
}
function sha256(text) {
  return crypto.createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}
function round12(value) {
  if (!Number.isFinite(value)) fail("non-finite numeric result");
  const out = Number(value.toFixed(12));
  return Object.is(out, -0) ? 0 : out;
}
function roundUp12(value) {
  if (!Number.isFinite(value) || value < 0) fail("invalid probability for conservative rounding");
  return Math.min(1, Math.ceil(value * 1e12) / 1e12);
}
function canonicalJson(value) { return JSON.stringify(value, null, 2) + "\n"; }

function parseArchive(csvText) {
  const lines = csvText.trim().split(/\r?\n/);
  if (lines[0] !== "data,n1,n2,n3,n4,n5") fail("unexpected archive header");
  const draws = [];
  for (let i = 1; i < lines.length; i++) {
    const fields = lines[i].split(",");
    if (fields.length !== 6) fail("malformed archive row " + i);
    const date = fields[0];
    const numbers = fields.slice(1).map(Number);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail("invalid date at row " + i);
    if (numbers.length !== 5 || numbers.some((x, j) =>
      !Number.isInteger(x) || x < 1 || x > 40 || (j > 0 && numbers[j - 1] >= x)
    )) fail("invalid sorted 5-of-40 draw at row " + i);
    if (i > 1 && !(draws[i - 2].d < date)) fail("dates not strictly increasing");
    draws.push({ d: date, n: numbers });
  }
  return draws;
}

function extractExactScorer(sourceText) {
  const start = sourceText.indexOf("function overlapCount");
  const end = sourceText.indexOf("const Card", start);
  if (start < 0 || end < 0) fail("could not isolate committed SONAR scorer functions");
  const code = sourceText.slice(start, end);
  return new Function(code + "\nreturn sonarAnalogCore;")();
}

function elementarySymmetric(weights, order = 5) {
  const dp = Array(order + 1).fill(0);
  dp[0] = 1;
  for (const weight of weights) {
    for (let k = order; k >= 1; k--) dp[k] += dp[k - 1] * weight;
  }
  return dp[order];
}

function bruteElementary(weights, order) {
  let total = 0;
  function visit(start, left, product) {
    if (left === 0) { total += product; return; }
    for (let i = start; i <= weights.length - left; i++) visit(i + 1, left - 1, product * weights[i]);
  }
  visit(0, order, 1);
  return total;
}

function buildLogWeights(scores, temperature) {
  const logWeights = Array(41).fill(0);
  if (temperature === null) return logWeights;
  const maxScore = Math.max(...scores.map(x => x.score));
  for (const item of scores) logWeights[item.n] = (item.score - maxScore) / temperature;
  return logWeights;
}

function subsetLikelihood(scores, actualNumbers, temperature) {
  const logWeights = buildLogWeights(scores, temperature);
  const weights = logWeights.slice(1).map(Math.exp);
  const z = elementarySymmetric(weights, 5);
  if (!(z > 0) || !Number.isFinite(z)) fail("invalid fifth elementary symmetric normalizer");
  const logZ = Math.log(z);
  const observedLogWeight = actualNumbers.reduce((sum, n) => sum + logWeights[n], 0);
  const sumLogWeights = logWeights.slice(1).reduce((a, b) => a + b, 0);
  const gain = LOG_COMBINATIONS + observedLogWeight - logZ;
  const expectedGainUnderUniform = LOG_COMBINATIONS + (5 / 40) * sumLogWeights - logZ;
  return {
    gain_raw: gain,
    expected_gain_raw: expectedGainUnderUniform,
    gain: round12(gain),
    expected_gain_under_uniform: round12(expectedGainUnderUniform),
    log_normalizer: round12(logZ),
    log_weights: logWeights
  };
}

function makeRng(seed) {
  let x = seed >>> 0;
  return function() {
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    return (x >>> 0) / 4294967296;
  };
}

function circularBlockBootstrapCI(values, reps, blockLength, seed) {
  const n = values.length;
  if (!n) fail("empty bootstrap input");
  const full = Math.floor(n / blockLength);
  const rem = n - full * blockLength;
  const fullWindows = new Float64Array(n);
  const remainderWindows = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    let a = 0, b = 0;
    for (let j = 0; j < blockLength; j++) a += values[(i + j) % n];
    for (let j = 0; j < rem; j++) b += values[(i + j) % n];
    fullWindows[i] = a;
    remainderWindows[i] = b;
  }
  const rng = makeRng(seed);
  const boot = new Array(reps);
  for (let r = 0; r < reps; r++) {
    let total = 0;
    for (let j = 0; j < full; j++) total += fullWindows[Math.floor(rng() * n)];
    if (rem) total += remainderWindows[Math.floor(rng() * n)];
    boot[r] = total / n;
  }
  boot.sort((a, b) => a - b);
  return [
    round12(boot[Math.floor(0.025 * (reps - 1))]),
    round12(boot[Math.floor(0.975 * (reps - 1))])
  ];
}

function holmAdjust(items) {
  const sorted = [...items].sort((a, b) => a.p_value - b.p_value);
  let running = 0;
  const adjusted = new Map();
  for (let i = 0; i < sorted.length; i++) {
    const value = Math.min(1, (sorted.length - i) * sorted[i].p_value);
    running = Math.max(running, value);
    adjusted.set(sorted[i].temperature, roundUp12(running));
  }
  return items.map(item => ({ ...item, p_holm: adjusted.get(item.temperature) }));
}

function splitName(targetOffset) {
  if (targetOffset < DISCOVERY_N) return "discovery";
  if (targetOffset < DISCOVERY_N + VALIDATION_N) return "validation";
  return "historical_blind_oos";
}

function splitSummary(rows) {
  const models = {};
  for (const temperature of TEMPERATURES) {
    const key = "gain_" + temperatureKey(temperature);
    const expectedKey = "expected_" + temperatureKey(temperature);
    const values = rows.map(r => r[key]);
    const expected = rows.map(r => r[expectedKey]);
    models[String(temperature)] = {
      mean_log_likelihood_gain: round12(values.reduce((a, b) => a + b, 0) / rows.length),
      cumulative_log_likelihood_gain: round12(values.reduce((a, b) => a + b, 0)),
      mean_conditional_null_expected_gain: round12(expected.reduce((a, b) => a + b, 0) / rows.length)
    };
  }
  models.uniform = {
    mean_log_likelihood_gain: 0,
    cumulative_log_likelihood_gain: 0,
    mean_conditional_null_expected_gain: 0
  };
  return {
    targets: rows.length,
    first_target: rows[0].target_date,
    last_target: rows[rows.length - 1].target_date,
    mean_top5_hits: round12(rows.reduce((a, r) => a + r.top5_hits, 0) / rows.length),
    mean_top20_hits: round12(rows.reduce((a, r) => a + r.top20_hits, 0) / rows.length),
    models
  };
}

function temperatureKey(temperature) {
  return String(temperature).replace(".", "_");
}

function validateScores(scores, targetIndex) {
  if (!Array.isArray(scores) || scores.length !== 40) fail("invalid score vector at target " + targetIndex);
  const seen = new Set();
  for (let i = 0; i < scores.length; i++) {
    const item = scores[i];
    if (!item || !Number.isInteger(item.n) || item.n < 1 || item.n > 40 || seen.has(item.n)) {
      fail("score vector is not a permutation of 1..40 at target " + targetIndex);
    }
    if (!Number.isFinite(item.score)) fail("non-finite score at target " + targetIndex);
    if (i > 0) {
      const prev = scores[i - 1];
      if (prev.score < item.score) fail("score vector is not descending at target " + targetIndex);
      if (prev.score === item.score && prev.n > item.n) fail("tie-break mismatch at target " + targetIndex);
    }
    seen.add(item.n);
  }
  if (seen.size !== 40) fail("incomplete score permutation at target " + targetIndex);
}

function directSubsetNormalization(logWeights) {
  const w = logWeights.slice(1).map(Math.exp);
  let sum = 0;
  for (let a = 0; a < 36; a++)
    for (let b = a + 1; b < 37; b++)
      for (let c = b + 1; c < 38; c++)
        for (let d = c + 1; d < 39; d++)
          for (let e = d + 1; e < 40; e++)
            sum += w[a] * w[b] * w[c] * w[d] * w[e];
  return sum;
}

function buildLedgerCsv(rows) {
  const cols = [
    "target_index","target_date","cutoff_date","max_training_outcome_index","split",
    "draw_numbers","top5_hits","top20_hits","score_min","score_max","score_range"
  ];
  for (const t of TEMPERATURES) {
    cols.push("gain_" + temperatureKey(t));
    cols.push("expected_" + temperatureKey(t));
  }
  const lines = [cols.join(",")];
  for (const r of rows) {
    const values = [
      r.target_index,r.target_date,r.cutoff_date,r.max_training_outcome_index,r.split,
      '"' + r.draw_numbers + '"',r.top5_hits,r.top20_hits,r.score_min,r.score_max,r.score_range
    ];
    for (const t of TEMPERATURES) {
      values.push(r["gain_" + temperatureKey(t)]);
      values.push(r["expected_" + temperatureKey(t)]);
    }
    lines.push(values.join(","));
  }
  return lines.join("\n") + "\n";
}

function main() {
  const mode = process.argv[2] || "--check";
  if (mode !== "--write" && mode !== "--check") fail("use --write or --check");

  const archiveText = fs.readFileSync(ARCHIVE_PATH, "utf8");
  const sourceText = fs.readFileSync(SOURCE_PATH, "utf8");
  const activeText = fs.readFileSync(ACTIVE_PATH, "utf8");
  const protocolText = fs.readFileSync(PROTOCOL_PATH, "utf8");
  const scriptText = fs.readFileSync("scripts/sonar_q103_score_magnitude_subset_likelihood.js", "utf8");

  const archiveBlob = gitBlobSha1(archiveText);
  const scorerBlob = gitBlobSha1(sourceText);
  const activeBlob = gitBlobSha1(activeText);
  const protocolBlob = gitBlobSha1(protocolText);
  const scriptBlob = gitBlobSha1(scriptText);
  if (archiveBlob !== EXPECTED_ARCHIVE_BLOB) fail("canonical archive blob changed: " + archiveBlob);
  if (scorerBlob !== EXPECTED_SCORER_BLOB) fail("active scorer source blob changed: " + scorerBlob);
  if (activeBlob !== EXPECTED_ACTIVE_REPORT_BLOB) fail("active engine report blob changed: " + activeBlob);
  if (protocolBlob !== EXPECTED_PROTOCOL_BLOB) fail("preregistered protocol blob changed: " + protocolBlob);

  const active = JSON.parse(activeText);
  if (active.source_git_blob_sha !== archiveBlob || active.implementation_source_blob_sha !== scorerBlob) {
    fail("active engine report does not reconcile to pinned archive/scorer");
  }
  const protocol = JSON.parse(protocolText);
  if (protocol.experiment_id !== "Q103" || protocol.status !== "PREREGISTERED_BEFORE_SCORING") {
    fail("protocol is not the expected preregistered Q103");
  }

  const draws = parseArchive(archiveText);
  if (draws.length !== 3403 || draws[0].d !== "2017-07-17" || draws[draws.length - 1].d !== "2026-11-09") {
    fail("archive row count/date range differs from preregistration");
  }
  const scorer = extractExactScorer(sourceText);

  const uniformZ = elementarySymmetric(Array(40).fill(1), 5);
  if (uniformZ !== COMBINATIONS) fail("uniform subset normalizer mismatch: " + uniformZ);
  const smallWeights = [0.7, 1.2, 0.4, 1.7, 0.9, 1.3, 0.8, 1.1];
  const smallDp = elementarySymmetric(smallWeights, 5);
  const smallBrute = bruteElementary(smallWeights, 5);
  if (Math.abs(smallDp - smallBrute) > 1e-10) fail("small-n elementary-symmetric exhaustive test failed");

  const targetRows = [];
  let representativeLogWeights = null;
  let representativeLogZ = null;
  for (let t = WARMUP; t < draws.length; t++) {
    const forecast = scorer(draws.slice(0, t));
    validateScores(forecast.scores, t);
    const actual = draws[t].n;
    const actualSet = new Set(actual);
    const top5 = forecast.scores.slice(0, 5).map(x => x.n);
    const top20 = forecast.scores.slice(0, 20).map(x => x.n);
    const top5Hits = top5.filter(n => actualSet.has(n)).length;
    const top20Hits = top20.filter(n => actualSet.has(n)).length;
    const rawScores = forecast.scores.map(x => x.score);
    const scoreMin = Math.min(...rawScores);
    const scoreMax = Math.max(...rawScores);
    const scoreRange = scoreMax - scoreMin;

    const targetOffset = t - WARMUP;
    const row = {
      target_index: t,
      target_date: draws[t].d,
      cutoff_date: draws[t - 1].d,
      max_training_outcome_index: t - 1,
      split: splitName(targetOffset),
      draw_numbers: actual.join(" "),
      top5_hits: top5Hits,
      top20_hits: top20Hits,
      score_min: round12(scoreMin),
      score_max: round12(scoreMax),
      score_range: round12(scoreRange)
    };

    for (const temperature of TEMPERATURES) {
      const result = subsetLikelihood(forecast.scores, actual, temperature);
      const key = temperatureKey(temperature);
      row["gain_" + key] = result.gain;
      row["expected_" + key] = result.expected_gain_under_uniform;
      row["raw_gain_" + key] = result.gain_raw;
      row["raw_expected_" + key] = result.expected_gain_raw;
      if (t === WARMUP && temperature === 0.5) {
        representativeLogWeights = result.log_weights;
        representativeLogZ = result.log_normalizer;
      }
    }
    targetRows.push(row);
  }

  if (targetRows.length !== 3203) fail("walk-forward target count mismatch: " + targetRows.length);
  const discovery = targetRows.filter(r => r.split === "discovery");
  const validationRows = targetRows.filter(r => r.split === "validation");
  const blind = targetRows.filter(r => r.split === "historical_blind_oos");
  if (discovery.length !== DISCOVERY_N || validationRows.length !== VALIDATION_N || blind.length !== BLIND_N) {
    fail("chronological split sizes mismatch");
  }

  const normalizationDirect = directSubsetNormalization(representativeLogWeights);
  const normalizationDp = Math.exp(representativeLogZ);
  const normalizationError = Math.abs(normalizationDirect / normalizationDp - 1);
  if (!(normalizationError < 1e-10)) fail("exhaustive subset normalization failed: " + normalizationError);

  const cutoffs = [200, 201, 641, 1921, 2121, 2762, 3000, 3200, 3402];
  let futureMutationComparisons = 0;
  for (const t of cutoffs) {
    const original = scorer(draws.slice(0, t)).scores;
    const mutated = draws.map((d, i) => {
      if (i < t) return { d: d.d, n: [...d.n] };
      const base = ((i * 7) % 36) + 1;
      const nums = [base, ((base + 5) % 40) + 1, ((base + 11) % 40) + 1, ((base + 19) % 40) + 1, ((base + 27) % 40) + 1].sort((a,b)=>a-b);
      return { d: d.d, n: [...new Set(nums)].sort((a,b)=>a-b).slice(0,5) };
    });
    const changedFuture = scorer(mutated.slice(0, t)).scores;
    if (JSON.stringify(original) !== JSON.stringify(changedFuture)) fail("future-mutation invariance failed at cutoff " + t);
    futureMutationComparisons++;
  }

  const replayCutoffs = [200, 201, 641, 1921, 2121, 2762, 3200, 3402];
  let deterministicReplayComparisons = 0;
  for (const t of replayCutoffs) {
    const prefix = draws.slice(0, t);
    const a = scorer(prefix).scores;
    const b = scorer(prefix).scores;
    if (JSON.stringify(a) !== JSON.stringify(b)) fail("deterministic scorer replay failed at cutoff " + t);
    deterministicReplayComparisons++;
  }

  const discoverySummary = splitSummary(discovery);
  const validationSummary = splitSummary(validationRows);
  const blindSummary = splitSummary(blind);

  const selectionCandidates = TEMPERATURES.map(t => {
    const key = "raw_gain_" + temperatureKey(t);
    const rawMean = validationRows.reduce((sum, row) => sum + row[key], 0) / validationRows.length;
    return {
      temperature: String(t),
      mean_gain: rawMean,
      numeric_temperature: t
    };
  });
  selectionCandidates.push({
    temperature: "uniform",
    mean_gain: 0,
    numeric_temperature: Infinity
  });
  selectionCandidates.sort((a, b) =>
    b.mean_gain - a.mean_gain || b.numeric_temperature - a.numeric_temperature
  );
  const selected = selectionCandidates[0];
  const selectedTemperature = selected.temperature === "uniform" ? null : Number(selected.temperature);

  const blindTests = TEMPERATURES.map(temperature => {
    const key = "raw_gain_" + temperatureKey(temperature);
    const values = blind.map(r => r[key]);
    const rawTotalLogLikelihoodGain = values.reduce((a, b) => a + b, 0);
    const totalLogLikelihoodGain = round12(rawTotalLogLikelihoodGain);
    const logEValue = rawTotalLogLikelihoodGain;
    const pValueRaw = logEValue > 0 ? Math.min(1, Math.exp(-logEValue)) : 1;
    const pValue = pValueRaw === 0 ? 1e-12 : roundUp12(pValueRaw);
    return {
      temperature: String(temperature),
      mean_log_likelihood_gain: round12(rawTotalLogLikelihoodGain / blind.length),
      cumulative_log_likelihood_gain: totalLogLikelihoodGain,
      log_e_value: round12(logEValue),
      e_process_p_value: pValue,
      p_bonferroni_43: roundUp12(Math.min(1, 43 * (pValueRaw === 0 ? 1e-12 : pValueRaw)))
    };
  });
  const blindTestsHolm = holmAdjust(blindTests.map(x => ({
    temperature: x.temperature,
    p_value: x.e_process_p_value
  })));
  const holmMap = new Map(blindTestsHolm.map(x => [x.temperature, x.p_holm]));
  for (const item of blindTests) item.p_holm = holmMap.get(item.temperature);

  const selectedBlindKey = selectedTemperature === null ? null : "gain_" + temperatureKey(selectedTemperature);
  const selectedBlindValues = selectedBlindKey ? blind.map(r => r["raw_" + selectedBlindKey]) : blind.map(() => 0);
  const selectedBlindMean = round12(selectedBlindValues.reduce((a, b) => a + b, 0) / blind.length);
  const selectedBlindCI = circularBlockBootstrapCI(selectedBlindValues, BOOT_REPS, BLOCK_LENGTH, BOOT_SEED);
  const selectedBlindTest = selectedTemperature === null
    ? { temperature: "uniform", mean_log_likelihood_gain: 0, cumulative_log_likelihood_gain: 0, e_process_p_value: 1, p_holm: 1, p_bonferroni_43: 1 }
    : blindTests.find(x => x.temperature === String(selectedTemperature));

  const status = selectedTemperature === null || selectedBlindMean <= 0 || selectedBlindTest.p_holm >= 0.05
    ? "NO_PREDICTIVE_LIFT_DEMONSTRATED"
    : "HISTORICAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION";

  const checks = [
    { id: "source_provenance", status: "PASS", detail: "Archive, scorer, active report and preregistered protocol Git blob SHA-1 values match the pinned contract." },
    { id: "archive_integrity", status: "PASS", detail: "3403 unique chronological rows; every row is a sorted distinct 5-of-40 draw." },
    { id: "score_vector_integrity", status: "PASS", detail: "All 3203 prior-only score vectors contain each number 1..40 exactly once with finite descending scores and source tie-break." },
    { id: "strict_prior_cutoffs", status: "PASS", detail: "Every target t is scored from archive[0:t]; maximum training outcome index is t-1, strictly before target t." },
    { id: "subset_partition_dp", status: "PASS", detail: "Fifth elementary symmetric DP equals exhaustive small-n enumeration; uniform 40-node normalizer equals 658008." },
    { id: "exact_subset_normalization", status: "PASS", detail: "One representative finite-temperature forecast was exhaustively summed over all 658008 subsets; relative normalization error " + round12(normalizationError) + "." },
    { id: "future_mutation_invariance", status: "PASS", detail: futureMutationComparisons + "/9 future-mutation comparisons preserved the complete score vector." },
    { id: "deterministic_replay", status: "PASS", detail: deterministicReplayComparisons + "/8 fixed-cutoff scorer replays were byte-identical." },
    { id: "split_reconciliation", status: "PASS", detail: "1921 discovery + 641 validation + 641 historical blind OOS = 3203 targets." },
    { id: "likelihood_ratio_validity", status: "PASS", detail: "Each subset PMF is normalized and predictable from the strict prior; exp(cumulative log gain) is the registered likelihood-ratio test martingale under the conditional uniform null." }
  ];

  const report = {
    experiment_id: "Q103",
    title: "Active SONAR score-magnitude calibration as a 5-of-40 subset likelihood",
    status,
    generated_date: "2026-11-10",
    source: {
      main_commit: "d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b",
      archive_blob_sha1: archiveBlob,
      scorer_blob_sha1: scorerBlob,
      active_engine_report_blob_sha1: activeBlob,
      protocol_blob_sha1: protocolBlob,
      runner_blob_sha1: scriptBlob,
      draws: draws.length,
      first_date: draws[0].d,
      last_date: draws[draws.length - 1].d
    },
    model: {
      distribution: "Fisher noncentral hypergeometric over complete unordered 5-subsets",
      subset_probability: "product(weights for selected numbers) / e5(all 40 weights)",
      weight: "exp((score - max_score) / temperature)",
      exact_subset_count: COMBINATIONS,
      temperatures: TEMPERATURES,
      null_control: "uniform 5-of-40; log-likelihood gain exactly zero"
    },
    walk_forward: {
      warmup: WARMUP,
      targets: targetRows.length,
      splits: {
        discovery: discoverySummary,
        validation: validationSummary,
        historical_blind_oos: blindSummary
      },
      selected_temperature_validation: selected.temperature,
      validation_selection_rule: "maximum mean log-likelihood gain; uniform included; ties favor larger temperature"
    },
    blind_inference: {
      primary_endpoint: "cumulative prequential complete-quintet log-likelihood gain versus uniform",
      null: "conditional independent uniform 5-of-40 draws",
      e_process: "exp(sum_t log(P_T(D_t|F_{t-1}) / P_uniform(D_t))) is a likelihood-ratio test martingale under the null",
      tests: blindTests,
      correction: "Holm step-down across 9 fixed temperatures; Bonferroni x43 catalogue screen shown separately",
      selected_validation_model: {
        temperature: selected.temperature,
        mean_log_likelihood_gain: selectedBlindMean,
        cumulative_log_likelihood_gain: round12(selectedBlindValues.reduce((a,b)=>a+b,0)),
        circular_block_bootstrap_95_ci: selectedBlindCI,
        bootstrap_replicates: BOOT_REPS,
        block_length: BLOCK_LENGTH,
        seed: BOOT_SEED,
        inference: selectedBlindTest
      }
    },
    diagnostics: {
      selected_model_conditional_null_expected_gain_mean: selectedTemperature === null
        ? 0
        : blindSummary.models[String(selectedTemperature)].mean_conditional_null_expected_gain,
      top20_random_expected_mean_hits: 2.5,
      top5_random_expected_mean_hits: 0.625,
      blind_top20_mean_hits: blindSummary.mean_top20_hits,
      blind_top5_mean_hits: blindSummary.mean_top5_hits,
      exhaustive_subset_normalization_relative_error: round12(normalizationError)
    },
    validation: {
      status: "PASS",
      checks
    },
    interpretation: "This tests whether the magnitude of the active engine's pre-target scores supports a coherent probability distribution over complete quintets that improves sequential log score over the exact uniform 5-of-40 null. It does not alter or promote the active ranking engine.",
    limitations: [
      "Historical blind OOS was already examined by previous SONAR research, including Q100 rank calibration; it is not a virgin holdout.",
      "The source scores are heuristic normalized ranking scores, not calibrated probabilities.",
      "The product-weight subset model is a research calibration layer, not a replacement production engine.",
      "The e-process assumes each next draw is conditionally uniform under the null; the test is valid only for the registered fixed temperature family.",
      "Holm covers the nine fixed temperatures; Bonferroni x43 is only a conservative catalogue screen and cannot correct unknown analyst degrees of freedom.",
      "Any positive historical signal requires a new prospectively frozen cohort and Q60 completion."
    ],
    decision: {
      predictive_lift_demonstrated: status === "HISTORICAL_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION",
      promotion_allowed: false,
      production_change_allowed: false,
      prospective_freezes_changed: false,
      q60_h101_h102_changed: false
    }
  };

  const validation = {
    experiment_id: "Q103",
    status: "PASS",
    checks,
    counts: {
      archive_draws: draws.length,
      targets: targetRows.length,
      discovery: discovery.length,
      validation: validationRows.length,
      historical_blind_oos: blind.length,
      future_mutation_comparisons: futureMutationComparisons,
      deterministic_replay_comparisons: deterministicReplayComparisons
    },
    exact_normalization: {
      uniform_subset_count: uniformZ,
      representative_finite_temperature_relative_error: round12(normalizationError)
    },
    provenance: {
      archive_blob_sha1: archiveBlob,
      scorer_blob_sha1: scorerBlob,
      active_engine_report_blob_sha1: activeBlob,
      protocol_blob_sha1: protocolBlob,
      runner_blob_sha1: scriptBlob
    }
  };

  const ledger = buildLedgerCsv(targetRows);
  const checkpoint = [
    "# Q103 — score-magnitude subset-likelihood checkpoint (2026-11-10)",
    "",
    "## Status",
    status + ". Research-only; no production engine, freeze, Q60, H101 or H102 record was changed.",
    "",
    "## Source and protocol",
    "- Main: d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b.",
    "- Archive: 3403 draws through 2026-11-09; blob " + archiveBlob + ".",
    "- Active scorer: blob " + scorerBlob + "; active report blob " + activeBlob + ".",
    "- Preregistered protocol blob: " + protocolBlob + ".",
    "",
    "## Result",
    "- Targets: 3203 (Discovery 1921 / Validation 641 / historical Blind OOS 641).",
    "- Validation-selected temperature: " + selected.temperature + ".",
    "- Blind mean log-likelihood gain: " + selectedBlindMean + ".",
    "- Blind 95% circular block-bootstrap CI: [" + selectedBlindCI.join(", ") + "].",
    "- Selected-model e-process p: " + selectedBlindTest.e_process_p_value + "; Holm: " + selectedBlindTest.p_holm + ".",
    "",
    "## Integrity",
    "- " + checks.length + "/" + checks.length + " checks PASS.",
    "- Future mutation: " + futureMutationComparisons + "/9; deterministic replay: " + deterministicReplayComparisons + "/8.",
    "- Exhaustive 658008-subset normalization relative error: " + round12(normalizationError) + ".",
    "",
    "## Limitations / next action",
    "- Historical Blind OOS is not virgin; Q100 already examined rank performance on the same target period.",
    "- Do not tune additional temperatures or score transforms on this cohort.",
    "- Wait for official verification of contest 314 before append-only archive update and Q60 freeze evaluation.",
    "- Any positive score-calibration result still requires prospective confirmation; no promotion is authorized."
  ].join("\n") + "\n";

  const reportText = canonicalJson(report);
  const validationText = canonicalJson(validation);
  const outputs = {
    [REPORT_PATH]: reportText,
    [VALIDATION_PATH]: validationText,
    [LEDGER_PATH]: ledger,
    [CHECKPOINT_PATH]: checkpoint
  };
  const manifest = {
    experiment_id: "Q103",
    generated_date: "2026-11-10",
    source_git_blob_sha1: {
      archive: archiveBlob,
      scorer: scorerBlob,
      active_engine_report: activeBlob,
      protocol: protocolBlob,
      runner: scriptBlob
    },
    outputs: Object.fromEntries(Object.entries(outputs).map(([path, content]) => [path, {
      bytes: Buffer.byteLength(content, "utf8"),
      git_blob_sha1: gitBlobSha1(content),
      sha256: sha256(content)
    }]))
  };
  const manifestText = canonicalJson(manifest);
  outputs[MANIFEST_PATH] = manifestText;

  if (mode === "--write") {
    for (const [path, content] of Object.entries(outputs)) {
      fs.mkdirSync(path.slice(0, path.lastIndexOf("/")), { recursive: true });
      fs.writeFileSync(path, content, "utf8");
    }
    console.log("Q103_WRITE_PASS targets=" + targetRows.length + " selected=" + selected.temperature + " status=" + status);
  } else {
    for (const [path, expected] of Object.entries(outputs)) {
      if (!fs.existsSync(path)) fail("persisted output missing: " + path);
      const actual = fs.readFileSync(path, "utf8");
      if (actual !== expected) fail("persisted output differs from deterministic replay: " + path);
    }
    console.log("Q103_REPLAY_BYTE_IDENTICAL_PASS targets=" + targetRows.length + " selected=" + selected.temperature + " status=" + status);
  }
}

main();
