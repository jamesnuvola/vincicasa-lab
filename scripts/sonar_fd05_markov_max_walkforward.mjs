#!/usr/bin/env node
import fs from "node:fs";
import crypto from "node:crypto";

const ARCHIVE_PATH = "data/storico_daily.csv";
const EXPECTED_ARCHIVE_SHA = "5d2efd70684e918b27d8f06386d545647898336d";
const RESULT_PATH = "reports/sequence_agent/fd05_markov_max_conditioned_walkforward_20261108.json";

function calculate(csv, archiveSha) {
  const lines=csv.trim().split(/\r?\n/);
  if(lines[0] !== "data,n1,n2,n3,n4,n5") throw new Error("Unexpected CSV header");
  const draws=lines.slice(1).map(line=>{
    const p=line.split(",");
    if(p.length!==6 || !/^\d{4}-\d{2}-\d{2}$/.test(p[0])) throw new Error("Malformed row");
    const nums=p.slice(1).map(Number);
    if(nums.some(n=>!Number.isInteger(n)||n<1||n>40) || new Set(nums).size!==5) throw new Error("Invalid quintet");
    if(nums.some((n,i)=>i>0&&nums[i-1]>=n)) throw new Error("Numbers must be ascending and unique");
    return {date:p[0],nums,max:nums[4]};
  });
  for(let i=1;i<draws.length;i++) if(draws[i-1].date>=draws[i].date) throw new Error("Dates not strictly increasing");
  const N=draws.length;
  if(N<3401) throw new Error("Canonical archive shorter than expected");
  function choose(n,k){let x=1;for(let i=1;i<=k;i++)x=x*(n-i+1)/i;return x;}
  function band(n){return n<=31?0:n<=36?1:n<=38?2:3;}
  function seeded(seed){let x=seed>>>0;return ()=>{x=(1664525*x+1013904223)>>>0;return x/4294967296;};}
  const den=choose(40,5),pmf=Array(41).fill(0);
  for(let n=5;n<=40;n++)pmf[n]=choose(n-1,4)/den;
  const hs=[60,120,240,480],alphas=[50,200,500,1000];
  const configs=hs.flatMap(h=>alphas.map(alpha=>({h,alpha,id:`h${h}_a${alpha}`})));
  const splitDefs=[{id:"discovery",start:200,end:1700},{id:"validation",start:1700,end:2550},{id:"blind_oos",start:2550,end:N}];
  function metrics(a){return {targets:a.n,top5:a.top5/a.n,top10:a.top10/a.n,top20:a.top20/a.n,meanRank:a.rank/a.n,brier:a.brier/a.n,logLoss:a.logloss/a.n};}
  const modelRuns={},baselineRuns={};
  for(const c of configs)modelRuns[c.id]={};
  for(const split of splitDefs){
    const b={n:0,top5:0,top10:0,top20:0,rank:0,brier:0,logloss:0};
    const accs={};configs.forEach(c=>accs[c.id]={n:0,top5:0,top10:0,top20:0,rank:0,brier:0,logloss:0});
    const i0=split.start,state={};
    for(const h of hs){
      const counts=Array.from({length:4},()=>Array(41).fill(0));
      for(let j=1;j<i0;j++)counts[band(draws[j-1].max)][draws[j].max]+=Math.pow(2,-(i0-j)/h);
      state[h]=counts;
    }
    for(let i=split.start;i<split.end;i++){
      const y=draws[i].max,ctx=band(draws[i-1].max),brank=41-y;
      let bs=0;for(let n=5;n<=40;n++)bs+=(pmf[n]-(n===y?1:0))**2;
      const bll=-Math.log(pmf[y]);
      b.n++;b.top5+=brank<=5;b.top10+=brank<=10;b.top20+=brank<=20;b.rank+=brank;b.brier+=bs;b.logloss+=bll;
      for(const c of configs){
        const row=state[c.h][ctx];let total=0;for(let n=5;n<=40;n++)total+=row[n];
        const p=Array(41).fill(0);for(let n=5;n<=40;n++)p[n]=(c.alpha*pmf[n]+row[n])/(c.alpha+total);
        const order=Array.from({length:36},(_,k)=>k+5).sort((a,z)=>p[z]-p[a]||z-a);
        const rank=order.indexOf(y)+1;let score=0;for(let n=5;n<=40;n++)score+=(p[n]-(n===y?1:0))**2;
        const a=accs[c.id];a.n++;a.top5+=rank<=5;a.top10+=rank<=10;a.top20+=rank<=20;a.rank+=rank;a.brier+=score;a.logloss+=-Math.log(p[y]);
      }
      if(i<split.end-1){
        for(const h of hs){
          const lambda=Math.pow(2,-1/h),counts=state[h];
          for(let q=0;q<4;q++)for(let n=5;n<=40;n++)counts[q][n]*=lambda;
          counts[band(draws[i-1].max)][y]+=lambda;
        }
      }
    }
    baselineRuns[split.id]=metrics(b);
    for(const c of configs)modelRuns[c.id][split.id]=metrics(accs[c.id]);
  }
  const validationSelection=configs.map(c=>({id:c.id,validation:modelRuns[c.id].validation})).sort((a,b)=>a.validation.brier-b.validation.brier);
  const selected=configs.find(c=>c.id===validationSelection[0].id);
  const blind=splitDefs.find(s=>s.id==="blind_oos");
  function computeDiffs(c){
    const i0=blind.start,counts=Array.from({length:4},()=>Array(41).fill(0));
    for(let j=1;j<i0;j++)counts[band(draws[j-1].max)][draws[j].max]+=Math.pow(2,-(i0-j)/c.h);
    const out={brier:[],logloss:[],top5:[]};
    for(let i=blind.start;i<blind.end;i++){
      const y=draws[i].max,ctx=band(draws[i-1].max),row=counts[ctx];let total=0;
      for(let n=5;n<=40;n++)total+=row[n];
      const p=Array(41).fill(0);for(let n=5;n<=40;n++)p[n]=(c.alpha*pmf[n]+row[n])/(c.alpha+total);
      const order=Array.from({length:36},(_,k)=>k+5).sort((a,z)=>p[z]-p[a]||z-a);
      const rank=order.indexOf(y)+1;let score=0,base=0;
      for(let n=5;n<=40;n++){score+=(p[n]-(n===y?1:0))**2;base+=(pmf[n]-(n===y?1:0))**2;}
      out.brier.push(score-base);
      out.logloss.push(-Math.log(p[y])+Math.log(pmf[y]));
      out.top5.push((rank<=5?1:0)-((41-y)<=5?1:0));
      if(i<blind.end-1){
        const lambda=Math.pow(2,-1/c.h);
        for(let q=0;q<4;q++)for(let n=5;n<=40;n++)counts[q][n]*=lambda;
        counts[band(draws[i-1].max)][y]+=lambda;
      }
    }
    return out;
  }
  const blindDiffs={};for(const c of configs)blindDiffs[c.id]=computeDiffs(c);
  const rng=seeded(20261108),block=7,reps=5000;
  function blockSums(arr){const sums=[];for(let i=0;i<arr.length;i+=block){let s=0;for(let j=i;j<Math.min(i+block,arr.length);j++)s+=arr[j];sums.push(s);}return sums;}
  const tests=[];
  for(const c of configs){
    const arr=blindDiffs[c.id].brier,sums=blockSums(arr),observed=sums.reduce((a,b)=>a+b,0);let count=0;
    for(let r=0;r<reps;r++){let value=0;for(const s of sums)value+=(rng()<.5?1:-1)*s;if(value<=observed)count++;}
    tests.push({id:c.id,p:(count+1)/(reps+1),observedDelta:arr.reduce((a,b)=>a+b,0)/arr.length});
  }
  const ordered=tests.slice().sort((a,b)=>a.p-b.p);let running=0;
  for(let i=0;i<ordered.length;i++){running=Math.max(running,Math.min(1,(ordered.length-i)*ordered[i].p));ordered[i].holm=running;}
  const holmMap=Object.fromEntries(ordered.map(x=>[x.id,x.holm]));
  const bootRng=seeded(20261109);
  function bootstrapCI(arr){
    const blocks=[];for(let i=0;i<arr.length;i+=block)blocks.push(arr.slice(i,Math.min(i+block,arr.length)));
    const means=[];
    for(let r=0;r<2000;r++){let sum=0,n=0;while(n<arr.length){const b=blocks[Math.floor(bootRng()*blocks.length)];for(const v of b){if(n>=arr.length)break;sum+=v;n++;}}means.push(sum/arr.length);}
    means.sort((a,b)=>a-b);return [means[Math.floor(.025*means.length)],means[Math.floor(.975*means.length)]];
  }
  const chosenDiff=blindDiffs[selected.id];
  const selectedBlindDeltaBrier=chosenDiff.brier.reduce((a,b)=>a+b,0)/chosenDiff.brier.length;
  const selectedBlindDeltaLogLoss=chosenDiff.logloss.reduce((a,b)=>a+b,0)/chosenDiff.logloss.length;
  const selectedBlindDeltaTop5=chosenDiff.top5.reduce((a,b)=>a+b,0)/chosenDiff.top5.length;
  const lastIndex=N,ctx=band(draws[N-1].max),futureCounts=Array.from({length:4},()=>Array(41).fill(0));
  for(let j=1;j<lastIndex;j++)futureCounts[band(draws[j-1].max)][draws[j].max]+=Math.pow(2,-(lastIndex-j)/selected.h);
  const frow=futureCounts[ctx];let ftotal=0;for(let n=5;n<=40;n++)ftotal+=frow[n];
  const futureP=Array(41).fill(0);for(let n=5;n<=40;n++)futureP[n]=(selected.alpha*pmf[n]+frow[n])/(selected.alpha+ftotal);
  const futureOrder=Array.from({length:36},(_,k)=>k+5).sort((a,z)=>futureP[z]-futureP[a]||z-a);
  const exactOrder=Array.from({length:36},(_,k)=>k+5).sort((a,z)=>pmf[z]-pmf[a]||z-a);
  const contextRanges=["5-31","32-36","37-38","39-40"];
  const contextMass=[5,32,37,39].map((lo,q)=>pmf.slice(lo,q===0?32:q===1?37:q===2?39:41).reduce((a,b)=>a+b,0));
  return {
    protocol:"FD-05 prior-only Markov context model for the P5 order statistic; exploratory/no promotion",
    archive:{sha:archiveSha,draws:N,first:draws[0].date,last:draws[N-1].date,latest:draws[N-1].nums},
    hypothesis:"P(max_t | band(max_{t-1})) may deviate from the exact order-statistic null; estimate context-conditioned maximum distributions with exponential decay and Dirichlet shrinkage toward the analytical null.",
    contextBands:contextRanges.map((range,i)=>({range,theoreticalMass:contextMass[i]})),
    grid:configs,
    splitDefinitions:splitDefs.map(s=>({id:s.id,startIndex:s.start,endExclusive:s.end,targets:s.end-s.start})),
    baseline:baselineRuns,
    models:modelRuns,
    validationSelection:validationSelection.map(x=>({id:x.id,brier:x.validation.brier,logLoss:x.validation.logLoss,top5:x.validation.top5})),
    selected:selected.id,
    blindTests:configs.map(c=>({id:c.id,deltaBrier:tests.find(t=>t.id===c.id).observedDelta,p:tests.find(t=>t.id===c.id).p,pHolm:holmMap[c.id]})),
    selectedBlindDeltaBrier,selectedBlindDeltaLogLoss,selectedBlindDeltaTop5,
    bootstrap95:{brier:bootstrapCI(chosenDiff.brier),top5:bootstrapCI(chosenDiff.top5)},
    selectedBlind:modelRuns[selected.id].blind_oos,
    baselineBlind:baselineRuns.blind_oos,
    prospectiveFreeze:{target:"next draw after 2026-11-07",cutoff:"2026-11-07",previousP5:draws[N-1].max,contextBand:contextRanges[ctx],selectedModel:selected.id,modelTop5Candidates:futureOrder.slice(0,5),modelTop10Candidates:futureOrder.slice(0,10),exactNullTop5Candidates:exactOrder.slice(0,5),exactNullTop10Candidates:exactOrder.slice(0,10),modelTop5Probabilities:futureOrder.slice(0,5).map(n=>({number:n,probability:futureP[n]}))},
    testSettings:{blockLength:7,permutationReplicates:5000,bootstrapReplicates:2000,permutationSeed:20261108,bootstrapSeed:20261109,holmFamily:"16 fixed configurations; one-sided blind-OOS Brier improvement"}
  };
}

const csv = fs.readFileSync(ARCHIVE_PATH, "utf8");
const blobSha = crypto.createHash("sha1").update(`blob ${Buffer.byteLength(csv)}\0`).update(csv).digest("hex");
if (blobSha !== EXPECTED_ARCHIVE_SHA) {
  throw new Error(`Archive blob SHA mismatch: expected ${EXPECTED_ARCHIVE_SHA}, got ${blobSha}`);
}
const generated = calculate(csv, blobSha);
if (process.argv.includes("--write")) {
  fs.writeFileSync(RESULT_PATH, JSON.stringify(generated, null, 2) + "\n");
  process.stdout.write(`Wrote ${RESULT_PATH}\n`);
} else if (process.argv.includes("--check")) {
  const expected = JSON.parse(fs.readFileSync(RESULT_PATH, "utf8"));
  function firstMismatch(actual, expected, path = "$") {
    if (typeof actual === "number" && typeof expected === "number") {
      return Math.abs(actual - expected) <= 1e-12 ? null : {path, actual, expected};
    }
    if (actual === null || expected === null || typeof actual !== typeof expected) {
      return actual === expected ? null : {path, actual, expected};
    }
    if (Array.isArray(actual) || Array.isArray(expected)) {
      if (!Array.isArray(actual) || !Array.isArray(expected) || actual.length !== expected.length) {
        return {path, actualLength: actual?.length, expectedLength: expected?.length};
      }
      for (let i = 0; i < actual.length; i++) {
        const mismatch = firstMismatch(actual[i], expected[i], `${path}[${i}]`);
        if (mismatch) return mismatch;
      }
      return null;
    }
    if (typeof actual === "object") {
      const actualKeys = Object.keys(actual).sort();
      const expectedKeys = Object.keys(expected).sort();
      if (JSON.stringify(actualKeys) !== JSON.stringify(expectedKeys)) {
        return {path, actualKeys, expectedKeys};
      }
      for (const key of actualKeys) {
        const mismatch = firstMismatch(actual[key], expected[key], `${path}.${key}`);
        if (mismatch) return mismatch;
      }
      return null;
    }
    return actual === expected ? null : {path, actual, expected};
  }
  const mismatch = firstMismatch(generated, expected);
  if (mismatch) throw new Error(`FD-05 persisted-output mismatch: ${JSON.stringify(mismatch)}`);
  process.stdout.write("FD-05 deterministic output matches persisted JSON.\n");
} else {
  process.stdout.write(JSON.stringify({selected: generated.selected, blind: generated.selectedBlind, deltaBrier: generated.selectedBlindDeltaBrier, pHolm: generated.blindTests.find(x => x.id === generated.selected).pHolm, prospectiveFreeze: generated.prospectiveFreeze}, null, 2) + "\n");
}
