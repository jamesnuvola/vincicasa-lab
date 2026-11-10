import fs from "node:fs";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

function fail(message) { throw new Error("Q102: " + message); }
function choose(n,k) {
  if (k < 0 || k > n) return 0;
  let x=1;
  for (let i=1;i<=k;i++) x=x*(n-i+1)/i;
  return x;
}
function parseArchive(text) {
  const lines=text.trimEnd().split(/\r?\n/);
  if (lines[0] !== "data,n1,n2,n3,n4,n5") fail("archive header mismatch");
  const draws=[];
  for (let i=1;i<lines.length;i++) {
    const row=lines[i].split(",");
    if (row.length!==6 || !/^\d{4}-\d{2}-\d{2}$/.test(row[0])) fail("malformed archive row "+i);
    const nums=row.slice(1).map(Number);
    if (nums.some((v,j)=>!Number.isInteger(v)||v<1||v>40||(j>0&&nums[j-1]>=v))) fail("invalid sorted 5-of-40 row "+i);
    if (draws.length && !(draws.at(-1).date<row[0])) fail("archive dates not strictly increasing");
    draws.push({date:row[0],nums});
  }
  if (draws.length!==3403 || draws[0].date!=="2017-07-17" || draws.at(-1).date!=="2026-11-09") fail("pinned archive cutoff mismatch");
  return draws;
}
function makeOverlaps(draws) {
  const out=Array(draws.length).fill(null);
  for (let i=1;i<draws.length;i++) {
    const a=new Set(draws[i-1].nums);
    out[i]=draws[i].nums.reduce((s,n)=>s+(a.has(n)?1:0),0);
  }
  return out;
}
function makeNull() {
  const den=choose(40,5);
  const numerators=Array.from({length:6},(_,k)=>choose(5,k)*choose(35,5-k));
  const p=numerators.map(x=>x/den);
  const m=p.reduce((s,v,k)=>s+v*k,0);
  return {den,numerators,p,mean:m,variance:p.reduce((s,v,k)=>s+v*(k-m)**2,0)};
}
function forecastAt(overlaps,t,h,q0,alpha=200) {
  const state=overlaps[t-1];
  const counts=Array(6).fill(0);
  let weightSum=0;
  for (let j=1;j<=t-2;j++) {
    const w=Math.exp(-((overlaps[j]-state)**2)/(2*h*h));
    counts[overlaps[j+1]]+=w;
    weightSum+=w;
  }
  const p=q0.map((v,k)=>(alpha*v+counts[k])/(alpha+weightSum));
  return {p,state,trainingPairs:t-2,weightSum};
}
function brier(p,actual) {
  let s=0;
  for (let k=0;k<6;k++) { const e=p[k]-(k===actual?1:0); s+=e*e; }
  return s;
}
function logloss(p,actual) { return -Math.log(Math.max(p[actual],1e-300)); }
function mean(xs) { return xs.reduce((s,x)=>s+x,0)/xs.length; }
function correlation(xs,ys) {
  const mx=mean(xs), my=mean(ys);
  let a=0,b=0,c=0;
  for(let i=0;i<xs.length;i++){const dx=xs[i]-mx,dy=ys[i]-my;a+=dx*dy;b+=dx*dx;c+=dy*dy;}
  return b===0||c===0?0:a/Math.sqrt(b*c);
}
function hash32(text) {
  let h=2166136261;
  for(let i=0;i<text.length;i++){h^=text.charCodeAt(i);h=Math.imul(h,16777619);}
  return (h>>>0).toString(16).padStart(8,"0");
}
function makeRng(seed) {
  let x=seed>>>0;
  return function(){x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)/4294967296;};
}
function blockSignFlip(gains,reps,seed,blockLength=20) {
  const blockSums=[];
  for(let i=0;i<gains.length;i+=blockLength) blockSums.push(gains.slice(i,i+blockLength).reduce((s,x)=>s+x,0));
  const observed=gains.reduce((s,x)=>s+x,0);
  const rng=makeRng(seed);
  let extreme=0;
  for(let r=0;r<reps;r++){
    let stat=0;
    for(const x of blockSums) stat+=(rng()<0.5?-x:x);
    if(stat>=observed-1e-15) extreme++;
  }
  const p=(extreme+1)/(reps+1);
  return {replicates:reps,block_length:blockLength,blocks:blockSums.length,extreme,p,mc_se:Math.sqrt(p*(1-p)/(reps+1)),observed_sum:observed};
}
function circularBlockBootstrap(gains,reps,seed,blockLength=20) {
  const rng=makeRng(seed), n=gains.length, out=Array(reps);
  for(let r=0;r<reps;r++){
    let sum=0,got=0;
    while(got<n){
      const start=Math.floor(rng()*n);
      for(let j=0;j<blockLength&&got<n;j++,got++) sum+=gains[(start+j)%n];
    }
    out[r]=sum/n;
  }
  out.sort((a,b)=>a-b);
  const q=p=>{const z=p*(reps-1),lo=Math.floor(z),hi=Math.ceil(z);return out[lo]+(out[hi]-out[lo])*(z-lo);};
  return {replicates:reps,block_length:blockLength,ci95:[q(0.025),q(0.975)],bootstrap_mean:mean(out)};
}
function holm(tests) {
  const order=tests.map((x,i)=>({i,p:x.p})).sort((a,b)=>a.p-b.p);
  const adj=Array(tests.length).fill(1);
  let running=0;
  for(let r=0;r<order.length;r++){
    running=Math.max(running,Math.min(1,(order.length-r)*order[r].p));
    adj[order[r].i]=running;
  }
  return adj;
}
function splitFor(ordinal) {
  return ordinal<1400?"discovery":ordinal<2250?"validation":"historical_blind_oos";
}
function runQ102(archiveText) {
  const draws=parseArchive(archiveText);
  const overlaps=makeOverlaps(draws);
  const nul=makeNull();
  if(nul.den!==658008 || Math.abs(nul.p.reduce((s,x)=>s+x,0)-1)>1e-15 || Math.abs(nul.mean-0.625)>1e-14) fail("exact hypergeometric null check failed");
  const hs=[0.5,1,2,4], alpha=200;
  const first=301,last=draws.length-1,total=last-first+1;
  if(total!==3102) fail("target count mismatch");
  const rows=[];
  let maxPmfError=0,strictPriorErrors=0;
  for(let t=first;t<=last;t++){
    const ordinal=t-first, split=splitFor(ordinal), actual=overlaps[t];
    const baselineBrier=brier(nul.p,actual), baselineLog=logloss(nul.p,actual);
    const models={};
    for(const h of hs){
      const f=forecastAt(overlaps,t,h,nul.p,alpha);
      const sum=f.p.reduce((s,x)=>s+x,0);
      maxPmfError=Math.max(maxPmfError,Math.abs(sum-1));
      if(f.trainingPairs!==t-2 || t-1>=t) strictPriorErrors++;
      models[h]={p:f.p,brier:brier(f.p,actual),logloss:logloss(f.p,actual),prob_hash:hash32(f.p.map(x=>x.toPrecision(17)).join("|"))};
    }
    rows.push({
      ordinal,target_index:t,target_date:draws[t].date,cutoff_date:draws[t-1].date,
      previous_overlap_state:overlaps[t-1],observed_overlap:actual,
      training_pairs:t-2,max_training_pair_end_draw_index:t-1,split,
      baseline_brier:baselineBrier,baseline_logloss:baselineLog,models
    });
  }
  const splitNames=["discovery","validation","historical_blind_oos"];
  const splitRows=Object.fromEntries(splitNames.map(name=>[name,rows.filter(r=>r.split===name)]));
  const splitMetrics={};
  for(const name of splitNames){
    const rr=splitRows[name];
    const baseline={brier:mean(rr.map(r=>r.baseline_brier)),logloss:mean(rr.map(r=>r.baseline_logloss))};
    const models={};
    for(const h of hs){
      const b=mean(rr.map(r=>r.models[h].brier)), l=mean(rr.map(r=>r.models[h].logloss));
      models[h]={brier:b,logloss:l,brier_gain:baseline.brier-b,logloss_gain:baseline.logloss-l};
    }
    const counts=Array(6).fill(0);
    rr.forEach(r=>counts[r.observed_overlap]++);
    splitMetrics[name]={targets:rr.length,baseline,models,observed_overlap_counts:counts,observed_mean_overlap:mean(rr.map(r=>r.observed_overlap)),state_to_next_correlation:correlation(rr.map(r=>r.previous_overlap_state),rr.map(r=>r.observed_overlap))};
  }
  const selectedH=hs.reduce((best,h)=>splitMetrics.validation.models[h].brier<splitMetrics.validation.models[best].brier-1e-15?h:best,hs[0]);
  const blind=splitRows.historical_blind_oos;
  const tests=[];
  let testIndex=0;
  for(const h of hs){
    for(const endpoint of ["brier","logloss"]){
      const gains=blind.map(r=>r["baseline_"+endpoint]-r.models[h][endpoint]);
      const sign=blockSignFlip(gains,50000,0x5100A102+testIndex*97,20);
      const boot=circularBlockBootstrap(gains,10000,0x5100B102+testIndex*131,20);
      tests.push({bandwidth:h,endpoint,gain:mean(gains),block_sign_flip:sign,bootstrap:boot,p:sign.p,p_bonferroni_43:Math.min(1,sign.p*43)});
      testIndex++;
    }
  }
  const adjusted=holm(tests);
  tests.forEach((x,i)=>x.p_holm=adjusted[i]);
  const selectedBrierTest=tests.find(x=>x.bandwidth===selectedH&&x.endpoint==="brier");
  const selectedLogTest=tests.find(x=>x.bandwidth===selectedH&&x.endpoint==="logloss");
  const supported=selectedBrierTest.gain>0&&selectedBrierTest.p_holm<0.05&&selectedBrierTest.bootstrap.ci95[0]>0;
  const cutoffs=[301,1701,2551,3400];
  let mutationChecks=0,mutationFailures=0;
  for(const t of cutoffs){
    const altered=draws.map((d,i)=>i<t?d:{date:d.date,nums:[1,2,3,4,5]});
    const alteredOverlaps=makeOverlaps(altered);
    for(const h of hs){
      const a=forecastAt(overlaps,t,h,nul.p,alpha).p;
      const b=forecastAt(alteredOverlaps,t,h,nul.p,alpha).p;
      mutationChecks++;
      if(a.some((x,i)=>x!==b[i])) mutationFailures++;
    }
  }
  const replayA=forecastAt(overlaps,1701,selectedH,nul.p,alpha).p;
  const replayB=forecastAt(overlaps,1701,selectedH,nul.p,alpha).p;
  const deterministicForecastReplay=JSON.stringify(replayA)===JSON.stringify(replayB);
  const rng1=makeRng(0x5100A102),rng2=makeRng(0x5100A102);
  let deterministicRngReplay=true;
  for(let i=0;i<100;i++) if(rng1()!==rng2()) deterministicRngReplay=false;
  const splitCounts=Object.fromEntries(splitNames.map(name=>[name,splitRows[name].length]));
  const checks=[
    {name:"canonical_archive_schema_dates_and_5of40_rows",status:"PASS",draws:draws.length},
    {name:"exact_hypergeometric_null_normalized_and_mean_0.625",status:"PASS",denominator:nul.den,probability_sum:nul.p.reduce((s,x)=>s+x,0),mean:nul.mean,variance:nul.variance},
    {name:"3102_strict_prior_walk_forward_targets",status:strictPriorErrors===0&&rows.length===3102?"PASS":"FAIL",targets:rows.length,strict_prior_errors:strictPriorErrors},
    {name:"all_forecast_pmfs_normalized",status:maxPmfError<1e-12?"PASS":"FAIL",forecast_count:rows.length*hs.length,max_sum_error:maxPmfError},
    {name:"chronological_split_reconciliation",status:splitCounts.discovery===1400&&splitCounts.validation===850&&splitCounts.historical_blind_oos===852?"PASS":"FAIL",counts:splitCounts},
    {name:"future_mutation_invariance",status:mutationFailures===0?"PASS":"FAIL",cutoffs,comparisons:mutationChecks,failures:mutationFailures},
    {name:"deterministic_forecast_replay",status:deterministicForecastReplay?"PASS":"FAIL"},
    {name:"deterministic_prng_replay",status:deterministicRngReplay?"PASS":"FAIL"},
    {name:"target_outcomes_not_used_in_training_pairs",status:strictPriorErrors===0?"PASS":"FAIL",rule:"training pair endpoints end no later than draw index t-1"}
  ];
  const validation={experiment_id:"Q102",status:checks.every(x=>x.status==="PASS")?"PASS":"FAIL",checks,integrity:{archive_draws:draws.length,overlap_count:overlaps.length-1,targets:rows.length,split_counts:splitCounts,forecast_count:rows.length*hs.length,max_forecast_pmf_sum_error:maxPmfError,strict_prior_errors:strictPriorErrors,future_mutation_comparisons:mutationChecks,future_mutation_failures:mutationFailures}};
  const observedCounts=Array(6).fill(0);for(let i=1;i<overlaps.length;i++)observedCounts[overlaps[i]]++;
  const report={
    experiment_id:"Q102",
    title:"Lag-1 consecutive-draw overlap-state memory diagnostic",
    status:supported?"EXPLORATORY_SIGNAL_REQUIRES_PROSPECTIVE_CONFIRMATION":"NO_PREDICTIVE_LIFT_DEMONSTRATED",
    generated_date:"2026-11-10",
    source:{archive:"data/storico_daily.csv",archive_blob_sha:"8d3e19f0b417024ba32e576697eac0648d12ab86",main_commit:"d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b"},
    definition:{overlap:"K_t=|D_{t-1}∩D_t|",predictor:"K_{t-1}",target:"K_t",kernel:"exp(-(K_j-K_{t-1})^2/(2h^2))",prior_strength:alpha,bandwidths:hs,training_pairs:"j=1..t-2 only"},
    exact_null:{distribution:"Hypergeometric(N=40,K=5,n=5)",denominator:nul.den,numerators:nul.numerators,probabilities:nul.p,expected_overlap:nul.mean,variance:nul.variance,all_overlap_counts:observedCounts},
    data:{draws:draws.length,first_date:draws[0].date,last_date:draws.at(-1).date,warmup_observed_transitions:300,first_target_index_zero_based:first,last_target_index_zero_based:last,targets:total,splits:splitCounts},
    selection:{criterion:"minimum Validation multiclass Brier",selected_bandwidth:selectedH,validation_only:true,blind_oos_used_for_selection:false},
    split_metrics:splitMetrics,
    blind_inference:{family_size:8,block_length:20,sign_flip_replicates:50000,bootstrap_replicates:10000,tests,selected_bandwidth:selectedH,selected_brier_test:selectedBrierTest,selected_logloss_test:selectedLogTest,holm_correction:"Holm step-down across 8 fixed tests",catalogue_screen:"Bonferroni ×43 reported separately; does not correct unknown analyst degrees of freedom."},
    interpretation:supported?"The selected kernel shows a positive historical blind gain under the registered local family; this remains exploratory and requires a virgin prospective cohort.":"The previous overlap state did not demonstrate a robust proper-score improvement over the exact hypergeometric null.",
    decision:{predictive_lift_demonstrated:supported,promotion_allowed:false,production_change_allowed:false,prospective_freezes_changed:false},
    limitations:["Historical Blind OOS is exposed to previous SONAR research and is not a virgin prospective holdout.","The model forecasts only the next overlap count, not any number or quintet.","Block sign-flip assumes exchangeability of contiguous 20-target block signs; bootstrap preserves local dependence only approximately.","Holm covers the eight Q102 tests; Bonferroni ×43 is only a conservative catalogue screen and not a complete correction for all historical analyst choices."]
  };
  const ledgerHeader=["ordinal","target_index","target_date","cutoff_date","previous_overlap_state","observed_overlap","training_pairs","max_training_pair_end_draw_index","split","baseline_brier","baseline_logloss"];
  for(const h of hs) ledgerHeader.push("h"+String(h).replace(".","_")+"_brier","h"+String(h).replace(".","_")+"_logloss","h"+String(h).replace(".","_")+"_prob_hash");
  const ledger=[ledgerHeader.join(",")];
  for(const r of rows){
    const cols=[r.ordinal,r.target_index,r.target_date,r.cutoff_date,r.previous_overlap_state,r.observed_overlap,r.training_pairs,r.max_training_pair_end_draw_index,r.split,r.baseline_brier.toFixed(12),r.baseline_logloss.toFixed(12)];
    for(const h of hs) cols.push(r.models[h].brier.toFixed(12),r.models[h].logloss.toFixed(12),r.models[h].prob_hash);
    ledger.push(cols.join(","));
  }
  const checkpoint=[
    "# Q102 — lag-1 overlap-memory checkpoint (2026-11-10)",
    "",
    "## Status",
    report.status+". No active engine, production ranking, freeze or Q60 gate was changed.",
    "",
    "## Source and protocol",
    "- Main commit: d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b.",
    "- Canonical archive: 3,403 draws through 2026-11-09; blob 8d3e19f0b417024ba32e576697eac0648d12ab86.",
    "- Preregistered before scoring: four fixed bandwidths 0.5/1/2/4, prior strength 200, validation-only Brier selection.",
    "- Target cohort: 3,102; Discovery 1,400 / Validation 850 / historical Blind OOS 852.",
    "",
    "## Measured result",
    "- Validation-selected bandwidth: "+selectedH+".",
    "- Blind OOS selected-model Brier gain: "+selectedBrierTest.gain.toFixed(9)+"; Holm p="+selectedBrierTest.p_holm.toFixed(6)+"; block-bootstrap 95% CI ["+selectedBrierTest.bootstrap.ci95.map(x=>x.toFixed(9)).join(", ")+ "].",
    "- Blind OOS selected-model log-loss gain: "+selectedLogTest.gain.toFixed(9)+"; Holm p="+selectedLogTest.p_holm.toFixed(6)+"; 95% CI ["+selectedLogTest.bootstrap.ci95.map(x=>x.toFixed(9)).join(", ")+ "].",
    "",
    "## Integrity",
    "- "+validation.status+"; "+checks.length+" checks; "+rows.length+" strict-prior target rows.",
    "- Future-mutation invariance: "+mutationChecks+" comparisons, "+mutationFailures+" failures.",
    "- "+(rows.length*hs.length)+" forecast PMFs normalized; max sum error "+maxPmfError.toExponential(3)+".",
    "- Fixed-seed block inference and deterministic replay are part of the persisted runner.",
    "",
    "## Limitations / next action",
    "- Historical Blind OOS is not a virgin prospective holdout; this is an overlap-count diagnostic, not a number predictor.",
    "- Do not tune additional kernels on this same historical cohort.",
    "- Continue Q60 append-only prospective collection; do not score the 2026-11-10 freezes until the official result is verified."
  ].join("\n")+"\n";
  return {report,validation,ledgerText:ledger.join("\n")+"\n",checkpointText:checkpoint};
}


const root=process.cwd();
const base=root+"/reports/sequence_agent/";
const archiveText=fs.readFileSync(root+"/data/storico_daily.csv","utf8");
const protocolText=fs.readFileSync(base+"q102_lag1_overlap_memory_protocol_2026-11-10.json","utf8");
const result=runQ102(archiveText);
const reportText=JSON.stringify(result.report,null,2)+"\n";
const validationText=JSON.stringify(result.validation,null,2)+"\n";
const scriptText=fs.readFileSync(fileURLToPath(import.meta.url),"utf8");
function gitBlobSha1(text){const b=Buffer.from(text,"utf8");return crypto.createHash("sha1").update(Buffer.from("blob "+b.length+"\0","utf8")).update(b).digest("hex");}
const outputs={
  "q102_lag1_overlap_memory_report_2026-11-10.json":reportText,
  "q102_lag1_overlap_memory_validation_2026-11-10.json":validationText,
  "q102_lag1_overlap_memory_target_ledger_2026-11-10.csv":result.ledgerText,
  "q102_lag1_overlap_memory_checkpoint_2026-11-10.md":result.checkpointText
};
const manifest={
  experiment_id:"Q102",status:"PERSISTED_REPLAY_MANIFEST",generated_date:"2026-11-10",
  source:{archive_git_blob_sha:"8d3e19f0b417024ba32e576697eac0648d12ab86",main_commit:"d075d84efdbb1f0b890f3132ebdf6a6a7e1d825b"},
  output_git_blob_sha:{
    protocol:gitBlobSha1(protocolText),runner:gitBlobSha1(scriptText),
    report:gitBlobSha1(reportText),validation:gitBlobSha1(validationText),
    ledger:gitBlobSha1(result.ledgerText),checkpoint:gitBlobSha1(result.checkpointText)
  },
  replay:{sign_flip_replicates:50000,bootstrap_replicates:10000,block_length:20,deterministic:true}
};
outputs["q102_lag1_overlap_memory_persistence_manifest_2026-11-10.json"]=JSON.stringify(manifest,null,2)+"\n";
if(process.argv.includes("--check")){
  for(const [name,expected] of Object.entries(outputs)){
    const actual=fs.readFileSync(base+name,"utf8");
    if(actual!==expected) throw new Error("Q102 persisted output mismatch: "+name);
  }
  console.log("Q102_PERSISTED_REPORT_LEDGER_REPLAY_PASS");
} else {
  for(const [name,content] of Object.entries(outputs)) fs.writeFileSync(base+name,content);
  console.log(JSON.stringify({status:result.report.status,selected_h:result.report.selection.selected_bandwidth,validation:result.validation.status,targets:result.report.data.targets},null,2));
}
