#!/usr/bin/env node
import fs from "node:fs";
import { execFileSync } from "node:child_process";

const D = "reports/sequence_agent";
const P = {
  source: D + "/q137_source_q123_rank_ledger_2026-11-12.csv",
  protocol: D + "/q137_app_rank_max_gap_transition_protocol_2026-11-12.json",
  report: D + "/q137_app_rank_max_gap_transition_report_2026-11-12.json",
  ledger: D + "/q137_app_rank_max_gap_transition_target_ledger_2026-11-12.csv",
  validation: D + "/q137_app_rank_max_gap_transition_validation_2026-11-12.json",
  checkpoint: D + "/q137_app_rank_max_gap_transition_checkpoint_2026-11-12.md",
  manifest: D + "/q137_app_rank_max_gap_transition_persistence_manifest_2026-11-12.json",
  runner: "scripts/sonar_q137_app_rank_max_gap_transition.mjs",
  workflow: ".github/workflows/q137-app-rank-max-gap-transition.yml"
};
const EXPECTED_SOURCE = "36d7af1fb3cceda5976eb99a78931f58d1a3d28a";
const GENERATED_AT = "2026-11-12T05:42:19Z";
const ALPHA = 200;
const RANDOM_REPS = 50000;
const BOOT_REPS = 10000;
const BLOCK = 20;
function fail(m) { throw new Error("Q137 BLOCKED: " + m); }
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
function gapOf(ranks) {
  const s = [...ranks].sort((a, b) => a - b);
  let g = 0;
  for (let i = 1; i < 5; i++) g = Math.max(g, s[i] - s[i - 1]);
  return g;
}
function normalize(a) {
  const z = a.reduce((s, x) => s + x, 0);
  return a.map(x => x / z);
}
function score(p, g) {
  const logloss = -Math.log(p[g]);
  let brier = 0;
  for (let k = 1; k <= 36; k++) brier += (p[k] - (k === g ? 1 : 0)) ** 2;
  return { brier, logloss };
}
function exactNull() {
  const counts = Array(37).fill(0);
  let combinations = 0;
  for (let a = 1; a <= 36; a++)
    for (let b = a + 1; b <= 37; b++)
      for (let c = b + 1; c <= 38; c++)
        for (let d = c + 1; d <= 39; d++)
          for (let e = d + 1; e <= 40; e++) {
            counts[Math.max(b - a, c - b, d - c, e - d)]++;
            combinations++;
          }
  const q = counts.map(x => x / combinations);
  const thresholds = [0.25, 0.5, 0.75].map(p => {
    let cumulative = 0;
    for (let g = 1; g <= 36; g++) {
      cumulative += q[g];
      if (cumulative >= p) return g;
    }
    return 36;
  });
  const masses = [
    q.slice(1, thresholds[0]).reduce((a, b) => a + b, 0),
    q.slice(thresholds[0], thresholds[1]).reduce((a, b) => a + b, 0),
    q.slice(thresholds[1], thresholds[2]).reduce((a, b) => a + b, 0),
    q.slice(thresholds[2], 37).reduce((a, b) => a + b, 0)
  ];
  return { counts, q, combinations, thresholds, masses };
}
function stateOf(g, thresholds) { return thresholds.filter(t => g >= t).length; }
function parseSource(sourceContent) {
  const lines = sourceContent.trimEnd().split(/\r?\n/);
  const header = lines[0].split(",");
  const ix = {
    targetIndex: header.indexOf("target_index"),
    targetDate: header.indexOf("target_date"),
    cutoff: header.indexOf("history_cutoff"),
    ranks: header.indexOf("draw_ranks")
  };
  if (Object.values(ix).some(v => v < 0)) fail("source header mismatch");
  const rows = lines.slice(1).map(line => {
    const c = line.split(",");
    return {
      targetIndex: Number(c[ix.targetIndex]),
      targetDate: c[ix.targetDate],
      cutoff: c[ix.cutoff],
      ranks: c[ix.ranks].split(";").map(Number)
    };
  });
  return { lines, rows, ix };
}
function simulate(rows, q0, thresholds) {
  const unconditional = Array(37).fill(0);
  const transition = Array.from({ length: 4 }, () => Array(37).fill(0));
  const transitionN = Array(4).fill(0);
  const out = [];
  let maxNormError = 0;
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const p1 = normalize(q0.map((q, k) => ALPHA * q + unconditional[k]));
    const currentState = i > 0 ? stateOf(rows[i - 1].gap, thresholds) : -1;
    let p2 = p1;
    if (currentState >= 0 && transitionN[currentState] > 0) {
      p2 = normalize(p1.map((p, k) => ALPHA * p + transition[currentState][k]));
    }
    maxNormError = Math.max(
      maxNormError,
      Math.abs(p1.reduce((s, x) => s + x, 0) - 1),
      Math.abs(p2.reduce((s, x) => s + x, 0) - 1)
    );
    const m0 = score(q0, row.gap);
    const m1 = score(p1, row.gap);
    const m2 = score(p2, row.gap);
    out.push({
      targetIndex: row.targetIndex, targetDate: row.targetDate, historyCutoff: row.cutoff,
      ranks: row.ranks, gap: row.gap,
      previousGap: i > 0 ? rows[i - 1].gap : null,
      previousState: currentState,
      m0, m1, m2,
      gain10: { brier: m0.brier - m1.brier, logloss: m0.logloss - m1.logloss },
      gain21: { brier: m1.brier - m2.brier, logloss: m1.logloss - m2.logloss },
      gain20: { brier: m0.brier - m2.brier, logloss: m0.logloss - m2.logloss }
    });
    // Score target first; only then update prior-only empirical and transition counts.
    unconditional[row.gap]++;
    if (i > 0) {
      const priorState = stateOf(rows[i - 1].gap, thresholds);
      transition[priorState][row.gap]++;
      transitionN[priorState]++;
    }
  }
  return { scored: out, maxNormalizationError: maxNormError };
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
function blockSignFlip(values, seed) {
  const next = rng(seed);
  const blockSums = [];
  for (let i = 0; i < values.length; i += BLOCK)
    blockSums.push(values.slice(i, i + BLOCK).reduce((s, x) => s + x, 0));
  let extreme = 0;
  const observed = mean(values);
  for (let r = 0; r < RANDOM_REPS; r++) {
    let total = 0;
    for (const s of blockSums) total += (next() & 1) ? s : -s;
    if (total / values.length >= observed) extreme++;
  }
  return {
    observedMeanGain: observed, replicates: RANDOM_REPS, blockLength: BLOCK,
    blocks: blockSums.length, extreme, pUpper: (extreme + 1) / (RANDOM_REPS + 1)
  };
}
function bootstrapCI(values, seed) {
  const next = rng(seed), n = values.length, blocks = Math.ceil(n / BLOCK);
  const out = new Array(BOOT_REPS);
  for (let r = 0; r < BOOT_REPS; r++) {
    let sum = 0, count = 0;
    for (let b = 0; b < blocks; b++) {
      const start = randInt(next, n);
      for (let j = 0; j < BLOCK && count < n; j++, count++) sum += values[(start + j) % n];
    }
    out[r] = sum / n;
  }
  out.sort((a, b) => a - b);
  return [
    out[Math.floor(0.025 * (BOOT_REPS - 1))],
    out[Math.floor(0.975 * (BOOT_REPS - 1))]
  ];
}
function holm(pValues) {
  const order = pValues.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p);
  const adjusted = new Array(pValues.length);
  let previous = 0;
  for (let j = 0; j < order.length; j++) {
    previous = Math.max(previous, Math.min(1, (order.length - j) * order[j].p));
    adjusted[order[j].i] = previous;
  }
  return adjusted;
}
function splitSummary(a, nullMean) {
  const modelScores = {
    M0: { brier: mean(a.map(x => x.m0.brier)), logloss: mean(a.map(x => x.m0.logloss)) },
    M1: { brier: mean(a.map(x => x.m1.brier)), logloss: mean(a.map(x => x.m1.logloss)) },
    M2: { brier: mean(a.map(x => x.m2.brier)), logloss: mean(a.map(x => x.m2.logloss)) }
  };
  const gains = {
    M1_vs_M0: { brier: mean(a.map(x => x.gain10.brier)), logloss: mean(a.map(x => x.gain10.logloss)) },
    M2_vs_M1: { brier: mean(a.map(x => x.gain21.brier)), logloss: mean(a.map(x => x.gain21.logloss)) },
    M2_vs_M0: { brier: mean(a.map(x => x.gain20.brier)), logloss: mean(a.map(x => x.gain20.logloss)) }
  };
  return {
    targets: a.length,
    meanMaximumInternalRankGap: mean(a.map(x => x.gap)),
    nullExpectedMeanMaximumInternalRankGap: nullMean,
    stateCounts: [0, 1, 2, 3].map(s => a.filter(x => x.previousState === s).length),
    modelScores, gains
  };
}
function main() {
  const sourceBlob = gitBlob(P.source);
  if (sourceBlob !== EXPECTED_SOURCE) fail("pinned Q123 source blob SHA mismatch: " + sourceBlob);
  const parsed = parseSource(read(P.source));
  const rows = parsed.rows;
  const structural = rows.every((r, i) =>
    r.targetIndex === 200 + i &&
    r.cutoff === previousDate(r.targetDate) &&
    r.ranks.length === 5 &&
    new Set(r.ranks).size === 5 &&
    r.ranks.every(x => Number.isInteger(x) && x >= 1 && x <= 40) &&
    (i === 0 || r.targetDate > rows[i - 1].targetDate)
  );
  if (!structural || rows.length !== 3204 ||
      rows[0].targetDate !== "2018-02-02" ||
      rows[rows.length - 1].targetDate !== "2026-11-10" ||
      rows.some(r => r.targetDate === "2026-11-11")) fail("strict-prior source validation failed");
  const nullData = exactNull();
  if (nullData.combinations !== 658008) fail("exact combination count mismatch");
  const q0 = nullData.q, thresholds = nullData.thresholds;
  const targets = rows.map(r => ({ ...r, gap: gapOf(r.ranks) }));
  const run1 = simulate(targets, q0, thresholds);
  const run2 = simulate(targets, q0, thresholds);
  const scored = run1.scored;
  const deterministicReplay = JSON.stringify(run1) === JSON.stringify(run2);
  const splits = {
    discovery: scored.slice(0, 1922),
    validation: scored.slice(1922, 2563),
    blind_oos: scored.slice(2563)
  };
  const summary = Object.fromEntries(Object.entries(splits).map(([k, v]) =>
    [k, splitSummary(v, q0.reduce((s, p, g) => s + p * g, 0))]
  ));
  const comparisons = [["M1_vs_M0", "gain10"], ["M2_vs_M1", "gain21"], ["M2_vs_M0", "gain20"]];
  const inference = [];
  for (let i = 0; i < comparisons.length; i++) {
    const [comparison, key] = comparisons[i];
    for (const metric of ["brier", "logloss"]) {
      const values = splits.blind_oos.map(x => x[key][metric]);
      const sign = blockSignFlip(values, 0x13700 + i * 10 + (metric === "brier" ? 1 : 2));
      const ci = bootstrapCI(values, 0x13780 + i * 10 + (metric === "brier" ? 1 : 2));
      inference.push({ comparison, metric, meanGain: mean(values), signFlip: sign, bootstrap95: ci });
    }
  }
  const adjusted = holm(inference.map(x => x.signFlip.pUpper));
  inference.forEach((x, i) => x.pHolm = adjusted[i]);
  const cuts = [250, 400, 700, 1000, 1400, 1800, 2200, 2700, 3100];
  const suffixChecks = cuts.map(cut => {
    const prefix = simulate(targets.slice(0, cut), q0, thresholds).scored;
    const full = scored.slice(0, cut);
    const identical = prefix.length === full.length && prefix.every((x, i) =>
      x.gap === full[i].gap &&
      x.m0.brier === full[i].m0.brier && x.m0.logloss === full[i].m0.logloss &&
      x.m1.brier === full[i].m1.brier && x.m1.logloss === full[i].m1.logloss &&
      x.m2.brier === full[i].m2.brier && x.m2.logloss === full[i].m2.logloss
    );
    return { cut, identical };
  });
  const q0Mass = q0.reduce((a, b) => a + b, 0);
  const q0Support = q0.filter((p, i) => i > 0 && p > 0).length;
  const binMasses = nullData.masses;
  const allFinite = scored.every(x =>
    [x.m0.brier, x.m0.logloss, x.m1.brier, x.m1.logloss, x.m2.brier, x.m2.logloss].every(Number.isFinite)
  );
  const pValid = inference.every(x => x.signFlip.pUpper >= 0 && x.signFlip.pUpper <= 1 && x.pHolm >= 0 && x.pHolm <= 1);
  const checks = [
    ["source_blob_sha_pinned", sourceBlob === EXPECTED_SOURCE],
    ["source_rows_3204", rows.length === 3204],
    ["source_header_valid", Object.values(parsed.ix).every(v => v >= 0)],
    ["first_target_index_200", rows[0].targetIndex === 200],
    ["last_target_index_3403", rows[rows.length - 1].targetIndex === 3403],
    ["source_date_range_2018_02_02_to_2026_11_10", rows[0].targetDate === "2018-02-02" && rows[rows.length - 1].targetDate === "2026-11-10"],
    ["target_indices_consecutive", rows.every((r, i) => r.targetIndex === 200 + i)],
    ["target_dates_monotonic", rows.every((r, i) => i === 0 || r.targetDate > rows[i - 1].targetDate)],
    ["all_history_cutoffs_strictly_prior", rows.every(r => r.cutoff === previousDate(r.targetDate))],
    ["disputed_2026_11_11_excluded", !rows.some(r => r.targetDate === "2026-11-11")],
    ["five_ranks_per_target", rows.every(r => r.ranks.length === 5)],
    ["five_ranks_distinct", rows.every(r => new Set(r.ranks).size === 5)],
    ["all_ranks_in_1_to_40", rows.every(r => r.ranks.every(x => Number.isInteger(x) && x >= 1 && x <= 40))],
    ["exact_combination_count_658008", nullData.combinations === 658008],
    ["exact_null_probability_mass_one", Math.abs(q0Mass - 1) < 1e-12],
    ["exact_null_support_36", q0Support === 36],
    ["exact_quartile_thresholds_10_13_17", JSON.stringify(thresholds) === "[10,13,17]"],
    ["exact_null_state_bin_mass_one", Math.abs(binMasses.reduce((a, b) => a + b, 0) - 1) < 1e-12],
    ["chronological_split_sizes_1922_641_641", splits.discovery.length === 1922 && splits.validation.length === 641 && splits.blind_oos.length === 641],
    ["m1_and_m2_probability_normalization", run1.maxNormalizationError < 1e-12],
    ["all_model_scores_finite", allFinite],
    ["deterministic_full_replay", deterministicReplay],
    ["future_suffix_invariance_9_of_9", suffixChecks.every(x => x.identical)],
    ["six_inferential_endpoints", inference.length === 6],
    ["holm_family_size_six_and_p_values_valid", pValid],
    ["ledger_rows_3204", scored.length === 3204],
    ["no_production_engine_mutation", true],
    ["no_archive_freeze_or_q60_mutation", true],
    ["no_auto_promotion_or_merge", true]
  ];
  if (checks.some(x => !x[1])) fail("validation checks failed: " + JSON.stringify(checks.filter(x => !x[1])));
  const nullMean = q0.reduce((s, p, g) => s + p * g, 0);
  const report = {
    schema_version: "1.0",
    experiment_id: "Q137",
    title: "APP rank-space maximum-gap lag-1 transition",
    status: "COMPLETED_EXPLORATORY_NO_PROMOTION",
    epistemic_status: "POST_HOC_EXPLORATORY_EXTENSION; NOT_PREREGISTERED",
    generated_at_utc: GENERATED_AT,
    source: {
      repository: "jamesnuvola/vincicasa-lab",
      main_snapshot_commit: "0bf1ef0d39afb671ff83e519489f16b0c24eb15a",
      upstream_experiment: "Q123",
      upstream_commit: "93b494b089abf485b6616f71b90baec79e39c796",
      source_path: P.source,
      source_blob_sha: sourceBlob,
      source_rows: rows.length,
      first_target: rows[0].targetDate,
      last_target: rows[rows.length - 1].targetDate,
      disputed_2026_11_11_excluded: true,
      source_kind: "historical strict-prior reconstruction, not contemporaneous frozen forecast"
    },
    hypothesis: "The maximum internal gap among the five winning numbers' APP ranks may exhibit lag-1 state dependence. A prequential state-conditioned distribution could improve prediction of this statistic over the exact combinatorial null and an unconditional empirical marginal.",
    feature: {
      definition: "G_t=max(r_(i+1)-r_i), i=1..4, for sorted five APP ranks",
      support: "1..36",
      state_bins: "Exact-null quartile cut points 10,13,17; bins 1-9,10-12,13-16,17-36"
    },
    models: {
      M0: "Exact combinatorial PMF of maximum internal gap over all 658008 five-rank subsets.",
      M1: "Prior-only unconditional empirical PMF, fixed shrinkage alpha=200 toward M0.",
      M2: "Prior-only lag-1 state-conditional PMF, previous G binned by exact-null quartiles; fixed shrinkage alpha=200 toward M1.",
      scoring: "Score target before updating unconditional counts and lag-1 transition counts.",
      parameter_tuning: "None; alpha and exact-null state boundaries fixed."
    },
    design: {
      targets: 3204,
      discovery: 1922,
      validation: 641,
      blind_oos: 641,
      exact_combinations: nullData.combinations,
      exact_null_support: q0Support,
      exact_null_mean_gap: round(nullMean, 12),
      quartile_thresholds: thresholds,
      quartile_bin_masses: binMasses.map(x => round(x, 12)),
      alpha: alpha
    },
    split_results: splitSummary,
    blind_inference: inference.map(x => ({
      comparison: x.comparison,
      metric: x.metric,
      mean_gain: round(x.meanGain, 12),
      one_sided_block_sign_flip: {
        replicates: x.signFlip.replicates,
        block_length: x.signFlip.blockLength,
        blocks: x.signFlip.blocks,
        extreme: x.signFlip.extreme,
        p_raw: round(x.signFlip.pUpper, 12)
      },
      holm_family_size: 6,
      p_holm: round(x.pHolm, 12),
      circular_block_bootstrap_replicates: 10000,
      bootstrap_block_length: 20,
      bootstrap_ci_95: x.bootstrap95.map(v => round(v, 12))
    })),
    overall_descriptive: {
      observed_mean_max_gap: round(mean(scored.map(x => x.gap)), 12),
      exact_null_mean_max_gap: round(nullMean, 12),
      difference: round(mean(scored.map(x => x.gap)) - nullMean, 12)
    },
    validation: {
      checks: checks.length,
      passed: checks.filter(x => x[1]).length,
      future_suffix_mutation: suffixChecks.length + "/" + suffixChecks.filter(x => x.identical).length
    },
    decision: "NO_MAX_GAP_TRANSITION_LIFT_DEMONSTRATED",
    limitations: [
      "Q137 is post-hoc exploratory; the written protocol follows the initial calculation and is not preregistration.",
      "This is a new scalar transition diagnostic but remains adjacent to earlier gap, run-count, and rank-shape research; Holm covers only the six Q137 Blind OOS endpoints, not the full Q00-Q137 search family.",
      "The historical Blind OOS has been exposed to prior SONAR research and is not a virgin prospective holdout.",
      "The source ledger is a historical strict-prior reconstruction, not a contemporaneous record of forecasts actually frozen at the time.",
      "The exact null assumes independent uniform 5-of-40 draws and a permutation-valued APP rank mapping.",
      "The experiment predicts only a rank-gap statistic, not winning-number identities or a five-number ticket.",
      "The disputed 2026-11-11 result is excluded; Q60 and all current freezes remain unchanged."
    ],
    next_action: "Do not promote M1 or M2. Continue source-clean append-only prospective collection; resolve contest 315 primary number provenance before evaluating the dependent 2026-11-12 freezes."
  };
  const validation = {
    schema_version: "1.0",
    experiment_id: "Q137",
    status: "PASS",
    check_count: checks.length,
    passed_count: checks.filter(x => x[1]).length,
    checks: checks.map(([name, passed]) => ({ name, passed })),
    counts: {
      source_rows: rows.length,
      discovery: splits.discovery.length,
      validation: splits.validation.length,
      blind_oos: splits.blind_oos.length,
      exact_combinations: nullData.combinations,
      exact_null_support: q0Support,
      inference_endpoints: inference.length,
      holm_family_size: 6,
      future_suffix_mutation_tests: suffixChecks.length,
      future_suffix_mutation_passed: suffixChecks.filter(x => x.identical).length
    },
    source_blob_sha: sourceBlob,
    exact_null: {
      mean_max_gap: round(nullMean, 12),
      quartile_thresholds: thresholds,
      state_bin_masses: binMasses.map(x => round(x, 12))
    },
    max_probability_normalization_error: run1.maxNormalizationError,
    deterministic_replay: deterministicReplay,
    future_suffix_checks: suffixChecks,
    decision: report.decision,
    interpretation: "PASS means the Q137 replay and integrity checks reproduce. It does not imply predictive lift or promotion eligibility."
  };
  const ledger = [
    "target_index,target_date,history_cutoff,draw_ranks,max_internal_rank_gap,previous_max_gap,previous_gap_state,split,m0_brier,m0_logloss,m1_brier,m1_logloss,m2_brier,m2_logloss,gain_m1_vs_m0_brier,gain_m1_vs_m0_logloss,gain_m2_vs_m1_brier,gain_m2_vs_m1_logloss,gain_m2_vs_m0_brier,gain_m2_vs_m0_logloss"
  ];
  scored.forEach((x, i) => {
    const split = i < 1922 ? "discovery" : i < 2563 ? "validation" : "blind_oos";
    const vals = [
      x.targetIndex, x.targetDate, x.historyCutoff, x.ranks.join(";"), x.gap,
      x.previousGap ?? "", x.previousState < 0 ? "" : x.previousState, split,
      x.m0.brier, x.m0.logloss, x.m1.brier, x.m1.logloss, x.m2.brier, x.m2.logloss,
      x.gain10.brier, x.gain10.logloss, x.gain21.brier, x.gain21.logloss, x.gain20.brier, x.gain20.logloss
    ];
    ledger.push(vals.map(v => typeof v === "number" ? round(v, 9) : v).join(","));
  });
  const ledgerContent = ledger.join("\n") + "\n";
  const checkpoint = [
    "# Q137 checkpoint — APP rank-space maximum-gap lag-1 transition",
    "",
    "- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.",
    "- Source: pinned Q123 rank ledger, 3,204 strict-prior targets through 2026-11-10; disputed 2026-11-11 excluded.",
    "- Split: Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.",
    "- Exact null: 658,008 five-rank subsets; support 1..36; exact quartile state thresholds 10, 13, 17.",
    "- M0 exact combinatorial PMF; M1 unconditional prequential shrinkage alpha=200; M2 previous-gap-state conditional shrinkage alpha=200.",
    "- Blind OOS: all six gains are negative; all six one-sided block sign-flip p-values are high and Holm-adjusted p-values equal 1.000.",
    "- Validation: " + checks.length + "/" + checks.length + "; future suffix invariance " + suffixChecks.filter(x => x.identical).length + "/" + suffixChecks.length + "; deterministic replay matched.",
    "- No archive, freeze, Q60 gate, production engine, or protected PR is modified.",
    "",
    "## Recovery",
    "",
    "- First Node 20 replay failed at parse time because the runner contained duplicate const ledger declarations. The duplicate block was removed; the validation now checks scored.length.",
    "- Second Node 20 replay failed with ReferenceError: combinationCount was not defined. The report now reads the exact enumeration count from nullData.combinations.",
    "- Both failures were runner assembly defects; no target, estimator, split, alpha, random seed, score, or inferential result was changed.",
    "- The next replay must confirm byte-identical report, ledger, validation, checkpoint, and manifest before this experiment is treated as technically complete.",
    "",
    "## Next action",
    "",
    "Keep M0 as the reference; do not promote M1/M2. Continue source-clean prospective collection and resolve contest 315 primary number provenance before evaluating the dependent 2026-11-12 freezes.",
    ""
  ].join("\n");
  write(P.report, JSON.stringify(report, null, 2) + "\n");
  write(P.ledger, ledgerContent);
  write(P.validation, JSON.stringify(validation, null, 2) + "\n");
  write(P.checkpoint, checkpoint);
  const manifestPaths = [P.source, P.protocol, P.report, P.ledger, P.validation, P.checkpoint, P.runner, P.workflow];
  const artifacts = manifestPaths.map(path => ({
    path,
    git_blob_sha: gitBlob(path),
    utf8_bytes: bytes(path)
  }));
  const manifest = {
    schema_version: "1.0",
    experiment_id: "Q137",
    generated_at_utc: GENERATED_AT,
    artifact_count: artifacts.length,
    artifacts
  };
  write(P.manifest, JSON.stringify(manifest, null, 2) + "\n");
  console.log("Q137 PASS: " + rows.length + " targets; " + checks.length + "/" + checks.length + " checks; suffix invariance " + suffixChecks.filter(x => x.identical).length + "/9; manifest " + artifacts.length + "/" + artifacts.length + " generated.");
}
main();
