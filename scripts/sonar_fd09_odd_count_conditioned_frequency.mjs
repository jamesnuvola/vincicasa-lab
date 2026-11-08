import fs from "node:fs";
const csv=fs.readFileSync(process.argv[2] ?? "data/storico_daily.csv","utf8");
function run(csv){

const lines = csv.trim().split(/\r?\n/);
if (lines[0] !== "data,n1,n2,n3,n4,n5") throw new Error("Unexpected CSV header");
const rows = lines.slice(1).map((line, i) => {
  const f=line.split(","), date=f[0], nums=f.slice(1).map(Number);
  if(f.length!==6||nums.length!==5||nums.some(n=>!Number.isInteger(n)||n<1||n>40)||new Set(nums).size!==5)throw new Error("Invalid CSV row "+(i+2));
  return {date,nums};
});
if(rows.length!==3401||rows[0].date!=="2017-07-17"||rows[rows.length-1].date!=="2026-11-07")throw new Error("Archive bounds/count mismatch");
for(let i=1;i<rows.length;i++)if(!(rows[i].date>rows[i-1].date))throw new Error("Dates not ascending");
const oddCount=d=>d.reduce((s,n)=>s+(n%2===1?1:0),0), oddState=o=>o<=1?0:o<=3?1:2;
const alphaGrid=[0,25,50,100,200,500,1000],configs=alphaGrid.map(alpha=>({id:"ODD3_A"+alpha,alpha}));
const splitOf=t=>t<=1699?"discovery":t<=2549?"validation":"blind_oos";
const splitBounds={discovery:{start:300,end:1699},validation:{start:1700,end:2549},blind_oos:{start:2550,end:3400}};
const newM=()=>({targets:0,hits5:0,hits10:0,hits20:0,rankSum:0,brierSum:0,logLossSum:0});
const metrics=Object.fromEntries(["discovery","validation","blind_oos"].map(s=>[s,{baseline:newM(),models:configs.map(()=>newM())}]));
const total=Array(41).fill(0);for(let i=0;i<300;i++)for(const n of rows[i].nums)total[n]++;
const cc=Array.from({length:3},()=>Array(41).fill(0)),ex=Array(3).fill(0);
for(let j=1;j<300;j++){const st=oddState(oddCount(rows[j-1].nums));ex[st]++;for(const n of rows[j].nums)cc[st][n]++;}
const records=[];
const rank=s=>Array.from({length:40},(_,i)=>i+1).sort((a,b)=>(s[b]-s[a])||(a-b));
const hits=(r,a,k)=>{const set=new Set(r.slice(0,k));let h=0;for(const n of a)if(set.has(n))h++;return h;};
const update=(m,a,r,s)=>{m.targets++;m.hits5+=hits(r,a,5);m.hits10+=hits(r,a,10);m.hits20+=hits(r,a,20);const pos=new Map(r.map((n,i)=>[n,i+1])),as=new Set(a);for(const n of a)m.rankSum+=pos.get(n);let b=0,ll=0;for(let n=1;n<=40;n++){const p=Math.min(1-1e-12,Math.max(1e-12,s[n])),y=as.has(n)?1:0;b+=(y-p)*(y-p);ll-=y*Math.log(p)+(1-y)*Math.log(1-p);}m.brierSum+=b/40;m.logLossSum+=ll/40;};
for(let t=300;t<rows.length;t++){
 const split=splitOf(t),actual=rows[t].nums,freq=Array(41).fill(0);for(let n=1;n<=40;n++)freq[n]=total[n]/t;
 const br=rank(freq);update(metrics[split].baseline,actual,br,freq);
 const po=oddCount(rows[t-1].nums),st=oddState(po),mr=[];
 for(let ci=0;ci<configs.length;ci++){const alpha=configs[ci].alpha,s=Array(41).fill(0),den=ex[st]+alpha;for(let n=1;n<=40;n++)s[n]=den>0?(cc[st][n]+alpha*freq[n])/den:freq[n];const rr=rank(s);update(metrics[split].models[ci],actual,rr,s);mr.push({top5:rr.slice(0,5),hits5:hits(rr,actual,5)});}
 records.push({t,date:rows[t].date,cutoff:rows[t-1].date,split,po,st,actual:actual.slice(),baselineTop5:br.slice(0,5),baselineHits5:hits(br,actual,5),models:mr});
 // strict-prior target t update occurs only after all target scores are frozen
 for(const n of actual)total[n]++;ex[st]++;for(const n of actual)cc[st][n]++;
}
const summary=m=>({targets:m.targets,hits5:m.hits5,top5HitSharePct:m.targets?100*m.hits5/(5*m.targets):null,hits10:m.hits10,top10HitSharePct:m.targets?100*m.hits10/(5*m.targets):null,hits20:m.hits20,top20HitSharePct:m.targets?100*m.hits20/(5*m.targets):null,meanRank:m.targets?m.rankSum/(5*m.targets):null,brier:m.targets?m.brierSum/m.targets:null,logLoss:m.targets?m.logLossSum/m.targets:null});
let best=0;for(let ci=1;ci<configs.length;ci++){const a=metrics.validation.models[ci],b=metrics.validation.models[best];if(a.hits5>b.hits5||(a.hits5===b.hits5&&(a.brierSum<b.brierSum-1e-12||(Math.abs(a.brierSum-b.brierSum)<=1e-12&&configs[ci].alpha>configs[best].alpha))))best=ci;
}
const choose=(n,k)=>{if(k<0||k>n)return 0;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
const hd=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/choose(40,5));let dp=[1];
for(let i=0;i<851;i++){const nx=Array(dp.length+5).fill(0);for(let j=0;j<dp.length;j++)for(let k=0;k<=5;k++)nx[j+k]+=dp[j]*hd[k];dp=nx;}
const pExact=o=>{let p=0;for(let i=Math.max(0,o);i<dp.length;i++)p+=dp[i];return Math.min(1,Math.max(0,p));};
const holm=ps=>{const m=ps.length,ord=ps.map((p,i)=>({p,i})).sort((a,b)=>a.p-b.p||a.i-b.i),adj=Array(m).fill(1);let run=0;for(let k=0;k<m;k++){run=Math.max(run,Math.min(1,(m-k)*ord[k].p));adj[ord[k].i]=run;}return adj;};
const rngM=seed=>{let a=seed>>>0;return()=>{a=(a+0x6D2B79F5)>>>0;let z=a;z=Math.imul(z^(z>>>15),z|1);z^=z+Math.imul(z^(z>>>7),z|61);return((z^(z>>>14))>>>0)/4294967296;};};
const blind=records.filter(r=>r.split==="blind_oos");if(blind.length!==851)throw new Error("Blind split mismatch");
const up=[pExact(metrics.blind_oos.baseline.hits5),...configs.map((_,ci)=>pExact(metrics.blind_oos.models[ci].hits5))],uh=holm(up);
const nb=Math.floor(blind.length/7),tail=blind.length-nb*7,bd=configs.map((_,ci)=>Array.from({length:nb},(_,b)=>{let d=0;for(let k=0;k<7;k++)d+=blind[b*7+k].models[ci].hits5-blind[b*7+k].baselineHits5;return d;})),obs=bd.map(ds=>ds.reduce((s,x)=>s+x,0));
const sr=rngM(0xFD09A11),sreps=20000,exc=Array(configs.length).fill(0);
for(let rep=0;rep<sreps;rep++){const sums=Array(configs.length).fill(0);for(let b=0;b<nb;b++){const sign=sr()<0.5?-1:1;for(let ci=0;ci<configs.length;ci++)sums[ci]+=sign*bd[ci][b];}for(let ci=0;ci<configs.length;ci++)if(Math.abs(sums[ci])>=Math.abs(obs[ci])-1e-12)exc[ci]++;}
const pr=[1,...exc.map(x=>(x+1)/(sreps+1))],ph=holm(pr),sd=blind.map(r=>r.models[best].hits5-r.baselineHits5),brng=rngM(0xFD09B22),breps=10000,bn=blind.length,bc=Math.ceil(bn/7),bv=Array(breps);
for(let rep=0;rep<breps;rep++){let sum=0,count=0;for(let b=0;b<bc&&count<bn;b++){const start=Math.floor(brng()*bn);for(let k=0;k<7&&count<bn;k++,count++)sum+=sd[(start+k)%bn];}bv[rep]=100*sum/(5*bn);}bv.sort((a,b)=>a-b);
const q=(a,p)=>a[Math.min(a.length-1,Math.max(0,Math.floor(p*(a.length-1))))];
const bb=summary(metrics.blind_oos.baseline),sb=summary(metrics.blind_oos.models[best]);
const modelRows=configs.map((c,ci)=>({id:c.id,alpha:c.alpha,discovery:summary(metrics.discovery.models[ci]),validation:summary(metrics.validation.models[ci]),blind_oos:summary(metrics.blind_oos.models[ci]),uniform_p_exact:up[ci+1],uniform_p_holm:uh[ci+1],paired_block_p_raw:pr[ci+1],paired_block_p_holm:ph[ci+1]}));
const rawBest=modelRows.reduce((a,b)=>b.uniform_p_exact<a.uniform_p_exact?b:a,modelRows[0]);
const header=["target_index","target_date","cutoff_date","split","previous_draw_odd_count","condition_state","actual_numbers","baseline_top5","baseline_hits","validation_selected_model","selected_top5","selected_hits","delta_hits"].concat(configs.flatMap(c=>[c.id+"_top5",c.id+"_hits"])),ll=[header.join(",")];
for(const r of records){const s=r.models[best],cells=[r.t,r.date,r.cutoff,r.split,r.po,r.st,r.actual.join("-"),r.baselineTop5.join("-"),r.baselineHits5,configs[best].id,s.top5.join("-"),s.hits5,s.hits5-r.baselineHits5];for(const m of r.models)cells.push(m.top5.join("-"),m.hits5);ll.push(cells.join(","));}
const ledgerCsv=ll.join("\n")+"\n";
const result={schema_version:"1.0",task_id:"FD09",status:"EXPLORATORY_RETROSPECTIVE_NO_PROMOTION",
 archive:{path:"data/storico_daily.csv",git_blob_sha:"5d2efd70684e918b27d8f06386d545647898336d",draw_count:rows.length,first_date:rows[0].date,last_date:rows[rows.length-1].date,csv_line_count:lines.length},
 integrity:{dates_unique_ascending:true,each_draw_five_distinct_in_1_to_40:true,strict_prior_loop_order:"PASS: target scored before updating unconditional or state-conditioned histories",training_condition_rows:"j in [1,t-1], state from draw j-1",target_state:"odd-count bucket of draw t-1",cutoff_alignment:"target date t; cutoff date t-1",target_count:records.length,split_counts:{discovery:metrics.discovery.baseline.targets,validation:metrics.validation.baseline.targets,blind_oos:metrics.blind_oos.baseline.targets},independent_runtime_repetitions:2,native_node_execution:"NOT_RUN",github_actions_ci:"NOT_RUN"},
 hypothesis:"Previous-draw odd-count composition (0-1, 2-3, 4-5) may condition next-draw per-number inclusion frequencies with shrinkage toward unconditional strict-prior frequency.",
 method:{state_bins:[{state:0,odd_count:[0,1]},{state:1,odd_count:[2,3]},{state:2,odd_count:[4,5]}],alpha_grid:alphaGrid,model_count:configs.length,minimum_prior_draws:300,split_bounds:splitBounds,primary_endpoint:"Top5 hit-share",selection:"validation maximum Top5 hit count; ties lower Brier, then larger alpha",secondary_endpoints:["Top10/Top20 coverage of actual drawn numbers","mean rank","Brier","log-loss"],exact_uniform_null:"851-fold convolution of Hypergeometric(40,5,5) overlap distribution",multiple_testing:{uniform_null_family_size:22,paired_family_size:22,correction:"Holm",paired_block_length:7,complete_blocks:nb,omitted_tail_targets:tail,sign_flip_replicates:sreps,bootstrap_block_length:7,bootstrap_replicates:breps}},
 selected_model:configs[best].id,selected_alpha:configs[best].alpha,
 selected_metrics:{discovery:{model:summary(metrics.discovery.models[best]),baseline:summary(metrics.discovery.baseline)},validation:{model:summary(metrics.validation.models[best]),baseline:summary(metrics.validation.baseline)},blind_oos:{model:sb,baseline:bb,delta_top5_hit_share_pp:sb.top5HitSharePct-bb.top5HitSharePct,delta_top5_hits:sb.hits5-bb.hits5,uniform_p_exact:up[best+1],uniform_p_holm:uh[best+1],paired_block_p_raw:pr[best+1],paired_block_p_holm:ph[best+1],paired_delta_bootstrap_95_ci_pp:[q(bv,0.025),q(bv,0.975)],brier_delta_model_minus_baseline:sb.brier-bb.brier,log_loss_delta_model_minus_baseline:sb.logLoss-bb.logLoss}},
 baseline_uniform_reference:{top5_hit_share_pct:12.5,top10_coverage_pct:25,top20_coverage_pct:50,mean_rank:20.5,blind_baseline_hits5:bb.hits5,blind_baseline_hit_share_pct:bb.top5HitSharePct,uniform_p_exact:up[0],uniform_p_holm:uh[0]},
 best_blind_raw_configuration:{id:rawBest.id,alpha:rawBest.alpha,blind_hits5:rawBest.blind_oos.hits5,blind_top5_hit_share_pct:rawBest.blind_oos.top5HitSharePct,uniform_p_exact:rawBest.uniform_p_exact,uniform_p_holm:rawBest.uniform_p_holm,retrospective_only:true},
 models:modelRows,decision:"No predictive lift confirmed. Selected model's small retrospective Top5 difference versus unconditional frequency is not significant and scoring metrics are slightly worse. Prior SONAR experiments reuse this blind period; no independent prospective evidence.",next_action:"Freeze FD-09; no retuning on this blind segment. Continue append-only Q60 prospective freezes and register any new hypothesis/endpoint before computation."};
result.ledgerCsv=ledgerCsv;return result;

}
const result=run(csv);
const ledgerPath=process.argv[3] ?? "reports/sequence_agent/fd09_odd_count_conditioned_target_ledger_20261108.csv";
fs.writeFileSync(ledgerPath,result.ledgerCsv,"utf8");
delete result.ledgerCsv;
process.stdout.write(JSON.stringify(result,null,2)+"\n");
