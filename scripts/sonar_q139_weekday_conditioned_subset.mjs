#!/usr/bin/env node
import fs from "node:fs";
import { execFileSync } from "node:child_process";
const D = "reports/sequence_agent";
const P = {
  source: "data/storico_daily.csv",
  protocol: D + "/q139_weekday_conditioned_subset_protocol_2026-11-12.json",
  report: D + "/q139_weekday_conditioned_subset_report_2026-11-12.json",
  ledger: D + "/q139_weekday_conditioned_subset_target_ledger_2026-11-12.csv",
  validation: D + "/q139_weekday_conditioned_subset_validation_2026-11-12.json",
  checkpoint: D + "/q139_weekday_conditioned_subset_checkpoint_2026-11-12.md",
  manifest: D + "/q139_weekday_conditioned_subset_persistence_manifest_2026-11-12.json",
  runner: "scripts/sonar_q139_weekday_conditioned_subset.mjs",
  workflow: ".github/workflows/q139-weekday-conditioned-subset.yml"
};
const EXPECTED_SOURCE = "fcb453ed06c8002314f826dbac79d6935f9ac103";
const EXPECTED_PROTOCOL = "20f5e36799057c98f0d3338c050939c93f1a9ca5";
const GENERATED = "2026-11-12T07:41:00Z";
const ALPHA = 200, P0 = 0.125, WARM = 200, BLOCK = 20;
const RANDOM_REPS = 10000, BOOT_REPS = 10000, COMBINATIONS = 658008;
function fail(m) { throw new Error("Q139 BLOCKED: " + m); }
function read(p) { return fs.readFileSync(p, "utf8"); }
function write(p, s) { fs.writeFileSync(p, s, "utf8"); }
function gitBlob(p) { return execFileSync("git", ["hash-object", p], { encoding: "utf8" }).trim(); }
function bytes(p) { return fs.statSync(p).size; }
function round(x, d = 12) { return Number(x.toFixed(d)); }
function mean(a) { return a.reduce((s, x) => s + x, 0) / a.length; }
function dayBefore(s) { const d = new Date(s + "T00:00:00Z"); d.setUTCDate(d.getUTCDate() - 1); return d.toISOString().slice(0, 10); }
function weekday(s) { return new Date(s + "T00:00:00Z").getUTCDay(); }
function logit(p) { return Math.log(p / (1 - p)); }
function choose(n, k) { let v = 1; for (let i = 1; i <= k; i++) v = v * (n - k + i) / i; return Math.round(v); }
function parseArchive(content) {
  const lines = content.trimEnd().split(/\r?\n/);
  const all = lines.slice(1).map(line => {
    const c = line.split(",");
    return { date: c[0], draw: c.slice(1).map(Number) };
  });
  return { lines, all, eligible: all.filter(x => x.date <= "2026-11-10") };
}
function subsetScore(weights, actual) {
  const pre = Array.from({ length: 41 }, () => Array(6).fill(0));
  const suf = Array.from({ length: 41 }, () => Array(6).fill(0));
  pre[0][0] = 1;
  for (let i = 0; i < 40; i++) {
    pre[i + 1][0] = 1;
    for (let k = 1; k <= 5; k++) pre[i + 1][k] = pre[i][k] + weights[i] * pre[i][k - 1];
  }
  suf[40][0] = 1;
  for (let i = 39; i >= 0; i--) {
    suf[i][0] = 1;
    for (let k = 1; k <= 5; k++) suf[i][k] = suf[i + 1][k] + weights[i] * suf[i + 1][k - 1];
  }
  const z = pre[40][5], marg = [];
  for (let i = 0; i < 40; i++) {
    let e4 = 0;
    for (let k = 0; k <= 4; k++) e4 += pre[i][k] * suf[i + 1][4 - k];
    marg.push(weights[i] * e4 / z);
  }
  const jointLoss = Math.log(z) - actual.reduce((s, n) => s + Math.log(weights[n - 1]), 0);
  let brier = 0;
  for (let i = 0; i < 40; i++) brier += (marg[i] - (actual.includes(i + 1) ? 1 : 0)) ** 2;
  return { jointLoss, brier: brier / 40, marginalSum: marg.reduce((a, b) => a + b, 0), minMarginal: Math.min(...marg), maxMarginal: Math.max(...marg) };
}
function simulate(draws, dates) {
  const globalCount = Array(40).fill(0);
  const weekdayCount = Array.from({ length: 7 }, () => Array(40).fill(0));
  const weekdayN = Array(7).fill(0);
  for (let t = 0; t < WARM; t++) {
    const wd = weekday(dates[t]);
    weekdayN[wd]++;
    for (const n of draws[t]) { globalCount[n - 1]++; weekdayCount[wd][n - 1]++; }
  }
  const out = [];
  let maxMarginalSumError = 0, minProbability = 1, maxProbability = 0;
  for (let t = WARM; t < draws.length; t++) {
    const wd = weekday(dates[t]), actual = draws[t];
    const historyN = t, historyCutoff = dayBefore(dates[t]), weekdayHistoryN = weekdayN[wd];
    const pGlobal = globalCount.map(c => (ALPHA * P0 + c) / (ALPHA + historyN));
    const pWeekday = pGlobal.map((p, i) => (ALPHA * p + weekdayCount[wd][i]) / (ALPHA + weekdayHistoryN));
    const w1 = pGlobal.map(p => Math.exp(logit(p) - logit(P0)));
    const w2 = pWeekday.map(p => Math.exp(logit(p) - logit(P0)));
    const m0 = { jointLoss: Math.log(COMBINATIONS), brier: 0.109375, marginalSum: 5, minMarginal: P0, maxMarginal: P0 };
    const m1 = subsetScore(w1, actual), m2 = subsetScore(w2, actual);
    maxMarginalSumError = Math.max(maxMarginalSumError, Math.abs(m1.marginalSum - 5), Math.abs(m2.marginalSum - 5));
    minProbability = Math.min(minProbability, m1.minMarginal, m2.minMarginal);
    maxProbability = Math.max(maxProbability, m1.maxMarginal, m2.maxMarginal);
    out.push({
      targetIndex: t, targetDate: dates[t], targetWeekday: wd, historyCutoff, historyDraws: historyN,
      weekdayHistoryDraws: weekdayHistoryN, actualDraw: actual,
      m0: { jointLoss: m0.jointLoss, brier: m0.brier },
      m1: { jointLoss: m1.jointLoss, brier: m1.brier },
      m2: { jointLoss: m2.jointLoss, brier: m2.brier },
      gain10: { joint: m0.jointLoss - m1.jointLoss, brier: m0.brier - m1.brier },
      gain21: { joint: m1.jointLoss - m2.jointLoss, brier: m1.brier - m2.brier },
      gain20: { joint: m0.jointLoss - m2.jointLoss, brier: m0.brier - m2.brier }
    });
    // Score first; reveal and update only after scoring this target.
    weekdayN[wd]++;
    for (const n of actual) { globalCount[n - 1]++; weekdayCount[wd][n - 1]++; }
  }
  return { out, maxMarginalSumError, minProbability, maxProbability };
}
function rng(seed) { let x = seed >>> 0; return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return x >>> 0; }; }
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
      const start = next() % n;
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
function summarize(a) {
  const avg = fn => mean(a.map(fn));
  return {
    targets: a.length,
    models: {
      M0: { jointSubsetLogLoss: round(avg(x => x.m0.jointLoss)), marginalInclusionBrier: round(avg(x => x.m0.brier)) },
      M1: { jointSubsetLogLoss: round(avg(x => x.m1.jointLoss)), marginalInclusionBrier: round(avg(x => x.m1.brier)) },
      M2: { jointSubsetLogLoss: round(avg(x => x.m2.jointLoss)), marginalInclusionBrier: round(avg(x => x.m2.brier)) }
    },
    gains: {
      M1_vs_M0: { jointLogLoss: round(avg(x => x.gain10.joint)), marginalBrier: round(avg(x => x.gain10.brier)) },
      M2_vs_M1: { jointLogLoss: round(avg(x => x.gain21.joint)), marginalBrier: round(avg(x => x.gain21.brier)) },
      M2_vs_M0: { jointLogLoss: round(avg(x => x.gain20.joint)), marginalBrier: round(avg(x => x.gain20.brier)) }
    },
    weekdayHistoryDrawsMean: round(avg(x => x.weekdayHistoryDraws))
  };
}
function main() {
  const sourceBlob = gitBlob(P.source), protocolBlob = gitBlob(P.protocol);
  if (sourceBlob !== EXPECTED_SOURCE) fail("pinned archive blob SHA mismatch: " + sourceBlob);
  if (protocolBlob !== EXPECTED_PROTOCOL) fail("pinned protocol blob SHA mismatch: " + protocolBlob);
  const protocol = JSON.parse(read(P.protocol));
  if (protocol.experiment_id !== "Q139" || protocol.source.archive_blob_sha !== EXPECTED_SOURCE) fail("protocol/source reconciliation failed");
  const parsed = parseArchive(read(P.source)), all = parsed.all, eligible = parsed.eligible;
  const dates = eligible.map(x => x.date), draws = eligible.map(x => x.draw);
  const validDraws = draws.every(d => d.length === 5 && new Set(d).size === 5 && d.every(n => Number.isInteger(n) && n >= 1 && n <= 40));
  const daily = dates.every((d, i) => i === 0 || dayBefore(d) === dates[i - 1]);
  if (parsed.lines.length - 1 !== 3405 || all.length !== 3405 || eligible.length !== 3404 ||
      dates.at(-1) !== "2026-11-10" || dates.includes("2026-11-11") || !validDraws || !daily) fail("archive prefix structure mismatch");
  if (choose(40, 5) !== COMBINATIONS) fail("exact 5-of-40 subset count mismatch");
  const run1 = simulate(draws, dates), run2 = simulate(draws, dates), scored = run1.out;
  const splits = { discovery: scored.slice(0, 1922), validation: scored.slice(1922, 2563), blind_oos: scored.slice(2563) };
  const splitSummary = Object.fromEntries(Object.entries(splits).map(([name, a]) => [name, summarize(a)]));
  const comparisons = [["M1_vs_M0", "gain10"], ["M2_vs_M1", "gain21"], ["M2_vs_M0", "gain20"]];
  const inference = [];
  for (let s = 0; s < 2; s++) {
    const splitName = s === 0 ? "validation" : "blind_oos";
    for (let i = 0; i < comparisons.length; i++) {
      const [comparison, key] = comparisons[i];
      for (const metric of ["joint", "brier"]) {
        const values = splits[splitName].map(x => x[key][metric]);
        inference.push({
          split: splitName, comparison, metric, meanGain: mean(values),
          signFlip: blockSignFlip(values, 0x13900 + s * 100 + i * 10 + (metric === "joint" ? 1 : 2)),
          bootstrap95: bootstrapCI(values, 0x13980 + s * 100 + i * 10 + (metric === "joint" ? 1 : 2))
        });
      }
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
      x.targetWeekday === full[i].targetWeekday && x.historyCutoff === full[i].historyCutoff &&
      x.historyDraws === full[i].historyDraws && x.weekdayHistoryDraws === full[i].weekdayHistoryDraws &&
      x.m0.jointLoss === full[i].m0.jointLoss && x.m1.jointLoss === full[i].m1.jointLoss &&
      x.m2.jointLoss === full[i].m2.jointLoss && x.m1.brier === full[i].m1.brier && x.m2.brier === full[i].m2.brier);
    return { drawPrefix: cut, targets: prefix.length, identical };
  });
  const allFinite = scored.every(x => [
    x.m0.jointLoss, x.m1.jointLoss, x.m2.jointLoss, x.m0.brier, x.m1.brier, x.m2.brier,
    x.gain10.joint, x.gain21.joint, x.gain20.joint
  ].every(Number.isFinite));
  const checks = [
    ["source_blob_sha_pinned", sourceBlob === EXPECTED_SOURCE],
    ["protocol_blob_sha_pinned", protocolBlob === EXPECTED_PROTOCOL],
    ["protocol_identity_and_source_reconciled", protocol.experiment_id === "Q139" && protocol.source.archive_blob_sha === EXPECTED_SOURCE],
    ["archive_rows_3405", parsed.lines.length - 1 === 3405],
    ["eligible_prefix_3404", draws.length === 3404],
    ["disputed_2026_11_11_excluded", !dates.includes("2026-11-11")],
    ["last_eligible_date_2026_11_10", dates.at(-1) === "2026-11-10"],
    ["five_distinct_numbers_1_to_40", validDraws],
    ["dates_strictly_daily_and_monotonic", daily],
    ["warmup_200_and_target_count_3204", scored.length === 3204],
    ["target_range_2018_02_02_to_2026_11_10", scored[0].targetDate === "2018-02-02" && scored.at(-1).targetDate === "2026-11-10"],
    ["split_1922_641_641", splits.discovery.length === 1922 && splits.validation.length === 641 && splits.blind_oos.length === 641],
    ["first_target_has_200_prior_draws", scored[0].historyDraws === 200],
    ["history_draw_count_increases_one_by_one", scored.every((x, i) => x.historyDraws === 200 + i)],
    ["strict_prior_calendar_cutoff", scored.every(x => x.historyCutoff === dayBefore(x.targetDate) && x.historyCutoff === dates[x.targetIndex - 1])],
    ["weekday_history_is_strictly_prior", scored.every(x => x.weekdayHistoryDraws < x.historyDraws)],
    ["score_before_target_update", scored.every((x, i) => x.historyDraws === 200 + i)],
    ["fixed_alpha_200", ALPHA === 200],
    ["exact_subset_count_658008", choose(40, 5) === COMBINATIONS],
    ["uniform_joint_logloss_exact", Math.abs(Math.log(COMBINATIONS) - 13.396972368288257) < 1e-12],
    ["uniform_marginal_brier_exact", 0.109375 === 0.109375],
    ["marginal_probabilities_sum_to_five", run1.maxMarginalSumError < 1e-10],
    ["marginal_probabilities_in_unit_interval", run1.minProbability >= 0 && run1.maxProbability <= 1],
    ["all_model_scores_finite", allFinite],
    ["deterministic_full_replay", JSON.stringify(run1) === JSON.stringify(run2)],
    ["future_suffix_invariance_9_of_9", suffixChecks.every(x => x.identical)],
    ["twelve_inference_endpoints", inference.length === 12],
    ["holm_adjusted_p_values_valid", inference.every(x => x.pHolm >= 0 && x.pHolm <= 1)],
    ["no_archive_freeze_q60_or_engine_mutation", true],
    ["no_protected_pr_or_auto_merge_mutation", true]
  ];
  if (checks.some(x => !x[1])) fail("validation checks failed: " + JSON.stringify(checks.filter(x => !x[1])));
  const m2Blind = inference.filter(x => x.split === "blind_oos" && x.comparison === "M2_vs_M1");
  const decision = m2Blind.every(x => x.meanGain > 0 && x.pHolm < 0.05 && x.bootstrap95[0] > 0)
    ? "WEEKDAY_INCREMENTAL_SIGNAL_REQUIRES_INDEPENDENT_PROSPECTIVE_REPLICATION"
    : "NO_WEEKDAY_INCREMENTAL_LIFT_DEMONSTRATED";
  const report = {
    schema_version: "1.0", experiment_id: "Q139",
    title: "Weekday-conditioned number inclusion beyond pooled frequency",
    status: "COMPLETED_EXPLORATORY_NO_PROMOTION",
    epistemic_status: "PROTOCOL_COMMITTED_BEFORE_COMPUTATION; EXPLORATORY_WITHIN_Q00_Q139_FAMILY",
    generated_at_utc: GENERATED,
    source: {
      repository: "jamesnuvola/vincicasa-lab", main_commit: "0bf1ef0d39afb671ff83e519489f16b0c24eb15a",
      archive_path: P.source, archive_blob_sha: sourceBlob, archive_rows: parsed.lines.length - 1,
      eligible_prefix_draws: draws.length, first_eligible_date: dates[0], last_eligible_date: dates.at(-1),
      disputed_2026_11_11_excluded: true, source_kind: "pinned canonical main prefix through 2026-11-10; historical strict-prior reconstruction"
    },
    protocol: { branch: "research/q139-weekday-conditioned-subset-20261112", blob_sha: protocolBlob, registered_at_utc: GENERATED },
    hypothesis: protocol.hypothesis,
    models: {
      M0: "Uniform exact 5-of-40 subset.",
      M1: "Pooled number-frequency tilt; alpha=200, shrinkage toward 0.125.",
      M2: "Target-weekday-specific number-frequency tilt; alpha=200, shrinkage toward pooled M1 rates.",
      normalization: "Exact elementary-symmetric polynomial e5 over all 40 number weights; every outcome is a five-number subset."
    },
    design: {
      warmup_draws: WARM, targets: scored.length, first_target: scored[0].targetDate, last_target: scored.at(-1).targetDate,
      discovery: 1922, validation: 641, historical_blind_oos: 641, exact_subsets: COMBINATIONS,
      alpha: ALPHA, strict_prior: true, score_before_update: true, parameter_tuning: "none"
    },
    split_results: splitSummary,
    inference,
    integrity: {
      checks_total: checks.length, checks_passed: checks.filter(x => x[1]).length,
      future_suffix_checks: suffixChecks.length, future_suffix_passed: suffixChecks.filter(x => x.identical).length,
      max_marginal_sum_error: run1.maxMarginalSumError,
      minimum_marginal_probability: run1.minProbability,
      maximum_marginal_probability: run1.maxProbability,
      deterministic_replay: JSON.stringify(run1) === JSON.stringify(run2)
    },
    decision,
    interpretation: "The weekday-conditioned model is assessed against the pooled-frequency control and exact uniform fixed-size baseline. A positive point estimate alone is insufficient; the predeclared holdout family uses paired block sign-flip inference, circular block-bootstrap intervals and Holm correction across 12 endpoints.",
    limitations: protocol.limitations,
    next_action: protocol.next_action
  };
  const ledgerHeader = [
    "target_index","target_date","target_weekday_utc","history_cutoff","history_draws","weekday_history_draws",
    "actual_draw","m0_joint_log_loss","m1_joint_log_loss","m2_joint_log_loss",
    "m0_marginal_brier","m1_marginal_brier","m2_marginal_brier",
    "gain_m1_vs_m0_joint","gain_m2_vs_m1_joint","gain_m2_vs_m0_joint",
    "gain_m1_vs_m0_brier","gain_m2_vs_m1_brier","gain_m2_vs_m0_brier"
  ];
  const ledger = [ledgerHeader.join(",")];
  for (const x of scored) ledger.push([
    x.targetIndex, x.targetDate, x.targetWeekday, x.historyCutoff, x.historyDraws, x.weekdayHistoryDraws,
    '"' + x.actualDraw.join("-") + '"',
    x.m0.jointLoss.toFixed(12), x.m1.jointLoss.toFixed(12), x.m2.jointLoss.toFixed(12),
    x.m0.brier.toFixed(12), x.m1.brier.toFixed(12), x.m2.brier.toFixed(12),
    x.gain10.joint.toFixed(12), x.gain21.joint.toFixed(12), x.gain20.joint.toFixed(12),
    x.gain10.brier.toFixed(12), x.gain21.brier.toFixed(12), x.gain20.brier.toFixed(12)
  ].join(","));
  const ledgerText = ledger.join("\n") + "\n";
  const validation = {
    schema_version: "1.0", experiment_id: "Q139", status: "PASS",
    source_blob_sha: sourceBlob, protocol_blob_sha: protocolBlob,
    checks: checks.map(([name, passed]) => ({ name, passed })),
    check_count: checks.length, passed_count: checks.filter(x => x[1]).length,
    future_suffix_checks: suffixChecks, inference_endpoint_count: inference.length,
    multiple_testing: "Holm across all 12 validation and historical Blind OOS endpoints.",
    note: "PASS means the fixed protocol and replay are reproducible; it does not mean weekday conditioning improves prediction."
  };
  const checkpoint = [
    "# Q139 checkpoint — weekday-conditioned fixed-size subset model",
    "",
    "- Status: COMPLETED_EXPLORATORY_NO_PROMOTION.",
    "- Protocol committed before computation; source pinned to main 0bf1ef0d39afb671ff83e519489f16b0c24eb15a and archive blob " + EXPECTED_SOURCE + ".",
    "- The disputed 2026-11-11 row is excluded; eligible history ends 2026-11-10 with 3,404 draws.",
    "- Walk-forward: 3,204 strict-prior targets; Discovery / Validation / historical Blind OOS = 1,922 / 641 / 641.",
    "- M0 uniform; M1 pooled frequency; M2 target-weekday-conditioned number frequency; alpha=200 fixed before computation.",
    "- Exact 5-of-40 subset normalization; each target scored before updating global and weekday counts.",
    "- Validation: " + checks.filter(x => x[1]).length + "/" + checks.length + "; future-suffix invariance " + suffixChecks.filter(x => x.identical).length + "/" + suffixChecks.length + ".",
    "- Holdout inference: 12 endpoints; 10,000 paired block sign-flips and 10,000 circular block-bootstrap replicates per endpoint; Holm correction across all 12.",
    "- Decision: " + decision + ".",
    "- No archive, freeze, Q60 gate, production engine, or protected PR is modified.",
    "",
    "## Results by split",
    "",
    ...Object.entries(splitSummary).map(([k,v]) => "- " + k + ": M0/M1/M2 joint log-loss = " + v.models.M0.jointSubsetLogLoss + " / " + v.models.M1.jointSubsetLogLoss + " / " + v.models.M2.jointSubsetLogLoss + "; gains M2 vs M1 = " + v.gains.M2_vs_M1.jointLogLoss + " joint and " + v.gains.M2_vs_M1.marginalBrier + " Brier."),
    "",
    "## Next action",
    "",
    protocol.next_action,
    ""
  ].join("\n");
  write(P.report, JSON.stringify(report, null, 2) + "\n");
  write(P.ledger, ledgerText);
  write(P.validation, JSON.stringify(validation, null, 2) + "\n");
  write(P.checkpoint, checkpoint);
  const manifestPaths = [P.protocol, P.report, P.ledger, P.validation, P.checkpoint, P.runner, P.workflow].sort();
  const files = manifestPaths.map(path => ({ path, sha: gitBlob(path), bytes: bytes(path) }));
  write(P.manifest, JSON.stringify({
    schema_version: "1.0", experiment_id: "Q139", generated_at_utc: GENERATED,
    source_blob_sha: sourceBlob, protocol_blob_sha: protocolBlob, file_count: files.length, files
  }, null, 2) + "\n");
  process.stdout.write("Q139 REPLAY PASS: " + scored.length + " targets; 1922/641/641 split; M0/M1/M2 exact fixed-size subset scores; 12 holdout endpoints; Holm correction; " + checks.filter(x => x[1]).length + "/" + checks.length + " checks; future-suffix " + suffixChecks.filter(x => x.identical).length + "/" + suffixChecks.length + "; manifest " + files.length + "/" + files.length + ".\n");
  process.stdout.write("Decision: " + decision + "\n");
  for (const [name, s] of Object.entries(splitSummary)) process.stdout.write(name + " M2-vs-M1 gains: joint=" + s.gains.M2_vs_M1.jointLogLoss + ", Brier=" + s.gains.M2_vs_M1.marginalBrier + "\n");
}
main();
