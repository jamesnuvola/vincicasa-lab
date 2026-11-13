import assert from "node:assert/strict";
import {
  parseCsv, gitBlobSha1, choose, elementarySymmetric, rankWeights,
  marginalInclusionProbabilities, scoreRankModel, exactSignFlipGreater,
  exactSignFlipTwoSided, eProcessVille, holmAdjust
} from "../scripts/sonar_q145_rank_subset_likelihood.mjs";

const csv = 'a,b,c\n1,"two, with comma",3\n4,"say ""hi""",6\n';
const parsed = parseCsv(csv);
assert.equal(parsed.length, 2);
assert.equal(parsed[0].b, "two, with comma");
assert.equal(parsed[1].b, 'say "hi"');

assert.equal(choose(40, 5), 658008);
assert.equal(gitBlobSha1("hello\n"), "ce013625030ba8dba906f756967f9e9ca394464a");

const smallWeights = [1, 2, 3, 4, 5];
let exhaustive = 0;
for (let a = 0; a < 5; a++) for (let b = a + 1; b < 5; b++) for (let c = b + 1; c < 5; c++) {
  exhaustive += smallWeights[a] * smallWeights[b] * smallWeights[c];
}
assert.equal(elementarySymmetric(smallWeights, 3), exhaustive);

const top20 = Array.from({ length: 20 }, (_, i) => i + 1);
const weights = rankWeights(top20, 1);
assert.ok(weights[0] > weights[1] && weights[18] > weights[19]);
assert.equal(weights[20], 1);
assert.ok(weights.every(w => Number.isFinite(w) && w > 0));

const p = marginalInclusionProbabilities(weights);
assert.equal(p.length, 40);
assert.ok(Math.abs(p.reduce((a, b) => a + b, 0) - 5) < 1e-12);
assert.ok(p.every(x => x > 0 && x < 1));

const scored = scoreRankModel(top20, [1, 2, 3, 4, 5], 1);
assert.equal(scored.modalTop5.join(","), "1,2,3,4,5");
assert.ok(Number.isFinite(scored.logGain));
assert.ok(scored.modeProbability > 0 && scored.modeProbability < 1);
assert.ok(Math.abs(scored.marginals.reduce((a, b) => a + b, 0) - 5) < 1e-12);

assert.equal(exactSignFlipGreater([1, -1]), 0.75);
assert.equal(exactSignFlipTwoSided([1, -1]), 1);
assert.equal(eProcessVille([0, 0, 0]), 1);
assert.ok(Math.abs(eProcessVille([0.5, 0.5]) - Math.exp(-1)) < 1e-12);

const adjusted = holmAdjust({ a: 0.01, b: 0.04, c: 0.03 });
assert.equal(adjusted.a, 0.03);
assert.equal(adjusted.c, 0.06);
assert.equal(adjusted.b, 0.06);

console.log("Q145_TESTS_OK 23/23");
