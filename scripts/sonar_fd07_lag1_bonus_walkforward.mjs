#!/usr/bin/env node
'use strict';
// FD-07: strict-prior exponential frequency with a standardized lag-1 bonus.
// Deterministic, dependency-free research script. No promotion is performed.
const fs = require('node:fs');
const crypto = require('node:crypto');
const csv = fs.readFileSync(process.argv[2] || 'data/storico_daily.csv', 'utf8');
const expectedBlob = '5d2efd70684e918b27d8f06386d545647898336d';
const gitBlob = crypto.createHash('sha1').update('blob ' + Buffer.byteLength(csv) + '\\0').update(csv).digest('hex');
if (gitBlob !== expectedBlob) throw new Error('Canonical archive Git blob SHA mismatch: ' + gitBlob);
const lines = csv.trim().split(/\\r?\\n/);
if (lines[0] !== 'data,n1,n2,n3,n4,n5') throw new Error('Unexpected CSV header');
const rows = lines.slice(1).map(line => {
  const p = line.split(',');
  return { date: p[0], nums: p.slice(1).map(Number) };
});
const N = rows.length;
if (N !== 3401 || rows[0].date !== '2017-07-17' || rows[N-1].date !== '2026-11-07') throw new Error('Unexpected archive bounds');
for (let i=0;i<N;i++) {
  const r=rows[i];
  if (r.nums.length!==5 || new Set(r.nums).size!==5 || r.nums.some(n=>!Number.isInteger(n)||n<1||n>40) || (i && rows[i-1].date>=r.date)) throw new Error('Archive structural validation failed at row '+i);
}
const hs=[60,120,200,400], lambdas=[0,0.25,0.5,1,1.5,2];
const models=hs.flatMap(h=>lambdas.map(l=>({h,l,key:'h'+h+'_l'+l})));
const scores=Object.fromEntries(hs.map(h=>[h,Array(41).fill(0)]));
const decay=Object.fromEntries(hs.map(h=>[h,Math.pow(2,-1/h)]));
const hits=Object.fromEntries(models.map(m=>[m.key,Array(N).fill(0)]));
const lagHits=Array(N).fill(0);
function rankFor(h,l,previous) {
  const s=scores[h];
  const mean=s.slice(1).reduce((a,b)=>a+b,0)/40;
  const sd=Math.sqrt(s.slice(1).reduce((a,b)=>a+(b-mean)*(b-mean),0)/40);
  return Array.from({length:40},(_,i)=>i+1).sort((a,b)=>{
    const sa=s[a]+l*sd*(previous.has(a)?1:0);
    const sb=s[b]+l*sd*(previous.has(b)?1:0);
    return (sb-sa)||a-b;
  });
}
for (let t=0;t<N;t++) {
  if (t>=200) {
    const previous=new Set(rows[t-1].nums), actual=new Set(rows[t].nums);
    lagHits[t]=rows[t].nums.filter(n=>previous.has(n)).length;
    for (const m of models) hits[m.key][t]=rankFor(m.h,m.l,previous).slice(0,5).filter(n=>actual.has(n)).length;
  }
  // Only after scoring target t, incorporate draw t for target t+1.
  for (const h of hs) {
    const s=scores[h], d=decay[h];
    for (let n=1;n<=40;n++) s[n]*=d;
    for (const n of rows[t].nums) s[n]+=1;
  }
}
const split={discovery:[200,1700],validation:[1700,2550],blind:[2550,N]};
function summarize(arr,a,b) {
  const count=arr.slice(a,b).reduce((x,y)=>x+y,0), n=b-a;
  return {targets:n,hits:count,hitSharePct:100*count/(5*n),meanHitsPerDraw:count/n};
}
const metrics=Object.fromEntries(models.map(m=>[m.key,Object.fromEntries(Object.entries(split).map(([name,[a,b]])=>[name,summarize(hits[m.key],a,b)]))]));
const lagMetrics=Object.fromEntries(Object.entries(split).map(([name,[a,b]])=>[name,summarize(lagHits,a,b)]));
const selected=[...models].sort((a,b)=>metrics[b.key].validation.hits-metrics[a.key].validation.hits||a.l-b.l||a.h-b.h)[0];
const sameHNoLag=models.find(m=>m.h===selected.h&&m.l===0);
const diff=Array.from({length:851},(_,i)=>hits[selected.key][2550+i]-hits[sameHNoLag.key][2550+i]);
const blockLen=7, blockCount=Math.floor(diff.length/blockLen);
const blockSums=Array.from({length:blockCount},(_,j)=>diff.slice(j*blockLen,(j+1)*blockLen).reduce((a,b)=>a+b,0));
const observedBlockSum=blockSums.reduce((a,b)=>a+b,0);
let seed=20261108;
function rand(){seed=(Math.imul(1664525,seed)+1013904223)>>>0;return seed/4294967296;}
const bootstrapReplicates=20000, boot=[];
for(let r=0;r<bootstrapReplicates;r++){let s=0;for(let j=0;j<blockCount;j++)s+=blockSums[Math.floor(rand()*blockCount)];boot.push(s/(blockCount*blockLen));}
boot.sort((a,b)=>a-b);
const bootCI=[boot[Math.floor(0.025*bootstrapReplicates)],boot[Math.floor(0.975*bootstrapReplicates)]];
const signFlipReplicates=50000;let extreme=0;
for(let r=0;r<signFlipReplicates;r++){let s=0;for(let j=0;j<blockCount;j++)s+=(rand()<0.5?1:-1)*blockSums[j];if(Math.abs(s)>=Math.abs(observedBlockSum))extreme++;}
const signFlipP=(extreme+1)/(signFlipReplicates+1);
function choose(n,k){if(k<0||k>n)return 0;k=Math.min(k,n-k);let x=1;for(let i=1;i<=k;i++)x=x*(n-k+i)/i;return x;}
const denom=choose(40,5), pmf=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/denom);
let seed2=20261109;
function rand2(){seed2=(Math.imul(1664525,seed2)+1013904223)>>>0;return seed2/4294967296;}
const mcReplicates=20000, nullTotals=[];
for(let r=0;r<mcReplicates;r++){let total=0;for(let t=0;t<851;t++){const u=rand2();let acc=0,k=5;for(let j=0;j<6;j++){acc+=pmf[j];if(u<acc){k=j;break;}}total+=k;}nullTotals.push(total);}
nullTotals.sort((a,b)=>a-b);
function mcP(observed){let lo=0,hi=nullTotals.length;while(lo<hi){const mid=(lo+hi)>>1;if(nullTotals[mid]<observed)lo=mid+1;else hi=mid;}return (nullTotals.length-lo+1)/(mcReplicates+1);}
const observedByModel=Object.fromEntries(models.map(m=>[m.key,metrics[m.key].blind.hits]));
observedByModel.lag1_only=lagMetrics.blind.hits;
const rawP=Object.fromEntries(Object.entries(observedByModel).map(([key,obs])=>[key,mcP(obs)]));
const ordered=Object.entries(rawP).sort((a,b)=>a[1]-b[1]);let priorAdjusted=0;const holm={};
for(let i=0;i<ordered.length;i++){priorAdjusted=Math.max(priorAdjusted,Math.min(1,(ordered.length-i)*ordered[i][1]));holm[ordered[i][0]]=priorAdjusted;}
const prospectiveRank=rankFor(selected.h,selected.l,new Set(rows[N-1].nums));
const prospective={target:'2026-11-08',cutoff:'2026-11-07',selectedModel:selected.key,top5:prospectiveRank.slice(0,5),top5Scores:prospectiveRank.slice(0,5).map(n=>{const s=scores[selected.h],mean=s.slice(1).reduce((a,b)=>a+b,0)/40,sd=Math.sqrt(s.slice(1).reduce((a,b)=>a+(b-mean)*(b-mean),0)/40);return {number:n,score:s[n]+selected.l*sd*(rows[N-1].nums.includes(n)?1:0),lag1:rows[N-1].nums.includes(n)};})};
const output={
 protocol:{archivePath:'data/storico_daily.csv',archiveBlobSha:expectedBlob,archiveRows:N,firstDate:rows[0].date,lastDate:rows[N-1].date,minHistory:200,split,primaryEndpoint:'per-draw count of actual numbers within the model Top-5 candidate set; random Top-5 expectation 0.625 hits/draw (12.5% of five actual numbers)',gridSize:24,validationSelection:'maximize validation Top-5 hit count; tie-break lower lag bonus, then lower half-life',randomNullFamilySize:25,randomNullMethod:'20,000 Monte Carlo replicates of 851 independent Hypergeometric(40,5,5) overlaps; one-sided greater tail; Holm correction',nullSeed:20261109},
 selected,baseline:sameHNoLag,
 metrics:{selected:metrics[selected.key],sameHalfLifeNoLag:metrics[sameHNoLag.key],lag1Only:lagMetrics},
 blindPaired:{targets:851,selectedHits:metrics[selected.key].blind.hits,baselineHits:metrics[sameHNoLag.key].blind.hits,deltaHits:metrics[selected.key].blind.hits-metrics[sameHNoLag.key].blind.hits,deltaPctPoints:100*(metrics[selected.key].blind.hits-metrics[sameHNoLag.key].blind.hits)/(851*5),blockLength:7,completeBlocks:blockCount,tailTargetsExcludedFromBlockTest:diff.length-blockCount*blockLen,blockSignFlipReplicates:signFlipReplicates,pTwoSided:signFlipP,blockBootstrapReplicates:bootstrapReplicates,bootstrapCI_meanDeltaHitsPerDraw:bootCI,bootstrapCI_hitSharePercentagePoints:bootCI.map(x=>x*20)},
 randomNull:{hypergeomPMF:pmf,replicates:mcReplicates,bestRaw:ordered[0],bestHolm:holm[ordered[0][0]],selectedRaw:rawP[selected.key],selectedHolm:holm[selected.key],lag1Raw:rawP.lag1_only,lag1Holm:holm.lag1_only,allModels:models.map(m=>({key:m.key,blindHits:observedByModel[m.key],pRaw:rawP[m.key],pHolm:holm[m.key]})).concat([{key:'lag1_only',blindHits:lagMetrics.blind.hits,pRaw:rawP.lag1_only,pHolm:holm.lag1_only}])},
 prospectiveFreeze:prospective,
 grid:models.map(m=>({key:m.key,h:m.h,l:m.l,discovery:metrics[m.key].discovery.hitSharePct,validation:metrics[m.key].validation.hitSharePct,blind:metrics[m.key].blind.hitSharePct,blindHits:metrics[m.key].blind.hits,pHolm:holm[m.key]}))
};
console.log(JSON.stringify(output,null,2));
