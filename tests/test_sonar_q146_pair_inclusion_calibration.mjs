import assert from "node:assert/strict";
import {
  pairInclusionProbabilities, scorePairModel, scorePairWeights, validateShadowTemporalRow,
  buildArtifacts
} from "../scripts/sonar_q146_pair_inclusion_calibration.mjs";

let passed = 0;
function test(name, fn) {
  fn();
  passed++;
  process.stdout.write("PASS " + name + "\n");
}

test("uniform weights give exactly 1/78 pair inclusion", () => {
  const { pairs, mass } = pairInclusionProbabilities(Array(40).fill(1));
  assert.equal(pairs.length, 780);
  assert.ok(Math.abs(mass - 10) < 1e-10);
  assert.ok(pairs.every(p => Math.abs(p.probability - 1/78) < 1e-12));
});

test("nonuniform pair inclusion probabilities sum to ten", () => {
  const w = Array.from({ length: 40 }, (_, i) => Math.exp((40-i)/40));
  const out = pairInclusionProbabilities(w);
  assert.ok(Math.abs(out.mass - 10) < 1e-10);
  assert.equal(out.pairs.length, 780);
});

test("pair inclusion probabilities remain finite and bounded", () => {
  const w = Array.from({ length: 40 }, (_, i) => i < 20 ? 2.5 - i/100 : 1);
  const out = pairInclusionProbabilities(w);
  assert.ok(out.pairs.every(p => Number.isFinite(p.probability) && p.probability > 0 && p.probability < 1));
});

test("uniform ranking weights have zero pairwise Brier and composite-log gain", () => {
  const draw = [1, 2, 3, 4, 5];
  const score = scorePairWeights(Array(40).fill(1), draw);
  assert.equal(score.observedPairs, 10);
  assert.ok(Math.abs(score.pairMass - 10) < 1e-10);
  assert.ok(Math.abs(score.brierGain) < 1e-12);
  assert.ok(Math.abs(score.compositeLogGain) < 1e-12);
});

test("invalid draw is rejected", () => {
  assert.throws(() => scorePairModel(Array.from({length:20},(_,i)=>i+1), [1,2,3,4,4]));
});

test("strict-prior temporal guard accepts a valid freeze and rejects a future cutoff", () => {
  const valid = { target_date:"2026-11-13", history_cutoff:"2026-11-12", frozen_at:"2026-11-13T19:18:07+01:00" };
  const invalid = { target_date:"2026-11-13", history_cutoff:"2026-11-13", frozen_at:"2026-11-13T19:18:07+01:00" };
  assert.equal(validateShadowTemporalRow(valid), true);
  assert.equal(validateShadowTemporalRow(invalid), false);
});

test("full upstream archive, shadow, Q144 ledger and Q145 checkpoint reconcile", () => {
  const b = buildArtifacts();
  assert.equal(b.report.integrity.archive_draws, 3406);
  assert.equal(b.report.integrity.shadow_rows, 1364);
  assert.equal(b.report.integrity.strict_prior_rows, 1364);
  assert.equal(b.report.integrity.pending_2026_11_13_rows, 43);
  assert.equal(b.report.sample.targets, 31);
  assert.equal(b.report.sample.historical_blind_oos, 7);
  assert.ok(b.report.integrity.pair_mass_max_abs_error < 1e-10);
});

test("registered primary decision remains negative and no promotion is allowed", () => {
  const b = buildArtifacts();
  assert.equal(b.report.decision, "PAIRWISE_CALIBRATION_NOT_ESTABLISHED; KEEP_Q145_FROZEN; HISTORICAL_RESULTS_EXPLORATORY");
  assert.ok(b.report.splits.blind_oos.borda.mean_pair_brier_gain < 0);
});

process.stdout.write(JSON.stringify({ status:"Q146_TESTS_OK", passed, total:8 }) + "\n");
