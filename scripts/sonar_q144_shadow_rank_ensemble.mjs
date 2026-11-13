import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import assert from "node:assert/strict";

export const Q144 = Object.freeze({
  experimentId: "Q144",
  branch: "research/q144-shadow-rank-ensemble-20261113",
  baseMainCommit: "4a55fb7da216bd3850b79f862bf10b2cbcafa968",
  archiveBlobSha: "6e53bd2dc02932d1cef5af4f68e17734d9d1e6cb",
  shadowBlobSha: "ffc5a4eb0c38e4dfc67032e1ef5737689be5fec1",
  preregBlobSha: "fef0d86ab401215f6f5560a633bf8bfaa2f80fbf",
  targetDate: "2026-11-13",
  targetCutoff: "2026-11-12",
  frozenAtUtc: "2026-11-13T17:49:56Z",
  frozenAtLocal: "2026-11-13T18:49:56+01:00",
  drawLocalTime: "20:00:00",
  bootstrapReplicates: 20000,
  bootstrapBlockLength: 2,
  bootstrapSeed: 14401
});

export function parseCsv(input) {
  const text = input.replace(/^\uFEFF/, "");
  const records = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field.replace(/\r$/, "")); records.push(row); row = []; field = ""; }
    else field += c;
  }
  if (field.length || row.length) { row.push(field.replace(/\r$/, "")); records.push(row); }
  const header = records.shift();
  assert.ok(header && header.length > 1, "CSV header missing");
  return records.filter(r => !(r.length === 1 && r[0] === "")).map(r =>
    Object.fromEntries(header.map((key, i) => [key, r[i] ?? ""]))
  );
}

export function gitBlobSha1(content) {
  const bytes = Buffer.from(content, "utf8");
  return crypto.createHash("sha1").update("blob " + bytes.length + "\0").update(bytes).digest("hex");
}

export function parseNumberList(value) {
  if (!value || !value.trim()) return [];
  return value.trim().split(/\s+/).map(Number);
}

export function validateTop20(values) {
  assert.equal(values.length, 20, "Top20 must contain exactly 20 numbers");
  assert.equal(new Set(values).size, 20, "Top20 contains duplicates");
  assert.ok(values.every(n => Number.isInteger(n) && n >= 1 && n <= 40), "Top20 number outside 1..40");
  return values;
}

function targetDrawTimestamp(targetDate, offset) {
  return Date.parse(targetDate + "T" + Q144.drawLocalTime + offset);
}

export function validateFreezeRow(row, targetDate, archiveDateSet) {
  const freezeDate = row.frozen_at.slice(0, 10);
  const offset = row.frozen_at.slice(-6);
  const freezeMs = Date.parse(row.frozen_at);
  assert.ok(Number.isFinite(freezeMs), "Invalid frozen_at timestamp");
  assert.ok(archiveDateSet.has(row.history_cutoff), "history_cutoff is absent from canonical archive");
  assert.ok(row.history_cutoff < targetDate, "history_cutoff is not prior to target");
  assert.ok(row.history_cutoff <= freezeDate, "history_cutoff is after freeze date");
  assert.ok(freezeMs < targetDrawTimestamp(targetDate, offset), "Forecast was frozen after target draw time");
  if (row.history_cutoff === freezeDate) {
    assert.ok(freezeMs > targetDrawTimestamp(freezeDate, offset), "Same-day cutoff was used before that day's draw");
  }
  return true;
}

export function aggregateTarget(rows) {
  const types = ["family", "pair", "chain"];
  const expected = { family: 24, pair: 12, chain: 6 };
  const ruleRows = rows.filter(r => types.includes(r.config_type));
  const appRows = rows.filter(r => r.config_type === "app_engine");
  assert.equal(ruleRows.length, 42, "Expected 42 non-APP rule rows");
  assert.equal(appRows.length <= 1, true, "More than one APP row");
  const bordaByType = Object.fromEntries(types.map(t => [t, Array(41).fill(0)]));
  const inclusionByType = Object.fromEntries(types.map(t => [t, Array(41).fill(0)]));
  const counts = {};
  for (const type of types) {
    const group = ruleRows.filter(r => r.config_type === type);
    counts[type] = group.length;
    assert.equal(group.length, expected[type], "Unexpected rule count for " + type);
    const ids = group.map(r => r.config_id);
    assert.equal(new Set(ids).size, ids.length, "Duplicate config_id in " + type);
    for (const row of group) {
      const ranked = validateTop20(parseNumberList(row.top20));
      ranked.forEach((number, index) => {
        bordaByType[type][number] += 20 - index;
        inclusionByType[type][number] += 1;
      });
    }
  }
  const bordaScore = Array(41).fill(0);
  const inclusionScore = Array(41).fill(0);
  for (const type of types) {
    for (let number = 1; number <= 40; number++) {
      bordaScore[number] += bordaByType[type][number] / counts[type];
      inclusionScore[number] += inclusionByType[type][number] / counts[type];
    }
  }
  const rank = scores => Array.from({ length: 40 }, (_, i) => i + 1)
    .sort((a, b) => scores[b] - scores[a] || a - b).slice(0, 20);
  const app = appRows[0] ? validateTop20(parseNumberList(appRows[0].top20)) : null;
  return { borda: rank(bordaScore), inclusion: rank(inclusionScore), app, counts };
}

export function exactSignFlipGreater(differences) {
  const n = differences.length;
  assert.ok(n > 0 && n <= 20, "Exact sign-flip test supports 1..20 pairs");
  const observed = differences.reduce((a, b) => a + b, 0) / n;
  let extreme = 0;
  const total = 2 ** n;
  for (let mask = 0; mask < total; mask++) {
    let sum = 0;
    for (let i = 0; i < n; i++) sum += ((mask >> i) & 1) ? differences[i] : -differences[i];
    if (sum / n >= observed - 1e-12) extreme++;
  }
  return extreme / total;
}

function choose(n, k) {
  if (k < 0 || k > n) return 0;
  let value = 1;
  for (let i = 1; i <= k; i++) value = value * (n - i + 1) / i;
  return value;
}

export function hypergeometricTop20Pmf() {
  const denominator = choose(40, 20);
  return Array.from({ length: 6 }, (_, k) => choose(5, k) * choose(35, 20 - k) / denominator);
}

export function exactUniformUpperTail(totalHits, draws = 7) {
  const pmf = hypergeometricTop20Pmf();
  let distribution = [1];
  for (let d = 0; d < draws; d++) {
    const next = Array(distribution.length + 5).fill(0);
    for (let i = 0; i < distribution.length; i++) {
      for (let k = 0; k <= 5; k++) next[i + k] += distribution[i] * pmf[k];
    }
    distribution = next;
  }
  return distribution.slice(totalHits).reduce((a, b) => a + b, 0);
}

function mulberry32(seed) {
  return function () {
    let t = seed += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

export function circularBlockBootstrapCI(values, seed, replicates = 20000, blockLength = 2) {
  const random = mulberry32(seed);
  const n = values.length;
  const means = [];
  for (let b = 0; b < replicates; b++) {
    let sum = 0, count = 0;
    while (count < n) {
      const start = Math.floor(random() * n);
      for (let j = 0; j < blockLength && count < n; j++, count++) {
        sum += values[(start + j) % n];
      }
    }
    means.push(sum / n);
  }
  means.sort((a, b) => a - b);
  return [means[Math.floor(0.025 * replicates)], means[Math.floor(0.975 * replicates)]];
}

export function holmAdjust(namedPValues) {
  const sorted = Object.entries(namedPValues).sort((a, b) => a[1] - b[1]);
  const adjusted = {};
  let running = 0;
  sorted.forEach(([name, p], index) => {
    running = Math.max(running, Math.min(1, (sorted.length - index) * p));
    adjusted[name] = running;
  });
  return adjusted;
}

function sameNumbers(a, b) {
  return a.length === b.length && [...a].sort((x, y) => x - y).every((n, i) => n === [...b].sort((x, y) => x - y)[i]);
}

function metrics(rows) {
  const result = { target_dates: rows.length };
  for (const [name, key] of [["borda", "borda_hits"], ["inclusion", "inclusion_hits"], ["app", "app_hits"]]) {
    const values = rows.map(r => r[key]).filter(v => v !== null);
    result[name] = values.length ? {
      n: values.length,
      total_hits: values.reduce((a, b) => a + b, 0),
      mean_hits: values.reduce((a, b) => a + b, 0) / values.length,
      four_plus: values.filter(v => v >= 4).length,
      five_of_five: values.filter(v => v === 5).length
    } : null;
  }
  result.uniform_top20 = { expected_hits_per_draw: 2.5 };
  return result;
}

function csvEscape(value) {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

function makeLedgerCsv(rows) {
  const header = ["target_date", "actual_numbers", "rule_rows", "family_rows", "pair_rows", "chain_rows", "app_available",
    "borda_top20", "borda_hits", "inclusion_top20", "inclusion_hits", "app_top20", "app_hits"];
  const lines = [header.join(",")];
  for (const r of rows) {
    lines.push([
      r.target_date, r.actual_numbers.join(" "), r.rule_rows, r.family_rows, r.pair_rows, r.chain_rows,
      r.app_available ? 1 : 0, r.borda_top20.join(" "), r.borda_hits, r.inclusion_top20.join(" "), r.inclusion_hits,
      r.app_top20 ? r.app_top20.join(" ") : "", r.app_hits === null ? "" : r.app_hits
    ].map(csvEscape).join(","));
  }
  return lines.join("\n") + "\n";
}

export function buildQ144Outputs(archiveCsv, shadowCsv, preregText) {
  assert.equal(gitBlobSha1(archiveCsv), Q144.archiveBlobSha, "Canonical archive blob changed");
  assert.equal(gitBlobSha1(shadowCsv), Q144.shadowBlobSha, "Shadow forecast source blob changed");
  assert.equal(gitBlobSha1(preregText), Q144.preregBlobSha, "Q144 preregistration blob changed");
  const archiveRows = parseCsv(archiveCsv);
  const shadowRows = parseCsv(shadowCsv);
  const archiveMap = new Map();
  const archiveDateSet = new Set();
  let previousDate = "";
  for (const row of archiveRows) {
    assert.ok(row.data > previousDate, "Archive dates are not unique and chronological");
    previousDate = row.data;
    const values = [row.n1, row.n2, row.n3, row.n4, row.n5].map(Number);
    assert.equal(new Set(values).size, 5, "Invalid canonical draw");
    assert.ok(values.every(n => Number.isInteger(n) && n >= 1 && n <= 40));
    archiveMap.set(row.data, values);
    archiveDateSet.add(row.data);
  }
  const grouped = new Map();
  for (const row of shadowRows) {
    if (!grouped.has(row.target_date)) grouped.set(row.target_date, []);
    grouped.get(row.target_date).push(row);
  }
  const completedDates = [...grouped.keys()].filter(d => d < Q144.targetDate).sort();
  assert.equal(archiveRows.length, 3406, "Unexpected canonical archive size");
  assert.equal(shadowRows.length, 1364, "Unexpected shadow ledger size");
  assert.equal(completedDates.length, 31, "Unexpected completed shadow target count");

  const ledger = [];
  let cutoffChecks = 0, freezeChecks = 0, reconciledRows = 0, staleCutoffRows = 0, freshCutoffRows = 0;
  const multipleFreezeTimestampDates = [];\n  const multipleFreezeTimestampDates = [];
  for (const date of completedDates) {
    const rows = grouped.get(date);
    const ruleRows = rows.filter(r => ["family", "pair", "chain"].includes(r.config_type));
    const appRows = rows.filter(r => r.config_type === "app_engine");
    assert.ok(rows.length === 42 || rows.length === 43, "Unexpected rows for " + date);
    assert.equal(appRows.length <= 1, true);
    const cutoff = rows[0].history_cutoff;
    assert.ok(rows.every(r => r.history_cutoff === cutoff), "Inconsistent history cutoff for " + date);
    if (new Set(rows.map(r => r.frozen_at)).size > 1) multipleFreezeTimestampDates.push(date);
    for (const row of rows) {
      validateFreezeRow(row, date, archiveDateSet);
      cutoffChecks++;
      freezeChecks++;
      const freezeDate = row.frozen_at.slice(0, 10);
      const offset = row.frozen_at.slice(-6);
      const latestAvailable = [...archiveDateSet].filter(d => d < freezeDate || (d === freezeDate && Date.parse(row.frozen_at) > targetDrawTimestamp(freezeDate, offset))).sort().at(-1);
      if (latestAvailable && row.history_cutoff < latestAvailable) staleCutoffRows++;
      else freshCutoffRows++;
    }
    const actual = archiveMap.get(date);
    assert.ok(actual, "Target date absent from canonical archive: " + date);
    for (const row of rows) {
      assert.equal(row.status, "EVALUATED", "Historical shadow row is not evaluated");
      assert.ok(sameNumbers(parseNumberList(row.actual_numbers), actual), "Shadow outcome differs from canonical archive for " + date);
      reconciledRows++;
    }
    const aggregate = aggregateTarget(rows);
    const hitCount = set => set.filter(n => actual.includes(n)).length;
    ledger.push({
      target_date: date,
      actual_numbers: actual,
      rule_rows: ruleRows.length,
      family_rows: aggregate.counts.family,
      pair_rows: aggregate.counts.pair,
      chain_rows: aggregate.counts.chain,
      app_available: aggregate.app !== null,
      borda_top20: aggregate.borda,
      borda_hits: hitCount(aggregate.borda),
      inclusion_top20: aggregate.inclusion,
      inclusion_hits: hitCount(aggregate.inclusion),
      app_top20: aggregate.app,
      app_hits: aggregate.app ? hitCount(aggregate.app) : null
    });
  }

  const discovery = ledger.slice(0, 18);
  const validation = ledger.slice(18, 24);
  const blind = ledger.slice(24);
  assert.equal(discovery.length, 18);
  assert.equal(validation.length, 6);
  assert.equal(blind.length, 7);
  assert.ok(blind.every(r => r.app_available), "APP comparator missing in blind OOS");

  const dApp = blind.map(r => r.borda_hits - r.app_hits);
  const dInclusion = blind.map(r => r.borda_hits - r.inclusion_hits);
  const dUniform = blind.map(r => r.borda_hits - 2.5);
  const blindBordaTotal = blind.reduce((s, r) => s + r.borda_hits, 0);
  const pRaw = {
    borda_vs_app: exactSignFlipGreater(dApp),
    borda_vs_inclusion: exactSignFlipGreater(dInclusion),
    borda_vs_uniform: exactUniformUpperTail(blindBordaTotal, blind.length)
  };
  const pHolm = holmAdjust(pRaw);
  const ci = {
    borda_minus_app: circularBlockBootstrapCI(dApp, 14401, Q144.bootstrapReplicates, Q144.bootstrapBlockLength),
    borda_minus_inclusion: circularBlockBootstrapCI(dInclusion, 14402, Q144.bootstrapReplicates, Q144.bootstrapBlockLength),
    borda_minus_uniform: circularBlockBootstrapCI(dUniform, 14403, Q144.bootstrapReplicates, Q144.bootstrapBlockLength)
  };

  const pending = grouped.get(Q144.targetDate);
  assert.ok(pending, "Prospective target freeze missing");
  assert.equal(pending.length, 43);
  assert.equal(pending.filter(r => ["family", "pair", "chain"].includes(r.config_type)).length, 42);
  assert.equal(pending.filter(r => r.config_type === "app_engine").length, 1);
  assert.ok(pending.every(r => r.status === "FROZEN_PENDING"));
  assert.ok(pending.every(r => !r.actual_numbers && !r.hit_numbers && !r.hit_count && !r.all5_top20 && !r.evaluated_at_data_through));
  assert.ok(pending.every(r => r.history_cutoff === Q144.targetCutoff));
  for (const row of pending) {
    validateFreezeRow(row, Q144.targetDate, archiveDateSet);
    cutoffChecks++;
    freezeChecks++;
  }
  const pendingAggregate = aggregateTarget(pending);
  const freeze = {
    schema_version: "1.0",
    experiment_id: "Q144",
    algorithm_id: "family_balanced_borda_v1",
    status: "FROZEN_PENDING",
    target_date: Q144.targetDate,
    history_cutoff: Q144.targetCutoff,
    frozen_at_utc: Q144.frozenAtUtc,
    frozen_at_local: Q144.frozenAtLocal,
    source_archive_blob_sha: Q144.archiveBlobSha,
    source_shadow_blob_sha: Q144.shadowBlobSha,
    preregistration_blob_sha: Q144.preregBlobSha,
    component_forecasts: { family: 24, pair: 12, chain: 6 },
    app_engine_used_as_input: false,
    top20_ranked: pendingAggregate.borda,
    alternative_equal_type_inclusion_top20: pendingAggregate.inclusion,
    outcome: null,
    note: "Research-only aggregation of 42 component Top20 forecasts already frozen before the 2026-11-13 target; this does not replace or alter any existing shadow freeze."
  };

  const report = {
    schema_version: "1.0",
    experiment_id: "Q144",
    title: "Family-balanced Borda aggregation of pre-target shadow forecasts",
    status: "COMPLETE_RETROSPECTIVE_EXPLORATORY",
    generated_at_utc: Q144.frozenAtUtc,
    base_main_commit: Q144.baseMainCommit,
    preregistration_blob_sha: Q144.preregBlobSha,
    source: {
      archive_path: "data/storico_daily.csv",
      archive_blob_sha: Q144.archiveBlobSha,
      shadow_path: "reports/sequence_agent/shadow_forecasts.csv",
      shadow_blob_sha: Q144.shadowBlobSha,
      archive_draws: archiveRows.length,
      shadow_rows: shadowRows.length
    },
    hypothesis: {
      statement: "A family-balanced rank aggregation of pre-target family, pair and chain Top20 forecasts improves next-draw Top20 hits over the independently frozen APP Top20.",
      primary_endpoint: "Blind OOS paired mean Top20-hit difference: Q144 Borda minus APP",
      minimum_practical_effect_hits_per_draw: 0.25,
      secondary_endpoints: ["Q144 Borda minus equal-type inclusion consensus", "Q144 Borda minus uniform Top20 expectation 2.5"]
    },
    method: {
      rule_counts: { family: 24, pair: 12, chain: 6 },
      borda_points: "20,19,...,1 for ranks 1..20; zero outside Top20",
      type_balance: "Average Borda points within each type, then sum the three type averages",
      alternative_consensus: "Sum within-type fractions of rules including each number in Top20",
      tie_break: "Smaller number first",
      app_engine: "Comparator only; excluded from ensemble input",
      no_fitted_parameters: true
    },
    sample: {
      completed_target_dates: ledger.length,
      discovery_dates: 18,
      validation_dates: 6,
      historical_blind_oos_dates: 7,
      app_comparator_dates: ledger.filter(r => r.app_available).length,
      pending_2026_11_13_source_rows: pending.length,
      split_dates: {
        discovery: [discovery[0].target_date, discovery.at(-1).target_date],
        validation: [validation[0].target_date, validation.at(-1).target_date],
        blind_oos: [blind[0].target_date, blind.at(-1).target_date]
      }
    },
    splits: {
      discovery: metrics(discovery),
      validation: metrics(validation),
      blind_oos: metrics(blind)
    },
    blind_inference: {
      dates: blind.map(r => r.target_date),
      borda_minus_app_by_target: dApp,
      borda_minus_inclusion_by_target: dInclusion,
      borda_minus_uniform_by_target: dUniform,
      mean_differences: {
        borda_minus_app: dApp.reduce((a, b) => a + b, 0) / blind.length,
        borda_minus_inclusion: dInclusion.reduce((a, b) => a + b, 0) / blind.length,
        borda_minus_uniform: dUniform.reduce((a, b) => a + b, 0) / blind.length
      },
      block_bootstrap_ci_95: ci,
      p_values_one_sided_raw: pRaw,
      p_values_holm_adjusted: pHolm,
      exact_uniform_top20_hypergeometric_pmf: hypergeometricTop20Pmf(),
      blind_borda_total_hits: blindBordaTotal,
      bootstrap: { replicates: Q144.bootstrapReplicates, circular_block_length: Q144.bootstrapBlockLength, seeds: [14401, 14402, 14403] },
      paired_sign_flip_assignments: 128
    },
    integrity: {
      archive_draws: archiveRows.length,
      archive_dates_unique_chronological: true,
      shadow_rows: shadowRows.length,
      completed_targets_reconciled: ledger.length,
      historical_shadow_rows_reconciled: reconciledRows,
      rule_rows_per_target: 42,
      rule_type_counts_per_target: { family: 24, pair: 12, chain: 6 },
      app_rows: ledger.filter(r => r.app_available).length,
      pending_rows: pending.length,
      pending_rows_without_outcomes: true,
      strict_prior_cutoff_checks: cutoffChecks,
      pre_target_freeze_time_checks: freezeChecks,
      source_rows_with_one_day_stale_but_still_prior_cutoff: staleCutoffRows,
      source_rows_using_latest_available_cutoff: freshCutoffRows,
      target_groups_with_multiple_freeze_timestamps: multipleFreezeTimestampDates.length,
      target_dates_with_multiple_freeze_timestamps: multipleFreezeTimestampDates
    },
    decision: "NO_PROMOTION_HISTORICAL_LIFT_NOT_ESTABLISHED",
    limitations: [
      "The aggregation rule was registered after the component forecast outcomes already existed; historical Blind OOS is not virgin confirmatory evidence.",
      "Blind OOS contains only seven dates and has low power.",
      "Component rules are correlated and are not 42 independent information sources.",
      "The endpoint is Top20 hit count, not exact five-number ticket probability.",
      "The one-day-stale cutoff rows are conservative prior-only freezes; no leakage was detected, but some component forecasts used less than the latest available history."
    ],
    next_action: "Preserve the separate 2026-11-13 Q144 Top20 freeze. Reconcile it only after official publication. Accumulate at least 100 consecutive prospective Q144 freezes before a confirmatory evaluation; do not tune aggregation weights on the historical 31 dates."
  };

  const ledgerCsv = makeLedgerCsv(ledger);
  const manifest = {
    schema_version: "1.0",
    experiment_id: "Q144",
    branch: Q144.branch,
    status: "ARTIFACTS_REPRODUCIBLE_FROM_PINNED_SOURCES",
    source_blob_shas: { archive: Q144.archiveBlobSha, shadow_forecasts: Q144.shadowBlobSha, preregistration: Q144.preregBlobSha },
    artifacts: [
      "scripts/sonar_q144_shadow_rank_ensemble.mjs",
      "tests/test_sonar_q144_shadow_rank_ensemble.mjs",
      ".github/workflows/q144-shadow-rank-ensemble.yml",
      "reports/sequence_agent/q144_shadow_rank_ensemble_preregistration_2026-11-13.md",
      "reports/sequence_agent/q144_shadow_rank_ensemble_report_2026-11-13.json",
      "reports/sequence_agent/q144_shadow_rank_ensemble_report_2026-11-13.md",
      "reports/sequence_agent/q144_shadow_rank_ensemble_ledger_2026-11-13.csv",
      "reports/sequence_agent/q144_shadow_rank_ensemble_freeze_2026-11-13.json"
    ],
    no_canonical_archive_or_existing_freeze_modified: true
  };
  return { report, ledgerCsv, freeze, manifest, ledger };
}

function outputPaths() {
  return {
    archive: "data/storico_daily.csv",
    shadow: "reports/sequence_agent/shadow_forecasts.csv",
    prereg: "reports/sequence_agent/q144_shadow_rank_ensemble_preregistration_2026-11-13.md",
    report: "reports/sequence_agent/q144_shadow_rank_ensemble_report_2026-11-13.json",
    ledger: "reports/sequence_agent/q144_shadow_rank_ensemble_ledger_2026-11-13.csv",
    freeze: "reports/sequence_agent/q144_shadow_rank_ensemble_freeze_2026-11-13.json",
    manifest: "reports/sequence_agent/q144_shadow_rank_ensemble_manifest_2026-11-13.json"
  };
}

if (process.argv[1] && path.basename(process.argv[1]) === "sonar_q144_shadow_rank_ensemble.mjs") {
  const paths = outputPaths();
  const archiveCsv = fs.readFileSync(paths.archive, "utf8");
  const shadowCsv = fs.readFileSync(paths.shadow, "utf8");
  const preregText = fs.readFileSync(paths.prereg, "utf8");
  const outputs = buildQ144Outputs(archiveCsv, shadowCsv, preregText);
  const files = {
    [paths.report]: JSON.stringify(outputs.report, null, 2) + "\n",
    [paths.ledger]: outputs.ledgerCsv,
    [paths.freeze]: JSON.stringify(outputs.freeze, null, 2) + "\n",
    [paths.manifest]: JSON.stringify(outputs.manifest, null, 2) + "\n"
  };
  const mode = process.argv[2] || "--write";
  if (mode === "--write") {
    for (const [file, content] of Object.entries(files)) {
      fs.mkdirSync(path.dirname(file), { recursive: true });
      fs.writeFileSync(file, content);
    }
    process.stdout.write("Q144_WRITE_OK targets=" + outputs.ledger.length + "\n");
  } else if (mode === "--verify") {
    for (const [file, content] of Object.entries(files)) {
      assert.equal(fs.readFileSync(file, "utf8"), content, "Committed artifact differs from deterministic replay: " + file);
    }
    process.stdout.write("Q144_VERIFY_OK targets=" + outputs.ledger.length + " blind=" + outputs.report.sample.historical_blind_oos_dates + "\n");
  } else {
    throw new Error("Use --write or --verify");
  }
}
