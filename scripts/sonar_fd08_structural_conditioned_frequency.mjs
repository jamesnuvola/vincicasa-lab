#!/usr/bin/env node
import fs from "node:fs";
import { createHash } from "node:crypto";

const archivePath = process.argv[2] ?? "data/storico_daily.csv";
const reportPath = process.argv[3] ?? "reports/sequence_agent/fd08_structural_conditioned_frequency_20261108.json";
const ledgerPath = process.argv[4] ?? "reports/sequence_agent/fd08_structural_conditioned_target_ledger_20261108.csv";
const csv = fs.readFileSync(archivePath, "utf8");
const gitBlobSha = createHash("sha1").update(Buffer.from(`blob ${Buffer.byteLength(csv)}\\0${csv}`, "utf8")).digest("hex");
const expectedBlobSha = "5d2efd70684e918b27d8f06386d545647898336d";
if (gitBlobSha !== expectedBlobSha) throw new Error(`Archive Git blob SHA mismatch: ${gitBlobSha}`);
const analyze = function(csv,actualBlobSha){
  const expected="5d2efd70684e918b27d8f06386d545647898336d";
  const lines=csv.trimEnd().split(/\r?\n/);
  if(lines[0]!=="data,n1,n2,n3,n4,n5")throw new Error("Unexpected CSV header");
  const rows=lines.slice(1).map(line=>{const a=line.split(",");return {date:a[0],nums:a.slice(1).map(Number)};});
  const shapeValid=rows.length===3401&&lines.length===3402&&rows.every((r,i)=>r.nums.length===5&&new Set(r.nums).size===5&&r.nums.every(n=>Number.isInteger(n)&&n>=1&&n<=40)&&/^\d{4}-\d{2}-\d{2}$/.test(r.date)&&(i===0||r.date>rows[i-1].date));
  if(actualBlobSha!==expected||!shapeValid)throw new Error("Fail-closed archive validation: blob SHA or draw structure mismatch");
  const N=rows.length,sums=rows.map(r=>r.nums.reduce((a,b)=>a+b,0)),first200=sums.slice(0,200).slice().sort((a,b)=>a-b);
  function thresholds(K){return Array.from({length:K-1},(_,i)=>first200[Math.floor((i+1)*(200/K)-1)]);}
  const cuts={2:thresholds(2),4:thresholds(4)};
  function stateOf(sum,K){let s=0;for(const c of cuts[K])if(sum>c)s++;return s;}
  function splitOf(t){return t<1700?"discovery":t<2550?"validation":"blind_oos";}
  function empty(){return {targets:0,top5Hits:0,top10Hits:0,top20Hits:0,rankSum:0,brierSum:0,loglossSum:0};}
  function rank(scores){return scores.map((v,i)=>({n:i+1,v})).sort((a,b)=>b.v-a.v||a.n-b.n);}
  function record(obj,ranked,draw,scores){
    const rankMap=Array(41);ranked.forEach((x,i)=>rankMap[x.n]=i+1);
    const actual=new Set(draw);let h5=0,h10=0,h20=0,rankSum=0,brier=0,ll=0;
    for(let n=1;n<=40;n++){
      const y=actual.has(n)?1:0;
      if(rankMap[n]<=5&&y)h5++;if(rankMap[n]<=10&&y)h10++;if(rankMap[n]<=20&&y)h20++;
      rankSum+=rankMap[n]*y;
      const p=Math.max(1e-6,Math.min(1-1e-6,scores[n-1]));
      brier+=(p-y)**2;ll+=-(y*Math.log(p)+(1-y)*Math.log(1-p));
    }
    obj.targets++;obj.top5Hits+=h5;obj.top10Hits+=h10;obj.top20Hits+=h20;obj.rankSum+=rankSum/5;obj.brierSum+=brier/40;obj.loglossSum+=ll/40;
    return {h5,h10,h20,rankMean:rankSum/5,brier:brier/40,logloss:ll/40};
  }
  function finish(o){return {targets:o.targets,top5HitShare:o.top5Hits/(o.targets*5),top5Hits:o.top5Hits,top10HitShare:o.top10Hits/(o.targets*5),top10Hits:o.top10Hits,top20HitShare:o.top20Hits/(o.targets*5),top20Hits:o.top20Hits,meanRank:o.rankSum/o.targets,brier:o.brierSum/o.targets,logloss:o.loglossSum/o.targets};}
  function holm(ps){const ix=ps.map((p,i)=>({p,i})).sort((a,b)=>a.p-b.p);const out=Array(ps.length);let running=0;for(let k=0;k<ix.length;k++){running=Math.max(running,Math.min(1,(ps.length-k)*ix[k].p));out[ix[k].i]=running;}return out;}
  const models=[];for(const K of [2,4])for(const alpha of [0,50,200,500,1000])models.push({id:`K${K}_A${alpha}`,K,alpha});
  const baseline={id:"UNCONDITIONAL",splits:{discovery:empty(),validation:empty(),blind_oos:empty()}};
  const modelStats=Object.fromEntries(models.map(m=>[m.id,{splits:{discovery:empty(),validation:empty(),blind_oos:empty()}}]));
  const total=Array(40).fill(0);for(let i=0;i<300;i++)for(const n of rows[i].nums)total[n-1]++;
  const cond={2:Array.from({length:2},()=>Array(40).fill(0)),4:Array.from({length:4},()=>Array(40).fill(0))};
  const exposure={2:Array(2).fill(0),4:Array(4).fill(0)};
  for(let j=1;j<300;j++){const s2=stateOf(sums[j-1],2),s4=stateOf(sums[j-1],4);exposure[2][s2]++;exposure[4][s4]++;for(const n of rows[j].nums){cond[2][s2][n-1]++;cond[4][s4][n-1]++;}}
  const perTarget=[];
  for(let t=300;t<N;t++){
    const actual=rows[t].nums,split=splitOf(t),baseScores=total.map(c=>c/t),baseRank=rank(baseScores);
    const baseVal=record(baseline.splits[split],baseRank,actual,baseScores);
    const targetState2=stateOf(sums[t-1],2),targetState4=stateOf(sums[t-1],4),modelValues={};
    for(const m of models){
      const state=m.K===2?targetState2:targetState4,den=exposure[m.K][state]+m.alpha;
      if(!(den>0))throw new Error("Zero conditional exposure");
      const scores=cond[m.K][state].map((c,n)=>(c+m.alpha*baseScores[n])/den),ranked=rank(scores);
      const val=record(modelStats[m.id].splits[split],ranked,actual,scores);
      modelValues[m.id]={...val,top5:ranked.slice(0,5).map(x=>x.n),top10:ranked.slice(0,10).map(x=>x.n),top20:ranked.slice(0,20).map(x=>x.n)};
    }
    perTarget.push({t,date:rows[t].date,cutoff:rows[t-1].date,split,actual:actual.slice(),previousSum:sums[t-1],state2:targetState2,state4:targetState4,baseline:{...baseVal,top5:baseRank.slice(0,5).map(x=>x.n)},models:modelValues});
    const stateForDraw2=stateOf(sums[t],2),stateForDraw4=stateOf(sums[t],4);
    exposure[2][stateForDraw2]++;exposure[4][stateForDraw4]++;
    for(const n of actual){total[n-1]++;cond[2][stateForDraw2][n-1]++;cond[4][stateForDraw4][n-1]++;}
  }
  const splitMetrics={};for(const m of models){splitMetrics[m.id]={};for(const s of ["discovery","validation","blind_oos"])splitMetrics[m.id][s]=finish(modelStats[m.id].splits[s]);}
  const baselineMetrics={};for(const s of ["discovery","validation","blind_oos"])baselineMetrics[s]=finish(baseline.splits[s]);
  const modelResults=models.map(m=>({id:m.id,K:m.K,alpha:m.alpha,discovery:splitMetrics[m.id].discovery,validation:splitMetrics[m.id].validation,blind_oos:splitMetrics[m.id].blind_oos}));
  const selected=modelResults.slice().sort((a,b)=>b.validation.top5HitShare-a.validation.top5HitShare||a.validation.brier-b.validation.brier||b.alpha-a.alpha||a.K-b.K)[0];
  const blind=perTarget.filter(x=>x.split==="blind_oos"),choose=(n,k)=>{if(k<0||k>n)return 0;k=Math.min(k,n-k);let v=1;for(let i=1;i<=k;i++)v=v*(n-k+i)/i;return v;};
  const hypergeom=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k)/choose(40,5));
  let dist=[1];for(let i=0;i<blind.length;i++){const next=Array(dist.length+5).fill(0);for(let a=0;a<dist.length;a++)for(let k=0;k<6;k++)next[a+k]+=dist[a]*hypergeom[k];dist=next;}
  function exactTail(hits){let p=0;for(let i=hits;i<dist.length;i++)p+=dist[i];return p;}
  const uniformRaw=modelResults.map(m=>exactTail(m.blind_oos.top5Hits)),uniformHolm=holm(uniformRaw);
  const paired={};
  for(const m of models){
    const delta=blind.map(x=>x.models[m.id].h5-x.baseline.h5),blocks=[];for(let i=0;i<delta.length;i+=7)blocks.push(delta.slice(i,i+7).reduce((a,b)=>a+b,0));
    const observed=blocks.reduce((a,b)=>a+b,0);let extreme=0;const reps=20000;let seed=0xFD0808;
    function rng(){seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;}
    for(let r=0;r<reps;r++){let s=0;for(const d of blocks)s+=(rng()<0.5?-1:1)*d;if(Math.abs(s)>=Math.abs(observed)-1e-12)extreme++;}
    paired[m.id]={deltaHits:observed,deltaHitShare:observed/(blind.length*5),blockSignFlipTwoSidedP:(extreme+1)/(reps+1),blocks:blocks.length,repetitions:reps};
  }
  const pairedHolm=holm(models.map(m=>paired[m.id].blockSignFlipTwoSidedP));models.forEach((m,i)=>paired[m.id].holmP=pairedHolm[i]);
  const results=modelResults.map((m,i)=>({...m,blind_uniform_p:uniformRaw[i],blind_uniform_holm_p:uniformHolm[i],paired_vs_unconditional:paired[m.id]}));
  const selectedResult=results.find(x=>x.id===selected.id),bestBlind=results.slice().sort((a,b)=>b.blind_oos.top5HitShare-a.blind_oos.top5HitShare)[0];
  const deltaSelected=blind.map(x=>x.models[selected.id].h5-x.baseline.h5),observedDelta=deltaSelected.reduce((a,b)=>a+b,0);
  const bootstrap=[];const bootReps=10000,blockLength=7,T=deltaSelected.length;let bootSeed=0xFD08B00B;
  function bootRng(){bootSeed=(Math.imul(bootSeed,1664525)+1013904223)>>>0;return bootSeed/4294967296;}
  for(let r=0;r<bootReps;r++){let sum=0,count=0;while(count<T){const start=Math.floor(bootRng()*T);for(let k=0;k<blockLength&&count<T;k++,count++)sum+=deltaSelected[(start+k)%T];}bootstrap.push(sum/(T*5));}
  bootstrap.sort((a,b)=>a-b);
  const ci=[bootstrap[Math.floor(0.025*(bootReps-1))],bootstrap[Math.floor(0.975*(bootReps-1))]];
  const report={
    schema_version:"1.0",task_id:"FD08",status:"EXPLORATORY_NULL_NO_PROMOTION",
    archive:{path:"data/storico_daily.csv",git_blob_sha:actualBlobSha,draw_count:N,first_date:rows[0].date,last_date:rows[N-1].date},
    validation:{csv_line_count:lines.length,draw_count_check:rows.length===3401,dates_unique_and_ascending:true,draws_five_distinct_in_1_to_40:true,source_blob_sha_matches_registered:actualBlobSha===expected,strict_prior_loop_order:"PASS: target t scored before adding draw t to total or conditional histories",reproducibility_protocol:"two independent CodeMode executions compared byte-for-byte; native Node/CI remain pending"},
    hypothesis:"The sum of the previous draw defines a discrete structural state; next-draw per-number inclusion frequencies conditional on that state may improve Top5 ranking over unconditional historical frequencies.",
    method:{minimum_prior_draws:300,cutpoints_from_initial_prefix_draws:200,cutpoints_frozen_for_all_scored_targets:true,state_count_grid:[2,4],alpha_grid:[0,50,200,500,1000],configuration_count:10,score_formula:"(conditional_count[n,state] + alpha * unconditional_frequency[n]) / (state_exposure[state] + alpha)",baseline:"unconditional per-number occurrence frequency over all prior draws",tie_break:"score descending, then number ascending",validation_selection:"maximize validation Top5 hit share; tie-break lower Brier, then higher alpha, then fewer states"},
    splits:{discovery:{target_index_start:300,target_index_end_exclusive:1700,targets:1400},validation:{target_index_start:1700,target_index_end_exclusive:2550,targets:850},blind_oos:{target_index_start:2550,target_index_end_exclusive:3401,targets:851}},
    state_cutpoints_from_initial_prefix:{K2:cuts[2],K4:cuts[4],quantile_method:"sorted first 200 sums; order-statistic cutpoints at 50% or 25/50/75%; category increments when sum exceeds cutpoint"},
    selection:{selected_on_validation:selected.id,selected_validation_metrics:selected.validation,selected_blind_oos_metrics:selected.blind_oos,blind_oos_leader_descriptive_only:{id:bestBlind.id,blind_metrics:bestBlind.blind_oos,blind_uniform_p:bestBlind.blind_uniform_p,blind_uniform_holm_p:bestBlind.blind_uniform_holm_p,paired_vs_unconditional:bestBlind.paired_vs_unconditional,not_eligible_for_selection:true}},
    baseline:{id:"UNCONDITIONAL",metrics:baselineMetrics,uniform_reference:{top5_hit_share:0.125,top10_hit_share:0.25,top20_hit_share:0.5,mean_rank:20.5}},
    models:results,
    summary:{selected_blind_top5_hits:selected.blind_oos.top5Hits,uniform_expected_blind_top5_hits:blind.length*5*0.125,selected_blind_top5_raw_p:uniformRaw[results.findIndex(x=>x.id===selected.id)],selected_blind_top5_holm_p:uniformHolm[results.findIndex(x=>x.id===selected.id)],selected_vs_unconditional_delta_hits:observedDelta,selected_vs_unconditional_delta_hit_share:observedDelta/(blind.length*5),selected_vs_unconditional_paired_raw_p:paired[selected.id].blockSignFlipTwoSidedP,selected_vs_unconditional_paired_holm_p:pairedHolm[models.findIndex(m=>m.id===selected.id)],selected_delta_hit_share_block_bootstrap_95_ci:ci,bootstrap_repetitions:bootReps,bootstrap_block_length:7,selected_brier_delta_vs_unconditional:selected.blind_oos.brier-baselineMetrics.blind_oos.brier,selected_logloss_delta_vs_unconditional:selected.blind_oos.logloss-baselineMetrics.blind_oos.logloss},
    multiple_testing:{uniform_null:{distribution:"exact convolution of Hypergeometric(N=40,K=5,n=5) overlap for each blind target",alternative:"greater Top5 hit count",family_size:10,correction:"Holm-Bonferroni",raw_p_values:uniformRaw,adjusted_p_values:uniformHolm},paired_baseline_null:{method:"Monte Carlo block sign-flip, two-sided",block_length:7,repetitions:20000,seed:"0xFD0808",family_size:10,correction:"Holm-Bonferroni",raw_p_values:models.map(m=>paired[m.id].blockSignFlipTwoSidedP),adjusted_p_values:pairedHolm}},
    target_ledger:{path:"reports/sequence_agent/fd08_structural_conditioned_target_ledger_20261108.csv",rows:perTarget.length,columns:["target_index","target_date","cutoff_date","split","prior_draw_count","previous_draw_sum","state2","state4","actual_numbers","unconditional_top5","unconditional_hits","selected_model","selected_top5","selected_hits","delta_hits",...models.map(m=>m.id+"_top5_hits")]},
    outputs:{report_json:"reports/sequence_agent/fd08_structural_conditioned_frequency_20261108.json",report_markdown:"reports/sequence_agent/fd08_structural_conditioned_frequency_20261108.md",script:"scripts/sonar_fd08_structural_conditioned_frequency.mjs",target_ledger:"reports/sequence_agent/fd08_structural_conditioned_target_ledger_20261108.csv"},
    limits:["The experiment was motivated by prior exploratory SONAR work; the correction covers the registered 10 configurations within FD-08, not the entire historical project-wide hypothesis search.","The blind OOS is retrospective and reused across the project; this result is not independent prospective evidence.","The structural state is the previous draw's sum bin, not a physical causal state.","No promotion or Q60 prospective-gate increment."],
    next_action:"Freeze FD-08 parameters and compare only on future append-only targets; do not retune on this blind OOS."
  };
  const selectedModel=selected.id;
  const header=["target_index","target_date","cutoff_date","split","prior_draw_count","previous_draw_sum","state2","state4","actual_numbers","unconditional_top5","unconditional_hits","selected_model","selected_top5","selected_hits","delta_hits",...models.map(m=>m.id+"_top5_hits")];
  const ledgerRows=[header.join(",")];
  for(const x of perTarget){
    const sel=x.models[selectedModel],delta=sel.h5-x.baseline.h5;
    const row=[x.t,x.date,x.cutoff,x.split,x.t,x.previousSum,x.state2,x.state4,x.actual.join("-"),x.baseline.top5.join("-"),x.baseline.h5,selectedModel,sel.top5.join("-"),sel.h5,delta,...models.map(m=>x.models[m.id].h5)];
    ledgerRows.push(row.join(","));
  }
  return {report,ledgerCsv:ledgerRows.join("\n")+"\n"};
};
const result = analyze(csv, gitBlobSha);
fs.writeFileSync(reportPath, JSON.stringify(result.report, null, 2) + "\\n", "utf8");
fs.writeFileSync(ledgerPath, result.ledgerCsv, "utf8");
console.log(JSON.stringify({task_id:result.report.task_id,archive_sha:gitBlobSha,selected:result.report.selection.selected_on_validation,ledger_rows:result.report.target_ledger.rows,status:result.report.status}));
