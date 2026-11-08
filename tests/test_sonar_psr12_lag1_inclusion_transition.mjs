import assert from "node:assert/strict";
import { runExperiment, lag1ScoreVector } from "../scripts/sonar_psr12_lag1_inclusion_transition.mjs";

function syntheticCsv(count=180) {
  let seed=987654321;
  const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
  const lines=["data,n1,n2,n3,n4,n5"];
  for(let i=0;i<count;i++){
    const pool=Array.from({length:40},(_,j)=>j+1),nums=[];
    for(let k=0;k<5;k++){const ix=Math.floor(rand()*pool.length);nums.push(pool.splice(ix,1)[0]);}
    nums.sort((a,b)=>a-b);const date=new Date(Date.UTC(2020,0,1)+i*86400000).toISOString().slice(0,10);lines.push([date,...nums].join(","));
  }
  return lines.join(String.fromCharCode(10))+String.fromCharCode(10);
}

const q0=Array(40).fill(0.125),cond=Array(40).fill(0),exp=Array(40).fill(10);cond[0]=2;const state=[1];
const raw=lag1ScoreVector(q0,cond,exp,state,0);assert.equal(raw[0],0.2);assert.equal(raw[1],0.125);
const shrunk=lag1ScoreVector(q0,cond,exp,state,100);assert.ok(shrunk[0]>0.125&&shrunk[0]<0.2);assert.equal(shrunk[1],0.125);
assert.throws(()=>lag1ScoreVector(q0,cond,exp,state,-1),/nonnegative/);

const csv=syntheticCsv(),opts={synthetic:true,warmup:50,split1:80,split2:120,alphaGrid:[0,25],inferenceReplicates:500,bootstrapReplicates:300,seed:20261108};
const a=runExperiment(csv,opts),b=runExperiment(csv,opts);
assert.deepEqual(a.summary,b.summary);assert.equal(a.ledgers.discovery,b.ledgers.discovery);assert.equal(a.ledgers.validation,b.ledgers.validation);assert.equal(a.ledgers.blind_oos,b.ledgers.blind_oos);
assert.equal(a.summary.walkforward.targets,130);assert.equal(a.summary.walkforward.metrics.discovery.n,30);assert.equal(a.summary.walkforward.metrics.validation.n,40);assert.equal(a.summary.walkforward.metrics.blind_oos.n,60);
assert.equal(a.summary.controls.strict_prefix_checks,130);assert.equal(a.summary.controls.n_unique_target_keys,130);assert.equal(a.summary.controls.ledger_rows,130);assert.equal(a.summary.uniform_null.per_target_expected_hits,0.625);
assert.equal(a.ledgers.discovery.trim().split(String.fromCharCode(10)).length,31);assert.equal(a.ledgers.validation.trim().split(String.fromCharCode(10)).length,41);assert.equal(a.ledgers.blind_oos.trim().split(String.fromCharCode(10)).length,61);
console.log("PSR12_SYNTHETIC_TESTS_OK: lag score, shrinkage, strict-prefix, splits, exact null, deterministic replay");
