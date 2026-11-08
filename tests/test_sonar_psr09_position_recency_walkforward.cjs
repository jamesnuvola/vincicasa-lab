"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const {buildPrior,parseCsv,runWalkForward,renderMarkdown,gitBlobSha}=require("../scripts/sonar_psr09_position_recency_walkforward.cjs");
function syntheticCsv(n=260){
  const start=Date.UTC(2017,6,17),rows=["data,n1,n2,n3,n4,n5"];
  for(let t=0;t<n;t++){
    const date=new Date(start+t*86400000).toISOString().slice(0,10);
    const nums=[1+(t%8),10+(t%7),20+(t%5),28+(t%4),35+(t%5)];
    rows.push(date+","+nums.join(","));
  }
  return rows.join("\n")+"\n";
}
test("exact order-statistic priors normalize and have position supports",()=>{
  const priors=buildPrior();
  assert.equal(priors.length,5);
  assert.equal(priors[0].den,658008);
  priors.forEach((p,i)=>{
    assert.equal(p.countSum,658008);
    assert.ok(Math.abs(p.p.reduce((s,x)=>s+x,0)-1)<1e-12);
    assert.deepEqual(p.support,[i+1,36+i]);
  });
});
test("archive parser rejects duplicate values and non-chronological dates",()=>{
  assert.throws(()=>parseCsv("data,n1,n2,n3,n4,n5\n2017-07-17,1,1,2,3,4\n"),/Invalid draw row/);
  assert.throws(()=>parseCsv("data,n1,n2,n3,n4,n5\n2017-07-18,1,2,3,4,5\n2017-07-17,1,2,3,4,5\n"),/strictly increasing/);
});
test("walk-forward has strict prefix, normalized probabilities, and deterministic replay",()=>{
  const csv=syntheticCsv(),archiveBlobSha=gitBlobSha(csv),opts={archiveBlobSha,expectedArchiveSha:archiveBlobSha,runnerBlobSha:"test-runner",warmup:200,windowGrid:[30,90],alphaGrid:[100,300],bootstrapReplicates:50,blockLength:7};
  const a=runWalkForward(csv,opts),b=runWalkForward(csv,opts);
  assert.equal(a.report.integrity.scoredTargets,60);
  assert.equal(a.report.integrity.strictPrefixChecks,60);
  assert.equal(a.report.integrity.targetCutoffBeforeTargetChecks,60);
  assert.equal(a.report.integrity.expectedSelectedLedgerRows,300);
  assert.ok(a.report.integrity.maxProbabilityNormalizationError<1e-12);
  assert.equal(a.reportText,b.reportText);
  assert.deepEqual(a.ledgers,b.ledgers);
  assert.equal(renderMarkdown(a.report),renderMarkdown(b.report));
});
test("pinned archive mismatch is rejected",()=>{
  const csv=syntheticCsv();
  assert.throws(()=>runWalkForward(csv,{archiveBlobSha:gitBlobSha(csv),expectedArchiveSha:"not-the-sha",warmup:200,windowGrid:[30],alphaGrid:[100],bootstrapReplicates:10}),/Pinned archive Git blob SHA mismatch/);
});
