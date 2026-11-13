#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const D=path.join(ROOT,"reports","sequence_agent");
const P={
 archive:path.join(ROOT,"data","storico_daily.csv"),
 source:path.join(ROOT,"src","VinciCasaLab.jsx"),
 app:path.join(ROOT,"src","data.json"),
 active:path.join(D,"active_engine_walkforward.json"),
 protocol:path.join(D,"q123_app_ordinal_rank_skill_protocol_2026-11-11.json"),
 report:path.join(D,"q123_app_ordinal_rank_skill_report_2026-11-11.json"),
 ledger:path.join(D,"q123_app_ordinal_rank_skill_target_ledger_2026-11-11.csv"),
 validation:path.join(D,"q123_app_ordinal_rank_skill_validation_2026-11-11.json"),
 freeze:path.join(D,"q123_app_ordinal_rank_skill_prospective_freeze_2026-11-11.json"),
 checkpoint:path.join(D,"q123_app_ordinal_rank_skill_checkpoint_2026-11-11.md"),
 manifest:path.join(D,"q123_app_ordinal_rank_skill_persistence_manifest_2026-11-11.json"),
 runner:path.join(ROOT,"scripts","sonar_q123_app_ordinal_rank_skill.mjs"),
 workflow:path.join(ROOT,".github","workflows","q123-app-ordinal-rank-skill.yml")
};
const EXPECTED={
 archive:"40f317e2d0067e061c46ab799d66f777a0e087c0",
 source:"7ccb9a2abfe452ec535913b70225bc109f692304",
 app:"25c0b2316662664deff9e2157e60ec56cfa3a640",
 active:"822f955801c329585f7dd03df7fc61b0b6a2419c",
 protocolCommit:"f5c8e99a050b830683b454604ff5c3a52e741c02"
};
function fail(m){console.error("Q123 BLOCKED: "+m);process.exit(1);}
function read(p){return fs.readFileSync(p,"utf8");}
function git(a){return execFileSync("git",a,{encoding:"utf8"}).trim();}
function runCore(archiveText, sourceText, appText, activeText, protocolText, protocolCommit, activeBlobSha, freezeAtUtc) {
  const protocol=JSON.parse(protocolText), app=JSON.parse(appText), active=JSON.parse(activeText);
  const fail=(m)=>{throw new Error("Q123 BLOCKED: "+m);};
  const choose=(n,k)=>{if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-i+1)/i;return v;};
  const sum=a=>a.reduce((x,y)=>x+y,0), mean=a=>sum(a)/a.length, rnd=(x,d=12)=>Number(x.toFixed(d));
  function parseArchive(text){
    const lines=text.trimEnd().split(/\r?\n/);
    if(lines[0]!=="data,n1,n2,n3,n4,n5")fail("archive header mismatch");
    const out=[];let prev="";
    for(let i=1;i<lines.length;i++){
      const f=lines[i].split(","),date=f[0],n=f.slice(1).map(Number);
      if(f.length!==6||! /^\d{4}-\d{2}-\d{2}$/.test(date)||new Set(n).size!==5||n.some((x,j)=>!Number.isInteger(x)||x<1||x>40||(j>0&&x<n[j-1]))||(prev&&date<=prev))fail("invalid archive row "+(i+1));
      out.push({d:date,n});prev=date;
    }
    return out;
  }
  function extract(source,name,next){
    const a=source.indexOf("function "+name+"(");
    const b=next?source.indexOf("\nfunction "+next+"(",a+1):source.indexOf("\nconst Card =",a+1);
    if(a<0||b<0)fail("cannot extract exact APP function "+name);
    return source.slice(a,b).trim();
  }
  function makeScorer(source){
    const code=[extract(source,"overlapCount","sonarTransitionProfile"),extract(source,"sonarTransitionProfile","sonarAnalogCore"),extract(source,"sonarAnalogCore",null),"return sonarAnalogCore(draws);"].join("\n");
    try{return new Function("draws",code);}catch(e){fail("APP scorer compile failed: "+e.message);}
  }
  function rng(seed){let x=seed>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};}
  function quantile(sorted,p){return sorted[Math.max(0,Math.min(sorted.length-1,Math.floor(p*(sorted.length-1))))];}
  function bootstrap(values,seed){
    const rand=rng(seed),out=[],n=values.length;
    for(let r=0;r<10000;r++){
      let total=0,count=0;
      while(count<n){
        const start=Math.floor(rand()*n);
        for(let j=0;j<20&&count<n;j++,count++)total+=values[(start+j)%n];
      }
      out.push(total/n);
    }
    out.sort((a,b)=>a-b);
    return [rnd(quantile(out,0.025)),rnd(quantile(out,0.975))];
  }
  function exactTopKTail(K,N,observed){
    const den=choose(40,5),p=Array.from({length:6},(_,k)=>choose(K,k)*choose(40-K,5-k)/den);
    let dist=[1];
    for(let i=0;i<N;i++){
      const next=Array(dist.length+5).fill(0);
      for(let j=0;j<dist.length;j++)if(dist[j]!==0)for(let k=0;k<=5;k++)next[j+k]+=dist[j]*p[k];
      dist=next;
    }
    const mass=sum(dist);let tail=0;for(let j=observed;j<dist.length;j++)tail+=dist[j];
    return {observed,expected:rnd(N*K/8),mass_error:rnd(Math.abs(1-mass),18),p_one_sided_upper:rnd(Math.min(1,tail))};
  }
  function holm(tests){
    const order=tests.map((x,i)=>({i,p:x.p_one_sided_improvement??x.p_one_sided_upper})).sort((a,b)=>a.p-b.p);
    const adjusted=Array(tests.length).fill(1);let running=0,m=tests.length;
    order.forEach((x,rank)=>{running=Math.max(running,Math.min(1,(m-rank)*x.p));adjusted[x.i]=running;});
    return adjusted;
  }
  if(protocol.experiment_id!=="Q123"||protocol.status!=="PREREGISTERED_BEFORE_CALCULATION")fail("protocol state mismatch");
  if(protocol.base_commit!=="ea46a70c4c90db5dad44d5374a97f89a84e50ad9")fail("base commit mismatch");
  if(protocolCommit!=="f5c8e99a050b830683b454604ff5c3a52e741c02")fail("protocol commit mismatch");
  if(activeBlobSha!=="822f955801c329585f7dd03df7fc61b0b6a2419c")fail("active-engine walk-forward blob mismatch");
  const draws=parseArchive(archiveText);
  if(draws.length!==3404||draws[0].d!=="2017-07-17"||draws.at(-1).d!=="2026-11-10")fail("archive count/cutoff mismatch");
  if(app.histN!==draws.length||app.lastDate!==draws.at(-1).d||!Array.isArray(app.modelDraws)||app.modelDraws.length!==draws.length)fail("APP data metadata mismatch");
  for(let i=0;i<draws.length;i++)if(app.modelDraws[i].d!==draws[i].d||app.modelDraws[i].n.join(",")!==draws[i].n.join(","))fail("APP data mismatch at row "+i);
  if(!active.current_frozen_forecast||active.current_frozen_forecast.history_cutoff!=="2026-11-10")fail("active freeze missing/cutoff mismatch");
  const scorer=makeScorer(sourceText),rows=[];
  for(let t=200;t<draws.length;t++){
    const pred=scorer(draws.slice(0,t)),scores=pred.scores;
    if(!Array.isArray(scores)||scores.length!==40)fail("invalid 40-way APP score at target "+t);
    const rank=Array(41).fill(0);
    for(let i=0;i<40;i++){
      const n=scores[i].n;
      if(!Number.isInteger(n)||n<1||n>40||rank[n]!==0||!Number.isFinite(scores[i].score))fail("invalid/duplicate ranked number at target "+t);
      rank[n]=i+1;
    }
    const drawRanks=draws[t].n.map(n=>rank[n]).sort((a,b)=>a-b);
    if(drawRanks.length!==5||drawRanks.some(x=>!x)||new Set(drawRanks).size!==5)fail("invalid target ranks at "+t);
    const rankSum=sum(drawRanks);
    rows.push({target_index:t,target_date:draws[t].d,history_cutoff:draws[t-1].d,draw_ranks:drawRanks,rank_sum:rankSum,mean_rank:rankSum/5,top5_hits:drawRanks.filter(x=>x<=5).length,top10_hits:drawRanks.filter(x=>x<=10).length,top20_hits:drawRanks.filter(x=>x<=20).length});
  }
  if(rows.length!==3204)fail("target count mismatch");
  const n=rows.length,nd=Math.round(n*0.6),nv=Math.round(n*0.2);
  const slices={discovery:rows.slice(0,nd),validation:rows.slice(nd,nd+nv),blind_oos:rows.slice(nd+nv)};
  if(slices.discovery.length!==1922||slices.validation.length!==641||slices.blind_oos.length!==641)fail("split count mismatch");
  function summarize(a){
    const hitRanks=Array(40).fill(0);for(const r of a)for(const rank of r.draw_ranks)hitRanks[rank-1]++;
    const bands=Array.from({length:8},(_,i)=>({ranks:[i*5+1,i*5+5],observed:sum(hitRanks.slice(i*5,i*5+5)),expected:a.length*0.625}));
    return {targets:a.length,first_target:a[0].target_date,last_target:a.at(-1).target_date,mean_rank_sum:rnd(mean(a.map(x=>x.rank_sum))),mean_rank:rnd(mean(a.map(x=>x.mean_rank))),rank_gain_vs_uniform:rnd(20.5-mean(a.map(x=>x.mean_rank))),mean_top5_hits:rnd(mean(a.map(x=>x.top5_hits))),mean_top10_hits:rnd(mean(a.map(x=>x.top10_hits))),mean_top20_hits:rnd(mean(a.map(x=>x.top20_hits))),gains_vs_uniform:{top5:rnd(mean(a.map(x=>x.top5_hits))-0.625),top10:rnd(mean(a.map(x=>x.top10_hits))-1.25),top20:rnd(mean(a.map(x=>x.top20_hits))-2.5)},top20_5of5:a.filter(x=>x.top20_hits===5).length,rank_band_hits:bands};
  }
  const summaries=Object.fromEntries(Object.entries(slices).map(([k,v])=>[k,summarize(v)]));
  const blind=slices.blind_oos,observedRankSum=sum(blind.map(x=>x.rank_sum));
  const rankCounts=Array(191).fill(0);let combos=0;
  for(let a=1;a<=36;a++)for(let b=a+1;b<=37;b++)for(let c=b+1;c<=38;c++)for(let d=c+1;d<=39;d++)for(let e=d+1;e<=40;e++){rankCounts[a+b+c+d+e]++;combos++;}
  if(combos!==658008)fail("rank-sum null enumeration count mismatch");
  const rankMean=rankCounts.reduce((s,c,i)=>s+c*i,0)/combos;
  const rankVar=rankCounts.reduce((s,c,i)=>s+c*(i-rankMean)**2,0)/combos;
  if(Math.abs(rankMean-102.5)>1e-10||Math.abs(rankVar-597.9166666666666)>1e-8)fail("exact rank-sum null moments mismatch");
  const cdf=Array(191).fill(0);let acc=0;for(let i=15;i<=190;i++){acc+=rankCounts[i]/combos;cdf[i]=acc;}
  const rand=rng(0x123123);let extreme=0;
  for(let rep=0;rep<50000;rep++){
    let total=0;
    for(let j=0;j<blind.length;j++){
      const u=rand();let lo=15,hi=190;
      while(lo<hi){const mid=(lo+hi)>>1;if(cdf[mid]>=u)hi=mid;else lo=mid+1;}
      total+=lo;
    }
    if(total<=observedRankSum)extreme++;
  }
  const rankP=(extreme+1)/50001;
  const observedTop5=sum(blind.map(x=>x.top5_hits)),observedTop10=sum(blind.map(x=>x.top10_hits)),observedTop20=sum(blind.map(x=>x.top20_hits));
  const top5=exactTopKTail(5,blind.length,observedTop5),top10=exactTopKTail(10,blind.length,observedTop10),top20=exactTopKTail(20,blind.length,observedTop20);
  const tests=[
    {endpoint:"mean_rank_lower",metric:"mean_rank",baseline:20.5,observed:rnd(observedRankSum/(5*blind.length)),direction:"lower",p_one_sided_improvement:rnd(rankP),replicates:50000,extreme,expected_rank_sum:rnd(rankMean*blind.length),null_sd_of_total:rnd(Math.sqrt(rankVar*blind.length)),bootstrap_ci95:bootstrap(blind.map(x=>x.mean_rank),0x12345)},
    {endpoint:"top5_hits_upper",metric:"mean_top5_hits",baseline:0.625,observed:rnd(observedTop5/blind.length),observed_total:observedTop5,expected_total:top5.expected,direction:"higher",p_one_sided_upper:top5.p_one_sided_upper,mass_error:top5.mass_error,bootstrap_ci95:bootstrap(blind.map(x=>x.top5_hits),0x23456)},
    {endpoint:"top10_hits_upper",metric:"mean_top10_hits",baseline:1.25,observed:rnd(observedTop10/blind.length),observed_total:observedTop10,expected_total:top10.expected,direction:"higher",p_one_sided_upper:top10.p_one_sided_upper,mass_error:top10.mass_error,bootstrap_ci95:bootstrap(blind.map(x=>x.top10_hits),0x34567)},
    {endpoint:"top20_hits_upper",metric:"mean_top20_hits",baseline:2.5,observed:rnd(observedTop20/blind.length),observed_total:observedTop20,expected_total:top20.expected,direction:"higher",p_one_sided_upper:top20.p_one_sided_upper,mass_error:top20.mass_error,bootstrap_ci95:bootstrap(blind.map(x=>x.top20_hits),0x45678)}
  ];
  const adj=holm(tests);tests.forEach((x,i)=>x.p_holm=rnd(adj[i]));
  const maxMassError=Math.max(top5.mass_error,top10.mass_error,top20.mass_error);
  if(maxMassError>1e-9)fail("exact TopK null convolution mass error");
  const current=scorer(draws),ranked=current.scores.map((x,i)=>({rank:i+1,number:x.n,score:rnd(x.score)}));
  const currentTop20=ranked.slice(0,20).map(x=>x.number);
  if(currentTop20.join(",")!==active.current_frozen_forecast.top20_ranked.join(","))fail("current APP Top20 does not reconcile with active freeze");
  const futureIndices=[200,400,777,1200,1600,2000,2400,2800,3200];
  const futureChecks=[];
  for(const t of futureIndices){
    const base=scorer(draws.slice(0,t)).scores.map(x=>x.n);
    const mutated=draws.map((d,i)=>i<t?d:{d:d.d,n:[1,2,3,4,5]});
    const after=scorer(mutated.slice(0,t)).scores.map(x=>x.n);
    const pass=base.join(",")===after.join(",");
    futureChecks.push({target_index:t,target_date:draws[t].d,pass});
    if(!pass)fail("future-suffix mutation failed at "+t);
  }
  const localDate=new Date(Date.parse(freezeAtUtc)+3600000).toISOString().replace("Z","+01:00");
  if(Date.parse(freezeAtUtc)>=Date.parse("2026-11-11T19:00:00Z"))fail("prospective freeze timestamp is not before 20:00 CET draw");
  const freeze={experiment_id:"Q123",target_date:"2026-11-11",frozen_at_utc:freezeAtUtc,frozen_at_local:localDate,history_cutoff:draws.at(-1).d,model:"APP::SONAR_HYBRID_RECENCY_ANALOG_FULL_HISTORY",top40_ranked:ranked,top20_ranked:currentTop20,top10_ranked:ranked.slice(0,10).map(x=>x.number),top5_ranked:ranked.slice(0,5).map(x=>x.number),expected_mean_rank_under_null:20.5,expected_top5_hits_under_null:0.625,expected_top10_hits_under_null:1.25,expected_top20_hits_under_null:2.5,status:"FROZEN_PENDING",research_only:true,not_a_q60_pair:true};
  const ledgerHeader="target_index,target_date,history_cutoff,draw_ranks,rank_sum,mean_rank,top5_hits,top10_hits,top20_hits,top20_5of5";
  const ledger=[ledgerHeader,...rows.map(x=>[x.target_index,x.target_date,x.history_cutoff,x.draw_ranks.join(";"),x.rank_sum,rnd(x.mean_rank,8),x.top5_hits,x.top10_hits,x.top20_hits,x.top20_hits===5?1:0].join(","))].join("\n")+"\n";
  const decision=(tests[0].p_holm<0.05&&tests.slice(1).some(x=>x.p_holm<0.05&&x.observed>x.baseline))?"ORDINAL_RANK_SKILL_SUPPORTED_EXPLORATORILY":"NO_APP_ORDINAL_RANK_SKILL_DEMONSTRATED";
  const report={schema_version:"1.0",experiment_id:"Q123",title:"APP SONAR full-ranking ordinal skill",status:"COMPLETED_EXPLORATORY_NO_PROMOTION",decision,source:{repository:"jamesnuvola/vincicasa-lab",base_commit:protocol.base_commit,archive_blob_sha:protocol.source.archive_git_blob_sha1,scorer_blob_sha:protocol.source.scorer_git_blob_sha1,app_data_blob_sha:protocol.source.app_data_git_blob_sha1,active_walkforward_blob_sha:activeBlobSha,draws:draws.length,first_date:draws[0].d,last_date:draws.at(-1).d},preregistration:{path:"reports/sequence_agent/q123_app_ordinal_rank_skill_protocol_2026-11-11.json",commit:protocolCommit,committed_before_calculation:true},hypothesis:protocol.hypothesis,method:{rank_sum:"Sum of one-based APP ranks of the five target numbers; lower is better.",null:"Uniform 5-subset of ranks 1..40 conditional on each prior-only ranking.",baseline:{mean_rank:20.5,rank_sum_per_target:102.5,top5_hits:0.625,top10_hits:1.25,top20_hits:2.5},rank_sum_null:{enumerated_subsets:combos,mean_per_target:rnd(rankMean),variance_per_target:rnd(rankVar)},topk_null:"Exact Hypergeometric(40,K,5) convolved across Blind OOS targets.",update_order:"No fitted state; score each target from its strict prior prefix.",tie_break:"Exact APP scorer: score descending, then smaller number."},walk_forward:{warmup:200,targets:rows.length,first_target:rows[0].target_date,last_target:rows.at(-1).target_date,strict_prior:true,splits:summaries,split_rule:"Chronological 60/20/remainder; first two sizes rounded."},blind_inference:{family_size:4,adjustment:"Holm",primary_endpoint:"mean_rank_lower",randomization:{method:"Conditional Monte Carlo over exact 5-of-40 rank subsets; aggregate rank-sum lower tail.",replicates:50000,seed:"0x123123",p_one_sided_improvement:rnd(rankP),extreme,observed_rank_sum:observedRankSum,expected_rank_sum:rnd(rankMean*blind.length),null_sd_of_total:rnd(Math.sqrt(rankVar*blind.length))},tests},prospective_freeze:{target_date:freeze.target_date,history_cutoff:freeze.history_cutoff,frozen_at_utc:freeze.frozen_at_utc,top20_ranked:freeze.top20_ranked,top5_ranked:freeze.top5_ranked,status:freeze.status},leakage_checks:{strict_prior:true,future_suffix_mutations:futureChecks,app_archive_row_reconciliation:true,active_top20_reconciled:true},limitations:["Historical Blind OOS is not a virgin holdout after prior SONAR exploration.","The experiment tests ordinal rank information, not direct probability calibration or exact-quintet prediction.","The conditional randomization null assumes each official draw is an independent uniform 5-of-40 draw.","Holm correction covers the four Q123 endpoints only, not the full Q00-Q123 research family.","No prospective outcome for 2026-11-11 is available at freeze time."],next_action:"After official publication of contest 315, score the immutable Q123 full-ranking freeze; continue append-only Q60 paired collection."};
  const checks=[
    ["archive_rows_3404",draws.length===3404],["archive_cutoff_2026_11_10",draws.at(-1).d==="2026-11-10"],["dates_unique_and_ordered",new Set(draws.map(x=>x.d)).size===draws.length],["draws_valid",draws.every(x=>x.n.length===5&&new Set(x.n).size===5&&x.n.every(v=>v>=1&&v<=40))],["pinned_protocol_commit",protocolCommit==="f5c8e99a050b830683b454604ff5c3a52e741c02"],["active_walkforward_blob_pinned",activeBlobSha==="822f955801c329585f7dd03df7fc61b0b6a2419c"],["app_matches_archive",app.modelDraws.length===draws.length],["exact_app_scorer",true],["target_count_3204",rows.length===3204],["split_1922_641_641",slices.discovery.length===1922&&slices.validation.length===641&&slices.blind_oos.length===641],["strict_prior_cutoffs",rows.every(x=>x.history_cutoff<x.target_date)],["40_unique_ranks_per_target",true],["rank_sum_null_658008_subsets",combos===658008],["rank_sum_null_moments",Math.abs(rankMean-102.5)<1e-10&&Math.abs(rankVar-597.9166666666666)<1e-8],["future_suffix_9_of_9",futureChecks.every(x=>x.pass)],["active_top20_reconciled",currentTop20.join(",")===active.current_frozen_forecast.top20_ranked.join(",")],["topk_exact_null_mass",maxMassError<1e-9],["holm_four_endpoints",tests.length===4&&tests.every(x=>x.p_holm+1e-12>=(x.p_one_sided_improvement??x.p_one_sided_upper))],["topk_test_observed_means",Math.abs(tests[1].observed-observedTop5/blind.length)<1e-12&&Math.abs(tests[2].observed-observedTop10/blind.length)<1e-12&&Math.abs(tests[3].observed-observedTop20/blind.length)<1e-12],["freeze_before_20_cet",Date.parse(freezeAtUtc)<Date.parse("2026-11-11T19:00:00Z")]
  ];
  if(checks.some(x=>!x[1]))fail("validation check failed: "+checks.filter(x=>!x[1]).map(x=>x[0]).join(","));
  const validation={experiment_id:"Q123",status:"PASS",checks:checks.map(x=>({id:x[0],passed:x[1]})),checks_passed:checks.filter(x=>x[1]).length,checks_total:checks.length,target_count:rows.length,split_counts:{discovery:nd,validation:nv,blind_oos:rows.length-nd-nv},future_suffix_checks:futureChecks,rank_sum_null_subsets:combos,rank_sum_null_mean:rnd(rankMean),rank_sum_null_variance:rnd(rankVar),max_topk_null_mass_error:rnd(maxMassError,15),active_engine_top20_match:true,protocol_commit:protocolCommit,replay_mode:"CI recomputes and byte-compares all persisted artifacts."};
  const checkpoint=[
    "# Q123 checkpoint — APP full-ranking ordinal skill","",
    "- Preregistration commit: "+protocolCommit+".",
    "- Canonical archive: "+draws.length+" draws through "+draws.at(-1).d+"; blob "+protocol.source.archive_git_blob_sha1+".",
    "- Exact APP scorer and APP data blobs pinned; APP modelDraws reconciles row-by-row.",
    "- 3,204 strict-prior targets; Discovery/Validation/Blind OOS = 1,922/641/641.",
    "- Primary Blind OOS mean rank: "+summaries.blind_oos.mean_rank+" vs null 20.5; p="+rnd(rankP)+"; Holm="+tests[0].p_holm+".",
    "- Decision: "+decision+".",
    "- Q60 unchanged; no historical freeze reconstructed.",
    "- PRs #6, #7, #8 untouched; no merge or production promotion.","",
    "## Blind OOS metrics","","| Metric | Observed | Uniform null |","|---|---:|---:|",
    "| Mean drawn rank | "+summaries.blind_oos.mean_rank+" | 20.5 |",
    "| Top5 mean hits | "+summaries.blind_oos.mean_top5_hits+" | 0.625 |",
    "| Top10 mean hits | "+summaries.blind_oos.mean_top10_hits+" | 1.25 |",
    "| Top20 mean hits | "+summaries.blind_oos.mean_top20_hits+" | 2.5 |","",
    "## Next action","","Verify contest 315 after official publication; score Q123 freeze without retuning and continue Q60 append-only paired collection."
  ].join("\n")+"\n";
  return {report,reportText:JSON.stringify(report,null,2)+"\n",ledger,validation,validationText:JSON.stringify(validation,null,2)+"\n",freeze,freezeText:JSON.stringify(freeze,null,2)+"\n",checkpoint,rows,summaries,tests,decision,checks};
}
function manifestText(createdAt){
 const files=[P.protocol,P.report,P.ledger,P.validation,P.freeze,P.checkpoint,P.runner,P.workflow];
 const entries=files.map(p=>({path:path.relative(ROOT,p).replaceAll("\\","/"),git_blob_sha1:git(["hash-object",p]),bytes:Buffer.byteLength(read(p),"utf8")}));
 return JSON.stringify({experiment_id:"Q123",created_at_utc:createdAt,verification:"Git blob SHA-1 and UTF-8 byte lengths read from the worktree; manifest excludes itself.",files:entries},null,2)+"\n";
}
function main(){
 const check=process.argv.includes("--check");
 const archiveHash=git(["hash-object",P.archive]),sourceHash=git(["hash-object",P.source]),appHash=git(["hash-object",P.app]),activeHash=git(["hash-object",P.active]);
 if(archiveHash!==EXPECTED.archive||sourceHash!==EXPECTED.source||appHash!==EXPECTED.app||activeHash!==EXPECTED.active)fail("pinned source blob mismatch");
 if(git(["log","-1","--format=%H","--",P.protocol])!==EXPECTED.protocolCommit)fail("protocol commit mismatch");
 const existingFreeze=fs.existsSync(P.freeze)?JSON.parse(read(P.freeze)):null;
 const freezeAt=existingFreeze?.frozen_at_utc??new Date().toISOString();
 const out=runCore(read(P.archive),read(P.source),read(P.app),read(P.active),read(P.protocol),EXPECTED.protocolCommit,activeHash,freezeAt);
 const expectedFiles=[[P.report,out.reportText],[P.ledger,out.ledger],[P.validation,out.validationText],[P.freeze,out.freezeText],[P.checkpoint,out.checkpoint]];
 if(check){
  for(const [p,expected] of expectedFiles){
    const actual=read(p);
    if(actual!==expected){
      let at=0;while(at<actual.length&&at<expected.length&&actual[at]===expected[at])at++;
      fail("byte mismatch: "+path.relative(ROOT,p)+" at char "+at+"; actual="+JSON.stringify(actual.slice(Math.max(0,at-80),at+180))+"; expected="+JSON.stringify(expected.slice(Math.max(0,at-80),at+180)));
    }
  }
  const existingManifest=JSON.parse(read(P.manifest));
  const expectedManifest=manifestText(existingManifest.created_at_utc);
  if(read(P.manifest)!==expectedManifest)fail("manifest mismatch");
  console.log("Q123 CHECK PASS: "+out.rows.length+" targets; "+out.checks.filter(x=>x[1]).length+"/"+out.checks.length+" checks; report/ledger/validation/freeze/checkpoint byte-identical; manifest verified.");
 } else {
  for(const [p,content] of expectedFiles)fs.writeFileSync(p,content);
  const manifest=manifestText(new Date().toISOString());
  fs.writeFileSync(P.manifest,manifest);
  console.log("Q123 artifacts generated: "+out.rows.length+" targets; "+out.checks.filter(x=>x[1]).length+"/"+out.checks.length+" checks.");
 }
}
main();
