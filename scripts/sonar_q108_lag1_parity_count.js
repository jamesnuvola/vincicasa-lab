#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "reports", "sequence_agent");
const CSV_PATH = path.join(ROOT, "data", "storico_daily.csv");
const PROTOCOL_PATH = path.join(OUT, "q108_lag1_parity_count_protocol_2026-11-11.json");
const REPORT_PATH = path.join(OUT, "q108_lag1_parity_count_report_2026-11-11.json");
const VALIDATION_PATH = path.join(OUT, "q108_lag1_parity_count_validation_2026-11-11.json");
const LEDGER_PATH = path.join(OUT, "q108_lag1_parity_count_target_ledger_2026-11-11.csv");
const CHECKPOINT_PATH = path.join(OUT, "q108_lag1_parity_count_checkpoint_2026-11-11.md");
const MANIFEST_PATH = path.join(OUT, "q108_lag1_parity_count_persistence_manifest_2026-11-11.json");
const PINNED_MAIN = "161273b72804c2b6e815e41f20b90dabfea4fdfa";
const PINNED_ARCHIVE = "40f317e2d0067e061c46ab799d66f777a0e087c0";
const PINNED_PREFIX = "8d3e19f0b417024ba32e576697eac0648d12ab86";
const DRAW_COUNT = 3403;
const FIRST_TARGET = 301;
const ALPHA = 200;
const BLOCK = 20;
const SIGN_REPS = 50000;
const BOOT_REPS = 10000;
const SEED = 20261111;

function assert(ok, message) {
  if (!ok) throw new Error("Q108 BLOCKED: " + message);
}
function round(x) { return Number(x.toFixed(12)); }
function mean(xs) { return xs.reduce((a,b)=>a+b,0)/xs.length; }
function quantile(sorted,q) {
  const p=(sorted.length-1)*q, lo=Math.floor(p), hi=Math.ceil(p);
  return sorted[lo]+(sorted[hi]-sorted[lo])*(p-lo);
}
function rng(seed) {
  let x=(seed>>>0)||1;
  return ()=>{ x^=x<<13; x^=x>>>17; x^=x<<5; return (x>>>0)/4294967296; };
}
function stableJson(x) { return JSON.stringify(x,null,2)+"\n"; }
function choose(n,k) {
  if(k<0||k>n) return 0;
  let v=1;
  for(let i=1;i<=k;i++) v=v*(n-k+i)/i;
  return Math.round(v);
}
const Q0_NUM=[15504,96900,216600,216600,96900,15504];
const Q0_DEN=658008;
const Q0=Q0_NUM.map(x=>x/Q0_DEN);

function parseCsv(text) {
  const lines=text.split(/\r?\n/);
  while(lines.length&&lines[lines.length-1]==="") lines.pop();
  assert(lines[0]==="data,n1,n2,n3,n4,n5","archive header mismatch");
  const rows=[], seen=new Set();
  let previous="";
  for(let i=1;i<lines.length;i++){
    const f=lines[i].split(",");
    assert(f.length===6,"malformed CSV row "+(i+1));
    const date=f[0], nums=f.slice(1).map(Number);
    assert(/^\d{4}-\d{2}-\d{2}$/.test(date),"invalid date at row "+(i+1));
    assert(!seen.has(date),"duplicate date "+date); seen.add(date);
    assert(date>previous,"non-chronological date "+date); previous=date;
    assert(nums.length===5&&nums.every(n=>Number.isInteger(n)&&n>=1&&n<=40),"invalid number at "+date);
    assert(new Set(nums).size===5,"duplicate number at "+date);
    rows.push({date,nums});
  }
  return rows;
}
function gitBlobSha1(text) {
  const bytes=Buffer.from(text,"utf8");
  return crypto.createHash("sha1").update(Buffer.from("blob "+bytes.length+"\0","utf8")).update(bytes).digest("hex");
}
function parityOf(rows) { return rows.map(r=>r.nums.reduce((s,n)=>s+(n%2),0)); }
function blankCounts() { return Array.from({length:6},()=>Array(6).fill(0)); }
function blankTotals() { return Array(6).fill(0); }
function forecast(state,counts,totals) {
  const den=ALPHA+totals[state];
  return Q0.map((p,k)=>(ALPHA*p+counts[state][k])/den);
}
function losses(p,actual) {
  let b=0;
  for(let k=0;k<6;k++){ const y=k===actual?1:0; b+=(p[k]-y)*(p[k]-y); }
  return {brier:b,logloss:-Math.log(p[actual])};
}
function forecastAt(parity,t) {
  const c=blankCounts(), n=blankTotals();
  for(let j=1;j<t;j++){ c[parity[j-1]][parity[j]]++; n[parity[j-1]]++; }
  return forecast(parity[t-1],c,n);
}
function signFlip(values,reps,blockLength,seed) {
  const sums=[];
  for(let i=0;i<values.length;i+=blockLength) sums.push(values.slice(i,i+blockLength).reduce((a,b)=>a+b,0));
  const observed=mean(values), random=rng(seed);
  let ge=0;
  for(let r=0;r<reps;r++){
    let s=0;
    for(const v of sums) s+=(random()<0.5?-1:1)*v;
    if(s>=observed*values.length) ge++;
  }
  const p=(ge+1)/(reps+1);
  return {n:values.length,blocks:sums.length,observed_mean:round(observed),replicates:reps,block_length:blockLength,extreme:ge,p_one_sided:round(p),monte_carlo_se:round(Math.sqrt(p*(1-p)/reps))};
}
function blockBootstrap(values,reps,blockLength,seed) {
  const random=rng(seed), n=values.length, means=[], blocks=Math.ceil(n/blockLength);
  for(let r=0;r<reps;r++){
    let sum=0,count=0;
    for(let b=0;b<blocks;b++){
      const start=Math.floor(random()*n);
      for(let j=0;j<blockLength&&count<n;j++){ sum+=values[(start+j)%n]; count++; }
    }
    means.push(sum/n);
  }
  means.sort((a,b)=>a-b);
  return {replicates:reps,block_length:blockLength,ci95:{lower:round(quantile(means,0.025)),upper:round(quantile(means,0.975))}};
}
function holm(ps) {
  const order=ps.map((p,i)=>({p,i})).sort((a,b)=>a.p-b.p);
  const out=Array(ps.length); let running=0,m=ps.length;
  for(let j=0;j<m;j++){ running=Math.max(running,Math.min(1,(m-j)*order[j].p)); out[order[j].i]=round(running); }
  return out;
}
function csvQuote(v) {
  const s=String(v);
  return /[",\r\n]/.test(s)?'"'+s.replace(/"/g,'""')+'"':s;
}
function splitName(i,counts) {
  if(i<counts.discovery) return "discovery";
  if(i<counts.discovery+counts.validation) return "validation";
  return "historical_blind_oos";
}
function summarize(rows) {
  const out={targets:rows.length,first_target:rows[0].target_date,last_target:rows[rows.length-1].target_date};
  for(const key of ["m0_brier","m1_brier","brier_gain","m0_logloss","m1_logloss","logloss_gain"]){
    out[key]=round(mean(rows.map(r=>r[key])));
  }
  out.mean_previous_odd_count=round(mean(rows.map(r=>r.previous_odd_count)));
  out.mean_state_support=round(mean(rows.map(r=>r.state_support)));
  out.actual_odd_count_distribution=Array(6).fill(0);
  for(const r of rows) out.actual_odd_count_distribution[r.actual_odd_count]++;
  return out;
}
function runAnalysis(csvText,sourceInfo) {
  const all=parseCsv(csvText);
  assert(all.length===3404,"expected 3404 archive rows including one unverified append, got "+all.length);
  assert(all[0].date==="2017-07-17","unexpected first date");
  assert(all[3402].date==="2026-11-09","verified analysis prefix cutoff mismatch");
  assert(all[3403].date==="2026-11-10","unexpected appended row date");
  assert(all[3403].nums.join(",")==="1,7,11,22,25","unexpected appended row content");
  const rows=all.slice(0,DRAW_COUNT);
  const parity=parityOf(rows);
  const counts=blankCounts(), totals=blankTotals();
  for(let j=1;j<=300;j++){ counts[parity[j-1]][parity[j]]++; totals[parity[j-1]]++; }
  const ledger=[];
  for(let t=FIRST_TARGET;t<DRAW_COUNT;t++){
    const state=parity[t-1], p1=forecast(state,counts,totals), p0=Q0.slice(), actual=parity[t];
    const l0=losses(p0,actual), l1=losses(p1,actual);
    assert(totals.reduce((a,b)=>a+b,0)===t-1,"training transition count mismatch at target "+t);
    const sum=p1.reduce((a,b)=>a+b,0);
    assert(p1.every(x=>Number.isFinite(x)&&x>0)&&Math.abs(sum-1)<1e-12,"invalid forecast probabilities at "+rows[t].date);
    ledger.push({
      target_index:t,target_date:rows[t].date,cutoff_date:rows[t-1].date,
      prior_transition_count:t-1,previous_odd_count:state,actual_odd_count:actual,
      state_support:totals[state],m0_brier:l0.brier,m1_brier:l1.brier,brier_gain:l0.brier-l1.brier,
      m0_logloss:l0.logloss,m1_logloss:l1.logloss,logloss_gain:l0.logloss-l1.logloss,
      m0_probabilities:p0.map(round),m1_probabilities:p1.map(round)
    });
    counts[state][actual]++; totals[state]++;
  }
  const splitCounts={discovery:1861,validation:620,historical_blind_oos:621};
  assert(ledger.length===3102,"target count mismatch");
  const split={discovery:[],validation:[],historical_blind_oos:[]};
  ledger.forEach((r,i)=>split[splitName(i,splitCounts)].push(r));
  const metrics={};
  for(const name of Object.keys(split)) metrics[name]=summarize(split[name]);
  const blind=split.historical_blind_oos;
  const brierDiff=blind.map(r=>r.brier_gain), logDiff=blind.map(r=>r.logloss_gain);
  const brierTest=signFlip(brierDiff,SIGN_REPS,BLOCK,SEED+1);
  const logTest=signFlip(logDiff,SIGN_REPS,BLOCK,SEED+2);
  const brierBoot=blockBootstrap(brierDiff,BOOT_REPS,BLOCK,SEED+3);
  const logBoot=blockBootstrap(logDiff,BOOT_REPS,BLOCK,SEED+4);
  const adjusted=holm([brierTest.p_one_sided,logTest.p_one_sided]);
  const blindInference={
    method:"One-sided block sign-flip of contiguous paired loss-gain blocks; circular moving-block bootstrap for 95% confidence intervals.",
    block_length:BLOCK,sign_flip_replicates:SIGN_REPS,bootstrap_replicates:BOOT_REPS,seed:SEED,holm_family_size:2,
    endpoints:[
      {name:"m1_vs_m0_brier_gain",...brierTest,bootstrap:brierBoot,p_holm:adjusted[0]},
      {name:"m1_vs_m0_logloss_gain",...logTest,bootstrap:logBoot,p_holm:adjusted[1]}
    ]
  };
  const supports=ledger.map(r=>r.state_support).sort((a,b)=>a-b);
  const stateSupport={min:supports[0],median:supports[Math.floor((supports.length-1)/2)],max:supports[supports.length-1]};
  const report={
    experiment_id:"Q108",title:"Lag-1 parity-count transition memory",
    decision:"NO_LAG1_PARITY_INCREMENTAL_LIFT_DEMONSTRATED",
    source:sourceInfo,
    definition:{
      feature:"A_t = number of odd values in draw D_t",target:"A_t",state:"A_(t-1)",state_space:[0,1,2,3,4,5],
      exact_null:{distribution:"Hypergeometric(N=40,K=20 odd,n=5)",numerators:Q0_NUM,denominator:Q0_DEN,probabilities:Q0.map(round),expected_odd_count:2.5}
    },
    models:{M0:"Exact Hypergeometric(40,20,5) PMF.",M1:"One-step categorical shrinkage toward M0, alpha=200.",alpha:ALPHA,parameter_selection:"None; fixed before scoring."},
    walk_forward:{
      draws:DRAW_COUNT,warmup_transition_pairs:300,first_target_index_zero_based:FIRST_TARGET,targets:ledger.length,
      split_rule:"Chronological 60%/20%/20%, fixed before scoring.",
      splits:Object.fromEntries(Object.entries(split).map(([k,v])=>[k,{targets:v.length,first_target:v[0].target_date,last_target:v[v.length-1].target_date}]))
    },
    metrics,
    blind_inference:blindInference,
    diagnostics:{prior_state_support:stateSupport,transition_state_counts:totals.slice(),observed_odd_count_distribution:parity.reduce((a,k)=>(a[k]++,a),Array(6).fill(0))},
    interpretation:{
      primary:"M1 tests whether the previous draw's odd-count adds predictive information about the next draw's odd-count beyond the exact combinatorial marginal.",
      caveat:"The historical Blind OOS is not a virgin holdout: many earlier SONAR experiments examined related draw-structure features. Holm correction is within Q108 only, not across the entire historical research family.",
      scope:"This is a structural diagnostic; it does not directly forecast an exact 5-number combination."
    },
    integrity:{exact_null_numerator_sum:Q0_NUM.reduce((a,b)=>a+b,0),exact_null_denominator:Q0_DEN,maximum_probability_normalization_error:round(Math.max(...ledger.map(r=>Math.abs(r.m1_probabilities.reduce((a,b)=>a+b,0)-1))))}
  };
  const checks=[];
  const add=(name,ok,detail)=>checks.push({name,status:ok?"PASS":"FAIL",detail});
  add("archive_schema_chronology_and_draw_validity",all.length===3404&&rows.every((r,i)=>i===0||r.date>rows[i-1].date),"3,404 chronological valid rows; first 3,403 used.");
  add("pinned_source_blobs",sourceInfo.current_archive_blob_sha1===PINNED_ARCHIVE&&sourceInfo.analysis_prefix_blob_sha1===PINNED_PREFIX&&sourceInfo.pinned_main_commit===PINNED_MAIN,"Current archive and 3,403-row analysis prefix match the preregistered Git blobs.");
  add("unverified_append_excluded",rows.length===3403&&rows[rows.length-1].date==="2026-11-09"&&all[3403].date==="2026-11-10","2026-11-10 row is present in source but excluded from all forecasts and scores.");
  add("exact_hypergeometric_null",Q0_NUM.reduce((a,b)=>a+b,0)===Q0_DEN&&Math.abs(Q0.reduce((a,b)=>a+b,0)-1)<1e-14,"Exact parity-count numerators sum to 658,008.");
  add("walk_forward_counts_and_splits",ledger.length===3102&&split.discovery.length===1861&&split.validation.length===620&&split.historical_blind_oos.length===621,"3,102 targets split 1,861/620/621.");
  add("strict_prior_cutoffs",ledger.every(r=>r.target_date>r.cutoff_date&&r.prior_transition_count===r.target_index-1),"Every target uses exactly t-1 transitions strictly before its draw index.");
  add("forecast_probability_normalization",ledger.every(r=>r.m1_probabilities.every(x=>Number.isFinite(x)&&x>0)&&Math.abs(r.m1_probabilities.reduce((a,b)=>a+b,0)-1)<1e-10),"All M0/M1 probabilities finite, positive and normalized.");
  const cutoffs=[301,500,900,1200,1600,2000,2400,2800,3300].filter(t=>t<DRAW_COUNT);
  const futureInvariant=cutoffs.every(t=>{
    const p=forecastAt(parity,t);
    const changed=parity.slice(); for(let j=t;j<changed.length;j++) changed[j]=(changed[j]+1)%6;
    const p2=forecastAt(changed,t);
    return p.every((v,i)=>v===p2[i]);
  });
  add("future_mutation_invariance_9_cutoffs",futureInvariant,"Mutating target and all future parity states leaves the prior-only forecast unchanged at nine cutoffs.");
  const synC=blankCounts(),synN=blankTotals();
  for(let i=0;i<40;i++){synC[4][0]++;synN[4]++;}
  const syn=forecast(4,synC,synN);
  add("synthetic_state_sensitivity",syn.some((v,i)=>Math.abs(v-Q0[i])>1e-8),"A synthetic state with distinct outcomes changes M1 relative to M0.");
  const empty=forecast(5,blankCounts(),blankTotals());
  add("synthetic_no_support_fallback",empty.every((v,i)=>v===Q0[i]),"A state with no prior support falls back exactly to M0.");
  const replay1=JSON.stringify({b:signFlip(brierDiff,SIGN_REPS,BLOCK,SEED+1),l:signFlip(logDiff,SIGN_REPS,BLOCK,SEED+2),bb:blockBootstrap(brierDiff,BOOT_REPS,BLOCK,SEED+3),lb:blockBootstrap(logDiff,BOOT_REPS,BLOCK,SEED+4)});
  const replay2=JSON.stringify({b:signFlip(brierDiff,SIGN_REPS,BLOCK,SEED+1),l:signFlip(logDiff,SIGN_REPS,BLOCK,SEED+2),bb:blockBootstrap(brierDiff,BOOT_REPS,BLOCK,SEED+3),lb:blockBootstrap(logDiff,BOOT_REPS,BLOCK,SEED+4)});
  add("deterministic_inference_replay",replay1===replay2,"Fixed-seed sign-flip and circular block-bootstrap reproduce exactly.");
  add("ledger_report_reconciliation",ledger.length===Object.values(metrics).reduce((s,x)=>s+x.targets,0)&&metrics.historical_blind_oos.targets===621,"Ledger target count equals report split totals.");
  assert(checks.length===12,"acceptance check count mismatch");
  assert(checks.every(c=>c.status==="PASS"),"one or more acceptance checks failed");
  const validation={experiment_id:"Q108",status:"PASS",checks_passed:checks.filter(c=>c.status==="PASS").length,checks_total:checks.length,checks,inference_constants:{alpha:ALPHA,block_length:BLOCK,sign_flip_replicates:SIGN_REPS,circular_block_bootstrap_replicates:BOOT_REPS,seed:SEED,holm_family_size:2}};
  const header=["target_index","target_date","cutoff_date","prior_transition_count","previous_odd_count","actual_odd_count","state_support","m0_brier","m1_brier","brier_gain","m0_logloss","m1_logloss","logloss_gain","m0_probabilities","m1_probabilities"];
  const csv=[header.join(",")];
  for(const r of ledger){
    const vals=[r.target_index,r.target_date,r.cutoff_date,r.prior_transition_count,r.previous_odd_count,r.actual_odd_count,r.state_support,r.m0_brier,r.m1_brier,r.brier_gain,r.m0_logloss,r.m1_logloss,r.logloss_gain,JSON.stringify(r.m0_probabilities),JSON.stringify(r.m1_probabilities)];
    csv.push(vals.map(csvQuote).join(","));
  }
  const ledgerText=csv.join("\n")+"\n";
  const checkpoint=[
    "# Q108 — lag-1 parity-count checkpoint (2026-11-11)","",
    "- Status: NO_LAG1_PARITY_INCREMENTAL_LIFT_DEMONSTRATED.",
    "- Protocol preregistered before scoring; alpha=200 fixed; no tuning.",
    "- Source main commit: "+PINNED_MAIN+".",
    "- Analysis prefix: 3,403 draws through 2026-11-09; the 2026-11-10 row in main is excluded because the official archive still lists contest 314 as pending.",
    "- Walk-forward: 3,102 targets; Discovery/Validation/historical Blind OOS = 1,861/620/621.",
    "- Primary comparison: one-step parity-state M1 versus exact Hypergeometric(40,20,5) M0.",
    "- Historical Blind OOS is not virgin; within-Q108 Holm correction covers two preregistered endpoints only.",
    "- Validation: 12/12 PASS.",
    "- No production scorer, canonical data, Q60, H101/H102 or existing freeze was modified.",
    "- Next action: continue append-only prospective evaluation; reconcile contest 314 only after official publication; do not reconstruct missing freezes.",
    ""
  ].join("\n");
  return {report,validation,ledgerText,checkpoint};
}

async function main() {
  const csvText=fs.readFileSync(CSV_PATH,"utf8");
  const protocolText=fs.readFileSync(PROTOCOL_PATH,"utf8");
  const protocol=JSON.parse(protocolText);
  assert(protocol.experiment_id==="Q108"&&protocol.status==="PREREGISTERED_BEFORE_SCORING","protocol missing or not preregistered");
  const lines=csvText.split(/\r?\n/); while(lines.length&&lines[lines.length-1]==="") lines.pop();
  const prefixText=lines.slice(0,DRAW_COUNT+1).join("\r\n")+"\r\n";
  const sourceInfo={
    pinned_main_commit:PINNED_MAIN,
    current_archive_blob_sha1:gitBlobSha1(csvText),
    analysis_prefix_blob_sha1:gitBlobSha1(prefixText),
    archive_rows:lines.length-1,draws_used:DRAW_COUNT,
    first_date:"2017-07-17",last_date:"2026-11-09",
    excluded_appended_row:{date:"2026-11-10",numbers:[1,7,11,22,25],reason:"Official archive pending; excluded."}
  };
  assert(sourceInfo.current_archive_blob_sha1===PINNED_ARCHIVE,"current archive blob changed");
  assert(sourceInfo.analysis_prefix_blob_sha1===PINNED_PREFIX,"analysis prefix blob changed");
  const out=runAnalysis(csvText,sourceInfo);
  const outputs={
    [REPORT_PATH]:JSON.stringify(out.report,null,2)+"\n",
    [VALIDATION_PATH]:JSON.stringify(out.validation,null,2)+"\n",
    [LEDGER_PATH]:out.ledgerText,
    [CHECKPOINT_PATH]:out.checkpoint
  };
  if(process.argv.includes("--check")){
    for(const [p,expected] of Object.entries(outputs)){
      assert(fs.readFileSync(p,"utf8")===expected,"persisted artifact mismatch: "+path.basename(p));
    }
    const manifest=JSON.parse(fs.readFileSync(MANIFEST_PATH,"utf8"));
    for(const [p,expected] of Object.entries(outputs)){
      assert(manifest.files[path.basename(p)].git_blob_sha1===gitBlobSha1(expected),"manifest Git blob hash mismatch: "+path.basename(p));
    }
    console.log(JSON.stringify({experiment_id:"Q108",status:"PASS",targets:out.report.walk_forward.targets,checks:out.validation.checks_passed,artifact_replay:"BYTE_IDENTICAL"}));
    return;
  }
  for(const [p,content] of Object.entries(outputs)) fs.writeFileSync(p,content);
  const tracked=[
    [PROTOCOL_PATH,protocolText],
    [path.join(ROOT,"scripts","sonar_q108_lag1_parity_count.js"),fs.readFileSync(path.join(ROOT,"scripts","sonar_q108_lag1_parity_count.js"),"utf8")],
    ...Object.entries(outputs).map(([p,c])=>[p,c])
  ];
  const files={};
  for(const [p,content] of tracked){
    const name=path.basename(p);
    files[name]={sha256:crypto.createHash("sha256").update(content).digest("hex"),git_blob_sha1:gitBlobSha1(content),bytes:Buffer.byteLength(content)};
  }
  const manifest={experiment_id:"Q108",generated_at_utc:"2026-11-11T01:42:00Z",source_main_commit:PINNED_MAIN,files,verification:"Generated by runner; CI --check recomputes report, validation, ledger and checkpoint and compares byte-for-byte."};
  fs.writeFileSync(MANIFEST_PATH,JSON.stringify(manifest,null,2)+"\n");
  console.log(JSON.stringify({experiment_id:"Q108",decision:out.report.decision,targets:out.report.walk_forward.targets,blind:out.report.metrics.historical_blind_oos,inference:out.report.blind_inference,checks:out.validation.checks_passed,ledger_rows:out.ledgerText.split("\n").length-2}));
}

main().catch(e=>{console.error(e.stack||String(e));process.exit(1);});
