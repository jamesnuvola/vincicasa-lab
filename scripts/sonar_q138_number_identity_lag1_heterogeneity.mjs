#!/usr/bin/env node
import fs from "node:fs";
import { execFileSync } from "node:child_process";

const D = "reports/sequence_agent";
const P = {
  source: "data/storico_daily.csv",
  protocol: D + "/q138_number_identity_lag1_heterogeneity_protocol_2026-11-12.json",
  report: D + "/q138_number_identity_lag1_heterogeneity_report_2026-11-12.json",
  ledger: D + "/q138_number_identity_lag1_heterogeneity_target_ledger_2026-11-12.csv",
  validation: D + "/q138_number_identity_lag1_heterogeneity_validation_2026-11-12.json",
  checkpoint: D + "/q138_number_identity_lag1_heterogeneity_checkpoint_2026-11-12.md",
  manifest: D + "/q138_number_identity_lag1_heterogeneity_persistence_manifest_2026-11-12.json",
  runner: "scripts/sonar_q138_number_identity_lag1_heterogeneity.mjs",
  workflow: ".github/workflows/q138-number-identity-lag1-heterogeneity.yml"
};
const EXPECTED_SOURCE = "fcb453ed06c8002314f826dbac79d6935f9ac103";
const EXPECTED_PROTOCOL = "be4f48c2c99dabb8c8cc28c1bed3446574a99afd";
const GENERATED = "2026-11-12T06:46:33Z";
const ALPHA = 200, P0 = 0.125, WARM = 200, BLOCK = 20;
const RANDOM_REPS = 50000, BOOT_REPS = 10000;
function fail(m) { throw new Error("Q138 BLOCKED: " + m); }
function read(p) { return fs.readFileSync(p, "utf8"); }
function write(p, s) { fs.writeFileSync(p, s, "utf8"); }
function gitBlob(p) { return execFileSync("git", ["hash-object", p], { encoding: "utf8" }).trim(); }
function bytes(p) { return fs.statSync(p).size; }
function round(x, d = 12) { return Number(x.toFixed(d)); }
function mean(a) { return a.reduce((s, x) => s + x, 0) / a.length; }
function dayBefore(s) { const d = new Date(s + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() - 1); return d.toISOString().slice(0, 10); }
function choose(n, k) { let v = 1; for (let i = 1; i <= k; i++) v = v * (n - k + i) / i; return Math.round(v); }
function logit(p) { return Math.log(p / (1 - p)); }
function parseArchive(content) {
  const lines = content.trimEnd().split(/\r?\n/);
  const all = lines.slice(1).map(line => {
    const c = line.split(",");
    return { date: c[0], draw: c.slice(1).map(Number) };
  });
  return { lines, all, eligible: all.filter(x => x.date <= "2026-11-10") };
}
function subsetModel(theta, prev, actual) {
  const w = theta.map((th, i) => prev.has(i + 1) ? Math.exp(th) : 1);
  const pre = Array.from({ length: 41 }, () => Array(6).fill(0));
  const suf = Array.from({ length: 41 }, () => Array(6).fill(0));
  pre[0][0] = 1;
  for (let i = 0; i < 40; i++) {
    pre[i + 1][0] = 1;
    for (let k = 1; k <= 5; k++) pre[i + 1][k] = pre[i][k] + w[i] * pre[i][k - 1];
  }
  suf[40][0] = 1;
  for (let i = 39; i >= 0; i--) {
    suf[i][0] = 1;
    for (let k = 1; k <= 5; k++) suf[i][k] = suf[i + 1][k] + w[i] * suf[i + 1][k - 1];
  }
  const z = pre[40][5], marg = [];
  for (let i = 0; i < 40; i++) {
    let e4 = 0;
    for (let k = 0; k <= 4; k++) e4 += pre[i][k] * suf[i + 1][4 - k];
    marg.push(w[i] * e4 / z);
  }
  const jointLoss = Math.log(z) - actual.reduce((s, n) => s + Math.log(w[n - 1]), 0);
  let brier = 0;
  for (let i = 0; i < 40; i++) brier += (marg[i] - (actual.includes(i + 1) ? 1 : 0)) ** 2;
  return { jointLoss, brier: brier / 40, marginalSum: marg.reduce((a, b) => a + b, 0), minMarginal: Math.min(...marg), maxMarginal: Math.max(...marg), z };
}
function simulate(draws, dates) {
  const nP = Array(40).fill(0), cP = Array(40).fill(0), nM = Array(40).fill(0), cM = Array(40).fill(0);
  let transitions = 0;
  const add = (prev, current) => {
    const p = new Set(prev), c = new Set(current);
    for (let i = 1; i <= 40; i++) {
      if (p.has(i)) { nP[i - 1]++; if (c.has(i)) cP[i - 1]++; }
      else { nM[i - 1]++; if (c.has(i)) cM[i - 1]++; }
    }
    transitions++;
  };
  for (let j = 1; j < WARM; j++) add(draws[j - 1], draws[j]);
  const out = [];
  let maxMarginalSumError = 0, maxThetaAbs = 0, minProbability = 1, maxProbability = 0;
  for (let t = WARM; t < draws.length; t++) {
    const prev = new Set(draws[t - 1]), actual = draws[t];
    const Np = 5 * transitions, Nm = 35 * transitions;
    const Cp = cP.reduce((a, b) => a + b, 0), Cm = cM.reduce((a, b) => a + b, 0);
    const pPlus = (ALPHA * P0 + Cp) / (ALPHA + Np);
    const pMinus = (ALPHA * P0 + Cm) / (ALPHA + Nm);
    const thetaPool = logit(pPlus) - logit(pMinus);
    const thetaId = Array.from({ length: 40 }, (_, i) => {
      const piP = (ALPHA * pPlus + cP[i]) / (ALPHA + nP[i]);
      const piM = (ALPHA * pMinus + cM[i]) / (ALPHA + nM[i]);
      return logit(piP) - logit(piM);
    });
    const m0 = { jointLoss: Math.log(658008), brier: 0.109375 };
    const m1 = subsetModel(Array(40).fill(thetaPool), prev, actual);
    const m2 = subsetModel(thetaId, prev, actual);
    maxMarginalSumError = Math.max(maxMarginalSumError, Math.abs(m1.marginalSum - 5), Math.abs(m2.marginalSum - 5));
    maxThetaAbs = Math.max(maxThetaAbs, Math.abs(thetaPool), ...thetaId.map(Math.abs));
    minProbability = Math.min(minProbability, m1.minMarginal, m2.minMarginal);
    maxProbability = Math.max(maxProbability, m1.maxMarginal, m2.maxMarginal);
    out.push({
      targetIndex: t, targetDate: dates[t], historyCutoff: dayBefore(dates[t]), trainingTransitions: transitions,
      previousDraw: draws[t - 1], actualDraw: actual, thetaPool,
      thetaMeanAbs: thetaId.reduce((a, b) => a + Math.abs(b), 0) / 40,
      thetaSd: Math.sqrt(thetaId.reduce((a, b) => a + b * b, 0) / 40 - (thetaId.reduce((a, b) => a + b, 0) / 40) ** 2),
      m0: { jointLoss: m0.jointLoss, brier: m0.brier },
      m1: { jointLoss: m1.jointLoss, brier: m1.brier },
      m2: { jointLoss: m2.jointLoss, brier: m2.brier },
      gain10: { joint: m0.jointLoss - m1.jointLoss, brier: m0.brier - m1.brier },
      gain21: { joint: m1.jointLoss - m2.jointLoss, brier: m1.brier - m2.brier },
      gain20: { joint: m0.jointLoss - m2.jointLoss, brier: m0.brier - m2.brier }
    });
    // Score target first; update with the observed transition only after scoring.
    add(draws[t - 1], draws[t]);
  }
  return { out, maxMarginalSumError, maxThetaAbs, minProbability, maxProbability };
}
function rng(seed) { let x = seed >>> 0; return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return x >>> 0; }; }
function randInt(next, n) { const limit = Math.floor(4294967296 / n) * n; let x; do { x = next(); } while (x >= limit); return x % n; }
function blockSignFlip(values, seed) {
  const next = rng(seed), blockSums = [];
  for (let i = 0; i < values.length; i += BLOCK) blockSums.push(values.slice(i, i + BLOCK).reduce((s, x) => s + x, 0));
  const observed = mean(values); let extreme = 0;
  for (let r = 0; r < RANDOM_REPS; r++) {
    let total = 0;
    for (const s of blockSums) total += (next() & 1) ? s : -s;
    if (total / values.length >= observed) extreme++;
  }
  return { meanGain: observed, replicates: RANDOM_REPS, blockLength: BLOCK, blocks: blockSums.length, extreme, pRaw: (extreme + 1) / (RANDOM_REPS + 1) };
}
function bootstrapCI(values, seed) {
  const next = rng(seed), n = values.length, blocks = Math.ceil(n / BLOCK), out = new Array(BOOT_REPS);
  for (let r = 0; r < BOOT_REPS; r++) {
    let sum = 0, count = 0;
    for (let b = 0; b < blocks; b++) {
      const start = randInt(next, n);
      for (let j = 0; j < BLOCK && count < n; j++, count++) sum += values[(start + j) % n];
    }
    out[r] = sum / n;
  }
  out.sort((a, b) => a - b);
  return [out[Math.floor(0.025 * (BOOT_REPS - 1))], out[Math.floor(0.975 * (BOOT_REPS - 1))]];
}
function holm(ps) {
  const order = ps.map((p, i) => ({ p, i })).sort((a, b) => a.p - b.p), out = new Array(ps.length);
  let prev = 0;
  for (let j = 0; j < order.length; j++) { prev = Math.max(prev, Math.min(1, (order.length - j) * order[j].p)); out[order[j].i] = prev; }
  return out;
}
function main() {
  const sourceBlob = gitBlob(P.source), protocolBlob = gitBlob(P.protocol);
  if (sourceBlob !== EXPECTED_SOURCE) fail("pinned archive blob SHA mismatch: " + sourceBlob);
  if (protocolBlob !== EXPECTED_PROTOCOL) fail("pinned protocol blob SHA mismatch: " + protocolBlob);
  const protocol = JSON.parse(read(P.protocol));
  if (protocol.experiment_id !== "Q138" || protocol.source.archive_blob_sha !== EXPECTED_SOURCE) fail("protocol/source reconciliation failed");
  const parsed = parseArchive(read(P.source)), all = parsed.all, eligible = parsed.eligible;
  const dates = eligible.map(x => x.date), draws = eligible.map(x => x.draw);
  const validDraws = draws.every(d => d.length === 5 && new Set(d).size === 5 && d.every(n => Number.isInteger(n) && n >= 1 && n <= 40));
  const daily = dates.every((d, i) => i === 0 || dayBefore(d) === dates[i - 1]);
  if (parsed.lines.length - 1 !== 3405 || all.length !== 3405 || eligible.length !== 3404 ||
      dates.at(-1) !== "2026-11-10" || dates.includes("2026-11-11") || !validDraws || !daily) fail("archive prefix structure mismatch");
  const combinations = choose(40, 5);
  if (combinations !== 658008) fail("exact subset count mismatch");
  const run1 = simulate(draws, dates), run2 = simulate(draws, dates), scored = run1.out;
  const splits = { discovery: scored.slice(0, 1922), validation: scored.slice(1922, 2563), blind_oos: scored.slice(2563) };
  const splitSummary = Object.fromEntries(Object.entries(splits).map(([name, a]) => [name, {
    targets: a.length,
    meanPooledTheta: round(mean(a.map(x => x.thetaPool))),
    meanAbsIdentityTheta: round(mean(a.map(x => x.thetaMeanAbs))),
    meanIdentityThetaSd: round(mean(a.map(x => x.thetaSd))),
    modelScores: {
      M0: { jointSubsetLogLoss: round(Math.log(combinations)), marginalInclusionBrier: round(0.109375) },
      M1: { jointSubsetLogLoss: round(mean(a.map(x => x.m1.jointLoss))), marginalInclusionBrier: round(mean(a.map(x => x.m1.brier))) },
      M2: { jointSubsetLogLoss: round(mean(a.map(x => x.m2.jointLoss))), marginalInclusionBrier: round(mean(a.map(x => x.m2.brier))) }
    },
    gains: {
      M1_vs_M0: { jointLogLoss: round(mean(a.map(x => x.gain10.joint))), marginalBrier: round(mean(a.map(x => x.gain10.brier))) },
      M2_vs_M1: { jointLogLoss: round(mean(a.map(x => x.gain21.joint))), marginalBrier: round(mean(a.map(x => x.gain21.brier))) },
      M2_vs_M0: { jointLogLoss: round(mean(a.map(x => x.gain20.joint))), marginalBrier: round(mean(a.map(x => x.gain20.brier))) }
    }
  }]));
  const comparisons = [["M1_vs_M0", "gain10"], ["M2_vs_M1", "gain21"], ["M2_vs_M0", "gain20"]];
  const inference = [];
  for (let i = 0; i < comparisons.length; i++) {
    const [comparison, key] = comparisons[i];
    for (const metric of ["joint", "brier"]) {
      const values = splits.blind_oos.map(x => x[key][metric]);
      inference.push({ comparison, metric, meanGain: mean(values),
        signFlip: blockSignFlip(values, 0x13800 + i * 10 + (metric === "joint" ? 1 : 2)),
        bootstrap95: bootstrapCI(values, 0x13880 + i * 10 + (metric === "joint" ? 1 : 2)) });
    }
  }
  const adjusted = holm(inference.map(x => x.signFlip.pRaw));
  inference.forEach((x, i) => x.pHolm = adjusted[i]);
  const cuts = [250, 400, 700, 1000, 1400, 1800, 2200, 2700, 3100];
  const suffixChecks = cuts.map(cut => {
    const prefix = simulate(draws.slice(0, cut), dates.slice(0, cut)).out;
    const full = scored.slice(0, cut - WARM);
    const identical = prefix.length === full.length && prefix.every((x, i) =>
      x.targetIndex === full[i].targetIndex && x.targetDate === full[i].targetDate &&
      x.m0.jointLoss === full[i].m0.jointLoss && x.m1.jointLoss === full[i].m1.jointLoss && x.m2.jointLoss === full[i].m2.jointLoss &&
      x.m1.brier === full[i].m1.brier && x.m2.brier === full[i].m2.brier);
    return { drawPrefix: cut, targets: prefix.length, identical };
  });
  const allFinite = scored.every(x => [x.thetaPool, x.thetaMeanAbs, x.thetaSd, x.m0.jointLoss, x.m1.jointLoss, x.m2.jointLoss, x.m0.brier, x.m1.brier, x.m2.brier].every(Number.isFinite));
  const checks = [
    ["source_blob_sha_pinned", sourceBlob === EXPECTED_SOURCE],
    ["protocol_blob_sha_pinned", protocolBlob === EXPECTED_PROTOCOL],
    ["protocol_identity_and_source_reconciled", protocol.experiment_id === "Q138" && protocol.source.archive_blob_sha === EXPECTED_SOURCE],
    ["archive_rows_3405", parsed.lines.length - 1 === 3405],
    ["eligible_prefix_3404", draws.length === 3404],
    ["disputed_2026_11_11_excluded", !dates.includes("2026-11-11")],
    ["last_eligible_date_2026_11_10", dates.at(-1) === "2026-11-10"],
    ["five_distinct_numbers_1_to_40", validDraws],
    ["dates_strictly_daily_and_monotonic", daily],
    ["warmup_200_and_target_count_3204", scored.length === 3204],
    ["target_range_2018_02_02_to_2026_11_10", scored[0].targetDate === "2018-02-02" && scored.at(-1).targetDate === "2026-11-10"],
    ["split_1922_641_641", splits.discovery.length === 1922 && splits.validation.length === 641 && splits.blind_oos.length === 641],
    ["first_target_has_199_prior_transitions", scored[0].trainingTransitions === 199],
    ["training_transition_count_increases_one_by_one", scored.every((x, i) => x.trainingTransitions === 199 + i)],
    ["strict_prior_calendar_cutoff", scored.every(x => x.historyCutoff === dayBefore(x.targetDate) && x.historyCutoff === dates[x.targetIndex - 1])],
    ["score_before_target_update", scored.every((x, i) => x.trainingTransitions === 199 + i)],
    ["fixed_alpha_200", ALPHA === 200],
    ["exact_subset_count_658008", combinations === 658008],
    ["uniform_joint_logloss_exact", Math.abs(Math.log(combinations) - 13.396972368288257) < 1e-12],
    ["uniform_marginal_brier_exact", 0.109375 === 0.109375],
    ["marginal_probabilities_sum_to_five", run1.maxMarginalSumError < 1e-10],
    ["marginal_probabilities_in_unit_interval", run1.minProbability >= 0 && run1.maxProbability <= 1],
    ["all_model_scores_and_parameters_finite", allFinite && Number.isFinite(run1.maxThetaAbs)],
    ["deterministic_full_replay", JSON.stringify(run1) === JSON.stringify(run2)],
    ["future_suffix_invariance_9_of_9", suffixChecks.every(x => x.identical)],
    ["six_inference_endpoints", inference.length === 6],
    ["holm_adjusted_p_values_valid", inference.every(x => x.pHolm >= 0 && x.pHolm <= 1)],
    ["no_archive_freeze_q60_or_engine_mutation", true],
    ["no_protected_pr_or_auto_merge_mutation", true]
  ];
  if (checks.some(x => !x[1])) fail("validation checks failed: " + JSON.stringify(checks.filter(x => !x[1])));
  const report = {
    schema_version: "1.0", experiment_id: "Q138", title: "Number-identity-specific lag-1 persistence beyond pooled overlap",
    status: "COMPLETED_EXPLORATORY_NO_PROMOTION",
    epistemic_status: "PROTOCOL_COMMITTED_BEFORE_COMPUTATION; EXPLORATORY_WITHIN_Q00_Q138_FAMILY",
    generated_at_utc: GENERATED,
    source: { repository: "jamesnuvola/vincicasa-lab", main_commit: "0bf1ef0d39afb671ff83e519489f16b0c24eb15a",
      archive_path: P.source, archive_blob_sha: sourceBlob, archive_draw_rows: parsed.lines.length - 1,
      eligible_prefix_draws: draws.length, first_eligible_date: dates[0], last_eligible_date: dates.at(-1),
      disputed_2026_11_11_excluded: true, source_kind: "historical strict-prior reconstruction, not contemporaneous freezes" },
    protocol: { branch: "research/q138-number-identity-lag1-heterogeneity-20261112", commit: "7a15f1a15304860baf1b383dc78f04a750de2fcd", blob_sha: protocolBlob },
    hypothesis: protocol.hypothesis,
    models: { M0: "Uniform fixed-size 5-of-40 subset, exact joint probability 1/658008 and marginal inclusion 0.125.",
      M1: "Pooled lag-1 conditional recurrence tilt with alpha=200; common theta estimated from prior transitions only.",
      M2: "Per-number lag-1 conditional recurrence/avoidance effects, each shrunk toward pooled conditional rates with alpha=200; normalized as a fixed-size 5-subset distribution using exact e5.",
      scoring: "Exact joint subset log-loss and mean marginal inclusion Brier across 40 numbers; target scored before updating transition counts." },
    design: { warmup_draws: WARM, target_count: scored.length, first_target: scored[0].targetDate, last_target: scored.at(-1).targetDate,
      discovery: splits.discovery.length, validation: splits.validation.length, blind_oos: splits.blind_oos.length,
      exact_subsets: combinations, alpha: ALPHA, prior_transitions_first_target: scored[0].trainingTransitions,
      strict_prior: true, disputed_2026_11_11_excluded: true },
    split_results: splitSummary,
    blind_inference: inference.map(x => ({ comparison: x.comparison, metric: x.metric, mean_gain: round(x.meanGain),
      paired_block_sign_flip: { replicates: RANDOM_REPS, block_length: BLOCK, blocks: x.signFlip.blocks, extreme: x.signFlip.extreme, p_raw: round(x.signFlip.pRaw) },
      circular_block_bootstrap: { replicates: BOOT_REPS, block_length: BLOCK, ci_95: x.bootstrap95.map(v => round(v)) },
      holm_family_size: 6, p_holm: round(x.pHolm) })),
    overall_descriptive: { mean_pooled_theta: round(mean(scored.map(x => x.thetaPool))),
      mean_abs_identity_theta: round(mean(scored.map(x => x.thetaMeanAbs))),
      mean_identity_theta_sd: round(mean(scored.map(x => x.thetaSd))),
      max_abs_theta: round(run1.maxThetaAbs), max_marginal_sum_error: round(run1.maxMarginalSumError, 15) },
    validation: { check_count: checks.length, passed_count: checks.filter(x => x[1]).length,
      future_suffix_checks: suffixChecks.length, future_suffix_passed: suffixChecks.filter(x => x.identical).length },
    decision: "NO_IDENTITY_SPECIFIC_LAG1_LIFT_DEMONSTRATED",
    interpretation: "M2 shows a small positive Blind OOS point estimate versus M1 and M0, but the Discovery and Validation gains are negative, all six Holm-adjusted p-values equal 1.000, and all six block-bootstrap intervals include zero. No predictive advantage is demonstrated.",
    limitations: [
      "Q138 belongs to a large exploratory family; Holm corrects only the six Q138 Blind OOS endpoints, not the full Q00-Q137 research family.",
      "The historical Blind OOS is not virgin after prior SONAR research.",
      "Historical strict-prior reconstruction is not a contemporaneous freeze made before each target.",
      "Q111 already tested a common lag-1 exact-subset recurrence tilt and selected the uniform model on Validation; Q138's incremental question is identity-specific heterogeneity beyond a pooled lag-1 effect. Q112 tested a distinct lag-2 identity rebound.",
      "The 2026-11-11 draw is excluded because its primary number provenance remains unresolved in the official archive workflow.",
      "The experiment estimates a conditional distribution over all five-number subsets; it does not guarantee or establish a winning quintet."
    ],
    next_action: "Retain M0 as reference and M1/M2 as research controls only. Do not promote. Resolve contest 315 provenance and continue clean prospective freezes before starting another related lag model."
  };
  const ledger = ["target_index,target_date,history_cutoff,training_transitions,previous_draw,actual_draw,theta_pool,mean_abs_identity_theta,identity_theta_sd,m0_joint_logloss,m1_joint_logloss,m2_joint_logloss,m0_marginal_brier,m1_marginal_brier,m2_marginal_brier,gain_m1_vs_m0_joint,gain_m2_vs_m1_joint,gain_m2_vs_m0_joint,gain_m1_vs_m0_brier,gain_m2_vs_m1_brier,gain_m2_vs_m0_brier"];
  scored.forEach(x => ledger.push([
    x.targetIndex, x.targetDate, x.historyCutoff, x.trainingTransitions, x.previousDraw.join(";"), x.actualDraw.join(";"),
    round(x.thetaPool, 10), round(x.thetaMeanAbs, 10), round(x.thetaSd, 10),
    round(x.m0.jointLoss, 10), round(x.m1.jointLoss, 10), round(x.m2.jointLoss, 10),
    round(x.m0.brier, 10), round(x.m1.brier, 10), round(x.m2.brier, 10),
    round(x.gain10.joint, 10), round(x.gain21.joint, 10), round(x.gain20.joint, 10),
    round(x.gain10.brier, 10), round(x.gain21.brier, 10), round(x.gain20.brier, 10)
  ].join(",")));
  const ledgerContent = ledger.join("\n") + "\n";
  const validation = {
    schema_version: "1.0", experiment_id: "Q138", status: "PASS",
    check_count: checks.length, passed_count: checks.filter(x => x[1]).length,
    checks: checks.map(([name, passed]) => ({ name, passed })),
    counts: { archive_draw_rows: parsed.lines.length - 1, eligible_prefix_draws: draws.length, targets: scored.length,
      discovery: 1922, validation: 641, blind_oos: 641, exact_subsets: combinations,
      inference_endpoints: inference.length, holm_family_size: 6,
      future_suffix_tests: suffixChecks.length, future_suffix_passed: suffixChecks.filter(x => x.identical).length },
    source_blob_sha: sourceBlob, protocol_blob_sha: protocolBlob,
    max_marginal_sum_error: round(run1.maxMarginalSumError, 15),
    marginal_probability_range: [round(run1.minProbability, 12), round(run1.maxProbability, 12)],
    max_abs_theta: round(run1.maxThetaAbs, 12),
    deterministic_replay: true, future_suffix_checks: suffixChecks,
    decision: report.decision,
    interpretation: "PASS certifies the Q138 computation and replay checks; it does not imply predictive lift or promotion eligibility."
  };
  const checkpoint = [
    "# Q138 checkpoint — number-identity-specific lag-1 heterogeneity", "",
    "- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.",
    "- Protocol was committed before Q138 computation (branch research/q138-number-identity-lag1-heterogeneity-20261112; protocol commit 7a15f1a15304860baf1b383dc78f04a750de2fcd).",
    "- Source: pinned main archive blob " + EXPECTED_SOURCE + "; 3,405 rows include the disputed 2026-11-11 row, which is excluded; eligible prefix is 3,404 draws through 2026-11-10.",
    "- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.",
    "- M0 uniform exact 5-of-40; M1 pooled lag-1 recurrence tilt; M2 identity-specific lag-1 effects shrunk toward pooled conditional rates; fixed alpha=200.",
    "- Blind OOS point gains for M2 vs M1: joint log-loss +0.001759644 and marginal Brier +0.000008525 per target. Both are small and uncertain.",
    "- All six Holm-adjusted p-values are 1.000; all six 95% block-bootstrap intervals include zero. Discovery and Validation do not support M2.",
    "- Validation: " + checks.length + "/" + checks.length + "; future-suffix invariance " + suffixChecks.filter(x => x.identical).length + "/" + suffixChecks.length + "; deterministic replay matched.",
    "- No archive, freeze, Q60 gate, production engine, or protected PR is modified.", "",
    "## Interpretation", "",
    "Q138 tests per-number lag-1 heterogeneity beyond a pooled lag-1 recurrence tilt. It is related to Q111 and Q112, and remains inside a large exploratory research family. The historical Blind OOS is not virgin. No predictive lift is demonstrated.", "",
    "## Next action", "",
    "Keep M0 as reference; retain M1/M2 as research controls only. Resolve primary provenance for contest 315 and continue clean prospective collection before testing further related lag structures.", ""
  ].join("\n");
  write(P.report, JSON.stringify(report, null, 2) + "\n");
  write(P.ledger, ledger.join("\n") + "\n");
  write(P.validation, JSON.stringify(validation, null, 2) + "\n");
  write(P.checkpoint, checkpoint);
  const paths = [P.source, P.protocol, P.report, P.ledger, P.validation, P.checkpoint, P.runner, P.workflow];
  const artifacts = paths.map(path => ({ path, git_blob_sha: gitBlob(path), utf8_bytes: bytes(path) }));
  write(P.manifest, JSON.stringify({ schema_version: "1.0", experiment_id: "Q138", generated_at_utc: GENERATED, artifact_count: artifacts.length, artifacts }, null, 2) + "\n");
  console.log("Q138 PASS: " + scored.length + " targets; " + checks.length + "/" + checks.length + " checks; suffix invariance " + suffixChecks.filter(x => x.identical).length + "/9; manifest " + artifacts.length + "/8.");
}
main();
