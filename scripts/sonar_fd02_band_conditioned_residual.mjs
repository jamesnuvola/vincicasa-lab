#!/usr/bin/env node
/**
 * SONAR FD-02: band-conditioned residual / conditional randomization audit.
 * Uses prior-only exponentially decayed occurrence scores (half-life 200 draws),
 * the frozen FD-01 Gaussian smoother (sigma=4), and a reflected-boundary variant.
 * Exploratory diagnostic only; no model promotion.
 */
import fs from "node:fs";
import assert from "node:assert/strict";

const csv = fs.readFileSync(new URL("../data/storico_daily.csv", import.meta.url), "utf8").trim();
const lines = csv.split(/\r?\n/);
assert.equal(lines[0], "data,n1,n2,n3,n4,n5");
const rows = lines.slice(1).map(line => {
  const [date, ...numbers] = line.split(",");
  return { date, numbers: numbers.map(Number) };
});
const N = rows.length, M = 40, HALF_LIFE = 200, SIGMA = 4, WARMUP = 200;
const lambda = Math.pow(2, -1 / HALF_LIFE);
const bands = [[1,5],[6,10],[11,30],[31,35],[36,40]];
const bandIndex = n => bands.findIndex(([lo,hi]) => n >= lo && n <= hi);
const bandSizes = bands.map(([lo,hi]) => hi-lo+1);

let previousDate = "";
for (const row of rows) {
  assert.ok(row.date > previousDate, "dates must be unique and chronological");
  assert.equal(row.numbers.length, 5);
  assert.equal(new Set(row.numbers).size, 5, "each draw must contain five distinct numbers");
  assert.ok(row.numbers.every(n => Number.isInteger(n) && n >= 1 && n <= 40));
  previousDate = row.date;
}

const gaussian = (a,b) => Math.exp(-((a-b)**2)/(2*SIGMA*SIGMA));
const directKernel = Array.from({length:M},(_,n) =>
  Array.from({length:M},(_,k) => gaussian(n,k)));
const reflectedKernel = Array.from({length:M},(_,n) =>
  Array.from({length:M},(_,k) => {
    let weight = 0;
    // Image method on a reflected interval of 40 labels; period 80.
    for (let image=-3; image<=3; image++) {
      const direct = n-k+80*image;
      const mirror = n+k+1+80*image;
      weight += Math.exp(-(direct*direct)/(2*SIGMA*SIGMA));
      weight += Math.exp(-(mirror*mirror)/(2*SIGMA*SIGMA));
    }
    return weight;
  }));
const rowSums = matrix => matrix.map(row => row.reduce((sum,value) => sum+value,0));
const directNorm = rowSums(directKernel), reflectedNorm = rowSums(reflectedKernel);

const rankings = { raw: [], diff: [], ref: [] };
const rankMaps = { raw: [], diff: [], ref: [] };
const actual = [];
const decayed = Array(M).fill(0);
const makeRanking = scores => scores.map((score,index) => [index+1,score])
  .sort((a,b) => b[1]-a[1] || a[0]-b[0]).map(pair => pair[0]);

for (let target=0; target<N; target++) {
  if (target >= WARMUP) {
    const diffusion = Array(M).fill(0), reflected = Array(M).fill(0);
    for (let n=0; n<M; n++) {
      for (let k=0; k<M; k++) {
        diffusion[n] += directKernel[n][k]*decayed[k];
        reflected[n] += reflectedKernel[n][k]*decayed[k];
      }
      diffusion[n] /= directNorm[n];
      reflected[n] /= reflectedNorm[n];
    }
    const scoreSets = { raw: decayed.slice(), diff: diffusion, ref: reflected };
    for (const model of Object.keys(scoreSets)) {
      const order = makeRanking(scoreSets[model]);
      rankings[model].push(order);
      rankMaps[model].push(new Map(order.map((number,index) => [number,index+1])));
    }
    actual.push(rows[target].numbers.slice());
  }
  // Update only after scoring target: strictly prior-only features.
  for (let k=0; k<M; k++) decayed[k] *= lambda;
  for (const number of rows[target].numbers) decayed[number-1] += 1;
}

function splitMetrics(model,start,end) {
  let top5=0, top10=0, top20=0, rankSum=0, allFiveTop5=0;
  const perTargetTop5=[];
  for (let target=start; target<end; target++) {
    const index=target-WARMUP, rankMap=rankMaps[model][index];
    let hits5=0;
    for (const number of rows[target].numbers) {
      const rank=rankMap.get(number);
      rankSum += rank;
      if (rank<=5) { top5++; hits5++; }
      if (rank<=10) top10++;
      if (rank<=20) top20++;
    }
    if (hits5===5) allFiveTop5++;
    perTargetTop5.push(hits5);
  }
  const targets=end-start, cases=targets*5;
  return {
    targets,
    top5_hit_pct:Number((100*top5/cases).toFixed(4)),
    top10_hit_pct:Number((100*top10/cases).toFixed(4)),
    top20_hit_pct:Number((100*top20/cases).toFixed(4)),
    mean_rank:Number((rankSum/cases).toFixed(4)),
    top5_hits:top5,
    all_five_top5:allFiveTop5,
    per_target_top5:perTargetTop5
  };
}

function lcg(seed) {
  let state=seed>>>0;
  return () => { state=(1664525*state+1013904223)>>>0; return state/4294967296; };
}
function pairedBlockTest(model) {
  const candidate=splitMetrics(model,2550,3401).per_target_top5;
  const baseline=splitMetrics("raw",2550,3401).per_target_top5;
  const differences=candidate.map((value,index)=>value-baseline[index]);
  const observed=differences.reduce((sum,value)=>sum+value,0);
  const blockSums=[];
  for (let start=0; start<differences.length; start+=7)
    blockSums.push(differences.slice(start,start+7).reduce((sum,value)=>sum+value,0));
  let random=lcg(model==="diff"?10023:10024), exceed=0, reps=20000;
  for (let rep=0; rep<reps; rep++) {
    let nullSum=0;
    for (const value of blockSums) nullSum += (random()<0.5 ? 1 : -1)*value;
    if (nullSum >= observed-1e-12) exceed++;
  }
  random=lcg(model==="diff"?20023:20024);
  const bootstrap=[];
  for (let rep=0; rep<5000; rep++) {
    let sum=0,count=0;
    while (count<differences.length) {
      const start=Math.floor(random()*differences.length);
      for (let j=0; j<7 && count<differences.length; j++,count++)
        sum += differences[(start+j)%differences.length];
    }
    bootstrap.push(sum/differences.length);
  }
  bootstrap.sort((a,b)=>a-b);
  const meanDelta=observed/differences.length;
  return {
    mean_delta_hits_per_target:Number(meanDelta.toFixed(5)),
    delta_top5_percentage_points:Number((meanDelta/5*100).toFixed(4)),
    block7_permutation_p_one_sided:(exceed+1)/(reps+1),
    moving_block_bootstrap_95_hits_per_target:[
      Number(bootstrap[Math.floor(0.025*bootstrap.length)].toFixed(5)),
      Number(bootstrap[Math.floor(0.975*bootstrap.length)].toFixed(5))
    ],
    block_count:blockSums.length
  };
}

function conditionalRandomization(model,reps=10000) {
  const records=[];
  let observed=0, analyticExpected=0;
  for (let target=2550; target<3401; target++) {
    const index=target-WARMUP, prediction=rankings[model][index].slice(0,5);
    const actualSet=new Set(rows[target].numbers), forecastCounts=Array(5).fill(0), actualCounts=Array(5).fill(0);
    let hits=0;
    for (const number of prediction) {
      forecastCounts[bandIndex(number)]++;
      if (actualSet.has(number)) hits++;
    }
    for (const number of actualSet) actualCounts[bandIndex(number)]++;
    let expected=0;
    for (let b=0; b<5; b++) expected += forecastCounts[b]*actualCounts[b]/bandSizes[b];
    records.push({forecastCounts,actualSet,hits,expected});
    observed += hits;
    analyticExpected += expected;
  }
  const groups=bands.map(([lo,hi]) => Array.from({length:hi-lo+1},(_,i)=>lo+i));
  const random=lcg(model==="raw"?42001:model==="diff"?42002:42003);
  let upper=0, nullSum=0, nullValues=new Array(reps);
  for (let rep=0; rep<reps; rep++) {
    let total=0;
    for (const record of records) {
      for (let b=0; b<5; b++) {
        const group=groups[b], selected=record.forecastCounts[b], swaps=[];
        for (let j=0; j<selected; j++) {
          const k=j+Math.floor(random()*(group.length-j));
          [group[j],group[k]]=[group[k],group[j]];
          swaps.push(k);
          if (record.actualSet.has(group[j])) total++;
        }
        for (let j=selected-1; j>=0; j--) {
          const k=swaps[j];
          [group[j],group[k]]=[group[k],group[j]];
        }
      }
    }
    nullValues[rep]=total;
    nullSum += total;
    if (total>=observed) upper++;
  }
  nullValues.sort((a,b)=>a-b);
  return {
    observed_hits:observed,
    analytic_conditional_expected:Number(analyticExpected.toFixed(3)),
    excess_vs_conditional_expected:Number((observed-analyticExpected).toFixed(3)),
    mc_replicates:reps,
    mc_null_mean:Number((nullSum/reps).toFixed(3)),
    mc_null_95:[nullValues[Math.floor(0.025*reps)],nullValues[Math.floor(0.975*reps)]],
    upper_tail_p:(upper+1)/(reps+1)
  };
}
function holm(modelPValues) {
  const ordered=Object.entries(modelPValues).sort((a,b)=>a[1]-b[1]);
  let previous=0;
  const adjusted={};
  ordered.forEach(([model,p],index) => {
    const value=Math.min(1,p*(ordered.length-index));
    previous=Math.max(previous,value);
    adjusted[model]=previous;
  });
  return adjusted;
}

const splits={discovery:[200,1700],validation:[1700,2550],blind_oos:[2550,3401]};
const metrics={};
for (const [split,[start,end]] of Object.entries(splits)) {
  metrics[split]={};
  for (const model of ["raw","diff","ref"]) {
    const result=splitMetrics(model,start,end);
    delete result.per_target_top5;
    metrics[split][model]=result;
  }
}
const paired={diff_vs_raw:pairedBlockTest("diff"),ref_vs_raw:pairedBlockTest("ref")};
paired.holm_adjusted_p=holm({
  diff:paired.diff_vs_raw.block7_permutation_p_one_sided,
  reflected:paired.ref_vs_raw.block7_permutation_p_one_sided
});
const conditional={
  raw:conditionalRandomization("raw"),
  diff:conditionalRandomization("diff"),
  ref:conditionalRandomization("ref")
};
conditional.holm_adjusted_upper_tail_p=holm({
  raw:conditional.raw.upper_tail_p,
  diff:conditional.diff.upper_tail_p,
  reflected:conditional.ref.upper_tail_p
});

const nextDate=new Date(`${rows[N-1].date}T00:00:00Z`);
nextDate.setUTCDate(nextDate.getUTCDate()+1);
const targetDate=nextDate.toISOString().slice(0,10);
const currentDiffusion=Array(M).fill(0), currentReflected=Array(M).fill(0);
for (let n=0; n<M; n++) {
  for (let k=0; k<M; k++) {
    currentDiffusion[n] += directKernel[n][k]*decayed[k];
    currentReflected[n] += reflectedKernel[n][k]*decayed[k];
  }
  currentDiffusion[n] /= directNorm[n];
  currentReflected[n] /= reflectedNorm[n];
}
const currentScores={raw:decayed.slice(),diff:currentDiffusion,ref:currentReflected};
const currentForecast={target_date:targetDate,history_cutoff:rows[N-1].date,archive_draws:N};
for (const model of ["raw","diff","ref"]) {
  const order=makeRanking(currentScores[model]);
  currentForecast[model]={top20:order.slice(0,20),top10:order.slice(0,10),top5:order.slice(0,5)};
}
console.log(JSON.stringify({
  status:"EXPLORATORY_NOT_PROMOTABLE",
  archive:{draws:N,first_date:rows[0].date,last_date:rows[N-1].date,warmup:WARMUP},
  parameters:{half_life_draws:HALF_LIFE,sigma:SIGMA,block_length:7,conditional_randomization_replicates:10000},
  metrics,paired,conditional,currentForecast
},null,2));
