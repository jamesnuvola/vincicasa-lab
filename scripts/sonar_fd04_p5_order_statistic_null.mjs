#!/usr/bin/env node
import fs from "node:fs";
const csv=fs.readFileSync(new URL("../data/storico_daily.csv",import.meta.url),"utf8");
function analyze(csv){
 const lines=csv.trim().split(/\r?\n/);
 if(lines[0]!=="data,n1,n2,n3,n4,n5")throw new Error("bad CSV header");
 const rows=lines.slice(1).map(line=>{const [date,...numbers]=line.split(",");return {date,numbers:numbers.map(Number)};});
 let previous="";
 for(const row of rows){if(row.date<=previous||row.numbers.length!==5||new Set(row.numbers).size!==5||!row.numbers.every(n=>Number.isInteger(n)&&n>=1&&n<=40))throw new Error("invalid archive row "+row.date);previous=row.date;}
 const N=rows.length,W=200,halfLives=[100,200,500],alphas=[50,200,500],splits=["discovery","validation","blind_oos"];
 const splitOf=t=>t<1700?"discovery":t<2550?"validation":"blind_oos";
 const p0=Array(41).fill(0);for(let n=5;n<=40;n++)p0[n]=((n-1)*(n-2)*(n-3)*(n-4))/24;const norm=p0.reduce((a,b)=>a+b,0);for(let n=5;n<=40;n++)p0[n]/=norm;
 const configs=halfLives.flatMap(h=>alphas.map(alpha=>({h,alpha,id:"h"+h+"_a"+alpha,lambda:Math.pow(2,-1/h)})));
 const baseline=Object.fromEntries(splits.map(s=>[s,{n:0,h5:0,h10:0,h20:0,rank:0,brier:0,logloss:0}]));
 const metrics=Object.fromEntries(configs.map(c=>[c.id,Object.fromEntries(splits.map(s=>[s,{n:0,h5:0,h10:0,h20:0,rank:0,brier:0,logloss:0}]))]));
 const deltas=Object.fromEntries(configs.map(c=>[c.id,{hit5:[],brier:[],logloss:[]}]));
 const counts=Object.fromEntries(configs.map(c=>[c.id,Array(41).fill(0)])),p0brier=p0.reduce((s,p)=>s+p*p,0);
 for(let t=0;t<N;t++){
  if(t>=W){
   const split=splitOf(t),actual=Math.max(...rows[t].numbers),baseRank=41-actual,b=baseline[split];
   b.n++;b.h5+=baseRank<=5?1:0;b.h10+=baseRank<=10?1:0;b.h20+=baseRank<=20?1:0;b.rank+=baseRank;b.brier+=p0brier-2*p0[actual]+1;b.logloss+=-Math.log(p0[actual]);
   for(const c of configs){
    const cc=counts[c.id],sum=cc.reduce((a,b)=>a+b,0),q=Array(41).fill(0);for(let n=5;n<=40;n++)q[n]=(cc[n]+c.alpha*p0[n])/(sum+c.alpha);
    const order=Array.from({length:36},(_,i)=>i+5).sort((a,b)=>q[b]-q[a]||a-b),rank=Array(41).fill(41);order.forEach((n,i)=>rank[n]=i+1);
    const r=rank[actual],hit5=r<=5?1:0,brier=q.reduce((s,p,n)=>s+p*p,0)-2*q[actual]+1,logloss=-Math.log(q[actual]),m=metrics[c.id][split];
    m.n++;m.h5+=hit5;m.h10+=r<=10?1:0;m.h20+=r<=20?1:0;m.rank+=r;m.brier+=brier;m.logloss+=logloss;
    if(split==="blind_oos"){deltas[c.id].hit5.push(hit5-(baseRank<=5?1:0));deltas[c.id].brier.push(brier-(p0brier-2*p0[actual]+1));deltas[c.id].logloss.push(logloss+Math.log(p0[actual]));}
   }
  }
  for(const c of configs){const cc=counts[c.id];for(let n=5;n<=40;n++)cc[n]*=c.lambda;cc[Math.max(...rows[t].numbers)]+=1;}
 }
 const selected=configs.slice().sort((a,b)=>metrics[a.id].validation.brier/metrics[a.id].validation.n-metrics[b.id].validation.brier/metrics[b.id].validation.n)[0];
 function rngFactory(seed){let x=seed>>>0;return ()=>{x=(Math.imul(x,1664525)+1013904223)>>>0;return x/4294967296;};}
 const B=5000,block=7,rand=rngFactory(20261108);
 function signFlipP(vals,alt){const sums=[];for(let i=0;i<vals.length;i+=block)sums.push(vals.slice(i,i+block).reduce((a,b)=>a+b,0));const observed=sums.reduce((a,b)=>a+b,0);let extreme=0;for(let r=0;r<B;r++){let total=0;for(const z of sums)total+=(rand()<0.5?-z:z);if(alt==="greater"?total>=observed:total<=observed)extreme++;}return (extreme+1)/(B+1);}
 const pHit={},pBrier={},pLogloss={};for(const c of configs){pHit[c.id]=signFlipP(deltas[c.id].hit5,"greater");pBrier[c.id]=signFlipP(deltas[c.id].brier,"less");pLogloss[c.id]=signFlipP(deltas[c.id].logloss,"less");}
 function holm(pobj){const entries=Object.entries(pobj).sort((a,b)=>a[1]-b[1]);let out={},running=0,m=entries.length;entries.forEach(([id,p],i)=>{running=Math.max(running,(m-i)*p);out[id]=Math.min(1,running);});return out;}
 const hHit=holm(pHit),hBrier=holm(pBrier),hLogloss=holm(pLogloss);
 function bootstrapCI(vals,B=2000){const rr=rngFactory(880122),means=[];for(let r=0;r<B;r++){let sum=0,count=0;while(count<vals.length){const start=Math.floor(rr()*Math.max(1,vals.length-block+1));for(let j=0;j<block&&count<vals.length;j++,count++)sum+=vals[start+j];}means.push(sum/vals.length);}means.sort((a,b)=>a-b);return [means[Math.floor(.025*B)],means[Math.floor(.975*B)]];}
 const exactTop5=1-p0.slice(5,36).reduce((a,b)=>a+b,0),exactTop10=1-p0.slice(5,31).reduce((a,b)=>a+b,0),exactTop20=1-p0.slice(5,21).reduce((a,b)=>a+b,0),exactMeanRank=p0.reduce((s,p,n)=>s+p*(n>=5?41-n:0),0);
 const report={experiment_id:"SONAR_FD04_P5_ORDER_STATISTIC_BASELINE_AUDIT",status:"EXPLORATORY_NULL_FOR_PROMOTION",archive:{draws:N,first_date:rows[0].date,last_date:rows.at(-1).date,integrity_validated:true},protocol:{strict_prior:true,minimum_prior_draws:W,splits:[["discovery",200,1700],["validation",1700,2550],["blind_oos",2550,N]],grid_size:configs.length,primary_selection_metric:"validation Brier lower is better",block_permutation:{block_length:7,repetitions:B,seed:20261108,holm_family_size:configs.length},bootstrap:{block_length:7,repetitions:2000,seed:880122}},exact_baseline:{top5_probability:exactTop5,top5_candidates:[36,37,38,39,40],top10_probability:exactTop10,top10_candidates:Array.from({length:10},(_,i)=>i+31),top20_probability:exactTop20,top20_candidates:Array.from({length:20},(_,i)=>i+21),expected_rank:exactMeanRank},split_metrics:{},grid_results:{},multiple_testing:{p_hit5:pHit,holm_hit5:hHit,p_brier_improvement:pBrier,holm_brier:hBrier,p_logloss_improvement:pLogloss,holm_logloss:hLogloss},selected_model:{id:selected.id,h:selected.h,alpha:selected.alpha,metrics:{},blind_paired_delta_ci:{hit5:bootstrapCI(deltas[selected.id].hit5),brier:bootstrapCI(deltas[selected.id].brier),logloss:bootstrapCI(deltas[selected.id].logloss)},blind_paired_permutation_p:{hit5:pHit[selected.id],hit5_holm:hHit[selected.id],brier_improvement:pBrier[selected.id],brier_holm:hBrier[selected.id],logloss_improvement:pLogloss[selected.id],logloss_holm:hLogloss[selected.id]}}};
 for(const s of splits){const b=baseline[s];report.split_metrics[s]={exact_baseline:{targets:b.n,top5_hit_pct:100*b.h5/b.n,top10_hit_pct:100*b.h10/b.n,top20_hit_pct:100*b.h20/b.n,mean_rank:b.rank/b.n,brier:b.brier/b.n,logloss:b.logloss/b.n},models:{}};for(const c of configs){const m=metrics[c.id][s];report.split_metrics[s].models[c.id]={targets:m.n,top5_hit_pct:100*m.h5/m.n,top10_hit_pct:100*m.h10/m.n,top20_hit_pct:100*m.h20/m.n,mean_rank:m.rank/m.n,brier:m.brier/m.n,logloss:m.logloss/m.n};}}
 for(const c of configs){report.grid_results[c.id]={h:c.h,alpha:c.alpha,validation_brier:metrics[c.id].validation.brier/metrics[c.id].validation.n,blind:report.split_metrics.blind_oos.models[c.id],blind_p:{hit5:pHit[c.id],hit5_holm:hHit[c.id],brier_improvement:pBrier[c.id],brier_holm:hBrier[c.id],logloss_improvement:pLogloss[c.id],logloss_holm:hLogloss[c.id]}};}
 for(const s of splits)report.selected_model.metrics[s]=report.split_metrics[s].models[selected.id];
 return report;
}
console.log(JSON.stringify(analyze(csv),null,2));
