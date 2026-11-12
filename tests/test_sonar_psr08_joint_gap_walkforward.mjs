import test from "node:test";
import assert from "node:assert/strict";
import { runWalkForward, renderMarkdown } from "../scripts/sonar_psr08_joint_gap_walkforward.mjs";

function syntheticCsv(n=90) {
  let state=0x12345678;
  const next=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state;};
  const rows=["data,n1,n2,n3,n4,n5"];
  for(let i=0;i<n;i++) {
    const set=new Set();
    while(set.size<5)set.add((next()%40)+1);
    const nums=[...set].sort((a,b)=>a-b);
    const date=new Date(Date.UTC(2017,0,1)+i*86400000).toISOString().slice(0,10);
    rows.push([date,...nums].join(","));
  }
  return rows.join("\n")+"\n";
}
const opts={expectedArchiveBlobSha:null,archiveBlobSha:null,warmup:50,bootstrapReplicates:100,blockLength:7,seedBase:20261108,alphaGrid:[100,300,1000]};

test("exact pair prior and strict-prefix synthetic walk-forward reconcile",()=>{
  const out=runWalkForward(syntheticCsv(),opts);
  assert.equal(out.report.prior.denominator,658008);
  assert.equal(out.report.prior.pairs.length,4);
  for(const p of out.report.prior.pairs) {
    assert.equal(p.jointSupportCells,666);
    assert.equal(p.totalPriorCount,658008);
    assert.deepEqual(p.gapQuartileCutpoints,[3,5,10]);
  }
  assert.equal(out.report.integrity.scoredTargets,40);
  assert.equal(out.report.integrity.strictPrefixTrainNChecks,40);
  assert.equal(out.report.integrity.targetCutoffBeforeTargetDateChecks,40);
  assert.equal(out.report.integrity.expectedSelectedLedgerRows,160);
  assert.ok(out.report.integrity.maxProbabilityNormalizationError<1e-12);
  const lines=out.ledgers.P1_P2.trimEnd().split("\n");
  assert.equal(lines.length,41);
  const first=lines[1].split(",");
  assert.equal(first[0],"50");
  assert.equal(first[6],"48");
  assert.ok(first[1]>first[2]);
  assert.equal(out.report.protocol.splits.discovery.n,20);
  assert.equal(out.report.protocol.splits.validation.n,10);
  assert.equal(out.report.protocol.splits.blind_oos.n,10);
  assert.ok(renderMarkdown(out.report).includes("EXPLORATORY / NO PROMOTION"));
});

test("synthetic output replay is byte deterministic",()=>{
  const csv=syntheticCsv();
  const a=runWalkForward(csv,opts),b=runWalkForward(csv,opts);
  assert.equal(a.reportText,b.reportText);
  assert.equal(renderMarkdown(a.report),renderMarkdown(b.report));
  assert.deepEqual(a.ledgers,b.ledgers);
});

test("invalid chronological archive fails closed",()=>{
  const rows=syntheticCsv().trimEnd().split("\n");
  const tmp=rows[10];rows[10]=rows[11];rows[11]=tmp;
  assert.throws(()=>runWalkForward(rows.join("\n")+"\n",opts),/chronological|line/);
});
