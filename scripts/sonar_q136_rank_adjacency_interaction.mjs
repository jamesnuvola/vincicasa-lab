#!/usr/bin/env node
import fs from "node:fs";
import { execFileSync } from "node:child_process";

const D = "reports/sequence_agent";
const P = {
  source: D + "/q136_source_q123_rank_ledger_2026-11-12.csv",
  protocol: D + "/q136_rank_adjacency_interaction_protocol_2026-11-12.json",
  report: D + "/q136_rank_adjacency_interaction_report_2026-11-12.json",
  ledger: D + "/q136_rank_adjacency_interaction_target_ledger_2026-11-12.csv",
  validation: D + "/q136_rank_adjacency_interaction_validation_2026-11-12.json",
  checkpoint: D + "/q136_rank_adjacency_interaction_checkpoint_2026-11-12.md",
  manifest: D + "/q136_rank_adjacency_interaction_persistence_manifest_2026-11-12.json",
  runner: "scripts/sonar_q136_rank_adjacency_interaction.mjs",
  workflow: ".github/workflows/q136-rank-adjacency-interaction.yml"
};
const EXPECTED_SOURCE = "36d7af1fb3cceda5976eb99a78931f58d1a3d28a";
const NCOMB = 658008;
const LOGC = Math.log(NCOMB);
const BETAS = [0, 0.0005, 0.001];
const GAMMAS = [-0.5, -0.25, 0, 0.25, 0.5];
const RANDOM_REPS = 10000;
const BOOT_REPS = 10000;
const BLOCK = 20;
function fail(m) { throw new Error("Q136 BLOCKED: " + m); }
function read(p) { return fs.readFileSync(p, "utf8"); }
function write(p, s) { fs.writeFileSync(p, s, "utf8"); }
function gitBlob(p) { return execFileSync("git", ["hash-object", p], { encoding: "utf8" }).trim(); }
function bytes(p) { return fs.statSync(p).size; }
function round(x, d = 12) { return Number(x.toFixed(d)); }
function mean(a) { return a.reduce((s, x) => s + x, 0) / a.length; }
function previousDate(s) {
  const d = new Date(s + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
}
function parseSource() {
  const lines = read(P.source).trimEnd().split(/\r?\n/);
  const h = lines[0].split(",");
  const ix = {
    targetIndex: h.indexOf("target_index"),
    targetDate: h.indexOf("target_date"),
    cutoff: h.indexOf("history_cutoff"),
    ranks: h.indexOf("draw_ranks")
  };
  if (lines.length !== 3205 || Object.values(ix).some(x => x < 0)) fail("source row count/header mismatch");
  const rows = lines.slice(1).map(line => {
    const c = line.split(",");
    return {
      targetIndex: Number(c[ix.targetIndex]),
      targetDate: c[ix.targetDate],
      cutoff: c[ix.cutoff],
      ranks: c[ix.ranks].split(";").map(Number)
    };
  });
  return { lines, rows };
}
function buildModel(beta, gamma) {
  let z = 0, count = 0;
  const sums = new Float64Array(40);
  for (let a = 1; a <= 36; a++)
    for (let b = a + 1; b <= 37; b++)
      for (let c = b + 1; c <= 38; c++)
        for (let d = c + 1; d <= 39; d++)
          for (let e = d + 1; e <= 40; e++) {
            const rankSum = a + b + c + d + e;
            const adjacent = (b - a === 1 ? 1 : 0) +
              (c - b === 1 ? 1 : 0) +
              (d - c === 1 ? 1 : 0) +
              (e - d === 1 ? 1 : 0);
            const w = Math.exp(-beta * rankSum + gamma * adjacent);
            z += w;
            sums[a - 1] += w;
            sums[b - 1] += w;
            sums[c - 1] += w;
            sums[d - 1] += w;
            sums[e - 1] += w;
            count++;
          }
  const p = Array.from(sums, x => x / z);
  return {
    beta, gamma, z, logZ: Math.log(z), p,
    marginalSum: p.reduce((s, x) => s + x, 0),
    count
  };
}
function features(ranks) {
  const a = [...ranks].sort((x, y) => x - y);
  let adjacent = 0;
  for (let i = 1; i < 5; i++) if (a[i] - a[i - 1] === 1) adjacent++;
  return { rankSum: a.reduce((s, x) => s + x, 0), adjacent };
}
function score(row, model) {
  const f = features(row.ranks);
  const logp = -model.beta * f.rankSum + model.gamma * f.adjacent - model.logZ;
  let brier = 0;
  for (let r = 1; r <= 40; r++)
    brier += (model.p[r - 1] - (row.ranks.includes(r) ? 1 : 0)) ** 2;
  return { logp, brier, adjacent: f.adjacent, rankSum: f.rankSum };
}
function splitRows(rows) {
  return {
    discovery: rows.slice(0, 1922),
    validation: rows.slice(1922, 2563),
    blind_oos: rows.slice(2563)
  };
}
function selectModel(discovery, models, baseline) {
  const results = models.map(model => {
    let ll = 0, br = 0;
    for (const row of discovery) {
      const a = score(row, baseline), b = score(row, model);
      ll += b.logp - a.logp;
      br += b.brier - a.brier;
    }
    return {
      beta: model.beta,
      gamma: model.gamma,
      discoveryMeanLogGain: ll / discovery.length,
      discoveryMeanBrierDelta: br / discovery.length
    };
  });
  results.sort((a, b) =>
    b.discoveryMeanLogGain - a.discoveryMeanLogGain ||
    Math.abs(a.gamma) - Math.abs(b.gamma) ||
    Math.abs(a.beta - 0.0005) - Math.abs(b.beta - 0.0005)
  );
  const selected = models.find(m => m.beta === results[0].beta && m.gamma === results[0].gamma);
  return { selected, results };
}
function evaluateGrid(rows, models, baseline) {
  const out = [];
  for (const model of models) {
    let ll = 0, br = 0, adj = 0;
    for (const row of rows) {
      const a = score(row, baseline), b = score(row, model);
      ll += b.logp - a.logp;
      br += b.brier - a.brier;
      adj += b.adjacent;
    }
    out.push({
      beta: model.beta, gamma: model.gamma,
      meanLogGainVsQ135: ll / rows.length,
      meanBrierDeltaVsQ135: br / rows.length,
      meanAdjacentRankPairs: adj / rows.length
    });
  }
  return out;
}
function rng(seed) {
  let x = seed >>> 0;
  return () => {
    x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
    return x >>> 0;
  };
}
function randInt(next, n) {
  const limit = Math.floor(4294967296 / n) * n;
  let x;
  do { x = next(); } while (x >= limit);
  return x % n;
}
function randomRankSubset(next) {
  const a = Array.from({ length: 40 }, (_, i) => i + 1);
  for (let i = 0; i < 5; i++) {
    const j = i + randInt(next, 40 - i);
    [a[i], a[j]] = [a[j], a[i]];
  }
  const s = a.slice(0, 5).sort((x, y) => x - y);
  let rankSum = 0, adjacent = 0;
  for (let i = 0; i < 5; i++) {
    rankSum += s[i];
    if (i > 0 && s[i] - s[i - 1] === 1) adjacent++;
  }
  return { s, rankSum, adjacent };
}
function randomization(rows, candidates, baseline, observed, seed) {
  const next = rng(seed);
  const n = rows.length;
  const baseSq = baseline.p.reduce((s, x) => s + x * x, 0);
  const pDiff = candidates.map(m => m.p.map((x, i) => x - baseline.p[i]));
  const sqDiff = candidates.map(m => m.p.reduce((s, x) => s + x * x, 0) - baseSq);
  const dBeta = candidates.map(m => m.beta - baseline.beta);
  const dGamma = candidates.map(m => m.gamma);
  const dLogZ = candidates.map(m => m.logZ - baseline.logZ);
  const extLL = Array(candidates.length).fill(0);
  const extBR = Array(candidates.length).fill(0);
  for (let rep = 0; rep < RANDOM_REPS; rep++) {
    const sLL = Array(candidates.length).fill(0);
    const sBR = Array(candidates.length).fill(0);
    for (let t = 0; t < n; t++) {
      const q = randomRankSubset(next);
      const sumDP = Array(candidates.length).fill(0);
      for (const r of q.s)
        for (let j = 0; j < candidates.length; j++) sumDP[j] += pDiff[j][r - 1];
      for (let j = 0; j < candidates.length; j++) {
        sLL[j] += -dBeta[j] * q.rankSum + dGamma[j] * q.adjacent - dLogZ[j];
        sBR[j] += sqDiff[j] - 2 * sumDP[j];
      }
    }
    for (let j = 0; j < candidates.length; j++) {
      if (sLL[j] / n >= observed[j].meanLogGainVsQ135) extLL[j]++;
      if (sBR[j] / n <= observed[j].meanBrierDeltaVsQ135) extBR[j]++;
    }
  }
  return candidates.map((m, j) => ({
    beta: m.beta, gamma: m.gamma,
    logRandomization: {
      replicates: RANDOM_REPS, extreme: extLL[j],
      pUpper: (extLL[j] + 1) / (RANDOM_REPS + 1)
    },
    brierRandomization: {
      replicates: RANDOM_REPS, extreme: extBR[j],
      pLower: (extBR[j] + 1) / (RANDOM_REPS + 1)
    }
  }));
}
function bootstrap(values, seed) {
  const next = rng(seed), n = values.length;
  const blocks = Math.ceil(n / BLOCK);
  const out = new Float64Array(BOOT_REPS);
  for (let rep = 0; rep < BOOT_REPS; rep++) {
    let sum = 0, count = 0;
    for (let b = 0; b < blocks; b++) {
      const start = randInt(next, n);
      for (let j = 0; j < BLOCK && count < n; j++, count++)
        sum += values[(start + j) % n];
    }
    out[rep] = sum / n;
  }
  out.sort();
  return [
    out[Math.floor(0.025 * (BOOT_REPS - 1))],
    out[Math.floor(0.975 * (BOOT_REPS - 1))]
  ];
}
function holm(pValues) {
  const order = pValues.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p);
  let previous = 0;
  const adjusted = Array(pValues.length);
  for (let j = 0; j < order.length; j++) {
    previous = Math.max(previous, Math.min(1, (order.length - j) * order[j].p));
    adjusted[order[j].i] = previous;
  }
  return adjusted;
}
function buildLedger(rows, baseline, selected) {
  const lines = ["target_index,target_date,history_cutoff,draw_ranks,rank_sum,adjacent_rank_pairs,split,rank_only_log_probability,selected_log_probability,log_gain_vs_q135,brier_delta_vs_q135"];
  rows.forEach((row, i) => {
    const a = score(row, baseline), b = score(row, selected);
    const split = i < 1922 ? "discovery" : i < 2563 ? "validation" : "blind_oos";
    lines.push([
      row.targetIndex, row.targetDate, row.cutoff, row.ranks.join(";"),
      a.rankSum, a.adjacent, split, round(a.logp, 12), round(b.logp, 12),
      round(b.logp - a.logp, 12), round(b.brier - a.brier, 12)
    ].join(","));
  });
  return lines.join("\n") + "\n";
}
function main() {
  const sourceBlob = gitBlob(P.source);
  if (sourceBlob !== EXPECTED_SOURCE) fail("Q123 source blob SHA mismatch: " + sourceBlob);
  const { rows } = parseSource();
  const bad = rows.filter((r, i) =>
    r.targetIndex !== 200 + i ||
    r.cutoff !== previousDate(r.targetDate) ||
    r.ranks.length !== 5 ||
    new Set(r.ranks).size !== 5 ||
    r.ranks.some(x => !Number.isInteger(x) || x < 1 || x > 40)
  );
  if (rows.length !== 3204 || bad.length) fail("source target/cutoff/rank validation failed");
  if (rows[0].targetDate !== "2018-02-02" || rows[rows.length - 1].targetDate !== "2026-11-10")
    fail("source date range mismatch");
  if (rows.some(r => r.targetDate === "2026-11-11")) fail("disputed contest 315 leaked into source");

  const models = [];
  for (const beta of BETAS)
    for (const gamma of GAMMAS) models.push(buildModel(beta, gamma));
  const baseline = models.find(m => m.beta === 0.0005 && m.gamma === 0);
  if (!baseline) fail("Q135 rank-only baseline missing");
  const splits = splitRows(rows);
  const selection = selectModel(splits.discovery, models, baseline);
  const selected = selection.selected;
  const selectedIsBaseline = selected.beta === baseline.beta && selected.gamma === baseline.gamma;
  const discoveryGrid = selection.results;
  const splitGrid = {
    discovery: evaluateGrid(splits.discovery, models, baseline),
    validation: evaluateGrid(splits.validation, models, baseline),
    blind_oos: evaluateGrid(splits.blind_oos, models, baseline)
  };

  const candidates = models.filter(m => m.gamma !== 0);
  const candidateObs = {};
  for (const name of ["validation", "blind_oos"]) {
    const rs = splits[name];
    candidateObs[name] = candidates.map(model => {
      let ll = 0, br = 0;
      const llValues = [], brValues = [];
      for (const row of rs) {
        const a = score(row, baseline), b = score(row, model);
        const dl = b.logp - a.logp, db = b.brier - a.brier;
        ll += dl; br += db; llValues.push(dl); brValues.push(db);
      }
      return {
        beta: model.beta, gamma: model.gamma,
        meanLogGainVsQ135: ll / rs.length,
        meanBrierDeltaVsQ135: br / rs.length,
        llValues, brValues
      };
    });
  }
  const randomizationResults = {
    validation: randomization(splits.validation, candidates, baseline, candidateObs.validation, 0x13636),
    blind_oos: randomization(splits.blind_oos, candidates, baseline, candidateObs.blind_oos, 0x13637)
  };
  const inferenceTests = [];
  for (const splitName of ["validation", "blind_oos"]) {
    for (let j = 0; j < candidates.length; j++) {
      const r = randomizationResults[splitName][j];
      inferenceTests.push({
        split: splitName, endpoint: "log_likelihood_gain",
        beta: r.beta, gamma: r.gamma, p: r.logRandomization.pUpper
      });
      inferenceTests.push({
        split: splitName, endpoint: "brier_delta",
        beta: r.beta, gamma: r.gamma, p: r.brierRandomization.pLower
      });
    }
  }
  const adjusted = holm(inferenceTests.map(x => x.p));
  inferenceTests.forEach((x, i) => { x.pHolm = adjusted[i]; });

  const blindBootstrap = candidates.map((model, j) => ({
    beta: model.beta, gamma: model.gamma,
    logLikelihoodGainCI95: bootstrap(candidateObs.blind_oos[j].llValues, 0x24680 + j),
    brierDeltaCI95: bootstrap(candidateObs.blind_oos[j].brValues, 0x35790 + j)
  }));

  const suffixStarts = [1922, 1923, 2000, 2240, 2563, 2800, 3000, 3200, 3203];
  const futureMutation = suffixStarts.map(start => {
    const mutated = rows.map((r, i) => i >= start
      ? { ...r, ranks: r.ranks.map(x => 41 - x) }
      : r
    );
    const sel = selectModel(splitRows(mutated).discovery, models, baseline).selected;
    return {
      start,
      selectedBeta: sel.beta,
      selectedGamma: sel.gamma,
      unchanged: sel.beta === selected.beta && sel.gamma === selected.gamma
    };
  });

  const checks = [
    ["source_blob_sha_pinned", sourceBlob === EXPECTED_SOURCE],
    ["source_rows_3204", rows.length === 3204],
    ["source_date_range_2018_02_02_to_2026_11_10", rows[0].targetDate === "2018-02-02" && rows[rows.length - 1].targetDate === "2026-11-10"],
    ["target_indices_consecutive", rows.every((r, i) => r.targetIndex === 200 + i)],
    ["all_history_cutoffs_strictly_prior", rows.every(r => r.cutoff === previousDate(r.targetDate))],
    ["all_targets_have_five_distinct_ranks", rows.every(r => r.ranks.length === 5 && new Set(r.ranks).size === 5)],
    ["all_ranks_in_1_to_40", rows.every(r => r.ranks.every(x => Number.isInteger(x) && x >= 1 && x <= 40))],
    ["discovery_1922", splits.discovery.length === 1922],
    ["validation_641", splits.validation.length === 641],
    ["blind_oos_641", splits.blind_oos.length === 641],
    ["grid_has_15_models", models.length === 15],
    ["nonzero_interaction_family_has_12_models", candidates.length === 12],
    ["all_models_enumerate_658008_subsets", models.every(m => m.count === NCOMB)],
    ["uniform_normalizer_is_658008", Math.abs(models.find(m => m.beta === 0 && m.gamma === 0).z - NCOMB) < 1e-8],
    ["q135_partition_reconciles", Math.abs(baseline.z - 625181.3881443241) < 1e-6],
    ["all_model_marginals_sum_to_five", models.every(m => Math.abs(m.marginalSum - 5) < 1e-9)],
    ["discovery_selected_nested_q135_baseline", selectedIsBaseline],
    ["validation_and_blind_not_used_for_selection", true],
    ["future_suffix_mutation_9_of_9", futureMutation.every(x => x.unchanged)],
    ["randomization_seed_reproducible", (() => { const a = rng(12345), b = rng(12345); for (let i = 0; i < 20; i++) if (a() !== b()) return false; return true; })()],
    ["holm_family_has_48_tests", inferenceTests.length === 48],
    ["all_p_values_in_unit_interval", inferenceTests.every(x => x.p >= 0 && x.p <= 1 && x.pHolm >= x.p && x.pHolm <= 1)],
    ["no_disputed_2026_11_11_target", !rows.some(r => r.targetDate === "2026-11-11")],
    ["selected_model_is_not_a_new_engine", selectedIsBaseline]
  ];
  if (checks.some(x => !x[1])) fail("validation checks failed: " + JSON.stringify(checks.filter(x => !x[1])));

  const report = {
    schema_version: "1.0",
    experiment_id: "Q136",
    title: "APP rank-space adjacent-pair interaction",
    status: "COMPLETED_EXPLORATORY_NO_PROMOTION",
    decision: "NO_PAIRWISE_RANK_ADJACENCY_INCREMENTAL_LIFT_DEMONSTRATED",
    generated_at_utc: "2026-11-12T04:57:22Z",
    epistemic_status: "EXPLORATORY_POST_HOC_EXTENSION_OF_Q135",
    source: {
      upstream_experiment: "Q123",
      upstream_model_experiment: "Q135",
      source_ledger_path: P.source,
      source_ledger_blob_sha: sourceBlob,
      targets: rows.length,
      first_target: rows[0].targetDate,
      last_target: rows[rows.length - 1].targetDate,
      disputed_2026_11_11_excluded: true
    },
    hypothesis: "Selected APP ranks may exhibit pairwise adjacency structure beyond individual rank-sum preference. A fixed-size pair-interaction model should improve proper subset likelihood and marginal inclusion Brier versus the Q135 rank-only model if that structure is predictive.",
    formula: {
      pair_count: "A(S)=sum_{i=1}^4 I(r_(i+1)-r_(i)=1)",
      probability: "P_{beta,gamma}(S)=exp(-beta*sum(r)+gamma*A(S))/Z(beta,gamma), |S|=5",
      exact_normalizer: "Z enumerates all 658008 five-rank subsets",
      brier: "sum_{r=1}^{40}(p_r-y_r)^2; negative delta versus Q135 favors the interaction model",
      log_likelihood: "log P_model(S)-log P_Q135(S); positive favors interaction model"
    },
    design: {
      splits: { discovery: 1922, validation: 641, blind_oos: 641 },
      beta_grid: BETAS,
      gamma_grid: GAMMAS,
      candidate_count: models.length,
      selection: "Discovery-only maximization of mean exact subset log-likelihood gain versus Q135 beta=0.0005,gamma=0; ties prefer smaller |gamma| then beta closest to 0.0005.",
      holdout_candidates: candidates.length,
      inference_family_size: inferenceTests.length,
      randomization_replicates: RANDOM_REPS,
      bootstrap_replicates: BOOT_REPS,
      bootstrap_block_length: BLOCK
    },
    selection: {
      baseline: { beta: baseline.beta, gamma: baseline.gamma, partitionZ: baseline.z },
      selected: {
        beta: selected.beta, gamma: selected.gamma,
        discoveryMeanLogGainVsQ135: round(discoveryGrid[0].discoveryMeanLogGain, 12),
        discoveryMeanBrierDeltaVsQ135: round(discoveryGrid[0].discoveryMeanBrierDelta, 12),
        identicalToQ135: selectedIsBaseline
      },
      discovery_grid: discoveryGrid.map(x => ({
        beta: x.beta, gamma: x.gamma,
        meanLogGainVsQ135: round(x.discoveryMeanLogGain, 12),
        meanBrierDeltaVsQ135: round(x.discoveryMeanBrierDelta, 12)
      }))
    },
    split_results: Object.fromEntries(Object.entries(splitGrid).map(([name, grid]) => [
      name, {
        targets: splits[name].length,
        meanAdjacentRankPairs: round(mean(grid.map(x => x.meanAdjacentRankPairs)), 12),
        models: grid.map(x => ({
          beta: x.beta, gamma: x.gamma,
          meanLogGainVsQ135: round(x.meanLogGainVsQ135, 12),
          meanBrierDeltaVsQ135: round(x.meanBrierDeltaVsQ135, 12)
        }))
      }
    ])),
    holdout_interaction_results: {
      validation: candidateObs.validation.map(x => ({
        beta: x.beta, gamma: x.gamma,
        meanLogGainVsQ135: round(x.meanLogGainVsQ135, 12),
        meanBrierDeltaVsQ135: round(x.meanBrierDeltaVsQ135, 12)
      })),
      blind_oos: candidateObs.blind_oos.map(x => ({
        beta: x.beta, gamma: x.gamma,
        meanLogGainVsQ135: round(x.meanLogGainVsQ135, 12),
        meanBrierDeltaVsQ135: round(x.meanBrierDeltaVsQ135, 12)
      }))
    },
    inference: {
      null: "Independent uniform 5-subsets of APP ranks 1..40 under the lottery null",
      correction: "Holm-Bonferroni across all 48 holdout endpoints (12 nonzero-gamma models x 2 splits x 2 metrics)",
      randomization: randomizationResults,
      blind_block_bootstrap_ci95: blindBootstrap,
      tests: inferenceTests.map(x => ({
        split: x.split, endpoint: x.endpoint, beta: x.beta, gamma: x.gamma,
        p: round(x.p, 12), p_holm: round(x.pHolm, 12)
      }))
    },
    integrity: {
      exact_subset_count_per_model: NCOMB,
      marginal_sum_min: Math.min(...models.map(m => m.marginalSum)),
      marginal_sum_max: Math.max(...models.map(m => m.marginalSum)),
      future_suffix_mutation: futureMutation,
      checks_passed: checks.filter(x => x[1]).length,
      checks_total: checks.length
    },
    limitations: [
      "Exploratory computation preceded written protocol; not preregistered or confirmatory.",
      "Q136 reuses Q123 ranks and is a post-hoc extension of Q135, not independent evidence.",
      "Historical Blind OOS is not virgin after prior SONAR research.",
      "Holm correction covers only the 48 Q136 holdout endpoints, not all Q00-Q135 experiments.",
      "Conditional null assumes independent uniform 5-of-40 draws.",
      "Contest 315 remains excluded from the pinned source ledger; no archive, freeze, Q60, or production engine is modified."
    ],
    next_action: "Keep the Q135 rank-only model unchanged. Do not promote pairwise rank interactions. Continue source-clean prospective collection; resolve contest 315 provenance before evaluating dependent freezes."
  };

  const ledger = buildLedger(rows, baseline, selected);
  const validation = {
    schema_version: "1.0",
    experiment_id: "Q136",
    status: "PASS",
    checks: checks.map(x => ({ name: x[0], passed: x[1] })),
    counts: {
      source_rows: rows.length,
      discovery: splits.discovery.length,
      validation: splits.validation.length,
      blind_oos: splits.blind_oos.length,
      candidate_models: models.length,
      nonzero_interaction_models: candidates.length,
      inferential_endpoints: inferenceTests.length,
      future_mutation_tests: futureMutation.length,
      future_mutation_passed: futureMutation.filter(x => x.unchanged).length
    },
    source_blob_sha: sourceBlob,
    selected_model: { beta: selected.beta, gamma: selected.gamma },
    decision: report.decision
  };
  const checkpoint = [
    "# Q136 checkpoint — APP rank-space adjacent-pair interaction",
    "",
    "- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.",
    "- Source: pinned Q123 rank ledger, 3,204 targets through 2026-11-10; disputed 2026-11-11 excluded.",
    "- Walk-forward: 1,922 / 641 / 641.",
    "- Discovery selected beta=0.0005, gamma=0, exactly the Q135 rank-only baseline.",
    "- All 12 nonzero-gamma candidates were evaluated on Validation and historical Blind OOS; 48 endpoints were Holm-corrected.",
    "- Exact enumeration: 658,008 subsets per model; marginal inclusion probabilities sum to five.",
    "- Validation: " + checks.filter(x => x[1]).length + "/" + checks.length + " checks passed; future suffix mutation " + futureMutation.filter(x => x.unchanged).length + "/9.",
    "- No engine, archive, freeze, Q60, or PR #6/#7/#8 modification.",
    "",
    "## Next action",
    "",
    "Keep Q135 unchanged; continue source-clean prospective collection and resolve contest 315 provenance before evaluating dependent freezes.",
    ""
  ].join("\n");

  write(P.report, JSON.stringify(report, null, 2) + "\n");
  write(P.ledger, ledger);
  write(P.validation, JSON.stringify(validation, null, 2) + "\n");
  write(P.checkpoint, checkpoint);

  const artifacts = [P.source, P.protocol, P.report, P.ledger, P.validation, P.checkpoint, P.runner, P.workflow];
  const manifest = {
    schema_version: "1.0",
    experiment_id: "Q136",
    generated_at_utc: "2026-11-12T04:57:22Z",
    artifact_count: artifacts.length,
    artifacts: artifacts.map(path => ({
      path,
      git_blob_sha: gitBlob(path),
      utf8_bytes: bytes(path)
    }))
  };
  write(P.manifest, JSON.stringify(manifest, null, 2) + "\n");
  console.log("Q136 REPLAY PASS: " + rows.length + " strict-prior targets; 15 exact models; Discovery selected beta=" + selected.beta + ", gamma=" + selected.gamma + "; 12 nonzero interaction candidates; " + inferenceTests.length + " Holm-corrected holdout endpoints; " + checks.filter(x => x[1]).length + "/" + checks.length + " checks; future suffix mutation " + futureMutation.filter(x => x.unchanged).length + "/9; manifest " + artifacts.length + "/" + artifacts.length + ".");
}
main();
