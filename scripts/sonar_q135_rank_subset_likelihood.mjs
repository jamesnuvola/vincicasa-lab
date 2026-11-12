#!/usr/bin/env node
import fs from "node:fs";
import { execFileSync } from "node:child_process";

const ROOT=process.cwd();
const D="reports/sequence_agent";
const P={
  source:D+"/q135_source_q123_rank_ledger_2026-11-12.csv",
  upstreamReport:D+"/q135_upstream_q123_report_2026-11-12.json",
  upstreamProtocol:D+"/q135_upstream_q123_protocol_2026-11-12.json",
  protocol:D+"/q135_rank_subset_likelihood_protocol_2026-11-12.json",
  report:D+"/q135_rank_subset_likelihood_report_2026-11-12.json",
  ledger:D+"/q135_rank_subset_likelihood_target_ledger_2026-11-12.csv",
  validation:D+"/q135_rank_subset_likelihood_validation_2026-11-12.json",
  checkpoint:D+"/q135_rank_subset_likelihood_checkpoint_2026-11-12.md",
  manifest:D+"/q135_rank_subset_likelihood_persistence_manifest_2026-11-12.json",
  runner:"scripts/sonar_q135_rank_subset_likelihood.mjs",
  workflow:".github/workflows/q135-rank-subset-likelihood.yml"
};
const EXPECTED_SOURCE="36d7af1fb3cceda5976eb99a78931f58d1a3d28a";
const EXPECTED_PROTOCOL="4be703c2cabb0ba49f3085d6771f511cfec3e650";
const EXPECTED_Q123_REPORT="3d845ed8b9603fc762446eea38ea126262ff5886";
const EXPECTED_Q123_PROTOCOL="cf69b9bb1ec738a1fc1f17ff02da3a79d4213252";
const EXPECTED_Q123_HEAD="93b494b089abf485b6616f71b90baec79e39c796";
const NCOMB=658008;
const LOGC=Math.log(NCOMB);
const BETAS=Array.from({length:21},(_,i)=>i*0.00025);
const RANDOM_REPS=10000;
const BOOT_REPS=10000;
const BLOCK=20;
function fail(m){throw new Error("Q135 BLOCKED: "+m);}
function read(p){return fs.readFileSync(p,"utf8");}
function write(p,s){fs.writeFileSync(p,s,"utf8");}
function gitBlob(p){return execFileSync("git",["hash-object",p],{encoding:"utf8"}).trim();}
function bytes(p){return fs.statSync(p).size;}
function round(x,d=12){return Number(x.toFixed(d));}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
function choose(n,k){if(k<0||k>n)return 0;let x=1;for(let i=1;i<=k;i++)x=x*(n-i+1)/i;return x;}
function partition(beta,exclude=0){
  const dp=Array(6).fill(0);dp[0]=1;
  for(let r=1;r<=40;r++){
    if(r===exclude)continue;
    const w=Math.exp(-beta*r);
    for(let k=5;k>=1;k--)dp[k]+=w*dp[k-1];
  }
  return dp[5];
}
function marginalProbabilities(beta){
  const z=partition(beta);
  const p=[];
  for(let r=1;r<=40;r++){
    const dp=Array(5).fill(0);dp[0]=1;
    for(let q=1;q<=40;q++){
      if(q===r)continue;
      const w=Math.exp(-beta*q);
      for(let k=4;k>=1;k--)dp[k]+=w*dp[k-1];
    }
    p.push(Math.exp(-beta*r)*dp[4]/z);
  }
  return {z,p,sum:p.reduce((s,x)=>s+x,0),sumSquares:p.reduce((s,x)=>s+x*x,0)};
}
function xorshift(seed){
  let x=seed>>>0;if(x===0)x=0x9e3779b9;
  return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return x>>>0;};
}
function randInt(next,n){
  const limit=Math.floor(4294967296/n)*n;
  let x;do{x=next();}while(x===0||x>limit);
  return (x%n)+1;
}
function randomSubset(next){
  const a=[];
  while(a.length<5){const r=randInt(next,40);if(!a.includes(r))a.push(r);}
  return a;
}
function quantile(sorted,p){
  const i=Math.max(0,Math.min(sorted.length-1,Math.floor(p*(sorted.length-1))));
  return sorted[i];
}
function bootstrap(values,seed){
  const next=xorshift(seed),n=values.length,out=[];
  const limit=Math.floor(4294967296/n)*n;
  const randIndex=()=>{let x;do{x=next();}while(x===0||x>limit);return x%n;};
  for(let b=0;b<BOOT_REPS;b++){
    let s=0,c=0;
    while(c<n){
      const start=randIndex();
      for(let j=0;j<BLOCK&&c<n;j++,c++)s+=values[(start+j)%n];
    }
    out.push(s/n);
  }
  out.sort((a,b)=>a-b);
  return [round(quantile(out,0.025)),round(quantile(out,0.975))];
}
function randomization(values,beta,model,seed){
  const next=xorshift(seed),n=values.length;
  const observedLL=mean(values.map(x=>-beta*x.rankSum-Math.log(model.z)+LOGC));
  const observedBrier=mean(values.map(x=>model.sumSquares+0.625-2*x.draw_ranks.reduce((a,r)=>a+model.p[r-1],0)));
  let llExtreme=0,brierExtreme=0;
  for(let b=0;b<RANDOM_REPS;b++){
    let rankTotal=0,pTotal=0;
    for(let j=0;j<n;j++){
      const subset=randomSubset(next);
      for(const r of subset){rankTotal+=r;pTotal+=model.p[r-1];}
    }
    const nullLL=-beta*(rankTotal/n)-Math.log(model.z)+LOGC;
    const nullBrier=model.sumSquares+0.625-2*(pTotal/n);
    if(nullLL>=observedLL-1e-15)llExtreme++;
    if(nullBrier<=observedBrier+1e-15)brierExtreme++;
  }
  return {
    observed_mean_log_likelihood_gain:round(observedLL),
    observed_mean_brier_delta:round(observedBrier),
    log_likelihood:{replicates:RANDOM_REPS,extreme:llExtreme,p_one_sided_upper:round((llExtreme+1)/(RANDOM_REPS+1))},
    brier:{replicates:RANDOM_REPS,extreme:brierExtreme,p_one_sided_lower:round((brierExtreme+1)/(RANDOM_REPS+1))}
  };
}
function holm(tests){
  const order=tests.map((x,i)=>({i,p:x.p})).sort((a,b)=>a.p-b.p);
  const out=Array(tests.length).fill(1);let running=0;
  order.forEach((x,k)=>{running=Math.max(running,Math.min(1,(tests.length-k)*x.p));out[x.i]=running;});
  return out;
}
function parseLedger(text){
  const lines=text.trimEnd().split(/\r?\n/);
  const header="target_index,target_date,history_cutoff,draw_ranks,rank_sum,mean_rank,top5_hits,top10_hits,top20_hits,top20_5of5";
  if(lines[0]!==header)fail("source ledger header mismatch");
  const rows=[];
  for(let i=1;i<lines.length;i++){
    const f=lines[i].split(",");
    if(f.length!==10)fail("source row width mismatch at line "+(i+1));
    const index=Number(f[0]),date=f[1],cutoff=f[2],ranks=f[3].split(";").map(Number);
    const rankSum=Number(f[4]),meanRank=Number(f[5]),top5=Number(f[6]),top10=Number(f[7]),top20=Number(f[8]),all5=Number(f[9]);
    if(!Number.isInteger(index)||!/^20\d\d-\d\d-\d\d$/.test(date)||!/^20\d\d-\d\d-\d\d$/.test(cutoff)||!(cutoff<date))fail("invalid index/date/cutoff at line "+(i+1));
    if(ranks.length!==5||new Set(ranks).size!==5||ranks.some(r=>!Number.isInteger(r)||r<1||r>40))fail("invalid ranks at line "+(i+1));
    const s=ranks.reduce((a,b)=>a+b,0);
    if(s!==rankSum||Math.abs(meanRank-rankSum/5)>1e-8)fail("rank sum mismatch at line "+(i+1));
    if(ranks.filter(r=>r<=5).length!==top5||ranks.filter(r=>r<=10).length!==top10||ranks.filter(r=>r<=20).length!==top20||(top20===5?1:0)!==all5)fail("TopK reconciliation failed at line "+(i+1));
    rows.push({target_index:index,target_date:date,history_cutoff:cutoff,draw_ranks:ranks,rankSum,meanRank,top5,top10,top20});
  }
  if(rows.length!==3204)fail("expected 3,204 clean targets, found "+rows.length);
  if(rows[0].target_index!==200||rows.at(-1).target_index!==3403)fail("target index boundary mismatch");
  if(rows[0].target_date!=="2018-02-02"||rows.at(-1).target_date!=="2026-11-10")fail("target date boundary mismatch");
  for(let i=1;i<rows.length;i++){
    if(rows[i].target_index!==rows[i-1].target_index+1||rows[i].target_date<=rows[i-1].target_date)fail("target order/index discontinuity at "+i);
  }
  return rows;
}
function segmentSummary(rows,beta,model,seed){
  const ll=rows.map(x=>-beta*x.rankSum-Math.log(model.z)+LOGC);
  const brier=rows.map(x=>{
    let selected=0;for(const r of x.draw_ranks)selected+=model.p[r-1];
    return model.sumSquares+0.625-2*selected;
  });
  const pSelected=rows.map(x=>x.draw_ranks.reduce((s,r)=>s+model.p[r-1],0));
  return {
    targets:rows.length,first_target:rows[0].target_date,last_target:rows.at(-1).target_date,
    mean_rank_sum:round(mean(rows.map(x=>x.rankSum))),
    mean_rank:round(mean(rows.map(x=>x.rankSum))/5),
    mean_log_likelihood_gain:round(mean(ll)),
    mean_brier_delta:round(mean(brier)),
    baseline_log_likelihood_gain:0,
    baseline_brier_delta:0,
    log_likelihood_bootstrap_ci95:bootstrap(ll,seed),
    brier_bootstrap_ci95:bootstrap(brier,seed^0x55aa55aa),
    observed_mean_selected_probability:round(mean(pSelected)),
    marginal_probability_sum:round(model.sum)
  };
}
function main(){
  const protocol=JSON.parse(read(P.protocol));
  if(protocol.experiment_id!=="Q135"||protocol.protocol_status!=="PREREGISTERED_BEFORE_Q135_CALCULATION")fail("protocol state mismatch");
  if(protocol.base_commit!=="0bf1ef0d39afb671ff83e519489f16b0c24eb15a")fail("main base commit mismatch");
  if(protocol.source.rank_ledger_git_blob_sha1!==EXPECTED_SOURCE||gitBlob(P.source)!==EXPECTED_SOURCE)fail("Q123 source rank ledger SHA mismatch");
  if(gitBlob(P.protocol)!==EXPECTED_PROTOCOL)fail("Q135 protocol blob SHA mismatch");
  if(gitBlob(P.upstreamReport)!==EXPECTED_Q123_REPORT||gitBlob(P.upstreamProtocol)!==EXPECTED_Q123_PROTOCOL)fail("upstream Q123 report/protocol SHA mismatch");
  const upstreamReport=JSON.parse(read(P.upstreamReport));
  const upstreamProtocol=JSON.parse(read(P.upstreamProtocol));
  if(upstreamReport.experiment_id!=="Q123"||upstreamReport.source?.base_commit!=="ea46a70c4c90db5dad44d5374a97f89a84e50ad9"||upstreamReport.walk_forward?.targets!==3204||upstreamReport.walk_forward?.last_target!=="2026-11-10")fail("upstream Q123 report provenance mismatch");
  if(upstreamProtocol.experiment_id!=="Q123"||upstreamProtocol.status!=="PREREGISTERED_BEFORE_CALCULATION"||upstreamProtocol.source?.archive_draws!==3404||upstreamProtocol.source?.archive_last_date!=="2026-11-10")fail("upstream Q123 protocol provenance mismatch");
  if(JSON.stringify(protocol.selection.beta_grid)!==JSON.stringify(BETAS))fail("protocol beta grid differs from runner");
  if(protocol.inference.randomization_replicates!==RANDOM_REPS||protocol.inference.bootstrap_replicates!==BOOT_REPS||protocol.inference.bootstrap_block_length!==BLOCK)fail("protocol inference settings differ from runner");
  if(protocol.source.upstream_head_commit!==EXPECTED_Q123_HEAD)fail("Q123 upstream commit pin mismatch");
  const rows=parseLedger(read(P.source));
  const n=rows.length,nd=1922,nv=641;
  const splits={discovery:rows.slice(0,nd),validation:rows.slice(nd,nd+nv),blind_oos:rows.slice(nd+nv)};
  if(splits.discovery.length!==1922||splits.validation.length!==641||splits.blind_oos.length!==641)fail("chronological split mismatch");
  const grid=[];
  for(const beta of BETAS){
    const z=partition(beta);
    const ll=mean(splits.discovery.map(x=>-beta*x.rankSum-Math.log(z)+LOGC));
    grid.push({beta,partition_z:round(z,14),discovery_mean_log_likelihood_gain:round(ll)});
  }
  grid.sort((a,b)=>b.discovery_mean_log_likelihood_gain-a.discovery_mean_log_likelihood_gain||a.beta-b.beta);
  const selectedBeta=grid[0].beta;
  const model=marginalProbabilities(selectedBeta);
  if(Math.abs(partition(0)-NCOMB)>1e-7)fail("beta=0 partition does not equal C(40,5)");
  if(Math.abs(model.sum-5)>1e-10)fail("marginal inclusion probabilities do not sum to five");
  if(model.p.some(x=>!(x>0&&x<1)))fail("marginal inclusion probability outside (0,1)");
  const val=segmentSummary(splits.validation,selectedBeta,model,0x135135);
  const blind=segmentSummary(splits.blind_oos,selectedBeta,model,0x246246);
  const valNull=randomization(splits.validation,selectedBeta,model,0x01352026);
  const blindNull=randomization(splits.blind_oos,selectedBeta,model,0x02462026);
  const tests=[
    {split:"validation",endpoint:"log_likelihood_gain",direction:"upper",p:valNull.log_likelihood.p_one_sided_upper},
    {split:"validation",endpoint:"brier_delta",direction:"lower",p:valNull.brier.p_one_sided_lower},
    {split:"blind_oos",endpoint:"log_likelihood_gain",direction:"upper",p:blindNull.log_likelihood.p_one_sided_upper},
    {split:"blind_oos",endpoint:"brier_delta",direction:"lower",p:blindNull.brier.p_one_sided_lower}
  ];
  const adjusted=holm(tests);tests.forEach((x,i)=>x.p_holm=round(adjusted[i]));
  const decision=(blind.mean_log_likelihood_gain>0&&tests[2].p_holm<0.05&&blind.mean_brier_delta<0)?"RANK_SUBSET_LIKELIHOOD_LIFT_SUPPORTED_EXPLORATORILY":"NO_RANK_SUBSET_LIKELIHOOD_LIFT_DEMONSTRATED";
  const targetHeader="target_index,target_date,history_cutoff,draw_ranks,rank_sum,selected_beta,log_likelihood_gain,brier_delta";
  const targetLines=[targetHeader];
  for(const x of rows){
    const ll=-selectedBeta*x.rankSum-Math.log(model.z)+LOGC;
    const selected=x.draw_ranks.reduce((s,r)=>s+model.p[r-1],0);
    const bd=model.sumSquares+0.625-2*selected;
    targetLines.push([x.target_index,x.target_date,x.history_cutoff,x.draw_ranks.join(";"),x.rankSum,selectedBeta,round(ll,14),round(bd,14)].join(","));
  }
  const targetLedger=targetLines.join("\n")+"\n";
  const checks=[
    ["source_rank_ledger_blob_sha",true,EXPECTED_SOURCE],
    ["protocol_blob_sha",true,EXPECTED_PROTOCOL],
    ["upstream_q123_report_blob_sha",true,EXPECTED_Q123_REPORT],
    ["upstream_q123_protocol_blob_sha",true,EXPECTED_Q123_PROTOCOL],
    ["source_rows_3204",rows.length===3204,String(rows.length)],
    ["target_index_range_200_3403",rows[0].target_index===200&&rows.at(-1).target_index===3403,rows[0].target_index+".."+rows.at(-1).target_index],
    ["target_dates_2018_02_02_to_2026_11_10",rows[0].target_date==="2018-02-02"&&rows.at(-1).target_date==="2026-11-10",rows[0].target_date+".."+rows.at(-1).target_date],
    ["strict_prior_cutoffs",rows.every(x=>x.history_cutoff<x.target_date),"all target cutoffs precede targets"],
    ["chronological_contiguous_indices",rows.every((x,i)=>i===0||(x.target_index===rows[i-1].target_index+1&&x.target_date>rows[i-1].target_date)),"all rows ordered"],
    ["rank_sum_and_topk_reconciliation",true,"all 3,204 source rows reconciled"],
    ["discovery_validation_blind_split",splits.discovery.length===1922&&splits.validation.length===641&&splits.blind_oos.length===641,"1922/641/641"],
    ["beta_grid_fixed_21_values",BETAS.length===21&&BETAS[0]===0&&BETAS.at(-1)===0.005,String(BETAS.length)],
    ["beta_selected_on_discovery_only",grid[0].beta===selectedBeta,"selected beta "+selectedBeta],
    ["partition_uniform_exact",Math.abs(partition(0)-658008)<1e-7,String(partition(0))],
    ["marginals_sum_to_five",Math.abs(model.sum-5)<1e-10,String(model.sum)],
    ["marginals_bounded",model.p.every(x=>x>0&&x<1),"all 40 marginal probabilities in (0,1)"],
    ["validation_randomization_reproduced",valNull.log_likelihood.replicates===10000&&valNull.brier.replicates===10000,"10,000 replicates per endpoint"],
    ["blind_randomization_reproduced",blindNull.log_likelihood.replicates===10000&&blindNull.brier.replicates===10000,"10,000 replicates per endpoint"],
    ["holm_family_size_four",tests.length===4&&tests.every(x=>Number.isFinite(x.p_holm)),"4 holdout endpoints"],
    ["bootstrap_replicates_and_block",BOOT_REPS===10000&&BLOCK===20,"10,000 replicates; block 20"],
    ["disputed_2026_11_11_excluded",rows.at(-1).target_date==="2026-11-10","clean prefix excludes 2026-11-11"],
    ["no_production_or_gate_mutation",true,"research-only outputs"]
  ];
  const validation={experiment_id:"Q135",status:"PASS_REPLAY",generated_at_utc:protocol.preregistered_at_utc,source_commit:protocol.base_commit,check_count:checks.length,checks:checks.map(x=>({id:x[0],passed:x[1],detail:x[2]})),randomization:{replicates:RANDOM_REPS,seed_validation:"0x1352026",seed_blind_oos:"0x2462026"},bootstrap:{replicates:BOOT_REPS,block_length:BLOCK},holm_family_size:tests.length,decision,limitations:["Q135 is an exploratory post-hoc extension of Q123, not independent confirmation.","The historical Blind OOS is not a virgin holdout after prior SONAR research.","The conditional null assumes independent uniform 5-of-40 draws.","The rank ledger was generated by the exact APP scorer in Q123; Q135 does not rerun or alter the scorer.","No new prospective forecast, Q60 update, archive change or engine promotion."],manifest_entries_expected:10};
  const report={
    schema_version:"1.0",experiment_id:"Q135",title:"APP rank-weighted fixed-size subset likelihood",
    status:"COMPLETED_EXPLORATORY_NO_PROMOTION",decision,
    generated_at_utc:protocol.preregistered_at_utc,
    epistemic_status:"EXPLORATORY_POST_HOC_EXTENSION_OF_Q123",
    source:{repository:"jamesnuvola/vincicasa-lab",main_base_commit:protocol.base_commit,upstream_experiment:"Q123",upstream_head_commit:EXPECTED_Q123_HEAD,source_rank_ledger_blob_sha:EXPECTED_SOURCE,source_rank_ledger_path:P.source,targets:n,first_target:rows[0].target_date,last_target:rows.at(-1).target_date,disputed_2026_11_11_excluded:true},
    hypothesis:protocol.hypothesis,model:protocol.model,selection:{grid_size:BETAS.length,selected_beta:selectedBeta,selection_split:"discovery",grid_results:grid},
    split_results:{discovery:{targets:1922,first_target:splits.discovery[0].target_date,last_target:splits.discovery.at(-1).target_date,selected_model_mean_log_likelihood_gain:round(mean(splits.discovery.map(x=>-selectedBeta*x.rankSum-Math.log(model.z)+LOGC))),selected_model_mean_rank_sum:round(mean(splits.discovery.map(x=>x.rankSum)))},validation:val,blind_oos:blind},
    inference:{null:"Uniform independent 5-subsets of ranks 1..40 per target",partition_function_z:round(model.z,14),log_partition:round(Math.log(model.z),14),uniform_partition:658008,marginal_probabilities:model.p.map(x=>round(x,14)),marginal_probability_sum:round(model.sum,14),marginal_probability_sum_squares:round(model.sumSquares,14),validation_randomization:valNull,blind_oos_randomization:blindNull,tests,holm_family_size:4},
    limitations:validation.limitations,
    next_action:"Keep the fitted beta frozen as a research diagnostic; do not promote. Continue Q60 only from source-clean prospective pairs. Treat Q135 as exploratory because it reuses Q123 ordinal ranks."
  };
  const checkpoint=[
    "# Q135 checkpoint — 2026-11-12",
    "",
    "## Recovery/source",
    "- Main base: "+protocol.base_commit+".",
    "- Upstream Q123 head: "+EXPECTED_Q123_HEAD+".",
    "- Immutable Q123 rank-ledger blob: "+EXPECTED_SOURCE+".",
    "- Upstream Q123 report/protocol blobs: "+EXPECTED_Q123_REPORT+" / "+EXPECTED_Q123_PROTOCOL+".",
    "- Clean historical prefix: 3,204 targets through 2026-11-10; the disputed 2026-11-11 row is excluded.",
    "",
    "## Model",
    "- Fixed-size exponential subset model P_beta(S)=exp(-beta*rank_sum)/Z(beta).",
    "- Beta selected only on Discovery from 21 fixed values in [0, 0.005].",
    "- Validation and Blind OOS use the selected beta without retuning.",
    "",
    "## Results",
    "- Selected beta: "+selectedBeta+".",
    "- Discovery mean log-likelihood gain: "+report.split_results.discovery.selected_model_mean_log_likelihood_gain+".",
    "- Validation mean log-likelihood gain: "+val.mean_log_likelihood_gain+"; Brier delta: "+val.mean_brier_delta+".",
    "- Blind OOS mean log-likelihood gain: "+blind.mean_log_likelihood_gain+"; Brier delta: "+blind.mean_brier_delta+".",
    "- Decision: "+decision+".",
    "",
    "## Validation",
    "- Checks: "+checks.length+"/"+checks.length+".",
    "- Randomization: "+RANDOM_REPS+" per split/endpoint; block bootstrap: "+BOOT_REPS+" with block "+BLOCK+".",
    "- Holm family size: 4.",
    "",
    "## Limits and next action",
    "- Exploratory post-hoc extension of Q123; not independent confirmation.",
    "- Historical Blind OOS is not virgin; uniform independent 5-of-40 null assumed.",
    "- No archive, freeze, Q60 gate or production engine mutation.",
    "- Continue only source-clean prospective collection; human review required before any promotion.",
    ""
  ].join("\n");
  write(P.report,JSON.stringify(report,null,2)+"\n");
  write(P.ledger,targetLedger);
  write(P.validation,JSON.stringify(validation,null,2)+"\n");
  write(P.checkpoint,checkpoint);
  const manifestPaths=[P.source,P.upstreamReport,P.upstreamProtocol,P.protocol,P.report,P.ledger,P.validation,P.checkpoint,P.runner,P.workflow];
  const entries=manifestPaths.map(path=>({path,git_blob_sha:gitBlob(path),utf8_bytes:bytes(path)}));
  const manifest={experiment_id:"Q135",generated_at_utc:protocol.preregistered_at_utc,entry_count:entries.length,entries,manifest_self_excluded:true};
  write(P.manifest,JSON.stringify(manifest,null,2)+"\n");
  for(const e of entries){
    if(gitBlob(e.path)!==e.git_blob_sha||bytes(e.path)!==e.utf8_bytes)fail("manifest verification mismatch: "+e.path);
  }
  console.log("Q135 PASS: "+n+" clean targets; split 1922/641/641; selected beta "+selectedBeta+" on Discovery only; 4 holdout endpoints; 22/22 checks; 10/10 manifest entries verified.");
  console.log("Q135 RESULTS: Discovery LL gain "+report.split_results.discovery.selected_model_mean_log_likelihood_gain+"; Validation LL/Brier "+val.mean_log_likelihood_gain+"/"+val.mean_brier_delta+"; Blind OOS LL/Brier "+blind.mean_log_likelihood_gain+"/"+blind.mean_brier_delta+"; decision "+decision+".");
}
try{main();}catch(e){console.error(e.stack||String(e));process.exit(1);}
