import fs from "node:fs";
import crypto from "node:crypto";

const EXPECTED_ARCHIVE_BLOB = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const EXPECTED_LEDGER_BLOB = "50f384ec3fec77ba505d30374daa7e0ddd54afbe";
const EXPECTED_Q100_PROTOCOL_BLOB = "927266f5f5cb3906b0faec7e67ce8955edb1e643";
const EXPECTED_Q100_REPORT_BLOB = "9de459c57e3120958a9bc6ba2de63d00e34f53f2";
const EXPECTED_Q100_VALIDATION_BLOB = "b3498f334007e7b7dd135e9a407409f0f15523ad";
const EXPECTED_SCORER_BLOB = "7ccb9a2abfe452ec535913b70225bc109f692304";
const EXPECTED_ACTIVE_REPORT_BLOB = "ff07b6da4948bb89467067c2552d9b1f78bc9549";
const MONTE_CARLO_REPS = 20000;
const MONTE_CARLO_SEED = 0x5100A101;
const REPLAY_REPS = 1000;
const FAMILY_SIZE = 43;
const DISCOVERY_N = 1921;
const VALIDATION_N = 641;
const BLIND_N = 641;
const WARMUP = 200;
const CENTERS = [3, 8, 13, 18, 23, 28, 33, 38];
const LINEAR = CENTERS.map(x => x - 20.5);
const LINEAR_NORM = LINEAR.reduce((s, x) => s + x * x, 0);
const RESIDUAL_EIGENVALUE = 175 / 312;

function fail(message) { throw new Error("Q101: " + message); }

function gitBlobSha1(text) {
  const body = Buffer.from(text, "utf8");
  return crypto.createHash("sha1")
    .update(Buffer.from("blob " + body.length + "\0", "utf8"))
    .update(body)
    .digest("hex");
}

function parseCsv(text) {
  return text.trimEnd().split(/\r?\n/).map(line => line.split(","));
}

function parseArchive(text) {
  const table = parseCsv(text);
  if (table[0].join(",") !== "data,n1,n2,n3,n4,n5") fail("archive header mismatch");
  const draws = [];
  for (let i = 1; i < table.length; i++) {
    const row = table[i];
    const nums = row.slice(1).map(Number);
    if (row.length !== 6 || !/^\d{4}-\d{2}-\d{2}$/.test(row[0])) fail("malformed archive row " + i);
    if (nums.length !== 5 || nums.some((x, j) => !Number.isInteger(x) || x < 1 || x > 40 || (j && nums[j - 1] >= x))) {
      fail("invalid 5-of-40 archive row " + i);
    }
    if (i > 1 && !(draws[i - 2].date < row[0])) fail("archive dates not strictly increasing");
    draws.push({ date: row[0], nums });
  }
  return draws;
}

function parseLedger(text) {
  const table = parseCsv(text);
  const header = table[0];
  const ix = Object.fromEntries(header.map((name, i) => [name, i]));
  const required = [
    "target_index","target_date","cutoff_date","max_training_outcome_index","split",
    "draw_numbers","draw_ranks","rank_sum","mean_rank","gain_vs_exact_null",
    "top5_hits","top10_hits","top20_hits",
    "bin1_rank1_5_hits","bin2_rank6_10_hits","bin3_rank11_15_hits","bin4_rank16_20_hits",
    "bin5_rank21_25_hits","bin6_rank26_30_hits","bin7_rank31_35_hits","bin8_rank36_40_hits"
  ];
  if (required.some(k => ix[k] === undefined)) fail("Q100 ledger header missing required columns");
  return table.slice(1).map((r, i) => ({
    target_index: Number(r[ix.target_index]),
    target_date: r[ix.target_date],
    cutoff_date: r[ix.cutoff_date],
    max_training_outcome_index: Number(r[ix.max_training_outcome_index]),
    split: r[ix.split],
    draw_numbers: r[ix.draw_numbers].split(" ").map(Number),
    draw_ranks: r[ix.draw_ranks].split(" ").map(Number),
    rank_sum: Number(r[ix.rank_sum]),
    mean_rank: Number(r[ix.mean_rank]),
    gain: Number(r[ix.gain_vs_exact_null]),
    top5_hits: Number(r[ix.top5_hits]),
    top10_hits: Number(r[ix.top10_hits]),
    top20_hits: Number(r[ix.top20_hits]),
    bins: required.slice(13).map(k => Number(r[ix[k]]))
  }));
}

function expectedSplit(ordinal) {
  return ordinal < DISCOVERY_N ? "discovery" :
    ordinal < DISCOVERY_N + VALIDATION_N ? "validation" : "historical_blind_oos";
}

function validateAndAggregate(draws, rows, q100Report) {
  if (draws.length !== 3403 || draws[0].date !== "2017-07-17" || draws.at(-1).date !== "2026-11-09") {
    fail("canonical archive cutoff mismatch");
  }
  if (rows.length !== DISCOVERY_N + VALIDATION_N + BLIND_N) fail("Q100 ledger target count mismatch");
  const counts = { discovery: 0, validation: 0, historical_blind_oos: 0 };
  let cutoffErrors = 0, actualErrors = 0, rankErrors = 0, summaryErrors = 0, splitErrors = 0;
  for (let ordinal = 0; ordinal < rows.length; ordinal++) {
    const row = rows[ordinal];
    const t = WARMUP + ordinal;
    const target = draws[t];
    if (!target || row.target_index !== t || row.target_date !== target.date ||
        row.cutoff_date !== draws[t - 1].date || row.max_training_outcome_index !== t - 1) cutoffErrors++;
    if (!target || row.draw_numbers.join(" ") !== target.nums.join(" ")) actualErrors++;
    if (row.draw_ranks.length !== 5 || new Set(row.draw_ranks).size !== 5 ||
        row.draw_ranks.some(x => !Number.isInteger(x) || x < 1 || x > 40)) rankErrors++;
    const bins = Array(8).fill(0);
    row.draw_ranks.forEach(rank => bins[Math.floor((rank - 1) / 5)]++);
    const rankSum = row.draw_ranks.reduce((a, b) => a + b, 0);
    const top5 = row.draw_ranks.filter(x => x <= 5).length;
    const top10 = row.draw_ranks.filter(x => x <= 10).length;
    const top20 = row.draw_ranks.filter(x => x <= 20).length;
    if (bins.some((x, i) => x !== row.bins[i]) || rankSum !== row.rank_sum ||
        Math.abs(rankSum / 5 - row.mean_rank) > 1e-12 ||
        Math.abs((20.5 - rankSum / 5) - row.gain) > 1e-12 ||
        top5 !== row.top5_hits || top10 !== row.top10_hits || top20 !== row.top20_hits) summaryErrors++;
    const split = expectedSplit(ordinal);
    if (row.split !== split) splitErrors++;
    counts[split]++;
  }
  if (cutoffErrors || actualErrors || rankErrors || summaryErrors || splitErrors) {
    fail("ledger reconciliation failed: " + JSON.stringify({ cutoffErrors, actualErrors, rankErrors, summaryErrors, splitErrors }));
  }
  if (counts.discovery !== DISCOVERY_N || counts.validation !== VALIDATION_N || counts.historical_blind_oos !== BLIND_N) {
    fail("chronological split counts mismatch");
  }

  const splitRows = {
    discovery: rows.slice(0, DISCOVERY_N),
    validation: rows.slice(DISCOVERY_N, DISCOVERY_N + VALIDATION_N),
    historical_blind_oos: rows.slice(DISCOVERY_N + VALIDATION_N)
  };
  const result = {};
  for (const [name, subset] of Object.entries(splitRows)) {
    result[name] = calculateShape(subset);
    const published = q100Report.splits[name];
    const meanBin = result[name].band_counts.map(x => x / subset.length);
    const binErrors = meanBin.map((x, i) => Math.abs(x - published.mean_hits_by_rank_bin_1_5_to_36_40[i]));
    if (binErrors.some(x => x > 1e-12)) fail("Q100 published rank-bin summary mismatch in " + name);
    if (Math.abs(result[name].rank_mean - published.mean_rank) > 1e-12) fail("Q100 mean rank mismatch in " + name);
  }
  return { splitRows, result, counts };
}

function calculateShape(rows) {
  const T = rows.length;
  const bandCounts = Array(8).fill(0);
  let rankSum = 0;
  for (const row of rows) {
    row.bins.forEach((x, i) => bandCounts[i] += x);
    rankSum += row.rank_sum;
  }
  const expected = 0.625 * T;
  const x = bandCounts.map(v => v - expected);
  const beta = x.reduce((s, v, i) => s + v * LINEAR[i], 0) / LINEAR_NORM;
  const residual = x.map((v, i) => v - beta * LINEAR[i]);
  const Q = residual.reduce((s, v) => s + v * v, 0) / (T * RESIDUAL_EIGENVALUE);
  return {
    targets: T,
    rank_mean: rankSum / (5 * T),
    rank_gain: 20.5 - rankSum / (5 * T),
    band_counts: bandCounts,
    expected_per_band: expected,
    residual_hits_per_target: residual.map(v => v / T),
    Q,
    Q_over_df: Q / 6,
    linear_beta: beta / T
  };
}

function choose(n, k) {
  if (k < 0 || k > n) return 0;
  let out = 1;
  for (let i = 1; i <= k; i++) out = out * (n - i + 1) / i;
  return out;
}

function makeCompositions() {
  const out = [];
  function visit(pos, left, values, weight) {
    if (pos === 7) {
      out.push({ values: [...values, left], weight: weight * choose(5, left) });
      return;
    }
    for (let k = 0; k <= Math.min(5, left); k++) {
      visit(pos + 1, left - k, [...values, k], weight * choose(5, k));
    }
  }
  visit(0, 5, [], 1);
  return out;
}

function makeAlias(compositions) {
  const total = compositions.reduce((s, x) => s + x.weight, 0);
  if (total !== 658008) fail("multivariate hypergeometric weights do not sum to 658008");
  const n = compositions.length;
  const prob = new Float64Array(n);
  const alias = new Int32Array(n);
  const scaled = compositions.map(x => x.weight * n / total);
  const small = [], large = [];
  for (let i = 0; i < n; i++) (scaled[i] < 1 ? small : large).push(i);
  while (small.length && large.length) {
    const s = small.pop(), l = large.pop();
    prob[s] = scaled[s];
    alias[s] = l;
    scaled[l] = scaled[l] + scaled[s] - 1;
    (scaled[l] < 1 ? small : large).push(l);
  }
  for (const i of [...small, ...large]) { prob[i] = 1; alias[i] = i; }
  return { prob, alias, total };
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

function simulateQ(T, reps, seed, observedQ, compositions, aliasTable) {
  const rng = makeRng(seed);
  let extreme = 0;
  const values = new Float64Array(reps);
  const { prob, alias } = aliasTable;
  const m = compositions.length;
  for (let rep = 0; rep < reps; rep++) {
    const counts = new Int32Array(8);
    for (let t = 0; t < T; t++) {
      const u = rng() * m;
      const i = Math.floor(u);
      const j = (u - i) < prob[i] ? i : alias[i];
      const v = compositions[j].values;
      for (let b = 0; b < 8; b++) counts[b] += v[b];
    }
    const expected = 0.625 * T;
    let dot = 0;
    for (let b = 0; b < 8; b++) dot += (counts[b] - expected) * LINEAR[b];
    const beta = dot / LINEAR_NORM;
    let q = 0;
    for (let b = 0; b < 8; b++) {
      const residual = (counts[b] - expected) - beta * LINEAR[b];
      q += residual * residual;
    }
    q /= T * RESIDUAL_EIGENVALUE;
    values[rep] = q;
    if (q >= observedQ) extreme++;
  }
  values.sort();
  const p = (extreme + 1) / (reps + 1);
  return {
    replicates: reps,
    extreme,
    p,
    mc_se: Math.sqrt(p * (1 - p) / (reps + 1)),
    null_q95: values[Math.floor(0.95 * (reps - 1))],
    null_q99: values[Math.floor(0.99 * (reps - 1))]
  };
}

export function runQ101(options = {}) {
  const root = options.root ?? process.cwd();
  const reps = options.replicates ?? MONTE_CARLO_REPS;
  const archiveText = fs.readFileSync(root + "/data/storico_daily.csv", "utf8");
  const ledgerText = fs.readFileSync(root + "/reports/sequence_agent/q101_source_q100_rank_ledger_2026-11-10.csv", "utf8");
  const q100ProtocolText = fs.readFileSync(root + "/reports/sequence_agent/q101_source_q100_protocol_2026-11-10.json", "utf8");
  const q100ReportText = fs.readFileSync(root + "/reports/sequence_agent/q101_source_q100_report_2026-11-10.json", "utf8");
  const q100ValidationText = fs.readFileSync(root + "/reports/sequence_agent/q101_source_q100_validation_2026-11-10.json", "utf8");
  const scorerText = fs.readFileSync(root + "/src/VinciCasaLab.jsx", "utf8");
  const activeReportText = fs.readFileSync(root + "/reports/sequence_agent/active_engine_walkforward.json", "utf8");

  const hashes = {
    archive: gitBlobSha1(archiveText),
    source_ledger: gitBlobSha1(ledgerText),
    q100_protocol: gitBlobSha1(q100ProtocolText),
    q100_report: gitBlobSha1(q100ReportText),
    q100_validation: gitBlobSha1(q100ValidationText),
    scorer: gitBlobSha1(scorerText),
    active_report: gitBlobSha1(activeReportText)
  };
  const expected = {
    archive: EXPECTED_ARCHIVE_BLOB,
    source_ledger: EXPECTED_LEDGER_BLOB,
    q100_protocol: EXPECTED_Q100_PROTOCOL_BLOB,
    q100_report: EXPECTED_Q100_REPORT_BLOB,
    q100_validation: EXPECTED_Q100_VALIDATION_BLOB,
    scorer: EXPECTED_SCORER_BLOB,
    active_report: EXPECTED_ACTIVE_REPORT_BLOB
  };
  for (const [key, value] of Object.entries(expected)) if (hashes[key] !== value) fail(key + " blob mismatch: " + hashes[key]);

  const q100Protocol = JSON.parse(q100ProtocolText);
  const q100Report = JSON.parse(q100ReportText);
  const q100Validation = JSON.parse(q100ValidationText);
  const activeReport = JSON.parse(activeReportText);
  if (q100Protocol.experiment_id !== "Q100" || q100Report.experiment_id !== "Q100" ||
      q100Validation.status !== "PASS") fail("Q100 source evidence is not accepted");
  if (q100Validation.provenance.archive_blob_sha !== hashes.archive ||
      q100Validation.provenance.scorer_blob_sha !== hashes.scorer ||
      q100Validation.provenance.active_report_blob_sha !== hashes.active_report) fail("Q100 provenance mismatch");
  if (activeReport.source_git_blob_sha !== hashes.archive ||
      activeReport.implementation_source_blob_sha !== hashes.scorer) fail("active report source mismatch");

  const draws = parseArchive(archiveText);
  const rows = parseLedger(ledgerText);
  const validated = validateAndAggregate(draws, rows, q100Report);
  const blind = validated.splitRows.historical_blind_oos;
  const observedQ = validated.result.historical_blind_oos.Q;
  const compositions = makeCompositions();
  const weightTotal = compositions.reduce((s, x) => s + x.weight, 0);
  const aliasTable = makeAlias(compositions);
  const mc = simulateQ(blind.length, reps, MONTE_CARLO_SEED, observedQ, compositions, aliasTable);
  const replayA = simulateQ(blind.length, REPLAY_REPS, MONTE_CARLO_SEED, observedQ, compositions, aliasTable);
  const replayB = simulateQ(blind.length, REPLAY_REPS, MONTE_CARLO_SEED, observedQ, compositions, aliasTable);
  if (replayA.extreme !== replayB.extreme || replayA.p !== replayB.p) fail("Monte Carlo deterministic replay failed");

  const pAdjusted = Math.min(1, mc.p * FAMILY_SIZE);
  const report = {
    experiment_id: "Q101",
    title: "Nonlinear rank-band shape audit of the active SONAR ranking",
    status: "POST_HOC_EXPLORATORY_NO_NONLINEAR_RANK_SHAPE_LIFT_DEMONSTRATED",
    generated_date: "2026-11-10",
    source: {
      archive: "data/storico_daily.csv",
      archive_blob_sha: hashes.archive,
      q100_rank_ledger_blob_sha: hashes.source_ledger,
      q100_protocol_blob_sha: hashes.q100_protocol,
      q100_report_blob_sha: hashes.q100_report,
      q100_validation_blob_sha: hashes.q100_validation,
      scorer_blob_sha: hashes.scorer,
      active_report_blob_sha: hashes.active_report
    },
    data: {
      draws: draws.length,
      first_date: draws[0].date,
      last_date: draws.at(-1).date,
      warmup_draws: WARMUP,
      targets: rows.length
    },
    integrity: {
      ledger_rows: rows.length,
      strict_prior_cutoff_errors: 0,
      actual_draw_mismatches: 0,
      invalid_rank_vectors: 0,
      rank_summary_mismatches: 0,
      split_mismatches: 0,
      split_counts: validated.counts,
      q100_source_validation_status: q100Validation.status,
      exact_composition_count: compositions.length,
      exact_subset_weight_sum: weightTotal,
      exact_subset_total: aliasTable.total
    },
    splits: validated.result,
    inference: {
      primary_split: "historical_blind_oos",
      primary_statistic: "Residualized nonlinear rank-band shape Q; six-dimensional subspace after projecting out constant and linear rank trend.",
      degrees_of_freedom: 6,
      null_expected_Q: 6,
      observed_Q: observedQ,
      conditional_null: "Exact multivariate hypergeometric composition law for five ranks sampled without replacement from eight bands of five ranks each; 20,000 Monte Carlo replicates; fixed xorshift32 seed; add-one upper-tail p-value.",
      monte_carlo: mc,
      family_size_bonferroni: FAMILY_SIZE,
      p_bonferroni_43: pAdjusted,
      deterministic_replay_1000: { extreme: replayA.extreme, p: replayA.p, identical: true }
    },
    interpretation: "The historical Blind OOS nonlinear rank-band shape statistic is close to its six-degree-of-freedom null scale and is not significant under conditional randomization. The result does not support a stable nonlinear rank-shape signal. This is a post-hoc diagnostic, not independent confirmation.",
    decision: {
      nonlinear_shape_departure_demonstrated: pAdjusted < 0.05,
      predictive_lift_demonstrated: false,
      promotion_allowed: false,
      production_change_allowed: false,
      merge_allowed: false,
      human_review_required: true
    },
    limitations: [
      "Q100 rank-bin means were already disclosed descriptively; Q101 is post-hoc despite its formula and seed being frozen before Q101 scoring.",
      "Historical Blind OOS is not a virgin holdout and has been exposed to prior SONAR research.",
      "The conditional randomization null assumes independent uniform 5-of-40 draws; rankings are treated as fixed conditional on pre-target history.",
      "Bonferroni ×43 is a conservative screen for the catalogued model family and cannot cover unknown analyst degrees of freedom.",
      "A nonlinear rank-shape departure would not by itself establish a profitable or superior five-number ticket."
    ],
    next_action: "Do not tune the active engine from Q101. Continue append-only prospective Q60 collection; evaluate 2026-11-10 freezes only after the official result is verified and appended to the canonical archive."
  };

  const validation = {
    status: "PASS",
    tests: [
      { id: "source_blob_provenance", status: "PASS", detail: "Archive, Q100 protocol/report/validation/ledger, scorer and active report Git blob hashes match the pinned source evidence." },
      { id: "q100_source_validation", status: "PASS", detail: "The pinned Q100 validation artifact reports PASS and its provenance matches the canonical archive, scorer and active report." },
      { id: "canonical_archive_integrity", status: "PASS", detail: "3403 unique chronological draws; every row is a sorted five-number subset of 1..40." },
      { id: "strict_prior_cutoff_reconciliation", status: "PASS", detail: "All 3203 target indices, target dates, previous-day cutoffs and maximum training indices reconcile to the canonical archive." },
      { id: "rank_value_integrity", status: "PASS", detail: "All 3203 five-rank vectors contain five distinct integer ranks in 1..40." },
      { id: "rank_summary_reconciliation", status: "PASS", detail: "Rank sums, means, Top5/Top10/Top20 and eight band counts recompute exactly from the Q100 ledger." },
      { id: "chronological_split_reconciliation", status: "PASS", detail: "1921 Discovery + 641 Validation + 641 historical Blind OOS = 3203 targets." },
      { id: "q100_report_reconciliation", status: "PASS", detail: "Per-band means and mean ranks reconcile to the pinned Q100 report in all three splits." },
      { id: "exact_multivariate_hypergeometric_law", status: "PASS", detail: "All 792 band-count compositions are enumerated; integer weights sum to exactly 658008 five-subsets." },
      { id: "monte_carlo_seed_replay", status: "PASS", detail: "Repeated 1000-replicate runs with the fixed seed produce identical extreme counts and p-values." },
      { id: "conditional_null_full_run", status: "PASS", detail: "The registered 20000-replicate Blind OOS conditional randomization completed." }
    ],
    provenance: hashes,
    checks: {
      cutoff_errors: 0,
      actual_draw_mismatches: 0,
      invalid_rank_vectors: 0,
      rank_summary_mismatches: 0,
      split_mismatches: 0,
      compositions: compositions.length,
      subset_weight_sum: weightTotal
    },
    monte_carlo: {
      replicates: reps,
      extreme: mc.extreme,
      p: mc.p,
      replay_extreme_a: replayA.extreme,
      replay_extreme_b: replayB.extreme
    }
  };

  const checkpoint = [
    "# Q101 — nonlinear rank-shape checkpoint (2026-11-10)",
    "",
    "## Status",
    "**POST_HOC_EXPLORATORY_NO_NONLINEAR_RANK_SHAPE_LIFT_DEMONSTRATED.** No engine change, no production change, no merge, no promotion.",
    "",
    "## Recovery / source",
    "- Q100 protocol, report, validation and 3,203-row rank ledger are pinned by Git blob SHA.",
    "- Q100 validation artifact status: PASS; Q101 independently reconciles every ledger row to the canonical archive.",
    "- Q101 uses the same frozen Discovery/Validation/historical Blind OOS split and does not alter any forecast or freeze.",
    "",
    "## Measured result",
    "- Discovery Q: " + validated.result.discovery.Q.toFixed(6) + " (df=6; descriptive).",
    "- Validation Q: " + validated.result.validation.Q.toFixed(6) + " (df=6; descriptive).",
    "- Historical Blind OOS Q: " + observedQ.toFixed(6) + " (null expectation 6).",
    "- Conditional-null Monte Carlo: " + reps + " replicates; extreme=" + mc.extreme + "; p=" + mc.p.toFixed(6) + "; Bonferroni x43=" + pAdjusted.toFixed(6) + ".",
    "- Blind OOS residualized band profile per target: " + validated.result.historical_blind_oos.residual_hits_per_target.map(x => x.toFixed(6)).join(", ") + ".",
    "",
    "## Integrity",
    "- 3,203 strict-prior ledger rows reconciled; zero cutoff, actual, rank, summary or split errors.",
    "- 792 multivariate-hypergeometric band compositions; weights sum to 658,008 exact 5-of-40 subsets.",
    "- Fixed-seed 1,000-replicate replay identical; full conditional-null run completed.",
    "",
    "## Interpretation / next action",
    "- The rank-shape statistic does not show a significant nonlinear departure after removing the linear rank trend.",
    "- This is post-hoc because Q100 bin summaries were already visible; historical Blind OOS is not virgin.",
    "- Stop retrospective rank-shape tuning. Continue Q60 append-only prospective collection; do not score the 2026-11-10 freezes until the official result is verified."
  ].join("\n") + "\n";

  const reportText = JSON.stringify(report, null, 2) + "\n";
  const validationText = JSON.stringify(validation, null, 2) + "\n";
  const scriptText = fs.readFileSync(new URL(import.meta.url), "utf8");
  const protocolText = fs.readFileSync(root + "/reports/sequence_agent/q101_nonlinear_rank_shape_protocol_2026-11-10.json", "utf8");
  const manifest = {
    experiment_id: "Q101",
    status: "PERSISTED_REPLAY_MANIFEST",
    generated_date: "2026-11-10",
    source_blob_sha: hashes,
    output_git_blob_sha: {
      protocol: gitBlobSha1(protocolText),
      script: gitBlobSha1(scriptText),
      report: gitBlobSha1(reportText),
      validation: gitBlobSha1(validationText),
      checkpoint: gitBlobSha1(checkpoint)
    },
    replay: { monte_carlo_replicates: reps, seed: "0x5100A101", deterministic_1000_replay: true }
  };
  const manifestText = JSON.stringify(manifest, null, 2) + "\n";

  if (options.write !== false) {
    const out = root + "/reports/sequence_agent/";
    fs.writeFileSync(out + "q101_nonlinear_rank_shape_report_2026-11-10.json", reportText);
    fs.writeFileSync(out + "q101_nonlinear_rank_shape_validation_2026-11-10.json", validationText);
    fs.writeFileSync(out + "q101_nonlinear_rank_shape_checkpoint_2026-11-10.md", checkpoint);
    fs.writeFileSync(out + "q101_nonlinear_rank_shape_persistence_manifest_2026-11-10.json", manifestText);
  }
  return { report, validation, checkpoint, manifest };
}

if (process.argv[1] && process.argv[1].endsWith("sonar_q101_nonlinear_rank_shape.js")) {
  const result = runQ101();
  console.log(JSON.stringify({
    status: result.report.status,
    split_Q: Object.fromEntries(Object.entries(result.report.splits).map(([k, v]) => [k, v.Q])),
    blind_mc: result.report.inference.monte_carlo,
    adjusted_p: result.report.inference.p_bonferroni_43,
    validation: result.validation.status
  }, null, 2));
}
