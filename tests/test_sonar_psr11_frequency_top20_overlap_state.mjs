import assert from "node:assert/strict";
import { run, stateReference } from "../scripts/sonar_psr11_frequency_top20_overlap_state.mjs";

const ref=stateReference();
assert.deepEqual(ref.exact_r_counts,[15504,96900,216600,216600,96900,15504]);
assert.deepEqual(ref.exact_state_counts,[112404,433200,112404]);
assert.equal(ref.total_combinations,658008);
assert.ok(Math.abs(ref.state_mass_fractions.reduce((a,b)=>a+b,0)-1)<1e-15);

function syntheticCsv(){
  let seed=987654321;
  const rows=["data,n1,n2,n3,n4,n5"];
  const start=Date.UTC(2017,6,17);
  for(let i=0;i<400;i++){
    const set=new Set();
    while(set.size<5){seed=(1664525*seed+1013904223)>>>0;set.add((seed%40)+1);}
    const nums=Array.from(set).sort((a,b)=>a-b);
    const date=new Date(start+i*86400000).toISOString().slice(0,10);
    rows.push(date+","+nums.join(","));
  }
  return rows.join("\n")+"\n";
}
const csv=syntheticCsv();
const opts={trainStart:200,targetStart:300,discoveryCount:40,validationCount:30,alphaGrid:[0,25,100],blockLength:7,signFlipReps:40,bootstrapReps:40,seed:20261108,strictArchive:false};
const a=run(csv,opts),b=run(csv,opts);
assert.equal(a.json,b.json,"same archive/options must replay JSON byte-identically");
assert.equal(a.markdown,b.markdown,"same archive/options must replay Markdown byte-identically");
assert.equal(a.ledger,b.ledger,"same archive/options must replay ledger byte-identically");
const rows=a.ledger.trim().split(/\r?\n/);
assert.equal(rows.length,101,"one header plus 100 target rows");
const header=rows[0].split(","),first=rows[1].split(",");
const ix=name=>header.indexOf(name);
assert.equal(first[ix("target_index")],"300");
assert.equal(first[ix("cutoff")],new Date(Date.UTC(2017,6,17)+299*86400000).toISOString().slice(0,10));
assert.equal(first[ix("train_outcomes")],"100");
assert.equal(first[ix("prev_overlap_top20")],first[ix("state")]==="0"?"0":first[ix("state")]==="1"?"2":"4");

const altered=csv.split(/\r?\n/);
const old=altered[301].split(",").slice(1).map(Number);
const alt=old.join(" ")==="1 2 3 4 6"?"2,3,4,5,7":"1,2,3,4,6";
altered[301]=altered[301].split(",")[0]+","+alt;
const c=run(altered.join("\n"),opts);
const crows=c.ledger.trim().split(/\r?\n/),cfirst=crows[1].split(",");
assert.equal(first[ix("state")],cfirst[ix("state")],"target outcome must not affect its pre-target state");
assert.equal(first[ix("model_top5")],cfirst[ix("model_top5")],"target outcome must not affect its pre-target candidate Top5");
assert.notEqual(first[ix("actual")],cfirst[ix("actual")],"synthetic target outcome was changed");
assert.equal(a.result.integrity.target_cutoff_checks,100);
assert.equal(a.result.integrity.state_window_checks,100);
assert.equal(a.result.integrity.training_prefix_checks,100);
assert.equal(a.result.integrity.normalization_checks,100*4);
console.log("PSR-11 synthetic state, strict-prefix, no-target-leakage, normalization, and replay tests PASS");
