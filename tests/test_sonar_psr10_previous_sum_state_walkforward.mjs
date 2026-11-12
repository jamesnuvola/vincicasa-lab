import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArchive, runPSR10, buildSumQuartiles, buildPrior } from "../scripts/sonar_psr10_previous_sum_state_walkforward.mjs";
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const csv = fs.readFileSync(path.join(ROOT, "data", "storico_daily.csv"), "utf8");
const rows = parseArchive(csv);
assert.equal(rows.length, 3401);
const prior = buildPrior();
assert.equal(prior.length, 5);
for (const p of prior) assert.equal(p.countSum, 658008);
const q = buildSumQuartiles();
assert.deepEqual(q.cuts, [86, 102, 119]);
assert.equal(q.mass.reduce((s, x) => s + x, 0), 658008);
const lines = csv.trim().split(/\r?\n/);
const mini = lines.slice(0, 701).join("\n") + "\n";
const opts = { archiveBlobSha: null, expectedArchiveSha: null, warmup: 200, alphaGrid: [300, 1000], bootstrapReplicates: 50, blockLength: 7, seedBase: 42, generatedAtUtc: "2026-01-01T00:00:00Z" };
const a = runPSR10(mini, opts);
const b = runPSR10(mini, opts);
assert.deepEqual(a, b, "run output must replay deterministically");
assert.equal(a.report.design.walk_forward_targets, 500);
assert.equal(a.report.design.splits.discovery.n, 300);
assert.equal(a.report.design.splits.validation.n, 100);
assert.equal(a.report.design.splits.blind_oos.n, 100);
assert.equal(a.report.integrity.strict_prefix_checks, 500);
assert.equal(a.report.integrity.target_cutoff_before_target_checks, 500);
assert.equal(a.report.integrity.ledger_rows_total, 2500);
assert.equal(a.report.integrity.candidate_and_global_probability_normalization_checks, 15000);
for (let i = 1; i <= 5; i++) {
  const ledger = a.ledgers["P" + i].trim().split(/\r?\n/);
  assert.equal(ledger.length, 501);
  for (let r = 1; r < ledger.length; r++) {
    const f = ledger[r].split(",");
    const targetIndex = Number(f[0]);
    assert.ok(f[2] < f[1], "cutoff date must precede target date");
    assert.equal(Number(f[7]), targetIndex - 1, "strict transition prefix must exclude target");
    assert.ok(Number(f[8]) <= Number(f[7]), "state-specific training must be a subset of prior transitions");
  }
}
assert.throws(() => parseArchive("data,n1,n2,n3,n4,n5\n2020-01-02,1,2,3,4,5\n2020-01-01,1,2,3,4,5\n"), /Dates not strictly increasing/);
console.log("PSR-10 synthetic tests PASS: exact prior/quartiles, deterministic replay, strict-prefix/cutoff, ledger integrity.");
