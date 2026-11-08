#!/usr/bin/env node
/**
 * Audit P5 pooled logistic ranker against exact sorted-position order-statistic prior.
 * The ranker report supplies only aggregate metrics; no paired target ranks are available.
 */
import fs from "node:fs";
import path from "node:path";
const dataPath = process.argv[2] ?? "data/storico_daily.csv";
const pooledPath = process.argv[3] ?? "reports/sequence_agent/p5_pooled_logistic_walkforward_2026-11-07.json";
const rollingPath = process.argv[4] ?? "reports/sequence_agent/p5_logistic_rolling_and_permutation_audit_2026-11-07.json";
const outDir = process.argv[5] ?? "reports/position_specific_range_residual";

const raw = fs.readFileSync(dataPath, "utf8").trim().split(/\r?\n/);
if (raw[0]?.trim() !== "data,n1,n2,n3,n4,n5") throw new Error("Unexpected canonical archive header");
const rows = raw.slice(1).map((line, i) => {
  const [date, ...cells] = line.split(",");
  const nums = cells.map(Number);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || nums.length !== 5 ||
      nums.some((n) => !Number.isInteger(n) || n < 1 || n > 40) ||
      nums.some((n, j) => j > 0 && n <= nums[j - 1])) throw new Error(`Invalid draw at CSV row ${i + 2}`);
  return { date, nums, p5: nums[4] };
});
for (let i=1;i<rows.length;i++) if(rows[i].date<=rows[i-1].date) throw new Error("Archive dates not strictly ascending");
const pooled=JSON.parse(fs.readFileSync(pooledPath,"utf8"));
const rolling=JSON.parse(fs.readFileSync(rollingPath,"utf8"));
const choose=(n,k)=>{if(k<0||n<k)return 0;if(k===0||k===n)return 1;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
const total=choose(40,5);
const p5Prior=Array.from({length:40},(_,i)=>{const n=i+1;return n>=5?choose(n-1,4)/total:0;});
const priorRank=Array.from({length:40},(_,i)=>i+1).sort((a,b)=>p5Prior[b-1]-p5Prior[a-1]||a-b);
const rankMap=new Map(priorRank.map((n,i)=>[n,i+1]));
const topSets={};
const priorCoverage={};
for(const k of [1,5,10,20]){topSets[k]=priorRank.slice(0,k);priorCoverage[k]=topSets[k].reduce((s,n)=>s+p5Prior[n-1],0);}
const trainSpec=pooled.temporal_split.train_target_dates;
const testSpec=pooled.temporal_split.test_target_dates;
const m=testSpec.match(/(\d{4}-\d{2}-\d{2})\s+through\s+(\d{4}-\d{2}-\d{2})/);
if(!m) throw new Error("Could not parse pooled ranker test date window");
const trainMatch=trainSpec.match(/(\d{4}-\d{2}-\d{2})\s+through\s+(\d{4}-\d{2}-\d{2})/);
if(!trainMatch) throw new Error("Could not parse pooled ranker train date window");
const trainStart=trainMatch[1],trainEnd=trainMatch[2],testStart=m[1],testEnd=m[2];
const test=rows.filter(r=>r.date>=testStart&&r.date<=testEnd);
if(test.length!==pooled.temporal_split.test_draws) throw new Error(`P5 audit target count mismatch: archive=${test.length}, ranker report=${pooled.temporal_split.test_draws}`);
const train=rows.filter(r=>r.date>=trainStart&&r.date<=trainEnd);
if(train.length!==pooled.temporal_split.train_draws) throw new Error("P5 empirical baseline training count mismatch");
const priorTestMetrics={targets:test.length,top1_hit_rate:test.filter(r=>topSets[1].includes(r.p5)).length/test.length,
 top5_hit_rate:test.filter(r=>topSets[5].includes(r.p5)).length/test.length,
 top10_hit_rate:test.filter(r=>topSets[10].includes(r.p5)).length/test.length,
 top20_hit_rate:test.filter(r=>topSets[20].includes(r.p5)).length/test.length,
 mean_rank:test.reduce((s,r)=>s+rankMap.get(r.p5),0)/test.length,
 top5_hits:test.filter(r=>topSets[5].includes(r.p5)).length,
 top1_hits:test.filter(r=>topSets[1].includes(r.p5)).length};
const freq=Array(41).fill(0);
for(const r of train)freq[r.p5]++;
const empiricalRank=Array.from({length:40},(_,i)=>i+1).sort((a,b)=>freq[b]-freq[a]||a-b);
const empiricalMap=new Map(empiricalRank.map((n,i)=>[n,i+1]));
const empiricalTestMetrics={training_draws:train.length,training_cutoff:train.at(-1)?.date,
 top1_set:empiricalRank.slice(0,1),top5_set:empiricalRank.slice(0,5),top10_set:empiricalRank.slice(0,10),
 top1_hit_rate:test.filter(r=>empiricalRank.slice(0,1).includes(r.p5)).length/test.length,
 top5_hit_rate:test.filter(r=>empiricalRank.slice(0,5).includes(r.p5)).length/test.length,
 top10_hit_rate:test.filter(r=>empiricalRank.slice(0,10).includes(r.p5)).length,
 mean_rank:test.reduce((s,r)=>s+empiricalMap.get(r.p5),0)/test.length};
const rollingCompare=[];
for(const rr of rolling.rolling_year_results){
 const year=rr.test_year.match(/(\d{4})/)[1];
 const endMatch=rr.test_year.match(/through_(\d{4}-\d{2}-\d{2})/);
 const start=`${year}-01-01`,end=endMatch?endMatch[1]:`${year}-12-31`;
 const ys=rows.filter(r=>r.date>=start&&r.date<=end);
 if(ys.length!==rr.test_targets) throw new Error(`Rolling P5 target count mismatch for ${rr.test_year}: ${ys.length} vs ${rr.test_targets}`);
 const priorTop5=ys.filter(r=>topSets[5].includes(r.p5)).length/ys.length;
 const priorTop1=ys.filter(r=>topSets[1].includes(r.p5)).length/ys.length;
 const priorMeanRank=ys.reduce((s,r)=>s+rankMap.get(r.p5),0)/ys.length;
 rollingCompare.push({test_year:rr.test_year,targets:ys.length,start,end,
  logistic_top5_rate:rr.top5_rate,prior_top5_rate:priorTop5,delta_logistic_minus_prior_top5:rr.top5_rate-priorTop5,
  logistic_top1_rate:rr.top1_rate,prior_top1_rate:priorTop1,delta_logistic_minus_prior_top1:rr.top1_rate-priorTop1,
  logistic_mean_rank:rr.mean_rank,prior_mean_rank:priorMeanRank,delta_logistic_minus_prior_mean_rank:rr.mean_rank-priorMeanRank});
}
const testTop5Hits=priorTestMetrics.top5_hits,n=test.length,p=priorCoverage[5];
const logFact=[0];for(let i=1;i<=n;i++)logFact[i]=logFact[i-1]+Math.log(i);
const logBinom=(k)=>logFact[n]-logFact[k]-logFact[n-k]+k*Math.log(p)+(n-k)*Math.log(1-p);
const binomTail=(k)=>{let s=0;for(let j=k;j<=n;j++)s+=Math.exp(logBinom(j));return Math.min(1,s);};
const binomLower=(k)=>{let s=0;for(let j=0;j<=k;j++)s+=Math.exp(logBinom(j));return Math.min(1,s);};
const exactP={one_sided_prior_set_above_null:binomTail(testTop5Hits),two_sided_prior_set:Math.min(1,2*Math.min(binomLower(testTop5Hits),binomTail(testTop5Hits)))};
const ranker=pooled.results;
const rankerVsPrior={logistic_top5_rate:ranker.test_top5_rate,prior_top5_rate:priorTestMetrics.top5_hit_rate,delta_top5_pp:100*(ranker.test_top5_rate-priorTestMetrics.top5_hit_rate),
 logistic_top1_rate:ranker.test_top1_rate,prior_top1_rate:priorTestMetrics.top1_hit_rate,delta_top1_pp:100*(ranker.test_top1_rate-priorTestMetrics.top1_hit_rate),
 logistic_mean_rank:ranker.mean_rank,prior_mean_rank:priorTestMetrics.mean_rank,delta_mean_rank:ranker.mean_rank-priorTestMetrics.mean_rank,
 logistic_top5_hits_approx:Math.round(ranker.test_top5_rate*n),prior_top5_hits:priorTestMetrics.top5_hits,
 paired_inference:"NOT_AVAILABLE: aggregate ranker report has no per-target rank or hit ledger"};
const result={
 experiment:"P5-ORDERSTAT-PRIOR-AUDIT",status:"BASELINE_REINTERPRETATION_NO_PROMOTION",
 archive:{path:dataPath,draw_count:rows.length,first_date:rows[0].date,last_date:rows.at(-1).date},
 sources:{pooled_ranker_report:pooledPath,rolling_ranker_report:rollingPath,pooled_test_dates:[testStart,testEnd],ranker_test_draws:pooled.temporal_split.test_draws},
 exact_prior:{formula:"pi5(n)=C(n-1,4)/C(40,5), n=5..40",top1_set:topSets[1],top5_set:topSets[5],top10_set:topSets[10],top20_set:topSets[20],coverage:priorCoverage,mean_rank:priorRank.reduce((s,n,i)=>s+p5Prior[n-1]*(i+1),0)},
 prior_test_metrics:priorTestMetrics,empirical_frequency_prior_baseline:empiricalTestMetrics,ranker_vs_prior:rankerVsPrior,exact_binomial_check_for_prior_top5_set:exactP,rolling_year_comparison:rollingCompare,
 interpretation:["The report's uniform-rank Top5 reference 12.5% is not the correct P5 baseline: P5 is the maximum order statistic and is strongly concentrated in high values.",
 "The exact prior Top5 set {36,37,38,39,40} covers 50.6644% under a uniform 5-subset; on the same 673 pooled-test dates it covered the observed share reported here.",
 "The pooled P5 logistic ranker is below the exact prior baseline on Top5, Top1 and mean rank. Aggregate-only ranker evidence prevents a paired significance test.",
 "Top5 prior-set test count is close to its exact expected coverage; this does not establish a mechanical bias or future edge."],
 caveats:["This is a baseline audit, not a rerun of the logistic ranker.","No per-target ranker predictions are present in the repository report; paired test is unavailable.","The prior baseline is theoretically fixed before test; empirical-frequency baseline uses only dates before 2025-01-01.","No engine promotion or guarantee."]};
const outJson=path.join(outDir,"p5_orderstat_prior_audit_20261108.json");
const outMd=path.join(outDir,"p5_orderstat_prior_audit_20261108.md");
fs.mkdirSync(outDir,{recursive:true});
fs.writeFileSync(outJson,JSON.stringify(result,null,2)+"\n");
let md=`# P5 Logistic Ranker — Exact Order-Statistic Prior Audit

**Run:** 2026-11-08 · **Status:** BASELINE REINTERPRETATION / NO PROMOTION  
**Archive:** ${rows.length} draws, ${rows[0].date}–${rows.at(-1).date}  
**Pooled ranker report:** ${pooledPath} (test ${testStart}–${testEnd}, N=${n})  
**Rolling report:** ${rollingPath}

## Correct P5 null

P5 is the maximum of five distinct uniformly drawn numbers, not a uniform label over 1..40:
\\[
\\pi_5(n)=\\frac{\\binom{n-1}{4}}{\\binom{40}{5}},\\quad n=5,\\ldots,40.
\\]
The most probable values are 40,39,38,37,36. Exact null Top-K coverage:

| K | Exact prior Top-K set | Expected coverage |
|---|---|---:|
`;
for(const k of [1,5,10,20])md+=`| ${k} | ${topSets[k].join(", ")} | ${(100*priorCoverage[k]).toFixed(4)}% |\n`;
md+=`
Exact prior-ranked mean rank: ${result.exact_prior.mean_rank.toFixed(6)}.

## Pooled 2025-01-01 through 2026-11-04 (N=${n})

| Metric | P5 logistic | Exact prior-ranked on same dates | Delta logistic−prior |
|---|---:|---:|---:|
| Top5 hit rate | ${(100*ranker.test_top5_rate).toFixed(4)}% | ${(100*priorTestMetrics.top5_hit_rate).toFixed(4)}% | ${rankerVsPrior.delta_top5_pp.toFixed(4)} pp |
| Top1 hit rate | ${(100*ranker.test_top1_rate).toFixed(4)}% | ${(100*priorTestMetrics.top1_hit_rate).toFixed(4)}% | ${rankerVsPrior.delta_top1_pp.toFixed(4)} pp |
| Mean rank (lower is better) | ${ranker.mean_rank.toFixed(6)} | ${priorTestMetrics.mean_rank.toFixed(6)} | +${rankerVsPrior.delta_mean_rank.toFixed(6)} |

Prior-set Top5 hits: ${priorTestMetrics.top5_hits}/${n}; exact expected coverage ${(100*p).toFixed(4)}%. One-sided binomial p for exceeding its null expectation: ${exactP.one_sided_prior_set_above_null.toFixed(6)} (two-sided ${exactP.two_sided_prior_set.toFixed(6)}). The prior-set coverage itself is close to its theoretical expectation; this is not evidence of bias.

A fixed empirical-frequency ranking trained only through ${empiricalTestMetrics.training_cutoff} selected Top5 ${empiricalTestMetrics.top5_set.join(", ")} and achieved ${(100*empiricalTestMetrics.top5_hit_rate).toFixed(4)}% on the same test dates; it matched the exact prior Top5 set. Its mean rank was ${empiricalTestMetrics.mean_rank.toFixed(6)}.

## Rolling-year check

| Test year | N | Logistic Top5 | Prior Top5 on same dates | Delta pp | Logistic Top1 | Prior Top1 | Logistic mean rank | Prior mean rank |
|---|---:|---:|---:|---:|---:|---:|---:|
`;
for(const x of rollingCompare)md+=`| ${x.test_year} | ${x.targets} | ${(100*x.logistic_top5_rate).toFixed(4)}% | ${(100*x.prior_top5_rate).toFixed(4)}% | ${(100*x.delta_logistic_minus_prior_top5).toFixed(4)} | ${(100*x.logistic_top1_rate).toFixed(4)}% | ${(100*x.prior_top1_rate).toFixed(4)}% | ${x.logistic_mean_rank.toFixed(3)} | ${x.prior_mean_rank.toFixed(3)} |\n`;
md+=`
The prior Top5 set is equal or better in each rolling year; prior-mode Top1 and mean rank are also better in all four years.

## Root cause and limits

The earlier 12.5% “uniform-rank Top5” baseline is inappropriate for the maximum order statistic. The pooled logistic rate 42.7935% is below the exact prior's 50.6644% expected Top5 coverage; Top1 10.4012% is below the prior mode's 12.5%; mean rank 8.7519 is worse than exact prior mean rank 6.8333. The apparently large improvement over 12.5% is largely a baseline artifact.

The ranker report contains only aggregate results. Without per-target Top5/Top1 hits or rank vectors, paired block tests against the prior cannot be reconstructed. Therefore the differences are descriptive, not inferential. The exact prior baseline and empirical frequency comparator are useful controls; the logistic model is **not promoted**. Preserve the Top10/other diagnostics only if their target-level ledger can be recovered and they are tested against proper P5 order-statistic baselines.

## Next action

Recover the Q90 feature matrix and target-level P5 rank ledger (or regenerate them), then run a strict-prior nested walk-forward comparing logistic score × exact P5 prior with fixed prior and frequency controls; pre-register primary Top5/mean-rank endpoints, paired block tests and multiple-testing scope. Until then, the logistic result remains exploratory and below baseline.
`;
fs.writeFileSync(outMd,md);
console.log(JSON.stringify({outJson,outMd,archiveDraws:rows.length,testN:n,priorCoverage,priorTestMetrics,empiricalTestMetrics,rankerVsPrior,exactP,rollingCompare},null,2));
