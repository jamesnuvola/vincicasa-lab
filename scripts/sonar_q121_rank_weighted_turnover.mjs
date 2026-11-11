#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const DIR=path.join(ROOT,"reports","sequence_agent");
const P={
  archive:path.join(ROOT,"data","storico_daily.csv"),
  app:path.join(ROOT,"src","data.json"),
  source:path.join(ROOT,"src","VinciCasaLab.jsx"),
  active:path.join(DIR,"active_engine_walkforward.json"),
  protocol:path.join(DIR,"q121_rank_weighted_turnover_protocol_2026-11-11.json"),
  runner:path.join(ROOT,"scripts","sonar_q121_rank_weighted_turnover.mjs"),
  workflow:path.join(ROOT,".github","workflows","q121-rank-weighted-turnover.yml"),
  ledger:path.join(DIR,"q121_rank_weighted_turnover_target_ledger_2026-11-11.csv"),
  report:path.join(DIR,"q121_rank_weighted_turnover_report_2026-11-11.json"),
  validation:path.join(DIR,"q121_rank_weighted_turnover_validation_2026-11-11.json"),
  checkpoint:path.join(DIR,"q121_rank_weighted_turnover_checkpoint_2026-11-11.md"),
  manifest:path.join(DIR,"q121_rank_weighted_turnover_persistence_manifest_2026-11-11.json")
};
const Q0=Array.from({length:6},(_,k)=>choose(20,k)*choose(20,5-k)/choose(40,5));
const ALPHA=200,MIN_HISTORY=201,BLOCK=20,REPS=50000,BOOT=10000;
const OVERLAP_STATES=["LOW","MID","HIGH"];
const RANK_STATES=["STABLE","MODERATE","VOLATILE"];
function fail(m){console.error("Q121 BLOCKED: "+m);process.exit(1);}
function git(args){return execFileSync("git",args,{encoding:"utf8"}).trim();}
function blob(p){return git(["hash-object",p]);}
function commitFor(p){return git(["log","-1","--format=%H","--",p]);}
function commitTimeFor(p){return git(["log","-1","--format=%cI","--",p]);}
function choose(n,k){if(k<0||k>n)return 0;let v=1;for(let i=1;i<=k;i++)v=v*(n-i+1)/i;return v;}
function sum(a){return a.reduce((x,y)=>x+y,0);}
function mean(a){return a.length?sum(a)/a.length:NaN;}
function close(a,b,tol=1e-12){return Math.abs(a-b)<=tol;}
function parse(text){
  const lines=text.trimEnd().split(/\r?\n/);
  if(lines[0]!=="data,n1,n2,n3,n4,n5")fail("archive header mismatch");
  const out=[];let prev="";
  for(let i=1;i<lines.length;i++){
    const f=lines[i].split(","),d=f[0],n=f.slice(1).map(Number);
    if(f.length!==6||!/^\d{4}-\d{2}-\d{2}$/.test(d)||n.length!==5||new Set(n).size!==5||
      n.some((v,j)=>!Number.isInteger(v)||v<1||v>40||(j>0&&v<n[j-1]))||(prev&&d<=prev))fail("invalid archive row "+(i+1));
    out.push({d,n});prev=d;
  }
  return out;
}
function extract(s,n,next){
  const a=s.indexOf("function "+n+"(");
  const b=next?s.indexOf("\nfunction "+next+"(",a+1):s.indexOf("\nconst Card =",a+1);
  if(a<0||b<0)fail("cannot extract exact APP function "+n);
  return s.slice(a,b).trim();
}
function makeScorer(s){
  const code=[
    extract(s,"overlapCount","sonarTransitionProfile"),
    extract(s,"sonarTransitionProfile","sonarAnalogCore"),
    extract(s,"sonarAnalogCore",null),
    "return sonarAnalogCore(draws);"
  ].join("\n");
  return new Function("draws",code);
}
function top20(draws,score){
  const r=score(draws);
  if(!r||!Array.isArray(r.scores)||r.scores.length!==40)fail("APP scorer did not return 40 ranked scores");
  const top=r.scores.slice(0,20).map(x=>x.n);
  if(top.length!==20||new Set(top).size!==20)fail("invalid APP Top20");
  return top;
}
function features(current,previous){
  const rc=new Map(current.map((n,i)=>[n,i+1]));
  const rp=new Map(previous.map((n,i)=>[n,i+1]));
  const common=current.filter(n=>rp.has(n));
  const overlap=common.length;
  const displacement=overlap?mean(common.map(n=>Math.abs(rc.get(n)-rp.get(n))/19)):1;
  const overlapState=overlap<=15?"LOW":overlap<=17?"MID":"HIGH";
  const rankState=displacement<=0.25?"STABLE":displacement<=0.50?"MODERATE":"VOLATILE";
  return {overlap,displacement,overlapState,rankState,key:overlapState+"|"+rankState};
}
function newCounts(){return {n:0,c:Array(6).fill(0)};}
function conditional(prior,counts){
  const p=prior.map((q,k)=>(ALPHA*q+counts.c[k])/(ALPHA+counts.n));
  const z=sum(p);
  return {p,error:Math.abs(z-1)};
}
function brier(p,h){return sum(p.map((x,k)=>(x-(k===h?1:0))**2));}
function logloss(p,h){return -Math.log(Math.max(Number.MIN_VALUE,p[h]));}
function scoreTarget(p0,p1,p2,h){
  const b0=brier(p0,h),b1=brier(p1,h),b2=brier(p2,h);
  const l0=logloss(p0,h),l1=logloss(p1,h),l2=logloss(p2,h);
  return {brier0:b0,brier1:b1,brier2:b2,logloss0:l0,logloss1:l1,logloss2:l2,
    brierGain21:b1-b2,loglossGain21:l1-l2,brierGain20:b0-b2,loglossGain20:l0-l2};
}
function run(draws,score){
  const overlapCounts={LOW:newCounts(),MID:newCounts(),HIGH:newCounts()};
  const jointCounts={};
  let previous=top20(draws.slice(0,200),score);
  const rows=[];
  let maxNormError=0;
  for(let i=MIN_HISTORY;i<draws.length;i++){
    const current=top20(draws.slice(0,i),score);
    const f=features(current,previous);
    const c1=overlapCounts[f.overlapState];
    const c2=jointCounts[f.key]||newCounts();
    const p1r=conditional(Q0,c1),p2r=conditional(p1r.p,c2);
    maxNormError=Math.max(maxNormError,p1r.error,p2r.error);
    const actual=new Set(draws[i].n);
    const hits=current.reduce((n,x)=>n+(actual.has(x)?1:0),0);
    const losses=scoreTarget(Q0,p1r.p,p2r.p,hits);
    rows.push({
      date:draws[i].d,history_cutoff:draws[i-1].d,previous_forecast_cutoff:draws[i-2].d,
      overlap:f.overlap,overlap_state:f.overlapState,mean_rank_displacement:f.displacement,
      rank_state:f.rankState,joint_state:f.key,prior_overlap_n:c1.n,prior_joint_n:c2.n,
      hits,p0:Q0,p1:p1r.p,p2:p2r.p,p1_sum:sum(p1r.p),p2_sum:sum(p2r.p),...losses
    });
    c1.n++;c1.c[hits]++;
    if(!jointCounts[f.key])jointCounts[f.key]=newCounts();
    jointCounts[f.key].n++;jointCounts[f.key].c[hits]++;
    previous=current;
  }
  return {rows,overlapCounts,jointCounts,maxNormError,previous};
}
function csv(rows){
  const h=["target_date","history_cutoff","previous_forecast_cutoff","top20_overlap","overlap_state","mean_rank_displacement","rank_state","joint_state","prior_overlap_targets","prior_joint_targets","actual_top20_hits"];
  for(let k=0;k<6;k++)h.push("p0_"+k);
  for(let k=0;k<6;k++)h.push("p1_"+k);
  for(let k=0;k<6;k++)h.push("p2_"+k);
  h.push("p1_sum","p2_sum","brier_gain_m2_vs_m1","logloss_gain_m2_vs_m1","brier_gain_m2_vs_m0","logloss_gain_m2_vs_m0");
  const lines=[h.join(",")];
  for(const r of rows){
    const v=[r.date,r.history_cutoff,r.previous_forecast_cutoff,r.overlap,r.overlap_state,r.mean_rank_displacement.toFixed(10),r.rank_state,r.joint_state,r.prior_overlap_n,r.prior_joint_n,r.hits];
    for(const p of [r.p0,r.p1,r.p2])for(const x of p)v.push(x.toFixed(10));
    v.push(r.p1_sum.toFixed(10),r.p2_sum.toFixed(10),r.brierGain21.toFixed(10),r.loglossGain21.toFixed(10),r.brierGain20.toFixed(10),r.loglossGain20.toFixed(10));
    lines.push(v.join(","));
  }
  return lines.join("\n")+"\n";
}
function segment(rows){
  const hist=Array(6).fill(0),ov={LOW:0,MID:0,HIGH:0},rk={STABLE:0,MODERATE:0,VOLATILE:0},joint={};
  for(const r of rows){hist[r.hits]++;ov[r.overlap_state]++;rk[r.rank_state]++;joint[r.joint_state]=(joint[r.joint_state]||0)+1;}
  const avg=k=>mean(rows.map(r=>r[k]));
  return {
    targets:rows.length,first_target:rows[0]?.date,last_target:rows.at(-1)?.date,
    mean_top20_hits:avg("hits"),mean_overlap:avg("overlap"),mean_rank_displacement:avg("mean_rank_displacement"),
    hit_distribution:hist,overlap_state_counts:ov,rank_state_counts:rk,joint_state_support:joint,
    mean_brier_m0:avg("brier0"),mean_brier_m1:avg("brier1"),mean_brier_m2:avg("brier2"),
    mean_logloss_m0:avg("logloss0"),mean_logloss_m1:avg("logloss1"),mean_logloss_m2:avg("logloss2"),
    brier_gain_m2_vs_m1:avg("brierGain21"),logloss_gain_m2_vs_m1:avg("loglossGain21"),
    brier_gain_m2_vs_m0:avg("brierGain20"),logloss_gain_m2_vs_m0:avg("loglossGain20")
  };
}
function rng(seed){let s=seed>>>0;return()=>{s^=s<<13;s^=s>>>17;s^=s<<5;return(s>>>0)/4294967296;};}
function quantile(a,p){const x=[...a].sort((u,v)=>u-v),z=(x.length-1)*p,l=Math.floor(z),h=Math.ceil(z);return x[l]+(x[h]-x[l])*(z-l);}
function infer(gains,seed){
  const n=gains.length,obs=mean(gains),blocks=[];
  for(let i=0;i<n;i+=BLOCK)blocks.push(sum(gains.slice(i,Math.min(n,i+BLOCK))));
  const r=rng(seed);let extreme=0;
  for(let b=0;b<REPS;b++){let v=0;for(const x of blocks)v+=(r()<0.5?-x:x);if(v>=obs*n-1e-15)extreme++;}
  const p=(extreme+1)/(REPS+1),r2=rng(seed+0x9e3779b9),boot=[];
  for(let b=0;b<BOOT;b++){
    let v=0,c=0;
    while(c<n){const st=Math.floor(r2()*n);for(let j=0;j<BLOCK&&c<n;j++,c++)v+=gains[(st+j)%n];}
    boot.push(v/n);
  }
  return {n,mean_gain:obs,block_length:BLOCK,block_count:blocks.length,sign_flip_replicates:REPS,sign_flip_extreme:extreme,p_one_sided_improvement:p,bootstrap_replicates:BOOT,bootstrap_ci95:[quantile(boot,0.025),quantile(boot,0.975)]};
}
function holm(ps){
  const a=ps.map((p,i)=>({p,i})).sort((x,y)=>x.p-y.p),out=Array(ps.length).fill(1);let prev=0;
  for(let i=0;i<a.length;i++){prev=Math.max(prev,(a.length-i)*a[i].p);out[a[i].i]=Math.min(1,prev);}
  return out;
}
function canonicalize(v){
  if(typeof v==="number")return Number(v.toFixed(12));
  if(Array.isArray(v))return v.map(canonicalize);
  if(v&&typeof v==="object")return Object.fromEntries(Object.entries(v).map(([k,x])=>[k,canonicalize(x)]));
  return v;
}
function gitBlobSha(text){
  const b=Buffer.from(text,"utf8");
  return createHash("sha1").update(Buffer.from("blob "+b.length+"\0","utf8")).update(b).digest("hex");
}
function expectedOutputs(){
  const protocol=JSON.parse(fs.readFileSync(P.protocol,"utf8"));
  const dataSha=blob("data/storico_daily.csv"),sourceSha=blob("src/VinciCasaLab.jsx"),appSha=blob("src/data.json");
  if(protocol.experiment_id!=="Q121"||protocol.source.archive_git_blob_sha1!==dataSha||protocol.source.scorer_git_blob_sha1!==sourceSha||protocol.source.app_data_git_blob_sha1!==appSha)fail("pinned source blob SHA mismatch");
  const draws=parse(fs.readFileSync(P.archive,"utf8"));
  const app=JSON.parse(fs.readFileSync(P.app,"utf8"));
  let appOK=Array.isArray(app.modelDraws)&&app.modelDraws.length===draws.length&&app.histN===draws.length&&app.lastDate===draws.at(-1).d;
  if(appOK)for(let i=0;i<draws.length;i++){const x=app.modelDraws[i];if(!x||x.d!==draws[i].d||!Array.isArray(x.n)||x.n.join(",")!==draws[i].n.join(",")){appOK=false;break;}}
  const active=JSON.parse(fs.readFileSync(P.active,"utf8"));
  const score=makeScorer(fs.readFileSync(P.source,"utf8"));
  const a=run(draws,score),b=run(draws,score),rows=a.rows;
  const n=rows.length,d=Math.round(n*0.6),v=Math.round(n*0.2),o=n-d-v;
  const replay=csv(rows)===csv(b.rows);
  const segments={
    discovery:segment(rows.slice(0,d)),
    validation:segment(rows.slice(d,d+v)),
    blind_oos:segment(rows.slice(d+v))
  };
  const blind=rows.slice(d+v);
  const tests=[
    {endpoint:"M2_vs_M1_Brier",metric:"multiclass_brier",baseline:"M1_overlap_only",gains:blind.map(r=>r.brierGain21),seed:121001},
    {endpoint:"M2_vs_M1_LogLoss",metric:"realized_hit_count_logloss",baseline:"M1_overlap_only",gains:blind.map(r=>r.loglossGain21),seed:121002},
    {endpoint:"M2_vs_M0_Brier",metric:"multiclass_brier",baseline:"M0_exact_hypergeometric",gains:blind.map(r=>r.brierGain20),seed:121003},
    {endpoint:"M2_vs_M0_LogLoss",metric:"realized_hit_count_logloss",baseline:"M0_exact_hypergeometric",gains:blind.map(r=>r.loglossGain20),seed:121004}
  ];
  for(const t of tests)t.inference=infer(t.gains,t.seed);
  const adjusted=holm(tests.map(t=>t.inference.p_one_sided_improvement));
  tests.forEach((t,i)=>{t.inference.p_holm=adjusted[i];delete t.gains;});
  const bothVsM1=segments.blind_oos.brier_gain_m2_vs_m1>0&&segments.blind_oos.logloss_gain_m2_vs_m1>0;
  const bothVsM0=segments.blind_oos.brier_gain_m2_vs_m0>0&&segments.blind_oos.logloss_gain_m2_vs_m0>0;
  const sig=tests.every(t=>t.inference.p_holm<0.05);
  const decision=bothVsM1&&bothVsM0&&sig?"POTENTIAL_INCREMENTAL_RANK_TURNOVER_LIFT_REQUIRES_HUMAN_REVIEW":"NO_INCREMENTAL_RANK_WEIGHTED_TURNOVER_LIFT_DEMONSTRATED";
  const futureIndices=[201,401,801,1201,1601,2001,2401,2801,3200];
  const future=[];
  for(const i of futureIndices){
    const origCurrent=top20(draws.slice(0,i),score),origPrevious=top20(draws.slice(0,i-1),score),origFeature=features(origCurrent,origPrevious);
    const mutated=draws.map((x,j)=>j>=i?{d:x.d,n:[...x.n].reverse()}:{d:x.d,n:[...x.n]});
    const mutCurrent=top20(mutated.slice(0,i),score),mutPrevious=top20(mutated.slice(0,i-1),score),mutFeature=features(mutCurrent,mutPrevious);
    future.push(origCurrent.join(",")===mutCurrent.join(",")&&origPrevious.join(",")===mutPrevious.join(",")&&JSON.stringify(origFeature)===JSON.stringify(mutFeature));
  }
  const seenOverlap={LOW:0,MID:0,HIGH:0},seenJoint={};
  let priorCountsOK=true,maxNorm=0,maxDisp=0;
  for(const r of rows){
    const key=r.joint_state;
    if(r.prior_overlap_n!==seenOverlap[r.overlap_state]||r.prior_joint_n!==(seenJoint[key]||0))priorCountsOK=false;
    seenOverlap[r.overlap_state]++;
    seenJoint[key]=(seenJoint[key]||0)+1;
    maxNorm=Math.max(maxNorm,Math.abs(r.p1_sum-1),Math.abs(r.p2_sum-1));
    maxDisp=Math.max(maxDisp,r.mean_rank_displacement);
  }
  const current=top20(draws,score),previous=top20(draws.slice(0,-1),score),freezeFeature=features(current,previous);
  const f1=conditional(Q0,a.overlapCounts[freezeFeature.overlapState]);
  const f2=conditional(f1.p,a.jointCounts[freezeFeature.key]||newCounts());
  const nextDate=(d)=>{const x=new Date(d+"T12:00:00Z");x.setUTCDate(x.getUTCDate()+1);return x.toISOString().slice(0,10);};
  const freeze={
    schema_version:"1.0",experiment_id:"Q121",status:"FROZEN_PENDING",
    target_date:nextDate(draws.at(-1).d),history_cutoff:draws.at(-1).d,
    freeze_reference_commit:commitFor("scripts/sonar_q121_rank_weighted_turnover.mjs"),
    freeze_reference_commit_time_utc:commitTimeFor("scripts/sonar_q121_rank_weighted_turnover.mjs"),
    note:"Research-only hit-count calibration; not a Q60 paired forecast and not a production ticket.",
    app_engine_top20_ranked:current,previous_app_engine_top20_ranked:previous,
    overlap:freezeFeature.overlap,overlap_state:freezeFeature.overlapState,
    mean_rank_displacement:freezeFeature.displacement,rank_state:freezeFeature.rankState,joint_state:freezeFeature.key,
    prior_overlap_targets:f1.p? a.overlapCounts[freezeFeature.overlapState].n:0,
    prior_joint_targets:(a.jointCounts[freezeFeature.key]||newCounts()).n,
    probability_hit_count_M0:Q0,probability_hit_count_M1:f1.p,probability_hit_count_M2:f2.p,
    expected_top20_hits:{M0:sum(Q0.map((p,k)=>p*k)),M1:sum(f1.p.map((p,k)=>p*k)),M2:sum(f2.p.map((p,k)=>p*k))},
    normalization_error:Math.max(f1.error,f2.error)
  };
  const appTop20Matches=Array.isArray(active.current_frozen_forecast?.top20_ranked)&&active.current_frozen_forecast.top20_ranked.join(",")===current.join(",");
  const checks=[
    ["archive_rows_3404",draws.length===3404],
    ["archive_cutoff_2026_11_10",draws.at(-1).d==="2026-11-10"],
    ["canonical_dates_unique_chronological",new Set(draws.map(x=>x.d)).size===draws.length&&draws.every((x,i)=>i===0||x.d>draws[i-1].d)],
    ["all_draws_five_sorted_distinct_1_40",draws.every(x=>x.n.length===5&&new Set(x.n).size===5&&x.n.every((z,i)=>Number.isInteger(z)&&z>=1&&z<=40&&(i===0||z>=x.n[i-1])))],
    ["archive_app_scorer_blob_sha_pinned",dataSha===protocol.source.archive_git_blob_sha1&&sourceSha===protocol.source.scorer_git_blob_sha1&&appSha===protocol.source.app_data_git_blob_sha1],
    ["app_data_matches_canonical_csv",appOK],
    ["active_engine_current_top20_matches_exact_committed_scorer",appTop20Matches],
    ["target_count_3203",n===3203],
    ["chronological_split_1922_641_640",d===1922&&v===641&&o===640],
    ["current_and_previous_forecasts_strict_prior",rows.every(r=>r.previous_forecast_cutoff<r.history_cutoff&&r.history_cutoff<r.date)],
    ["prior_overlap_and_joint_counts_exclude_current_target",priorCountsOK],
    ["rank_displacement_in_unit_interval",rows.every(r=>Number.isFinite(r.mean_rank_displacement)&&r.mean_rank_displacement>=0&&r.mean_rank_displacement<=1)&&maxDisp<=1],
    ["all_probability_vectors_normalized",maxNorm<1e-12],
    ["deterministic_full_replay",replay],
    ["future_suffix_invariance_9_of_9",future.every(Boolean)],
    ["all_hit_counts_in_0_5",rows.every(r=>r.hits>=0&&r.hits<=5)],
    ["freeze_target_is_next_calendar_day",freeze.target_date==="2026-11-11"&&freeze.history_cutoff==="2026-11-10"],
    ["freeze_top20_matches_active_engine",current.join(",")===active.current_frozen_forecast.top20_ranked.join(",")],
    ["freeze_probabilities_normalized",close(sum(f1.p),1,1e-12)&&close(sum(f2.p),1,1e-12)]
  ];
  const protocolCommit=commitFor("reports/sequence_agent/q121_rank_weighted_turnover_protocol_2026-11-11.json");
  const protocolCommitTime=commitTimeFor("reports/sequence_agent/q121_rank_weighted_turnover_protocol_2026-11-11.json");
  const report=canonicalize({
    schema_version:"1.0",experiment_id:"Q121",title:"Rank-weighted forecast turnover conditional on Top20 set overlap",
    status:"COMPLETED_EXPLORATORY_NO_PROMOTION",decision,
    source:{repository:"jamesnuvola/vincicasa-lab",base_commit:"04fed58ab8a4226da3cd2bc2a495a12095941355",archive_path:"data/storico_daily.csv",archive_blob_sha1:dataSha,app_data_blob_sha1:appSha,scorer_path:"src/VinciCasaLab.jsx",scorer_blob_sha1:sourceSha,draws:draws.length,first_date:draws[0].d,last_date:draws.at(-1).d},
    preregistration:{path:"reports/sequence_agent/q121_rank_weighted_turnover_protocol_2026-11-11.json",commit:protocolCommit,commit_time_utc:protocolCommitTime},
    hypothesis:protocol.hypothesis,
    method:{M0:"exact Hypergeometric(40,20,5)",M1:"Q117 overlap-only prequential model, shrinkage 200",M2:"hierarchical conditional rank-displacement model, shrinkage 200",overlap_states:protocol.estimand.overlap_states,rank_states:protocol.estimand.displacement_states,selection:"No parameter tuning; thresholds and shrinkage fixed in preregistration.",update_order:"Score first, then update prior-only state counts.",metrics:["multiclass Brier","realized hit-count log-loss"]},
    walk_forward:{warmup:MIN_HISTORY,targets:n,first_target:rows[0].date,last_target:rows.at(-1).date,splits:{discovery:d,validation:v,blind_oos:o},strict_prior:true},
    segments,blind_inference:{family_size:4,adjustment:"Holm",tests},
    support:{overlap_states:a.overlapCounts,joint_states:a.jointCounts,max_probability_normalization_error:maxNormError},
    replay:{identical:replay,ledger_rows:rows.length,future_suffix_invariance:future,passed_future_tests:future.filter(Boolean).length,total_future_tests:future.length},
    decision_rule:protocol.decision_rule,
    limitations:[
      "Historical Blind OOS is not a virgin holdout after the extensive prior SONAR experiment family.",
      "M1 reproduces the Q117 overlap-state model; Q121 tests only whether rank displacement adds information conditional on overlap.",
      "Fixed displacement thresholds are preregistered and not optimized; sparse joint states may be heavily shrunk.",
      "Holm covers the four Q121 primary endpoints, not the full Q00-Q121 research family.",
      "The model predicts Top20 hit-count probabilities only; it does not establish predictability of a specific five-number draw.",
      "No production scorer, Q60 record or existing forecast freeze is modified."
    ],
    next_action:"Wait for official publication of contest 315; evaluate existing frozen forecasts without retuning; continue Q60 append-only and do not reconstruct missing freezes."
  });
  const validation={experiment_id:"Q121",protocol_commit:protocolCommit,checks,future_tests:future,passed:checks.filter(x=>x[1]).length,total:checks.length,max_probability_normalization_error:maxNorm,deterministic_replay_identical:replay};
  const checkpoint=[
    "# Q121 checkpoint — rank-weighted forecast turnover",
    "",
    "- Protocol committed before calculation; protocol commit: "+protocolCommit+" ("+protocolCommitTime+").",
    "- Source main commit 04fed58ab8a4226da3cd2bc2a495a12095941355; archive blob "+dataSha+"; "+draws.length+" draws through "+draws.at(-1).d+".",
    "- Exact APP scorer blob "+sourceSha+"; app data blob "+appSha+"; APP data row-by-row matches canonical archive: "+appOK+".",
    "- Walk-forward: "+n+" strict-prior targets; Discovery / Validation / historical Blind OOS = "+d+" / "+v+" / "+o+".",
    "- M2 adds fixed rank-displacement bins conditional on the Q117 overlap state; shrinkage 200; no tuning.",
    "- Blind OOS M2 vs M1 Brier gain "+segments.blind_oos.brier_gain_m2_vs_m1+"; log-loss gain "+segments.blind_oos.logloss_gain_m2_vs_m1+".",
    "- Blind OOS M2 vs M0 Brier gain "+segments.blind_oos.brier_gain_m2_vs_m0+"; log-loss gain "+segments.blind_oos.logloss_gain_m2_vs_m0+".",
    "- Holm family size 4; "+validation.passed+"/"+validation.total+" checks; future-suffix invariance "+future.filter(Boolean).length+"/9; deterministic replay "+replay+".",
    "- Separate Q121-only 2026-11-11 hit-count freeze; not a Q60 pair.",
    "- Limitations: historical Blind OOS is not virgin; Q121 Holm does not cover Q00-Q121; rank displacement is a calibration diagnostic, not a lottery prediction.",
    "- Next action: evaluate only after official contest 315 publication; no retuning; continue Q60 append-only.",
    ""
  ].join("\n");
  const outputs=[
    [P.ledger,csv(rows)],
    [P.report,JSON.stringify(report,null,2)+"\n"],
    [P.validation,JSON.stringify(validation,null,2)+"\n"],
    [P.checkpoint,checkpoint],
    [path.join(DIR,"q121_rank_weighted_turnover_prospective_freeze_2026-11-11.json"),JSON.stringify(canonicalize(freeze),null,2)+"\n"]
  ];
  const manifestItems=[
    ["protocol",P.protocol],["runner",P.runner],["workflow",P.workflow],
    ["ledger",P.ledger],["report",P.report],["validation",P.validation],["checkpoint",P.checkpoint],
    ["prospective_freeze",path.join(DIR,"q121_rank_weighted_turnover_prospective_freeze_2026-11-11.json")]
  ];
  const manifest={schema_version:"1.0",experiment_id:"Q121",generated_from_commit:commitFor("scripts/sonar_q121_rank_weighted_turnover.mjs"),files:manifestItems.map(([role,p])=>({role,path:path.relative(ROOT,p).replaceAll(path.sep,"/"),git_blob_sha1:gitBlobSha(fs.readFileSync(p,"utf8")),bytes:Buffer.byteLength(fs.readFileSync(p,"utf8"),"utf8")}))};
  outputs.push([P.manifest,JSON.stringify(manifest,null,2)+"\n"]);
  return {outputs,manifest,report,validation,freeze};
}
function main(){
  const mode=process.argv.includes("--verify")?"verify":process.argv.includes("--write")?"write":null;
  if(!mode)fail("pass --write or --verify");
  const x=expectedOutputs();
  if(mode==="write"){
    for(const [p,c] of x.outputs)fs.writeFileSync(p,c,"utf8");
  }else{
    for(const [p,c] of x.outputs){
      if(!fs.existsSync(p))fail("missing persisted artifact "+path.relative(ROOT,p));
      const actual=fs.readFileSync(p,"utf8");
      if(actual!==c){let i=0;while(i<actual.length&&i<c.length&&actual[i]===c[i])i++;fail("artifact mismatch "+path.relative(ROOT,p)+" expected_bytes="+Buffer.byteLength(c)+" actual_bytes="+Buffer.byteLength(actual)+" first_diff="+i);}
    }
    const manifest=JSON.parse(fs.readFileSync(P.manifest,"utf8"));
    for(const f of manifest.files){
      const p=path.join(ROOT,f.path),actual=fs.readFileSync(p,"utf8");
      if(gitBlobSha(actual)!==f.git_blob_sha1||Buffer.byteLength(actual,"utf8")!==f.bytes)fail("manifest mismatch "+f.path);
    }
  }
  const s=x.report.segments.blind_oos;
  console.log(JSON.stringify({
    experiment_id:"Q121",mode,targets:x.report.walk_forward.targets,
    splits:x.report.walk_forward.splits,
    blind_oos:{brier_gain_m2_vs_m1:s.brier_gain_m2_vs_m1,logloss_gain_m2_vs_m1:s.logloss_gain_m2_vs_m1,brier_gain_m2_vs_m0:s.brier_gain_m2_vs_m0,logloss_gain_m2_vs_m0:s.logloss_gain_m2_vs_m0},
    decision:x.report.decision,checks:x.validation.passed+"/"+x.validation.total,
    future_suffix_tests:x.validation.future_tests.filter(Boolean).length+"/9",
    manifest_files:x.manifest.files.length
  },null,2));
}
main();
