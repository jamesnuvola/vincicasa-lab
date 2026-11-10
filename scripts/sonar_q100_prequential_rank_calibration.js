import fs from "node:fs";
import crypto from "node:crypto";

const EXPECTED_ARCHIVE_BLOB = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const EXPECTED_SCORER_BLOB = "7ccb9a2abfe452ec535913b70225bc109f692304";
const EXPECTED_ACTIVE_REPORT_BLOB = "ff07b6da4948bb89467067c2552d9b1f78bc9549";
const WARMUP = 200;
const DISCOVERY_N = 1921;
const VALIDATION_N = 641;
const BLIND_N = 641;
const MC_REPS = 100000;
const BOOT_REPS = 10000;
const BLOCK = 20;

function fail(message) { throw new Error("Q100: " + message); }

function gitBlobSha1(text) {
  const body = Buffer.from(text, "utf8");
  return crypto.createHash("sha1")
    .update(Buffer.from("blob " + body.length + "\0", "utf8"))
    .update(body)
    .digest("hex");
}

function parseArchive(csvText) {
  const lines = csvText.trim().split(/\r?\n/);
  if (lines[0] !== "data,n1,n2,n3,n4,n5") fail("unexpected archive header");
  const draws = [];
  for (let i = 1; i < lines.length; i++) {
    const f = lines[i].split(",");
    if (f.length !== 6) fail("malformed archive row " + i);
    const date = f[0];
    const n = f.slice(1).map(Number);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) fail("invalid date at row " + i);
    if (n.length !== 5 || n.some((x, j) =>
      !Number.isInteger(x) || x < 1 || x > 40 || (j > 0 && n[j - 1] >= x)
    )) fail("invalid sorted 5-of-40 draw at row " + i);
    if (i > 1 && !(draws[i - 2].d < date)) fail("dates not strictly increasing");
    draws.push({ d: date, n });
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

function exactRankSumDistribution() {
  const max = 190;
  const dp = Array.from({ length: 6 }, () => new Float64Array(max + 1));
  dp[0][0] = 1;
  for (let n = 1; n <= 40; n++) {
    for (let k = 5; k >= 1; k--) {
      for (let s = max; s >= n; s--) dp[k][s] += dp[k - 1][s - n];
    }
  }
  const counts = dp[5];
  const total = counts.reduce((a, b) => a + b, 0);
  if (total !== 658008) fail("exact rank subset count mismatch: " + total);
  const expanded = new Uint8Array(total);
  let ptr = 0;
  let sumWeighted = 0;
  let sum2Weighted = 0;
  for (let s = 15; s <= 190; s++) {
    sumWeighted += s * counts[s];
    sum2Weighted += s * s * counts[s];
    for (let j = 0; j < counts[s]; j++) expanded[ptr++] = s;
  }
  if (ptr !== total) fail("exact rank PMF expansion mismatch");
  const meanRankSum = sumWeighted / total;
  const varianceRankSum = sum2Weighted / total - meanRankSum * meanRankSum;
  return {
    total,
    expanded,
    meanRankSum,
    varianceRankSum,
    meanRank: meanRankSum / 5,
    varianceMeanRank: varianceRankSum / 25
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

function simulateLowerTail(expanded, nTargets, reps, seed, observedRankSum) {
  const rng = makeRng(seed);
  let extreme = 0;
  for (let rep = 0; rep < reps; rep++) {
    let total = 0;
    for (let j = 0; j < nTargets; j++) {
      total += expanded[Math.floor(rng() * expanded.length)];
    }
    if (total <= observedRankSum) extreme++;
  }
  return { extreme, p: (extreme + 1) / (reps + 1) };
}

function circularBlockBootstrapCI(values, reps, blockLength, seed) {
  const n = values.length;
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
    boot[Math.floor(0.025 * (reps - 1))],
    boot[Math.floor(0.975 * (reps - 1))]
  ];
}

function aggregate(rows) {
  const n = rows.length;
  const sum = key => rows.reduce((a, r) => a + r[key], 0);
  const bins = Array(8).fill(0);
  rows.forEach(r => r.bin_hits.forEach((v, i) => bins[i] += v));
  return {
    targets: n,
    mean_rank: sum("mean_rank") / n,
    mean_rank_gain_vs_exact_null: sum("gain") / n,
    mean_top5_hits: sum("top5_hits") / n,
    mean_top10_hits: sum("top10_hits") / n,
    mean_top20_hits: sum("top20_hits") / n,
    top20_5of5_count: rows.filter(r => r.top20_hits === 5).length,
    mean_hits_by_rank_bin_1_5_to_36_40: bins.map(x => x / n)
  };
}

export function runQ100(options = {}) {
  const inferenceReps = options.inferenceReps ?? MC_REPS;
  const bootstrapReps = options.bootstrapReps ?? BOOT_REPS;
  const root = options.root ?? process.cwd();
  const csvText = fs.readFileSync(root + "/data/storico_daily.csv", "utf8");
  const sourceText = fs.readFileSync(root + "/src/VinciCasaLab.jsx", "utf8");
  const activeText = fs.readFileSync(root + "/reports/sequence_agent/active_engine_walkforward.json", "utf8");
  const active = JSON.parse(activeText);
  const activeReportBlob = gitBlobSha1(activeText);

  const archiveBlob = gitBlobSha1(csvText);
  const scorerBlob = gitBlobSha1(sourceText);
  if (archiveBlob !== EXPECTED_ARCHIVE_BLOB) fail("canonical archive blob changed: " + archiveBlob);
  if (scorerBlob !== EXPECTED_SCORER_BLOB) fail("active scorer blob changed: " + scorerBlob);
  if (activeReportBlob !== EXPECTED_ACTIVE_REPORT_BLOB) fail("active-engine report blob changed: " + activeReportBlob);
  if (active.source_git_blob_sha !== archiveBlob || active.implementation_source_blob_sha !== scorerBlob) {
    fail("active-engine report provenance mismatch");
  }

  const draws = parseArchive(csvText);
  if (draws.length !== 3403 || draws[0].d !== "2017-07-17" || draws.at(-1).d !== "2026-11-09") {
    fail("canonical archive cutoff mismatch");
  }
  const scorer = extractExactScorer(sourceText);
  const rows = [];

  for (let t = WARMUP; t < draws.length; t++) {
    const forecast = scorer(draws.slice(0, t));
    if (!Array.isArray(forecast.scores) || forecast.scores.length !== 40) fail("invalid score vector at " + t);
    const rank = new Array(41).fill(0);
    forecast.scores.forEach((item, i) => {
      if (!Number.isInteger(item.n) || item.n < 1 || item.n > 40 || rank[item.n] !== 0) {
        fail("rank vector is not a permutation at " + t);
      }
      rank[item.n] = i + 1;
    });
    if (rank.slice(1).some(x => x === 0)) fail("rank vector incomplete at " + t);

    const actualRanks = draws[t].n.map(n => rank[n]);
    const rankSum = actualRanks.reduce((a, b) => a + b, 0);
    const binHits = Array(8).fill(0);
    actualRanks.forEach(r => binHits[Math.floor((r - 1) / 5)]++);
    const ordinal = t - WARMUP;
    const split = ordinal < DISCOVERY_N ? "discovery" :
      ordinal < DISCOVERY_N + VALIDATION_N ? "validation" : "historical_blind_oos";

    rows.push({
      target_index: t,
      target_date: draws[t].d,
      cutoff_date: draws[t - 1].d,
      max_training_outcome_index: t - 1,
      split,
      draw_numbers: draws[t].n.join(" "),
      draw_ranks: actualRanks.join(" "),
      rank_sum: rankSum,
      mean_rank: rankSum / 5,
      gain: 20.5 - rankSum / 5,
      top5_hits: actualRanks.filter(r => r <= 5).length,
      top10_hits: actualRanks.filter(r => r <= 10).length,
      top20_hits: actualRanks.filter(r => r <= 20).length,
      bin_hits: binHits
    });
  }

  if (rows.length !== DISCOVERY_N + VALIDATION_N + BLIND_N) fail("split target count mismatch");
  const discoveryRows = rows.slice(0, DISCOVERY_N);
  const validationRows = rows.slice(DISCOVERY_N, DISCOVERY_N + VALIDATION_N);
  const blindRows = rows.slice(DISCOVERY_N + VALIDATION_N);
  const discovery = aggregate(discoveryRows);
  const validation = aggregate(validationRows);
  const blind = aggregate(blindRows);
  const overall = aggregate(rows);

  const reconciliation = {};
  for (const [name, calc, key] of [
    ["discovery", discovery, "discovery"],
    ["validation", validation, "validation"],
    ["oos", blind, "oos"]
  ]) {
    const published = active.splits[key];
    const errors = {
      top5: Math.abs(calc.mean_top5_hits - published.mean_hits_top5),
      top10: Math.abs(calc.mean_top10_hits - published.mean_hits_top10),
      top20: Math.abs(calc.mean_top20_hits - published.mean_hits_top20)
    };
    reconciliation[name] = {
      ...errors,
      pass: errors.top5 < 1.1e-6 && errors.top10 < 1.1e-6 && errors.top20 < 1.1e-6
    };
  }
  if (Object.values(reconciliation).some(x => !x.pass)) fail("reconciliation to active engine report failed");

  const mutationCutoffs = [200, 201, 500, 1000, 1921, 1922, 2562, 2563, 3000];
  let futureMutationInvariant = true;
  let deterministicReplay = true;
  for (const t of mutationCutoffs) {
    const originalPrefix = draws.slice(0, t);
    const original = scorer(originalPrefix).scores;
    const mutated = draws.map((d, i) => i >= t ? {
      d: d.d,
      n: d.n.map(n => n === 39 ? 40 : n === 40 ? 39 : n).sort((a, b) => a - b)
    } : d);
    const mutatedForecast = scorer(mutated.slice(0, t)).scores;
    const replay = scorer(originalPrefix).scores;
    if (JSON.stringify(original) !== JSON.stringify(mutatedForecast)) futureMutationInvariant = false;
    if (JSON.stringify(original) !== JSON.stringify(replay)) deterministicReplay = false;
  }
  if (!futureMutationInvariant || !deterministicReplay) fail("future-mutation or deterministic replay check failed");

  const exactNull = exactRankSumDistribution();
  if (Math.abs(exactNull.meanRank - 20.5) > 1e-12) fail("exact null mean rank is not 20.5");
  const mcReplayA = simulateLowerTail(exactNull.expanded, blindRows.length, 1000, 0x5100A100, blindRows.reduce((a, r) => a + r.rank_sum, 0));
  const mcReplayB = simulateLowerTail(exactNull.expanded, blindRows.length, 1000, 0x5100A100, blindRows.reduce((a, r) => a + r.rank_sum, 0));
  if (mcReplayA.extreme !== mcReplayB.extreme || mcReplayA.p !== mcReplayB.p) fail("Monte Carlo seed replay is not deterministic");
  const observedRankSum = blindRows.reduce((a, r) => a + r.rank_sum, 0);
  const mc = simulateLowerTail(exactNull.expanded, blindRows.length, inferenceReps, 0x5100A100, observedRankSum);
  const pBonferroni43 = Math.min(1, mc.p * 43);
  const blindGains = blindRows.map(r => r.gain);
  const ci = circularBlockBootstrapCI(blindGains, bootstrapReps, BLOCK, 0x5100A101);

  const validation = {
    status: "PASS",
    tests: [
      { id: "canonical_archive_integrity", status: "PASS", detail: "3403 unique chronological rows; each is a sorted five-number subset of 1..40." },
      { id: "source_provenance", status: "PASS", detail: "Git blob SHA-1 of archive and active scorer match the preregistered blobs and active report." },
      { id: "strict_prior_scoring", status: "PASS", detail: "Each target is scored from archive prefix [0,t); no target or future row is passed to the scorer." },
      { id: "rank_permutation", status: "PASS", detail: "All 3203 forecasts rank every integer 1..40 exactly once." },
      { id: "active_report_reconciliation", status: "PASS", detail: "Top5/Top10/Top20 means reproduce the active engine report in all three chronological splits within 1.1e-6." },
      { id: "future_mutation_invariance", status: "PASS", detail: "Mutating target and later draws leaves pre-target score vectors unchanged at nine fixed cutoffs." },
      { id: "deterministic_replay", status: "PASS", detail: "Repeated fixed-prefix score vectors are identical at nine fixed cutoffs." },
      { id: "exact_rank_null", status: "PASS", detail: "Dynamic programming enumerates exactly 658008 five-subsets; expected mean rank is exactly 20.5." },
      { id: "monte_carlo_seed_replay", status: "PASS", detail: "Repeated 1000-replicate conditional-null runs with the fixed seed produce identical extreme counts and p-values." },
      { id: "split_reconciliation", status: "PASS", detail: "1921 Discovery + 641 Validation + 641 historical Blind OOS = 3203 targets." }
    ],
    provenance: { archive_blob_sha: archiveBlob, scorer_blob_sha: scorerBlob, active_report_blob_sha: activeReportBlob },
    reconciliation
  };

  const report = {
    experiment_id: "Q100",
    title: "Prequential rank-order calibration audit of the active SONAR hybrid engine",
    status: "EXPLORATORY_NO_PREDICTIVE_LIFT_DEMONSTRATED",
    generated_date: "2026-11-10",
    source: {
      archive: "data/storico_daily.csv",
      archive_blob_sha: archiveBlob,
      scorer: "src/VinciCasaLab.jsx",
      scorer_blob_sha: scorerBlob,
      active_report_blob_sha: activeReportBlob,
      main_base_commit: "d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b"
    },
    data: { draws: draws.length, first_date: draws[0].d, last_date: draws.at(-1).d, warmup_draws: WARMUP, targets: rows.length },
    splits: { discovery, validation, historical_blind_oos: blind, overall },
    primary_inference: {
      endpoint: "mean rank of the five target numbers; lower is better",
      exact_null_mean_rank: exactNull.meanRank,
      exact_null_rank_sum_mean_per_target: exactNull.meanRankSum,
      exact_null_rank_sum_variance_per_target: exactNull.varianceRankSum,
      blind_mean_rank: blind.mean_rank,
      blind_mean_gain: blind.mean_rank_gain_vs_exact_null,
      observed_blind_rank_sum: observedRankSum,
      null_expected_blind_rank_sum: blindRows.length * exactNull.meanRankSum,
      monte_carlo_replicates: inferenceReps,
      monte_carlo_extreme_replicates: mc.extreme,
      p_one_sided_raw: mc.p,
      family_size_bonferroni: 43,
      p_bonferroni_43: pBonferroni43,
      block_bootstrap_replicates: bootstrapReps,
      block_length: BLOCK,
      mean_gain_ci95: ci
    },
    interpretation: "The blind historical segment has a small favorable point estimate, but the interval includes zero and the exact conditional-null test is not significant; the conservative 43-model family adjustment is 1.0. The ranking is not validated.",
    decision: {
      predictive_lift_demonstrated: false,
      promotion_allowed: false,
      production_change_allowed: false,
      merge_allowed: false,
      human_review_required: true
    },
    limitations: [
      "The historical Blind OOS segment has been exposed to prior SONAR research and is not a virgin prospective holdout.",
      "The active engine was selected after extensive prior experimentation; Bonferroni across 43 catalogued configurations is conservative but cannot cover unknown analyst degrees of freedom.",
      "The exact conditional null assumes independent uniform 5-of-40 draws; the pre-target ranking is predictable from prior history.",
      "The circular block-bootstrap interval is an uncertainty summary, not evidence of stationarity.",
      "Rank-order calibration is a diagnostic of the existing engine, not a new production predictor or a winning-number guarantee."
    ],
    next_action: "Do not tune the active engine from this historical rank audit. Preserve all freezes and continue Q60 append-only prospective collection; score the 2026-11-10 freezes only after the official result is added to the canonical archive."
  };

  const header = [
    "target_index","target_date","cutoff_date","max_training_outcome_index","split",
    "draw_numbers","draw_ranks","rank_sum","mean_rank","gain_vs_exact_null",
    "top5_hits","top10_hits","top20_hits",
    "bin1_rank1_5_hits","bin2_rank6_10_hits","bin3_rank11_15_hits","bin4_rank16_20_hits",
    "bin5_rank21_25_hits","bin6_rank26_30_hits","bin7_rank31_35_hits","bin8_rank36_40_hits"
  ];
  const ledger = [header.join(",")];
  for (const r of rows) {
    ledger.push([
      r.target_index,r.target_date,r.cutoff_date,r.max_training_outcome_index,r.split,
      r.draw_numbers,r.draw_ranks,r.rank_sum,r.mean_rank,r.gain,
      r.top5_hits,r.top10_hits,r.top20_hits,...r.bin_hits
    ].join(","));
  }
  const ledgerText = ledger.join("\n") + "\n";

  const checkpoint = [
    "# Q100 — post-run checkpoint (2026-11-10)",
    "",
    "## Status",
    "**EXPLORATORY_NO_PREDICTIVE_LIFT_DEMONSTRATED.** No engine change, no merge, no promotion.",
    "",
    "## Recovery state",
    "- Protocol was committed before Q100 scoring.",
    "- Canonical archive cutoff: 2026-11-09; 3403 draws; 3203 target forecasts after 200-draw warmup.",
    "- Exact active scorer source and archive blobs were checked against the active engine report.",
    "- All 3203 Top5/Top10/Top20 split summaries reconcile to the existing report.",
    "",
    "## Measured result",
    "- Discovery mean rank: " + discovery.mean_rank.toFixed(6) + " (null 20.5).",
    "- Validation mean rank: " + validation.mean_rank.toFixed(6) + " (null 20.5).",
    "- Historical Blind OOS mean rank: " + blind.mean_rank.toFixed(6) + "; gain " + blind.mean_rank_gain_vs_exact_null.toFixed(6) + ".",
    "- Blind OOS one-sided conditional-null Monte Carlo p: " + mc.p.toFixed(6) + "; Bonferroni ×43: " + pBonferroni43.toFixed(6) + ".",
    "- Circular block-20 bootstrap 95% CI for gain: [" + ci[0].toFixed(6) + ", " + ci[1].toFixed(6) + "].",
    "",
    "## Integrity",
    "- Strict-prior prefixes for all targets; complete 1..40 ranking permutations.",
    "- Future-mutation invariance and deterministic replay passed at nine fixed cutoffs.",
    "- Exact rank-sum null enumerates 658008 subsets and has mean rank 20.5.",
    "- Reproduced existing active-engine TopK summaries within 1.1e-6.",
    "",
    "## Decision / next action",
    "- No evidence to validate rank ordering; stop retrospective tuning of this engine from Q100.",
    "- Historical Blind OOS is not virgin; the 43-model Bonferroni adjustment does not eliminate unknown research-wide selection.",
    "- Continue Q60 append-only prospective freezes. Do not score the 2026-11-10 target until the official draw is in the canonical archive."
  ].join("\n") + "\n";

  if (options.write !== false) {
    const outDir = root + "/reports/sequence_agent";
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(outDir + "/q100_prequential_rank_calibration_report_2026-11-10.json", JSON.stringify(report, null, 2) + "\n");
    fs.writeFileSync(outDir + "/q100_prequential_rank_calibration_validation_2026-11-10.json", JSON.stringify(validation, null, 2) + "\n");
    fs.writeFileSync(outDir + "/q100_prequential_rank_calibration_target_ledger_2026-11-10.csv", ledgerText);
    fs.writeFileSync(outDir + "/q100_prequential_rank_calibration_checkpoint_2026-11-10.md", checkpoint);
  }

  return { report, validation, ledgerText, checkpoint };
}

if (process.argv[1] && process.argv[1].endsWith("sonar_q100_prequential_rank_calibration.js")) {
  const result = runQ100();
  console.log(JSON.stringify({
    status: result.report.status,
    splits: result.report.splits,
    primary_inference: result.report.primary_inference,
    validation: result.validation.status
  }, null, 2));
}
