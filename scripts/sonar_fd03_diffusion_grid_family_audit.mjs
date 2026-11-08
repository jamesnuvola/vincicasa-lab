#!/usr/bin/env node
import fs from "node:fs";
const csv=fs.readFileSync(new URL("../data/storico_daily.csv",import.meta.url),"utf8");
function analyze(csv) {
  const lines=csv.trim().split(/\r?\n/);
  if(lines[0]!=="data,n1,n2,n3,n4,n5") throw new Error("bad CSV header");
  const rows=lines.slice(1).map(line=>{
    const [date,...nums]=line.split(",");
    return {date,numbers:nums.map(Number)};
  });
  const N=rows.length,WARM=200,M=40,hs=[50,100,200,500],sigmas=[0.5,1,2,4];
  if(N<=2550) throw new Error("insufficient archive for registered split");
  let prev="";
  for(const r of rows){
    if(!(r.date>prev)) throw new Error("dates not strictly ordered");
    if(r.numbers.length!==5||new Set(r.numbers).size!==5||!r.numbers.every(n=>Number.isInteger(n)&&n>=1&&n<=40)) throw new Error("invalid draw "+r.date);
    prev=r.date;
  }
  const splits=[["discovery",200,1700],["validation",1700,2550],["blind_oos",2550,N]];
  const lambdas=hs.map(h=>Math.pow(2,-1/h)),decayed=hs.map(()=>Array(M).fill(0)),kernels={};
  for(const h of hs)for(const s of sigmas){
    const mat=Array.from({length:M},(_,n)=>Array.from({length:M},(_,k)=>Math.exp(-((n-k)**2)/(2*s*s))));
    kernels[`${h}|${s}`]={mat,norms:mat.map(row=>row.reduce((a,b)=>a+b,0))};
  }
  const modelIds=hs.flatMap(h=>sigmas.map(s=>`FD h=${h} sigma=${s}`)),rawIds=hs.map(h=>`RAW h=${h}`);
  const ids=[...modelIds,...rawIds],accum={},blindHits={};
  for(const id of ids){accum[id]=splits.map(()=>({targets:0,h5:0,h10:0,h20:0,rankSum:0,allFiveTop5:0}));blindHits[id]=[];}
  const rankMapOf=scores=>{
    const order=scores.map((v,i)=>[i+1,v]).sort((a,b)=>b[1]-a[1]||a[0]-b[0]);
    const ranks=Array(M);order.forEach((pair,i)=>ranks[pair[0]-1]=i+1);return ranks;
  };
  const record=(id,t,ranks,actual)=>{
    const si=splits.findIndex(([,a,b])=>t>=a&&t<b);if(si<0)return;
    const a=accum[id][si];a.targets++;let drawH5=0;
    for(const n of actual){const rank=ranks[n-1];a.rankSum+=rank;if(rank<=5){a.h5++;drawH5++;}if(rank<=10)a.h10++;if(rank<=20)a.h20++;}
    if(drawH5===5)a.allFiveTop5++;
    if(si===2)blindHits[id].push(drawH5);
  };
  for(let t=0;t<N;t++){
    if(t>=WARM){
      for(let hi=0;hi<hs.length;hi++){
        const h=hs[hi],c=decayed[hi];record(`RAW h=${h}`,t,rankMapOf(c),rows[t].numbers);
        for(const s of sigmas){
          const {mat,norms}=kernels[`${h}|${s}`],scores=Array(M).fill(0);
          for(let n=0;n<M;n++){let v=0;for(let k=0;k<M;k++)v+=mat[n][k]*c[k];scores[n]=v/norms[n];}
          record(`FD h=${h} sigma=${s}`,t,rankMapOf(scores),rows[t].numbers);
        }
      }
    }
    for(let hi=0;hi<hs.length;hi++){
      const c=decayed[hi],lambda=lambdas[hi];for(let k=0;k<M;k++)c[k]*=lambda;
      for(const n of rows[t].numbers)c[n-1]+=1;
    }
  }
  const metrics={};
  for(const id of ids){
    metrics[id]={};
    for(let si=0;si<splits.length;si++){
      const a=accum[id][si],cases=a.targets*5;
      metrics[id][splits[si][0]]={targets:a.targets,top5_hit_pct:+(100*a.h5/cases).toFixed(4),top10_hit_pct:+(100*a.h10/cases).toFixed(4),top20_hit_pct:+(100*a.h20/cases).toFixed(4),mean_rank:+(a.rankSum/cases).toFixed(4),top5_hits:a.h5,all_five_top5:a.allFiveTop5};
    }
  }
  const choose=(n,k)=>{if(k<0||k>n)return 0;let r=1;for(let i=1;i<=k;i++)r=r*(n-i+1)/i;return r;};
  const perDraw=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/choose(40,5));
  const blindCount=N-2550;let dp=[1];
  for(let t=0;t<blindCount;t++){const next=new Array(dp.length+5).fill(0);for(let j=0;j<dp.length;j++)if(dp[j])for(let k=0;k<=5;k++)next[j+k]+=dp[j]*perDraw[k];dp=next;}
  const exactUpperTail=obs=>Math.min(1,dp.slice(obs).reduce((a,b)=>a+b,0));
  const pUniform={};for(const id of modelIds)pUniform[id]=exactUpperTail(metrics[id].blind_oos.top5_hits);
  const holm=ps=>{const entries=Object.entries(ps).sort((a,b)=>a[1]-b[1]);const out={};let running=0,m=entries.length;entries.forEach(([id,p],i)=>{running=Math.max(running,Math.min(1,(m-i)*p));out[id]=running;});return out;};
  const pUniformHolm=holm(pUniform),lcg=seed=>{let state=seed>>>0;return()=>{state=(1664525*state+1013904223)>>>0;return state/4294967296;}};
  const pPairedRaw={},ciPairedRaw={};
  for(let mi=0;mi<modelIds.length;mi++){
    const id=modelIds[mi],h=hs[Math.floor(mi/sigmas.length)],rawId=`RAW h=${h}`,cand=blindHits[id],base=blindHits[rawId],diff=cand.map((v,i)=>v-base[i]),observed=diff.reduce((a,b)=>a+b,0),blockSums=[];
    for(let start=0;start<diff.length;start+=7)blockSums.push(diff.slice(start,start+7).reduce((a,b)=>a+b,0));
    let random=lcg(31000+mi),exceed=0,reps=10000;
    for(let rep=0;rep<reps;rep++){let sum=0;for(const b of blockSums)sum+=(random()<.5?1:-1)*b;if(sum>=observed-1e-12)exceed++;}
    pPairedRaw[id]=(exceed+1)/(reps+1);
    random=lcg(41000+mi);const boot=[],B=2000,n=diff.length;
    for(let rep=0;rep<B;rep++){let sum=0,count=0;while(count<n){const start=Math.floor(random()*n);for(let j=0;j<7&&count<n;j++,count++)sum+=diff[(start+j)%n];}boot.push(sum/n);}
    boot.sort((a,b)=>a-b);ciPairedRaw[id]=[+boot[Math.floor(.025*B)].toFixed(5),+boot[Math.floor(.975*B)].toFixed(5)];
  }
  const pPairedHolm=holm(pPairedRaw),grid=modelIds.map(id=>({
    model:id,discovery:metrics[id].discovery,validation:metrics[id].validation,blind_oos:metrics[id].blind_oos,
    p_uniform_blind_exact:pUniform[id],p_uniform_blind_holm16:pUniformHolm[id],
    paired_vs_same_half_life_raw_p_block7:pPairedRaw[id],paired_vs_same_half_life_raw_p_holm16:pPairedHolm[id],
    paired_vs_raw_moving_block_bootstrap_95_hits_per_target:ciPairedRaw[id]
  }));
  const selected="FD h=200 sigma=4",sel=metrics[selected],raw=metrics["RAW h=200"];
  return {
    experiment_id:"SONAR_FD03_DIFFUSION_GRID_FAMILY_AUDIT",
    status:"EXPLORATORY_NOT_PROMOTABLE",
    archive:{draws:N,first_date:rows[0].date,last_date:rows[N-1].date,validated:true},
    protocol:{minimum_prior_draws:200,splits,half_lives:hs,sigmas,grid_size:16,selected_by_validation_top5:"h=200 sigma=4 (frozen by FD-01 report)",blind_oos_targets:blindCount,ranking_tie_break:"ascending number",uniform_null:"independent uniform 5-subsets per target; exact hypergeometric-overlap convolution"},
    uniform_baseline:{top5_pct:12.5,top10_pct:25,top20_pct:50,mean_rank:20.5,expected_blind_top5_hits:blindCount*0.625},
    selected:{model:selected,metrics:sel,p_uniform_blind_exact:pUniform[selected],p_uniform_blind_holm16:pUniformHolm[selected],
      paired_vs_raw_same_half_life:{raw_model:"RAW h=200",extra_top5_hits:sel.blind_oos.top5_hits-raw.blind_oos.top5_hits,
        delta_top5_percentage_points:+(sel.blind_oos.top5_hit_pct-raw.blind_oos.top5_hit_pct).toFixed(4),
        p_block7_one_sided:pPairedRaw[selected],p_holm16:pPairedHolm[selected],
        moving_block_bootstrap_95_hits_per_target:ciPairedRaw[selected]}},
    raw_metrics:Object.fromEntries(rawIds.map(id=>[id,metrics[id]])),grid
  };
}
const result=analyze(csv);
console.log(JSON.stringify(result,null,2));
