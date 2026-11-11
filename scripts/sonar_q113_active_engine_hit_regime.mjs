#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const P = "reports/sequence_agent/";
const read = p => fs.readFileSync(path.join(ROOT, p), "utf8");
const sha = s => { const b = Buffer.from(s, "utf8"); return crypto.createHash("sha1").update("blob " + b.length + "\0").update(b).digest("hex"); };
const choose = (n, k) => { if (k < 0 || k > n) return 0; let v = 1; for (let i = 1; i <= k; i++) v = v * (n - i + 1) / i; return v; };
const round = x => Number(x.toFixed(12));
const fail = m => { console.error("Q113 BLOCKED: " + m); process.exit(1); };
const csvCell = v => { const s = String(v); return /[,"\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
const rng = seed => { let x = seed >>> 0; return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; return (x >>> 0) / 4294967296; }; };
function signFlip(values, B, seed) {
  const rand = rng(seed), blocks = [];
  for (let i = 0; i < values.length; i += 20) blocks.push(values.slice(i, i + 20).reduce((a, b) => a + b, 0));
  const observed = values.reduce((a, b) => a + b, 0) / values.length;
  let ge = 0;
  for (let b = 0; b < B; b++) { let sum = 0; for (const v of blocks) sum += rand() < 0.5 ? -v : v; if (sum / values.length >= observed - 1e-15) ge++; }
  return { mean: observed, p: (ge + 1) / (B + 1) };
}
function blockBootstrap(values, B, seed) {
  const rand = rng(seed), out = [];
  for (let b = 0; b < B; b++) {
    let sum = 0, count = 0;
    while (count < values.length) {
      const start = Math.floor(rand() * values.length);
      for (let j = 0; j < 20 && count < values.length; j++, count++) sum += values[(start + j) % values.length];
    }
    out.push(sum / values.length);
  }
  out.sort((a, b) => a - b);
  return [out[Math.floor(0.025 * B)], out[Math.floor(0.975 * B)]];
}
function extract(source, name, next) {
  const a = source.indexOf("function " + name + "(");
  const b = next ? source.indexOf("\nfunction " + next + "(", a + 1) : source.indexOf("\nconst Card =", a + 1);
  if (a < 0 || b < 0) fail("cannot extract exact UI scorer function " + name);
  return source.slice(a, b).trim();
}
function main() {
  const csv = read("data/storico_daily.csv");
  const app = read("src/VinciCasaLab.jsx");
  const data = JSON.parse(read("src/data.json"));
  const engine = JSON.parse(read(P + "active_engine_walkforward.json"));
  const queue = JSON.parse(read(P + "research_queue_status.json"));
  const freeze = JSON.parse(read(P + "q113_active_engine_hit_regime_prospective_freeze_2026-11-11.json"));
  const report = JSON.parse(read(P + "q113_active_engine_hit_regime_report_2026-11-11.json"));
  const validation = JSON.parse(read(P + "q113_active_engine_hit_regime_validation_2026-11-11.json"));
  const manifest = JSON.parse(read(P + "q113_active_engine_hit_regime_persistence_manifest_2026-11-11.json"));
  const draws = csv.trimEnd().split(/\r?\n/).slice(1).map(line => { const f = line.split(","); return { d: f[0], n: f.slice(1).map(Number) }; });
  if (draws.length !== 3404 || data.modelDraws.length !== draws.length) fail("archive/app size mismatch");
  for (let i = 0; i < draws.length; i++) if (data.modelDraws[i].d !== draws[i].d || data.modelDraws[i].n.join(",") !== draws[i].n.join(",")) fail("app data mismatch at " + i);
  const score = new Function("draws", [
    extract(app, "overlapCount", "sonarTransitionProfile"),
    extract(app, "sonarTransitionProfile", "sonarAnalogCore"),
    extract(app, "sonarAnalogCore", null),
    "return sonarAnalogCore(draws);"
  ].join("\n"));
  const h = Array(draws.length).fill(null);
  for (let t = 200; t < draws.length; t++) {
    const ranking = score(draws.slice(0, t)).scores.map(x => x.n);
    if (ranking.length !== 40 || new Set(ranking).size !== 40) fail("invalid rank at target " + t);
    const actual = new Set(draws[t].n);
    h[t] = ranking.slice(0, 20).filter(n => actual.has(n)).length;
  }
  const q = Array.from({ length: 6 }, (_, k) => choose(20, k) * choose(20, 5 - k) / choose(40, 5));
  const counts = Array.from({ length: 6 }, () => Array(6).fill(0));
  const stateCounts = Array(6).fill(0);
  const rows = [];
  const brier = (p, y) => p.reduce((s, x, k) => s + (x - (k === y ? 1 : 0)) ** 2, 0);
  for (let t = 201; t < draws.length; t++) {
    const state = h[t - 1], y = h[t];
    const p = q.map((v, k) => (200 * v + counts[state][k]) / (200 + stateCounts[state]));
    const b0 = brier(q, y), b1 = brier(p, y), l0 = -Math.log(q[y]), l1 = -Math.log(p[y]);
    rows.push({ date: draws[t].d, cutoff: draws[t - 1].d, state, y, q, p, b0, b1, bg: b0 - b1, l0, l1, lg: l0 - l1 });
    counts[state][y]++; stateCounts[state]++;
  }
  const n = rows.length, cut1 = Math.floor(n * 0.6), cut2 = Math.floor(n * 0.8);
  const avg = (a, key) => a.reduce((s, x) => s + x[key], 0) / a.length;
  const summarize = a => ({
    targets: a.length, mean_actual_hits: avg(a, "y"), brier_gain: avg(a, "bg"), log_loss_gain: avg(a, "lg"),
    baseline_brier: avg(a, "b0"), model_brier: avg(a, "b1"), baseline_log_loss: avg(a, "l0"), model_log_loss: avg(a, "l1")
  });
  const splits = { discovery: summarize(rows.slice(0, cut1)), validation: summarize(rows.slice(cut1, cut2)), blind_oos: summarize(rows.slice(cut2)) };
  const blind = rows.slice(cut2);
  const sb = signFlip(blind.map(x => x.bg), 50000, 11301), sl = signFlip(blind.map(x => x.lg), 50000, 11302);
  const cb = blockBootstrap(blind.map(x => x.bg), 10000, 11303), cl = blockBootstrap(blind.map(x => x.lg), 10000, 11304);
  const pvals = [sb.p, sl.p].sort((a, b) => a - b);
  const holm = [Math.min(1, 2 * pvals[0]), 1];
  const active = score(draws).scores.map(x => x.n);
  if (JSON.stringify(active.slice(0, 20)) !== JSON.stringify(engine.current_frozen_forecast.top20_ranked)) fail("active engine freeze does not reproduce");
  if (freeze.previous_top20_hits !== h.at(-1) || freeze.history_cutoff !== draws.at(-1).d || freeze.outcome !== null) fail("Q113 freeze metadata mismatch");
  const next = q.map((v, k) => (200 * v + counts[h.at(-1)][k]) / (200 + stateCounts[h.at(-1)]));
  if (next.some((v, i) => Math.abs(v - freeze.transition_pmf[i]) > 1e-14)) fail("Q113 frozen PMF mismatch");
  const header = ["target_date","history_cutoff","previous_top20_hits","actual_top20_hits","baseline_pmf","transition_pmf","baseline_brier","model_brier","brier_gain","baseline_log_loss","model_log_loss","log_loss_gain","split"];
  const lines = [header.join(",")];
  rows.forEach((r, i) => lines.push([
    r.date, r.cutoff, r.state, r.y, JSON.stringify(r.q.map(round)), JSON.stringify(r.p.map(round)),
    round(r.b0), round(r.b1), round(r.bg), round(r.l0), round(r.l1), round(r.lg),
    i < cut1 ? "discovery" : i < cut2 ? "validation" : "blind_oos"
  ].map(csvCell).join(",")));
  const expectedLedger = lines.join("\n") + "\n";
  if (read(P + "q113_active_engine_hit_regime_target_ledger_2026-11-11.csv") !== expectedLedger) fail("ledger content does not replay byte-for-byte");
  const roundedSplits = Object.fromEntries(Object.entries(splits).map(([k, v]) => [k, Object.fromEntries(Object.entries(v).map(([a, b]) => [a, round(b)]))]));
  if (JSON.stringify(report.walk_forward.split_metrics) !== JSON.stringify(roundedSplits)) fail("split metrics do not replay");
  if (round(report.blind_inference.brier.p) !== round(sb.p) || round(report.blind_inference.log_loss.p) !== round(sl.p)) fail("block sign-flip p-values do not replay");
  if (JSON.stringify(report.blind_inference.brier.ci95) !== JSON.stringify(cb.map(round)) || JSON.stringify(report.blind_inference.log_loss.ci95) !== JSON.stringify(cl.map(round))) fail("bootstrap intervals do not replay");
  if (queue.tasks.find(x => x.id === "Q60")?.validation_errors?.[0]?.startsWith("23 complete prospective paired targets") !== true) fail("Q60 queue state changed");
  if (validation.checks_passed !== 17 || validation.checks_total !== 17 || !validation.passed) fail("validation record");
  for (const [file, meta] of Object.entries(manifest.artifacts)) {
    const content = read(file);
    if (sha(content) !== meta.git_blob_sha1 || Buffer.byteLength(content) !== meta.byte_length) fail("manifest mismatch " + file);
  }
  console.log(JSON.stringify({ status: "PASS", targets: n, splits: [cut1, cut2 - cut1, n - cut2], ledger_replay: "BYTE_IDENTICAL", report_metrics: "REPLAYED", inference: "REPLAYED", q60: "23/200", manifest_artifacts: Object.keys(manifest.artifacts).length }));
}
main();
