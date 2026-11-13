import fs from "node:fs";
import path from "node:path";
import {
  parseCsv, gitBlobSha1, rankWeights, elementarySymmetric,
  circularBlockBootstrap, exactSignFlipTwoSided, holmAdjust,
  verifyArtifacts as verifyQ145
} from "./sonar_q145_rank_subset_likelihood.mjs";

export const Q146 = Object.freeze({
  experimentId: "Q146",
  archivePath: "data/storico_daily.csv",
  shadowPath: "reports/sequence_agent/shadow_forecasts.csv",
  q144LedgerPath: "reports/sequence_agent/q144_shadow_rank_ensemble_ledger_2026-11-13.csv",
  q144FreezePath: "reports/sequence_agent/q144_shadow_rank_ensemble_freeze_2026-11-13.json",
  q145ReportPath: "reports/sequence_agent/q145_rank_subset_likelihood_report_2026-11-13.json",
  q145CheckpointPath: "reports/sequence_agent/q145_rank_subset_likelihood_checkpoint_2026-11-13.json",
  q145ScriptPath: "scripts/sonar_q145_rank_subset_likelihood.mjs",
  q145PreregPath: "reports/sequence_agent/q145_rank_subset_likelihood_preregistration_2026-11-13.md",
  sourceShas: Object.freeze({
    archive: "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb",
    shadow: "ffc5a4eb0c38e4dfc67032e1ef5737689be5fec1",
    q144Ledger: "c14e13b0c8e7f7a8c20ae40c9af56101f5209762",
    q144Freeze: "df20af45433ae8693b90e06124d31df0ad345dfe",
    q145Report: "8ab96c407df9ed2bf256cb01c5a2e9282e6c3412",
    q145Checkpoint: "e961e75bda0f7c28342f0f9cd19f8fc8e68afdba",
    q145Script: "b0515ae21faa403991994d9535fc82b707a8b9ff",
    q145Prereg: "6bb8725ccb57ffad5f803352252ba94c42b29b70"
  }),
  bootstrapReplicates: 20000,
  blockLength: 2
});

const ROOT = process.cwd();
const OUT = {
  reportJson: "reports/sequence_agent/q146_pair_inclusion_calibration_report_2026-11-13.json",
  reportMd: "reports/sequence_agent/q146_pair_inclusion_calibration_report_2026-11-13.md",
  ledger: "reports/sequence_agent/q146_pair_inclusion_calibration_ledger_2026-11-13.csv",
  checkpoint: "reports/sequence_agent/q146_pair_inclusion_calibration_checkpoint_2026-11-13.json",
  manifest: "reports/sequence_agent/q146_pair_inclusion_calibration_manifest_2026-11-13.json"
};

const read = p => fs.readFileSync(path.join(ROOT, p), "utf8");
const round = (x, d = 12) => {
  const v = Number(x.toFixed(d));
  return Object.is(v, -0) ? 0 : v;
};
const avg = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
const parseNumbers = value => !value || !value.trim() ? [] : value.trim().split(/\s+/).map(Number);
const drawTimestamp = (date, offset) => Date.parse(date + "T20:00:00" + offset);

export function validateShadowTemporalRow(row) {
  const freezeMs = Date.parse(row.frozen_at);
  const offset = row.frozen_at.slice(-6);
  const freezeDate = row.frozen_at.slice(0, 10);
  if (!Number.isFinite(freezeMs) || !(row.history_cutoff < row.target_date) ||
      !(row.history_cutoff <= freezeDate) ||
      !(freezeMs < drawTimestamp(row.target_date, offset))) return false;
  if (row.history_cutoff === freezeDate &&
      !(freezeMs > drawTimestamp(row.history_cutoff, offset))) return false;
  return true;
}

export function pairInclusionProbabilities(weights) {
  if (weights.length !== 40 || weights.some(w => !(w > 0) || !Number.isFinite(w))) {
    throw new Error("Expected 40 finite positive weights");
  }
  const denominator = elementarySymmetric(weights, 5);
  const pairs = [];
  let mass = 0;
  for (let i = 0; i < 40; i++) {
    for (let j = i + 1; j < 40; j++) {
      const rest = weights.filter((_, k) => k !== i && k !== j);
      const p = weights[i] * weights[j] * elementarySymmetric(rest, 3) / denominator;
      if (!(p > 0 && p < 1) || !Number.isFinite(p)) throw new Error("Invalid pair inclusion probability");
      pairs.push({ i: i + 1, j: j + 1, probability: p });
      mass += p;
    }
  }
  return { pairs, mass };
}

export function scorePairWeights(weights, draw) {
  if (draw.length !== 5 || new Set(draw).size !== 5 ||
      draw.some(n => !Number.isInteger(n) || n < 1 || n > 40)) throw new Error("Invalid 5-of-40 draw");
  const { pairs, mass } = pairInclusionProbabilities(weights);
  const selected = new Set(draw);
  const uniform = 10 / 780;
  let modelBrier = 0, uniformBrier = 0, modelLog = 0, uniformLog = 0, observedPairs = 0;
  for (const pair of pairs) {
    const y = selected.has(pair.i) && selected.has(pair.j) ? 1 : 0;
    const p = pair.probability;
    if (y) observedPairs++;
    modelBrier += (p - y) ** 2;
    uniformBrier += (uniform - y) ** 2;
    modelLog += y * Math.log(p) + (1 - y) * Math.log1p(-p);
    uniformLog += y * Math.log(uniform) + (1 - y) * Math.log1p(-uniform);
  }
  if (observedPairs !== 10) throw new Error("A 5-number draw must contain exactly 10 unordered pairs");
  return {
    pairMass: mass,
    observedPairs,
    brierGain: (uniformBrier - modelBrier) / 780,
    compositeLogGain: (modelLog - uniformLog) / 780
  };
}

export function scorePairModel(top20, draw) {
  return scorePairWeights(rankWeights(top20, 1), draw);
}

function validateShadowRows(shadowRows, archiveMap) {
  if (shadowRows.length !== 1364) throw new Error("Expected 1,364 shadow rows");
  let strictPrior = 0, pending = 0;
  const byDate = new Map();
  for (const row of shadowRows) {
    if (!validateShadowTemporalRow(row)) throw new Error("Strict-prior timestamp failed: " + row.target_date + "/" + row.config_id);
    strictPrior++;
    if (!byDate.has(row.target_date)) byDate.set(row.target_date, []);
    byDate.get(row.target_date).push(row);
    if (row.target_date === "2026-11-13") {
      pending++;
      if (row.actual_numbers || row.hit_count || row.hit_numbers || row.history_cutoff !== "2026-11-12") {
        throw new Error("Pending 2026-11-13 row contains an outcome or wrong cutoff");
      }
    } else if (row.status === "EVALUATED") {
      const actual = parseNumbers(row.actual_numbers).sort((a, b) => a - b);
      const canonical = archiveMap.get(row.target_date);
      if (!canonical || actual.join(",") !== canonical.join(",")) {
        throw new Error("Shadow/archive mismatch: " + row.target_date);
      }
    }
  }
  if (strictPrior !== 1364 || pending !== 43) throw new Error("Shadow temporal audit totals mismatch");
  for (const [date, group] of byDate) {
    if (date === "2026-11-13") {
      if (group.length !== 43) throw new Error("Pending row count mismatch");
      continue;
    }
    const rules = group.filter(r => ["family", "pair", "chain"].includes(r.config_type));
    if (rules.length !== 42 ||
        rules.filter(r => r.config_type === "family").length !== 24 ||
        rules.filter(r => r.config_type === "pair").length !== 12 ||
        rules.filter(r => r.config_type === "chain").length !== 6) {
      throw new Error("Shadow component counts mismatch: " + date);
    }
  }
  return { strictPriorRows: strictPrior, pendingRows: pending, targetGroups: byDate.size };
}

function validateTop20(top20, label) {
  if (top20.length !== 20 || new Set(top20).size !== 20 ||
      top20.some(n => !Number.isInteger(n) || n < 1 || n > 40)) {
    throw new Error(label + " Top20 invalid");
  }
}

function summarize(rows, model) {
  const a = rows.filter(r => r.models[model]);
  if (!a.length) return null;
  return {
    n: a.length,
    mean_pair_brier_gain: round(avg(a.map(r => r.models[model].brierGain))),
    mean_pair_composite_log_gain: round(avg(a.map(r => r.models[model].compositeLogGain))),
    mean_pair_mass: round(avg(a.map(r => r.models[model].pairMass)))
  };
}

function renderMarkdown(report) {
  const f = x => Number(x).toFixed(8);
  const lines = [
    "# Q146 — Pair-inclusion calibration audit",
    "",
    "**Decision:** pairwise calibration not established; Q145 remains frozen and unchanged.",
    "",
    "## Method",
    "- For each unordered pair {i,j}: P(i,j included)=w_i*w_j*e3(w excluding i,j)/e5(w).",
    "- Rank weights and temperature are unchanged from Q145: u(r)=(21-r)/20 for Top20, zero outside; w=exp(u), T=1.",
    "- Uniform pair baseline: 10/C(40,2)=1/78.",
    "- Primary endpoint: target-level mean pairwise Brier gain. Secondary: mean pairwise Bernoulli composite log-score gain; this is not a joint subset likelihood.",
    "- The 780 pair events within a target are dependent. Inference resamples target-level aggregates only.",
    "",
    "## Walk-forward results",
    "| Split | Model | n | Pair Brier gain | Pair composite log gain | Pair mass |",
    "|---|---|---:|---:|---:|---:|"
  ];
  for (const split of ["discovery", "validation", "blind_oos"]) {
    for (const model of ["borda", "inclusion", "app"]) {
      const s = report.splits[split][model];
      if (s) lines.push("| " + split + " | " + model + " | " + s.n + " | " +
        f(s.mean_pair_brier_gain) + " | " + f(s.mean_pair_composite_log_gain) + " | " +
        f(s.mean_pair_mass) + " |");
    }
  }
  lines.push("", "## Historical Blind OOS inference (7 targets)", "| Endpoint | Raw p | Holm p | 95% block-bootstrap CI |", "|---|---:|---:|---:|");
  for (const [key, p] of Object.entries(report.blind_inference.raw_p_values)) {
    const ci = report.blind_inference.bootstrap_ci_95[key];
    lines.push("| " + key + " | " + f(p) + " | " + f(report.blind_inference.holm_adjusted_p_values[key]) +
      " | [" + f(ci[0]) + ", " + f(ci[1]) + "] |");
  }
  lines.push(
    "",
    "The historical split is exploratory, not a virgin prospective test: Q145's rank-to-PMF transformation was specified after Q144 outcomes had been inspected. The blind segment contains only seven targets. Sign-flip inference assumes symmetry/exchangeability; Holm covers the five registered Q146 endpoints, not all SONAR experiments.",
    "",
    "## Integrity",
    "- 3,406 canonical archive rows; 1,364 shadow rows checked for strict-prior cutoffs and pre-draw timestamps; 43 pending 2026-11-13 rows remain outcome-free.",
    "- 31 Q144 target rows reconciled with the canonical archive; all Top20 hit counts recomputed.",
    "- Every model/target pair inclusion mass sums to 10 within 1e-10; every observed 5-number draw has exactly 10 unordered pairs.",
    "- Q145 upstream verifier passed against pinned source hashes before Q146 scoring.",
    "",
    "## Limits and next action",
    "- Pairwise Brier and composite log score evaluate marginal pair inclusion, not the full dependence structure of a 5-number subset.",
    "- No historical predictive lift or calibrated probability claim is made. No engine promotion.",
    "- Preserve the Q145 2026-11-13 freeze. Reconcile only after official publication and accumulate at least 100 consecutive prospective targets without retuning."
  );
  return lines.join("\n") + "\n";
}

export function buildArtifacts() {
  const sourceFiles = {
    archive: read(Q146.archivePath),
    shadow: read(Q146.shadowPath),
    q144Ledger: read(Q146.q144LedgerPath),
    q144Freeze: read(Q146.q144FreezePath),
    q145Report: read(Q146.q145ReportPath),
    q145Checkpoint: read(Q146.q145CheckpointPath),
    q145Script: read(Q146.q145ScriptPath),
    q145Prereg: read(Q146.q145PreregPath)
  };
  const sourceHashes = Object.fromEntries(Object.entries(sourceFiles).map(([k, v]) => [k, gitBlobSha1(v)]));
  for (const [key, expected] of Object.entries(Q146.sourceShas)) {
    if (sourceHashes[key] !== expected) throw new Error("Pinned Q145 source SHA mismatch: " + key);
  }

  const upstream = verifyQ145();
  if (upstream.status !== "Q145_VERIFY_OK" || upstream.targets !== 31 || upstream.blind !== 7) {
    throw new Error("Q145 upstream verifier did not return the pinned completed state");
  }

  const archiveRows = parseCsv(sourceFiles.archive);
  if (archiveRows.length !== 3406) throw new Error("Canonical archive row count mismatch");
  const archiveMap = new Map();
  for (const row of archiveRows) {
    const nums = [row.n1, row.n2, row.n3, row.n4, row.n5].map(Number).sort((a, b) => a - b);
    if (nums.length !== 5 || new Set(nums).size !== 5 ||
        nums.some(n => !Number.isInteger(n) || n < 1 || n > 40)) throw new Error("Invalid archive row " + row.data);
    archiveMap.set(row.data, nums);
  }

  const shadowRows = parseCsv(sourceFiles.shadow);
  const shadowAudit = validateShadowRows(shadowRows, archiveMap);
  const q144Rows = parseCsv(sourceFiles.q144Ledger);
  const q144Freeze = JSON.parse(sourceFiles.q144Freeze);
  const q145Report = JSON.parse(sourceFiles.q145Report);
  const q145Checkpoint = JSON.parse(sourceFiles.q145Checkpoint);
  if (q144Rows.length !== 31 || q144Freeze.status !== "FROZEN_PENDING" ||
      q144Freeze.outcome !== null || q144Freeze.target_date !== "2026-11-13" ||
      q144Freeze.history_cutoff !== "2026-11-12") throw new Error("Q144 freeze/ledger mismatch");
  if (q145Report.decision !== "NO_HISTORICAL_PREDICTIVE_LIFT_CLAIM; PROSPECTIVE_FROZEN_TEST_PENDING" ||
      q145Checkpoint.status !== "Q145_ARTIFACTS_REPLAYABLE_DEDICATED_CI_PASSED") {
    throw new Error("Q145 report/checkpoint status mismatch");
  }

  const rows = q144Rows.map((r, i) => {
    const draw = parseNumbers(r.actual_numbers).sort((a, b) => a - b);
    const canonical = archiveMap.get(r.target_date);
    if (!canonical || draw.join(",") !== canonical.join(",")) throw new Error("Q144/archive mismatch " + r.target_date);
    const borda = parseNumbers(r.borda_top20);
    const inclusion = parseNumbers(r.inclusion_top20);
    validateTop20(borda, "Borda");
    validateTop20(inclusion, "Equal-type inclusion");
    if (draw.filter(n => borda.includes(n)).length !== Number(r.borda_hits) ||
        draw.filter(n => inclusion.includes(n)).length !== Number(r.inclusion_hits)) {
      throw new Error("Q144 hit count mismatch " + r.target_date);
    }
    const models = {
      borda: scorePairModel(borda, draw),
      inclusion: scorePairModel(inclusion, draw)
    };
    if (r.app_available === "1") {
      const app = parseNumbers(r.app_top20);
      validateTop20(app, "APP");
      if (draw.filter(n => app.includes(n)).length !== Number(r.app_hits)) {
        throw new Error("APP hit count mismatch " + r.target_date);
      }
      models.app = scorePairModel(app, draw);
    } else if (r.app_top20 || r.app_hits) {
      throw new Error("APP availability flag mismatch " + r.target_date);
    }
    return { date: r.target_date, draw, split: i < 18 ? "discovery" : i < 24 ? "validation" : "blind_oos", models };
  });

  const splits = {};
  for (const name of ["discovery", "validation", "blind_oos"]) {
    const subset = rows.filter(r => r.split === name);
    splits[name] = { n: subset.length };
    for (const model of ["borda", "inclusion", "app"]) {
      const s = summarize(subset, model);
      if (s) splits[name][model] = s;
    }
  }

  const blind = rows.filter(r => r.split === "blind_oos");
  const appBlind = blind.filter(r => r.models.app);
  const diffs = {
    borda_vs_uniform: blind.map(r => r.models.borda.brierGain),
    inclusion_vs_uniform: blind.map(r => r.models.inclusion.brierGain),
    app_vs_uniform: appBlind.map(r => r.models.app.brierGain),
    borda_vs_inclusion: blind.map(r => r.models.borda.brierGain - r.models.inclusion.brierGain),
    borda_vs_app: appBlind.map(r => r.models.borda.brierGain - r.models.app.brierGain)
  };
  const rawP = Object.fromEntries(Object.entries(diffs).map(([k, v]) => [k, round(exactSignFlipTwoSided(v))]));
  const adjustedP = holmAdjust(rawP);
  const bootstrapCI = Object.fromEntries(Object.entries(diffs).map(([k, v], i) =>
    [k, circularBlockBootstrap(v, 14601 + i, Q146.bootstrapReplicates, Q146.blockLength)]
  ));
  const maxPairMassAbsError = Math.max(...rows.flatMap(r =>
    Object.values(r.models).map(m => Math.abs(m.pairMass - 10))
  ));
  const report = {
    schema_version: "1.0",
    experiment_id: "Q146",
    title: "Pair-inclusion calibration audit of Q145 rank-to-subset PMFs",
    status: "COMPLETE_RETROSPECTIVE_EXPLORATORY",
    method: {
      pair_probability: "P(i,j included)=w_i*w_j*e3(w excluding i,j)/e5(w)",
      rank_utility: "u(r)=(21-r)/20 for ranks 1..20; zero outside Top20",
      weights: "w_i=exp(u_i), temperature=1 (unchanged from Q145)",
      uniform_pair_probability: 10 / 780,
      pair_count: 780,
      primary_endpoint: "target-level mean pairwise Brier gain vs uniform",
      secondary_endpoint: "target-level mean pairwise Bernoulli composite log-score gain vs uniform; not a joint subset likelihood"
    },
    source_blob_shas: sourceHashes,
    integrity: {
      archive_draws: archiveRows.length,
      shadow_rows: shadowRows.length,
      strict_prior_rows: shadowAudit.strictPriorRows,
      pending_2026_11_13_rows: shadowAudit.pendingRows,
      shadow_target_groups: shadowAudit.targetGroups,
      q144_targets: rows.length,
      all_q144_draws_reconciled: true,
      all_top20_hit_counts_recomputed: true,
      pair_mass_max_abs_error: round(maxPairMassAbsError, 15),
      observed_pairs_per_draw: 10,
      upstream_q145_verifier: upstream.status
    },
    sample: { targets: rows.length, discovery: 18, validation: 6, historical_blind_oos: 7, app_targets: rows.filter(r => r.models.app).length },
    splits,
    blind_inference: {
      raw_p_values: rawP,
      holm_adjusted_p_values: adjustedP,
      bootstrap_ci_95: bootstrapCI,
      bootstrap_replicates: Q146.bootstrapReplicates,
      circular_block_length: Q146.blockLength,
      signflip_assignments: 128,
      signflip_assumption: "symmetry/exchangeability of target-level paired score differences",
      multiplicity_family_size: 5,
      caveat: "Historical inference is exploratory, not confirmatory: Q145's PMF transformation was specified after Q144 outcomes were inspected. Blind OOS contains only seven targets."
    },
    decision: "PAIRWISE_CALIBRATION_NOT_ESTABLISHED; KEEP_Q145_FROZEN; HISTORICAL_RESULTS_EXPLORATORY"
  };

  const ledgerHeader = "target_date,actual_numbers,split,borda_pair_brier_gain,borda_pair_composite_log_gain,inclusion_pair_brier_gain,inclusion_pair_composite_log_gain,app_pair_brier_gain,app_pair_composite_log_gain,borda_pair_mass,inclusion_pair_mass,app_pair_mass";
  const ledger = [ledgerHeader, ...rows.map(r => [
    r.date, r.draw.join(" "), r.split,
    round(r.models.borda.brierGain), round(r.models.borda.compositeLogGain),
    round(r.models.inclusion.brierGain), round(r.models.inclusion.compositeLogGain),
    r.models.app ? round(r.models.app.brierGain) : "",
    r.models.app ? round(r.models.app.compositeLogGain) : "",
    round(r.models.borda.pairMass), round(r.models.inclusion.pairMass),
    r.models.app ? round(r.models.app.pairMass) : ""
  ].join(","))].join("\n") + "\n";
  const reportJson = JSON.stringify(report, null, 2) + "\n";
  const reportMd = renderMarkdown(report);
  const checkpoint = {
    schema_version: "1.0",
    experiment_id: "Q146",
    status: "Q146_COMPUTED_REPLAYABLE_PENDING_DEDICATED_CI",
    branch: "research/q146-pair-inclusion-calibration-20261113",
    parent_commit: "e7abea15977000adff5a1bbe869824e2d28a078a",
    source_blob_shas: sourceHashes,
    sample: report.sample,
    integrity: report.integrity,
    decision: report.decision,
    next_action: "Run dedicated Q146 CI, verify remote readback, keep Q145 prospective freeze unchanged, and reconcile only after official publication."
  };
  const checkpointJson = JSON.stringify(checkpoint, null, 2) + "\n";
  const preregPath = "reports/sequence_agent/q146_pair_inclusion_calibration_preregistration_2026-11-13.md";
  const scriptPath = "scripts/sonar_q146_pair_inclusion_calibration.mjs";
  const testPath = "tests/test_sonar_q146_pair_inclusion_calibration.mjs";
  const workflowPath = ".github/workflows/q146-pair-inclusion-calibration.yml";
  const artifactContent = {
    [preregPath]: read(preregPath),
    [scriptPath]: read(scriptPath),
    [testPath]: read(testPath),
    [workflowPath]: read(workflowPath),
    [OUT.reportJson]: reportJson,
    [OUT.reportMd]: reportMd,
    [OUT.ledger]: ledger,
    [OUT.checkpoint]: checkpointJson
  };
  const manifest = {
    schema_version: "1.0",
    experiment_id: "Q146",
    branch: "research/q146-pair-inclusion-calibration-20261113",
    status: "Q146_DETERMINISTIC_ARTIFACT_MANIFEST",
    source_blob_shas: sourceHashes,
    artifact_blob_shas: Object.fromEntries(Object.entries(artifactContent).map(([p, content]) => [p, gitBlobSha1(content)])),
    no_canonical_archive_or_existing_freeze_modified: true,
    q145_freeze_unchanged: true,
    no_engine_promotion: true
  };
  const manifestJson = JSON.stringify(manifest, null, 2) + "\n";
  return { report, reportJson, reportMd, ledger, checkpointJson, manifestJson };
}

export function writeArtifacts() {
  const b = buildArtifacts();
  for (const [p, content] of Object.entries({
    [OUT.reportJson]: b.reportJson, [OUT.reportMd]: b.reportMd, [OUT.ledger]: b.ledger,
    [OUT.checkpoint]: b.checkpointJson, [OUT.manifest]: b.manifestJson
  })) {
    fs.mkdirSync(path.dirname(path.join(ROOT, p)), { recursive: true });
    fs.writeFileSync(path.join(ROOT, p), content);
  }
  return verifyArtifacts();
}

export function verifyArtifacts() {
  const b = buildArtifacts();
  const expected = {
    [OUT.reportJson]: b.reportJson, [OUT.reportMd]: b.reportMd, [OUT.ledger]: b.ledger,
    [OUT.checkpoint]: b.checkpointJson, [OUT.manifest]: b.manifestJson
  };
  const mismatches = [];
  for (const [p, content] of Object.entries(expected)) {
    if (!fs.existsSync(path.join(ROOT, p)) || fs.readFileSync(path.join(ROOT, p), "utf8") !== content) mismatches.push(p);
  }
  if (mismatches.length) throw new Error("Q146 deterministic artifact mismatch: " + mismatches.join(", "));
  return {
    status: "Q146_VERIFY_OK",
    targets: b.report.sample.targets,
    blind: b.report.sample.historical_blind_oos,
    strictPriorRows: b.report.integrity.strict_prior_rows,
    pendingRows: b.report.integrity.pending_2026_11_13_rows,
    maxPairMassAbsError: b.report.integrity.pair_mass_max_abs_error,
    artifacts: Object.keys(expected).length
  };
}

if (path.basename(process.argv[1] || "") === "sonar_q146_pair_inclusion_calibration.mjs") {
  const result = process.argv.includes("--write") ? writeArtifacts() : verifyArtifacts();
  process.stdout.write(JSON.stringify(result) + "\n");
}
